"""Tests for credential_store — headless-safe OS keyring wrapper (CRED-07)."""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest
    import pytest_mock


def test_store_credential_success(mocker):
    """store_credential returns True when keyring.set_password succeeds."""
    from homelab_mcp.credential_store import store_credential

    mocker.patch("keyring.set_password", return_value=None)
    result = store_credential("192.168.1.1", "root", "secret")
    assert result is True


def test_store_credential_headless_no_keyring_error(mocker):
    """store_credential returns False (not raises) when NoKeyringError occurs."""
    import keyring.errors

    from homelab_mcp.credential_store import store_credential

    mocker.patch("keyring.set_password", side_effect=keyring.errors.NoKeyringError())
    result = store_credential("192.168.1.1", "root", "secret")
    assert result is False


def test_store_credential_headless_runtime_error(mocker):
    """store_credential returns False (not raises) when RuntimeError occurs."""
    from homelab_mcp.credential_store import store_credential

    mocker.patch("keyring.set_password", side_effect=RuntimeError("dbus not available"))
    result = store_credential("192.168.1.1", "root", "secret")
    assert result is False


def test_get_credential_success(mocker):
    """get_credential returns the password string when keyring.get_password succeeds."""
    from homelab_mcp.credential_store import get_credential

    mocker.patch("keyring.get_password", return_value="secret")
    result = get_credential("192.168.1.1", "root")
    assert result == "secret"


def test_get_credential_headless_no_keyring_error(mocker):
    """get_credential returns None (not raises) when NoKeyringError occurs."""
    import keyring.errors

    from homelab_mcp.credential_store import get_credential

    mocker.patch("keyring.get_password", side_effect=keyring.errors.NoKeyringError())
    result = get_credential("192.168.1.1", "root")
    assert result is None


def test_get_credential_headless_runtime_error(mocker):
    """get_credential returns None (not raises) when RuntimeError occurs."""
    from homelab_mcp.credential_store import get_credential

    mocker.patch("keyring.get_password", side_effect=RuntimeError("dbus not available"))
    result = get_credential("192.168.1.1", "root")
    assert result is None


def test_delete_credential_not_found(mocker):
    """delete_credential returns False (not raises) when PasswordDeleteError occurs."""
    import keyring.errors

    from homelab_mcp.credential_store import delete_credential

    mocker.patch("keyring.delete_password", side_effect=keyring.errors.PasswordDeleteError())
    result = delete_credential("192.168.1.1", "root")
    assert result is False


def test_no_module_level_keyring_import():
    """credential_store.py must not import keyring at module level."""
    import ast
    import pathlib

    cs_path = pathlib.Path("src/homelab_mcp/credential_store.py")
    if not cs_path.exists():
        import pytest

        pytest.skip("credential_store.py does not exist yet — RED phase")

    tree = ast.parse(cs_path.read_text())
    module_level_imports = [
        node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) and node.col_offset == 0
    ]
    keyring_imports = [
        node
        for node in module_level_imports
        if (isinstance(node, ast.Import) and any(alias.name == "keyring" for alias in node.names))
        or (isinstance(node, ast.ImportFrom) and node.module is not None and node.module.startswith("keyring"))
    ]
    assert keyring_imports == [], (
        f"Found module-level keyring import(s) in credential_store.py: {[ast.dump(n) for n in keyring_imports]}"
    )


def test_keyring_in_core_dependencies():
    """pyproject.toml must list keyring in [project.dependencies], not only in optional-dependencies."""
    import pathlib

    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    pyproject_path = pathlib.Path("pyproject.toml")
    data = tomllib.loads(pyproject_path.read_text())

    core_deps = data.get("project", {}).get("dependencies", [])
    has_keyring_in_core = any("keyring" in dep for dep in core_deps)
    assert has_keyring_in_core, f"keyring not found in [project.dependencies]. Core deps: {core_deps}"


# ---------------------------------------------------------------------------
# Phase 18 — Wave 0 RED tests: registry functions + credential_type parameter
# ---------------------------------------------------------------------------


def test_register_and_list(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """register_credential + list_credentials returns the registered entry."""
    monkeypatch.setattr("homelab_mcp.credential_store._REGISTRY_PATH", tmp_path / "registry.json")
    from homelab_mcp.credential_store import list_credentials, register_credential  # noqa: PLC0415

    register_credential("host1", "user1", credential_type="ssh")
    entries = list_credentials(credential_type="ssh")
    assert entries == [{"hostname": "host1", "username": "user1", "credential_type": "ssh"}]


def test_unregister_removes_entry(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """unregister_credential removes the entry; subsequent list_credentials returns []."""
    monkeypatch.setattr("homelab_mcp.credential_store._REGISTRY_PATH", tmp_path / "registry.json")
    from homelab_mcp.credential_store import (  # noqa: PLC0415
        list_credentials,
        register_credential,
        unregister_credential,
    )

    register_credential("host1", "user1", credential_type="ssh")
    unregister_credential("host1", credential_type="ssh")
    entries = list_credentials(credential_type="ssh")
    assert entries == []


def test_list_credentials_no_file(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """list_credentials returns [] when registry file does not exist."""
    missing_path = tmp_path / "nonexistent_registry.json"
    monkeypatch.setattr("homelab_mcp.credential_store._REGISTRY_PATH", missing_path)
    from homelab_mcp.credential_store import list_credentials  # noqa: PLC0415

    entries = list_credentials("ssh")
    assert entries == []


def test_store_proxmox_uses_proxmox_service_name(mocker: pytest_mock.MockerFixture) -> None:
    """store_credential with credential_type='proxmox' calls keyring with 'homelab-mcp-proxmox'."""
    mock_set = mocker.patch("keyring.set_password", return_value=None)
    from homelab_mcp.credential_store import store_credential  # noqa: PLC0415

    store_credential("host", "user", "pw", credential_type="proxmox")
    mock_set.assert_called_once()
    call_args = mock_set.call_args
    assert call_args[0][0] == "homelab-mcp-proxmox", (
        f"Expected service name 'homelab-mcp-proxmox', got '{call_args[0][0]}'"
    )


def test_register_upsert(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Registering the same (hostname, username, type) twice results in exactly one entry."""
    monkeypatch.setattr("homelab_mcp.credential_store._REGISTRY_PATH", tmp_path / "registry.json")
    from homelab_mcp.credential_store import list_credentials, register_credential  # noqa: PLC0415

    register_credential("host1", "user1", credential_type="ssh")
    register_credential("host1", "user1", credential_type="ssh")
    entries = list_credentials(credential_type="ssh")
    assert len(entries) == 1


def test_list_filters_by_type(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """list_credentials('ssh') returns only ssh entries, not proxmox ones."""
    monkeypatch.setattr("homelab_mcp.credential_store._REGISTRY_PATH", tmp_path / "registry.json")
    from homelab_mcp.credential_store import list_credentials, register_credential  # noqa: PLC0415

    register_credential("ssh-host", "ssh-user", credential_type="ssh")
    register_credential("px-host", "px-user", credential_type="proxmox")
    ssh_entries = list_credentials(credential_type="ssh")
    assert ssh_entries == [{"hostname": "ssh-host", "username": "ssh-user", "credential_type": "ssh"}]
    proxmox_entries = list_credentials(credential_type="proxmox")
    assert proxmox_entries == [{"hostname": "px-host", "username": "px-user", "credential_type": "proxmox"}]
