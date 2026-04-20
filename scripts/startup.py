"""
startup.py — Pre-startup tasks for Railway deployment.

Automatically called by run_api.py before starting the server.

Tasks:
  1. Decode GOOGLE_TOKEN_B64 env var → token.pickle file
     (Railway cannot store binary files, so we store base64 in env var)
  2. Decode GOOGLE_CREDENTIALS_B64 env var → credentials.json file
     (same reason)

These only run on Railway (when RAILWAY_ENVIRONMENT is set).
Locally this file does nothing — you have the real files already.
"""

import os
import base64
import sys


def decode_google_files():
    """Decode base64-encoded Google auth files from environment variables."""

    is_railway = bool(os.getenv("RAILWAY_ENVIRONMENT"))
    if not is_railway:
        return   # Local environment — real files already exist

    print("Railway environment detected — decoding Google auth files...", file=sys.stderr)

    # ── Decode token.pickle ───────────────────────────────────
    token_b64 = os.getenv("GOOGLE_TOKEN_B64", "")
    token_file = os.getenv("GOOGLE_TOKEN_FILE", "token.pickle")

    if token_b64:
        try:
            token_data = base64.b64decode(token_b64)
            with open(token_file, "wb") as f:
                f.write(token_data)
            print(f"✅ token.pickle decoded → {token_file}", file=sys.stderr)
        except Exception as exc:
            print(f"⚠️  Failed to decode GOOGLE_TOKEN_B64: {exc}", file=sys.stderr)
    else:
        print("⚠️  GOOGLE_TOKEN_B64 not set — Google Calendar/Gmail will not work", file=sys.stderr)

    # ── Decode credentials.json ───────────────────────────────
    creds_b64  = os.getenv("GOOGLE_CREDENTIALS_B64", "")
    creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

    if creds_b64:
        try:
            creds_data = base64.b64decode(creds_b64)
            with open(creds_file, "wb") as f:
                f.write(creds_data)
            print(f"✅ credentials.json decoded → {creds_file}", file=sys.stderr)
        except Exception as exc:
            print(f"⚠️  Failed to decode GOOGLE_CREDENTIALS_B64: {exc}", file=sys.stderr)
    else:
        print("⚠️  GOOGLE_CREDENTIALS_B64 not set — Google services may not work", file=sys.stderr)


if __name__ == "__main__":
    decode_google_files()