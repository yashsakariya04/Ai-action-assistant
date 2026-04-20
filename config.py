"""
config.py — Centralized configuration loaded entirely from environment variables.

Locally  : reads from .env via python-dotenv
Railway  : reads from Railway environment variables dashboard

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LLM TIER ARCHITECTURE — 3 API Keys × 3 Model Tiers
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This project splits LLM workload across three independent Groq API keys and
model tiers to maximise free-tier token budgets and ensure uninterrupted service.

TIER 1 — PRIMARY  (GROQ_API_KEY_PRIMARY  +  GROQ_MODEL_PRIMARY)
  Default model : openai/gpt-oss-120b
  Token budget  : highest quality, used sparingly for critical reasoning
  Assigned tasks:
    • Action planning / intent detection   — needs best JSON accuracy
    • Confirmation detection               — needs nuance understanding
    • Missing field prompt generation      — needs natural language quality
    • RAG response synthesis               — needs best answer quality

TIER 2 — MEDIUM   (GROQ_API_KEY_MEDIUM   +  GROQ_MODEL_MEDIUM)
  Default model : llama-3.3-70b-versatile
  Token budget  : large context, good writing quality
  Assigned tasks:
    • Email drafting                       — needs professional writing
    • Document summarization               — long context, high volume
    • Calendar event description drafting  — structured output

TIER 3 — LIGHT    (GROQ_API_KEY_LIGHT    +  GROQ_MODEL_LIGHT)
  Default model : llama-3.1-8b-instant  (or openai/gpt-oss-20b)
  Token budget  : 500k+ TPD, ultra-fast, high volume
  Assigned tasks:
    • Weather response formatting          — simple, fast
    • News response formatting             — simple, fast
    • Web search result formatting         — simple, fast
    • General conversation fallback        — when primary is exhausted

FALLBACK BEHAVIOUR:
  If a tier's API key is not set, it automatically falls back to the
  next available key. If only one key is configured, all tiers use it.
  This means the system works with 1, 2, or 3 keys — no code changes needed.

  Single key setup  : set only GROQ_API_KEY_PRIMARY (or legacy GROQ_API_KEY)
  Two key setup     : set PRIMARY + LIGHT (medium falls back to primary)
  Full three key    : set all three for maximum token budget

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ─── LLM — Tier 1: PRIMARY ────────────────────────────────────────────────────
# Best reasoning model. Used for intent detection, RAG, confirmation, prompts.
# Falls back to GROQ_API_KEY (legacy single-key setup) if not set.
GROQ_API_KEY_PRIMARY = (
    os.getenv("GROQ_API_KEY_PRIMARY") or
    os.getenv("GROQ_API_KEY", "")
)
GROQ_MODEL_PRIMARY = os.getenv("GROQ_MODEL_PRIMARY", "openai/gpt-oss-120b")

# ─── LLM — Tier 2: MEDIUM ─────────────────────────────────────────────────────
# Good writing quality + large context. Used for email drafting, summarization.
# Falls back to PRIMARY key if not set.
GROQ_API_KEY_MEDIUM = (
    os.getenv("GROQ_API_KEY_MEDIUM") or
    GROQ_API_KEY_PRIMARY
)
GROQ_MODEL_MEDIUM = os.getenv("GROQ_MODEL_MEDIUM", "llama-3.3-70b-versatile")

# ─── LLM — Tier 3: LIGHT ──────────────────────────────────────────────────────
# Ultra-fast, high token budget. Used for weather/news/search formatting.
# Falls back to PRIMARY key if not set.
GROQ_API_KEY_LIGHT = (
    os.getenv("GROQ_API_KEY_LIGHT") or
    GROQ_API_KEY_PRIMARY
)
GROQ_MODEL_LIGHT = os.getenv("GROQ_MODEL_LIGHT", "llama-3.1-8b-instant")

# ─── LLM — Legacy single-key alias (backward compatible) ──────────────────────
# If you only have one Groq key, set GROQ_API_KEY and everything works.
GROQ_API_KEY = GROQ_API_KEY_PRIMARY
GROQ_MODEL   = GROQ_MODEL_PRIMARY

# ─── LLM — Provider ───────────────────────────────────────────────────────────
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")

# ─── Vector DB ────────────────────────────────────────────────────────────────
CHROMA_DB_DIR = os.getenv(
    "CHROMA_DB_DIR",
    "/app/chroma_db" if os.getenv("RAILWAY_ENVIRONMENT") else "./chroma_db"
)

# ─── File Uploads ─────────────────────────────────────────────────────────────
UPLOAD_DIR = os.getenv(
    "UPLOAD_DIR",
    "/tmp/uploads" if os.getenv("RAILWAY_ENVIRONMENT") else "./uploads"
)

# ─── Email ────────────────────────────────────────────────────────────────────
EMAIL_USER = os.getenv("EMAIL_USER", "")

# ─── News API ─────────────────────────────────────────────────────────────────
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

# ─── Weather API ──────────────────────────────────────────────────────────────
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

# ─── Google Calendar + Gmail ──────────────────────────────────────────────────
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_TOKEN_FILE       = os.getenv("GOOGLE_TOKEN_FILE", "token.pickle")
CALENDAR_TIMEZONE       = os.getenv("CALENDAR_TIMEZONE", "Asia/Kolkata")

# ─── RAG ──────────────────────────────────────────────────────────────────────
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.45"))
DEFAULT_URLS = [
    url.strip()
    for url in os.getenv(
        "DEFAULT_URLS",
        "https://en.wikipedia.org/wiki/Srinivasa_Ramanujan,https://en.wikipedia.org/wiki/India"
    ).split(",")
    if url.strip()
]

# ─── Environment Detection ────────────────────────────────────────────────────
IS_RAILWAY    = bool(os.getenv("RAILWAY_ENVIRONMENT"))
IS_PRODUCTION = IS_RAILWAY or os.getenv("ENVIRONMENT") == "production"

# ─── API / Security ───────────────────────────────────────────────────────────
ALLOWED_ORIGINS        = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:8000")
RATE_LIMIT_REQUESTS    = int(os.getenv("RATE_LIMIT_REQUESTS", "30"))
RATE_LIMIT_WINDOW      = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
UPLOAD_MAX_AGE_SECONDS = int(os.getenv("UPLOAD_MAX_AGE_SECONDS", str(60 * 60)))
UPLOAD_MAX_BYTES       = int(os.getenv("UPLOAD_MAX_BYTES", str(10 * 1024 * 1024)))

# ─── Database ─────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "")

# --- Voice -- STT: Groq Whisper ----------------------------------------------
# TTS uses browser Web Speech Synthesis API (client-side, no backend needed).
# Upgrade path: set TTS_PROVIDER=azure or TTS_PROVIDER=google when ready.
GROQ_AUDIO_URL   = os.getenv("GROQ_AUDIO_URL", "https://api.groq.com/openai/v1/audio/transcriptions")
WHISPER_MODEL    = os.getenv("WHISPER_MODEL", "whisper-large-v3-turbo")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "en")
TTS_PROVIDER     = os.getenv("TTS_PROVIDER", "browser")  # browser | azure | google

# ─── Auth (JWT) ───────────────────────────────────────────────────────────────
JWT_SECRET_KEY   = os.getenv("JWT_SECRET_KEY", "change-me-in-production-please")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "72"))


def validate():
    """Validate critical config at startup. Raises EnvironmentError on failure."""
    if not GROQ_API_KEY_PRIMARY:
        raise EnvironmentError(
            "GROQ_API_KEY_PRIMARY (or GROQ_API_KEY) is not set. "
            "Get a free key at https://console.groq.com"
        )
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(CHROMA_DB_DIR, exist_ok=True)
