"""
app.py — FastAPI application (AWS production-ready).

Routes:
  GET  /           — Login page
  GET  /health     — Health check (used by ALB / ECS / App Runner)
  POST /auth/register  — Sign up
  POST /auth/login     — Sign in -> JWT
  GET  /auth/me        — Current user profile
  POST /chat       — Main chat endpoint (requires JWT)
  POST /reset      — Reset a session
  GET  /sessions   — List user's chat sessions
"""

import sys
import logging
import os
import uuid
import time
import threading
from contextlib import asynccontextmanager
from collections import defaultdict
from typing import Optional

import config
config.setup_logging()

from fastapi import FastAPI, Form, File, UploadFile, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.orm import Session as DBSession

from backend.schemas import ChatResponse
from backend.auth import get_current_user, router as auth_router
from backend.google_auth import router as google_auth_router
from db.database import get_db, init_db
from db.models import User

log = logging.getLogger(__name__)

# ── Rate limiting ─────────────────────────────────────────────
RATE_LIMIT_REQUESTS = config.RATE_LIMIT_REQUESTS
RATE_LIMIT_WINDOW   = config.RATE_LIMIT_WINDOW
_rate_counters: dict = defaultdict(list)
_rate_lock = threading.Lock()


def _is_rate_limited(session_id: str) -> bool:
    now = time.time()
    with _rate_lock:
        timestamps = _rate_counters[session_id]
        _rate_counters[session_id] = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
        if len(_rate_counters[session_id]) >= RATE_LIMIT_REQUESTS:
            return True
        _rate_counters[session_id].append(now)
        return False


# ── Upload cleanup ────────────────────────────────────────────
def _cleanup_uploads():
    try:
        cutoff = time.time() - config.UPLOAD_MAX_AGE_SECONDS
        for fname in os.listdir(config.UPLOAD_DIR):
            fpath = os.path.join(config.UPLOAD_DIR, fname)
            if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                os.remove(fpath)
    except Exception as exc:
        log.warning("Upload cleanup error: %s", exc)


def _start_cleanup_thread():
    def _loop():
        while True:
            time.sleep(1800)
            _cleanup_uploads()
    threading.Thread(target=_loop, daemon=True).start()


# ── Startup / shutdown ────────────────────────────────────────
_startup_error = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _startup_error
    try:
        config.validate()
        log.info("Config validated OK")
    except Exception as exc:
        _startup_error = str(exc)
        log.error("Config validation failed: %s", exc)
        yield
        return

    try:
        init_db()
    except Exception as exc:
        log.error("DB init failed: %s", exc)
        _startup_error = str(exc)
        yield
        return

    try:
        from core.rag_pipeline import initialize_knowledge_base
        initialize_knowledge_base()
    except Exception as exc:
        log.warning("KB init failed (non-fatal): %s", exc)

    _start_cleanup_thread()
    env_label = "Railway" if config.IS_RAILWAY else ("AWS" if config.IS_AWS else "Local")
    log.info("API ready [%s]", env_label)
    yield
    log.info("API shutting down.")


# ── App ───────────────────────────────────────────────────────
app = FastAPI(
    title="AI Action Assistant",
    description="POST /chat with { message, session_id } or multipart with file.",
    version="3.0.0",
    lifespan=lifespan,
    # Disable Swagger UI in production (re-enable by removing this or setting ENVIRONMENT != production)
    docs_url="/docs" if not config.IS_PRODUCTION else None,
    redoc_url=None,
)

_ALLOWED_ORIGINS = [o.strip() for o in config.ALLOWED_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Session-ID"],
)


# ── Global exception handlers ─────────────────────────────────
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(auth_router)
app.include_router(google_auth_router)


