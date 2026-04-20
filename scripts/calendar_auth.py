"""
calendar_auth.py — Google OAuth2 credential management.
Handles token caching, refresh, and re-authentication flows.
"""

import os
import pickle
import logging

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

import config

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send"]


def get_credentials():
    """
    Load cached OAuth2 credentials or run the OAuth flow.

    Returns:
        google.oauth2.credentials.Credentials — valid credentials object.

    Raises:
        FileNotFoundError: if credentials.json is missing.
        RuntimeError: if authentication fails.
    """
    creds = None

    # ── Load cached token ──────────────────────────────────────────────────
    if os.path.exists(config.GOOGLE_TOKEN_FILE):
        try:
            with open(config.GOOGLE_TOKEN_FILE, "rb") as fh:
                creds = pickle.load(fh)
        except (pickle.UnpicklingError, EOFError):
            log.warning("Corrupt token file — will re-authenticate.")
            creds = None

    # ── Refresh or re-authenticate ─────────────────────────────────────────
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as exc:
                log.warning("Token refresh failed (%s) — re-authenticating.", exc)
                creds = None

        if not creds:
            if not os.path.exists(config.GOOGLE_CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Google credentials file not found: {config.GOOGLE_CREDENTIALS_FILE}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GOOGLE_CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Persist refreshed/new token
        with open(config.GOOGLE_TOKEN_FILE, "wb") as fh:
            pickle.dump(creds, fh)

    return creds


if __name__ == "__main__":
    """
    Run this script directly to authorize Google Calendar + Gmail.
    Opens a browser window for OAuth consent.
    Saves token.pickle in the project directory.
    """
    import sys

    print("=" * 50)
    print("Google OAuth2 Authorization")
    print("Scopes: Calendar + Gmail Send")
    print("=" * 50)
    print()

    # Check credentials.json exists
    if not os.path.exists(config.GOOGLE_CREDENTIALS_FILE):
        print(f"ERROR: {config.GOOGLE_CREDENTIALS_FILE} not found.")
        print("Download it from Google Cloud Console:")
        print("  APIs & Services → Credentials → Download OAuth 2.0 Client")
        sys.exit(1)

    # Delete old token to force fresh auth with new scopes
    if os.path.exists(config.GOOGLE_TOKEN_FILE):
        os.remove(config.GOOGLE_TOKEN_FILE)
        print(f"Deleted old {config.GOOGLE_TOKEN_FILE}")

    print("Opening browser for Google authorization...")
    print("Please sign in and allow both Calendar and Gmail permissions.")
    print()

    try:
        creds = get_credentials()
        print()
        print("=" * 50)
        print("SUCCESS! Token saved to:", config.GOOGLE_TOKEN_FILE)
        print("Scopes authorized:", getattr(creds, "scopes", SCOPES))
        print("=" * 50)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Authorization failed: {e}")
        sys.exit(1)
