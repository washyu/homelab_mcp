"""Tests for MCP Resources protocol handlers in server.py.

Tests cover:
- list_resources returns all homelab:// URIs with correct metadata
- read_resource returns application/json stub content for known URIs
- read_resource raises McpError(-32002) for unknown URIs
- Server capabilities include non-None resources field
- subscribe/unsubscribe update the _subscriptions tracker
- Live dispatch to reader functions (Phase 9 Plan 02)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import mcp.types as types
import pytest
from mcp.shared.exceptions import McpError
from pydantic import AnyUrl
from pytest_mock import MockerFixture

from src.homelab_mcp.server import (
    HOMELAB_RESOURCES,
    RESOURCE_NOT_FOUND,
    _subscriptions,
    handle_list_resources,
    handle_read_resource,
    handle_subscribe_resource,
    handle_unsubscribe_resource,
    server,
)

# ---------------------------------------------------------------------------
# AnyUrl stringification sanity check (validates URI scheme format)
# ---------------------------------------------------------------------------


def test_anyurl_stringification() -> None:
    """str(AnyUrl('homelab://vms')) matches the key used in HOMELAB_RESOURCES.

    Resolves open question #2 from research: pydantic may stringify as
    'homelab:///vms' (triple slash). This test documents the actual behavior.
    """
    uri_str = str(AnyUrl("homelab://vms"))
    assert uri_str in HOMELAB_RESOURCES, (
        f"AnyUrl stringified to {uri_str!r}, but HOMELAB_RESOURCES keys are "
        f"{list(HOMELAB_RESOURCES.keys())!r}. Update dict keys to match."
    )


# ---------------------------------------------------------------------------
# list_resources tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_resources_returns_resources() -> None:
    """handle_list_resources() returns a list of types.Resource objects."""
    resources = await handle_list_resources()
    assert isinstance(resources, list)
    assert len(resources) == len(HOMELAB_RESOURCES)
    for resource in resources:
        assert isinstance(resource, types.Resource)


@pytest.mark.asyncio
async def test_list_resources_has_homelab_uris() -> None:
    """Every returned Resource.uri starts with 'homelab://'."""
    resources = await handle_list_resources()
    for resource in resources:
        assert str(resource.uri).startswith(
            "homelab://"
        ), f"Resource URI {resource.uri!r} does not start with 'homelab://'"


@pytest.mark.asyncio
async def test_list_resources_has_json_mimetype() -> None:
    """Every returned Resource has mimeType == 'application/json'."""
    resources = await handle_list_resources()
    for resource in resources:
        assert (
            resource.mimeType == "application/json"
        ), f"Resource {resource.uri!r} has mimeType {resource.mimeType!r}, expected 'application/json'"


# ---------------------------------------------------------------------------
# Server capabilities test
# ---------------------------------------------------------------------------


def test_capabilities_include_resources() -> None:
    """Server capabilities must advertise non-None resources field."""
    from mcp.server.lowlevel.server import NotificationOptions

    caps = server.get_capabilities(
        notification_options=NotificationOptions(),
        experimental_capabilities={},
    )
    assert caps.resources is not None, "Server capabilities.resources is None — list_resources handler not registered"


# ---------------------------------------------------------------------------
# read_resource tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_known_resource_returns_json() -> None:
    """handle_read_resource for a known URI returns ReadResourceContents with application/json."""
    from mcp.server.lowlevel.helper_types import ReadResourceContents

    result = await handle_read_resource(AnyUrl("homelab://vms"))
    assert isinstance(result, list)
    assert len(result) > 0
    for item in result:
        assert isinstance(item, ReadResourceContents)
        assert item.mime_type == "application/json"


@pytest.mark.asyncio
async def test_read_resource_content_is_valid_json() -> None:
    """Content string from read_resource parses as valid JSON."""
    result = await handle_read_resource(AnyUrl("homelab://vms"))
    assert len(result) > 0
    content = result[0].content
    parsed = json.loads(content)
    assert isinstance(parsed, dict)


@pytest.mark.asyncio
async def test_read_unknown_resource_raises_mcp_error() -> None:
    """handle_read_resource for unknown URI raises McpError with code -32002."""
    with pytest.raises(McpError) as exc_info:
        await handle_read_resource(AnyUrl("homelab://nonexistent"))
    assert exc_info.value.error.code == -32002


# ---------------------------------------------------------------------------
# subscribe/unsubscribe tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_adds_to_tracker() -> None:
    """After handle_subscribe_resource, URI is in _subscriptions."""
    _subscriptions.clear()
    await handle_subscribe_resource(AnyUrl("homelab://vms"))
    assert str(AnyUrl("homelab://vms")) in _subscriptions


@pytest.mark.asyncio
async def test_unsubscribe_removes_from_tracker() -> None:
    """After subscribe then unsubscribe, URI is no longer in _subscriptions."""
    _subscriptions.clear()
    await handle_subscribe_resource(AnyUrl("homelab://vms"))
    await handle_unsubscribe_resource(AnyUrl("homelab://vms"))
    assert str(AnyUrl("homelab://vms")) not in _subscriptions


@pytest.mark.asyncio
async def test_unsubscribe_nonexistent_no_error() -> None:
    """Unsubscribing a URI that was never subscribed does not raise."""
    _subscriptions.clear()
    # Should not raise
    await handle_unsubscribe_resource(AnyUrl("homelab://nonexistent"))


@pytest.mark.asyncio
async def test_subscribe_idempotent() -> None:
    """Subscribing same URI twice results in only one entry (_subscriptions is a set)."""
    _subscriptions.clear()
    await handle_subscribe_resource(AnyUrl("homelab://vms"))
    await handle_subscribe_resource(AnyUrl("homelab://vms"))
    uri_str = str(AnyUrl("homelab://vms"))
    matching = [s for s in _subscriptions if s == uri_str]
    assert len(matching) == 1


# ---------------------------------------------------------------------------
# Live dispatch tests (Phase 9 Plan 02)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_vms_resource_has_scanned_at(mocker: MockerFixture) -> None:
    """handle_read_resource dispatches to read_vms_resource and response includes scanned_at."""
    mocker.patch(
        "homelab_mcp.server.read_vms_resource",
        new=AsyncMock(return_value={"vms": [], "scanned_at": "2026-01-01T00:00:00+00:00", "total": 0}),
    )
    result = await handle_read_resource(AnyUrl("homelab://vms"))
    assert len(result) == 1
    assert result[0].mime_type == "application/json"
    data = json.loads(result[0].content)
    assert "scanned_at" in data


@pytest.mark.asyncio
async def test_read_devices_resource_has_scanned_at(mocker: MockerFixture) -> None:
    """handle_read_resource dispatches to read_devices_resource and response includes scanned_at."""
    mocker.patch(
        "homelab_mcp.server.read_devices_resource",
        new=AsyncMock(return_value={"devices": [], "scanned_at": "2026-01-01T00:00:00+00:00", "total": 0}),
    )
    result = await handle_read_resource(AnyUrl("homelab://devices"))
    assert len(result) == 1
    assert result[0].mime_type == "application/json"
    data = json.loads(result[0].content)
    assert "scanned_at" in data


@pytest.mark.asyncio
async def test_read_services_template_uri(mocker: MockerFixture) -> None:
    """handle_read_resource dispatches homelab://services/nginx to read_service_resource('nginx')."""
    mocker.patch(
        "homelab_mcp.server.read_service_resource",
        new=AsyncMock(
            return_value={
                "service": "nginx",
                "status": "running",
                "scanned_at": "2026-01-01T00:00:00+00:00",
            }
        ),
    )
    result = await handle_read_resource(AnyUrl("homelab://services/nginx"))
    assert len(result) == 1
    assert result[0].mime_type == "application/json"
    data = json.loads(result[0].content)
    assert "service" in data


@pytest.mark.asyncio
async def test_read_services_empty_name_error() -> None:
    """handle_read_resource for homelab://services/ (empty name) raises McpError -32002."""
    with pytest.raises(McpError) as exc_info:
        await handle_read_resource(AnyUrl("homelab://services/"))
    assert exc_info.value.error.code == RESOURCE_NOT_FOUND
