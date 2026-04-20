"""
run_api.py — Server entry point with detailed startup logging.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()  # load .env before any config checks

if __name__ == "__main__":

    os.makedirs("logs", exist_ok=True)

    # Step 1 — decode Google auth files on Railway
    try:
        from scripts.startup import decode_google_files
        decode_google_files()
    except Exception as exc:
        print(f"WARNING: startup.py error: {exc}", file=sys.stderr)

    # Step 2 — log environment info for debugging
    print("=" * 50, file=sys.stderr)
    print("Starting AI Action Assistant", file=sys.stderr)
    print(f"Python: {sys.version}", file=sys.stderr)
    print(f"PORT: {os.environ.get('PORT', '8000')}", file=sys.stderr)
    print(f"RAILWAY: {bool(os.environ.get('RAILWAY_ENVIRONMENT'))}", file=sys.stderr)
    print(f"GROQ_API_KEY set: {bool(os.environ.get('GROQ_API_KEY'))}", file=sys.stderr)
    print("=" * 50, file=sys.stderr)

    # Step 3 — test critical imports before starting server
    print("Testing imports...", file=sys.stderr)
    try:
        import numpy
        print(f"  numpy: {numpy.__version__}", file=sys.stderr)
    except Exception as exc:
        print(f"  numpy FAILED: {exc}", file=sys.stderr)

    try:
        import torch
        print(f"  torch: {torch.__version__}", file=sys.stderr)
    except Exception as exc:
        print(f"  torch FAILED: {exc}", file=sys.stderr)

    try:
        import chromadb
        print(f"  chromadb: OK", file=sys.stderr)
    except Exception as exc:
        print(f"  chromadb FAILED: {exc}", file=sys.stderr)

    try:
        import sentence_transformers
        print(f"  sentence_transformers: OK", file=sys.stderr)
    except Exception as exc:
        print(f"  sentence_transformers FAILED: {exc}", file=sys.stderr)

    print("Imports checked. Starting server...", file=sys.stderr)

    # Step 4 — start server
    import uvicorn

    port = int(os.environ.get("PORT", 8000))

    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )