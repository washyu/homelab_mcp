"""Tests verifying sanitize_error is wired into error response paths (SEC-04).

These tests ensure that production modules use sanitize_error(e) instead
of raw str(e) in error response dicts returned to MCP clients.  Logger
calls are excluded because the root-logger CredentialFilter already
handles redaction there.
"""

from __future__ import annotations

import inspect
import re


def _count_raw_str_e_in_responses(source: str) -> int:
    """Count str(e) occurrences that appear in error response contexts.

    Excludes str(e) in logger.* calls (covered by CredentialFilter)
    and control-flow uses like ``"Authentication failed" in str(e)``.
    """
    count = 0
    for line in source.splitlines():
        stripped = line.strip()
        # Skip logger calls -- CredentialFilter covers these
        if re.match(r"logger\.\w+\(", stripped):
            continue
        # Skip control-flow checks like 'in str(e)'
        if "in str(e)" in stripped:
            continue
        # Count str(e) in remaining lines (error response dicts / f-strings)
        if "str(e)" in stripped:
            count += 1
    return count


def test_proxmox_api_uses_sanitize_error() -> None:
    """proxmox_api.py must import and use sanitize_error in error responses."""
    from homelab_mcp import proxmox_api

    source = inspect.getsource(proxmox_api)
    assert "sanitize_error" in source, "sanitize_error not found in proxmox_api"
    assert (
        _count_raw_str_e_in_responses(source) == 0
    ), "Raw str(e) found in error response dicts in proxmox_api"


def test_vm_operations_uses_sanitize_error() -> None:
    """vm_operations.py must import and use sanitize_error in error responses."""
    from homelab_mcp import vm_operations

    source = inspect.getsource(vm_operations)
    assert "sanitize_error" in source, "sanitize_error not found in vm_operations"
    assert (
        _count_raw_str_e_in_responses(source) == 0
    ), "Raw str(e) found in error response dicts in vm_operations"


def test_infrastructure_crud_uses_sanitize_error() -> None:
    """infrastructure_crud.py must import and use sanitize_error in error responses."""
    from homelab_mcp import infrastructure_crud

    source = inspect.getsource(infrastructure_crud)
    assert "sanitize_error" in source, "sanitize_error not found in infrastructure_crud"
    assert (
        _count_raw_str_e_in_responses(source) == 0
    ), "Raw str(e) found in error response dicts in infrastructure_crud"


def test_ssh_tools_uses_sanitize_error() -> None:
    """ssh_tools.py must import and use sanitize_error in error responses."""
    from homelab_mcp import ssh_tools

    source = inspect.getsource(ssh_tools)
    assert "sanitize_error" in source, "sanitize_error not found in ssh_tools"
    assert (
        _count_raw_str_e_in_responses(source) == 0
    ), "Raw str(e) found in error response dicts in ssh_tools"


def test_service_installer_uses_sanitize_error() -> None:
    """service_installer.py must import and use sanitize_error in error responses."""
    from homelab_mcp import service_installer

    source = inspect.getsource(service_installer)
    assert "sanitize_error" in source, "sanitize_error not found in service_installer"
    assert (
        _count_raw_str_e_in_responses(source) == 0
    ), "Raw str(e) found in error response dicts in service_installer"


def test_sitemap_uses_sanitize_error() -> None:
    """sitemap.py must import and use sanitize_error in error responses."""
    from homelab_mcp import sitemap

    source = inspect.getsource(sitemap)
    assert "sanitize_error" in source, "sanitize_error not found in sitemap"
    assert (
        _count_raw_str_e_in_responses(source) == 0
    ), "Raw str(e) found in error response dicts in sitemap"


def test_proxmox_scripts_uses_sanitize_error() -> None:
    """proxmox_scripts.py must import and use sanitize_error in error responses."""
    from homelab_mcp import proxmox_scripts

    source = inspect.getsource(proxmox_scripts)
    assert "sanitize_error" in source, "sanitize_error not found in proxmox_scripts"
    # proxmox_scripts has str(e) only in logger calls, which is fine
    assert (
        _count_raw_str_e_in_responses(source) == 0
    ), "Raw str(e) found in error response dicts in proxmox_scripts"
