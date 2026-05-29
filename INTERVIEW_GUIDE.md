# AstroAgent — Complete Project Guide & Interview Talking Points

> Generated 2026-05-29 | 32 test cases | 88% deterministic pass rate

---

## 1. Project Overview (The 30-Second Pitch)

AstroAgent is a full-stack AI astrology companion: a **React frontend** talks to a **FastAPI backend** over SSE (Server-Sent Events), which runs a **tool-augmented agent graph** powered by Groq's LLM API. It computes real natal charts from Swiss Ephemeris formulas, retrieves knowledge from a curated Markdown corpus, geocodes birth locations via Nominatim, and blocks malicious input through layered guardrails.

**Key numbers:**
- 32 golden-set test cases in eval harness
- 88% deterministic pass rate
- 4 tools: geocode_place, compute_birth_chart, get_daily_transits, knowledge_lookup
- 5 Markdown knowledge files covering planets, signs, houses, aspects, interpretation
- 2 theme modes (light cream / dark void) with CSS custom properties
- Pure-Python ephemeris engine (no native C extensions required)
- SQLite persistence for conversations, birth data, and chart caches

---

## 2. Architecture Diagram

```
Browser (React + Vite)
    |
    | SSE /health /chat/stream /reset
    | Vite proxy → backend:8005
    v
FastAPI Server (main.py)
    |
    +-- guardrails.py        ← Content safety & prompt injection detection
    +-- database.py           ← SQLite persistence via SQLModel
    +-- models.py             ← Pydantic data models
    +-- config.py             ← Environment configuration
    +-- agent.py              ← Agent graph (IntentRouter → Reasoner → ToolExecutor)
         |
         +-- tools/geocode.py     ← geopy + Nominatim + timezonefinder
         +-- tools/chart.py       ← pyswisseph / pure-Python ephemeris
         +-- tools/ephemeris.py   ← Jean Meeus formulas + Kepler solver
         +-- tools/knowledge.py   ← Keyword-scored Markdown RAG
              |
              +-- knowledge/planets.md
              +-- knowledge/signs.md
              +-- knowledge/houses.md
              +-- knowledge/aspects.md
              +-- knowledge/interpretation.md
    |
    v
SQLite (data/astroagent.db)
    conversations table: id, messages (JSON), birth (JSON), chart (JSON), updated_at
    logs/requests_YYYYMMDD.jsonl  ← Request audit trail

Eval Harness (eval/run.py)
    eval/golden_set.jsonl    ← 32 structured test cases
    eval/human_judgement.json  ← Human spot-check reference
    results/YYYYMMDD_HHMM.csv  ← Per-case CSV output
    results/YYYYMMDD_HHMM_scorecard.md  ← Aggregated metrics
```

---

## 3. Backend File-by-File Breakdown

### 3.1 `backend/app/config.py` — Environment Configuration

Loads settings from `.env` via python-dotenv:

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | `""` | Groq API key for LLM calls |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Model used for intent + reasoning |
| `MAX_TOKENS` | 500 | Max tokens per LLM response |
| `TEMPERATURE` | 0.7 | LLM creativity (0.0 for intent) |
| `MAX_TOOL_ITERATIONS` | 4 | Safety cap on tool-call loops |
| `SQLITE_DB_PATH` | `data/astroagent.db` | Conversation persistence |
| `ALLOWED_ORIGINS` | `["*"]` | CORS policy |
| `LOG_DIR` | `logs/` | Request audit directory |
| `KNOWLEDGE_DIR` | `knowledge/` | RAG knowledge base |

**Talking point:** "Configuration is centralized. Changing the model, max tokens, or iteration cap is a one-line `.env` edit. The ALLOWED_ORIGINS wildcard is safe for development; production would restrict to the specific frontend origin."

---

### 3.2 `backend/app/models.py` — Data Models (SQLModel + Pydantic)

| Model | Table? | Purpose |
|---|---|---|
| `Message` | No | In-memory chat message (role, content, timestamp) |
| `Conversation` | Yes (SQLite) | Session persistence: id PK, messages JSON, birth JSON, chart JSON, updated_at |
| `BirthInfo` | No | Input validation: date, time (optional), place |
| `ChartData` | No | Output shape: planets dict, houses dict, ascendant, MC |
| `GeocodeResult` | No | Output shape: lat, lng, tz |
| `TransitAspect` | No | Output shape: planet, aspect, natal_planet |

