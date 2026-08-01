"""MCP logging notification support for progress reporting.

Provides emit_progress() for sending log notifications to MCP clients during
long-running operations. Extracted into its own module to avoid circular imports
(server.py -> tool_handlers -> infrastructure_crud -> server.py).
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any

import mcp.types as types

# mcp 2.0 removed the SDK-global request contextvar; we keep our own, set by
# server._on_call_tool for each dispatch. Same name/semantics as the old SDK
# one so emit_progress and its tests are unchanged (unset -> LookupError).
request_ctx: ContextVar[Any] = ContextVar("homelab_request_ctx")

logger = logging.getLogger(__name__)

# Syslog severity levels in ascending order (RFC 5424)
LOG_LEVEL_ORDER: dict[str, int] = {
    "debug": 0,
    "info": 1,
    "notice": 2,
    "warning": 3,
    "error": 4,
    "critical": 5,
    "alert": 6,
    "emergency": 7,
}

# Minimum log level; updated by set_logging_level handler when client sends logging/setLevel.
_min_log_level: types.LoggingLevel = "info"


def should_emit(level: str, min_level: str) -> bool:
    """Return True if *level* is at or above *min_level* in syslog severity order."""
    return LOG_LEVEL_ORDER.get(level, 0) >= LOG_LEVEL_ORDER.get(min_level, 0)


def set_min_log_level(level: types.LoggingLevel) -> None:
    """Update the minimum log level (called by the set_logging_level handler)."""
    global _min_log_level  # noqa: PLW0603
    _min_log_level = level


async def emit_progress(
    level: types.LoggingLevel,
    message: str,
    data: Any | None = None,
) -> None:
    """Send a log notification to the connected MCP client.

    Gracefully degrades:
    - Returns immediately when *level* is below the client-configured minimum.
    - Catches LookupError when called outside a request context (e.g. during tests).
    - Catches generic exceptions to avoid crashing a tool handler due to notification failure.
    """
    if not should_emit(level, _min_log_level):
        return

    try:
        ctx = request_ctx.get()
        await ctx.session.send_log_message(
            level=level,
            data=data or message,
            logger="homelab-mcp",
        )
    except LookupError:
        # Not in a request context (e.g. tests, startup) -- skip notification.
        logger.debug("Skipping progress notification (no request context): %s", message)
    except Exception:
        logger.debug("Failed to emit progress notification: %s", message)
