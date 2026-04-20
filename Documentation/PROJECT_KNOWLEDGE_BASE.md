# AI ACTION ASSISTANT — COMPLETE PROJECT KNOWLEDGE BASE
# (For Academic Report Generation — 8th Semester B.Tech CE-AI Project)

---

## 1. PROJECT IDENTITY

- **Project Title:** AI Action Assistant — An Agentic AI System for Real-World Task Execution via Natural Language
- **Alternate Title:** A Production-Grade Personal AI Assistant Platform with Anti-Hallucination Safeguards and Multi-Service Integration
- **Domain:** Artificial Intelligence, Natural Language Processing, Agentic AI Systems
- **Academic Context:** 8th Semester B.Tech Final Year Project — Computer Engineering (AI)
- **Author:** Yash Sakariya
- **Organization:** Infopulse Tech
- **University:** (Fill in your university name)
- **Year:** 2025–2026
- **GitHub Repository:** https://github.com/yashsakariya04/Ai-action-assistant

---

## 2. PROBLEM STATEMENT

Most AI chatbot applications today are simple wrappers around LLM APIs — they receive a user query, forward it to an LLM (like GPT or LLaMA), and display the LLM's raw text response. They cannot execute real-world actions such as sending emails, scheduling calendar events, fetching live weather data, or summarizing documents. When users ask these chatbots to "send an email" or "schedule a meeting," the AI merely *pretends* to do so — generating fictional confirmations without any actual execution.

**Key Problems Identified:**
1. **No Action Execution:** Existing chatbots cannot interact with external APIs (Gmail, Google Calendar, News APIs, Weather APIs) to perform real tasks.
2. **Hallucination in Critical Data:** LLMs frequently fabricate email addresses, dates, and other critical data when asked to compose emails or schedule events.
3. **No Validation or Confirmation:** Actions are executed (or pretended) without user approval or preview.
4. **Single-Model Bottleneck:** Using one LLM for all tasks leads to token quota exhaustion and suboptimal performance — simple formatting tasks waste expensive reasoning capacity.
5. **No Knowledge Base Integration:** Chatbots cannot answer questions from custom document collections using Retrieval Augmented Generation (RAG).
6. **No Protocol Interoperability:** Chatbots are locked to their own UI and cannot be used from other AI tools (Claude Desktop, Cursor IDE).

---

## 3. PROPOSED SOLUTION

The AI Action Assistant is a production-grade agentic AI system that enforces a strict architectural separation:

> **The LLM handles reasoning only. Python code executes all real-world actions.**

The system uses a 7-step processing pipeline where:
- The LLM classifies user intent and extracts structured arguments
- A Python validation layer prevents hallucinated data from reaching APIs
- All irreversible actions (email, calendar) require explicit user confirmation via a preview screen
- Read-only actions (weather, news, search) execute immediately
- A 3-tier model architecture distributes LLM workload across different models for optimal cost/quality trade-offs

---

## 4. OBJECTIVES

1. Design and implement a full-stack AI assistant that can execute real-world tasks through natural language commands
2. Build a 7-step chat processing pipeline that separates LLM reasoning from Python execution
3. Implement an anti-hallucination validation layer that prevents fabricated email addresses and dates
4. Create a 3-tier LLM model architecture that distributes workload across multiple models
5. Integrate with 6+ external services: Gmail API, Google Calendar API, NewsAPI, OpenWeatherMap, DuckDuckGo, ChromaDB
6. Build a RAG (Retrieval Augmented Generation) pipeline for knowledge base queries
7. Implement JWT-based authentication with user registration and login
8. Develop a confirmation-gate architecture for irreversible actions
9. Deploy the system using Docker on Railway cloud platform
10. Expose an MCP (Model Context Protocol) server for integration with Claude Desktop and Cursor IDE
11. Build a responsive, multi-page web UI (login, signup, dashboard) without any frontend framework
12. Implement conversation memory with rolling buffer + LLM compression

---

## 5. TECHNOLOGY STACK (DETAILED)

### 5.1 Programming Language
- **Python 3.11** — chosen for its mature AI/ML ecosystem, async support, and extensive API client libraries

### 5.2 LLM (Large Language Model)
- **Provider:** Groq Cloud (free tier)
- **API:** Groq Chat Completions API
- **3-Tier Model Architecture:**
  - **Tier 1 — PRIMARY:** `openai/gpt-oss-120b` — Used for intent detection, action planning, RAG answer synthesis, confirmation detection, and missing field prompts. These tasks require the strongest reasoning capability.
  - **Tier 2 — MEDIUM:** `llama-3.3-70b-versatile` — Used for email drafting, calendar event description, and document summarization. Good writing quality with large context window.
  - **Tier 3 — LIGHT:** `llama-3.1-8b-instant` — Used for weather/news/search response formatting, general conversation fallback, and memory compression. Ultra-fast (~200 tokens/sec), 500k+ tokens/day free.
- **Fallback Behavior:** If a tier's API key is not configured, it automatically falls back to the PRIMARY key. The system works with 1, 2, or 3 API keys.

### 5.3 Backend Framework
- **FastAPI** (v0.110+) — High-performance async Python web framework with automatic OpenAPI documentation
- **Uvicorn** — ASGI server for serving FastAPI

### 5.4 Database
- **SQLAlchemy ORM** (v2.0+) — Database-agnostic ORM
- **SQLite** — Local development (file: `assistant.db`)
- **PostgreSQL** — Production deployment on Railway
- **Tables:** `users`, `sessions`, `messages`, `google_tokens`

