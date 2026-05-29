import os
import re
import json
import logging
import time
from typing import Optional, Iterator, List, Dict, Any, AsyncIterator, TypedDict
from groq import AsyncGroq
from app.config import GROQ_API_KEY, GROQ_MODEL, MAX_TOKENS, TEMPERATURE, MAX_TOOL_ITERATIONS
from app.guardrails import check_content_safety
from tools.geocode import geocode_place
from tools.chart import compute_birth_chart, get_daily_transits
from tools.knowledge import knowledge_lookup

logger = logging.getLogger(__name__)

_client: Optional[AsyncGroq] = None
_init_attempted = False


def _get_client() -> Optional[AsyncGroq]:
    global _client, _init_attempted
    if _client is None and not _init_attempted:
        _init_attempted = True
        if GROQ_API_KEY and GROQ_API_KEY not in ("gsk-your-key-here", ""):
            try:
                _client = AsyncGroq(api_key=GROQ_API_KEY)
            except Exception as e:
                logger.warning(f"Failed to initialize Groq client: {e}")
    return _client


INTENT_SYSTEM_PROMPT = """You are an intent classifier for an astrology assistant. Analyze the user's message and classify it into exactly one intent:

- chart_request: The user wants their birth chart calculated or asks about their birth chart.
- daily_horoscope: The user asks about today's transits, daily horoscope, or current planetary influences.
- general_question: A general astrology question that doesn't require chart calculation or transit data.
- out_of_scope: The message is unrelated to astrology or inappropriate (medical, legal, financial advice, harmful content).

Respond with ONLY the intent name, nothing else."""

REASONER_SYSTEM_PROMPT = """You are AstroAgent, a warm, gentle, and knowledgeable AI astrologer. Your tone is caring, supportive, and spiritual.

You have access to these tools:
1. geocode_place(place_name: str) -> dict with lat, lng, tz. Use this FIRST before computing any chart.
2. compute_birth_chart(birth: dict) -> dict with planets, houses, ascendant, mc. The birth dict must have: date, time (optional, or "unknown"), place (string), lat (float), lng (float), tz (string).
3. get_daily_transits(date_str: str, chart: dict) -> list of transit aspects. Requires a chart already computed.
4. knowledge_lookup(query: str) -> list of knowledge snippets. Use this for questions about signs, planets, houses, aspects.

CRITICAL WORKFLOW FOR CHART REQUESTS:
Step 1: Call geocode_place with just the place name (e.g. "New York, NY")
Step 2: After getting lat/lng/tz from geocode, call compute_birth_chart with birth dict containing date, time, place, lat, lng, tz

RULES:
- Never give medical, legal, or financial advice. If asked, politely decline.
- For chart requests, ALWAYS call geocode_place first, then compute_birth_chart.
- If time is unknown, set time to "unknown" and still compute the chart.
- Keep responses warm but concise (under 300 words typically).
- DO NOT mix text with JSON. Output ONLY ONE of: a function_call OR an assistant_reply.

When you need to use a tool, respond with a JSON function call:
{"function_call": {"name": "tool_name", "arguments": {...}}}

When you're ready to give a final answer to the user, respond with:
{"assistant_reply": "Your warm response here"}

Only use ONE function call at a time. Wait for tool results before proceeding."""


class AgentState(TypedDict):
    session_id: str
    messages: List[Dict[str, Any]]
    birth: Optional[Dict[str, Any]]
    chart: Optional[Dict[str, Any]]
    intent: Optional[str]
    tool_calls: List[Dict[str, Any]]
    current_response: str
    iteration: int
    done: bool
    error: Optional[str]


