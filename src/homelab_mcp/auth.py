"""
API key authentication middleware for HTTP transport.

Provides Bearer token authentication for the MCP HTTP server.
"""

import logging
import os
import secrets

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


class APIKeyAuth:
    """API key authentication middleware for Starlette."""

    def __init__(
        self,
        app: ASGIApp,
        api_key: str | None = None,
        enabled: bool = True,
        exclude_paths: list[str] | None = None,
    ) -> None:
        """
        Initialize the authentication middleware.

        Args:
            app: The ASGI application to wrap
            api_key: The API key to validate against. If None, uses MCP_API_KEY env var.
            enabled: Whether authentication is enabled
            exclude_paths: List of paths to exclude from authentication (e.g., ["/health"])
        """
        self.app = app
        self.enabled = enabled
        self.exclude_paths = exclude_paths or ["/health"]

        # Get API key from parameter or environment
        self.api_key = api_key or os.getenv("MCP_API_KEY")

        if self.enabled and not self.api_key:
            logger.warning(
                "HTTP authentication is enabled but MCP_API_KEY is not set. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """ASGI middleware entry point."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Check if path is excluded from authentication
        path = scope.get("path", "")
        for exclude_path in self.exclude_paths:
            # Support both exact match and prefix match (if exclude_path ends with /)
            if exclude_path.endswith("/"):
                if path.startswith(exclude_path):
                    await self.app(scope, receive, send)
                    return
            elif path == exclude_path:
                await self.app(scope, receive, send)
                return

        # Skip auth if disabled
        if not self.enabled:
            await self.app(scope, receive, send)
            return

        # No API key configured - reject all requests
        if not self.api_key:
            response = JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32001,
                        "message": "Server misconfigured: MCP_API_KEY not set",
                    },
                },
                status_code=500,
            )
            await response(scope, receive, send)
            return

        # Extract Authorization header
        request = Request(scope)
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            response = JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32001,
                        "message": "Missing or invalid Authorization header. Expected: Bearer <api-key>",
                    },
                },
                status_code=401,
            )
            await response(scope, receive, send)
            return

        # Extract and validate token
        token = auth_header[7:]  # Remove "Bearer " prefix

        if not secrets.compare_digest(token, self.api_key):
            logger.warning(f"Invalid API key attempt from {request.client}")
            response = JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32001,
                        "message": "Invalid API key",
                    },
                },
                status_code=401,
            )
            await response(scope, receive, send)
            return

        # Authentication successful - proceed with request
        await self.app(scope, receive, send)


def generate_api_key() -> str:
    """Generate a secure API key."""
    return secrets.token_urlsafe(32)


def validate_api_key_strength(api_key: str) -> tuple[bool, str]:
    """
    Validate that an API key meets minimum security requirements.

    Args:
        api_key: The API key to validate

    Returns:
        Tuple of (is_valid, message)
    """
    if len(api_key) < 16:
        return False, "API key must be at least 16 characters long"

    if api_key.isalpha() or api_key.isdigit():
        return False, "API key should contain a mix of characters"

    return True, "API key meets security requirements"
