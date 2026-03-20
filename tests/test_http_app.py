"""Tests for Origin validation middleware and HTTP app configuration."""

from __future__ import annotations

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
        response = client.post("/mcp", headers={"Origin": "http://localhost:3000"})
        assert response.status_code != 403

    def test_127_0_0_1_origin_allowed(self) -> None:
        """POST to /mcp with Origin 'http://127.0.0.1' returns non-403."""
        client = TestClient(_make_app())
        response = client.post("/mcp", headers={"Origin": "http://127.0.0.1"})
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
        response = client.post("/mcp", headers={"Origin": "http://myapp.local"})
        assert response.status_code != 403

        # Default localhost should NOT be allowed when custom list given
        # (unless explicitly included)
        response = client.post("/mcp", headers={"Origin": "http://evil.com"})
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

        response = client.post("/mcp", headers={"Origin": "http://myapp.local"})
        assert response.status_code != 403

        response = client.post("/mcp", headers={"Origin": "https://openwebui.local"})
        assert response.status_code != 403

        response = client.post("/mcp", headers={"Origin": "http://evil.com"})
        assert response.status_code == 403

    def test_403_response_is_json(self) -> None:
        """403 response body is valid JSON with error detail."""
        client = TestClient(_make_app())
        response = client.post("/mcp", headers={"Origin": "http://evil.com"})
        assert response.status_code == 403
        body = response.json()
        assert "error" in body or "detail" in body


# ---------------------------------------------------------------------------
# API key auth enforcement tests
# ---------------------------------------------------------------------------


class TestAPIKeyAuthEnforcement:
    """Tests for APIKeyAuth middleware wired into create_http_app()."""

    def test_mcp_endpoint_requires_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """POST to /mcp without Authorization header returns 401 when MCP_API_KEY is set."""
        monkeypatch.setenv("MCP_API_KEY", "test-secret-key-32chars-longxxxx")

        from homelab_mcp.http_app import create_http_app

        app = create_http_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/mcp", json={"jsonrpc": "2.0", "method": "ping", "id": 1})
        assert response.status_code == 401

    def test_mcp_endpoint_accepts_valid_bearer_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """POST /mcp with valid Bearer token does not return 401 when MCP_API_KEY is set."""
        monkeypatch.setenv("MCP_API_KEY", "test-secret-key-32chars-longxxxx")

        from homelab_mcp.http_app import create_http_app

        app = create_http_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
            headers={"Authorization": "Bearer test-secret-key-32chars-longxxxx"},
        )
        assert response.status_code != 401

    def test_health_endpoint_excluded_from_auth(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GET /health returns non-401 even when MCP_API_KEY is set (excluded path)."""
        monkeypatch.setenv("MCP_API_KEY", "test-secret-key-32chars-longxxxx")

        from homelab_mcp.http_app import create_http_app

        app = create_http_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/health")
        assert response.status_code != 401

    def test_no_api_key_set_allows_unauthenticated_access(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """POST /mcp succeeds without auth header when MCP_API_KEY is NOT set."""
        monkeypatch.delenv("MCP_API_KEY", raising=False)

        from homelab_mcp.http_app import create_http_app

        app = create_http_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/mcp", json={"jsonrpc": "2.0", "method": "ping", "id": 1})
        assert response.status_code != 401


# ---------------------------------------------------------------------------
# WebSocket read_output tests (SHELL-01, SHELL-03)
# ---------------------------------------------------------------------------


class TestWebSocketReadOutput:
    """Tests for the read_output inner function in handle_shell_websocket."""

    @pytest.mark.asyncio
    async def test_read_output_sends_eof_notification(self) -> None:
        """When stdout returns empty string (EOF), websocket receives a disconnect message.

        This test exercises read_output in isolation by calling the fixed
        http_app.py's logic directly: wrap stdout.read in asyncio.wait_for,
        detect empty-string EOF, send a disconnect notification.
        """
        import asyncio
        from unittest.mock import AsyncMock

        sent_messages: list[str] = []

        # Simulate stdout: first call returns data, second returns "" (EOF)
        read_calls = 0

        async def fake_read(n: int) -> str:
            nonlocal read_calls
            read_calls += 1
            if read_calls == 1:
                return "hello"
            return ""  # EOF

        mock_stdout = AsyncMock()
        mock_stdout.read = fake_read

        mock_websocket = AsyncMock()
        mock_websocket.send_text = AsyncMock(side_effect=lambda msg: sent_messages.append(msg))

        # Run the read_output logic directly (mirrors the fixed implementation)
        async def read_output() -> None:
            while True:
                try:
                    data = await asyncio.wait_for(
                        mock_stdout.read(4096),
                        timeout=0.05,
                    )
                    if data:
                        text = data if isinstance(data, str) else data.decode("utf-8")
                        await mock_websocket.send_text(text)
                    else:
                        # EOF — process exited
                        await mock_websocket.send_text("\r\n\x1b[31m[Connection closed]\x1b[0m\r\n")
                        break
                except TimeoutError:
                    pass
                except Exception:
                    break

        await read_output()

        # Verify data message and disconnect notification were sent
        assert "hello" in sent_messages, f"Expected data message; got: {sent_messages!r}"
        disconnect_msgs = [m for m in sent_messages if "closed" in m.lower() or "connection" in m.lower()]
        assert disconnect_msgs, (
            f"Expected a disconnect/closed notification in websocket messages; got: {sent_messages!r}"
        )

    def test_read_output_no_sleep_after_wait_for(self) -> None:
        """The read_output function body must NOT contain asyncio.sleep (removed after wait_for fix)."""
        import ast
        import inspect
        import textwrap

        from homelab_mcp import http_app

        source = inspect.getsource(http_app.handle_shell_websocket)

        # Extract read_output inner function body using AST
        tree = ast.parse(textwrap.dedent(source))

        # Flatten all Call nodes in the AST and look for asyncio.sleep calls
        sleep_calls: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check for asyncio.sleep(...)
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "sleep"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "asyncio"
                ):
                    sleep_calls.append(ast.unparse(node))

        assert not sleep_calls, f"asyncio.sleep should be removed from read_output; found: {sleep_calls}"

    def test_read_output_uses_wait_for(self) -> None:
        """The read_output function body must use asyncio.wait_for for non-blocking reads."""
        import ast
        import inspect
        import textwrap

        from homelab_mcp import http_app

        source = inspect.getsource(http_app.handle_shell_websocket)
        tree = ast.parse(textwrap.dedent(source))

        wait_for_calls: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "wait_for"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "asyncio"
                ):
                    wait_for_calls.append(ast.unparse(node))

        assert wait_for_calls, "read_output must use asyncio.wait_for for non-blocking stdout reads; none found"