### 5.5 Vector Database (RAG)
- **ChromaDB** (v0.5+) — Local persistent vector database for knowledge base storage
- **Cosine Similarity** with HNSW indexing for fast approximate nearest neighbor search
- **Similarity Threshold:** 0.45 (configurable)

### 5.6 Embeddings
- **Sentence Transformers** (v3.0+) — `all-MiniLM-L6-v2` model
- 384-dimensional embedding vectors
- Singleton pattern for model loading

### 5.7 Speech-to-Text (STT)
- **Groq Whisper API** — `whisper-large-v3-turbo` model
- Supports webm, mp4, wav, ogg, m4a, flac audio formats
- Ultra-fast transcription with accent and noise handling

### 5.8 Text-to-Speech (TTS)
- **Browser Web Speech Synthesis API** — Client-side, no backend needed, unlimited and free

### 5.9 External API Integrations
- **Gmail API** — OAuth2 via `google-auth`, sends real emails with HTML formatting
- **Google Calendar API** — OAuth2, creates events with custom reminders (10 min popup + 1 day email)
- **NewsAPI.org** — Real-time news headlines by topic or category
- **OpenWeatherMap API** — Current weather data for any city worldwide
- **DuckDuckGo Search** — Web search via `ddgs` library (no API key needed)
- **Wikipedia API** — Fallback search strategy (always free, highly reliable)

### 5.10 Authentication
- **JWT (JSON Web Tokens)** — `python-jose` library with HS256 algorithm
- **bcrypt** — Password hashing (one-way hash + salt)
- **OAuth2PasswordBearer** — FastAPI security dependency
- **Token expiry:** 72 hours (configurable)
- **Per-user Google OAuth2** — Stored in `google_tokens` table as base64-encoded pickle

### 5.11 Frontend
- **Vanilla HTML/CSS/JS** — No framework, no build tools
- **5 HTML pages:** login.html, signup.html, dashboard.html, profile.html, about.html
- **Fonts:** Geist Mono + DM Sans (Google Fonts)
- **Dark theme** with terminal-inspired aesthetic
- **Responsive design** — sidebar hidden on mobile (<680px)

### 5.12 Protocol
- **MCP (Model Context Protocol)** via FastMCP — 9 tools, 3 resources, 7 prompts
- Compatible with Claude Desktop, Cursor IDE, and any MCP client

### 5.13 Deployment
- **Docker** — Multi-stage build with CPU-only PyTorch (~800MB vs ~3.5GB CUDA)
- **Railway** — Cloud deployment with automatic GitHub integration

### 5.14 Key Python Libraries
```
groq>=0.9.0                     # LLM API client
chromadb>=0.5.0                 # Vector database
sentence-transformers>=3.0.0    # Text embeddings
beautifulsoup4>=4.12.0          # HTML parsing
requests>=2.32.0                # HTTP client
pypdf>=4.0.0                    # PDF text extraction
python-docx>=1.1.0              # DOCX text extraction
pandas>=2.0.0                   # Excel processing
openpyxl>=3.1.0                 # Excel file support
ddgs>=6.0.0                     # DuckDuckGo search
python-dotenv>=1.0.0            # Environment config
google-api-python-client>=2.100 # Google APIs
google-auth>=2.23.0             # Google authentication
dateparser>=1.2.0               # Natural language date parsing
python-dateutil>=2.9.0          # Date utility functions
fastapi>=0.110.0                # Web framework
uvicorn[standard]>=0.29.0       # ASGI server
pydantic>=2.0.0                 # Data validation
mcp[cli]>=1.0.0                 # Model Context Protocol
sqlalchemy>=2.0.0               # Database ORM
psycopg2-binary>=2.9.0          # PostgreSQL adapter
bcrypt>=4.0.0                   # Password hashing
python-jose[cryptography]>=3.3  # JWT tokens
python-multipart>=0.0.9         # File uploads
email-validator>=2.0.0          # Email validation
```

---

## 6. SYSTEM ARCHITECTURE

### 6.1 High-Level Architecture (Layered)

```
CLIENT LAYER
  ├── Browser (login.html / signup.html / dashboard.html / profile.html / about.html)
  ├── Terminal (test_terminal.py)
  └── MCP Clients (Claude Desktop / Cursor IDE / any MCP client)
         │
AUTH LAYER — JWT Bearer Tokens
  ├── POST /auth/register    → create user, return JWT
  ├── POST /auth/login       → verify credentials, return JWT
  ├── GET  /auth/me          → current user profile
  └── PATCH /auth/me         → update profile
         │
API GATEWAY — FastAPI (backend/app.py)
  ├── POST /chat             → main chat endpoint (JWT required)
  ├── POST /reset            → clear session memory
  ├── GET  /sessions         → list user's chat sessions
  ├── GET  /health           → system health check
  └── POST /voice/transcribe → audio → text via Groq Whisper
         │
CHAT ENGINE — 7-Step Processing Pipeline (backend/chat_engine.py)
  ├── Step 1: Confirmation Detection  → LLM classifies: confirm / cancel / new_info
  ├── Step 2: Action Planning         → LLM extracts intent + structured JSON arguments
  ├── Step 3: Validation              → Anti-hallucination checks on all arguments
  ├── Step 4: RAG Answer              → ChromaDB vector search → LLM synthesizes answer
  ├── Step 5: Direct Execution        → weather / news / search / summarize (no confirmation)
  ├── Step 6: Missing Field Collection → multi-turn conversation to gather required fields
  └── Step 7: Preview + Confirm       → full preview shown → user types "yes" to execute
         │
VALIDATOR LAYER — Anti-Hallucination (core/validators.py)
  ├── Email addresses  → regex-verified against actual user messages (RFC 5322)
  ├── Calendar dates   → validated as parseable + in the future
  ├── Event titles     → minimum 3 chars, max 200, no placeholders
  ├── Email bodies     → minimum 10 chars, no LLM placeholder patterns
  └── All arguments    → type-checked before any API call
         │
EXECUTION LAYER — Python Only, Zero LLM Involvement
  ├── Gmail API          → email_service.py
  ├── Google Calendar    → calendar_service.py
  ├── NewsAPI            → news_service.py
  ├── OpenWeatherMap     → weather_service.py
  ├── DuckDuckGo/Wiki    → web_search_service.py
  ├── Document Summarizer → summarizer_service.py
  └── ChromaDB RAG       → rag_pipeline.py
         │
MCP SERVER — 9 Tools + 3 Resources + 7 Prompts (mcp_server.py)
  └── Compatible with Claude Desktop, Cursor IDE, any MCP client
```

