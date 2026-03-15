"""Tests for credentials CLI commands and --version flag (Phase 18 Wave 0 RED tests).

All homelab_mcp imports are local (inside function bodies) to avoid collection-level
ImportError — these functions do not exist yet.
"""

from __future__ import annotations

import argparse
import sys

import pytest

# ---------------------------------------------------------------------------
# --version flag and bare invocation
# ---------------------------------------------------------------------------


def test_version_flag(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """main(["--version"]) exits 0 and prints a version string containing 'homelab-mcp'."""
    monkeypatch.setattr(sys, "argv", ["homelab-mcp", "--version"])
    from homelab_mcp.server import main  # noqa: PLC0415

    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "homelab-mcp" in captured.out


def test_bare_invocation_starts_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bare homelab-mcp invocation schedules the stdio server coroutine via asyncio.run."""
    import asyncio  # noqa: PLC0415

    from homelab_mcp.server import main  # noqa: PLC0415

    monkeypatch.setattr(sys, "argv", ["homelab-mcp"])
    asyncio_run_called: list[object] = []
    monkeypatch.setattr(asyncio, "run", lambda coro: asyncio_run_called.append(coro))
    main()
    assert len(asyncio_run_called) == 1  # server coroutine was scheduled


# ---------------------------------------------------------------------------
# credentials add
# ---------------------------------------------------------------------------


def test_credentials_add_ssh(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """credentials add myhost myuser stores ssh credential and prints success message."""
    import getpass  # noqa: PLC0415

    from homelab_mcp.server import _cmd_credentials_add  # noqa: PLC0415

    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "pw123")
    monkeypatch.setattr(
        "homelab_mcp.server.store_credential",
        lambda hostname, username, password, credential_type="ssh": True,
    )
    monkeypatch.setattr(
        "homelab_mcp.server.register_credential",
        lambda hostname, username, credential_type="ssh": None,
    )
    args = argparse.Namespace(hostname="myhost", username="myuser", credential_type="ssh")
    _cmd_credentials_add(args)
    captured = capsys.readouterr()
    assert "Stored ssh credential for myuser@myhost" in captured.out


def test_credentials_add_uses_getpass(monkeypatch: pytest.MonkeyPatch) -> None:
    """credentials add prompts for password via getpass (not CLI arg)."""
    import getpass  # noqa: PLC0415

    from homelab_mcp.server import _cmd_credentials_add  # noqa: PLC0415

    getpass_called: list[str] = []
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": getpass_called.append(prompt) or "pw")
    monkeypatch.setattr(
        "homelab_mcp.server.store_credential",
        lambda hostname, username, password, credential_type="ssh": True,
    )
    monkeypatch.setattr(
        "homelab_mcp.server.register_credential",
        lambda hostname, username, credential_type="ssh": None,
    )
    args = argparse.Namespace(hostname="h", username="u", credential_type="ssh")
    _cmd_credentials_add(args)
    assert len(getpass_called) == 1  # getpass was called exactly once


def test_credentials_add_keyring_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """credentials add exits 1 with warning when store_credential returns False."""
    import getpass  # noqa: PLC0415

    from homelab_mcp.server import _cmd_credentials_add  # noqa: PLC0415

    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "pw")
    monkeypatch.setattr(
        "homelab_mcp.server.store_credential",
        lambda hostname, username, password, credential_type="ssh": False,
    )
    args = argparse.Namespace(hostname="h", username="u", credential_type="ssh")
    with pytest.raises(SystemExit) as exc_info:
        _cmd_credentials_add(args)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# credentials list
# ---------------------------------------------------------------------------


def test_credentials_list_ssh(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """credentials list prints user@host entries and no password."""
    from homelab_mcp.server import _cmd_credentials_list  # noqa: PLC0415

    monkeypatch.setattr(
        "homelab_mcp.server.list_credentials",
        lambda credential_type="ssh": [{"hostname": "h1", "username": "u1", "credential_type": "ssh"}],
    )
    args = argparse.Namespace(credential_type="ssh")
    _cmd_credentials_list(args)
    captured = capsys.readouterr()
    assert "u1@h1" in captured.out
    # Output must not contain any password-like value
    assert "password" not in captured.out.lower()


def test_credentials_list_empty(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """credentials list prints 'No stored ssh credentials.' when list is empty."""
    from homelab_mcp.server import _cmd_credentials_list  # noqa: PLC0415

    monkeypatch.setattr(
        "homelab_mcp.server.list_credentials",
        lambda credential_type="ssh": [],
    )
    args = argparse.Namespace(credential_type="ssh")
    _cmd_credentials_list(args)
    captured = capsys.readouterr()
    assert "No stored ssh credentials." in captured.out


# ---------------------------------------------------------------------------
# credentials remove
# ---------------------------------------------------------------------------


def test_credentials_remove_ssh(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """credentials remove h1 removes the credential and prints success."""
    from homelab_mcp.server import _cmd_credentials_remove  # noqa: PLC0415

    monkeypatch.setattr(
        "homelab_mcp.server.list_credentials",
        lambda credential_type="ssh": [{"hostname": "h1", "username": "u1", "credential_type": "ssh"}],
    )
    monkeypatch.setattr(
        "homelab_mcp.server.delete_credential",
        lambda hostname, username, credential_type="ssh": True,
    )
    monkeypatch.setattr(
        "homelab_mcp.server.unregister_credential",
        lambda hostname, credential_type="ssh": None,
    )
    args = argparse.Namespace(hostname="h1", credential_type="ssh")
    _cmd_credentials_remove(args)
    captured = capsys.readouterr()
    assert "Removed ssh credential for h1" in captured.out


def test_credentials_remove_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """credentials remove exits 1 when credential is not found."""
    from homelab_mcp.server import _cmd_credentials_remove  # noqa: PLC0415

    monkeypatch.setattr(
        "homelab_mcp.server.list_credentials",
        lambda credential_type="ssh": [],
    )
    args = argparse.Namespace(hostname="h1", credential_type="ssh")
    with pytest.raises(SystemExit) as exc_info:
        _cmd_credentials_remove(args)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Proxmox credential type
# ---------------------------------------------------------------------------


def test_credentials_add_proxmox(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """credentials add --type proxmox stores proxmox credential and prints success."""
    import getpass  # noqa: PLC0415

    from homelab_mcp.server import _cmd_credentials_add  # noqa: PLC0415

    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "pw")
    monkeypatch.setattr(
        "homelab_mcp.server.store_credential",
        lambda hostname, username, password, credential_type="ssh": True,
    )
    monkeypatch.setattr(
        "homelab_mcp.server.register_credential",
        lambda hostname, username, credential_type="ssh": None,
    )
    args = argparse.Namespace(hostname="pxhost", username="pxuser", credential_type="proxmox")
    _cmd_credentials_add(args)
    captured = capsys.readouterr()
    assert "Stored proxmox credential for pxuser@pxhost" in captured.out


def test_credentials_list_proxmox(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """credentials list --type proxmox prints proxmox entries."""
    from homelab_mcp.server import _cmd_credentials_list  # noqa: PLC0415

    monkeypatch.setattr(
        "homelab_mcp.server.list_credentials",
        lambda credential_type="ssh": [{"hostname": "px1", "username": "admin", "credential_type": "proxmox"}],
    )
    args = argparse.Namespace(credential_type="proxmox")
    _cmd_credentials_list(args)
    captured = capsys.readouterr()
    assert "admin@px1" in captured.out


def test_credentials_remove_proxmox(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """credentials remove --type proxmox removes the proxmox credential."""
    from homelab_mcp.server import _cmd_credentials_remove  # noqa: PLC0415

    monkeypatch.setattr(
        "homelab_mcp.server.list_credentials",
        lambda credential_type="ssh": [{"hostname": "px1", "username": "admin", "credential_type": "proxmox"}],
    )
    monkeypatch.setattr(
        "homelab_mcp.server.delete_credential",
        lambda hostname, username, credential_type="ssh": True,
    )
    monkeypatch.setattr(
        "homelab_mcp.server.unregister_credential",
        lambda hostname, credential_type="ssh": None,
    )
    args = argparse.Namespace(hostname="px1", credential_type="proxmox")
    _cmd_credentials_remove(args)
    captured = capsys.readouterr()
    assert "Removed proxmox credential for px1" in captured.out