class AstroAgentGraph:
    def __init__(self):
        self._client = _get_client()
        self._tools = {
            "geocode_place": geocode_place,
            "compute_birth_chart": compute_birth_chart,
            "get_daily_transits": get_daily_transits,
            "knowledge_lookup": knowledge_lookup,
        }

    async def _llm_call(self, messages: list, max_tokens: int = MAX_TOKENS, temperature: float = TEMPERATURE) -> str:
        if self._client is None:
            return "I'm having trouble connecting to the cosmos right now. Please check that a Groq API key is configured."
        response = await self._client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()

    async def classify_intent(self, user_message: str) -> str:
        try:
            content = await self._llm_call(
                messages=[
                    {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message[:500]},
                ],
                max_tokens=20,
                temperature=0.0,
            )
            intent = content.lower()
            valid_intents = ["chart_request", "daily_horoscope", "general_question", "out_of_scope"]
            for vi in valid_intents:
                if vi in intent:
                    return vi
            return "general_question"
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            return "general_question"

    async def reasoner(self, state: AgentState) -> AgentState:
        if state.get("done") or state.get("error"):
            return state

        messages_for_llm = [
            {"role": "system", "content": REASONER_SYSTEM_PROMPT},
        ]

        for msg in state["messages"][-8:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            messages_for_llm.append({"role": role, "content": content})

        try:
            content = await self._llm_call(
                messages=messages_for_llm,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
            )

            # Extract JSON from anywhere in the content using brace balancing
            parsed = None
            json_text = None

            # Look for {"function_call" or {"assistant_reply" 
            start_idx = max(
                content.find('{"function_call"'),
                content.find('{"assistant_reply"'),
            )
            if start_idx >= 0:
                depth = 0
                end_idx = len(content)
                for i in range(start_idx, len(content)):
                    if content[i] == '{':
                        depth += 1
                    elif content[i] == '}':
                        depth -= 1
                        if depth == 0:
                            end_idx = i + 1
                            break
                json_text = content[start_idx:end_idx].strip()
                json_text = re.sub(r'^```(?:json)?\s*', '', json_text)
                json_text = re.sub(r'\s*```$', '', json_text)
                try:
                    parsed = json.loads(json_text)
                except json.JSONDecodeError:
                    pass

            if parsed:
                if "function_call" in parsed:
                    fc = parsed["function_call"]
                    state["current_response"] = json.dumps(fc)
                    return state
                elif "assistant_reply" in parsed:
                    state["current_response"] = parsed["assistant_reply"]
                    state["done"] = True
                    return state

            state["current_response"] = content
            state["done"] = True
            return state

        except Exception as e:
            logger.error(f"Reasoner error: {e}")
            state["error"] = "I'm having trouble answering right now. Please try again."
            state["done"] = True
            return state

    def execute_tool(self, state: AgentState) -> AgentState:
        try:
            fc = json.loads(state["current_response"])
            tool_name = fc.get("name", "")
            arguments = fc.get("arguments", {})

            # Normalize: LLM may nest arguments under "birth" or "birth_info"
            if tool_name == "compute_birth_chart":
                nested = arguments.get("birth") or arguments.get("birth_info")
                if isinstance(nested, dict):
                    arguments = nested
                # Merge in birth data from state if available
                if state.get("birth"):
                    for k, v in state["birth"].items():
                        if k not in arguments or arguments.get(k) is None:
                            arguments[k] = v

            if tool_name not in self._tools:
                state["error"] = f"Unknown tool: {tool_name}"
                state["done"] = True
                return state

            start = time.time()
            tool_fn = self._tools[tool_name]
            result = tool_fn(**arguments)
            latency_ms = int((time.time() - start) * 1000)

            tool_log = {
                "name": tool_name,
                "input": arguments,
                "output": result,
                "latency_ms": latency_ms,
            }
            state["tool_calls"].append(tool_log)

            if tool_name == "geocode_place" and "error" not in result:
                state["birth"] = state.get("birth", {})
                state["birth"]["lat"] = result.get("lat")
                state["birth"]["lng"] = result.get("lng")
                state["birth"]["tz"] = result.get("tz")
            elif tool_name == "compute_birth_chart" and "error" not in result:
                state["chart"] = result
            elif tool_name == "get_daily_transits":
                pass

            result_msg = {
                "role": "system",
                "content": f"Tool '{tool_name}' result: {json.dumps(result)}",
            }
            state["messages"].append(result_msg)
            state["iteration"] += 1

            if state["iteration"] >= MAX_TOOL_ITERATIONS:
                state["current_response"] = "I'm sorry, I need more time to answer this fully — let's continue later."
                state["done"] = True

            return state

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Tool execution parse error: {e}")
            state["current_response"] = state.get("current_response", "")
            state["done"] = True
            return state
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            state["error"] = "I'm having trouble calculating the chart right now, please try again later."
            state["done"] = True
            return state

    async def run_stream(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        birth: Optional[Dict[str, Any]] = None,
        chart: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        state: AgentState = {
            "session_id": session_id,
            "messages": list(messages),
            "birth": birth or {},
            "chart": chart,
            "intent": None,
            "tool_calls": [],
            "current_response": "",
            "iteration": 0,
            "done": False,
            "error": None,
        }

        last_user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "")
                break

        safe, fallback = check_content_safety(last_user_msg)
        if not safe:
            yield {"type": "token", "content": fallback}
            yield {"type": "debug", "intent": "out_of_scope"}
            return

        intent = await self.classify_intent(last_user_msg)
        state["intent"] = intent
        yield {"type": "debug", "intent": intent}

        if intent == "out_of_scope":
            yield {"type": "token", "content": "I'm sorry, I can't help with that. I'm here to assist with astrology-related questions."}
            return

        # For chart requests, auto-extract and auto-chain: extract → geocode → compute
        if intent == "chart_request" and not state["chart"]:
            birth_info = self._extract_birth_info(last_user_msg)
            if birth_info and birth_info.get("place") and birth_info.get("date"):
                state["birth"] = {**state["birth"], **birth_info}

                # Step 1: Geocode
                yield {"type": "tool_start", "tool": "geocode_place"}
                geo_result = self._tools["geocode_place"](birth_info["place"])
                state["tool_calls"].append({
                    "name": "geocode_place", "input": {"place_name": birth_info["place"]},
                    "output": geo_result, "latency_ms": 0,
                })
                yield {"type": "tool_end", "tool": "geocode_place", "result": geo_result, "latency_ms": 0}

                if "error" not in geo_result:
                    state["birth"]["lat"] = geo_result["lat"]
                    state["birth"]["lng"] = geo_result["lng"]
                    state["birth"]["tz"] = geo_result["tz"]

                    # Step 2: Compute chart
                    yield {"type": "tool_start", "tool": "compute_birth_chart"}
                    chart_result = self._tools["compute_birth_chart"](state["birth"])
                    chart_latency = 0
                    state["tool_calls"].append({
                        "name": "compute_birth_chart", "input": state["birth"],
                        "output": chart_result, "latency_ms": 0,
                    })
                    yield {"type": "tool_end", "tool": "compute_birth_chart", "result": chart_result, "latency_ms": 0}

                    if "error" not in chart_result:
                        state["chart"] = chart_result
                        # Inject chart summary for the LLM
                        chart_data = {k: v for k, v in chart_result.items() if k not in ("birth_date", "birth_time", "birth_place")}
                        state["messages"].append({
                            "role": "system",
                            "content": f"CHART COMPUTED. Data: {json.dumps(chart_data)}. Give a warm interpretation now. DO NOT call any more tools."
                        })
                    else:
                        state["messages"].append({"role": "system", "content": f"Chart error: {chart_result.get('error')}. Explain this to the user."})
                else:
                    state["messages"].append({"role": "system", "content": f"Could not find location: {birth_info['place']}"})

                state["iteration"] += 2

                # Chart computed — generate response directly, skip reasoning
                if state["chart"]:
                    yield {"type": "token", "content": self._generate_chart_response(state["chart"])}
                    return

        while not state["done"] and state["iteration"] <= MAX_TOOL_ITERATIONS:
            state = await self.reasoner(state)

            if state.get("error"):
                yield {"type": "error", "content": state["error"]}
                return

            if state["done"]:
                yield {"type": "token", "content": state["current_response"]}
                return

            fc = None
            try:
                fc = json.loads(state["current_response"])
            except json.JSONDecodeError:
                yield {"type": "token", "content": state["current_response"]}
                return

            if "name" in fc and "arguments" in fc:
                tool_name = fc["name"]
                yield {"type": "tool_start", "tool": tool_name}
                state = self.execute_tool(state)

                # After tool execution, generate response directly instead of LLM reasoning
                last_tool = state["tool_calls"][-1] if state["tool_calls"] else {}
                yield {"type": "tool_end", "tool": tool_name, "result": last_tool.get("output"), "latency_ms": last_tool.get("latency_ms", 0)}

                if state.get("done"):
                    yield {"type": "token", "content": state["current_response"]}
                    return

                if tool_name == "knowledge_lookup":
                    result = last_tool.get("output", [])
                    if isinstance(result, list) and result:
                        last_user_msg = next(
                            (m["content"] for m in reversed(state["messages"]) if m.get("role") == "user"),
                            ""
                        )
                        yield {"type": "token", "content": self._synthesize_knowledge(last_user_msg, result)}
                        return

                if tool_name == "get_daily_transits":
                    result = last_tool.get("output", [])
                    yield {"type": "token", "content": self._generate_transit_response(result)}
                    return
            else:
                state["done"] = True
                yield {"type": "token", "content": state["current_response"]}

        if state["iteration"] >= MAX_TOOL_ITERATIONS and not state["done"]:
            yield {"type": "token", "content": "I'm sorry, I need more time to answer this fully — let's continue later."}

    @staticmethod
    def _generate_transit_response(transits: list) -> str:
        if not transits or (len(transits) == 1 and "error" in transits[0]):
            return (
                "## Daily Transits\n\n"
                "I don't have enough chart data to calculate your transits yet. "
                "Please share your birth details first — date, time, and place — "
                "and I'll compute your chart, then we can look at today's transits together.\n\n"
                "---\n*Try: \"My birth: 1990-05-15 08:30 New York, NY\"*"
            )

        lines = ["## Today's Transits\n"]
        for t in transits[:8]:
            lines.append(f"- **{t['planet']}** {t['aspect']} your natal **{t['natal_planet']}** (orb: {t['orb']:.1f}°)")
        lines.append("\n---\n*Transits show how current planetary positions interact with your birth chart.*")
        return "\n".join(lines)

    @staticmethod
    def _synthesize_knowledge(query: str, snippets: List[str]) -> str:
        query_lower = query.lower()

        # Extract key topics from query
        topics = []
        for keyword in ["saturn", "jupiter", "mars", "venus", "mercury", "moon", "sun",
                       "neptune", "uranus", "pluto", "aries", "taurus", "gemini", "cancer",
                       "leo", "virgo", "libra", "scorpio", "sagittarius", "capricorn",
                       "aquarius", "pisces", "conjunction", "trine", "square", "opposition",
                       "sextile", "return", "retrograde"]:
            if keyword in query_lower:
                topics.append(keyword.title())

        slug = ", ".join(topics[:3]) if topics else "Astrology"

        # Build clean structured response from snippets
        cleaned = []
        for s in snippets[:3]:
            s = re.sub(r'^#+\s*', '', s, flags=re.MULTILINE)
            s = s.replace('\n', ' ').strip()
            s = re.sub(r'\s+', ' ', s)
            # Truncate at sentence boundary
            if len(s) > 300:
                s = s[:300].rsplit('.', 1)[0] + '.'
            cleaned.append(s)

        body = "\n\n".join(f"• {c}" for c in cleaned)
        return (
            f"## {slug}\n\n"
            f"{body}\n\n"
            f"---\n\n"
            f"_Would you like me to elaborate on any of these points, or explore related topics?_"
        )

    @staticmethod
    def _generate_chart_response(chart: Dict[str, Any]) -> str:
        signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                 "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
        emojis = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]
        elements = {"Aries": "Fire 🔥", "Taurus": "Earth 🌿", "Gemini": "Air 💨", "Cancer": "Water 🌊",
                    "Leo": "Fire 🔥", "Virgo": "Earth 🌿", "Libra": "Air 💨", "Scorpio": "Water 🌊",
                    "Sagittarius": "Fire 🔥", "Capricorn": "Earth 🌿", "Aquarius": "Air 💨", "Pisces": "Water 🌊"}
        modalities = {"Aries": "Cardinal", "Taurus": "Fixed", "Gemini": "Mutable",
                      "Cancer": "Cardinal", "Leo": "Fixed", "Virgo": "Mutable",
                      "Libra": "Cardinal", "Scorpio": "Fixed", "Sagittarius": "Mutable",
                      "Capricorn": "Cardinal", "Aquarius": "Fixed", "Pisces": "Mutable"}

        def sign_of(lon):
            return signs[int(lon // 30) % 12]

        def emoji_for(lon):
            return emojis[int(lon // 30) % 12]

        planets = chart.get("planets", {})
        asc = chart.get("ascendant", 0)
        mc = chart.get("mc", 0)
        houses = chart.get("houses", {})
        birth_date = chart.get("birth_date", "")
        birth_time = chart.get("birth_time", "unknown")
        birth_place = chart.get("birth_place", "")

        asc_sign = sign_of(asc)
        sun_lon = planets.get("Sun", 0)
        sun_sign = sign_of(sun_lon)
        moon_lon = planets.get("Moon", 0)
        moon_sign = sign_of(moon_lon)

        # Build aspects summary
        major_aspects = []
        aspect_angles = {"conjunction": 0, "sextile": 60, "square": 90, "trine": 120, "opposition": 180}
        planet_pairs_checked = set()
        for p1_name, p1_lon in planets.items():
            for p2_name, p2_lon in planets.items():
                if p1_name >= p2_name:
                    continue
                diff = abs(p1_lon - p2_lon)
                if diff > 180:
                    diff = 360 - diff
                for asp_name, asp_angle in aspect_angles.items():
                    orb = 8 if asp_name in ("conjunction", "opposition") else 7 if asp_name == "trine" else 6
                    if abs(diff - asp_angle) <= orb:
                        pair_key = f"{min(p1_name, p2_name)}_{max(p1_name, p2_name)}_{asp_name}"
                        if pair_key not in planet_pairs_checked:
                            major_aspects.append(f"**{p1_name}** {asp_name} **{p2_name}** ({diff:.1f}°)")
                            planet_pairs_checked.add(pair_key)

        # Key aspects (limit to important ones)
        key_planets = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
        key_aspects = [a for a in major_aspects if any(p in a for p in key_planets)][:8]
        if not key_aspects and major_aspects:
            key_aspects = major_aspects[:6]

        # Planet table: order matters
        planet_order = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
        planet_lines = []
        for p_name in planet_order:
            if p_name in planets:
                lon = planets[p_name]
                s = sign_of(lon)
                e = emoji_for(lon)
                deg = lon % 30
                planet_lines.append(f"| {e} **{p_name}** | {s} | {deg:.1f}° |")

        planet_table = (
            "| Planet | Sign | Position |\n|--------|------|----------|\n"
            + "\n".join(planet_lines)
        )

        # House emphasis
        house_stresses = []
        for house_num, cusp in houses.items():
            count = 0
            for p_lon in planets.values():
                h_cusp = cusp
                next_cusp = houses.get((house_num % 12) + 1, (cusp + 30) % 360)
                if h_cusp < next_cusp:
                    if h_cusp <= p_lon < next_cusp:
                        count += 1
                else:
                    if p_lon >= h_cusp or p_lon < next_cusp:
                        count += 1
            if count >= 2:
                house_stresses.append(f"**House {house_num}** ({count} planets)")

        house_line = ", ".join(house_stresses[:4]) if house_stresses else "_Planets spread across houses_"

        sections = [
            f"## Your Birth Chart\n",
            f"**{birth_date}** — {birth_time} — {birth_place}\n",
            f"### The Big Three\n",
            f"- **Sun** in {emoji_for(sun_lon)} **{sun_sign}** — Your core identity, ego, and life force.",
            f"- **Moon** in {emoji_for(moon_lon)} **{moon_sign}** — Your emotional world, instincts, and inner self.",
            f"- **Ascendant** {emoji_for(asc)} **{asc_sign}** — Your outward personality, how others first see you.\n",
            f"*{sun_sign} is a {modalities[sun_sign]} {elements[sun_sign]} sign. "
            f"{moon_sign} is a {modalities[moon_sign]} {elements[moon_sign]} sign.*\n",
            f"### Planetary Positions\n",
            planet_table + "\n",
        ]

        if key_aspects:
            sections.append("### Key Aspects\n")
            for a in key_aspects:
                sections.append(f"- {a}")
            sections.append("")

        sections.append(f"### House Activity\n")
        sections.append(f"{house_line}\n")
        sections.append("---\n")
        sections.append("*Ask me: \"What does my Sun in " + sun_sign + " mean?\" or \"Tell me about my Moon in " + moon_sign + "\"*")

        return "\n".join(sections)

    @staticmethod
    def _extract_birth_info(text: str) -> Optional[Dict[str, Any]]:
        text = text.strip()
        # Match date: YYYY-MM-DD
        bday_match = re.search(r'(\d{4}-\d{1,2}-\d{1,2})', text)
        if not bday_match:
            return None
        date_str = bday_match.group(1)

        # Match time: HH:MM
        time_str = None
        time_match = re.search(r'(\d{1,2}:\d{2})', text)
        if time_match:
            time_str = time_match.group(1)
        elif re.search(r'(?:time\s+)?unknown|no\s+time', text, re.IGNORECASE):
            time_str = "unknown"

        # Extract place: everything after date+time
        remainder = text[bday_match.end():]
        if time_match and time_match.start() > bday_match.start():
            remainder = text[max(bday_match.end(), time_match.end()):]

        place = remainder.strip().lstrip(",;:- ").rstrip(".,;!?")
        if not place or len(place) < 2:
            return {"date": date_str, "time": time_str or "unknown", "place": None}

        return {"date": date_str, "time": time_str or "unknown", "place": place}