### 6.2 Project Directory Structure

```
ai-action-assistant/
│
├── backend/
│   ├── app.py               # FastAPI app — all routes, middleware, lifespan
│   ├── auth.py              # JWT auth — register, login, get_current_user
│   ├── chat_engine.py       # 7-step processing pipeline (core brain) — 359 lines
│   ├── google_auth.py       # Per-user Google OAuth2 flow — 232 lines
│   ├── session_store.py     # Session management — in-memory cache + DB persistence
│   └── schemas.py           # Pydantic request/response models
│
├── core/
│   ├── action_controller.py # Required field validation per action type — 115 lines
│   ├── embedding.py         # Sentence Transformers embedding wrapper — 66 lines
│   ├── ingestion.py         # URL → text ingestion pipeline — 54 lines
│   ├── intent_parser.py     # 4-strategy datetime extraction — 176 lines
│   ├── llm_service.py       # 3-tier LLM routing + all prompts — 458 lines
│   ├── memory_manager.py    # Rolling conversation buffer + LLM compression — 141 lines
│   ├── rag_pipeline.py      # RAG — vector search + LLM response synthesis — 95 lines
│   └── validators.py        # Anti-hallucination validators — 460 lines
│
├── db/
│   ├── database.py          # SQLAlchemy engine + session factory — 65 lines
│   └── models.py            # ORM models — User, GoogleToken, ChatSession, Message — 81 lines
│
├── services/
│   ├── calendar_service.py  # Google Calendar API integration — 113 lines
│   ├── email_service.py     # Gmail API integration — 161 lines
│   ├── news_service.py      # NewsAPI + web search fallback — 171 lines
│   ├── summarizer_service.py# Multi-source summarization (URL/file/text) — 293 lines
│   ├── voice_service.py     # Groq Whisper STT — 77 lines
│   ├── weather_service.py   # OpenWeatherMap integration — 131 lines
│   └── web_search_service.py# DuckDuckGo + Wikipedia fallback — 205 lines
│
├── static/
│   ├── login.html           # Sign-in page (14KB)
│   ├── signup.html          # Account creation page (13KB)
│   ├── dashboard.html       # Full chat UI (69KB) — the main application
│   ├── profile.html         # User profile page (16KB)
│   └── about.html           # About page (18KB)
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
├── mcp_server.py            # FastMCP server entry point — 9 tools, 772 lines
├── config.py                # Centralized config from environment — 166 lines
├── run_api.py               # FastAPI server entry point
├── run_mcp.py               # MCP server entry point
│
├── Dockerfile               # Docker container (Railway optimized, CPU-only PyTorch)
├── Railway.json             # Railway deployment config
├── requirements.txt         # 56 lines of Python dependencies
└── .env.example             # 35+ environment variable template
```

**Total Lines of Code:**
- Backend (Python): ~4,200+ lines across 25+ modules
- Frontend (HTML/CSS/JS): ~130KB across 5 self-contained pages
- Configuration & DevOps: ~300+ lines

---

## 7. DETAILED MODULE DESCRIPTIONS

### 7.1 `backend/chat_engine.py` — The 7-Step Processing Pipeline

This is the **core brain** of the application. Every user message flows through this pipeline:

**Step 1: Confirmation Detection**
- If a pending action exists (e.g., user was shown an email preview), the LLM classifies the user's reply as `confirm`, `cancel`, or `new_info`
- If `confirm` → execute the pending action immediately
- If `cancel` → discard the pending action
- If `new_info` → re-plan with updated information

**Step 2: Action Planning**
- The LLM receives the user message + conversation history
- Outputs a structured JSON plan: `{"action": "email", "arguments": {"to": [...], "subject": "...", "body": "..."}}`
- Supported actions: `email`, `calendar`, `news`, `weather`, `web_search`, `summarize`, `rag`
- Service selection hints are passed when the user has toggled specific service chips in the UI

**Step 3: Validation (Anti-Hallucination)**
- All extracted arguments pass through `core/validators.py`
- Email addresses are regex-matched against actual user messages
- Calendar dates are validated as parseable and in the future
- Any fabricated data is stripped — the system asks the user again

**Step 4: RAG Answer**
- If action is `rag`, perform vector similarity search in ChromaDB
- Retrieve top-5 matching document chunks above similarity threshold
- LLM synthesizes an answer from retrieved context + conversation history
- Falls back to LLM general knowledge if no relevant documents found

**Step 5: Direct Execution**
- Actions that don't require confirmation: `weather`, `news`, `web_search`, `summarize`
- Execute immediately via the respective service module
- Return formatted result to the user

