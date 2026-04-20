"""
run_mcp.py — Start the MCP server.

Usage:
    python run_mcp.py                      # stdio transport (for Claude Desktop, Cursor)
    python run_mcp.py --transport sse      # SSE transport (for web/remote clients)

The MCP server exposes all assistant tools, resources, and prompts
via the Model Context Protocol.
"""

import sys
import os
import argparse
import logging

os.makedirs("logs", exist_ok=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── CRITICAL: For stdio transport, ALL logs must go to stderr, never stdout 
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),       # stderr only!
        logging.FileHandler("logs/mcp_server.log", encoding="utf-8"),
    ],
)

from mcp_server import mcp, initialize


def main():
    parser = argparse.ArgumentParser(description="AI Action Assistant — MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for SSE transport (default: 8001)",
    )
    args = parser.parse_args()

    # Initialize config + knowledge base before serving
    # All output to stderr so it doesn't pollute stdio transport
    try:
        print("Initializing MCP server...", file=sys.stderr)
        initialize()
        print("MCP server ready.", file=sys.stderr)
    except Exception as exc:
        print(f"WARNING: Initialization error: {exc}", file=sys.stderr)
        print("Server will start but some tools may not work.", file=sys.stderr)

    # Start the MCP server
    if args.transport == "sse":
        mcp.settings.port = args.port
        print(f"Starting MCP server (SSE) on port {args.port}...", file=sys.stderr)

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()