#!/usr/bin/env python3
"""Entry point for running the Homelab MCP server.

Supports two transport modes:
  - stdio (default): for Claude Desktop and other stdio-based MCP clients
  - HTTP (--http): for OpenWebUI and network-based MCP clients
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys


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


async def run_stdio() -> None:
    """Run the MCP server in stdio mode using the SDK transport.

    Registers signal handlers for SIGTERM and SIGINT that trigger graceful
    shutdown by cancelling the anyio task group.  This causes the stdio_server
    context manager to exit, which exits server.run(), which exits the
    lifespan context manager, which calls ResourceManager.shutdown().
    """
    import signal

    import anyio
    from mcp.server.stdio import stdio_server

    from src.homelab_mcp.server import server

    shutdown_event = anyio.Event()

    def _signal_handler(signum: int, frame: object) -> None:
        print(
            f"\nReceived signal {signal.Signals(signum).name}, shutting down...",
            file=sys.stderr,
        )
        shutdown_event.set()

    # Register signal handlers
    previous_sigterm = signal.signal(signal.SIGTERM, _signal_handler)
    previous_sigint = signal.signal(signal.SIGINT, _signal_handler)

    try:
        async with anyio.create_task_group() as tg:

            async def _run_server() -> None:
                async with stdio_server() as (read_stream, write_stream):
                    await server.run(read_stream, write_stream, server.create_initialization_options())

            async def _wait_for_shutdown() -> None:
                await shutdown_event.wait()
                tg.cancel_scope.cancel()

            tg.start_soon(_run_server)
            tg.start_soon(_wait_for_shutdown)
    finally:
        # Restore previous signal handlers
        signal.signal(signal.SIGTERM, previous_sigterm)
        signal.signal(signal.SIGINT, previous_sigint)


async def run_http(
    host: str = "0.0.0.0",
    port: int = 8080,
    ssl_certfile: str | None = None,
    ssl_keyfile: str | None = None,
) -> None:
    """Run the MCP server in HTTP mode using the SDK transport."""
    import uvicorn

    from src.homelab_mcp.http_app import create_http_app

    app = create_http_app()

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
    )
    uvi_server = uvicorn.Server(config)
    await uvi_server.serve()


if __name__ == "__main__":
    args = parse_args()

    # Debug output to stderr (will appear in logs)
    if args.http:
        protocol = "HTTPS" if args.ssl_cert else "HTTP"
        print(
            f"MCP Server starting in {protocol} mode on {args.host}:{args.port}",
            file=sys.stderr,
        )
        print(
            f"Authentication: {'disabled' if args.no_auth else 'enabled'}",
            file=sys.stderr,
        )
        if args.ssl_cert:
            print(f"SSL: enabled (cert: {args.ssl_cert})", file=sys.stderr)
    else:
        print("MCP Server starting in stdio mode...", file=sys.stderr)

    print(f"Current directory: {os.getcwd()}", file=sys.stderr)
    print(f"Python executable: {sys.executable}", file=sys.stderr)

    try:
        if args.http:
            asyncio.run(
                run_http(
                    host=args.host,
                    port=args.port,
                    ssl_certfile=args.ssl_cert,
                    ssl_keyfile=args.ssl_key,
                )
            )
        else:
            asyncio.run(run_stdio())
    except KeyboardInterrupt:
        print("\nServer stopped by user", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