**Step 6: Email Auto-Draft**
- For email actions, if body/subject are missing, the LLM drafts a professional email
- Uses Tier 2 (MEDIUM) model for writing quality
- The draft is then shown to the user for review, not sent directly

**Step 7: Missing Field Collection**
- If required fields are still missing (e.g., email recipient, calendar date), enter a multi-turn collection loop
- The LLM generates a natural language prompt asking for the specific missing field
- The pending_action scratchpad preserves previously collected fields across turns

**Step 8: Preview + Confirm**
- For email and calendar actions, a full preview is shown
- Session state is set to `awaiting_confirmation`
- The action only executes when the user explicitly confirms

### 7.2 `core/llm_service.py` — 3-Tier LLM Routing

**Architecture:**
- Maintains a pool of Groq API clients (one per unique API key)
- Routes each LLM call to the appropriate tier based on task complexity
- Implements automatic retry with fallback to PRIMARY key on rate limit errors

**System Prompts:**
- `BASE_SYSTEM_PROMPT` — Personality, response quality rules, accuracy rules
- `ACTION_PLANNER_PROMPT` — Strict intent classifier with JSON output schema
- `EMAIL_DRAFTER_PROMPT` — Professional email writing with structured format
- `CALENDAR_DESCRIPTION_PROMPT` — Event description generation
- `MISSING_FIELD_PROMPT` — Natural language field collection

**Functions:**
- `plan_action()` → Tier 1 PRIMARY — Intent detection + argument extraction
- `detect_confirmation()` → Tier 3 LIGHT — yes/no/new_info classification
- `get_llm_response()` → Tier 1 PRIMARY — RAG answer synthesis
- `draft_email()` → Tier 2 MEDIUM — Professional email writing
- `draft_event_description()` → Tier 2 MEDIUM — Calendar event description
- `generate_missing_field_prompt()` → Tier 3 LIGHT — Natural language prompts

### 7.3 `core/validators.py` — Anti-Hallucination Validation Layer (460 lines)

**Email Validation:**
- `is_valid_email_format()` — RFC 5322 regex validation
- `extract_emails_from_text()` — Find all email-like strings in user text
- `validate_email_address()` — Format check + CRITICAL: verify email was typed by user, not fabricated by LLM
- `validate_email_list()` — Batch validation of multiple recipients
- `validate_email_body()` — Reject bodies with LLM placeholder patterns like `[INSERT`, `[YOUR`, `[FILL`, `<INSERT`
- `validate_email_subject()` — Length and emptiness checks

**Calendar Validation:**
- `validate_datetime_phrase()` — 4-strategy datetime parser + future date enforcement
- `validate_event_title()` — Min 3 chars, max 200 chars, reject placeholders ("test", "asdf", "tbd", etc.)

**Weather Validation:**
- `validate_weather_action()` — City name length checks (2-100 chars)

**Web Search Validation:**
- `validate_web_search_action()` — Query length checks, auto-trim >300 chars

**Summarize Validation:**
- `validate_summarize_action()` — At least one of content/url/file_path must be provided

### 7.4 `core/memory_manager.py` — Conversation Memory (141 lines)

**ConversationMemory class:**
- Rolling buffer of last N turns (default 10)
- When buffer exceeds 2x max, oldest half is compressed into a summary using LLM (Tier 3 LIGHT)
- Summary preserves key decisions, names, emails, dates, and confirmed actions
- `get_context_block()` returns combined summary + recent 3 exchanges for RAG queries
- **Pending Action Scratchpad:** maintains state across multi-turn field collection
- `merge_action_arguments()` — Smart merge of new extracted fields into pending action

### 7.5 `core/intent_parser.py` — Datetime Extraction (176 lines)

**4-Strategy Approach:**
1. **"Next weekday" handler** — Explicitly handles "next Monday at 10am" (dateparser fails on these)
2. **dateparser with future preference** — Best for absolute dates like "March 22 2026 at 3pm"
3. **dateutil fuzzy parsing** — Good fallback for ambiguous/messy phrases
4. **Original phrase retry** — Try original before typo correction was applied

**Features:**
- Common typo correction: "match" → "march", "sept" → "september", etc.
- Filler word removal: "on 22 march" → "22 march"
- Default time: 9:00 AM if no time specified

### 7.6 `core/rag_pipeline.py` — RAG Pipeline (95 lines)

**Flow:**
1. Generate query embedding using Sentence Transformers
2. Query ChromaDB for top-5 similar chunks
3. Filter by similarity threshold (0.45)
4. Build context: KB chunks + conversation history
5. If KB context found → use Tier 1 PRIMARY for best quality answer
6. If no KB context → use Tier 3 LIGHT for general conversation (saves token budget)

### 7.7 `core/embedding.py` — Embedding Service (66 lines)

- Singleton `SentenceTransformer` model: `all-MiniLM-L6-v2`
- `chunk_text()` — Split text into 500-character overlapping chunks (100 char overlap)
- `generate_embeddings()` — Batch encoding with no progress bar

### 7.8 `core/vector_store.py` — ChromaDB Wrapper (88 lines)

- Persistent client with cosine similarity HNSW index
- `store_documents()` — Add chunks with embeddings (UUID-based IDs)
- `query_similar()` — Retrieve most similar chunks sorted by ascending distance
- `collection_count()` — Return total stored document count

### 7.9 `core/ingestion.py` — Web Content Ingestion (54 lines)

