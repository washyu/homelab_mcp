"""HTTP application composing MCP SDK transport with custom routes.

Uses StreamableHTTPSessionManager to handle MCP protocol on /mcp,
while preserving non-MCP routes (/health, /shell, /ws/shell).
"""

from __future__ import annotations

import contextlib
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from .error_handling import health_checker
from .server import server
from .shell_session import session_manager as shell_session_manager

try:
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
except ImportError:
    from mcp.server.streamable_http import StreamableHTTPSessionManager  # type: ignore[no-redef]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Non-MCP route handlers (carried over from http_transport.py)
# ---------------------------------------------------------------------------


async def handle_health(request: Request) -> Response:
    """Health check endpoint returning server status."""
    health_status = health_checker.get_health_status()
    health_status["transport"] = "http"
    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(health_status, status_code=status_code)


async def handle_root(request: Request) -> Response:
    """Root endpoint for service discovery."""
    return JSONResponse(
        {
            "name": "homelab-mcp",
            "version": "0.2.0",
            "protocol": "MCP",
            "transport": "streamable-http",
            "endpoints": {
                "mcp": "/mcp",
                "health": "/health",
                "shell": "/shell/{session_id}",
            },
        }
    )


async def handle_shell_page(request: Request) -> Response:
    """Serve the interactive shell HTML page."""
    session_id = request.path_params["session_id"]
    session = shell_session_manager.get_session(session_id)
    if not session:
        return JSONResponse({"error": "Session not found or expired"}, status_code=404)

    from pathlib import Path

    template_path = Path(__file__).parent / "shell_terminal.html"
    html_content = template_path.read_text()
    html_content = html_content.replace("{{session_id}}", session_id)
    html_content = html_content.replace("{{hostname}}", session.hostname)
    html_content = html_content.replace("{{username}}", session.username)
    return HTMLResponse(html_content)


async def handle_shell_websocket(websocket: WebSocket) -> None:
    """Handle WebSocket connection for interactive shell."""
    import asyncio

    session_id = websocket.path_params["session_id"]
    session = shell_session_manager.get_session(session_id)
    if not session:
        await websocket.close(code=1008, reason="Session not found")
        return

    await websocket.accept()
    logger.info(f"WebSocket connected for session {session_id}")

    if session.initial_command and session.process.stdin:
        logger.info(f"Sending initial command for session {session_id}")
        session.process.stdin.write(session.initial_command + "\n")

    try:

        async def read_output() -> None:
            while True:
                try:
                    if session.process.stdout:
                        data = await session.process.stdout.read(4096)
                        if data:
                            text = data if isinstance(data, str) else data.decode("utf-8")
                            await websocket.send_text(text)
                        else:
                            break
                except Exception as e:
                    logger.error(f"Error reading output: {e}")
                    break
                await asyncio.sleep(0.01)

        output_task = asyncio.create_task(read_output())

        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "input":
                if session.process.stdin:
                    session.process.stdin.write(data["data"])
            elif msg_type == "resize":
                rows = data.get("rows", 24)
                cols = data.get("cols", 80)
                await shell_session_manager.resize_terminal(session_id, rows, cols)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
    finally:
        if "output_task" in locals():
            output_task.cancel()
            try:
                await output_task
            except asyncio.CancelledError:
                pass


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_http_app(
    cors_origins: list[str] | None = None,
) -> Starlette:
    """Create a Starlette ASGI application with MCP SDK HTTP transport.

    The /mcp endpoint is handled by StreamableHTTPSessionManager,
    which speaks the MCP Streamable HTTP protocol. Other routes are
    standard Starlette handlers.

    Args:
        cors_origins: Allowed CORS origins (default ``["*"]``).

    Returns:
        Configured Starlette application.
    """
    origins = cors_origins or ["*"]

    session_manager = StreamableHTTPSessionManager(app=server)

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        """Starlette lifespan wrapping StreamableHTTPSessionManager."""
        logger.info("HTTP app starting -- initializing MCP session manager")
        shell_session_manager.start_cleanup_task()
        async with session_manager.run():
            yield
        logger.info("HTTP app stopped -- MCP session manager shut down")

    async def mcp_handler(scope: Any, receive: Any, send: Any) -> None:
        """ASGI handler delegating to StreamableHTTPSessionManager."""
        await session_manager.handle_request(scope, receive, send)

    routes = [
        Route("/", handle_root, methods=["GET"]),
        Route("/health", handle_health, methods=["GET"]),
        Route("/shell/{session_id}", handle_shell_page, methods=["GET"]),
        WebSocketRoute("/ws/shell/{session_id}", handle_shell_websocket),
        Mount("/mcp", app=mcp_handler),
    ]

    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )
    ]

    return Starlette(
        routes=routes,
        middleware=middleware,
        lifespan=lifespan,
    )
