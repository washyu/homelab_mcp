"""HTTP application composing MCP SDK transport with custom routes.

Uses StreamableHTTPSessionManager to handle MCP protocol on /mcp,
while preserving non-MCP routes (/health, /shell, /ws/shell).
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .auth import APIKeyAuth

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
    from mcp.server.streamable_http import StreamableHTTPSessionManager  # type: ignore[no-redef, attr-defined]

logger = logging.getLogger(__name__)

# Default origins considered safe (localhost variants)
_DEFAULT_ALLOWED_ORIGINS: list[str] = [
    "http://localhost",
    "https://localhost",
    "http://127.0.0.1",
    "https://127.0.0.1",
]


# ---------------------------------------------------------------------------
# Origin validation middleware (DNS rebinding protection)
# ---------------------------------------------------------------------------


class OriginValidationMiddleware:
    """ASGI middleware that validates the Origin header on incoming requests.

    Requests without an Origin header are allowed (non-browser clients).
    Requests with an Origin that does not match any allowed origin receive
    a ``403 Forbidden`` JSON response.

    Port variants are accepted: if ``http://localhost`` is allowed then
    ``http://localhost:3000`` is also accepted.
    """

    def __init__(
        self,
        app: Any,
        allowed_origins: list[str] | None = None,
    ) -> None:
        self.app = app
        self.allowed_origins = allowed_origins or list(_DEFAULT_ALLOWED_ORIGINS)

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        """ASGI interface -- check Origin on HTTP requests."""
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Extract Origin header from raw ASGI headers
        origin: str | None = None
        for header_name, header_value in scope.get("headers", []):
            if header_name == b"origin":
                origin = header_value.decode("latin-1")
                break

        if origin is not None and not self._is_allowed(origin):
            response = JSONResponse(
                {"error": "Forbidden", "detail": "Origin not allowed"},
                status_code=403,
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    def _is_allowed(self, origin: str) -> bool:
        """Check whether *origin* matches any allowed origin.

        An exact match passes.  A match of ``allowed + ":" + port`` also
        passes so that ``http://localhost:3000`` is accepted when
        ``http://localhost`` is in the allowed list.
        """
        for allowed in self.allowed_origins:
            if origin == allowed:
                return True
            if origin.startswith(allowed + ":"):
                return True
        return False


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
    allowed_origins: list[str] | None = None,
) -> Starlette | APIKeyAuth:
    """Create a Starlette ASGI application with MCP SDK HTTP transport.

    The /mcp endpoint is handled by StreamableHTTPSessionManager,
    which speaks the MCP Streamable HTTP protocol. Other routes are
    standard Starlette handlers.

    When ``MCP_API_KEY`` is set in the environment, the returned application
    is wrapped in :class:`~homelab_mcp.auth.APIKeyAuth` ASGI middleware so
    that all endpoints except ``/health``, ``/shell/``, and ``/ws/shell/``
    require a valid Bearer token.

    Args:
        cors_origins: Allowed CORS origins (default ``["*"]``).
        allowed_origins: Origins permitted by the Origin validation
            middleware.  Falls back to the ``MCP_ALLOWED_ORIGINS`` env
            var (comma-separated), then to localhost defaults.

    Returns:
        Configured Starlette application, optionally wrapped in
        :class:`~homelab_mcp.auth.APIKeyAuth` middleware.
    """
    origins = cors_origins or ["*"]

    # Resolve allowed origins: parameter > env var > defaults
    if allowed_origins is None:
        env_origins = os.getenv("MCP_ALLOWED_ORIGINS")
        if env_origins:
            allowed_origins = [o.strip() for o in env_origins.split(",") if o.strip()]

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
        Middleware(OriginValidationMiddleware, allowed_origins=allowed_origins),
        Middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        ),
    ]

    starlette_app = Starlette(
        routes=routes,
        middleware=middleware,
        lifespan=lifespan,
    )

    api_key = os.getenv("MCP_API_KEY")
    if api_key:
        from .auth import APIKeyAuth

        return APIKeyAuth(
            starlette_app,
            api_key=api_key,
            enabled=True,
            exclude_paths=["/health", "/shell/", "/ws/shell/"],
        )

    logger.warning("MCP_API_KEY not set — HTTP endpoints are unauthenticated")
    return starlette_app
