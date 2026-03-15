"""Tests for interactive shell session management."""

import asyncio
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