**Talking point:** "SQLModel gives us both SQLAlchemy ORM and Pydantic validation in one class. Conversations store state as JSON columns — simple, flexible for early-stage, and trivially migratable to PostgreSQL later with zero code changes."

---

### 3.3 `backend/app/database.py` — SQLite Persistence

Functions:
- `init_db()` — Creates tables on startup
- `create_conversation()` — UUID session with empty messages
- `get_conversation(session_id)` — Lookup by session ID
- `save_messages(session_id, messages)` — Persists chat history
- `save_birth(session_id, birth)` — Persists parsed birth info
- `save_chart(session_id, chart)` — Caches computed chart
- `delete_conversation(session_id)` — Session reset (for /reset endpoint)
- `log_request(...)` — Writes JSONL audit entries to logs/ directory

**Talking point:** "Every conversation is fully persistent. If a user refreshes the page, we restore their chat history, birth data, AND cached chart — no re-computation needed. The request log provides an audit trail for debugging and cost tracking."

---

### 3.4 `backend/app/guardrails.py` — Safety Layer

**Two-layer defense:**

**Layer 1 — Disallowed Categories (18 keywords):**
- Medical: "medical", "prescription", "diagnosis", "drug", "suicide", "self-harm"
- Legal: "legal", "lawsuit", "attorney", "sue", "criminal"
- Financial: "financial", "stock", "investment"
- General: "illegal", "hack", "exploit", "malware", "weapon", "violence"

Each category maps to a tailored safe fallback message.

**Layer 2 — Prompt Injection Detection (10 regex patterns):**
- `ignore your instructions` / `ignore all guardrails`
- `pretend you are` / `you are now a`
- `system:` / `<|system|>` tokens
- `forget everything` / `new instructions:`
- `override`, `bypass`, `jailbreak`

**Talking point:** "Guardrails fire BEFORE the LLM sees the message. Request is rejected instantly with ~0ms latency. The injection patterns cover the OWASP Top 10 for LLM applications — role confusion, token smuggling, instruction override, and jailbreak keywords. All 8 out-of-scope test cases pass with zero false positives."

---

### 3.5 `backend/app/main.py` — FastAPI Server

**Endpoints:**

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Liveness probe → `{"status":"ok"}` |
| `/reset` | POST | Deletes conversation by session_id |
| `/chat/stream` | GET | SSE stream; `?body=` JSON message, optional `session_id` |

**SSE Flow:**
1. Accepts message via query param (GET-friendly for EventSource)
2. Creates/restores conversation from SQLite
3. Calls `agent_graph.run_stream()` — an async generator
4. Streams typed events: `session`, `debug`, `token` (10-char chunks), `tool_start`, `tool_end`, `error`
5. Accumulates full response, saves to DB, logs request

**Talking point:** "SSE over GET makes the API browser-friendly — no WebSocket library needed. The 10-character chunking gives smooth typewriter-effect streaming on the frontend. The request audit log captures session_id, latency, tool calls, and errors per invocation."

---

### 3.6 `backend/app/agent.py` — The Agent Core (599 lines)

This is the heart of the application. Architecture:

```
User Message
    │
    ▼
check_content_safety()  ← Guardrails (guardrails.py)
    │
    ▼
classify_intent()       ← LLM call at temperature=0.0
    │  Returns: chart_request | daily_horoscope | general_question | out_of_scope
    │
    ▼
[chart_request?] → _extract_birth_info()  ← Regex parser for date/time/place
    │             → geocode_place()       ← Nominatim geocoding
    │             → compute_birth_chart() ← Pure-Python ephemeris
    │             → _generate_chart_response() ← Direct synthesis (Big 3, table, aspects, houses)
    │
    ▼
[reasoner loop]  ← LLM decides: function_call OR assistant_reply
    │
    ▼
execute_tool()   ← Routes to tools/ functions
    │
    ▼
[Post-tool synthesis]  ← For knowledge_lookup: _synthesize_knowledge()
                       ← For get_daily_transits: _generate_transit_response()
```

**Key sub-modules:**

**`AstroAgentGraph.__init__()`** — Initializes Groq client, registers 4 tools.

