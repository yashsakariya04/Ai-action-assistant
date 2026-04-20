# AI Action Assistant

> A production-grade Personal AI Assistant platform — built from scratch with Python, FastAPI, and Groq LLaMA 3.3 70B.

This is **not a chatbot wrapper**. It is a full agentic AI system that executes real-world tasks — sending emails, scheduling calendar events, fetching live data, searching the web, and summarizing documents — all through a single natural language conversational interface.

---

## Quick Start

```bash
python run_api.py          # API server  →  http://localhost:8000
python run_mcp.py          # MCP server  →  stdio (Claude Desktop / MCP clients)
```

| URL | Description |
|-----|-------------|
| `http://localhost:8000` | Login page (entry point) |
| `http://localhost:8000/signup` | Create account |
| `http://localhost:8000/dashboard` | Chat dashboard (requires login) |
| `http://localhost:8000/docs` | Interactive Swagger API docs |
| `http://localhost:8000/health` | System health check |

```bash
# MCP Inspector (browser UI for testing all 9 MCP tools)
npx @modelcontextprotocol/inspector python run_mcp.py
# Open http://localhost:5173
```

---

## What Makes This Different

Most AI assistant projects call an LLM API and display the response. This system enforces a strict architectural principle:

> **The LLM handles reasoning only. Python code executes all real-world actions.**

- The AI never pretends to send an email. Only the Gmail API sends emails.
- The AI never pretends to create a calendar event. Only the Google Calendar API creates events.
- Every action goes through a validation layer before execution.
- Every irreversible action requires explicit user confirmation via a preview screen.
- The LLM cannot hallucinate email addresses — they are regex-verified against actual user messages.
- The LLM cannot hallucinate dates — all dates are validated as parseable and in the future.

---

## Live Demo

Deployed on Railway → `https://your-app.up.railway.app`

API Documentation → `https://your-app.up.railway.app/docs`

Health Check → `https://your-app.up.railway.app/health`

> Update these URLs after deploying to Railway.

---

## Features

| Feature | Technology | Status |
|---------|-----------|--------|
| User authentication (JWT) | FastAPI + SQLite/PostgreSQL | ✅ Live |
| Email sending | Gmail API (OAuth2) | ✅ Live |
| Calendar scheduling | Google Calendar API (OAuth2) | ✅ Live |
| Live news | NewsAPI | ✅ Live |
| Real-time weather | OpenWeatherMap API | ✅ Live |
| Web search | DuckDuckGo + Wikipedia fallback | ✅ Live |
| Document summarization | Groq LLM + pypdf + python-docx | ✅ Live |
| RAG knowledge base | ChromaDB + Sentence Transformers | ✅ Live |
| MCP server | FastMCP — 9 tools | ✅ Live |
| File upload (PDF/DOCX/XLSX/TXT) | FastAPI multipart | ✅ Live |
| Conversation memory | Custom rolling buffer + LLM compression | ✅ Live |
| Anti-hallucination validation | Custom Python validators | ✅ Live |
| Rate limiting | In-memory per-session counter | ✅ Live |
| Persistent chat sessions | SQLite (local) / PostgreSQL (Railway) | ✅ Live |
| Multi-page UI | Separate login / signup / dashboard HTML | ✅ Live |

---

## System Architecture