- `fetch_url_content()` — Download URL, parse HTML with BeautifulSoup, extract clean text
- `ingest_urls()` — Process multiple URLs → chunk → embed → store in vector DB
- Default URLs: Wikipedia articles on Srinivasa Ramanujan and India

### 7.10 `services/email_service.py` — Gmail API Integration (161 lines)

- **Per-user OAuth2:** First checks DB for user-specific Google token
- **Fallback:** Shared `token.pickle` for legacy/admin setup
- Sends both plain text and HTML versions (multipart/alternative)
- Detailed error handling: permission denied, invalid grant, token expired

### 7.11 `services/calendar_service.py` — Google Calendar API (113 lines)

- Creates events with custom reminders: 10-minute popup + 1-day email
- Supports title, date, time, duration, description, location
- Returns event link for direct access

### 7.12 `services/news_service.py` — NewsAPI + Fallback (171 lines)

- Supports 7 categories: business, entertainment, general, health, science, sports, technology
- Topic extraction from natural language: removes stop words
- **Automatic fallback** to DuckDuckGo/Wikipedia when NewsAPI returns no results
- Text cleaning: removes URLs, brackets, special characters

### 7.13 `services/weather_service.py` — OpenWeatherMap (131 lines)

- Returns temperature (°C), feels-like, humidity, wind speed (km/h), visibility (km)
- Handles 404 (city not found), 401 (invalid key), and timeout errors
- Formatted output with aligned key-value pairs

### 7.14 `services/web_search_service.py` — Multi-Strategy Search (205 lines)

**4 fallback strategies:**
1. `ddgs` (new package)
2. `duckduckgo_search` (old package)
3. Wikipedia API (always works)
4. LLM knowledge fallback

### 7.15 `services/summarizer_service.py` — Multi-Source Summarization (293 lines)

**Supports 3 sources:**
1. Uploaded files: PDF (pypdf), DOCX (python-docx), XLSX (pandas), TXT
2. URLs: fetches page, extracts with BeautifulSoup, targets article/main content
3. Raw text: inline pasted content

**Processing:** Content capped at 8000 characters → LLM summarization via Tier 1

### 7.16 `services/voice_service.py` — Speech-to-Text (77 lines)

- Groq Whisper API: `whisper-large-v3-turbo` model
- MIME type detection for webm, mp4, wav, ogg, m4a, flac
- 30-second timeout, no speech detection handling

### 7.17 `backend/auth.py` — JWT Authentication (163 lines)

- `RegisterRequest` — email, password, optional name
- `_hash_password()` — bcrypt with auto-generated salt
- `_verify_password()` — bcrypt comparison
- `_create_token()` — JWT with user_id, email, expiry
- `get_current_user()` — FastAPI dependency that validates JWT and returns User row
- Profile update via PATCH `/auth/me`

### 7.18 `backend/google_auth.py` — Per-User Google OAuth2 (232 lines)

**Routes:**
- `GET /auth/google/connect` — Start OAuth flow (redirect to Google)
- `GET /auth/google/callback` — Handle redirect, exchange code for token, save to DB
- `GET /auth/google/status` — Check if user has connected Google
- `DELETE /auth/google/disconnect` — Remove user's Google token

**Implementation:**
- State tokens stored in-memory for CSRF protection
- Token auto-refresh on expiry
- Base64-encoded pickle storage in `google_tokens` table
- Scopes: Calendar + Gmail Send + OpenID + UserInfo Email

### 7.19 `backend/session_store.py` — Session Management (124 lines)

- `Session` class wraps DB row + in-memory ConversationMemory
- Lazy-loading: last 20 messages loaded from DB on first access
- Thread-safe in-process cache with `threading.Lock`
- `persist_message()` — Save to DB
- `get_user_sessions()` — List all sessions for a user (newest first, limit 50)

### 7.20 `db/models.py` — Database Models (81 lines)

**4 tables:**
- `users` — id (UUID), email (unique, indexed), password (bcrypt hash), name, avatar_url, bio, created_at, is_active
- `google_tokens` — id, user_id (FK), token_data (base64 pickle), email, created_at, updated_at
- `sessions` — id (UUID), user_id (FK), title (default "New Conversation"), created_at, updated_at
- `messages` — id (autoincrement), session_id (FK), role ("user"/"assistant"), content, created_at

### 7.21 `config.py` — Centralized Configuration (166 lines)

- Loads from `.env` file via `python-dotenv`
- 35+ environment variables with sensible defaults
- `validate()` — Startup check for critical config (GROQ_API_KEY)
- Auto-creates upload and ChromaDB directories

### 7.22 `mcp_server.py` — MCP Protocol Server (772 lines)

**9 Tools:**
1. `chat()` — Master brain, universal natural language routing
2. `weather_service()` — Current weather
3. `web_search_service()` — Internet search
4. `summarizer_service()` — URL/text/file summarization
5. `email_service()` — Full email workflow
6. `calendar_service()` — Full calendar workflow
7. `news_service()` — Live news headlines
8. `reset_conversation()` — Clear memory
9. `get_system_status()` — Health check

**3 Resources:**
- `config://settings` — Current configuration snapshot
- `kb://status` — Knowledge base document count
- `help://guide` — Usage guide

**7 Prompts (Quick-start templates):**
- compose_email, schedule_event, search_web, get_weather, summarize_url, get_news, ask_question

---

## 8. KEY ALGORITHMS AND TECHNIQUES

### 8.1 Intent Classification Algorithm
1. User message + last 1 exchange from history → ACTION_PLANNER_PROMPT
2. LLM outputs structured JSON with `action` + `arguments`
3. Service selection hints modify routing (user-toggled UI chips)
4. JSON parsing with regex fallback for extracting JSON from markdown code blocks

