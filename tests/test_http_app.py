"""Tests for Origin validation middleware and HTTP app configuration."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from homelab_mcp.http_app import OriginValidationMiddleware


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _echo_handler(request: Request) -> JSONResponse:
    """Simple handler that returns 200 OK."""
    return JSONResponse({"status": "ok"})


def _make_app(allowed_origins: list[str] | None = None) -> Starlette:
    """Create a minimal Starlette app with OriginValidationMiddleware."""
    middleware = [
        Middleware(OriginValidationMiddleware, allowed_origins=allowed_origins),
    ]
    return Starlette(
        routes=[Route("/mcp", _echo_handler, methods=["POST", "GET"])],
        middleware=middleware,
    )


# ---------------------------------------------------------------------------
# Origin validation tests
# ---------------------------------------------------------------------------


class TestOriginValidationMiddleware:
    """Tests for OriginValidationMiddleware."""

    def test_disallowed_origin_returns_403(self) -> None:
        """POST to /mcp with Origin 'http://evil.com' returns 403."""
        client = TestClient(_make_app())
        response = client.post("/mcp", headers={"Origin": "http://evil.com"})
        assert response.status_code == 403

    def test_localhost_origin_allowed(self) -> None:
        """POST to /mcp with Origin 'http://localhost' returns non-403."""
        client = TestClient(_make_app())
        response = client.post("/mcp", headers={"Origin": "http://localhost"})
        assert response.status_code != 403

    def test_localhost_with_port_allowed(self) -> None:
        """POST to /mcp with Origin 'http://localhost:3000' returns non-403."""
        client = TestClient(_make_app())
        response = client.post(
            "/mcp", headers={"Origin": "http://localhost:3000"}
        )
        assert response.status_code != 403

    def test_127_0_0_1_origin_allowed(self) -> None:
        """POST to /mcp with Origin 'http://127.0.0.1' returns non-403."""
        client = TestClient(_make_app())
        response = client.post(
            "/mcp", headers={"Origin": "http://127.0.0.1"}
        )
        assert response.status_code != 403

    def test_no_origin_header_allowed(self) -> None:
        """POST to /mcp with no Origin header returns non-403 (non-browser)."""
        client = TestClient(_make_app())
        response = client.post("/mcp")
        assert response.status_code != 403

    def test_custom_allowed_origins(self) -> None:
        """Custom allowed origins via constructor parameter work."""
        app = _make_app(allowed_origins=["http://myapp.local"])
        client = TestClient(app)

        # Custom origin allowed
        response = client.post(
            "/mcp", headers={"Origin": "http://myapp.local"}
        )
        assert response.status_code != 403

        # Default localhost should NOT be allowed when custom list given
        # (unless explicitly included)
        response = client.post(
            "/mcp", headers={"Origin": "http://evil.com"}
        )
        assert response.status_code == 403

    def test_env_var_parsed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MCP_ALLOWED_ORIGINS env var is parsed (comma-separated) and passed to middleware."""
        monkeypatch.setenv(
            "MCP_ALLOWED_ORIGINS",
            "http://myapp.local,https://openwebui.local",
        )

        from homelab_mcp.http_app import create_http_app

        app = create_http_app()
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/mcp", headers={"Origin": "http://myapp.local"}
        )
        assert response.status_code != 403

        response = client.post(
            "/mcp", headers={"Origin": "https://openwebui.local"}
        )
        assert response.status_code != 403

        response = client.post(
            "/mcp", headers={"Origin": "http://evil.com"}
        )
        assert response.status_code == 403

    def test_403_response_is_json(self) -> None:
        """403 response body is valid JSON with error detail."""
        client = TestClient(_make_app())
        response = client.post("/mcp", headers={"Origin": "http://evil.com"})
        assert response.status_code == 403
        body = response.json()
        assert "error" in body or "detail" in body