```
CLIENT
  Browser (login.html / signup.html / dashboard.html)
  Terminal (test_terminal.py)
  Claude Desktop / Cursor IDE / any MCP client
        ↓
AUTH LAYER  —  JWT Bearer tokens
  POST /auth/register  →  create user, return JWT
  POST /auth/login     →  verify credentials, return JWT
  GET  /auth/me        →  current user profile
        ↓
API GATEWAY  —  FastAPI (backend/app.py)
  POST /chat           →  main chat endpoint (JWT required)
  POST /reset          →  clear session memory
  GET  /sessions       →  list user's chat sessions
  GET  /health         →  system health check
        ↓
CHAT ENGINE  —  7-Step Processing Pipeline (backend/chat_engine.py)
  Step 1. Confirmation Detection   LLM classifies: yes / no / new_info
  Step 2. Action Planning          LLM extracts intent + structured arguments
  Step 3. RAG Answer               ChromaDB vector search → LLM synthesizes answer
  Step 4. Direct Execution         weather / news / search / summarize (no confirmation needed)
  Step 5. Email Auto-Draft         LLM writes subject + body from user intent
  Step 6. Missing Field Collection multi-turn conversation to gather required fields
  Step 7. Preview + Confirm        full preview shown → user types "yes" to execute
        ↓
VALIDATOR LAYER  —  Anti-hallucination (core/validators.py)
  Email addresses  →  regex-verified against actual user messages
  Calendar dates   →  validated as parseable + in the future
  All arguments    →  type-checked before any API call
        ↓
EXECUTION LAYER  —  Python only, zero LLM involvement
  Gmail API          →  email_service.py
  Google Calendar    →  calendar_service.py
  NewsAPI            →  news_service.py
  OpenWeatherMap     →  weather_service.py
  DuckDuckGo/Wiki    →  web_search_service.py
  ChromaDB           →  rag_pipeline.py
        ↓
MCP SERVER  —  9 tools (mcp_server.py)
  Compatible with Claude Desktop, Cursor IDE, any MCP client
```

---

## Frontend — Three Separate Pages

The UI is split into three dedicated HTML files under `static/`:

| File | Route | Purpose |
|------|-------|---------|
| `static/login.html` | `/login` and `/` | Sign-in form. Redirects to `/dashboard` if already logged in. |
| `static/signup.html` | `/signup` | Account creation form. Redirects to `/dashboard` after registration. |
| `static/dashboard.html` | `/dashboard` | Full chat interface. Redirects to `/login` if no JWT token found. |

### Auth Flow
1. User visits `/` → served `login.html`
2. On successful login → JWT stored in `localStorage` → redirect to `/dashboard`
3. `dashboard.html` checks `localStorage` for token on load → redirects to `/login` if missing
4. All `/chat`, `/reset`, `/sessions` API calls include `Authorization: Bearer <token>` header

### Dashboard Features
- Sidebar with service selector (Weather, News, Search, Email, Calendar, Summarize)
- Chat history with per-session persistence in `localStorage`
- File attachment (PDF, DOCX, XLSX, TXT) with drag-and-drop strip
- Quick-action chips for common queries
- Typing indicator with animated dots
- Status badges per message (SUCCESS · EMAIL, AWAITING · CALENDAR, etc.)
- Inline Confirm / Cancel buttons for pending actions
- Copy-to-clipboard on every message
- Responsive layout (sidebar hidden on mobile)

---

## Tech Stack

```
Language        Python 3.11
LLM             Groq API — 3-tier model architecture (see LLM Architecture section)
STT             Groq Whisper API — whisper-large-v3-turbo
TTS             Google Cloud Text-to-Speech — Neural2 voices
Backend         FastAPI + Uvicorn
Auth            JWT (python-jose) + bcrypt password hashing
Database        SQLAlchemy ORM — SQLite (local) / PostgreSQL (Railway)
Vector DB       ChromaDB (local persistent)
Embeddings      Sentence Transformers — all-MiniLM-L6-v2
Email           Gmail API (OAuth2 via google-auth)
Calendar        Google Calendar API (OAuth2 via google-auth)
News            NewsAPI.org + DuckDuckGo web search fallback
Weather         OpenWeatherMap API
Search          DuckDuckGo (ddgs) + Wikipedia API fallback
Files           pypdf + python-docx + pandas + BeautifulSoup4
Protocol        MCP (Model Context Protocol) via FastMCP
Frontend        Vanilla HTML/CSS/JS — no framework, no build step
Fonts           Geist Mono + DM Sans (Google Fonts)
Deployment      Railway (Docker)
```

---

## LLM Architecture — 3-Tier Model Routing

This project splits all LLM calls across three independent Groq API keys and model tiers to maximise free-tier token budgets and ensure uninterrupted service even when one key hits its daily limit.