### 8.2 Anti-Hallucination Algorithm
1. Extract all email-like strings from ALL user messages in the conversation
2. Compare LLM-provided email against user-provided emails (case-insensitive)
3. If no match found → strip the email field, mark as missing
4. For dates: parse with dateparser → validate as future → reject past dates
5. For email bodies: scan for LLM placeholder patterns using regex

### 8.3 RAG Pipeline Algorithm
1. User query → Sentence Transformer embedding (384 dimensions)
2. ChromaDB cosine similarity search → top-5 chunks
3. Filter: only chunks with distance < 0.45 (threshold)
4. Context = filtered KB chunks + conversation summary + recent exchanges
5. LLM synthesizes answer from context
6. Tier routing: use PRIMARY if KB context found, LIGHT otherwise

### 8.4 Conversation Memory Compression Algorithm
1. Buffer accumulates messages up to 2x max_buffer_turns
2. When threshold exceeded (30 messages), split buffer in half
3. Format oldest half as "ROLE: content" text
4. Send to LLM (Tier 3 LIGHT) with compression prompt
5. LLM returns factual summary preserving key details
6. Append to rolling summary; keep only recent half in buffer

### 8.5 Multi-Strategy Datetime Parsing Algorithm
1. Clean phrase: fix typos, remove filler words
2. Try: "next <weekday>" explicit handler
3. Try: dateparser with PREFER_DATES_FROM=future
4. Try: dateutil fuzzy parsing (reject if result ≈ now)
5. Try: dateparser on original uncleaned phrase
6. Return None if all strategies fail

### 8.6 3-Tier LLM Routing Algorithm
1. Map tier name to (API_KEY, MODEL) tuple
2. Build attempt list: [requested tier, primary fallback]
3. Try first: call Groq API with tier's key + model
4. On RateLimitError: try next attempt (fallback key)
5. On APIStatusError: return user-friendly error message
6. All exhausted: parse retry time from error, return rate-limit notice

### 8.7 Confirmation Gate Architecture
1. After all fields collected and validated → show full preview
2. Set session.awaiting_confirmation = True
3. Store complete plan in memory.pending_action
4. Next user message → detect_confirmation() classifies as confirm/cancel/new_info
5. Confirm → execute via _execute() → return result
6. Cancel → discard plan → return cancellation message
7. New info → re-enter planning pipeline with updated context

---

## 9. DATABASE DESIGN

### 9.1 Entity-Relationship Model

```
┌──────────────┐     1:N     ┌──────────────┐     1:N     ┌──────────────┐
│    users     │────────────→│   sessions   │────────────→│   messages   │
│              │             │              │             │              │
│ id (PK)      │             │ id (PK)      │             │ id (PK, AI)  │
│ email (UQ)   │             │ user_id (FK) │             │ session_id(FK│
│ password     │             │ title        │             │ role         │
│ name         │             │ created_at   │             │ content      │
│ avatar_url   │             │ updated_at   │             │ created_at   │
│ bio          │             └──────────────┘             └──────────────┘
│ created_at   │
│ is_active    │     1:1     ┌──────────────┐
│              │────────────→│google_tokens │
└──────────────┘             │              │
                             │ id (PK)      │
                             │ user_id (FK) │
                             │ token_data   │
                             │ email        │
                             │ created_at   │
                             │ updated_at   │
                             └──────────────┘
```

---

## 10. API ENDPOINTS

### Auth Endpoints
| Method | Endpoint | Auth | Body | Description |
|--------|----------|------|------|-------------|
| POST | /auth/register | No | {email, password, name?} | Create account, returns JWT |
| POST | /auth/login | No | form: username, password | Sign in, returns JWT |
| GET | /auth/me | JWT | — | Current user profile |
| PATCH | /auth/me | JWT | {name?, bio?, avatar_url?} | Update profile |

### Google OAuth Endpoints
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /auth/google/connect | JWT (query param) | Start OAuth flow |
| GET | /auth/google/callback | — | Handle Google redirect |
| GET | /auth/google/status | JWT | Check connection status |
| DELETE | /auth/google/disconnect | JWT | Remove Google token |

### Chat Endpoints
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /chat | JWT | Main chat (JSON or multipart with file) |
| POST | /reset | JWT | Reset session memory |
| GET | /sessions | JWT | List user's chat sessions |
| GET | /health | — | System health check |
| POST | /voice/transcribe | JWT | Audio → text via Whisper |

### Response Status Values
- `success` — action completed
- `error` — something went wrong
- `pending` — collecting missing fields
- `awaiting` — showing preview, needs confirmation
- `cancelled` — user cancelled the action

---

## 11. SECURITY MEASURES

1. **JWT Authentication** — All chat endpoints require valid JWT token
2. **bcrypt Password Hashing** — One-way hash with salt, resistant to rainbow tables
3. **Anti-Hallucination Validation** — LLM cannot fabricate critical data
4. **Confirmation Gate** — Irreversible actions require explicit user approval
5. **Rate Limiting** — 30 requests per session per 60 seconds (configurable)
6. **File Upload Limits** — Max 10MB, allowed extensions: .pdf, .docx, .xlsx, .xls, .txt
7. **CORS Configuration** — Restricted to known origins
8. **Input Sanitization** — All user inputs stripped and validated
9. **OAuth2 State Tokens** — CSRF protection for Google OAuth flow
10. **Environment Variable Security** — Secrets stored in .env, never committed to git

