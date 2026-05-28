"""
config.py — Centralized configuration from environment variables.

Local   : reads from .env via python-dotenv
AWS     : ECS Task Definition / App Runner / Elastic Beanstalk env vars
Railway : Railway environment variables dashboard

LLM TIER ARCHITECTURE
  TIER 1 PRIMARY  — intent, RAG, confirmation  (openai/gpt-oss-120b)
  TIER 2 MEDIUM   — email, summarize, calendar (llama-3.3-70b-versatile)
  TIER 3 LIGHT    — weather, news, search      (llama-3.1-8b-instant)
  Fallback: any unset tier falls back to PRIMARY key.
"""

import os
import logging
import logging.handlers
from dotenv import load_dotenv

load_dotenv()

# ─── Environment Detection ────────────────────────────────────────────────────
IS_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT"))
IS_AWS     = bool(
    os.getenv("AWS_EXECUTION_ENV") or
    os.getenv("ECS_CONTAINER_METADATA_URI") or
    os.getenv("AWS_REGION")
)
IS_PRODUCTION = IS_RAILWAY or IS_AWS or os.getenv("ENVIRONMENT") == "production"
_is_cloud     = IS_RAILWAY or IS_AWS

# ─── LLM — Tier 1: PRIMARY ────────────────────────────────────────────────────
GROQ_API_KEY_PRIMARY = (
    os.getenv("GROQ_API_KEY_PRIMARY") or
    os.getenv("GROQ_API_KEY", "")
)
GROQ_MODEL_PRIMARY = os.getenv("GROQ_MODEL_PRIMARY", "openai/gpt-oss-120b")

# ─── LLM — Tier 2: MEDIUM ─────────────────────────────────────────────────────
GROQ_API_KEY_MEDIUM = os.getenv("GROQ_API_KEY_MEDIUM") or GROQ_API_KEY_PRIMARY
GROQ_MODEL_MEDIUM   = os.getenv("GROQ_MODEL_MEDIUM", "llama-3.3-70b-versatile")

# ─── LLM — Tier 3: LIGHT ──────────────────────────────────────────────────────
GROQ_API_KEY_LIGHT = os.getenv("GROQ_API_KEY_LIGHT") or GROQ_API_KEY_PRIMARY
GROQ_MODEL_LIGHT   = os.getenv("GROQ_MODEL_LIGHT", "llama-3.1-8b-instant")

# ─── LLM — Legacy single-key alias ────────────────────────────────────────────
GROQ_API_KEY = GROQ_API_KEY_PRIMARY
GROQ_MODEL   = GROQ_MODEL_PRIMARY
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")

# ─── ChromaDB — EBS persistent path on AWS EC2, /app/chroma_db on containers ──
# On AWS EC2 with EBS: mount EBS at /data and set CHROMA_DB_PATH=/data/chromadb
# On ECS/App Runner:   /app/chroma_db (ephemeral — use EFS for persistence)
CHROMA_DB_DIR = os.getenv(
    "CHROMA_DB_PATH",
    os.getenv(
        "CHROMA_DB_DIR",
        "/app/chroma_db" if _is_cloud else "./chroma_db"
    )
)

# ─── File Uploads ─────────────────────────────────────────────────────────────
UPLOAD_DIR = os.getenv(
    "UPLOAD_DIR",
    "/tmp/uploads" if _is_cloud else "./uploads"
)

# ─── Email ────────────────────────────────────────────────────────────────────
EMAIL_USER = os.getenv("EMAIL_USER", "")

# ─── News API ─────────────────────────────────────────────────────────────────
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

# ─── Weather API ──────────────────────────────────────────────────────────────
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

# ─── Gemini API (Embeddings) ─────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ─── Google OAuth2 ────────────────────────────────────────────────────────────
GOOGLE_CLIENT_ID      = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET  = os.getenv("GOOGLE_CLIENT_SECRET", "")
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

# ─── CORS ─────────────────────────────────────────────────────────────────────
# In production set to your CloudFront URL + API domain
# e.g. https://d1234.cloudfront.net,https://api.yourdomain.com
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:8000"
)

# ─── Rate Limiting ────────────────────────────────────────────────────────────
RATE_LIMIT_REQUESTS    = int(os.getenv("RATE_LIMIT_REQUESTS", "30"))
RATE_LIMIT_WINDOW      = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
UPLOAD_MAX_AGE_SECONDS = int(os.getenv("UPLOAD_MAX_AGE_SECONDS", str(60 * 60)))
UPLOAD_MAX_BYTES       = int(os.getenv("UPLOAD_MAX_BYTES", str(10 * 1024 * 1024)))

# ─── Database ─────────────────────────────────────────────────────────────────
# AWS RDS: postgresql://user:password@your-rds-endpoint.rds.amazonaws.com:5432/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ─── Voice ────────────────────────────────────────────────────────────────────
GROQ_AUDIO_URL   = os.getenv("GROQ_AUDIO_URL", "https://api.groq.com/openai/v1/audio/transcriptions")
WHISPER_MODEL    = os.getenv("WHISPER_MODEL", "whisper-large-v3-turbo")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "en")
TTS_PROVIDER     = os.getenv("TTS_PROVIDER", "browser")

# ─── Auth (JWT) ───────────────────────────────────────────────────────────────
JWT_SECRET_KEY   = os.getenv("JWT_SECRET_KEY", "change-me-in-production-please")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "72"))

# ─── API Timeouts ─────────────────────────────────────────────────────────────
EXTERNAL_API_TIMEOUT = int(os.getenv("EXTERNAL_API_TIMEOUT", "30"))


# ─── Structured Logging ───────────────────────────────────────────────────────
def setup_logging():
    """Configure structured logging for production."""
    log_level = logging.DEBUG if not IS_PRODUCTION else logging.INFO
    log_format = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s"

    handlers = [logging.StreamHandler()]

    # File logging only when log dir is writable (EC2, not ECS Fargate)
    log_dir = os.getenv("LOG_DIR", "/app/logs" if _is_cloud else "./logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "app.log"),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    except (OSError, PermissionError):
        pass  # ECS Fargate read-only filesystem — stdout only

    logging.basicConfig(level=log_level, format=log_format, handlers=handlers)


def validate():
    """Validate critical config at startup. Raises EnvironmentError on failure."""
    if not GROQ_API_KEY_PRIMARY:
        raise EnvironmentError(
            "GROQ_API_KEY_PRIMARY (or GROQ_API_KEY) is not set. "
            "Get a free key at https://console.groq.com"
        )
    if not GEMINI_API_KEY:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. "
            "Get a free key at https://aistudio.google.com/app/apikey"
        )
    if IS_PRODUCTION and JWT_SECRET_KEY == "change-me-in-production-please":
        raise EnvironmentError(
            "JWT_SECRET_KEY must be changed from the default insecure value before running in production."
        )

    token_enc_key = os.getenv("TOKEN_ENCRYPTION_KEY", "")
    if IS_PRODUCTION:
        if not token_enc_key:
            raise EnvironmentError(
                "TOKEN_ENCRYPTION_KEY must be set in production. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        try:
            from cryptography.fernet import Fernet
            Fernet(token_enc_key.encode())
        except Exception:
            raise EnvironmentError(
                "TOKEN_ENCRYPTION_KEY is not a valid Fernet key (must be 32-byte URL-safe base64). "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(CHROMA_DB_DIR, exist_ok=True)
