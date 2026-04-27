"""Phase 38.1 Wave 5 (Plan 09): integration round-trip GREEN.

Pins the SPEC §Acceptance Criteria headline: `credentials add` → `discover_and_map`
→ `scan_drift` produces `counts['probed_ok'] >= 1` regardless of identifier form
(IP, short hostname, FQDN) or order (add-first vs discover-first).

Test architecture (per Plan 09 design):
  * SQLiteAdapter on tmp_path (no on-disk pollution)
  * keyring monkeypatched to an in-memory dict
  * credential_store._REGISTRY_PATH redirected to tmp_path
  * migration._MIGRATION_STATE_PATH pre-stamped so the destructive Phase 38.1
    R10 migration does NOT fire mid-test (the fresh tmp_path DB is already on
    the new schema thanks to ``init_schema``)
  * Proxmox API resolver + client patched at the drift_detection module level —
    fakes assert that ``credential_id`` is threaded through (Tier-0 short-circuit
    verification, T-38.1-09-02 mitigation)
  * Sitemap rows inserted directly via the typed adapter to simulate a successful
    ``discover_and_map`` (W4: Test 5 drives the actual ``_cmd_credentials_add``
    handler so the auto-bind side-effect is exercised end-to-end)

Tests 1-4: drive the binding flow via the ``_auto_bind_credential`` helper
directly — small surface, fast feedback for IP / short / FQDN / order
permutations.

Test 5 (W4): drives the real ``_cmd_credentials_add`` handler via an
``argparse.Namespace`` so a regression that drops ``_auto_bind_credential``
from the handler trips a test (Tests 1-4 would all still pass).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.integration


# ──────────────────────────────────────────────────────────────────────────
# Shared setup helper
# ──────────────────────────────────────────────────────────────────────────


def _setup_isolated_environment(tmp_path: Any, monkeypatch: Any) -> Any:
    """Create an isolated SQLiteAdapter + redirect keyring/registry/migration to tmp_path.

    Returns the connected adapter (caller owns close()).
    """
    # ── Registry + migration state isolation ─────────────────────────────
    # Patch BOTH module aliases (homelab_mcp.X and src.homelab_mcp.X) since
    # they resolve to separate module objects in sys.modules even though they
    # back the same .py file. The production code imports via src.homelab_mcp,
    # so that namespace is the binding-relevant one; patching homelab_mcp.X
    # too keeps any consumer that happens to import via the package-name
    # alias on the same isolated path.
    registry_path = tmp_path / "credential_registry.json"
    migration_state_path = tmp_path / "migration_state.json"
    monkeypatch.setattr("src.homelab_mcp.credential_store._REGISTRY_PATH", registry_path)
    monkeypatch.setattr("homelab_mcp.credential_store._REGISTRY_PATH", registry_path)
    monkeypatch.setattr("src.homelab_mcp.migration._MIGRATION_STATE_PATH", migration_state_path)
    monkeypatch.setattr("homelab_mcp.migration._MIGRATION_STATE_PATH", migration_state_path)
    # Pre-stamp the Phase 38.1 R10 migration as already-applied so it does not
    # fire mid-test on the freshly-initialised tmp_path DB. Without this stamp
    # the migration would attempt to backup the registry + drop the freshly-
    # created devices table (idempotency check fires only AFTER the first run).
    migration_state_path.write_text(json.dumps({"phase_38_1_credential_binding_applied": True}))

    # ── Keyring monkeypatch (W3 fix from Plan 09 plan) ───────────────────
    # store_credential / get_credential lazy-import keyring INSIDE the function
    # body (credential_store.py:58-70). Monkeypatching the module-level
    # ``keyring.set_password`` / ``keyring.get_password`` reaches the lazy
    # import successfully.
    keyring_store: dict[str, str] = {}

    def _set_password(svc: str, user: str, pw: str) -> None:
        keyring_store[f"{svc}:{user}"] = pw

    def _get_password(svc: str, user: str) -> str | None:
        return keyring_store.get(f"{svc}:{user}")

    def _delete_password(svc: str, user: str) -> None:
        keyring_store.pop(f"{svc}:{user}", None)

    monkeypatch.setattr("keyring.set_password", _set_password)
    monkeypatch.setattr("keyring.get_password", _get_password)
    monkeypatch.setattr("keyring.delete_password", _delete_password)

    # ── Sitemap DB on tmp_path SQLite ────────────────────────────────────
    from src.homelab_mcp.database import SQLiteAdapter  # noqa: PLC0415

    db_path = str(tmp_path / "sitemap.db")
    adapter = SQLiteAdapter(db_path)
    adapter.connect()
    adapter.init_schema()

    # ── Server-module wrappers must operate on the test's adapter ───────
    # The wrappers (get_sitemap_rows_for_hostname, set_device_credential_binding,
    # null_bindings_for_credential_id) lazy-import NetworkSiteMap inside the
    # function body (server.py:532, :550, :574) and instantiate it without
    # arguments, which would land on the user's home-directory DB. Replace
    # the wrappers with thin lambdas that route to the test adapter directly.
    def _get_rows(hostname: str) -> list[dict[str, Any]]:
        return adapter.find_devices_by_hostname_or_ip(hostname)

    def _set_binding(hostname: str, credential_type: str, credential_id: str | None) -> None:
        matches = adapter.find_devices_by_hostname_or_ip(hostname)
        matches = [r for r in matches if r["hostname"] == hostname]
        if not matches:
            raise ValueError(f"No sitemap row found for hostname {hostname!r}")
        if len(matches) > 1:
            raise ValueError(f"Multiple sitemap rows match hostname {hostname!r}")
        adapter.set_device_credential_binding(matches[0]["id"], credential_type, credential_id)

    def _null_bindings(credential_id: str, credential_type: str) -> list[str]:
        if not credential_id:
            return []
        return adapter.bulk_null_credential_binding([credential_id], credential_type)

    # Patch the wrapper seams in BOTH module namespaces. The production module
    # is loaded under src.homelab_mcp.server (since `from src.homelab_mcp...`
    # is the import path), but the homelab_mcp.server alias is also a valid
    # importable module — patch both so behaviour is predictable regardless
    # of import path.
    for module_path in ("src.homelab_mcp.server", "homelab_mcp.server"):
        monkeypatch.setattr(f"{module_path}.get_sitemap_rows_for_hostname", _get_rows)
        monkeypatch.setattr(f"{module_path}.set_device_credential_binding", _set_binding)
        monkeypatch.setattr(f"{module_path}.null_bindings_for_credential_id", _null_bindings)

    return adapter


def _insert_device_row(adapter: Any, hostname: str, connection_ip: str) -> None:
    """Insert a sitemap row simulating a successful discover_and_map."""
    adapter.execute_query(
        "INSERT INTO devices (hostname, connection_ip, last_seen, status) VALUES (?, ?, ?, ?)",
        (hostname, connection_ip, datetime.now().isoformat(), "success"),
    )


def _make_proxmox_mocks(expected_credential_id: str) -> tuple[Any, Any]:
    """Return (fake_get_proxmox_client, fake_resolve) that assert credential_id is threaded.

    These fakes implement T-38.1-09-02 mitigation: drift's call into the resolver
    MUST pass the binding UUID via ``credential_id=`` so the Tier-0 short-circuit
    fires. If a regression drops the kwarg, ``fake_get_proxmox_client`` raises
    AssertionError with a clear message.
    """
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=[{"type": "cluster", "name": "homelab", "version": 13}])

    async def fake_get_proxmox_client(
        host: str | None = None,
        *,
        session: Any = None,
        credential_id: str | None = None,
        **_kwargs: Any,
    ) -> Any:
        assert credential_id == expected_credential_id, (
            f"drift must pass binding UUID via credential_id=; got "
            f"credential_id={credential_id!r} (expected {expected_credential_id!r})"
        )
        return fake_client

    async def fake_resolve(
        host: str,
        *,
        session: Any = None,
        credential_id: str | None = None,
    ) -> tuple[str, str, str | None]:
        # Phase 38.1 R6: cache-hit second call also passes the binding through.
        # Same Tier-0 verification as get_proxmox_client.
        assert credential_id == expected_credential_id, (
            f"drift cache-hit resolve must pass credential_id=; got {credential_id!r}"
        )
        return ("root@pam!tok=fake-secret-token", "node", None)

    return fake_get_proxmox_client, fake_resolve


# ──────────────────────────────────────────────────────────────────────────
# Test 1: Add-first happy path with IP identifier
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_then_discover_then_drift_succeeds_with_ip_phase381(tmp_path: Any, monkeypatch: Any) -> None:
    """SPEC §Acceptance: register by IP → discover_and_map → scan_drift sees probed_ok >= 1."""
    adapter = _setup_isolated_environment(tmp_path, monkeypatch)
    try:
        # ── Step 1: credentials add (per-node, IP identifier) ─────────────
        from src.homelab_mcp.credential_store import (  # noqa: PLC0415
            register_credential,
            store_credential,
        )

        store_credential(
            "192.168.10.20",
            "root@pam!tok",
            "fake-secret-token",
            credential_type="proxmox",
        )
        new_uuid = register_credential(
            "192.168.10.20",
            "root@pam!tok",
            credential_type="proxmox",
            auth_type="password",
        )
        assert new_uuid, "Plan 02 prerequisite: register_credential must return UUID"

        # ── Step 2: discover_and_map simulation ───────────────────────────
        # Insert the row (post-discover_and_map shape) and run the auto-bind
        # helper directly. The auto-bind helper is what _cmd_credentials_add
        # invokes; calling it here mirrors the side-effect that would have run
        # if step 1 had been driven by the CLI handler. (Test 5 exercises the
        # full handler flow; Tests 1-4 keep the surface narrow.)
        _insert_device_row(adapter, "192.168.10.20", "192.168.10.20")

        from src.homelab_mcp.server import _auto_bind_credential  # noqa: PLC0415

        _auto_bind_credential(
            hostname="192.168.10.20",
            credential_type="proxmox",
            new_credential_id=new_uuid,
        )

        # Verify the binding landed (R4 acceptance)
        rows = adapter.find_devices_by_hostname_or_ip("192.168.10.20")
        assert len(rows) == 1
        assert rows[0]["proxmox_credential_id"] == new_uuid, (
            "Plan 07 R4 acceptance: auto-bind must write proxmox_credential_id "
            f"on the matching sitemap row; got {rows[0]['proxmox_credential_id']!r}"
        )

        # ── Step 3: scan_drift with mocked Proxmox API ────────────────────
        fake_client_factory, fake_resolve = _make_proxmox_mocks(new_uuid)

        with (
            patch(
                "src.homelab_mcp.drift_detection.get_proxmox_client",
                side_effect=fake_client_factory,
            ),
            patch(
                "src.homelab_mcp.drift_detection.resolve_proxmox_credentials",
                side_effect=fake_resolve,
            ),
        ):
            from src.homelab_mcp.drift_detection import scan_drift  # noqa: PLC0415

            result = await scan_drift(session=None, db_adapter=adapter)

        # ── Assertions ────────────────────────────────────────────────────
        assert result["status"] == "success"
        assert result["counts"]["probed_ok"] >= 1, (
            f"SPEC headline acceptance: counts.probed_ok must be >= 1; got counts={result['counts']!r}"
        )
        # T-38.1-09-01 mitigation: verify hostname matches AND not_eligible == 0,
        # so the test cannot accidentally pass on a stale row.
        assert result["probed_ok"][0]["hostname"] == "192.168.10.20"
        assert result["counts"]["not_eligible"] == 0, (
            f"Bound row must NOT land in not_eligible; got not_eligible bucket: {result['not_eligible']!r}"
        )
    finally:
        adapter.close()


# ──────────────────────────────────────────────────────────────────────────
# Test 2: Identifier-form independence — short hostname
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_then_discover_then_drift_succeeds_with_short_hostname_phase381(
    tmp_path: Any, monkeypatch: Any
) -> None:
    """Identifier-form independence: register by short hostname round-trips."""
    adapter = _setup_isolated_environment(tmp_path, monkeypatch)
    try:
        from src.homelab_mcp.credential_store import (  # noqa: PLC0415
            register_credential,
            store_credential,
        )

        store_credential("pve", "root@pam!tok", "fake-secret-token", credential_type="proxmox")
        new_uuid = register_credential(
            "pve",
            "root@pam!tok",
            credential_type="proxmox",
            auth_type="password",
        )

        # Sitemap row hostname = "pve" (matches the registered identifier so
        # the auto-bind hostname-OR-connection_ip clause finds it). The IP-vs-
        # short-hostname divergence is realistic: discover_and_map(192.168.10.20)
        # would store hostname="pve" + connection_ip="192.168.10.20".
        _insert_device_row(adapter, "pve", "192.168.10.20")

        from src.homelab_mcp.server import _auto_bind_credential  # noqa: PLC0415

        _auto_bind_credential(
            hostname="pve",
            credential_type="proxmox",
            new_credential_id=new_uuid,
        )

        rows = adapter.find_devices_by_hostname_or_ip("pve")
        assert len(rows) == 1
        assert rows[0]["proxmox_credential_id"] == new_uuid

        fake_client_factory, fake_resolve = _make_proxmox_mocks(new_uuid)
        with (
            patch(
                "src.homelab_mcp.drift_detection.get_proxmox_client",
                side_effect=fake_client_factory,
            ),
            patch(
                "src.homelab_mcp.drift_detection.resolve_proxmox_credentials",
                side_effect=fake_resolve,
            ),
        ):
            from src.homelab_mcp.drift_detection import scan_drift  # noqa: PLC0415

            result = await scan_drift(session=None, db_adapter=adapter)

        assert result["counts"]["probed_ok"] >= 1, (
            f"Phase 38.1 SPEC: short-hostname round-trip must produce probed_ok >= 1; got {result['counts']!r}"
        )
        assert result["probed_ok"][0]["hostname"] == "pve"
        assert result["counts"]["not_eligible"] == 0
    finally:
        adapter.close()


# ──────────────────────────────────────────────────────────────────────────
# Test 3: Identifier-form independence — FQDN
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_then_discover_then_drift_succeeds_with_fqdn_phase381(tmp_path: Any, monkeypatch: Any) -> None:
    """Identifier-form independence: register by FQDN round-trips."""
    adapter = _setup_isolated_environment(tmp_path, monkeypatch)
    try:
        from src.homelab_mcp.credential_store import (  # noqa: PLC0415
            register_credential,
            store_credential,
        )

        store_credential(
            "pve.home.lab",
            "root@pam!tok",
            "fake-secret-token",
            credential_type="proxmox",
        )
        new_uuid = register_credential(
            "pve.home.lab",
            "root@pam!tok",
            credential_type="proxmox",
            auth_type="password",
        )

        _insert_device_row(adapter, "pve.home.lab", "192.168.10.20")

        from src.homelab_mcp.server import _auto_bind_credential  # noqa: PLC0415

        _auto_bind_credential(
            hostname="pve.home.lab",
            credential_type="proxmox",
            new_credential_id=new_uuid,
        )

        rows = adapter.find_devices_by_hostname_or_ip("pve.home.lab")
        assert len(rows) == 1
        assert rows[0]["proxmox_credential_id"] == new_uuid

        fake_client_factory, fake_resolve = _make_proxmox_mocks(new_uuid)
        with (
            patch(
                "src.homelab_mcp.drift_detection.get_proxmox_client",
                side_effect=fake_client_factory,
            ),
            patch(
                "src.homelab_mcp.drift_detection.resolve_proxmox_credentials",
                side_effect=fake_resolve,
            ),
        ):
            from src.homelab_mcp.drift_detection import scan_drift  # noqa: PLC0415

            result = await scan_drift(session=None, db_adapter=adapter)

        assert result["counts"]["probed_ok"] >= 1, (
            f"Phase 38.1 SPEC: FQDN round-trip must produce probed_ok >= 1; got {result['counts']!r}"
        )
        assert result["probed_ok"][0]["hostname"] == "pve.home.lab"
        assert result["counts"]["not_eligible"] == 0
    finally:
        adapter.close()


# ──────────────────────────────────────────────────────────────────────────
# Test 4: Order independence — discover_first_then_add
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discover_first_then_add_phase381(tmp_path: Any, monkeypatch: Any) -> None:
    """Order independence: discover_and_map first, credentials add second, still GREEN."""
    adapter = _setup_isolated_environment(tmp_path, monkeypatch)
    try:
        # ── Step 1 (reversed): row exists FIRST (simulating prior discover) ─
        _insert_device_row(adapter, "192.168.10.20", "192.168.10.20")

        # ── Step 2 (reversed): credentials add fires AFTER ───────────────
        from src.homelab_mcp.credential_store import (  # noqa: PLC0415
            register_credential,
            store_credential,
        )

        store_credential(
            "192.168.10.20",
            "root@pam!tok",
            "fake-secret-token",
            credential_type="proxmox",
        )
        new_uuid = register_credential(
            "192.168.10.20",
            "root@pam!tok",
            credential_type="proxmox",
            auth_type="password",
        )

        from src.homelab_mcp.server import _auto_bind_credential  # noqa: PLC0415

        _auto_bind_credential(
            hostname="192.168.10.20",
            credential_type="proxmox",
            new_credential_id=new_uuid,
        )

        # Auto-bind on the post-discover row populates the binding
        rows = adapter.find_devices_by_hostname_or_ip("192.168.10.20")
        assert len(rows) == 1
        assert rows[0]["proxmox_credential_id"] == new_uuid, (
            "Order independence: auto-bind must find the pre-existing row from discover_and_map and write the binding"
        )

        # ── Step 3: drift sees the host ───────────────────────────────────
        fake_client_factory, fake_resolve = _make_proxmox_mocks(new_uuid)
        with (
            patch(
                "src.homelab_mcp.drift_detection.get_proxmox_client",
                side_effect=fake_client_factory,
            ),
            patch(
                "src.homelab_mcp.drift_detection.resolve_proxmox_credentials",
                side_effect=fake_resolve,
            ),
        ):
            from src.homelab_mcp.drift_detection import scan_drift  # noqa: PLC0415

            result = await scan_drift(session=None, db_adapter=adapter)

        assert result["counts"]["probed_ok"] >= 1, (
            f"Phase 38.1 SPEC: discover-first/add-second round-trip must "
            f"produce probed_ok >= 1; got {result['counts']!r}"
        )
        assert result["counts"]["not_eligible"] == 0
    finally:
        adapter.close()


# ──────────────────────────────────────────────────────────────────────────
# Test 5 (W4): CLI-handler-driven round-trip
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_round_trip_via_cli_handler_phase381(tmp_path: Any, monkeypatch: Any) -> None:
    """W4: drive the real ``_cmd_credentials_add`` handler via argparse.Namespace.

    The other four tests bypass the handler and call ``_auto_bind_credential``
    directly. That misses a regression class: if ``_cmd_credentials_add`` ever
    stops invoking ``_auto_bind_credential`` (refactor mistake, accidental
    early return, etc.), Tests 1-4 still pass because they bypass the handler.

    This test exercises the REAL wiring by calling ``_cmd_credentials_add(ns)``
    with a constructed ``argparse.Namespace`` — same code path as the CLI.
    """
    adapter = _setup_isolated_environment(tmp_path, monkeypatch)
    try:
        # Insert sitemap row FIRST so auto-bind has something to match.
        _insert_device_row(adapter, "192.168.10.20", "192.168.10.20")

        # Simulate stdin secret entry for getpass.getpass.
        monkeypatch.setattr("getpass.getpass", lambda prompt="": "fake-secret-token")
        # Simulate non-TTY so the auto-bind D-04 prompt does NOT fire (and the
        # D-05 non-TTY skip path is also OK because no existing binding is
        # present on the freshly-inserted row).
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        # Build the Namespace _cmd_credentials_add expects. Field names taken
        # from server.py:1170-1206 (add_p.add_argument(...)). The actual
        # argparse dest names are: hostname, username, credential_type,
        # key_path, scope.
        ns = argparse.Namespace(
            hostname="192.168.10.20",
            username="root@pam!tok",
            credential_type="proxmox",
            key_path=None,
            scope=None,
        )

        from src.homelab_mcp.server import _cmd_credentials_add  # noqa: PLC0415

        _cmd_credentials_add(ns)

        # W4 acceptance: verify auto-bind side-effect actually fired by querying
        # the binding via the typed adapter method (Plan 03 / Blocker B2).
        rows = adapter.find_devices_by_hostname_or_ip("192.168.10.20")
        assert len(rows) == 1
        assert rows[0]["proxmox_credential_id"] is not None, (
            "W4 regression guard: _cmd_credentials_add MUST invoke "
            "_auto_bind_credential so that the sitemap row's "
            "proxmox_credential_id is non-null after add."
        )

        bound_uuid = rows[0]["proxmox_credential_id"]

        # Drift then succeeds (same Proxmox API mock pattern as Test 1)
        fake_client_factory, fake_resolve = _make_proxmox_mocks(bound_uuid)
        with (
            patch(
                "src.homelab_mcp.drift_detection.get_proxmox_client",
                side_effect=fake_client_factory,
            ),
            patch(
                "src.homelab_mcp.drift_detection.resolve_proxmox_credentials",
                side_effect=fake_resolve,
            ),
        ):
            from src.homelab_mcp.drift_detection import scan_drift  # noqa: PLC0415

            result = await scan_drift(session=None, db_adapter=adapter)

        assert result["counts"]["probed_ok"] >= 1, (
            f"W4: handler-driven round-trip must produce probed_ok >= 1; got {result['counts']!r}"
        )
        assert result["probed_ok"][0]["hostname"] == "192.168.10.20"
        assert result["counts"]["not_eligible"] == 0
    finally:
        adapter.close()
