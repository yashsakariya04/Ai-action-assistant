"""
startup.py — Pre-startup tasks for cloud deployment.

Supports: Railway, AWS ECS, AWS App Runner, AWS Elastic Beanstalk.

Tasks:
  1. Decode GOOGLE_TOKEN_B64 env var -> token.pickle
  2. Decode GOOGLE_CREDENTIALS_B64 env var -> credentials.json
"""

import os
import base64
import sys


def _is_cloud() -> bool:
    return bool(
        os.getenv("RAILWAY_ENVIRONMENT") or
        os.getenv("AWS_EXECUTION_ENV") or
        os.getenv("ECS_CONTAINER_METADATA_URI") or
        os.getenv("AWS_REGION")
    )


def decode_google_files():
    """Decode base64-encoded Google auth files from environment variables."""
    if not _is_cloud():
        return  # Local environment — real files already exist

    env_name = "AWS" if os.getenv("AWS_REGION") else "Railway"
    print(f"{env_name} environment detected — decoding Google auth files...", file=sys.stderr)

    token_b64  = os.getenv("GOOGLE_TOKEN_B64", "")
    token_file = os.getenv("GOOGLE_TOKEN_FILE", "token.pickle")
    if token_b64:
        try:
            with open(token_file, "wb") as f:
                f.write(base64.b64decode(token_b64))
            print(f"token.pickle decoded -> {token_file}", file=sys.stderr)
        except Exception as exc:
            print(f"Failed to decode GOOGLE_TOKEN_B64: {exc}", file=sys.stderr)
    else:
        print("GOOGLE_TOKEN_B64 not set — Google Calendar/Gmail will not work", file=sys.stderr)

    creds_b64  = os.getenv("GOOGLE_CREDENTIALS_B64", "")
    creds_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    if creds_b64:
        try:
            with open(creds_file, "wb") as f:
                f.write(base64.b64decode(creds_b64))
            print(f"credentials.json decoded -> {creds_file}", file=sys.stderr)
        except Exception as exc:
            print(f"Failed to decode GOOGLE_CREDENTIALS_B64: {exc}", file=sys.stderr)
    else:
        print("GOOGLE_CREDENTIALS_B64 not set — Google services may not work", file=sys.stderr)


if __name__ == "__main__":
    decode_google_files()
