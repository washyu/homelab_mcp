"""
HTTP transport for MCP server using Starlette.

Implements the MCP Streamable HTTP transport protocol:
- POST /mcp - JSON-RPC requests
- GET /mcp - SSE stream for server notifications
- GET /health - Health check endpoint
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from .auth import APIKeyAuth
from .error_handling import health_checker
from .shell_session import session_manager

if TYPE_CHECKING:
    from .server import HomelabMCPServer

logger = logging.getLogger(__name__)


class SSEResponse(Response):
    """Server-Sent Events response for streaming notifications."""

    media_type = "text/event-stream"

    def __init__(
        self,
        content: Any = None,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        headers = headers or {}
        headers["Cache-Control"] = "no-cache"
        headers["Connection"] = "keep-alive"
        headers["X-Accel-Buffering"] = "no"
        super().__init__(
            content=content, status_code=status_code, headers=headers, **kwargs
        )


class MCPHTTPTransport:
    """HTTP transport layer for MCP server."""

    def __init__(
        self,
        server: HomelabMCPServer,
        auth_enabled: bool = True,
        api_key: str | None = None,
        cors_origins: list[str] | None = None,
    ) -> None:
        """
        Initialize the HTTP transport.

        Args:
            server: The HomelabMCPServer instance to handle requests
            auth_enabled: Whether to enable API key authentication
            api_key: Optional API key (uses MCP_API_KEY env var if not provided)
            cors_origins: List of allowed CORS origins (default: ["*"] for all)
        """
        self.server = server
        self.auth_enabled = auth_enabled
        self.api_key = api_key
        self.cors_origins = cors_origins or ["*"]
        self._notification_queues: list[asyncio.Queue[dict[str, Any]]] = []

    async def handle_mcp_post(self, request: Request) -> Response:
        """
        Handle MCP JSON-RPC requests via HTTP POST.

        This endpoint receives JSON-RPC 2.0 requests and returns responses.
        """
        try:
            # Parse JSON body
            try:
                body = await request.json()
            except json.JSONDecodeError as e:
                return JSONResponse(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32700,
                            "message": f"Parse error: {str(e)}",
                        },
                    },
                    status_code=400,
                )

            # Handle batch requests
            if isinstance(body, list):
                responses = []
                for req in body:
                    resp = await self._handle_single_request(req)
                    if resp is not None:  # Notifications don't return responses
                        responses.append(resp)
                return JSONResponse(responses if responses else None)

            # Handle single request
            response = await self._handle_single_request(body)
            if response is None:
                # Notification - return 204 No Content
                return Response(status_code=204)

            return JSONResponse(response)

        except Exception as e:
            logger.error(f"Error handling MCP request: {str(e)}", exc_info=True)
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}",
                    },
                },
                status_code=500,
            )

    async def _handle_single_request(self, request: Any) -> dict[str, Any] | None:
        """Handle a single JSON-RPC request."""
        # Validate JSON-RPC format
        if not isinstance(request, dict):
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32600,
                    "message": "Invalid Request: expected object",
                },
            }

        if request.get("jsonrpc") != "2.0":
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32600,
                    "message": "Invalid Request: missing or invalid jsonrpc version",
                },
            }

        # Check if this is a notification (no id)
        is_notification = "id" not in request

        # Handle notification
        if is_notification:
            method = request.get("method")
            if method == "notifications/initialized":
                logger.info("Client initialized notification received via HTTP")
            return None

        # Process request through the server
        response = await self.server.handle_request(request)
        return response

    async def handle_mcp_sse(self, request: Request) -> Response:
        """
        Handle SSE stream for server-to-client notifications.

        This endpoint provides a Server-Sent Events stream for
        real-time notifications from the server.
        """

        async def event_generator() -> Any:
            """Generate SSE events."""
            queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
            self._notification_queues.append(queue)

            try:
                # Send initial connection event
                yield f"event: connected\ndata: {json.dumps({'status': 'connected', 'timestamp': datetime.now(UTC).isoformat()})}\n\n"

                # Keep connection alive and send notifications
                while True:
                    try:
                        # Wait for notification with timeout for keepalive
                        notification = await asyncio.wait_for(queue.get(), timeout=30.0)
                        yield f"event: notification\ndata: {json.dumps(notification)}\n\n"
                    except TimeoutError:
                        # Send keepalive comment
                        yield ": keepalive\n\n"

            except asyncio.CancelledError:
                pass
            finally:
                self._notification_queues.remove(queue)

        return SSEResponse(content=event_generator())

    async def send_notification(self, notification: dict[str, Any]) -> None:
        """
        Send a notification to all connected SSE clients.

        Args:
            notification: The notification data to send
        """
        for queue in self._notification_queues:
            try:
                await queue.put(notification)
            except Exception as e:
                logger.error(f"Failed to send notification: {str(e)}")

    async def handle_health(self, request: Request) -> Response:
        """
        Health check endpoint.

        Returns server health status for monitoring.
        """
        health_status = health_checker.get_health_status()
        health_status["transport"] = "http"

        status_code = 200 if health_status["status"] == "healthy" else 503
        return JSONResponse(health_status, status_code=status_code)

    async def handle_shell_page(self, request: Request) -> Response:
        """
        Serve the interactive shell HTML page.

        Args:
            request: HTTP request with session_id in path

        Returns:
            HTML page with xterm.js terminal
        """
        session_id = request.path_params["session_id"]

        # Get session to verify it exists and get connection info
        session = session_manager.get_session(session_id)
        if not session:
            return JSONResponse(
                {"error": "Session not found or expired"},
                status_code=404
            )

        # Load HTML template
        from pathlib import Path
        template_path = Path(__file__).parent / "shell_terminal.html"
        html_content = template_path.read_text()

        # Replace template variables
        html_content = html_content.replace("{{session_id}}", session_id)
        html_content = html_content.replace("{{hostname}}", session.hostname)
        html_content = html_content.replace("{{username}}", session.username)

        return HTMLResponse(html_content)

    async def handle_shell_websocket(self, websocket: WebSocket) -> None:
        """
        Handle WebSocket connection for interactive shell.

        Args:
            websocket: WebSocket connection
        """
        session_id = websocket.path_params["session_id"]

        # Get session
        session = session_manager.get_session(session_id)
        if not session:
            await websocket.close(code=1008, reason="Session not found")
            return

        # Accept WebSocket connection
        await websocket.accept()
        logger.info(f"WebSocket connected for session {session_id}")

        # Send initial command if configured
        if session.initial_command and session.process.stdin:
            logger.info(f"Sending initial command for session {session_id}")
            session.process.stdin.write(session.initial_command + "\n")

        try:
            # Start output reader task
            async def read_output():
                """Read output from shell and send to WebSocket."""
                while True:
                    try:
                        if session.process.stdout:
                            data = await session.process.stdout.read(4096)
                            if data:
                                text = data if isinstance(data, str) else data.decode("utf-8")
                                await websocket.send_text(text)
                            else:
                                # EOF - process terminated
                                break
                    except Exception as e:
                        logger.error(f"Error reading output: {e}")
                        break
                    await asyncio.sleep(0.01)

            # Start output reader in background
            output_task = asyncio.create_task(read_output())

            # Handle incoming messages
            while True:
                message = await websocket.receive_text()
                data = json.loads(message)

                msg_type = data.get("type")

                if msg_type == "input":
                    # Send input to shell
                    if session.process.stdin:
                        session.process.stdin.write(data["data"])

                elif msg_type == "resize":
                    # Resize terminal
                    rows = data.get("rows", 24)
                    cols = data.get("cols", 80)
                    await session_manager.resize_terminal(session_id, rows, cols)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for session {session_id}")
        except Exception as e:
            logger.error(f"WebSocket error for session {session_id}: {e}")
        finally:
            # Cancel output reader
            if 'output_task' in locals():
                output_task.cancel()
                try:
                    await output_task
                except asyncio.CancelledError:
                    pass

    def create_app(self) -> Starlette | APIKeyAuth:
        """
        Create the Starlette ASGI application.

        Returns:
            Configured ASGI application (Starlette or wrapped with APIKeyAuth)
        """
        routes = [
            Route("/mcp", self.handle_mcp_post, methods=["POST"]),
            Route("/mcp", self.handle_mcp_sse, methods=["GET"]),
            Route("/health", self.handle_health, methods=["GET"]),
            Route("/", self._handle_root, methods=["GET"]),
            Route("/shell/{session_id}", self.handle_shell_page, methods=["GET"]),
            WebSocketRoute("/ws/shell/{session_id}", self.handle_shell_websocket),
        ]

        # Configure CORS middleware for cross-origin requests (e.g., OpenWebUI)
        middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=self.cors_origins,
                allow_credentials=True,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["*"],
            )
        ]

        app: Starlette | APIKeyAuth = Starlette(
            routes=routes,
            middleware=middleware,
            on_startup=[self._on_startup],
            on_shutdown=[self._on_shutdown],
        )

        # Wrap with authentication middleware if enabled
        if self.auth_enabled:
            app = APIKeyAuth(
                app,
                api_key=self.api_key,
                enabled=self.auth_enabled,
                exclude_paths=["/health", "/", "/shell/", "/ws/shell/"],
            )

        return app

    async def _handle_root(self, request: Request) -> Response:
        """Handle root endpoint for service discovery."""
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

    async def _on_startup(self) -> None:
        """Handle application startup."""
        logger.info("MCP HTTP transport starting up")
        # Start session cleanup task
        session_manager.start_cleanup_task()

    async def _on_shutdown(self) -> None:
        """Handle application shutdown."""
        logger.info("MCP HTTP transport shutting down")
        # Notify all connected clients
        shutdown_notification = {
            "type": "shutdown",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await self.send_notification(shutdown_notification)


def create_mcp_http_app(
    server: HomelabMCPServer,
    auth_enabled: bool = True,
    api_key: str | None = None,
    cors_origins: list[str] | None = None,
) -> Starlette | APIKeyAuth:
    """
    Create an MCP HTTP application.

    Args:
        server: The HomelabMCPServer instance
        auth_enabled: Whether to enable authentication
        api_key: Optional API key
        cors_origins: List of allowed CORS origins (default: ["*"] for all)

    Returns:
        Configured ASGI application
    """
    transport = MCPHTTPTransport(
        server=server,
        auth_enabled=auth_enabled,
        api_key=api_key,
        cors_origins=cors_origins,
    )
    return transport.create_app()