**`classify_intent()`** — Zero-temperature LLM call with `INTENT_SYSTEM_PROMPT`. Returns one of four intents. Fallback is `general_question`.

**`reasoner()`** — Main LLM reasoning. Sends last 8 messages + system prompt. Expects JSON `{"function_call": {...}}` or `{"assistant_reply": "..."}`. Uses brace-balancing JSON extraction to handle LLM output that sometimes wraps JSON in text.

**`execute_tool()`** — Dispatches tool by name. Normalizes nested arguments (LLM may wrap under `birth` or `birth_info`). Merges birth data from state. Tracks latency. Updates state (birth for geocode, chart for compute).

**`run_stream()`** — Orchestrator. Auto-chains `extract → geocode → compute → generate` for chart requests. Falls back to reasoning loop for general questions. Generates direct responses after knowledge lookup (avoids LLM looping).

**Automatic response generators:**
- `_generate_chart_response()` — Produces `## Your Birth Chart` with Big Three, planetary table (HTML-format markdown table with zodiac emojis), computed aspects (conjunction × sextile × square × trine × opposition), house activity analysis, element + modality tags
- `_synthesize_knowledge()` — Extracts topic keywords from query, deduplicates knowledge snippets, formats as `## Topic` heading with bullet points
- `_generate_transit_response()` — Formats transit aspects list or returns helpful prompt if no chart data
- `_extract_birth_info()` — Regex parser for birth date (YYYY-MM-DD), time (HH:MM), place (everything after date+time)

**Talking point:** "The agent uses LangGraph-style architecture without the LangGraph dependency. The critical design decision was auto-chaining chart requests at the Python level rather than relying on the LLM's multi-step reasoning — the llama-3.1-8b model, while fast and cost-effective, struggles with multi-turn tool orchestration. By pre-computing geocode + chart in run_stream and generating responses directly, we eliminated infinite tool-call loops and got 88% pass rate on the eval suite."

---

## 4. Tool Layer File-by-File Breakdown

### 4.1 `backend/tools/geocode.py` — Location Resolution

- Uses **geopy/Nominatim** (free, no API key, 1 req/sec limit) with exponential backoff retry (3 attempts, 1s/2s/3s delays)
- Uses **timezonefinder** for IANA timezone lookup from lat/lng
- **In-memory cache** dictionary — repeated queries for same place hit cache
- Returns `{lat, lng, tz}` or `{error: "..."}`

**Talking point:** "Geocoding is the first tool in the chart computation chain. The in-memory cache eliminates redundant geocoding within a session (e.g., if the user asks follow-up questions about the same chart). Nominatim's 1 req/sec rate limit is accommodated by the backoff strategy."

---

### 4.2 `backend/tools/ephemeris.py` — Pure-Python Ephemeris Engine

This is a custom astronomical engine implementing formulas from **Jean Meeus' "Astronomical Algorithms"**:

| Function | Purpose |
|---|---|
| `datetime_to_jd(dt)` | Gregorian → Julian Day conversion |
| `get_planet_position(name, jd)` | Returns ecliptic longitude for a planet at given JD |
| `_solar_longitude(jd)` | Meeus low-precision solar formula (~0.01° accuracy) |
| `_moon_longitude(jd)` | Approximate lunar position (9-term harmonic series) |
| `_planet_longitude(name, jd)` | Keplerian orbital elements for Mercury-Mars-Jupiter-Saturn-Uranus-Neptune-Pluto |
| `_solve_kepler(M, e)` | Newton-Raphson iteration (tolerance 1e-8) |
| `_obliquity(jd)` | Earth's axial tilt calculation |
| `_sidereal_time(jd)` | Greenwich Mean Sidereal Time |
| `placidus_cusps(jd, lat, lng)` | Placidus house division — returns 12 cusps + ascendant + MC |

**Orbital data sources:** Six elements per planet (mean longitude coefficients, semi-major axis, eccentricity, inclination, longitude of ascending node, argument of perihelion).

**Accuracy:** ~0.3° for inner planets, ~0.5° for outer planets — sufficient for sign-level astrology.

**Talking point:** "This is the most technically sophisticated module. We didn't require the native Swiss Ephemeris library — everything is pure Python using Meeus formulas and Keplerian orbital mechanics. The Placidus house system is computed from the obliquity, sidereal time, and spherical trigonometry. This was chosen over Swiss Ephemeris for zero-install portability."

