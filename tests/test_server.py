"""Tests for the MCP SDK-based server.

Tests cover:
- list_tools handler returns correct Tool objects
- call_tool handler dispatches and converts results
- call_tool with unknown tool raises ValueError
- Result conversion from legacy dict format to SDK types
- Lifespan manages ResourceManager lifecycle
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import mcp.types as types
import pytest

from src.homelab_mcp.server import (
    _convert_result,
    app_lifespan,
    handle_call_tool,
    handle_list_tools,
    server,
)


# ---------------------------------------------------------------------------
# list_tools tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tools_returns_tool_objects() -> None:
    """list_tools returns a list of types.Tool objects."""
    tools = await handle_list_tools()
    assert isinstance(tools, list)
    assert len(tools) > 0
    for tool in tools:
        assert isinstance(tool, types.Tool)


@pytest.mark.asyncio
async def test_list_tools_count_matches_schemas() -> None:
    """list_tools returns one Tool per schema in get_all_tool_schemas."""
    from src.homelab_mcp.tool_schemas import get_all_tool_schemas

    schemas = get_all_tool_schemas()
    tools = await handle_list_tools()
    assert len(tools) == len(schemas)


@pytest.mark.asyncio
async def test_list_tools_has_name_description_schema() -> None:
    """Each Tool has name, description, and inputSchema."""
    tools = await handle_list_tools()
    for tool in tools:
        assert tool.name, f"Tool missing name: {tool}"
        assert tool.description is not None, f"Tool {tool.name} missing description"
        assert tool.inputSchema is not None, f"Tool {tool.name} missing inputSchema"


@pytest.mark.asyncio
async def test_list_tools_includes_known_tools() -> None:
    """list_tools includes expected tool names like ssh_discover."""
    tools = await handle_list_tools()
    names = {t.name for t in tools}
    assert "ssh_discover" in names
    assert "list_vms" in names
    assert "get_network_sitemap" in names


# ---------------------------------------------------------------------------
# call_tool tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_tool_dispatches_to_handler() -> None:
    """call_tool finds the handler and converts the result."""
    mock_handler = AsyncMock(
        return_value={"content": [{"type": "text", "text": "hello world"}]}
    )

    with patch(
        "src.homelab_mcp.server.get_tool_handler", return_value=mock_handler
    ):
        result = await handle_call_tool("my_tool", {"arg": "value"})

    mock_handler.assert_awaited_once_with({"arg": "value"})
    assert len(result) == 1
    assert isinstance(result[0], types.TextContent)
    assert result[0].text == "hello world"


@pytest.mark.asyncio
async def test_call_tool_with_none_arguments() -> None:
    """call_tool passes empty dict when arguments is None."""
    mock_handler = AsyncMock(
        return_value={"content": [{"type": "text", "text": "ok"}]}
    )

    with patch(
        "src.homelab_mcp.server.get_tool_handler", return_value=mock_handler
    ):
        result = await handle_call_tool("my_tool", None)

    mock_handler.assert_awaited_once_with({})
    assert len(result) == 1
    assert result[0].text == "ok"


@pytest.mark.asyncio
async def test_call_tool_unknown_tool_raises_value_error() -> None:
    """call_tool raises ValueError for unknown tool names."""
    with pytest.raises(ValueError, match="Unknown tool"):
        await handle_call_tool("nonexistent_tool_xyz", {})


# ---------------------------------------------------------------------------
# Result conversion tests
# ---------------------------------------------------------------------------


def test_convert_result_text_content() -> None:
    """_convert_result converts text items to TextContent."""
    result: dict[str, Any] = {
        "content": [{"type": "text", "text": "hello"}]
    }
    converted = _convert_result(result)
    assert len(converted) == 1
    assert isinstance(converted[0], types.TextContent)
    assert converted[0].text == "hello"
    assert converted[0].type == "text"


def test_convert_result_multiple_items() -> None:
    """_convert_result handles multiple content items."""
    result: dict[str, Any] = {
        "content": [
            {"type": "text", "text": "first"},
            {"type": "text", "text": "second"},
        ]
    }
    converted = _convert_result(result)
    assert len(converted) == 2
    assert converted[0].text == "first"
    assert converted[1].text == "second"


def test_convert_result_image_content() -> None:
    """_convert_result converts image items to ImageContent."""
    result: dict[str, Any] = {
        "content": [
            {"type": "image", "data": "base64data", "mimeType": "image/png"}
        ]
    }
    converted = _convert_result(result)
    assert len(converted) == 1
    assert isinstance(converted[0], types.ImageContent)
    assert converted[0].data == "base64data"
    assert converted[0].mimeType == "image/png"


def test_convert_result_fallback_wraps_as_json() -> None:
    """_convert_result wraps non-standard results as JSON text."""
    result: dict[str, Any] = {"status": "ok", "count": 42}
    converted = _convert_result(result)
    assert len(converted) == 1
    assert isinstance(converted[0], types.TextContent)
    assert '"status"' in converted[0].text
    assert '"count"' in converted[0].text


# ---------------------------------------------------------------------------
# Lifespan tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lifespan_initializes_and_shuts_down_resource_manager() -> None:
    """app_lifespan creates, initializes, and shuts down ResourceManager."""
    mock_rm = MagicMock()
    mock_rm.initialize = AsyncMock()
    mock_rm.shutdown = AsyncMock()

    with (
        patch("src.homelab_mcp.server.get_config") as mock_get_config,
        patch("src.homelab_mcp.server.ResourceManager", return_value=mock_rm) as mock_rm_cls,
    ):
        mock_get_config.return_value = MagicMock()

        async with app_lifespan(server) as ctx:
            assert "resource_manager" in ctx
            assert ctx["resource_manager"] is mock_rm
            mock_rm.initialize.assert_awaited_once()
            mock_rm.shutdown.assert_not_awaited()

        # After exiting the context, shutdown should have been called
        mock_rm.shutdown.assert_awaited_once()


@pytest.mark.asyncio
async def test_lifespan_sets_module_resource_manager() -> None:
    """app_lifespan sets the module-level _resource_manager during its scope."""
    from src.homelab_mcp.server import get_resource_manager

    mock_rm = MagicMock()
    mock_rm.initialize = AsyncMock()
    mock_rm.shutdown = AsyncMock()

    with (
        patch("src.homelab_mcp.server.get_config") as mock_get_config,
        patch("src.homelab_mcp.server.ResourceManager", return_value=mock_rm),
    ):
        mock_get_config.return_value = MagicMock()

        async with app_lifespan(server) as ctx:
            rm = get_resource_manager()
            assert rm is mock_rm

    # After lifespan ends, get_resource_manager should raise
    with pytest.raises(RuntimeError, match="not available"):
        get_resource_manager()


@pytest.mark.asyncio
async def test_lifespan_shuts_down_on_exception() -> None:
    """app_lifespan shuts down ResourceManager even if body raises."""
    mock_rm = MagicMock()
    mock_rm.initialize = AsyncMock()
    mock_rm.shutdown = AsyncMock()

    with (
        patch("src.homelab_mcp.server.get_config") as mock_get_config,
        patch("src.homelab_mcp.server.ResourceManager", return_value=mock_rm),
    ):
        mock_get_config.return_value = MagicMock()

        with pytest.raises(RuntimeError, match="test error"):
            async with app_lifespan(server) as ctx:
                raise RuntimeError("test error")

        mock_rm.shutdown.assert_awaited_once()


# ---------------------------------------------------------------------------
# Server instance tests
# ---------------------------------------------------------------------------


def test_server_name() -> None:
    """Server instance has the correct name."""
    assert server.name == "homelab-mcp"


def test_server_has_handlers_registered() -> None:
    """Server has list_tools and call_tool handlers registered."""
    assert types.ListToolsRequest in server.request_handlers
    assert types.CallToolRequest in server.request_handlers
