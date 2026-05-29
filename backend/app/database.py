import os
import sqlite3
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlmodel import Session, SQLModel, create_engine
from app.config import SQLITE_DB_PATH, LOG_DIR
from app.models import Conversation, Message

os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

engine = create_engine(f"sqlite:///{SQLITE_DB_PATH}", echo=False)


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    return Session(engine)


def get_conversation(session_id: str) -> Optional[Conversation]:
    with get_session() as session:
        return session.get(Conversation, session_id)


def create_conversation() -> Conversation:
    conv = Conversation(
        id=str(uuid.uuid4()),
        messages=[],
        birth=None,
        chart=None,
        updated_at=datetime.now(timezone.utc),
    )
    with get_session() as session:
        session.add(conv)
        session.commit()
        session.refresh(conv)
    return conv


def save_messages(session_id: str, messages: List[Dict[str, Any]]):
    with get_session() as session:
        conv = session.get(Conversation, session_id)
        if conv:
            conv.messages = messages
            conv.updated_at = datetime.utcnow()
            session.add(conv)
            session.commit()


def save_birth(session_id: str, birth: Dict[str, Any]):
    with get_session() as session:
        conv = session.get(Conversation, session_id)
        if conv:
            conv.birth = birth
            conv.updated_at = datetime.utcnow()
            session.add(conv)
            session.commit()


def save_chart(session_id: str, chart: Dict[str, Any]):
    with get_session() as session:
        conv = session.get(Conversation, session_id)
        if conv:
            conv.chart = chart
            conv.updated_at = datetime.utcnow()
            session.add(conv)
            session.commit()


def get_cached_chart(session_id: str) -> Optional[Dict[str, Any]]:
    conv = get_conversation(session_id)
    if conv:
        return conv.chart
    return None


def get_birth(session_id: str) -> Optional[Dict[str, Any]]:
    conv = get_conversation(session_id)
    if conv:
        return conv.birth
    return None


def delete_conversation(session_id: str):
    with get_session() as session:
        conv = session.get(Conversation, session_id)
        if conv:
            session.delete(conv)
            session.commit()


def log_request(
    request_id: str,
    session_id: str,
    timestamp: str,
    token_count: int,
    tool_calls: List[Dict[str, Any]],
    latency_ms: float,
    error: Optional[str] = None,
):
    log_entry = {
        "request_id": request_id,
        "session_id": session_id,
        "timestamp": timestamp,
        "token_count": token_count,
        "tool_calls": tool_calls,
        "latency_ms": latency_ms,
        "error": error,
    }
    log_file = os.path.join(LOG_DIR, f"requests_{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")