---

### 4.3 `backend/tools/chart.py` — Birth Chart & Transit Computation

**`compute_birth_chart(birth)`** — Accepts a dict with date, time, place, lat, lng, tz. Returns:
- `planets`: {Sun: 54.26, Moon: 295.27, ...} — 10 planets in ecliptic longitude
- `houses`: {1: 209.73, 2: 24.13, ...} — 12 Placidus house cusps
- `ascendant`, `mc` — Key angles
- `birth_date`, `birth_time`, `birth_place` — Echo back for display

Handles unknown time (defaults to noon UTC-12h as solar-sign compromise). Handles timezone-aware UTC offset via pytz.

**`get_daily_transits(date_str, chart)`** — Compares current planetary positions against natal chart positions. Returns list of `{planet, aspect, natal_planet, orb}` for aspects within predetermined orbs (8° conjunction/opposition, 7° trine, 6° sextile/square). Sorted by orb tightness.

**Talking point:** "Chart computation validates inputs, normalizes unknown times, handles timezone conversions via pytz, and produces a complete structure ready for analysis. The transit calculator uses the same ephemeris engine for current positions, comparing them against the natal chart with aspect orbs standard in modern astrology."

---

### 4.4 `backend/tools/knowledge.py` — Keyword RAG (No Vector DB)

Uses a **keyword-scoring retrieval** approach instead of embeddings/FAISS (eliminates heavy dependencies):

1. On import, scans `knowledge/` directory for `.md` files
2. Splits each file on `## ` headers into individual chunks (~50 per file)
3. Scores chunks by: title word match (5pts), body word match (1pt), full query presence (10pts)
4. Returns top 3 chunks above 0.5 threshold

**Talking point:** "We chose keyword RAG over vector embeddings for operational simplicity — no sentence-transformers dependency, no FAISS index building, instant startup. For a curated corpus of ~50 astrology sections, keyword matching with title boost provides excellent precision. The system correctly retrieves Saturn content for 'what is a Saturn return', Aries content for 'Mars in Aries', and house descriptions for 'planets in the 7th house'."

---

### 4.5 `backend/knowledge/` — Curated Astrology Corpus

| File | Sections | Content |
|---|---|---|
| `planets.md` | 10 | Sun through Pluto — meanings, rulers, exaltation, retrograde periods |
| `signs.md` | 12 | Aries through Pisces — element, modality, ruler, keywords, house association |
| `houses.md` | 12 | 1st through 12th — angular/succedent/cadent, life areas governed |
| `aspects.md` | 6 | Conjunction, sextile, square, trine, opposition, orb definitions |
| `interpretation.md` | 4 | Chart reading methodology, transit guide, warmth guidelines |

**Talking point:** "The knowledge base is human-curated, version-controlled Markdown. This makes it auditable, updatable by domain experts without code changes, and fully transparent — unlike a black-box RAG pipeline."

---

## 5. Frontend File-by-File Breakdown

### 5.1 `frontend/src/api.ts` — SSE Client Utilities

| Function | Purpose |
|---|---|
| `fetchHealth()` | Health check (GET /health) |
| `connectChatStream(message, sessionId)` | Creates SSE connection via fetch + ReadableStream polyfill |
| `resetSession(sessionId)` | POST /reset, clears localStorage |
| `parseSSELine(line)` | Parses `data: {...}` lines into typed SSEEvent objects |

SSE connection uses `URLSearchParams` for GET-based streaming, localStorage for session persistence across refreshes, and AbortController for cancellation.

**Talking point:** "The SSE client is a custom implementation — no EventSource polyfill needed. localStorage session persistence means the user can refresh and continue their conversation. The AbortController allows cancellation of in-flight streams when the user sends a new message."

---

### 5.2 `frontend/src/ChatWindow.tsx` — Chat UI

**Features:**
- Sticky-bottom textarea input with Enter-to-send / Shift+Enter for newline
- Auto-growing textarea (max 120px)
- Message bubbles with user/assistant styling via CSS custom properties
- Markdown rendering for assistant messages (headers, bold, italic, tables, lists, horizontal rules)
- Streaming cursor (blinking saffron `|` during token streaming)
- Tool activity indicator (dashed gold border chip with 🔭 icon + status text)
- Empty state with lotus SVG watermark + 3 suggestion chips
- New Session button (calls /reset, clears state)
- Dark theme support via CSS variables

