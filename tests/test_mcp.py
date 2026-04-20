"""
test_mcp.py — Direct MCP tool tester.

Tests all 9 MCP tools without needing Claude Desktop or npx inspector.
Runs the MCP server in-process and calls each tool directly.

Usage:
    python test_mcp.py
    python test_mcp.py --tool weather_service
    python test_mcp.py --tool chat
"""

import sys
import os
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def separator(title: str):
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print('═' * 60)


def run_tool(name: str, fn, *args, **kwargs):
    print(f"\n▶ {name}")
    print(f"  Input: {args or kwargs}")
    print(f"  {'-' * 56}")
    try:
        result = fn(*args, **kwargs)
        # Print first 400 chars to keep output readable
        preview = result[:400] + "..." if len(result) > 400 else result
        for line in preview.split("\n"):
            print(f"  {line}")
        print(f"  ✅ PASSED")
        return True
    except Exception as exc:
        print(f"  ❌ FAILED: {exc}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test MCP tools directly")
    parser.add_argument("--tool", help="Run only a specific tool by name")
    args = parser.parse_args()

    print("\n" + "█" * 60)
    print("  AI Action Assistant — MCP Tool Test Suite")
    print("  Testing all 9 tools + 3 resources")
    print("█" * 60)

    # Initialize server
    print("\n⏳ Initializing server...")
    try:
        from mcp_server import initialize
        initialize()
        print("✅ Server initialized")
    except Exception as exc:
        print(f"⚠️  Init warning: {exc}")

    # Import all tool functions directly from mcp_server
    from mcp_server import (
        chat,
        weather_service,
        web_search_service,
        summarizer_service,
        email_service,
        calendar_service,
        news_service,
        reset_conversation,
        get_system_status,
        get_config_settings,
        get_kb_status,
        get_help_guide,
    )

    results = {}

    # ── Run specific tool if requested ────────────────────────
    if args.tool:
        tool_map = {
            "chat":               lambda: run_tool("chat('hello')", chat, "hello"),
            "weather_service":    lambda: run_tool("weather_service('Ahmedabad')", weather_service, "Ahmedabad"),
            "web_search_service": lambda: run_tool("web_search_service('Python FastAPI')", web_search_service, "Python FastAPI"),
            "summarizer_service": lambda: run_tool("summarizer_service(url=...)", summarizer_service, url="https://en.wikipedia.org/wiki/Artificial_intelligence"),
            "email_service":      lambda: run_tool("email_service(...)", email_service, "send a test email to john@example.com about project update"),
            "calendar_service":   lambda: run_tool("calendar_service(...)", calendar_service, "schedule a test meeting tomorrow at 3pm"),
            "news_service":       lambda: run_tool("news_service('technology')", news_service, "technology"),
            "reset_conversation": lambda: run_tool("reset_conversation()", reset_conversation),
            "get_system_status":  lambda: run_tool("get_system_status()", get_system_status),
        }

        if args.tool not in tool_map:
            print(f"\n❌ Unknown tool: {args.tool}")
            print(f"   Available: {', '.join(tool_map.keys())}")
            sys.exit(1)

        tool_map[args.tool]()
        return

    # ── Run all tools ─────────────────────────────────────────

    separator("1. MASTER BRAIN — chat()")
    results["chat_hello"]    = run_tool("chat('hello')", chat, "hello")
    results["chat_question"] = run_tool("chat('what can you do?')", chat, "what can you do?")

    separator("2. WEATHER SERVICE — weather_service()")
    results["weather"] = run_tool("weather_service('Ahmedabad')", weather_service, "Ahmedabad")

    separator("3. WEB SEARCH — web_search_service()")
    results["web_search"] = run_tool(
        "web_search_service('Python FastAPI tutorial')",
        web_search_service,
        "Python FastAPI tutorial"
    )

    separator("4. SUMMARIZER — summarizer_service()")
    results["summarize_url"] = run_tool(
        "summarizer_service(url='Wikipedia AI')",
        summarizer_service,
        url="https://en.wikipedia.org/wiki/Artificial_intelligence"
    )
    results["summarize_text"] = run_tool(
        "summarizer_service(text='...')",
        summarizer_service,
        text=(
            "FastAPI is a modern, fast web framework for building APIs with Python. "
            "It is based on standard Python type hints and provides automatic "
            "interactive API documentation. FastAPI is one of the fastest Python "
            "frameworks available, on par with NodeJS and Go."
        )
    )

    separator("5. NEWS SERVICE — news_service()")
    results["news"] = run_tool("news_service('technology')", news_service, "technology")

    separator("6. EMAIL SERVICE — email_service() [workflow start only]")
    results["email_start"] = run_tool(
        "email_service('send email to John about meeting')",
        email_service,
        "send a professional email to John about tomorrow's project meeting"
    )

    separator("7. CALENDAR SERVICE — calendar_service() [workflow start only]")
    results["calendar_start"] = run_tool(
        "calendar_service('schedule meeting tomorrow 3pm')",
        calendar_service,
        "schedule a team sync meeting tomorrow at 3pm"
    )

    separator("8. RESET CONVERSATION — reset_conversation()")
    results["reset"] = run_tool("reset_conversation()", reset_conversation)

    separator("9. SYSTEM STATUS — get_system_status()")
    results["status"] = run_tool("get_system_status()", get_system_status)

    separator("RESOURCES")
    results["config"]   = run_tool("get_config_settings()", get_config_settings)
    results["kb"]       = run_tool("get_kb_status()", get_kb_status)
    results["guide"]    = run_tool("get_help_guide() [preview]", get_help_guide)

    # ── Summary ───────────────────────────────────────────────
    separator("TEST SUMMARY")
    passed = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)
    total  = len(results)

    print(f"\n  Total  : {total}")
    print(f"  Passed : {passed} ✅")
    print(f"  Failed : {failed} ❌")
    print()

    for name, result in results.items():
        icon = "✅" if result else "❌"
        print(f"  {icon} {name}")

    print()
    if failed == 0:
        print("  🎉 All tests passed! MCP server is fully operational.")
    else:
        print(f"  ⚠️  {failed} test(s) failed. Check service configuration.")

    print()


if __name__ == "__main__":
    main()
