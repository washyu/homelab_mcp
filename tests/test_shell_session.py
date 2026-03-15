"""Tests for interactive shell session management."""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestShellSessionTermSize:
    """Tests for terminal size configuration."""

    @pytest.mark.asyncio
    async def test_create_session_uses_correct_term_size(self) -> None:
        """PTY must be created with width=80, height=24 (not inverted)."""
        with patch("homelab_mcp.shell_session.resolve_ssh_credentials") as mock_creds, \
             patch("homelab_mcp.shell_session.ssh_connect") as mock_connect:
            mock_creds.return_value = MagicMock(
                hostname="testhost", username="testuser", port=22,
                password=None, key_path=None,
            )
            mock_conn = AsyncMock()
            mock_process = MagicMock()
            mock_conn.create_process = AsyncMock(return_value=mock_process)
            mock_connect.return_value = mock_conn

            from homelab_mcp.shell_session import ShellSessionManager
            mgr = ShellSessionManager()
            await mgr.create_session("testhost")

            call_kwargs = mock_conn.create_process.call_args.kwargs
            assert call_kwargs["term_size"] == (80, 24), (
                f"term_size must be (80, 24) (width, height); got {call_kwargs['term_size']!r}"
            )


class TestStdioModeGuard:
    """Tests for stdio mode guard in handle_start_interactive_shell (SHELL-04)."""

    @pytest.mark.asyncio
    async def test_stdio_mode_returns_error_when_http_disabled(self) -> None:
        """handle_start_interactive_shell must return stdio_mode_unsupported when MCP_HTTP_ENABLED is unset."""
        env_without_http = {k: v for k, v in os.environ.items() if k != "MCP_HTTP_ENABLED"}
        with patch.dict(os.environ, env_without_http, clear=True):
            from homelab_mcp.tool_handlers.ssh_handlers import handle_start_interactive_shell
            result = await handle_start_interactive_shell({"hostname": "test"})

        assert "content" in result
        assert len(result["content"]) == 1
        text = result["content"][0]["text"]
        data = json.loads(text)
        assert data["status"] == "error"
        assert data["error_type"] == "stdio_mode_unsupported"
        assert "--http" in data["error"]

    @pytest.mark.asyncio
    async def test_stdio_mode_returns_error_when_http_false(self) -> None:
        """handle_start_interactive_shell must return error when MCP_HTTP_ENABLED=false."""
        with patch.dict(os.environ, {"MCP_HTTP_ENABLED": "false"}, clear=False):
            from homelab_mcp.tool_handlers.ssh_handlers import handle_start_interactive_shell
            result = await handle_start_interactive_shell({"hostname": "test"})

        data = json.loads(result["content"][0]["text"])
        assert data["error_type"] == "stdio_mode_unsupported"

    @pytest.mark.asyncio
    async def test_http_mode_proceeds_past_guard(self) -> None:
        """When MCP_HTTP_ENABLED=true, the guard is not triggered (session creation is attempted)."""
        with patch.dict(os.environ, {"MCP_HTTP_ENABLED": "true"}, clear=False), \
             patch("homelab_mcp.tool_handlers.ssh_handlers.session_manager") as mock_mgr:
            mock_session = MagicMock()
            mock_session.hostname = "test"
            mock_session.username = "user"
            mock_mgr.create_session = AsyncMock(return_value=("session-id-123", mock_session))

            from homelab_mcp.tool_handlers.ssh_handlers import handle_start_interactive_shell
            result = await handle_start_interactive_shell({"hostname": "test"})

        # Guard was not triggered — session_manager.create_session was called
        mock_mgr.create_session.assert_called_once()
        # Result should be a success response (not the guard error)
        data = json.loads(result["content"][0]["text"])
        assert data.get("error_type") != "stdio_mode_unsupported"