```
TIER 1 — PRIMARY   key: GROQ_API_KEY_PRIMARY   model: openai/gpt-oss-120b
  └─ plan_action()              Intent detection + argument extraction
  └─ detect_confirmation()      yes / no / new_info classification
  └─ generate_missing_field()   Natural language field collection
  └─ get_llm_response()         RAG answer synthesis
  Why: These tasks need the strongest reasoning. Wrong intent = wrong action.

TIER 2 — MEDIUM    key: GROQ_API_KEY_MEDIUM    model: llama-3.3-70b-versatile
  └─ draft_email()              Professional email writing
  └─ draft_event_description()  Calendar event description
  └─ Summarization via LLM      Long-context document summarization
  Why: Good writing quality + large context window. Separate quota from Tier 1.

TIER 3 — LIGHT     key: GROQ_API_KEY_LIGHT     model: llama-3.1-8b-instant
  └─ Weather response formatting
  └─ News response formatting
  └─ Web search result formatting
  └─ General conversation fallback
  Why: 500k+ TPD free, ultra-fast (~200 tok/s). Simple tasks don’t need 120B.
```

### Token Budget (Free Tier)

| Tier | Model | Daily Tokens | Tasks |
|------|-------|-------------|-------|
| Primary | openai/gpt-oss-120b | high | Planning, RAG, confirmation |
| Medium | llama-3.3-70b-versatile | 100k | Email, summarize, calendar |
| Light | llama-3.1-8b-instant | 500k | Weather, news, search |

### Fallback Behaviour

- If `GROQ_API_KEY_MEDIUM` is not set → falls back to `GROQ_API_KEY_PRIMARY`
- If `GROQ_API_KEY_LIGHT` is not set → falls back to `GROQ_API_KEY_PRIMARY`
- **Single key setup**: set only `GROQ_API_KEY_PRIMARY` — everything works, all tiers share it
- **Two key setup**: set `PRIMARY` + `LIGHT` — medium falls back to primary
- **Full three key**: maximum token budget, fully isolated quotas

### .env Configuration

```env
# Tier 1 — Primary (intent, RAG, confirmation)
GROQ_API_KEY_PRIMARY=your_primary_key
GROQ_MODEL_PRIMARY=openai/gpt-oss-120b

# Tier 2 — Medium (email, summarize, calendar)
GROQ_API_KEY_MEDIUM=your_medium_key
GROQ_MODEL_MEDIUM=llama-3.3-70b-versatile

# Tier 3 — Light (weather, news, search)
GROQ_API_KEY_LIGHT=your_light_key
GROQ_MODEL_LIGHT=llama-3.1-8b-instant
```

---

## MCP Server — 9 Tools

This project exposes a full MCP server compatible with Claude Desktop, Cursor IDE, and any MCP client.

| Tool | Description |
|------|-------------|
| `chat` | Master brain — natural language routing to all services |
| `weather_service` | Current weather for any city |
| `web_search_service` | Internet search with DuckDuckGo + Wikipedia fallback |
| `summarizer_service` | Summarize URL / plain text / uploaded file |
| `email_service` | Full email draft → preview → confirm → send workflow |
| `calendar_service` | Full calendar schedule → preview → confirm → create workflow |
| `news_service` | Live news headlines on any topic |
| `reset_conversation` | Clear session memory |
| `get_system_status` | Health check for all services |

---

## Project Structure

