#!/usr/bin/env python3
"""Entry point for running the Homelab MCP server."""

import argparse
import asyncio
import os
import sys

from src.homelab_mcp.server import main


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Homelab MCP Server - AI-powered homelab infrastructure management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run in stdio mode (for Claude Desktop)
  python run_server.py

  # Run in HTTP mode (for OpenWebUI)
  python run_server.py --http --port 8080

  # Run HTTP mode with custom host/port
  python run_server.py --http --host 127.0.0.1 --port 9000

  # Run HTTP mode without authentication (local development only)
  python run_server.py --http --no-auth

Environment Variables:
  MCP_HTTP_ENABLED    Enable HTTP mode by default (true/false)
  MCP_HTTP_HOST       Default HTTP host (default: 0.0.0.0)
  MCP_HTTP_PORT       Default HTTP port (default: 8080)
  MCP_API_KEY         API key for HTTP authentication
  MCP_AUTH_ENABLED    Enable/disable authentication (default: true)
""",
    )

    parser.add_argument(
        "--http",
        action="store_true",
        default=os.getenv("MCP_HTTP_ENABLED", "false").lower() == "true",
        help="Run in HTTP mode instead of stdio mode",
    )

    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("MCP_HTTP_HOST", "0.0.0.0"),
        help="HTTP server host (default: 0.0.0.0)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_HTTP_PORT", "8080")),
        help="HTTP server port (default: 8080)",
    )

    parser.add_argument(
        "--no-auth",
        action="store_true",
        default=os.getenv("MCP_AUTH_ENABLED", "true").lower() == "false",
        help="Disable API key authentication (not recommended for network access)",
    )

    parser.add_argument(
        "--api-key",
        type=str,
        default=os.getenv("MCP_API_KEY"),
        help="API key for authentication (can also use MCP_API_KEY env var)",
    )

    parser.add_argument(
        "--ssl-cert",
        type=str,
        default=os.getenv("MCP_SSL_CERT"),
        help="Path to SSL certificate file (enables HTTPS)",
    )

    parser.add_argument(
        "--ssl-key",
        type=str,
        default=os.getenv("MCP_SSL_KEY"),
        help="Path to SSL private key file",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Debug output to stderr (will appear in logs)
    if args.http:
        protocol = "HTTPS" if args.ssl_cert else "HTTP"
        print(f"MCP Server starting in {protocol} mode on {args.host}:{args.port}", file=sys.stderr)
        print(f"Authentication: {'disabled' if args.no_auth else 'enabled'}", file=sys.stderr)
        if args.ssl_cert:
            print(f"SSL: enabled (cert: {args.ssl_cert})", file=sys.stderr)
    else:
        print("MCP Server starting in stdio mode...", file=sys.stderr)

    print(f"Current directory: {os.getcwd()}", file=sys.stderr)
    print(f"Python executable: {sys.executable}", file=sys.stderr)

    try:
        asyncio.run(
            main(
                http_mode=args.http,
                host=args.host,
                port=args.port,
                auth_enabled=not args.no_auth,
                api_key=args.api_key,
                ssl_certfile=args.ssl_cert,
                ssl_keyfile=args.ssl_key,
            )
        )
    except KeyboardInterrupt:
        print("\nServer stopped by user", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
