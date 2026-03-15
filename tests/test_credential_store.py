"""Tests for credential_store — headless-safe OS keyring wrapper (CRED-07)."""

from __future__ import annotations


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