```
ai-action-assistant/
│
├── backend/
│   ├── app.py               # FastAPI app — all routes, middleware, lifespan
│   ├── auth.py              # JWT auth — register, login, get_current_user
│   ├── chat_engine.py       # 7-step processing pipeline (core brain)
│   ├── session_store.py     # Session management — in-memory + DB persistence
│   └── schemas.py           # Pydantic request/response models
│
├── core/
│   ├── action_controller.py # Required field validation per action type
│   ├── embedding.py         # Sentence Transformers wrapper
│   ├── ingestion.py         # URL → text ingestion pipeline
│   ├── intent_parser.py     # Datetime extraction helpers
│   ├── llm_service.py       # All LLM calls — planner, drafter, RAG, compressor
│   ├── memory_manager.py    # Rolling conversation buffer + LLM compression
│   ├── rag_pipeline.py      # RAG — vector search + LLM response synthesis
│   ├── validators.py        # Anti-hallucination validators
│   └── vector_store.py      # ChromaDB wrapper
│
├── db/
│   ├── database.py          # SQLAlchemy engine + session factory
│   └── models.py            # ORM models — User, ChatSession, ChatMessage
│
├── services/
│   ├── calendar_service.py  # Google Calendar API integration
│   ├── email_service.py     # Gmail API integration
│   ├── news_service.py      # NewsAPI integration
│   ├── summarizer_service.py# Multi-source summarization (URL/file/text)
│   ├── weather_service.py   # OpenWeatherMap integration
│   └── web_search_service.py# DuckDuckGo + Wikipedia fallback
│
├── static/
│   ├── login.html           # Sign-in page (served at / and /login)
│   ├── signup.html          # Account creation page (served at /signup)
│   └── dashboard.html       # Full chat UI (served at /dashboard, JWT-guarded)
│
├── scripts/
│   ├── calendar_auth.py     # Google OAuth2 flow — generates token.pickle
│   ├── encode_token.py      # Encode token.pickle to base64 for Railway
│   └── startup.py           # Railway startup — decode GOOGLE_TOKEN_B64
│
├── tests/
│   ├── test_mcp.py          # MCP tool test suite (all 9 tools)
│   └── test_terminal.py     # Terminal chat client for local testing
│
├── mcp_server.py            # FastMCP server entry point — 9 tools
├── config.py                # Centralized config from environment variables
├── run_api.py               # FastAPI server entry point (Uvicorn)
├── run_mcp.py               # MCP server entry point
│
├── Dockerfile               # Docker container definition
├── Railway.json             # Railway deployment config
├── requirements.txt         # Python dependencies
└── .env.example             # Environment variable template
```

---

## Getting Started — Local Setup

### Prerequisites

