#!/usr/bin/env python3
"""Entry point for running the Homelab MCP server."""

import asyncio
import os
import sys

from src.homelab_mcp.server import main

# Debug output to stderr (will appear in Claude logs)
print("MCP Server starting...", file=sys.stderr)
print(f"Current directory: {os.getcwd()}", file=sys.stderr)
print(f"Python executable: {sys.executable}", file=sys.stderr)
print(f"Script path: {__file__}", file=sys.stderr)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped by user", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