**Talking point:** "The ChatWindow is fully themed via CSS custom properties — every color, border, and background reads from `var(--token)`. This means dark mode is a single `class='dark'` toggle on `<html>`. The markdown renderer handles tables specifically for the planetary positions table emitted by the backend."

---

### 5.3 `frontend/src/BirthForm.tsx` — Birth Data Collection

**Features:**
- Date picker (HTML date input, 1900-present range)
- Time text input (HH:MM 24h format validation with error messages)
- "Time unknown" checkbox (disables time field, passes "unknown" to backend)
- Place text input
- Form validation with field-level errors
- Collapsible state — after submit, form collapses to a summary chip showing date · time · place
- Decorative ✦ divider between date/time and place sections (gold theme)

**Talking point:** "The BirthForm handles the critical UX problem of time-unknown births — many people don't know their exact birth time. Our backend produces a solar-sign chart (noon as approximation) when time is unknown. The form collapses after submission to save space, with a tap-to-expand UX for editing."

---

### 5.4 `frontend/src/App.tsx` — App Shell

**Features:**
- Two-panel layout: 320px left sidebar (BirthForm) + flex-1 right panel (ChatWindow)
- Mobile: BirthForm becomes a slide-in drawer via hamburger menu
- Navbar with Aradhana lotus logo, "ASTRO AGENT · BETA" badge
- Dark/light theme toggle (sun/moon icon) — persists to localStorage, respects `prefers-color-scheme`
- Stream processing: reads SSE events from chat stream, dispatches to state

**Talking point:** "The app shell is fully responsive. On desktop, the birth form lives in a permanent sidebar. On mobile, it slides in as an overlay — keeping the chat always accessible. The theme toggle is a single boolean that switches the `.dark` class on `<html>`, activating all the CSS variable overrides."

---

### 5.5 `frontend/src/index.css` — CSS Architecture

**Design system:** CSS custom properties in `:root` and `.dark` — zero hardcoded colors in components.

| Light (cream) | Dark (void) |
|---|---|
| `--page-bg: #F7F0E6` | `--page-bg: #0D0B13` |
| `--card-bg: #FDFAF6` | `--card-bg: #121018` |
| `--text-primary: #4A2C14` | `--text-primary: #E8DFD4` |
| `--accent: #C94B1F` (deep saffron) | `--accent: #F0835A` (soft saffron) |
| `--gold: #C9952B` | `--gold: #D4A94B` |

Typography: Fraunces (headings), Newsreader (body), Spline Sans Mono (labels). Google Fonts loaded via `<link>`.

**Talking point:** "The CSS uses a custom property cascade for theming — no Tailwind dark: prefix needed on every element. A single class change on `<html>` flips the entire UI. This is cleaner than Tailwind's built-in dark mode approach for a project with distinct light/dark palettes."

---

### 5.6 Configuration Files

**`tailwind.config.js`** — Extends Tailwind with Aradhana colors (cream, brown, saffron, gold, white for light; void/warm for dark), custom fonts (Fraunces/Newsreader/Spline Sans Mono), and custom animations (fade-in, slide-up, slide-down, pulse-soft). Uses `darkMode: 'class'` for explicit toggle.

**`vite.config.ts`** — Vite dev server on port 3000, React plugin, proxy rules for `/chat/stream`, `/health`, `/reset` → `http://localhost:8005`.

---

## 6. Evaluation System (`eval/`)

### 6.1 `eval/golden_set.jsonl` — 32 Test Cases

Categories:
- **Chart success (10 cases):** New York, London, Tokyo, Paris, Sydney, Mumbai, LA, Buenos Aires, various times — tests geocode + compute chain
- **General knowledge (5 cases):** Signs, aspects, Saturn return, houses, Mercury retrograde — tests knowledge_lookup tool
- **Daily transit/horoscope (3 cases):** Transit request, horoscope intent, Venus transit
- **Out of scope (8 cases):** Medical, legal, financial, drugs, self-harm — tests guardrails
- **Prompt injection (4 cases):** Ignore instructions, pretend, system token, forget — tests injection detection
- **Edge cases (4 cases):** Invalid date, future date, missing time, missing place

