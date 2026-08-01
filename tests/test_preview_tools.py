"""Tests for *_preview tool variants (Phase 15 — PREV-01 through PREV-08).

Wave 0 stubs: tests are RED at commit, GREEN after Plan 02 implementation.
All imports are local to avoid collection-level ImportError.
"""

from __future__ import annotations

import pytest

# Phase 33 (D-21): remove_server + remove_server_preview deleted from the tool surface.
_PREVIEW_TOOLS = [
    "decommission_device_preview",
    "delete_proxmox_vm_preview",
    "remove_vm_preview",
    "destroy_terraform_service_preview",
    "rollback_infrastructure_changes_preview",
]

_DESTRUCTIVE_TOOLS = [
    "decommission_device",
    "delete_proxmox_vm",
    "remove_vm",
    "destroy_terraform_service",
    "rollback_infrastructure_changes",
]


def test_decommission_device_preview_in_schema_registry() -> None:
    """PREV-01: decommission_device_preview is registered in the tool schema registry."""
    from homelab_mcp.tool_schemas import get_all_tool_schemas

    schemas = get_all_tool_schemas()
    assert "decommission_device_preview" in schemas


def test_delete_proxmox_vm_preview_in_schema_registry() -> None:
    """PREV-02: delete_proxmox_vm_preview is registered in the tool schema registry."""
    from homelab_mcp.tool_schemas import get_all_tool_schemas

    schemas = get_all_tool_schemas()
    assert "delete_proxmox_vm_preview" in schemas


def test_remove_vm_preview_in_schema_registry() -> None:
    """PREV-03: remove_vm_preview is registered in the tool schema registry."""
    from homelab_mcp.tool_schemas import get_all_tool_schemas

    schemas = get_all_tool_schemas()
    assert "remove_vm_preview" in schemas


# test_remove_server_preview_in_schema_registry REMOVED in Phase 33 (D-21).
# remove_server + remove_server_preview deleted; replacement is CLI `credentials remove`.


def test_destroy_terraform_service_preview_in_schema_registry() -> None:
    """PREV-05: destroy_terraform_service_preview is registered in the tool schema registry."""
    from homelab_mcp.tool_schemas import get_all_tool_schemas

    schemas = get_all_tool_schemas()
    assert "destroy_terraform_service_preview" in schemas


def test_rollback_infrastructure_changes_preview_in_schema_registry() -> None:
    """PREV-06: rollback_infrastructure_changes_preview is registered in the tool schema registry."""
    from homelab_mcp.tool_schemas import get_all_tool_schemas

    schemas = get_all_tool_schemas()
    assert "rollback_infrastructure_changes_preview" in schemas


def test_preview_tools_have_readonly_annotation() -> None:
    """PREV-07: All preview tools have readOnlyHint=True and destructiveHint=False."""
    from homelab_mcp.tool_annotations import TOOL_ANNOTATIONS

    for name in _PREVIEW_TOOLS:
        assert name in TOOL_ANNOTATIONS, f"Missing annotation for {name}"
        assert TOOL_ANNOTATIONS[name].read_only_hint is True, f"{name}: expected readOnlyHint=True"
        assert TOOL_ANNOTATIONS[name].destructive_hint is False, f"{name}: expected destructiveHint=False"


def test_original_destructive_tools_still_present() -> None:
    """PREV-08 (GREEN immediately): Original destructive tools are in registry with dry_run param."""
    from homelab_mcp.tool_schemas import get_all_tool_schemas

    schemas = get_all_tool_schemas()
    for name in _DESTRUCTIVE_TOOLS:
        assert name in schemas, f"Original tool {name!r} missing from registry"
        props = schemas[name]["inputSchema"]["properties"]
        assert "dry_run" in props, f"Original tool {name!r} is missing 'dry_run' param in inputSchema.properties"


def test_preview_tool_schema_has_no_dry_run_param() -> None:
    """PREV-08: Preview tool schemas do NOT include a dry_run parameter."""
    from homelab_mcp.tool_schemas import get_all_tool_schemas

    schemas = get_all_tool_schemas()
    for name in _PREVIEW_TOOLS:
        if name not in schemas:
            pytest.skip(f"Schema for {name!r} not yet added — skipping until Plan 02")
        props = schemas[name]["inputSchema"]["properties"]
        assert "dry_run" not in props, f"Preview tool {name!r} should NOT have 'dry_run' in inputSchema.properties"
