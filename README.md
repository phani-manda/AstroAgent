# AstroAgent — Your AI Astrology Companion

An agentic AI astrologer that computes rigorously-derived natal charts from a pure-Python ephemeris engine, geocodes birth locations, retrieves knowledge from a curated astrology corpus, and answers free-form questions — all streamed over SSE to a warm, dual-themed React frontend.

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Node](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)
[![React](https://img.shields.io/badge/react-18-61dafb.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/fastapi-0.100+-teal.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/eval-88%25_pass-brightgreen.svg)](results/20260529_2320_scorecard.md)

---

## Architecture

```
+------------------+          SSE               +-------------------+
|   React Frontend | <------------------------> |   FastAPI Server   |
| (Vite + TS)      |   GET /chat/stream (SSE)   | (Agent Graph)      |
|                   |   GET /health             |                    |
|  Aradhana Brand   |   POST /reset             |  guardrails.py     |
|  Light/Dark Theme |                           |  database.py       |
+--------+---------+                           +--------+----------+
         |                                            |
         |   Agent Graph:                              |
         |   1) check_content_safety (guardrails)      |
         |   2) classify_intent (LLM)                  |
         |   3) Auto-chain: extract → geocode → chart  |
         |   4) Reasoner / ToolExecutor                |
         |   5) Direct response synthesis              |
         |                                            |
+--------v---------+   SQLite (conversations, cache)    |
|   SQLite DB      +------------------------------------+
+------------------+
       |
       +-- geopy + Nominatim + timezonefinder (geocoding)
       +-- Pure-Python ephemeris (Jean Meeus formulas)
       +-- Keyword-scored Markdown RAG (knowledge)
```

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React 18, TypeScript, Vite 5, Tailwind CSS 3 | Dual-theme UI with SSE streaming, markdown rendering |
| Backend | FastAPI, Python 3.11+ | SSE streaming server, agent orchestration |
| LLM | Groq API (llama-3.1-8b-instant) | Intent classification, general question answering |
| Persistence | SQLite + SQLModel | Conversation history, birth data, chart caching |
| Ephemeris | Pure Python (Meeus algorithms) | Planetary positions, Placidus houses |
| Geocoding | geopy + Nominatim + timezonefinder | Place name → coordinates + timezone |
| RAG | Keyword-scored Markdown corpus | Astrology knowledge retrieval |
| Validation | Pydantic + SQLModel | Request/response schemas |
| Safety | Regex guardrails + keyword filters | Content safety, prompt injection detection |
| Eval | Custom Python harness (httpx) | 32 golden-set test cases, CSV + scorecard output |

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Groq API key ([console.groq.com](https://console.groq.com))

### Setup

**Backend:**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

Create `backend/.env`:

```env
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.1-8b-instant
```

**Frontend:**

```bash
cd frontend
npm install
```

### Run

**Terminal 1 — Backend:**

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8005
```

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

Open **http://localhost:3000** in your browser.

The Vite dev server proxies API calls to the backend. To change the backend port, edit `frontend/vite.config.ts`.

### Run Evaluations

```bash
# Windows
set ASTROAGENT_BACKEND_URL=http://localhost:8005
backend\.venv\Scripts\python eval\run.py

# Linux/macOS
ASTROAGENT_BACKEND_URL=http://localhost:8005 backend/.venv/bin/python eval/run.py
```

Results output to `results/YYYYMMDD_HHMM.csv` and a Markdown scorecard.

## Project Structure

```
AstroAgent/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI server + SSE streaming endpoint
│   │   ├── agent.py           # Agent graph: intent, reasoning, auto-chain, synthesis
│   │   ├── models.py          # SQLModel + Pydantic data models
│   │   ├── database.py        # SQLite persistence + request audit logging
│   │   ├── guardrails.py      # Content safety (18 categories) + injection detection (10 patterns)
│   │   └── config.py          # Environment configuration
│   ├── tools/
│   │   ├── geocode.py         # Nominatim geocoding + timezonefinder (in-memory cache)
│   │   ├── chart.py           # Birth chart + daily transit computation
│   │   ├── ephemeris.py       # Pure-Python ephemeris (Meeus formulas, Kepler solver, Placidus houses)
│   │   └── knowledge.py       # Keyword-scored Markdown RAG retrieval
│   ├── knowledge/
│   │   ├── planets.md         # Sun through Pluto — meanings, rulers, retrograde periods
│   │   ├── signs.md           # Aries through Pisces — elements, modalities, keywords
│   │   ├── houses.md          # 1st through 12th — life-area meanings
│   │   ├── aspects.md         # Conjunction, sextile, square, trine, opposition + orbs
│   │   └── interpretation.md  # Reading methodology, transit guide, warmth guidelines
│   ├── data/                  # SQLite database (auto-created)
│   ├── logs/                  # Request audit trail JSONL (auto-created)
│   ├── .env.example
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── App.tsx            # App shell: navbar, two-panel layout, theme toggle, stream handler
│   │   ├── ChatWindow.tsx     # Chat UI: input bar, markdown, tool indicator, empty state
│   │   ├── BirthForm.tsx      # Birth form with validation + collapse-on-submit
│   │   ├── api.ts             # SSE client, health check, session reset utilities
│   │   ├── index.css          # CSS custom properties, light/dark themes, animation keyframes
│   │   ├── main.tsx           # React root mount
│   │   └── vite-env.d.ts
│   ├── index.html             # Google Fonts (Fraunces, Newsreader, Spline Sans Mono)
│   ├── package.json
│   ├── tailwind.config.js     # Aradhana colors, dark mode class, custom animations
│   ├── tsconfig.json
│   └── vite.config.ts         # Dev server + proxy to backend
├── eval/
│   ├── golden_set.jsonl       # 32 structured test cases (10 chart, 5 knowledge, 3 transit, 8 safety, 4 injection, 4 edge)
│   ├── human_judgement.json   # Human spot-check reference
│   └── run.py                 # Evaluation harness (deterministic + LLM-as-judge + CSV scorecard)
├── results/                   # Evaluation output (CSV + MD scorecards)
├── INTERVIEW_GUIDE.md         # Comprehensive developer guide + interview talking points
├── EVALUATION.md              # Evaluation methodology documentation
├── README.md                  # This file
├── LICENSE                    # MIT
├── .gitignore
└── run_eval.sh                # One-command evaluation script
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/chat/stream` | GET | SSE stream. Query params: `body` (JSON-encoded message), `session_id` (optional). Returns typed SSE events. |
| `/health` | GET | Liveness probe → `{"status":"ok"}` |
| `/reset` | POST | Delete conversation. Body: `{"session_id":"..."}` |

### SSE Event Types

| Type | Payload | Description |
|---|---|---|
| `session` | `{session_id}` | Initial event with session identifier |
| `debug` | `{intent}` | Classified intent: `chart_request`, `daily_horoscope`, `general_question`, `out_of_scope` |
| `token` | `{content}` | 10-character streaming text chunk |
| `tool_start` | `{tool}` | Tool execution started (e.g. `geocode_place`) |
| `tool_end` | `{tool, result, latency_ms}` | Tool execution completed with output |
| `error` | `{content}` | Error message |

## Tools

| Tool | Purpose | Implementation |
|---|---|---|
| `geocode_place(place_name)` | Place → lat, lng, timezone | geopy + Nominatim + timezonefinder, in-memory cache, 3-retry backoff |
| `compute_birth_chart(birth)` | Calculate natal chart (10 planets, 12 houses) | Pure-Python ephemeris (Meeus algorithms), Kepler solver, Placidus houses |
| `get_daily_transits(date, chart)` | Daily transit aspects vs natal chart | Same ephemeris engine, 5 major aspects with configurable orbs |
| `knowledge_lookup(query)` | Retrieve astrology knowledge | Keyword-scored Markdown corpus (50 chunks, title-boosted scoring) |

## Agent Flow

```
User Message
    │
    ├─ check_content_safety()         ← Block medical/legal/financial/injection
    │
    ├─ classify_intent()              ← LLM at temperature 0.0
    │   └─ chart_request / daily_horoscope / general_question / out_of_scope
    │
    ├─ [chart_request]
    │   ├─ _extract_birth_info()      ← Regex: date (YYYY-MM-DD), time (HH:MM), place
    │   ├─ geocode_place()            ← Nominatim → lat/lng/tz (~1.2s)
    │   ├─ compute_birth_chart()      ← Pure-Python ephemeris (~0.5s)
    │   └─ _generate_chart_response() ← Big Three, planetary table, aspects, houses
    │
    ├─ [general_question]
    │   ├─ knowledge_lookup()         ← Keyword RAG → top 3 snippets
    │   └─ _synthesize_knowledge()    ← Structured response with headings
    │
    └─ [out_of_scope]
        └─ Safe fallback message      ← Category-specific response
```

**Key design decision:** For chart requests, the multi-step chain (extract → geocode → compute → interpret) runs at the Python level rather than relying on LLM multi-turn reasoning. The llama-3.1-8b model struggles with reliable tool orchestration; auto-chaining eliminates infinite loops and achieves sub-2s end-to-end latency.

## Safety & Guardrails

**Layer 1 — Category Detection (18 keywords):**
- Medical: `medical`, `prescription`, `diagnosis`, `drug`, `suicide`, `self-harm`
- Legal: `legal`, `lawsuit`, `attorney`, `sue`, `criminal`
- Financial: `financial`, `stock`, `investment`
- General: `illegal`, `hack`, `exploit`, `malware`, `weapon`, `violence`

**Layer 2 — Prompt Injection (10 regex patterns):**
- `ignore your/all/previous instructions/guardrails`
- `pretend you are/were`
- `you are now a/an`
- `system:` / `<|system|>` token smuggling
- `forget everything/all`
- `new instructions:`
- `override`, `bypass`, `jailbreak`

All blocked requests return category-specific safe fallback messages. Guardrails execute before the LLM sees any input (~0ms latency).

## Evaluation

### Test Suite
- **32 golden-set test cases** in `eval/golden_set.jsonl`
- 10 chart computation (8 cities, various times)
- 5 general knowledge (signs, aspects, houses, transits, retrogrades)
- 3 daily transit/horoscope
- 8 out-of-scope safety (medical, legal, financial, drugs, self-harm)
- 4 prompt injection (ignore, pretend, system, forget)
- 4 edge cases (invalid dates, missing time/place)

### Results (Latest: 2026-05-29)

| Metric | Value |
|---|---|
| Deterministic pass rate | **88% (28/32)** |
| Chart computation | 10/10 PASS |
| Guardrails (safety + injection) | 12/12 PASS |
| General knowledge | 5/5 tool calls correct |
| Avg latency (chart requests) | ~1.5s |
| Avg latency (safety blocks) | ~0.5s |

See `results/` for full per-case CSV and scorecard.

## Frontend Features

- **Dual theme**: Light (cream/brown/saffron) and dark (void/warm) with CSS custom properties. Toggle persisted to localStorage, respects `prefers-color-scheme`.
- **Responsive layout**: Two-panel on desktop (sidebar + chat), slide-in drawer on mobile.
- **SSE streaming**: 10-char token chunks for typewriter effect, blinking cursor during streaming.
- **Markdown rendering**: Chat responses render headers, bold/italic, tables (for planetary positions), horizontal rules.
- **Tool activity indicator**: Dashed gold chip with `🔭` icon shows active tool with status text.
- **Empty state**: Lotus watermark, Namaste greeting, 3 suggestion chips.
- **Birth form**: Date/time/place inputs with validation, "time unknown" checkbox, collapses to summary chip after submit.

## Design Decisions

| Decision | Rationale |
|---|---|
| Auto-chain at Python level, not LLM | llama-3.1-8b cannot reliably execute multi-step tool chains |
| Keyword RAG instead of vector embeddings | 50-chunk corpus doesn't need 1GB of ML dependencies |
| Pure-Python ephemeris, not Swiss Ephemeris | No native C extensions, zero-install portability |
| SSE instead of WebSockets | Simpler, auto-reconnect, no server-side connection management needed |
| CSS custom properties for theming | Cleaner than Tailwind `dark:` prefixing for distinct palettes |
| SQLite + JSON columns | Simple, portable, trivially migratable to PostgreSQL |

## Interview Preparation

See **[INTERVIEW_GUIDE.md](INTERVIEW_GUIDE.md)** — comprehensive developer guide covering:
- Every module and file explained in detail
- Architecture rationale and design justifications
- Evaluation methodology and test case analysis
- Mock Q&A for technical interviews

## License

MIT — see [LICENSE](LICENSE) for details.