---

## 12. FRONTEND DESIGN

### 12.1 Login Page (login.html)
- Centered card layout (max-width 400px) on dark background
- AI logo mark + "AI Action Assistant" branding
- Email + Password fields, "Sign In" button
- JWT stored in localStorage on success → redirect to /dashboard
- Error display with red banner
- Link to signup page

### 12.2 Signup Page (signup.html)
- Same card layout as login
- Full Name (optional) + Email + Password (min 8 chars)
- "Create Account" button → JWT stored → redirect to dashboard

### 12.3 Dashboard (dashboard.html — 69KB, the main application)
- **Two-column layout:** Fixed sidebar (260px) + main chat area
- **Sidebar features:**
  - Logo + "New conversation" button
  - 6 service selector chips: Weather 🌤, News 📰, Search 🔍, Email 📧, Calendar 📅, Summarize 📄
  - Chat history list with delete buttons
  - Google account connection button
  - Status indicator: Connected + model name
- **Chat area features:**
  - Message bubbles with AI/user avatars
  - Status badges: SUCCESS · WEATHER, AWAITING · CALENDAR, etc.
  - Inline Confirm/Cancel buttons for pending actions
  - Copy-to-clipboard on every message
  - Typing indicator with animated dots
  - File attachment with drag-and-drop
  - Voice input (microphone button → Whisper STT)
  - Voice output (speaker button → Web Speech Synthesis TTS)
  - Quick-action chips for common queries
  - Welcome screen when no messages
- **Responsive:** Sidebar hidden on mobile (<680px)

### 12.4 Profile Page (profile.html)
- User avatar, name, email, bio
- Edit profile form
- Google account connection status

### 12.5 About Page (about.html)
- Project description, features, and credits

---

## 13. DEPLOYMENT ARCHITECTURE

### 13.1 Docker Configuration
- Base image: `python:3.11-slim`
- NumPy pinned to <2 for torch compatibility
- CPU-only PyTorch (~800MB vs ~3.5GB CUDA)
- Separate installation steps for torch → sentence-transformers → remaining deps
- Creates /app/uploads, /app/chroma_db, /tmp/uploads, /app/static directories

### 13.2 Railway Deployment
- Auto-detects Dockerfile
- Environment variables set via Railway dashboard
- Google auth tokens encoded as base64 environment variables
- PostgreSQL database auto-provisioned
- Custom startup script decodes GOOGLE_TOKEN_B64 → token.pickle

---

## 14. TESTING

### 14.1 Terminal Chat Client (test_terminal.py)
- Interactive terminal interface for testing all features
- Supports file paths, session management, and multi-turn conversations

### 14.2 MCP Tool Tests (test_mcp.py)
- Tests all 9 MCP tools individually
- Can target specific tools: `--tool weather_service`

### 14.3 MCP Inspector
- Browser UI at localhost:5173
- Visual interaction with all 9 tools

---

## 15. DEVELOPMENT JOURNEY — 9 REBUILDS

1. **Rebuilds 1–3:** Separating LLM reasoning from Python execution. Early versions let the LLM "pretend" to execute actions.
2. **Rebuilds 4–5:** Multi-turn field collection with proper state management. Early versions lost context between turns.
3. **Rebuilds 6–7:** Anti-hallucination validation layer. The LLM was fabricating email addresses and dates.
4. **Rebuild 8:** Confirmation gate architecture. Actions were executing without user approval.
5. **Rebuild 9:** MCP protocol integration + production hardening (auth, rate limiting, DB persistence, Docker).

---

## 16. FEATURES SUMMARY

| Feature | Technology | Status |
|---------|-----------|--------|
| User authentication (JWT) | FastAPI + SQLite/PostgreSQL | ✅ Live |
| Per-user Google OAuth2 | Google OAuth2 | ✅ Live |
| Email sending | Gmail API (OAuth2) | ✅ Live |
| Calendar scheduling | Google Calendar API (OAuth2) | ✅ Live |
| Live news | NewsAPI + Web Search fallback | ✅ Live |
| Real-time weather | OpenWeatherMap API | ✅ Live |
| Web search | DuckDuckGo + Wikipedia fallback | ✅ Live |
| Document summarization | Groq LLM + pypdf + python-docx | ✅ Live |
| RAG knowledge base | ChromaDB + Sentence Transformers | ✅ Live |
| Voice input (STT) | Groq Whisper API | ✅ Live |
| Voice output (TTS) | Browser Web Speech Synthesis | ✅ Live |
| MCP server | FastMCP — 9 tools, 3 resources, 7 prompts | ✅ Live |
| File upload | PDF/DOCX/XLSX/TXT (max 10MB) | ✅ Live |
| Conversation memory | Rolling buffer + LLM compression | ✅ Live |
| Anti-hallucination | Custom Python validators | ✅ Live |
| Rate limiting | In-memory per-session counter | ✅ Live |
| Persistent chat sessions | SQLite (local) / PostgreSQL (Railway) | ✅ Live |
| Multi-page responsive UI | Vanilla HTML/CSS/JS | ✅ Live |
| Docker deployment | Railway (cloud) | ✅ Live |

---

## 17. DATA FLOW DIAGRAMS (TEXTUAL)

