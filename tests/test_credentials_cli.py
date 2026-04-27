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
        lambda hostname, username, credential_type="ssh", auth_type="password": None,
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
        lambda hostname, username, credential_type="ssh", auth_type="password": None,
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
        lambda hostname, username, credential_type="ssh", auth_type="password": None,
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


def test_help_output_includes_credentials(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """--help output must mention credentials subcommand so users can discover it."""
    import sys  # noqa: PLC0415

    from homelab_mcp.server import main  # noqa: PLC0415

    monkeypatch.setattr(sys, "argv", ["homelab-mcp", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    combined = capsys.readouterr().out + capsys.readouterr().err
    assert "credentials" in combined, "Expected 'credentials' in --help output"


# ---------------------------------------------------------------------------
# Phase 34 — cluster-scoped credential CLI tests (D-06, D-07, D-08, D-08a)
# ---------------------------------------------------------------------------


def test_credentials_add_cluster_scope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test 1 (D-06): add --scope cluster:<name> calls store/register with cluster kwargs, prints success."""
    import getpass  # noqa: PLC0415

    from homelab_mcp.server import _cmd_credentials_add  # noqa: PLC0415

    store_calls: list[dict[str, object]] = []
    register_calls: list[dict[str, object]] = []

    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "secret_uuid")
    monkeypatch.setattr(
        "homelab_mcp.server.store_credential",
        lambda hostname, username, password, credential_type="ssh", *, scope="node", cluster_name="": (
            store_calls.append(
                {
                    "hostname": hostname,
                    "username": username,
                    "password": password,
                    "credential_type": credential_type,
                    "scope": scope,
                    "cluster_name": cluster_name,
                }
            )
            or True
        ),
    )
    monkeypatch.setattr(
        "homelab_mcp.server.register_credential",
        lambda hostname, username, credential_type="ssh", auth_type="password", *, scope="node", cluster_name="": (
            register_calls.append(
                {
                    "hostname": hostname,
                    "username": username,
                    "credential_type": credential_type,
                    "auth_type": auth_type,
                    "scope": scope,
                    "cluster_name": cluster_name,
                }
            )
        ),
    )

    args = argparse.Namespace(
        hostname=None,
        username="root@pam!tok",
        credential_type="proxmox",
        scope="cluster:homelab-prod",
        key_path=None,
    )
    _cmd_credentials_add(args)

    captured = capsys.readouterr()
    # store_credential called with cluster kwargs
    assert len(store_calls) == 1
    assert store_calls[0]["hostname"] == ""
    assert store_calls[0]["scope"] == "cluster"
    assert store_calls[0]["cluster_name"] == "homelab-prod"
    assert store_calls[0]["username"] == "root@pam!tok"
    # register_credential called with cluster kwargs
    assert len(register_calls) == 1
    assert register_calls[0]["scope"] == "cluster"
    assert register_calls[0]["cluster_name"] == "homelab-prod"
    # stdout references cluster address form
    assert "cluster:homelab-prod" in captured.out


def test_credentials_add_proxmox_per_node_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test 2 (SC-5): add --type proxmox <hostname> <username> (no --scope) behaves as before."""
    import getpass  # noqa: PLC0415

    from homelab_mcp.server import _cmd_credentials_add  # noqa: PLC0415

    store_calls: list[dict[str, object]] = []

    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "pw")
    monkeypatch.setattr(
        "homelab_mcp.server.store_credential",
        lambda hostname, username, password, credential_type="ssh", *, scope="node", cluster_name="": (
            store_calls.append({"hostname": hostname, "scope": scope, "cluster_name": cluster_name}) or True
        ),
    )
    monkeypatch.setattr(
        "homelab_mcp.server.register_credential",
        lambda hostname, username, credential_type="ssh", auth_type="password", *, scope="node", cluster_name="": None,
    )

    args = argparse.Namespace(
        hostname="pve1.home",
        username="root@pam!tok",
        credential_type="proxmox",
        scope=None,
        key_path=None,
    )
    _cmd_credentials_add(args)

    captured = capsys.readouterr()
    # per-node path: hostname used, scope stays "node"
    assert len(store_calls) == 1
    assert store_calls[0]["hostname"] == "pve1.home"
    assert store_calls[0]["scope"] == "node"
    assert store_calls[0]["cluster_name"] == ""
    assert "pve1.home" in captured.out


def test_credentials_add_rejects_hostname_with_cluster_scope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test 3 (D-06): hostname positional must not be provided when --scope cluster:<name> is used."""
    import getpass  # noqa: PLC0415

    from homelab_mcp.server import _cmd_credentials_add  # noqa: PLC0415

    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "pw")

    args = argparse.Namespace(
        hostname="pve1.home",
        username="root@pam!tok",
        credential_type="proxmox",
        scope="cluster:homelab-prod",
        key_path=None,
    )
    with pytest.raises(SystemExit) as exc_info:
        _cmd_credentials_add(args)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "hostname" in captured.err.lower() or "must not be provided" in captured.err


def test_credentials_add_rejects_empty_cluster_name(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test 4 (D-06): --scope cluster: with empty name after colon exits 1."""
    import getpass  # noqa: PLC0415

    from homelab_mcp.server import _cmd_credentials_add  # noqa: PLC0415

    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "pw")

    args = argparse.Namespace(
        hostname=None,
        username="root@pam!tok",
        credential_type="proxmox",
        scope="cluster:",
        key_path=None,
    )
    with pytest.raises(SystemExit) as exc_info:
        _cmd_credentials_add(args)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "cluster_name" in captured.err or "cluster name" in captured.err.lower()


def test_credentials_add_rejects_cluster_scope_with_ssh_type(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test 5 (D-06): --scope cluster:<name> with --type ssh exits 1."""
    import getpass  # noqa: PLC0415

    from homelab_mcp.server import _cmd_credentials_add  # noqa: PLC0415

    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "pw")

    args = argparse.Namespace(
        hostname=None,
        username="admin",
        credential_type="ssh",
        scope="cluster:homelab-prod",
        key_path=None,
    )
    with pytest.raises(SystemExit) as exc_info:
        _cmd_credentials_add(args)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "--scope cluster" in captured.err
    assert "--type proxmox" in captured.err or "proxmox" in captured.err


def test_credentials_remove_cluster_scope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test 6 (D-07): remove --scope cluster:<name> deletes cluster entry and prints success."""
    from homelab_mcp.server import _cmd_credentials_remove  # noqa: PLC0415

    delete_calls: list[dict[str, object]] = []
    unregister_cluster_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "homelab_mcp.server.list_credentials",
        lambda credential_type="ssh": [
            {
                "hostname": "",
                "username": "root@pam!tok",
                "credential_type": "proxmox",
                "scope": "cluster",
                "cluster_name": "homelab-prod",
            }
        ],
    )
    monkeypatch.setattr(
        "homelab_mcp.server.delete_credential",
        lambda hostname, username, credential_type="ssh", *, scope="node", cluster_name="": (
            delete_calls.append(
                {
                    "hostname": hostname,
                    "username": username,
                    "credential_type": credential_type,
                    "scope": scope,
                    "cluster_name": cluster_name,
                }
            )
            or True
        ),
    )
    monkeypatch.setattr(
        "homelab_mcp.server.unregister_cluster_credential",
        lambda cluster_name, credential_type="proxmox": (
            unregister_cluster_calls.append({"cluster_name": cluster_name, "credential_type": credential_type})
        ),
    )

    args = argparse.Namespace(hostname=None, credential_type="proxmox", scope="cluster:homelab-prod")
    _cmd_credentials_remove(args)

    captured = capsys.readouterr()
    assert len(delete_calls) == 1
    assert delete_calls[0]["scope"] == "cluster"
    assert delete_calls[0]["cluster_name"] == "homelab-prod"
    assert len(unregister_cluster_calls) == 1
    assert unregister_cluster_calls[0]["cluster_name"] == "homelab-prod"
    assert "cluster:homelab-prod" in captured.out


def test_credentials_remove_per_node_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test 7 (SC-5): remove <hostname> --type proxmox without --scope behaves as before."""
    from homelab_mcp.server import _cmd_credentials_remove  # noqa: PLC0415

    delete_calls: list[dict[str, object]] = []
    unregister_calls: list[str] = []

    monkeypatch.setattr(
        "homelab_mcp.server.list_credentials",
        lambda credential_type="ssh": [
            {
                "hostname": "pve1.home",
                "username": "root@pam!tok",
                "credential_type": "proxmox",
                "scope": "node",
                "cluster_name": "",
            },
        ],
    )
    monkeypatch.setattr(
        "homelab_mcp.server.delete_credential",
        lambda hostname, username, credential_type="ssh", *, scope="node", cluster_name="": (
            delete_calls.append({"hostname": hostname, "username": username}) or True
        ),
    )
    monkeypatch.setattr(
        "homelab_mcp.server.unregister_credential",
        lambda hostname, credential_type="ssh": unregister_calls.append(hostname),
    )

    args = argparse.Namespace(hostname="pve1.home", credential_type="proxmox", scope=None)
    _cmd_credentials_remove(args)

    captured = capsys.readouterr()
    assert len(delete_calls) == 1
    assert delete_calls[0]["hostname"] == "pve1.home"
    assert "pve1.home" in captured.out
    assert len(unregister_calls) == 1
    assert unregister_calls[0] == "pve1.home"


def test_credentials_list_groups_per_node_and_cluster_sections(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test 8 (D-08): list renders Per-node and Cluster-scoped sections when both exist."""
    from homelab_mcp.server import _cmd_credentials_list  # noqa: PLC0415

    monkeypatch.setattr(
        "homelab_mcp.server.list_credentials",
        lambda credential_type="ssh": [
            {
                "hostname": "pve1.home",
                "username": "root@pam!tok1",
                "credential_type": "proxmox",
                "scope": "node",
                "cluster_name": "",
            },
            {
                "hostname": "",
                "username": "root@pam!cluster_tok",
                "credential_type": "proxmox",
                "scope": "cluster",
                "cluster_name": "homelab-prod",
            },
        ],
    )

    args = argparse.Namespace(credential_type="proxmox")
    _cmd_credentials_list(args)

    captured = capsys.readouterr()
    assert "Per-node:" in captured.out
    assert "Cluster-scoped:" in captured.out
    assert "root@pam!tok1@pve1.home" in captured.out
    assert "root@pam!cluster_tok@cluster:homelab-prod" in captured.out


def test_credentials_list_single_section_when_only_one_scope_has_entries(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test 9 (D-08): when only cluster entries exist, only Cluster-scoped section renders."""
    from homelab_mcp.server import _cmd_credentials_list  # noqa: PLC0415

    monkeypatch.setattr(
        "homelab_mcp.server.list_credentials",
        lambda credential_type="ssh": [
            {
                "hostname": "",
                "username": "root@pam!cluster_tok",
                "credential_type": "proxmox",
                "scope": "cluster",
                "cluster_name": "homelab-prod",
            },
        ],
    )

    args = argparse.Namespace(credential_type="proxmox")
    _cmd_credentials_list(args)

    captured = capsys.readouterr()
    assert "Per-node:" not in captured.out
    assert "Cluster-scoped:" in captured.out
    assert "root@pam!cluster_tok@cluster:homelab-prod" in captured.out


# ---------------------------------------------------------------------------
# Phase 38.1 — Wave 0 RED tests: auto-bind, link/unlink, list --json, remove nulls (R4, R8, R9, D-23)
# ---------------------------------------------------------------------------


class TestAutoBind:
    """Phase 38.1 R4 / D-01 / D-05 / D-06 / D-07: auto-bind side effects on credentials add."""

    def test_zero_match_silent_d01_phase381(
        self,
        tmp_path: "pytest.TempPathFactory",
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """D-01: no matching sitemap row → credential stored, no error/warning, exit 0."""
        import getpass  # noqa: PLC0415

        from homelab_mcp.server import _cmd_credentials_add  # noqa: PLC0415

        monkeypatch.setattr(getpass, "getpass", lambda prompt="": "secret123")
        monkeypatch.setattr(
            "homelab_mcp.server.store_credential",
            lambda hostname, username, password, credential_type="ssh", **kw: True,
        )
        monkeypatch.setattr(
            "homelab_mcp.server.register_credential",
            lambda hostname, username, credential_type="ssh", **kw: "fake-uuid-zero-match",
        )
        # Sitemap returns no matching rows — auto-bind silently skips
        monkeypatch.setattr(
            "homelab_mcp.server.get_sitemap_rows_for_hostname",
            lambda hostname: [],
        )

        args = argparse.Namespace(
            hostname="pve-not-in-sitemap",
            username="root",
            credential_type="proxmox",
            scope="node",
            key_path=None,
        )
        _cmd_credentials_add(args)

        captured = capsys.readouterr()
        # Credential is stored — success message present
        assert "Stored proxmox credential" in captured.out
        # Zero-match D-01: no "auto-bind" warning emitted
        assert "auto-bind" not in captured.out.lower()
        assert "no sitemap" not in captured.err.lower()

    def test_single_match_no_existing_binding_binds_phase381(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Single matching sitemap row with NULL binding → auto-bind sets proxmox_credential_id."""
        import getpass  # noqa: PLC0415

        from homelab_mcp.server import _cmd_credentials_add  # noqa: PLC0415

        bind_calls: list[dict[str, object]] = []
        monkeypatch.setattr(getpass, "getpass", lambda prompt="": "secret")
        monkeypatch.setattr(
            "homelab_mcp.server.store_credential",
            lambda hostname, username, password, credential_type="ssh", **kw: True,
        )
        monkeypatch.setattr(
            "homelab_mcp.server.register_credential",
            lambda hostname, username, credential_type="ssh", **kw: "auto-uuid-001",
        )
        monkeypatch.setattr(
            "homelab_mcp.server.get_sitemap_rows_for_hostname",
            lambda hostname: [{"hostname": "pve1", "proxmox_credential_id": None}],
        )
        monkeypatch.setattr(
            "homelab_mcp.server.set_device_credential_binding",
            lambda hostname, credential_type, credential_id: bind_calls.append(
                {"hostname": hostname, "credential_type": credential_type, "credential_id": credential_id}
            ),
        )

        args = argparse.Namespace(
            hostname="pve1",
            username="root",
            credential_type="proxmox",
            scope="node",
            key_path=None,
        )
        _cmd_credentials_add(args)

        # Phase 38.1 R4: set_device_credential_binding must have been called
        assert len(bind_calls) == 1, (
            f"Phase 38.1 R4: expected 1 auto-bind call, got {len(bind_calls)}"
        )
        assert bind_calls[0]["credential_id"] == "auto-uuid-001"
        assert bind_calls[0]["credential_type"] == "proxmox"

    def test_non_tty_skips_overwrite_per_d05_phase381(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """D-05: non-TTY + existing binding → skip auto-bind, print warning, exit 0."""
        import getpass  # noqa: PLC0415

        from homelab_mcp.server import _cmd_credentials_add  # noqa: PLC0415

        bind_calls: list[object] = []
        monkeypatch.setattr(getpass, "getpass", lambda prompt="": "secret")
        monkeypatch.setattr(
            "homelab_mcp.server.store_credential",
            lambda hostname, username, password, credential_type="ssh", **kw: True,
        )
        monkeypatch.setattr(
            "homelab_mcp.server.register_credential",
            lambda hostname, username, credential_type="ssh", **kw: "new-uuid-d05",
        )
        # Row has existing binding
        monkeypatch.setattr(
            "homelab_mcp.server.get_sitemap_rows_for_hostname",
            lambda hostname: [{"hostname": "pve1", "proxmox_credential_id": "old-uuid-d05"}],
        )
        monkeypatch.setattr(
            "homelab_mcp.server.set_device_credential_binding",
            lambda hostname, credential_type, credential_id: bind_calls.append(credential_id),
        )
        # Simulate non-TTY
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        args = argparse.Namespace(
            hostname="pve1",
            username="root",
            credential_type="proxmox",
            scope="node",
            key_path=None,
        )
        _cmd_credentials_add(args)

        captured = capsys.readouterr()
        # D-05: binding skipped in non-TTY
        assert len(bind_calls) == 0, (
            f"Phase 38.1 D-05: binding must be skipped in non-TTY, but got {len(bind_calls)} calls"
        )
        # Warning emitted
        assert "skip" in captured.err.lower() or "warn" in captured.err.lower() or "non-interactive" in captured.err.lower(), (
            "Phase 38.1 D-05: expected a warning on stderr when skipping overwrite in non-TTY"
        )

    def test_cluster_scope_skips_auto_bind_per_d07_phase381(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """D-07: cluster-scope add skips auto-bind entirely."""
        import getpass  # noqa: PLC0415

        from homelab_mcp.server import _cmd_credentials_add  # noqa: PLC0415

        bind_calls: list[object] = []
        monkeypatch.setattr(getpass, "getpass", lambda prompt="": "secret")
        monkeypatch.setattr(
            "homelab_mcp.server.store_credential",
            lambda hostname, username, password, credential_type="ssh", **kw: True,
        )
        monkeypatch.setattr(
            "homelab_mcp.server.register_credential",
            lambda hostname, username, credential_type="ssh", **kw: "cluster-uuid-d07",
        )
        monkeypatch.setattr(
            "homelab_mcp.server.set_device_credential_binding",
            lambda hostname, credential_type, credential_id: bind_calls.append(credential_id),
        )

        args = argparse.Namespace(
            hostname=None,
            username="root@pam!tok",
            credential_type="proxmox",
            scope="cluster:homelab-prod",
            key_path=None,
        )
        _cmd_credentials_add(args)

        # D-07: cluster-scope → no auto-bind
        assert len(bind_calls) == 0, (
            f"Phase 38.1 D-07: cluster-scope add must not auto-bind, got {len(bind_calls)} calls"
        )

    def test_multi_match_non_tty_skips_per_d06_phase381(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """D-06: multi-match sitemap rows + non-TTY → skip auto-bind, print warning."""
        import getpass  # noqa: PLC0415

        from homelab_mcp.server import _cmd_credentials_add  # noqa: PLC0415

        bind_calls: list[object] = []
        monkeypatch.setattr(getpass, "getpass", lambda prompt="": "secret")
        monkeypatch.setattr(
            "homelab_mcp.server.store_credential",
            lambda hostname, username, password, credential_type="ssh", **kw: True,
        )
        monkeypatch.setattr(
            "homelab_mcp.server.register_credential",
            lambda hostname, username, credential_type="ssh", **kw: "multi-uuid-d06",
        )
        # Multiple matching rows — ambiguous
        monkeypatch.setattr(
            "homelab_mcp.server.get_sitemap_rows_for_hostname",
            lambda hostname: [
                {"hostname": "pve1", "proxmox_credential_id": None},
                {"hostname": "192.168.10.20", "proxmox_credential_id": None},
            ],
        )
        monkeypatch.setattr(
            "homelab_mcp.server.set_device_credential_binding",
            lambda hostname, credential_type, credential_id: bind_calls.append(credential_id),
        )
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        args = argparse.Namespace(
            hostname="192.168.10.20",
            username="root",
            credential_type="proxmox",
            scope="node",
            key_path=None,
        )
        _cmd_credentials_add(args)

        captured = capsys.readouterr()
        # D-06: multi-match + non-TTY → no bind
        assert len(bind_calls) == 0, (
            f"Phase 38.1 D-06: multi-match non-TTY must not auto-bind, got {len(bind_calls)} calls"
        )
        assert "warn" in captured.err.lower() or "skip" in captured.err.lower() or "multiple" in captured.err.lower(), (
            "Phase 38.1 D-06: expected warning on stderr for multi-match non-TTY"
        )


class TestLinkUnlink:
    """Phase 38.1 R8: credentials link/unlink CLI commands."""

    def test_link_sets_binding_phase381(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """link <hostname> <uuid> --type proxmox sets the proxmox_credential_id."""
        from homelab_mcp.server import _cmd_credentials_link  # noqa: PLC0415

        bind_calls: list[dict[str, object]] = []
        monkeypatch.setattr(
            "homelab_mcp.server.find_credential_by_id",
            lambda cred_id: {
                "credential_id": cred_id,
                "hostname": "192.168.10.20",
                "credential_type": "proxmox",
            },
        )
        monkeypatch.setattr(
            "homelab_mcp.server.get_sitemap_rows_for_hostname",
            lambda hostname: [{"hostname": "pve1", "proxmox_credential_id": None}],
        )
        monkeypatch.setattr(
            "homelab_mcp.server.set_device_credential_binding",
            lambda hostname, credential_type, credential_id: bind_calls.append(
                {"hostname": hostname, "credential_type": credential_type, "credential_id": credential_id}
            ),
        )

        args = argparse.Namespace(
            hostname="pve1",
            credential_id="test-uuid-link",
            credential_type="proxmox",
        )
        _cmd_credentials_link(args)

        assert len(bind_calls) == 1, (
            f"Phase 38.1 R8: expected 1 bind call from link, got {len(bind_calls)}"
        )
        assert bind_calls[0]["credential_id"] == "test-uuid-link"

    def test_link_rejects_type_mismatch_per_d25_phase381(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """D-25: link rejects credential whose type doesn't match --type."""
        from homelab_mcp.server import _cmd_credentials_link  # noqa: PLC0415

        monkeypatch.setattr(
            "homelab_mcp.server.find_credential_by_id",
            lambda cred_id: {
                "credential_id": cred_id,
                "hostname": "host1",
                "credential_type": "ssh",  # type mismatch: requesting --type proxmox
            },
        )
        monkeypatch.setattr(
            "homelab_mcp.server.get_sitemap_rows_for_hostname",
            lambda hostname: [{"hostname": "host1"}],
        )

        args = argparse.Namespace(
            hostname="host1",
            credential_id="ssh-uuid-d25",
            credential_type="proxmox",  # mismatch
        )

        with pytest.raises(SystemExit) as exc_info:
            _cmd_credentials_link(args)

        captured = capsys.readouterr()
        assert exc_info.value.code != 0
        combined = captured.out + captured.err
        assert "ssh" in combined.lower() or "mismatch" in combined.lower() or "type" in combined.lower(), (
            f"Phase 38.1 D-25: expected type-mismatch error message, got: {combined!r}"
        )

    def test_link_errors_on_unknown_hostname_phase381(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """link errors with actionable message when hostname not in sitemap."""
        from homelab_mcp.server import _cmd_credentials_link  # noqa: PLC0415

        monkeypatch.setattr(
            "homelab_mcp.server.find_credential_by_id",
            lambda cred_id: {"credential_id": cred_id, "hostname": "unknown", "credential_type": "proxmox"},
        )
        monkeypatch.setattr(
            "homelab_mcp.server.get_sitemap_rows_for_hostname",
            lambda hostname: [],  # no match
        )

        args = argparse.Namespace(
            hostname="does-not-exist",
            credential_id="some-uuid",
            credential_type="proxmox",
        )

        with pytest.raises(SystemExit) as exc_info:
            _cmd_credentials_link(args)

        assert exc_info.value.code != 0

    def test_link_errors_on_unknown_uuid_phase381(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """link errors with actionable message when UUID not in registry."""
        from homelab_mcp.server import _cmd_credentials_link  # noqa: PLC0415

        monkeypatch.setattr(
            "homelab_mcp.server.find_credential_by_id",
            lambda cred_id: None,  # UUID not in registry
        )
        monkeypatch.setattr(
            "homelab_mcp.server.get_sitemap_rows_for_hostname",
            lambda hostname: [{"hostname": "pve1"}],
        )

        args = argparse.Namespace(
            hostname="pve1",
            credential_id="00000000-0000-4000-8000-000000000000",
            credential_type="proxmox",
        )

        with pytest.raises(SystemExit) as exc_info:
            _cmd_credentials_link(args)

        assert exc_info.value.code != 0

    def test_unlink_nulls_binding_phase381(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """unlink <hostname> --type proxmox nulls proxmox_credential_id."""
        from homelab_mcp.server import _cmd_credentials_unlink  # noqa: PLC0415

        bind_calls: list[dict[str, object]] = []
        monkeypatch.setattr(
            "homelab_mcp.server.get_sitemap_rows_for_hostname",
            lambda hostname: [{"hostname": "pve1", "proxmox_credential_id": "existing-uuid"}],
        )
        monkeypatch.setattr(
            "homelab_mcp.server.set_device_credential_binding",
            lambda hostname, credential_type, credential_id: bind_calls.append(
                {"hostname": hostname, "credential_type": credential_type, "credential_id": credential_id}
            ),
        )

        args = argparse.Namespace(hostname="pve1", credential_type="proxmox")
        _cmd_credentials_unlink(args)

        assert len(bind_calls) == 1
        assert bind_calls[0]["credential_id"] is None, (
            f"Phase 38.1 R8: unlink must set credential_id=None, got {bind_calls[0]['credential_id']!r}"
        )


def test_remove_nulls_bindings_phase381(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """credentials remove nulls sitemap binding that pointed at the removed UUID (R9 / D-26)."""
    from homelab_mcp.server import _cmd_credentials_remove  # noqa: PLC0415

    removed_uuid = "dead-uuid-9999"
    null_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "homelab_mcp.server.list_credentials",
        lambda credential_type="ssh": [
            {
                "hostname": "pve1",
                "username": "root",
                "credential_type": "proxmox",
                "credential_id": removed_uuid,
            }
        ],
    )
    monkeypatch.setattr(
        "homelab_mcp.server.delete_credential",
        lambda hostname, username, credential_type="ssh": True,
    )
    monkeypatch.setattr(
        "homelab_mcp.server.unregister_credential",
        lambda hostname, credential_type="ssh": None,
    )
    # R9: remove must null any sitemap binding pointing at removed_uuid
    monkeypatch.setattr(
        "homelab_mcp.server.null_bindings_for_credential_id",
        lambda credential_id, credential_type: null_calls.append(
            {"credential_id": credential_id, "credential_type": credential_type}
        ),
    )

    args = argparse.Namespace(hostname="pve1", credential_type="proxmox")
    _cmd_credentials_remove(args)

    assert len(null_calls) == 1, (
        f"Phase 38.1 R9: credentials remove must null sitemap bindings, got {len(null_calls)} calls"
    )
    assert null_calls[0]["credential_id"] == removed_uuid


def test_list_json_emits_credential_ids_phase381(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """credentials list --json includes credential_id per D-23."""
    import json  # noqa: PLC0415

    from homelab_mcp.server import _cmd_credentials_list  # noqa: PLC0415

    test_uuid = "11111111-1111-4111-8111-111111111111"
    monkeypatch.setattr(
        "homelab_mcp.server.list_credentials",
        lambda credential_type="ssh": [
            {
                "hostname": "pve1",
                "username": "root",
                "credential_type": "proxmox",
                "credential_id": test_uuid,
            }
        ],
    )

    args = argparse.Namespace(credential_type="proxmox", json=True)
    _cmd_credentials_list(args)

    captured = capsys.readouterr()
    # D-23: --json output must include credential_id
    try:
        output = json.loads(captured.out)
    except json.JSONDecodeError:
        output = []
    assert isinstance(output, list), f"Phase 38.1 D-23: expected JSON array, got: {captured.out!r}"
    assert len(output) == 1
    assert output[0].get("credential_id") == test_uuid, (
        f"Phase 38.1 D-23: credential_id missing from --json output: {output[0]}"
    )


def test_list_default_tabular_omits_credential_id_phase381(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """credentials list (tabular default) does NOT include credential_id per D-23."""
    from homelab_mcp.server import _cmd_credentials_list  # noqa: PLC0415

    test_uuid = "22222222-2222-4222-8222-222222222222"
    monkeypatch.setattr(
        "homelab_mcp.server.list_credentials",
        lambda credential_type="ssh": [
            {
                "hostname": "pve2",
                "username": "root",
                "credential_type": "proxmox",
                "credential_id": test_uuid,
            }
        ],
    )

    args = argparse.Namespace(credential_type="proxmox", json=False)
    _cmd_credentials_list(args)

    captured = capsys.readouterr()
    # D-23: tabular output must NOT expose UUIDs to users
    assert test_uuid not in captured.out, (
        f"Phase 38.1 D-23: tabular output must omit credential_id, but UUID was present in output"
    )
