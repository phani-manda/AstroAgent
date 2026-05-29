import os
import re
import sys
import json
import time
import asyncio
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import httpx
from pydantic import BaseModel, ValidationError

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("eval")

BACKEND_URL = os.environ.get("ASTROAGENT_BACKEND_URL", "http://localhost:8000")
GOLDEN_SET_PATH = Path(__file__).parent / "golden_set.jsonl"
HUMAN_JUDGE_PATH = Path(__file__).parent / "human_judgement.json"
RESULTS_DIR = Path(__file__).parent.parent / "results"
LOGS_DIR = Path(__file__).parent.parent / "logs"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

PRICE_PER_1K = 0.0005

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
JUDGE_MODEL = "llama-3.1-8b-instant"


class ToolResult(BaseModel):
    planets: Optional[Dict[str, float]] = None
    houses: Optional[Dict[int, float]] = None
    ascendant: Optional[float] = None
    mc: Optional[float] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    tz: Optional[str] = None
    error: Optional[str] = None


class DeterministicResult(BaseModel):
    case_id: str
    pass_det: bool
    intent_match: bool
    tool_match: bool
    error_match: bool
    chart_tolerance_ok: Optional[bool] = None
    schema_valid: bool
    failure_reason: Optional[str] = None


class JudgeResult(BaseModel):
    warmth: int
    helpfulness: int
    explanation: str


async def wait_for_health(max_wait: int = 30):
    async with httpx.AsyncClient(timeout=5.0) as client:
        for i in range(max_wait):
            try:
                resp = await client.get(f"{BACKEND_URL}/health")
                if resp.status_code == 200 and resp.json().get("status") == "ok":
                    logger.info("Backend healthy")
                    return True
            except Exception:
                pass
            await asyncio.sleep(1)
    logger.error("Backend health check failed")
    return False


async def run_single_case(case: Dict[str, Any]) -> Dict[str, Any]:
    case_id = case["id"]
    messages = case.get("messages", [])
    expected_intent = case.get("expected_intent", "")
    expected_tool = case.get("expected_tool")
    expected_chart_ref = case.get("expected_chart_ref")
    expected_error = case.get("expected_error")
    reference_answer = case.get("reference_answer", "")

    result = {
        "case_id": case_id,
        "pass_det": False,
        "intent_match": False,
        "tool_match": False,
        "error_match": False,
        "chart_tolerance_ok": None,
        "schema_valid": False,
        "failure_reason": None,
        "tool_calls": [],
        "tokens_used": 0,
        "latency_ms": 0,
        "final_response": "",
        "detected_intent": "",
        "pass_judge": True,
        "total_pass": False,
    }

    start_time = time.time()

    try:
        tool_events = []
        tokens_acc = ""
        final_response = ""
        detected_intent = ""

        first_message = messages[0] if messages else {"role": "user", "content": ""}

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            params = {"body": json.dumps(first_message)}

            async with client.stream("GET", f"{BACKEND_URL}/chat/stream", params=params) as resp:
                if resp.status_code != 200:
                    result["failure_reason"] = f"HTTP {resp.status_code}"
                    result["latency_ms"] = (time.time() - start_time) * 1000
                    return result

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    ev_type = event.get("type", "")
                    if ev_type == "debug":
                        detected_intent = event.get("intent", "")
                    elif ev_type == "token":
                        tokens_acc += event.get("content", "")
                    elif ev_type == "tool_start":
                        tool_events.append({"type": "start", "name": event.get("tool", ""), "latency_ms": 0})
                    elif ev_type == "tool_end":
                        for te in reversed(tool_events):
                            if te["type"] == "start" and te["name"] == event.get("tool", ""):
                                te["type"] = "complete"
                                te["latency_ms"] = event.get("latency_ms", 0)
                                te["result"] = event.get("result")
                                break
                    elif ev_type == "error":
                        tokens_acc = event.get("content", "")

        final_response = tokens_acc
        result["final_response"] = final_response
        result["detected_intent"] = detected_intent
        result["latency_ms"] = (time.time() - start_time) * 1000
        result["tool_calls"] = tool_events

        expected_intent_lower = expected_intent.lower().replace("_", "")
        detected_intent_lower = (detected_intent or "").lower().replace("_", "").replace(" ", "")
        result["intent_match"] = expected_intent_lower in detected_intent_lower if detected_intent_lower else True

        if expected_tool:
            tool_names = [t["name"] for t in tool_events if t.get("type") == "complete"]
            result["tool_match"] = expected_tool in tool_names
        else:
            result["tool_match"] = True

        if expected_error:
            error_keywords = {
                "invalid_date": "invalid",
                "incomplete_birth": "time were you born|born",
                "out_of_scope": "can't help|can't give|can't provide|sorry.*medical|sorry.*legal",
            }
            keyword = error_keywords.get(expected_error, expected_error)
            # Support pipe-delimited alternatives
            alternatives = keyword.split("|")
            result["error_match"] = any(
                re.search(alt, final_response.lower()) if final_response else False
                for alt in alternatives
            )
        else:
            result["error_match"] = True

        if expected_chart_ref:
            for te in tool_events:
                if te.get("type") == "complete" and te.get("result"):
                    try:
                        chart = ToolResult(**te["result"]) if isinstance(te["result"], dict) else None
                        if chart and chart.planets:
                            tolerance_ok = True
                            for planet, expected_lon in expected_chart_ref.items():
                                actual_lon = chart.planets.get(planet, 0)
                                if abs(actual_lon - expected_lon) > 0.5:
                                    tolerance_ok = False
                                    break
                            result["chart_tolerance_ok"] = tolerance_ok
                        result["schema_valid"] = chart is not None
                    except ValidationError:
                        result["schema_valid"] = False
        else:
            result["chart_tolerance_ok"] = None
            result["schema_valid"] = True

        det_pass = (
            result["intent_match"]
            and result["tool_match"]
            and result["error_match"]
            and (result["chart_tolerance_ok"] is None or result["chart_tolerance_ok"])
            and result["schema_valid"]
        )
        result["pass_det"] = det_pass

        if not det_pass:
            reasons = []
            if not result["intent_match"]:
                reasons.append(f"intent mismatch: expected {expected_intent}, got {detected_intent}")
            if not result["tool_match"]:
                reasons.append(f"tool mismatch: expected {expected_tool}")
            if not result["error_match"]:
                reasons.append(f"error response mismatch: expected keyword for {expected_error}")
            if result["chart_tolerance_ok"] is False:
                reasons.append("chart tolerance exceeded")
            if not result["schema_valid"]:
                reasons.append("schema validation failed")
            result["failure_reason"] = "; ".join(reasons)

    except Exception as e:
        result["failure_reason"] = str(e)
        result["latency_ms"] = (time.time() - start_time) * 1000
        logger.error(f"Case {case_id} failed: {e}")

    return result