- Python 3.10+
- A Groq API key — free at [console.groq.com](https://console.groq.com)
- Google Cloud project with **Gmail API** + **Google Calendar API** enabled
- NewsAPI key — free at [newsapi.org](https://newsapi.org)
- OpenWeatherMap key — free at [openweathermap.org](https://openweathermap.org/api)

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/ai-action-assistant.git
cd ai-action-assistant
```

### 2. Create virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
# LLM
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# Email
EMAIL_USER=your_gmail@gmail.com

# APIs
NEWS_API_KEY=your_newsapi_key
OPENWEATHER_API_KEY=your_openweather_key

# Google OAuth
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_TOKEN_FILE=token.pickle
CALENDAR_TIMEZONE=Asia/Kolkata
```

### 5. Set up Google OAuth (Calendar + Gmail)

Place your `credentials.json` from Google Cloud Console in the project root, then run:

```bash
python scripts/calendar_auth.py
```

A browser window opens → sign in → allow Calendar and Gmail permissions → `token.pickle` is saved.

### 6. Start the server

```bash
python run_api.py
```

Visit `http://localhost:8000` → sign up → start chatting.

---

## API Reference

### Auth Endpoints

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| `POST` | `/auth/register` | `{ email, password, name? }` | Create account, returns JWT |
| `POST` | `/auth/login` | `form: username, password` | Sign in, returns JWT |
| `GET` | `/auth/me` | — (Bearer token) | Current user profile |

### Chat Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/chat` | JWT | Main chat — JSON or multipart with file |
| `POST` | `/reset` | JWT | Reset session memory |
| `GET` | `/sessions` | JWT | List user's chat sessions |
| `GET` | `/health` | — | System health check |

### Chat Request (JSON)

```json
{
  "message": "What is the weather in Mumbai?",
  "session_id": "uuid-string",
  "selected_services": ["weather"]
}
```

### Chat Request (multipart — with file)

```
POST /chat
Content-Type: multipart/form-data

message=Summarize this document
session_id=uuid-string
file=<binary PDF/DOCX/XLSX/TXT>
```

### Chat Response

```json
{
  "status": "success",
  "action": "weather",
  "message": "Current weather in Mumbai: 32°C, Humid...",
  "session_id": "uuid-string",
  "news_articles": null
}
```

Status values: `success` | `error` | `pending` (collecting fields) | `awaiting` (confirmation required) | `cancelled`

---

## Testing

### Terminal chat client

```bash
python tests/test_terminal.py
```

### MCP tool test suite

```bash
# Test all 9 tools
python tests/test_mcp.py

# Test a specific tool
python tests/test_mcp.py --tool weather_service
python tests/test_mcp.py --tool get_system_status
```

### MCP Inspector (browser UI)

```bash
npx @modelcontextprotocol/inspector python run_mcp.py
```

Open `http://localhost:5173` to interact with all 9 tools visually.

---

## Connecting to Claude Desktop

Add this to your Claude Desktop config (`%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "ai-action-assistant": {
      "command": "C:\\path\\to\\python.exe",
      "args": ["run_mcp.py"],
      "cwd": "C:\\path\\to\\ai-action-assistant"
    }
  }
}
```

Restart Claude Desktop → click the hammer icon → all 9 tools are available.

---

## Deployment — Railway

### 1. Encode Google auth files

```bash
# Encode token.pickle
python scripts/encode_token.py

# Encode credentials.json
python -c "import base64; print(base64.b64encode(open('credentials.json','rb').read()).decode())"
```

### 2. Push to GitHub

```bash
git add .
git commit -m "Deploy to Railway"
git push
```

### 3. Create Railway project

1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
2. Select this repository
3. Railway auto-detects the Dockerfile

### 4. Set environment variables in Railway dashboard

```
GROQ_API_KEY
GROQ_MODEL
EMAIL_USER
NEWS_API_KEY
OPENWEATHER_API_KEY
CALENDAR_TIMEZONE
GOOGLE_TOKEN_B64          ← output from encode_token.py
GOOGLE_CREDENTIALS_B64    ← output from credentials.json encode
```

### 5. Access your live URL

Railway provides: `https://your-app.up.railway.app`

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY_PRIMARY` | Yes | — | Groq key for Tier 1 (intent, RAG, confirmation) |
| `GROQ_MODEL_PRIMARY` | No | `openai/gpt-oss-120b` | Tier 1 model |
| `GROQ_API_KEY_MEDIUM` | No | falls back to PRIMARY | Groq key for Tier 2 (email, summarize) |
| `GROQ_MODEL_MEDIUM` | No | `llama-3.3-70b-versatile` | Tier 2 model |
| `GROQ_API_KEY_LIGHT` | No | falls back to PRIMARY | Groq key for Tier 3 (weather, news, search) |
| `GROQ_MODEL_LIGHT` | No | `llama-3.1-8b-instant` | Tier 3 model |
| `GROQ_API_KEY` | No | — | Legacy single-key alias (maps to PRIMARY) |
| `EMAIL_USER` | For email | — | Gmail address (From: header) |
| `NEWS_API_KEY` | For news | — | NewsAPI.org key |
| `OPENWEATHER_API_KEY` | For weather | — | OpenWeatherMap key |
| `GOOGLE_CREDENTIALS_FILE` | Local only | `credentials.json` | Path to Google credentials |
| `GOOGLE_TOKEN_FILE` | Local only | `token.pickle` | Path to OAuth token |
| `CALENDAR_TIMEZONE` | No | `Asia/Kolkata` | Timezone for calendar events |
| `GOOGLE_TTS_API_KEY` | For voice TTS | — | Google Cloud TTS API key |
| `WHISPER_MODEL` | No | `whisper-large-v3-turbo` | Groq Whisper STT model |
| `TTS_DEFAULT_VOICE` | No | `en-US-Neural2-F` | Default TTS voice |
| `TTS_DEFAULT_SPEED` | No | `1.0` | TTS speaking rate (0.5–2.0) |
| `TTS_DEFAULT_PITCH` | No | `0.0` | TTS pitch (-10 to 10) |
| `GOOGLE_TOKEN_B64` | Railway only | — | Base64-encoded token.pickle |
| `GOOGLE_CREDENTIALS_B64` | Railway only | — | Base64-encoded credentials.json |
| `SIMILARITY_THRESHOLD` | No | `0.45` | RAG vector similarity cutoff |
| `RATE_LIMIT_REQUESTS` | No | `30` | Max requests per session per window |
| `RATE_LIMIT_WINDOW_SECONDS` | No | `60` | Rate limit window in seconds |
| `UPLOAD_MAX_BYTES` | No | `10485760` | Max file upload size (10 MB) |
| `ALLOWED_ORIGINS` | No | localhost ports | CORS allowed origins |
| `DATABASE_URL` | No | SQLite | PostgreSQL URL for Railway |
| `JWT_SECRET_KEY` | No | auto-generated | JWT signing secret |

---

## Anti-Hallucination System

A key engineering achievement of this project is preventing AI hallucination in task execution:

- **Email addresses** — regex-verified against actual user messages. The AI cannot fabricate or guess addresses.
- **Calendar dates** — validated as parseable and in the future. The AI cannot invent dates.
- **Confirmation gate** — every email and calendar action shows a full preview. Nothing executes without explicit user approval (user must type "yes").
- **Argument validation** — a separate Python validation layer (`core/validators.py`) runs before every API call.
- **Execution separation** — the LLM classifies intent and extracts arguments only. Python makes all actual API calls.
- **No tool-calling** — the system does not use LLM function-calling/tool-use features. The LLM outputs structured JSON which Python parses and validates independently.

---

## 7-Step Chat Engine Pipeline

Every message sent to `/chat` goes through this pipeline in `backend/chat_engine.py`:

1. **Confirmation Detection** — If a pending action exists in session state, the LLM classifies the user's reply as `yes`, `no`, or `new_info`. If `yes`, the action executes immediately.

2. **Action Planning** — The LLM receives the user message + conversation history and outputs a structured JSON plan: `{ "action": "email", "to": "...", "subject": "...", ... }`.

3. **RAG Answer** — If the action is `rag` (knowledge base query), ChromaDB performs a vector similarity search. If relevant documents are found above the similarity threshold, the LLM synthesizes an answer from them.

4. **Direct Execution** — Actions that don't require confirmation (weather, news, search, summarize) are executed immediately and the result is returned.

5. **Email Auto-Draft** — For email actions, the LLM drafts a professional subject line and body from the user's intent. The draft is shown to the user for review.

6. **Missing Field Collection** — If required fields are missing (e.g., email recipient, calendar date), the system enters a multi-turn collection loop, asking for one field at a time.

7. **Preview + Confirm** — For email and calendar actions, a full preview is shown. The session state is set to `awaiting_confirmation`. The action only executes when the user explicitly confirms.

---

## Roadmap

| Phase | Feature | Status |
|-------|---------|--------|
| Phase 1 | Agent Orchestrator Layer | Planned |
| Phase 2 | Tool Framework with BaseTool | Planned |
| Phase 3 | Streaming responses (SSE) | Planned |
| Phase 4 | Redis session store | Planned |
| Phase 5 | Multi-user sessions | Planned |
| Phase 6 | Voice interface (Whisper + TTS) | Planned |

---

## Development Journey

This project went through **9 complete rebuilds** before reaching production stability. Each rebuild identified and corrected a fundamental design flaw:

- **Rebuild 1–3** — Separating LLM reasoning from Python execution. Early versions let the LLM "pretend" to execute actions.
- **Rebuild 4–5** — Multi-turn field collection with proper state management. Early versions lost context between turns.
- **Rebuild 6–7** — Anti-hallucination validation layer. The LLM was fabricating email addresses and dates.
- **Rebuild 8** — Confirmation gate architecture. Actions were executing without user approval.
- **Rebuild 9** — MCP protocol integration + production hardening (auth, rate limiting, DB persistence, Docker).

---

## Google Stitch UI Prompt

Use this prompt in [Google Stitch](https://stitch.withgoogle.com) to generate a production-quality UI for this project:

```
Build a production-grade AI assistant web application UI with three separate pages.

Design system:
- Dark theme only. Background: #0a0a0a. Surface: #111111. Border: #222222.
- Accent color: #10a37f (green). Danger: #ef4444. Warning: #f59e0b. Info: #3b82f6.
- Typography: "Instrument Sans" for UI text, "Geist Mono" for labels, badges, and code.
- Border radius: 8px for inputs/buttons, 14px for cards, 16px for modals.
- No gradients. No shadows. Flat, minimal, terminal-inspired aesthetic.

PAGE 1 — Login (/login)
- Centered card (max-width 400px) on dark background.
- Logo mark: 38x38px green rounded square with "AI" in monospace white.
- Logo text: "AI Action Assistant" + subtitle "PRODUCTION · RAILWAY" in muted monospace.
- Heading: "Welcome back" (22px, semibold).
- Subtitle: "Sign in to your account to continue" (13px, muted).
- Two fields: Email (type=email) and Password (type=password). Labels in uppercase monospace.
- Primary button: full-width, green background, "Sign In".
- Error state: dark red background box with red border and red text.
- Footer link: "Don't have an account? Create one" linking to /signup.
- On load: if JWT token exists in localStorage, redirect to /dashboard.

PAGE 2 — Signup (/signup)
- Same card layout as login.
- Heading: "Create account". Subtitle: "Start using your personal AI assistant".
- Three fields: Full Name (optional), Email, Password (min 8 chars with hint text).
- Primary button: "Create Account".
- Footer link: "Already have an account? Sign in" linking to /login.
- On load: if JWT token exists in localStorage, redirect to /dashboard.

PAGE 3 — Dashboard (/dashboard)
- Full-screen two-column layout: fixed sidebar (260px) + main chat area (flex: 1).
- On load: if no JWT token in localStorage, redirect to /login.

SIDEBAR:
- Top section: logo + "New conversation" button (secondary style, full width).
- Service selector grid (2 columns, 6 items): Weather 🌤, News 📰, Web Search 🔍, Send Email 📧, Calendar 📅, Summarize 📄. Each is a toggleable card with a small checkbox indicator in the top-right corner. Selected state: green border + dark green background.
- Chat history list: scrollable, each item shows truncated title + hover-reveal delete button (🗑). Active item highlighted in green.
- Bottom status bar: animated green pulse dot + "Connected" text + "LLaMA 3.3" badge.

MAIN CHAT AREA:
- Header bar (54px): current conversation title (flex: 1) + two icon buttons (clear ↺, API docs ⎘).
- Messages area (flex: 1, scrollable): messages rendered as rows with avatar + bubble.
  - AI messages: left-aligned, "AI" green avatar, plain text bubble, status badge above (e.g. "● SUCCESS · WEATHER").
  - User messages: right-aligned, "Y" dark avatar, blue-tinted rounded bubble.
  - Status badge colors: success=green, error=red, pending=blue, awaiting=amber.
  - Awaiting confirmation: show inline "✓ Confirm" (green) and "✕ Cancel" (red) buttons below the message.
  - Hover on any message: show copy button with clipboard icon.
  - Typing indicator: three animated bouncing dots in an AI message row.
- Welcome screen (shown when no messages): centered icon + heading + 6 quick-action chips in a wrapping row.
- Input area (bottom, fixed):
  - Outer wrapper: rounded 14px border, focus glow.
  - File strip (hidden by default): shown when file attached — file icon + filename + remove button.
  - Textarea row: "+" attach button (left) + auto-resize textarea + circular send button (right, green, ↑ arrow).
  - Toolbar row below textarea: 4 quick-action buttons (Weather, News, Search, Summarize) with emoji icons.
  - Below input: small muted hint text "AI can make mistakes — always verify important info".

INTERACTIONS:
- Enter sends message. Shift+Enter adds newline.
- Textarea auto-resizes up to 140px height.
- File attachment: accept .pdf, .docx, .xlsx, .txt. Show file strip with icon and name.
- Service chips are toggleable — clicking selects/deselects with visual feedback.
- Chat history persists in localStorage per session ID.
- All API calls include Authorization: Bearer <token> header from localStorage.
- New conversation resets session ID and clears messages.

RESPONSIVE:
- Hide sidebar on screens narrower than 680px.
- Input area remains full-width on mobile.

Output three separate HTML files: login.html, signup.html, dashboard.html. Each file is fully self-contained with all CSS and JavaScript inline. No external JS frameworks. No build tools. Use Google Fonts CDN for Geist Mono and Instrument Sans.
```

---

## License

MIT License — see LICENSE file for details.

---

## Author

**Yash** — Infopulse Tech

Built as a production-grade AI engineering project demonstrating real-world agentic AI system design.

---

*If this project helped you, give it a star on GitHub.*