### 17.1 Email Sending Flow
```
User: "send email to ravi about the meeting"
  → Plan: {action: email, to: null, recipient_name: "ravi"}
  → Validate: to is null → missing_fields: ["to"]
  → Return: "What's Ravi's email address?"

User: "ravi@example.com"
  → Plan: {action: rag} → merge with pending: {action: email, to: ["ravi@example.com"], recipient_name: "ravi"}
  → Validate: email found in user message ✅
  → Draft email via Tier 2 MEDIUM
  → Validate: body and subject present ✅
  → Preview shown: "To: ravi@example.com, Subject: Meeting Update, Body: ..."
  → Return: "Confirm sending? (yes/no)"

User: "yes"
  → detect_confirmation() → "confirm"
  → execute() → Gmail API sends email
  → Return: "Email sent successfully! ✉️"
```

### 17.2 Weather Query Flow
```
User: "what's the weather in Mumbai?"
  → Plan: {action: weather, city: "Mumbai"}
  → Validate: city present ✅, length OK ✅
  → Execute immediately (no confirmation needed)
  → OpenWeatherMap API → parse response
  → Return: "Weather in Mumbai, IN — 32°C, Humid, ..."
```

### 17.3 RAG Query Flow
```
User: "tell me about Ramanujan's contributions"
  → Plan: {action: rag}
  → generate embedding for query
  → ChromaDB search → 3 chunks with score < 0.45
  → Context = KB chunks + conversation history
  → LLM (Tier 1 PRIMARY) synthesizes answer
  → Return: "Srinivasa Ramanujan made groundbreaking contributions..."
```

---

## 18. ENVIRONMENT VARIABLES (35+)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| GROQ_API_KEY_PRIMARY | Yes | — | Tier 1 LLM key |
| GROQ_MODEL_PRIMARY | No | openai/gpt-oss-120b | Tier 1 model |
| GROQ_API_KEY_MEDIUM | No | falls back to PRIMARY | Tier 2 LLM key |
| GROQ_MODEL_MEDIUM | No | llama-3.3-70b-versatile | Tier 2 model |
| GROQ_API_KEY_LIGHT | No | falls back to PRIMARY | Tier 3 LLM key |
| GROQ_MODEL_LIGHT | No | llama-3.1-8b-instant | Tier 3 model |
| EMAIL_USER | For email | — | Gmail address |
| NEWS_API_KEY | For news | — | NewsAPI.org key |
| OPENWEATHER_API_KEY | For weather | — | OpenWeatherMap key |
| GOOGLE_CREDENTIALS_FILE | Local | credentials.json | Google credentials path |
| GOOGLE_TOKEN_FILE | Local | token.pickle | OAuth token path |
| CALENDAR_TIMEZONE | No | Asia/Kolkata | Timezone |
| WHISPER_MODEL | No | whisper-large-v3-turbo | STT model |
| SIMILARITY_THRESHOLD | No | 0.45 | RAG cutoff |
| RATE_LIMIT_REQUESTS | No | 30 | Max requests per window |
| RATE_LIMIT_WINDOW_SECONDS | No | 60 | Window duration |
| UPLOAD_MAX_BYTES | No | 10485760 | Max file size (10MB) |
| DATABASE_URL | No | SQLite | PostgreSQL URL |
| JWT_SECRET_KEY | No | auto-generated | JWT signing secret |
| ALLOWED_ORIGINS | No | localhost ports | CORS origins |

---

## 19. LITERATURE SURVEY TOPICS

1. **Large Language Models (LLMs)** — Architecture, capabilities, limitations (GPT, LLaMA, etc.)
2. **Agentic AI Systems** — Autonomous AI agents that execute real-world tasks
3. **Retrieval Augmented Generation (RAG)** — Grounding LLM responses in retrieved documents
4. **Vector Databases** — Storage and retrieval of high-dimensional embeddings (ChromaDB, Pinecone, etc.)
5. **Sentence Transformers** — Pre-trained models for semantic text similarity
6. **Anti-Hallucination Techniques** — Validation layers, grounding, and verification in AI systems
7. **Model Context Protocol (MCP)** — Anthropic's protocol for tool-use in AI models
8. **JWT Authentication** — Stateless authentication for web applications
9. **OAuth2 Protocol** — Third-party authorization (Google APIs)
10. **Prompt Engineering** — System prompts, few-shot learning, structured output generation
11. **Conversation Memory Management** — Rolling buffers, summarization, long-term context
12. **Natural Language Understanding (NLU)** — Intent classification and entity extraction
13. **API Gateway Patterns** — FastAPI middleware, rate limiting, CORS
14. **Microservice Architecture** — Service-oriented design with independent modules

---

## 20. FUTURE SCOPE

1. **Agent Orchestrator Layer** — Multi-agent collaboration for complex tasks
2. **Tool Framework with BaseTool** — Pluggable tool architecture
3. **Streaming Responses (SSE)** — Real-time token-by-token response streaming
4. **Redis Session Store** — Horizontal scaling across multiple instances
5. **Multi-user Collaborative Sessions** — Shared workspaces
6. **Advanced RAG** — Hybrid search, re-ranking, document chunking strategies
7. **Multi-modal Input** — Image understanding and generation
8. **Task Scheduling** — Recurring email/calendar automations
9. **Plugin System** — Third-party service integrations (Slack, Notion, etc.)
10. **Mobile App** — React Native or Flutter frontend

---

## 21. AUTHOR INFORMATION (FOR TITLE PAGE)

- **Student Name:** Yash Sakariya
- **Enrollment No:** (Fill in)
- **Branch:** Computer Engineering (Artificial Intelligence)
- **Semester:** 8th
- **Academic Year:** 2025-2026
- **University:** (Fill in)
- **College:** (Fill in)
- **Guide/Mentor Name:** (Fill in)
- **Company:** Infopulse Tech
