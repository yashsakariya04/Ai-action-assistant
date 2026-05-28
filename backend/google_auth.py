"""
backend/google_auth.py — Per-user Google OAuth2 flow.

Routes:
  GET  /auth/google/connect      — start OAuth flow (redirect to Google)
  GET  /auth/google/callback     — handle Google redirect, save token to DB
  GET  /auth/google/status       — check if current user has connected Google
  DELETE /auth/google/disconnect — remove user's Google token

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECURITY WARNING — TOKEN SERIALIZATION
  DO NOT use pickle for token storage — it allows arbitrary code execution
  (RCE) if an attacker can write to the database.
  Tokens are stored as Fernet-encrypted JSON only. Never change this.
  To rotate the key, decrypt all rows with the old key and re-encrypt.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MIGRATION NOTE:
  Existing rows in the google_tokens table that were serialized with pickle
  will fail decryption and return None — the user will need to reconnect
  their Google account. A startup warning log is emitted when this happens.
"""

import json
import logging
import os
import secrets
import time

import requests
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from sqlalchemy.orm import Session as DBSession

from backend.auth import get_current_user
from db.database import get_db
from db.models import User, GoogleToken
import config

# Allow OAuth over plain HTTP on localhost only — never on cloud
_is_cloud = bool(
    os.getenv("RAILWAY_ENVIRONMENT") or
    os.getenv("AWS_EXECUTION_ENV") or
    os.getenv("ECS_CONTAINER_METADATA_URI") or
    os.getenv("AWS_REGION")
)
if not _is_cloud:
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/google", tags=["google-oauth"])

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

# Allowed page names for return_to — prevents open redirect
ALLOWED_RETURN_PAGES = {"dashboard", "profile"}

# state token → (data_dict, timestamp)  (in-memory; fine for single instance)
_pending_states: dict[str, tuple[dict, float]] = {}


# ── Fernet encryption helpers ──────────────────────────────────

def _get_fernet() -> Fernet:
    key = os.environ.get("TOKEN_ENCRYPTION_KEY", "")
    if not key:
        raise EnvironmentError(
            "TOKEN_ENCRYPTION_KEY is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def _encrypt(plain: str) -> str:
    return _get_fernet().encrypt(plain.encode()).decode()


def _decrypt(cipher: str) -> str:
    return _get_fernet().decrypt(cipher.encode()).decode()


def _load_client_config() -> dict:
    if not os.path.exists(config.GOOGLE_CREDENTIALS_FILE):
        raise FileNotFoundError(
            f"credentials.json not found at: {config.GOOGLE_CREDENTIALS_FILE}"
        )
    with open(config.GOOGLE_CREDENTIALS_FILE) as f:
        data = json.load(f)
    # supports both "web" and "installed" key
    return data.get("web") or data.get("installed")


def _redirect_uri(request: Request) -> str:
    return str(request.base_url).rstrip("/") + "/auth/google/callback"


def _save_token(user_id: str, creds: Credentials, google_email: str, db: DBSession):
    token_json = json.dumps({
        "token":          creds.token,
        "refresh_token":  creds.refresh_token,
        "token_uri":      creds.token_uri,
        "client_id":      creds.client_id,
        "client_secret":  creds.client_secret,
        "scopes":         list(creds.scopes or []),
        "expiry":         creds.expiry.isoformat() if creds.expiry else None,
    })
    encrypted = _encrypt(token_json)
    row = db.query(GoogleToken).filter(GoogleToken.user_id == user_id).first()
    if row:
        row.token_data = encrypted
        row.email = google_email
    else:
        row = GoogleToken(user_id=user_id, token_data=encrypted, email=google_email)
        db.add(row)
    db.commit()


def get_user_credentials(user_id: str, db: DBSession):
    """Load and auto-refresh Google credentials for a user. Returns None if not connected."""
    row = db.query(GoogleToken).filter(GoogleToken.user_id == user_id).first()
    if not row:
        return None
    try:
        token_json = _decrypt(row.token_data)
        data = json.loads(token_json)
    except (InvalidToken, Exception):
        log.warning(
            "Failed to decrypt token for user %s — token may be a legacy pickle row. "
            "User must reconnect their Google account.",
            user_id,
        )
        return None

    from datetime import datetime, timezone
    expiry = None
    if data.get("expiry"):
        try:
            expiry = datetime.fromisoformat(data["expiry"])
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
        except Exception:
            pass

    creds = Credentials(
        token=data["token"],
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes"),
    )
    creds.expiry = expiry

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(GoogleRequest())
            _save_token(user_id, creds, row.email, db)
        except Exception as exc:
            log.warning("Token refresh failed for user %s: %s", user_id, exc)
            return None

    return creds if (creds and creds.valid) else None


# ── Routes ────────────────────────────────────────────────────

@router.get("/connect")
def connect_google(
    request: Request,
    token: str = "cookie",
    return_to: str = "dashboard",
    auth_token: str | None = None,
    db: DBSession = Depends(get_db),
):
    """Start OAuth. Frontend calls /auth/google/connect?return_to=dashboard|profile
    The JWT is read from the auth_token HttpOnly cookie or the ?token= query param."""
    # Whitelist return_to to prevent open redirect
    return_to = return_to if return_to in ALLOWED_RETURN_PAGES else "dashboard"

    # Sweep stale pending states (older than 10 minutes)
    cutoff = time.time() - 600
    stale = [k for k, v in _pending_states.items() if v[1] < cutoff]
    for k in stale:
        _pending_states.pop(k, None)

    from jose import jwt as jose_jwt, JWTError
    from backend.auth import SECRET_KEY, ALGORITHM

    # Try cookie first, then fall back to query param
    cookie_token = request.cookies.get("auth_token")
    raw_token = cookie_token or (token if token != "cookie" else None)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        payload = jose_jwt.decode(raw_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    cfg = _load_client_config()
    state = secrets.token_urlsafe(32)
    _pending_states[state] = ({"user_id": user_id, "return_to": return_to}, time.time())

    redirect_uri = _redirect_uri(request)
    scope_str = " ".join(SCOPES)

    # Build the authorization URL manually — no PKCE, no code_challenge
    params = {
        "client_id":     cfg["client_id"],
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         scope_str,
        "access_type":   "offline",
        "prompt":        "consent",
        "state":         state,
    }
    from urllib.parse import urlencode
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return RedirectResponse(auth_url)


@router.get("/callback")
def google_callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
    db: DBSession = Depends(get_db),
):
    """Handle Google's redirect, exchange code for token, save to DB."""
    if error:
        return RedirectResponse("/dashboard?google_error=" + error)

    state_entry = _pending_states.pop(state, None)
    if not state_entry:
        return RedirectResponse("/dashboard?google_error=invalid_state")

    state_data, _ = state_entry
    user_id = state_data["user_id"]
    return_to = state_data.get("return_to", "dashboard")

    # Guard return_to again in case it was stored before the allowlist was added
    return_to = return_to if return_to in ALLOWED_RETURN_PAGES else "dashboard"

    try:
        cfg = _load_client_config()
        redirect_uri = _redirect_uri(request)

        # Exchange authorization code for tokens directly via HTTP POST — no PKCE
        token_resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code":          code,
                "client_id":     cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "redirect_uri":  redirect_uri,
                "grant_type":    "authorization_code",
            },
        )
        token_data = token_resp.json()
        if "error" in token_data:
            raise ValueError(f"Token exchange failed: {token_data['error']}")

        creds = Credentials(
            token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=cfg["client_id"],
            client_secret=cfg["client_secret"],
            scopes=SCOPES,
        )

        # Get the Google account email + profile picture
        userinfo = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        ).json()
        google_email = userinfo.get("email", "")
        avatar_url = userinfo.get("picture", "")

        _save_token(user_id, creds, google_email, db)

        # Update user's avatar and name if not set
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            if not user.avatar_url and avatar_url:
                user.avatar_url = avatar_url
            if not user.name and userinfo.get("name"):
                user.name = userinfo.get("name")
            db.commit()

        log.info("Google token saved for user %s (%s)", user_id, google_email)

    except Exception:
        log.exception("Google callback error for user %s", user_id)
        return RedirectResponse(f"/{return_to}?google_error=auth_failed")

    return RedirectResponse(f"/{return_to}?google_connected=1")


@router.get("/status")
def google_status(
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    row = db.query(GoogleToken).filter(GoogleToken.user_id == current_user.id).first()
    if row:
        return {"connected": True, "google_email": row.email}
    return {"connected": False, "google_email": None}


@router.delete("/disconnect")
def google_disconnect(
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    db.query(GoogleToken).filter(GoogleToken.user_id == current_user.id).delete()
    db.commit()
    return {"status": "ok", "message": "Google account disconnected."}
