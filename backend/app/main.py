import json
import logging
import uuid
import time
from typing import Optional
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_ORIGINS
from app.database import (
    init_db,
    get_conversation,
    create_conversation,
    save_messages,
    save_birth,
    save_chart,
    delete_conversation,
    log_request,
)
from app.agent import AstroAgentGraph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="AstroAgent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent_graph = AstroAgentGraph()


@app.on_event("startup")
async def startup():
    init_db()
    logger.info("AstroAgent startup complete")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/reset")
async def reset(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    delete_conversation(session_id)
    return {"msg": "reset"}


@app.get("/chat/stream")
async def chat_stream(
    request: Request,
    session_id: Optional[str] = Query(default=None),
):
    try:
        params = dict(request.query_params)
        body_str = params.get("body", "")
    except Exception:
        body_str = ""

    if not body_str:
        raise HTTPException(status_code=400, detail="body parameter required (JSON-encoded message)")

    try:
        user_message = json.loads(body_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in body param")

    request_id = str(uuid.uuid4())
    start_time = time.time()

    if session_id:
        conv = get_conversation(session_id)
        if not conv:
            conv = create_conversation()
            session_id = conv.id
        session_id = conv.id
    else:
        conv = create_conversation()
        session_id = conv.id

    messages = list(conv.messages) if conv.messages else []
    messages.append({
        "role": user_message.get("role", "user"),
        "content": user_message.get("content", ""),
        "created_at": user_message.get("created_at", ""),
    })

    birth = conv.birth
    chart = conv.chart

    save_messages(session_id, messages)

    async def event_generator():
        collected_tokens = []
        tool_calls_list = []
        final_intent = None
        final_error = None
        token_count = 0

        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"

        try:
            async for event in agent_graph.run_stream(session_id, messages, birth, chart):
                event_type = event.get("type")
                if event_type == "debug":
                    final_intent = event.get("intent")
                elif event_type == "error":
                    final_error = event.get("content")
                    yield f"data: {json.dumps(event)}\n\n"
                elif event_type == "token":
                    content = event.get("content", "")
                    collected_tokens.append(content)
                    chunks = [content[i:i+10] for i in range(0, len(content), 10)]
                    for chunk in chunks:
                        yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                elif event_type == "tool_start":
                    tool_calls_list.append({"name": event.get("tool"), "start": time.time()})
                    yield f"data: {json.dumps(event)}\n\n"
                elif event_type == "tool_end":
                    yield f"data: {json.dumps(event)}\n\n"
                else:
                    yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': 'An unexpected error occurred. Please try again.'})}\n\n"

        full_response = "".join(collected_tokens)

        if full_response and not final_error:
            messages.append({
                "role": "assistant",
                "content": full_response,
                "created_at": "",
            })
            save_messages(session_id, messages)

        if chart:
            save_chart(session_id, chart)
        if birth:
            save_birth(session_id, birth)

        latency_ms = (time.time() - start_time) * 1000
        log_request(
            request_id=request_id,
            session_id=session_id,
            timestamp=str(time.time()),
            token_count=token_count,
            tool_calls=tool_calls_list,
            latency_ms=latency_ms,
            error=final_error,
        )

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
