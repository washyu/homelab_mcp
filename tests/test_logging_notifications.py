"""Tests for MCP logging notification capability.

Covers:
- set_logging_level handler registration
- emit_progress helper with level filtering
- Graceful degradation outside request context
- should_emit level comparison logic
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homelab_mcp.server import (
    LOG_LEVEL_ORDER,
    emit_progress,
    should_emit,
)


class TestShouldEmit:
    """Tests for the should_emit level filtering function."""

    def test_same_level_emits(self) -> None:
        assert should_emit("info", "info") is True

    def test_higher_level_emits(self) -> None:
        assert should_emit("warning", "info") is True

    def test_lower_level_does_not_emit(self) -> None:
        assert should_emit("debug", "info") is False

    def test_emergency_always_emits(self) -> None:
        assert should_emit("emergency", "error") is True

    def test_debug_emits_when_min_is_debug(self) -> None:
        assert should_emit("debug", "debug") is True

    def test_all_levels_in_order(self) -> None:
        levels = list(LOG_LEVEL_ORDER.keys())
        for i, level in enumerate(levels):
            for j, min_level in enumerate(levels):
                expected = i >= j
                assert should_emit(level, min_level) is expected, (
                    f"should_emit({level!r}, {min_level!r}) should be {expected}"
                )


class TestEmitProgress:
    """Tests for the emit_progress async helper."""

    @pytest.mark.asyncio
    async def test_sends_log_message_in_request_context(self) -> None:
        """emit_progress sends log message via session when in request context."""
        mock_session = MagicMock()
        mock_session.send_log_message = AsyncMock()

        mock_ctx = MagicMock()
        mock_ctx.session = mock_session

        with patch("homelab_mcp.server.request_ctx") as mock_request_ctx, \
             patch("homelab_mcp.server._min_log_level", "info"):
            mock_request_ctx.get.return_value = mock_ctx
            await emit_progress("info", "Scanning network")

        mock_session.send_log_message.assert_awaited_once_with(
            level="info",
            data="Scanning network",
            logger="homelab-mcp",
        )

    @pytest.mark.asyncio
    async def test_sends_data_when_provided(self) -> None:
        """emit_progress sends data dict instead of message when data is provided."""
        mock_session = MagicMock()
        mock_session.send_log_message = AsyncMock()

        mock_ctx = MagicMock()
        mock_ctx.session = mock_session

        data_payload: dict[str, Any] = {"progress": 3, "total": 10}

        with patch("homelab_mcp.server.request_ctx") as mock_request_ctx, \
             patch("homelab_mcp.server._min_log_level", "info"):
            mock_request_ctx.get.return_value = mock_ctx
            await emit_progress("info", "progress update", data=data_payload)

        mock_session.send_log_message.assert_awaited_once_with(
            level="info",
            data=data_payload,
            logger="homelab-mcp",
        )

    @pytest.mark.asyncio
    async def test_no_crash_outside_request_context(self) -> None:
        """emit_progress gracefully handles LookupError when not in request context."""
        with patch("homelab_mcp.server.request_ctx") as mock_request_ctx, \
             patch("homelab_mcp.server._min_log_level", "info"):
            mock_request_ctx.get.side_effect = LookupError("no context")
            # Should not raise
            await emit_progress("info", "This should not crash")

    @pytest.mark.asyncio
    async def test_respects_minimum_log_level(self) -> None:
        """emit_progress skips sending when level is below min_level."""
        mock_session = MagicMock()
        mock_session.send_log_message = AsyncMock()

        mock_ctx = MagicMock()
        mock_ctx.session = mock_session

        with patch("homelab_mcp.server.request_ctx") as mock_request_ctx, \
             patch("homelab_mcp.server._min_log_level", "warning"):
            mock_request_ctx.get.return_value = mock_ctx
            await emit_progress("debug", "This debug message should be filtered")

        mock_session.send_log_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_catches_generic_exception(self) -> None:
        """emit_progress catches and logs unexpected exceptions without crashing."""
        mock_ctx = MagicMock()
        mock_ctx.session.send_log_message = AsyncMock(
            side_effect=RuntimeError("connection lost")
        )

        with patch("homelab_mcp.server.request_ctx") as mock_request_ctx, \
             patch("homelab_mcp.server._min_log_level", "info"):
            mock_request_ctx.get.return_value = mock_ctx
            # Should not raise
            await emit_progress("info", "This should not crash either")


class TestSetLoggingLevelRegistration:
    """Tests for set_logging_level handler registration."""

    def test_server_has_logging_handler(self) -> None:
        """The server should have a set_logging_level handler registered."""
        from homelab_mcp.server import server

        # The Server stores handlers internally; check that logging level handler exists.
        # When set_logging_level() decorator is used, it sets _set_logging_level_handler.
        assert server.set_logging_level_handler is not None, (
            "set_logging_level handler should be registered on the server"
        )