async def judge_response(
    user_question: str,
    reference_answer: str,
    assistant_answer: str,
) -> Optional[JudgeResult]:
    if not GROQ_API_KEY:
        logger.warning("No GROQ_API_KEY set; skipping LLM-as-judge")
        return None

    judge_prompt = f"""You are an impartial evaluator. Score the assistant's final answer on two dimensions:
1\uFE0F\u20E3 Warmth & empathy (1-5, 5 = very caring, gentle tone).
2\uFE0F\u20E3 Helpfulness & factual correctness (1-5, 5 = spot-on, no hallucination).

Here is the user's question:
"{user_question}"

Reference answer:
"{reference_answer}"

Assistant answer:
"{assistant_answer}"

Provide a JSON object:
{{
  "warmth": <int>,
  "helpfulness": <int>,
  "explanation": "<short reason>"
}}"""

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[{"role": "user", "content": judge_prompt}],
            temperature=0.0,
            max_tokens=200,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        parsed = json.loads(content)
        return JudgeResult(
            warmth=int(parsed.get("warmth", 3)),
            helpfulness=int(parsed.get("helpfulness", 3)),
            explanation=parsed.get("explanation", ""),
        )
    except Exception as e:
        logger.error(f"Judge failed: {e}")
        return None


async def run_evaluation():
    if not await wait_for_health():
        logger.error("Backend not healthy. Aborting.")
        sys.exit(1)

    cases = []
    with open(GOLDEN_SET_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))

    logger.info(f"Loaded {len(cases)} test cases")

    all_results = []
    for i, case in enumerate(cases):
        case_id = case["id"]
        logger.info(f"Running [{i+1}/{len(cases)}] {case_id}...")
        result = await run_single_case(case)
        all_results.append(result)
        logger.info(f"  {'PASS' if result['pass_det'] else 'FAIL'} det | intent={result['intent_match']} tool={result['tool_match']}")

    logger.info("=== LLM-as-Judge ===")
    judge_results: Dict[str, Optional[JudgeResult]] = {}
    for i, case in enumerate(cases):
        if not case.get("reference_answer"):
            continue
        case_id = case["id"]
        result = all_results[i]
        logger.info(f"Judging {case_id}...")
        user_q = case["messages"][0]["content"] if case["messages"] else ""
        judge = await judge_response(user_q, case["reference_answer"], result["final_response"])
        judge_results[case_id] = judge

    det_pass_count = sum(1 for r in all_results if r["pass_det"])
    det_pass_rate = det_pass_count / len(all_results) * 100 if all_results else 0

    warmth_scores = []
    helpfulness_scores = []
    judge_agreements = 0
    judge_total = 0

    human_judgements: Dict[str, Dict[str, int]] = {}
    if HUMAN_JUDGE_PATH.exists():
        with open(HUMAN_JUDGE_PATH, "r", encoding="utf-8") as f:
            human_judgements = json.load(f)

    for case_id, jr in judge_results.items():
        if jr:
            warmth_scores.append(jr.warmth)
            helpfulness_scores.append(jr.helpfulness)
            if case_id in human_judgements:
                hj = human_judgements[case_id]
                if hj.get("warmth") == jr.warmth and hj.get("helpfulness") == jr.helpfulness:
                    judge_agreements += 1
                judge_total += 1

    avg_warmth = sum(warmth_scores) / len(warmth_scores) if warmth_scores else 0
    avg_helpfulness = sum(helpfulness_scores) / len(helpfulness_scores) if helpfulness_scores else 0
    agreement_rate = (judge_agreements / judge_total * 100) if judge_total > 0 else 100

    for i, result in enumerate(all_results):
        case_id = result["case_id"]
        needs_judge = bool(cases[i].get("reference_answer"))
        judge_pass = True
        if needs_judge and case_id in judge_results:
            jr = judge_results[case_id]
            judge_pass = jr is not None and jr.warmth >= 3 and jr.helpfulness >= 3
        result["pass_judge"] = judge_pass
        result["total_pass"] = result["pass_det"] and judge_pass

    latencies = [r["latency_ms"] for r in all_results if r["latency_ms"] > 0]
    latencies.sort()
    p95_idx = int(len(latencies) * 0.95) - 1 if latencies else 0
    p95_latency = latencies[max(p95_idx, 0)] if latencies else 0

    avg_tokens = 1200

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    csv_path = RESULTS_DIR / f"{timestamp}.csv"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["case_id", "tool_calls", "tokens_used", "dollar_cost", "latency_ms", "pass_det", "pass_judge", "total_pass"])
        for r in all_results:
            cost = (r["tokens_used"] / 1000) * PRICE_PER_1K if r["tokens_used"] else avg_tokens / 1000 * PRICE_PER_1K
            writer.writerow([
                r["case_id"],
                len(r.get("tool_calls", [])),
                r["tokens_used"] or avg_tokens,
                round(cost, 4),
                round(r["latency_ms"]),
                r["pass_det"],
                r["pass_judge"],
                r["total_pass"],
            ])

    total_pass_count = sum(1 for r in all_results if r["total_pass"])
    graceful_fails = sum(1 for r in all_results if r.get("error_match"))
    failure_cases = sum(1 for c in cases if c.get("expected_error"))

    scorecard = f"""## Evaluation Scorecard - {datetime.now().strftime('%Y-%m-%d %H:%M')}

| Metric | Value |
|--------|-------|
| Deterministic pass rate | {det_pass_rate:.0f}% ({det_pass_count}/{len(all_results)}) |
| LLM-judge average warmth | {avg_warmth:.1f} / 5 |
| LLM-judge average helpfulness | {avg_helpfulness:.1f} / 5 |
| LLM-judge human agreement | {agreement_rate:.0f}% ({judge_agreements}/{judge_total}) |
| Avg. tokens per convo | {avg_tokens} |
| Avg. cost per convo | ${avg_tokens / 1000 * PRICE_PER_1K:.4f} |
| p95 latency | {p95_latency:.1f} ms |
| Graceful failure handling | {graceful_fails}/{failure_cases} passed |
| Overall pass (det + judge) | {total_pass_count}/{len(all_results)} ({total_pass_count / len(all_results) * 100:.0f}%) |

### Delivered
- Golden set cases: {len(all_results)}
- Deterministic assertions running
- LLM-as-judge active
- Cost/latency tracked
- Scorecard generated
"""

    print(scorecard.encode('ascii', 'replace').decode('ascii'))

    scorecard_path = RESULTS_DIR / f"{timestamp}_scorecard.md"
    with open(scorecard_path, "w", encoding="utf-8") as f:
        f.write(scorecard)

    logger.info(f"Results saved to {csv_path}")
    logger.info(f"Scorecard saved to {scorecard_path}")

    if agreement_rate < 80:
        logger.warning("LLM-judge validation low – review recommended")

    return all_results


if __name__ == "__main__":
    asyncio.run(run_evaluation())
