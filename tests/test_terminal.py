"""
test_terminal.py — Terminal client for testing the FastAPI backend.

Two modes:
  1. Direct mode  (no server needed):  python test_terminal.py --direct
  2. API mode     (server must be up):  python test_terminal.py
                                        python test_terminal.py --url http://localhost:8000

Direct mode runs the engine in-process — useful for quick logic testing.
API mode calls the real HTTP endpoint — tests the full stack.
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ─────────────────────────────────────────────────────────────
# API MODE  — talks to running FastAPI server via HTTP
# ─────────────────────────────────────────────────────────────

def run_api_mode(base_url: str):
    try:
        import requests
    except ImportError:
        print("ERROR: 'requests' package required. Run: pip install requests")
        sys.exit(1)

    chat_url  = f"{base_url}/chat"
    reset_url = f"{base_url}/reset"
    health_url = f"{base_url}/health"

    # Check server is up
    try:
        r = requests.get(health_url, timeout=5)
        info = r.json()
        print(f"\nServer OK  |  Model: {info.get('model')}  |  KB docs: {info.get('kb_docs')}")
    except Exception:
        print(f"\nERROR: Could not reach server at {base_url}")
        print("Make sure the server is running:  python run_api.py")
        sys.exit(1)

    print(f"\nConnected to {base_url}")
    print("Commands: 'reset' to clear conversation | 'exit' to quit")
    print("-" * 60)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "bye"):
            print("Goodbye.")
            break

        if user_input.lower() == "reset":
            requests.post(reset_url, json={"session_id": "terminal-api"})
            print("Assistant: Conversation reset.")
            continue

        try:
            resp = requests.post(
                chat_url,
                json={"message": user_input, "session_id": "terminal-api"},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.Timeout:
            print("Assistant: Request timed out. The LLM may be slow.")
            continue
        except Exception as e:
            print(f"Assistant: Request failed — {e}")
            continue

        _print_response(data)


# ─────────────────────────────────────────────────────────────
# DIRECT MODE  — runs engine in-process, no HTTP
# ─────────────────────────────────────────────────────────────

def run_direct_mode():
    import config
    from core.rag_pipeline import initialize_knowledge_base
    from backend.session_store import get_session, reset_session
    from backend.chat_engine import process

    try:
        config.validate()
    except EnvironmentError as e:
        print(f"Config error: {e}")
        sys.exit(1)

    print("Initialising knowledge base...")
    initialize_knowledge_base()

    print("\nDirect mode — engine running in-process.")
    print("Commands: 'reset' to clear conversation | 'exit' to quit")
    print("-" * 60)

    sid     = "terminal-direct"
    session = get_session(sid)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "bye"):
            print("Goodbye.")
            break
        if user_input.lower() == "reset":
            reset_session(sid)
            session = get_session(sid)
            print("Assistant: Conversation reset.")
            continue

        response = process(user_input, session)
        _print_response(response.model_dump())


# ─────────────────────────────────────────────────────────────
# SHARED DISPLAY
# ─────────────────────────────────────────────────────────────

def _print_response(data: dict):
    status = data.get("status", "")
    action = data.get("action", "")
    message = data.get("message", "")
    articles = data.get("news_articles") or []

    print(f"\n[{status.upper()} | {action}]")
    print("-" * 60)
    print(message)

    if articles:
        print()
        for i, a in enumerate(articles, 1):
            print(f"  {i}. {a.get('title','')}")
            if a.get("description"):
                print(f"     {a['description']}")
            print(f"     {a.get('source','')}  |  {a.get('published','')}")

    print("-" * 60)


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Terminal client for AI Action Assistant")
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Run engine directly in-process (no server required)",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="FastAPI server URL (default: http://localhost:8000)",
    )
    args = parser.parse_args()

    if args.direct:
        run_direct_mode()
    else:
        run_api_mode(args.url)
