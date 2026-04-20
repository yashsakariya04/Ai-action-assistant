"""
backend/google_auth.py — Per-user Google OAuth2 flow.

Routes:
  GET  /auth/google/connect      — start OAuth flow (redirect to Google)
  GET  /auth/google/callback     — handle Google redirect, save token to DB
  GET  /auth/google/status       — check if current user has connected Google
  DELETE /auth/google/disconnect — remove user's Google token
"""

import base64
import json
import logging
import os
import pickle
import secrets

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from sqlalchemy.orm import Session as DBSession

from backend.auth import get_current_user
from db.database import get_db
from db.models import User, GoogleToken
import config

# Allow OAuth over plain HTTP on localhost
if not os.getenv("RAILWAY_ENVIRONMENT"):
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/google", tags=["google-oauth"])

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

# state token → user_id  (in-memory; fine for single instance)
_pending_states: dict[str, str] = {}


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
    token_b64 = base64.b64encode(pickle.dumps(creds)).decode()
    row = db.query(GoogleToken).filter(GoogleToken.user_id == user_id).first()
    if row:
        row.token_data = token_b64
        row.email = google_email
    else:
        row = GoogleToken(user_id=user_id, token_data=token_b64, email=google_email)
        db.add(row)
    db.commit()


def get_user_credentials(user_id: str, db: DBSession):
    """Load and auto-refresh Google credentials for a user. Returns None if not connected."""
    row = db.query(GoogleToken).filter(GoogleToken.user_id == user_id).first()
    if not row:
        return None
    try:
        creds = pickle.loads(base64.b64decode(row.token_data))
    except Exception:
        return None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(GoogleRequest())
            row.token_data = base64.b64encode(pickle.dumps(creds)).decode()
            db.commit()
        except Exception as exc:
            log.warning("Token refresh failed for user %s: %s", user_id, exc)
            return None

    return creds if (creds and creds.valid) else None


# ── Routes ────────────────────────────────────────────────────

@router.get("/connect")
def connect_google(request: Request, token: str, return_to: str = "dashboard", db: DBSession = Depends(get_db)):
    """Start OAuth. Frontend calls /auth/google/connect?token=<jwt>&return_to=dashboard|profile"""
    from jose import jwt as jose_jwt, JWTError
    from backend.auth import SECRET_KEY, ALGORITHM
    try:
        payload = jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    cfg = _load_client_config()
    state = secrets.token_urlsafe(32)
    _pending_states[state] = {"user_id": user_id, "return_to": return_to}

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

    user_id = _pending_states.pop(state, None)
    if not user_id:
        return RedirectResponse("/dashboard?google_error=invalid_state")
    
    # Support both old string format and new dict format
    if isinstance(user_id, dict):
        return_to = user_id.get("return_to", "dashboard")
        user_id = user_id["user_id"]
    else:
        return_to = "dashboard"

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
            raise ValueError(f"Token exchange failed: {token_data['error']} — {token_data.get('error_description','')}")

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

    except Exception as exc:
        log.exception("Google callback error")
        return RedirectResponse(f"/{return_to}?google_error={str(exc)[:120]}")

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