# ── Voice routes ──────────────────────────────────────────────
@app.post("/voice/transcribe")
async def voice_transcribe(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """POST /voice/transcribe — audio file -> text via Groq Whisper."""
    from services.voice_service import transcribe_audio
    audio_bytes = await file.read()
    return transcribe_audio(audio_bytes, filename=file.filename or "audio.webm")


# ── Static page serving ───────────────────────────────────────
def _serve_static(filename: str) -> HTMLResponse:
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static", filename),
        os.path.join("static", filename),
        os.path.join("/app", "static", filename),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
    return HTMLResponse(f"<h2>{filename} not found.</h2>", status_code=404)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def root_ui():
    return _serve_static("login.html")


@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page():
    return _serve_static("login.html")


@app.get("/signup", response_class=HTMLResponse, include_in_schema=False)
def signup_page():
    return _serve_static("signup.html")


@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def dashboard_page():
    return _serve_static("dashboard.html")


@app.get("/profile", response_class=HTMLResponse, include_in_schema=False)
def profile_page():
    return _serve_static("profile.html")


@app.get("/about", response_class=HTMLResponse, include_in_schema=False)
def about_page():
    return _serve_static("about.html")


# ── Chat endpoint ─────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: Request,
    message: Optional[str] = Form(default=None),
    session_id: Optional[str] = Form(default=None),
    selected_services: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None),
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
) -> ChatResponse:
    if _startup_error:
        return ChatResponse(status="error", action="none", message=f"Configuration error: {_startup_error}")

    from backend.chat_engine import process
    from backend.session_store import get_session, update_session_title

    file_path      = None
    final_message  = message
    final_sid      = session_id
    final_services = selected_services

    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            body           = await request.json()
            final_message  = body.get("message", "")
            final_sid      = body.get("session_id") or final_sid
            final_services = body.get("selected_services", [])
        except Exception:
            return ChatResponse(status="error", action="none", message="Invalid JSON.")
    else:
        if not final_message:
            try:
                form           = await request.form()
                final_message  = form.get("message", "")
                final_sid      = form.get("session_id") or final_sid
                final_services = form.get("selected_services")
                if final_services:
                    import json
                    final_services = json.loads(final_services)
            except Exception:
                pass

        if file and file.filename:
            allowed = {".pdf", ".docx", ".xlsx", ".xls", ".txt"}
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in allowed:
                return ChatResponse(status="error", action="none", message=f"File type '{ext}' not supported.")
            safe_filename = f"{uuid.uuid4()}{ext}"
            file_path = os.path.join(config.UPLOAD_DIR, safe_filename)
            try:
                contents = await file.read()
                if len(contents) > config.UPLOAD_MAX_BYTES:
                    return ChatResponse(status="error", action="none",
                                        message=f"File too large. Max {config.UPLOAD_MAX_BYTES // (1024*1024)} MB.")
                with open(file_path, "wb") as f:
                    f.write(contents)
            except Exception as exc:
                return ChatResponse(status="error", action="none", message=f"Failed to save file: {exc}")
            if not final_message or not final_message.strip():
                final_message = f"summarize this {ext.lstrip('.')} file"
            if not final_services:
                final_services = ["summarize"]

    if not final_message or not final_message.strip():
        return ChatResponse(status="error", action="none", message="Message cannot be empty.")

    if not final_sid or not final_sid.strip():
        final_sid = str(uuid.uuid4())

    if _is_rate_limited(final_sid):
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")

    session = get_session(final_sid, db, user_id=str(current_user.id))
    response = process(final_message.strip(), session, file_path=file_path,
                       selected_services=final_services or [],
                       user_id=str(current_user.id), db=db)
    response.session_id = final_sid

    session.persist_message("user", final_message.strip())
    session.persist_message("assistant", response.message)

    from db.models import ChatSession
    row = db.query(ChatSession).filter(ChatSession.id == final_sid).first()
    if row and row.title == "New Conversation":
        update_session_title(final_sid, final_message.strip()[:60], db)

    return response


@app.get("/sessions")
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    from backend.session_store import get_user_sessions
    return get_user_sessions(str(current_user.id), db)


@app.get("/health")
def health():
    try:
        from core.vector_store import collection_count
        kb_docs = collection_count()
    except Exception:
        kb_docs = -1
    return {
        "status":          "ok" if not _startup_error else "degraded",
        "startup_error":   _startup_error,
        "environment":     "railway" if config.IS_RAILWAY else ("aws" if config.IS_AWS else "local"),
        "kb_docs":         kb_docs,
        "model":           config.GROQ_MODEL,
        "groq_configured": bool(config.GROQ_API_KEY),
    }


@app.post("/reset")
async def reset(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    from backend.session_store import reset_session
    try:
        body       = await request.json()
        session_id = body.get("session_id")
    except Exception:
        session_id = None
    if not session_id:
        return {"status": "error", "message": "session_id is required."}
    reset_session(session_id, db)
    return {"status": "ok", "message": "Session reset.", "session_id": session_id}