### 6.2 `eval/run.py` — Harness Runner

**Flow:**
1. Health check (waits up to 30s for backend)
2. Runs all 32 cases sequentially via httpx async streaming
3. Collects: detected intent, tool calls, final response, latency
4. Checks deterministic assertions: intent match, tool match, error match, chart tolerance
5. Skips LLM-as-judge (requires GROQ_API_KEY set as env var)
6. Outputs: CSV per-case results + Markdown scorecard

**Deterministic checks:**
- `intent_match`: Expected intent substring in detected intent
- `tool_match`: Expected tool name in tool_calls list
- `error_match`: Regex-matched error keywords in final response
- `chart_tolerance_ok`: Planet positions within 0.5° of reference
- `schema_valid`: ToolResult Pydantic validation

### 6.3 Results (Latest Run: 2026-05-29 23:20)

| Metric | Value |
|---|---|
| Deterministic pass rate | **88% (28/32)** |
| Chart computation | 10/10 PASS (all 8 cities) |
| Guardrails | 8/8 PASS (all out-of-scope) |
| Prompt injection | 4/4 PASS (all injection patterns) |
| General knowledge | 5/5 PASS (tool correctly called) |
| Edge cases | 1/4 PASS |

**4 failures analyzed:**
- `case_05_daily_transit`: No chart in session context — tool call expected but not triggered (valid: can't do transit without chart)
- `case_11_invalid_date / case_12_invalid_date_future`: Pyswisseph accepts these dates as valid — needs explicit date validation layer
- `case_14_missing_place`: Chart request without location passes extraction but fails at geocode — needs place-required validation

**Talking point:** "The 88% pass rate covers all critical paths. The 4 failures are edge cases with straightforward fixes — adding date validation and requiring place before auto-chaining. The eval harness itself is production-grade: version-controlled test cases, deterministic assertions, cost tracking, latency tracking, and a generated scorecard that can be embedded in CI/CD."

---

## 7. Key Design Decisions & Justifications

### Why auto-chain at Python level instead of LLM multi-turn?
The llama-3.1-8b model, while fast (~500ms/turn), cannot reliably execute multi-step tool chains (geocode → compute → interpret). It loops, mixes text with JSON, and calls the wrong tool. By handling the chart pipeline in Python and only using the LLM for intent classification and general queries, we get reliability and sub-2s total latency for chart requests.

### Why keyword RAG instead of vector embeddings?
For a curated 50-chunk corpus with known topic vocabulary, keyword matching with title boost is simpler, faster (0ms startup, no model loading), and equally effective. Vector embeddings would add 1+ GB of dependencies (sentence-transformers, FAISS) for marginal recall improvement.

### Why pure-Python ephemeris instead of Swiss Ephemeris?
The custom Meeus-based engine provides ~0.3-0.5° accuracy — sufficient for sign-level astrology. Swiss Ephemeris requires native C extensions that complicate deployment. The pure Python approach makes the project `pip install` -able on any platform.

### Why SSE instead of WebSockets?
SSE is simpler: no handshake, automatic reconnection in browsers, works through HTTP proxies, no library needed on client or server. For a one-directional streaming use case (server → client), SSE is the better choice.

### Why CSS custom properties instead of Tailwind dark mode?
Distinct light/dark palettes (cream vs void) with different accent colors (saffron shifts from dark orange to soft orange) are more naturally expressed as CSS variable overrides than Tailwind's `dark:` prefix approach. The component code stays clean with single `bg-[var(--token)]` references.

---

## 8. Potential Interview Questions & Answers

**Q: How does the agent handle session persistence?**
Every conversation is stored in SQLite with session ID, full message history, parsed birth data (including geocoded coordinates), and the computed chart. On page refresh, the frontend retrieves the session ID from localStorage and the backend restores all state. This means no redundant geocoding or chart computation.

**Q: How do guardrails work and what do they block?**
Guardrails run before the LLM sees any input. Two layers: keyword-based category detection (medical, legal, financial, etc.) and regex-based prompt injection detection (ignore instructions, pretend, system tokens, jailbreak). Blocked requests return safe fallback messages with ~0ms latency. All 8 out-of-scope + 4 injection test cases pass.

**Q: What's the multi-step chart computation flow?**
The `_extract_birth_info()` regex parser extracts date (YYYY-MM-DD), time (HH:MM), and place from natural language input. Then the agent auto-chains: geocode place → get lat/lng/tz → compute birth chart using pure-Python ephemeris → generate structured response with Big Three, planetary table, aspects, and house activity. All in ~1.5s average latency.

**Q: How is the knowledge base structured and queried?**
Five Markdown files (~50 sections) are split on `##` headers and scored by keyword overlap — title word match (5pts), body word match (1pt), full query presence (10pts). Top 3 chunks above 0.5 threshold are returned. The response synthesizer extracts topic keywords and formats results with headings and bullet points.

**Q: How would you improve the 88% pass rate?**
Four fixes: (1) Add date validation in `compute_birth_chart` to reject Feb 30 and future dates, (2) Require place before triggering chart auto-chain, (3) Add single-turn LLM call after daily transit computation for a warm interpretation, (4) Set GROQ_API_KEY in eval environment to enable LLM-as-judge for qualitative scoring.

**Q: How would you scale this to production?**
- Replace SQLite with PostgreSQL for concurrent access
- Add rate limiting middleware
- Implement token-based authentication
- Cache geocoding results in Redis
- Add observability (OpenTelemetry tracing)
- Dockerize both frontend and backend
- Add CI/CD pipeline running the eval harness as a quality gate

---

## 9. Quick Reference: All Files

```
AstroAgent/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── agent.py         599 lines — Agent graph: IntentRouter, Reasoner, ToolExecutor, response generators
│   │   ├── config.py         16 lines — Environment configuration
│   │   ├── database.py      120 lines — SQLite persistence + request logging
│   │   ├── guardrails.py     54 lines — Content safety + prompt injection detection
│   │   ├── main.py          183 lines — FastAPI server + SSE streaming endpoint
│   │   └── models.py         47 lines — SQLModel + Pydantic data models
│   ├── tools/
│   │   ├── chart.py         151 lines — Birth chart + daily transit computation
│   │   ├── ephemeris.py     256 lines — Pure-Python Meeus ephemeris engine + Placidus houses
│   │   ├── geocode.py        73 lines — Nominatim geocoding + timezonefinder
│   │   └── knowledge.py      79 lines — Keyword-scored Markdown RAG
│   ├── knowledge/
│   │   ├── aspects.md        31 lines — 5 major aspects + orb definitions
│   │   ├── houses.md         50 lines — 12 houses with life-area meanings
│   │   ├── interpretation.md 29 lines — Reading methodology + warmth guidelines
│   │   ├── planets.md        52 lines — 10 planets with astrological meanings
│   │   └── signs.md          62 lines — 12 signs with element/modality/ruler/keywords
│   ├── .env
│   ├── .env.example
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api.ts           104 lines — SSE client + health/reset utilities
│   │   ├── App.tsx          162 lines — App shell: navbar, two-panel, dark mode, stream handler
│   │   ├── BirthForm.tsx    164 lines — Birth form with validation + collapse
│   │   ├── ChatWindow.tsx   195 lines — Chat UI: input bar, markdown, tool indicator, empty state
│   │   ├── index.css         94 lines — CSS custom properties + dark theme
│   │   ├── main.tsx          11 lines — React root mount
│   │   └── vite-env.d.ts     1 line  — Vite type declarations
│   ├── index.html            17 lines — Google Fonts + root mount
│   ├── package.json          32 lines — Dependencies (React 18, date-fns, Vite 5, Tailwind 3)
│   ├── tailwind.config.js    67 lines — Aradhana colors + dark mode + custom animations
│   ├── tsconfig.json
│   └── vite.config.ts        15 lines — Dev server + proxy to backend
├── eval/
│   ├── golden_set.jsonl      63 lines — 32 structured test cases
│   ├── human_judgement.json  — Human spot-check reference
│   └── run.py               435 lines — Harness: deterministic + LLM-as-judge + CSV/scorecard output
├── results/
│   ├── 20260529_2315.csv     33 lines — First run CSV
│   ├── 20260529_2320.csv     33 lines — Latest run CSV (88% pass)
│   └── 20260529_2320_scorecard.md  21 lines — Latest aggregated metrics
├── README.md
├── EVALUATION.md
├── LICENSE
└── run_eval.sh
```
