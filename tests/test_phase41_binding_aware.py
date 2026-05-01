"""Phase 41 — Bug AA / BB / V regression tests.

RED in Wave 0 (xfail strict), flips GREEN when Plans 02-04 land.
A regression that drops a fix re-fails the test.
"""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homelab_mcp.error_handling import ssh_connection_wrapper
from homelab_mcp.sitemap import NetworkSiteMap, discover_and_store

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sitemap():
    """In-memory SQLite sitemap for tests that touch real DB rows."""
    return NetworkSiteMap(db_path=":memory:", db_type="sqlite")


def _seed_row(
    sitemap: NetworkSiteMap,
    hostname: str,
    connection_ip: str = "",
    ssh_credential_id: str | None = None,
    proxmox_credential_id: str | None = None,
    status: str = "success",
) -> int:
    """Insert a device row directly into the sitemap's SQLite database.

    Returns the inserted row's id.  Mirrors the seed helper pattern used
    in ``tests/test_sitemap.py`` — we insert via the db_adapter's
    ``store_device`` method so the schema is guaranteed consistent.
    """
    from homelab_mcp.sitemap import NetworkDevice

    device = NetworkDevice(
        hostname=hostname,
        connection_ip=connection_ip,
        last_seen=datetime.now().isoformat(),
        status=status,
    )
    device_id = sitemap.store_device(device)
    # Wire the binding columns separately (store_device doesn't write them).
    if ssh_credential_id is not None:
        sitemap.db_adapter.set_device_credential_binding(device_id, "ssh", ssh_credential_id)
    if proxmox_credential_id is not None:
        sitemap.db_adapter.set_device_credential_binding(device_id, "proxmox", proxmox_credential_id)
    return device_id


# ---------------------------------------------------------------------------
# Task 1 — six functional RED tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discover_and_map_uses_row_binding_when_row_exists(sitemap):
    """Bug AA: discover_and_store passes ssh_credential_id from the sitemap
    row to resolve_ssh_credentials via the credential_id= keyword.

    Pre-seed a row with ssh_credential_id="uuid-abc" for hostname="pve".
    Assert the resolver is called with credential_id="uuid-abc".
    Plan 03 fix: resolve_ssh_for_sitemap_row passes the row's credential_id.
    """
    _seed_row(sitemap, hostname="pve", connection_ip="192.168.10.20", ssh_credential_id="uuid-abc")

    # Phase 41 Plan 03: fake_creds must carry a non-None password/key_path so
    # the inner resolve_ssh_credentials call inside ssh_discover_system takes
    # the Tier-1 short-circuit (password supplied) instead of falling to Tier-2
    # registry-scan.  Without this, ssh_discover_system raises ValueError
    # ("No credentials found") before ssh_connect is called.
    fake_creds = SimpleNamespace(
        hostname="192.168.10.20",
        username="root",
        port=22,
        password="fake-password",
        key_path=None,
    )

    with (
        patch(
            "homelab_mcp.ssh_tools.resolve_ssh_credentials",
            return_value=fake_creds,
        ) as mock_resolver,
        patch(
            "homelab_mcp.ssh_tools.ssh_connect",
            new_callable=AsyncMock,
        ) as mock_connect,
    ):
        # Make ssh_connect return an async context manager
        cm = MagicMock()
        conn = MagicMock()
        conn.run = AsyncMock(return_value=MagicMock(exit_status=1, stdout=""))
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_connect.return_value = cm

        await discover_and_store(sitemap, hostname="pve")

    assert mock_resolver.called, "resolve_ssh_credentials was never called"
    # Phase 41 Plan 03: check the FIRST call to the resolver (from
    # resolve_ssh_for_sitemap_row) carries credential_id="uuid-abc".
    # A second call may occur inside ssh_discover_system (Tier-1 short-circuit
    # since fake_creds.password is non-None) — call_args_list[0] isolates the
    # first call.
    first_call_kwargs = mock_resolver.call_args_list[0].kwargs
    got_credential_id = first_call_kwargs.get("credential_id")
    assert got_credential_id == "uuid-abc", (
        f"Bug AA: resolver first call did not carry credential_id='uuid-abc'; "
        f"first call kwargs were {first_call_kwargs!r}"
    )


@pytest.mark.asyncio
async def test_failed_discover_writes_to_requested_identifier_row(sitemap):
    """Bug BB: a failed discovery should upsert to the existing row for
    hostname="pve", NOT create a degenerate zombie row.

    Pre-seed a row for "pve".  Force ssh_discover_system to return an error
    envelope with connection_ip="pve".  After discover_and_store, exactly one
    row should exist with hostname="pve" and status="error".
    """
    _seed_row(sitemap, hostname="pve", connection_ip="192.168.10.20")

    # The ssh_connection_wrapper error envelope uses "connection_ip" as the
    # dialed target but does NOT include a separate "hostname" field (Bug BB).
    # parse_discovery_output thus produces device.hostname="" — a degenerate
    # key that creates a zombie row keyed by (hostname="", connection_ip="pve")
    # instead of updating the pre-existing hostname="pve" row.
    error_payload = json.dumps(
        {
            "status": "error",
            "connection_ip": "pve",
            "error": "timeout",
            # NOTE: no "hostname" field — this is the actual shape produced by
            # ssh_connection_wrapper when a timeout occurs (Bug BB source).
        }
    )

    with patch(
        "homelab_mcp.ssh_tools.ssh_discover_system_with_binding",
        new_callable=AsyncMock,
        return_value=(error_payload, None),
    ):
        await discover_and_store(sitemap, hostname="pve")

    all_rows = sitemap.db_adapter.get_all_devices()
    assert len(all_rows) == 1, (
        f"Bug BB: expected exactly 1 row after failed discovery; got {len(all_rows)}: {all_rows!r}"
    )
    row = all_rows[0]
    assert row["hostname"] == "pve", f"Bug BB: row hostname should be 'pve'; got {row['hostname']!r}"
    assert row["status"] == "error", f"Bug BB: row status should be 'error'; got {row['status']!r}"


@pytest.mark.asyncio
async def test_failed_discover_does_not_collapse_to_empty_hostname(sitemap):
    """Bug BB: when parse_discovery_output gets a JSONDecodeError, the
    resulting row must use the requested hostname ("fakehost.local"), NOT
    "unknown" or "".

    No row pre-seeded.  Force the discovery result to be malformed JSON so
    parse_discovery_output raises JSONDecodeError internally.
    """
    malformed_payload = "NOT_VALID_JSON{"

    with patch(
        "homelab_mcp.ssh_tools.ssh_discover_system_with_binding",
        new_callable=AsyncMock,
        return_value=(malformed_payload, None),
    ):
        await discover_and_store(sitemap, hostname="fakehost.local")

    all_rows = sitemap.db_adapter.get_all_devices()
    hostnames = [r["hostname"] for r in all_rows]
    assert "fakehost.local" in hostnames, (
        f"Bug BB: expected row with hostname='fakehost.local'; got hostnames={hostnames!r}, all_rows={all_rows!r}"
    )
    # No zombie row with blank/unknown hostname should exist
    for row in all_rows:
        assert row["hostname"] not in ("", "unknown"), f"Bug BB: degenerate zombie row created: {row!r}"


@pytest.mark.asyncio
async def test_dial_target_uses_row_connection_ip(sitemap):
    """Bug V (discover side): ssh_connect must be called with the row's
    connection_ip ("192.168.10.20"), NOT the logical hostname ("pve").

    Pre-seed a row with connection_ip="192.168.10.20".  Assert ssh_connect
    sees hostname="192.168.10.20".

    Plan 03 fix: discover_and_store derives dial_target from row.connection_ip
    and passes it to ssh_discover_system. fake_creds carries a non-None
    password to trigger Tier-1 short-circuit inside ssh_discover_system so
    ssh_connect is actually reached.
    """
    _seed_row(sitemap, hostname="pve", connection_ip="192.168.10.20", ssh_credential_id="uuid-abc")

    fake_creds = SimpleNamespace(
        hostname="192.168.10.20",
        username="root",
        port=22,
        password="fake-password",
        key_path=None,
    )

    captured: dict = {}

    async def fake_ssh_connect(**kwargs):
        captured.update(kwargs)

        class _Ctx:
            async def __aenter__(self_inner):
                conn = MagicMock()
                conn.run = AsyncMock(return_value=MagicMock(exit_status=1, stdout=""))
                return conn

            async def __aexit__(self_inner, exc_type, exc, tb):
                return None

        return _Ctx()

    with (
        patch(
            "homelab_mcp.ssh_tools.resolve_ssh_credentials",
            return_value=fake_creds,
        ),
        patch(
            "homelab_mcp.ssh_tools.ssh_connect",
            side_effect=fake_ssh_connect,
        ),
    ):
        await discover_and_store(sitemap, hostname="pve")

    assert captured.get("hostname") == "192.168.10.20", (
        f"Bug V: ssh_connect dialed {captured.get('hostname')!r}, expected row.connection_ip='192.168.10.20'"
    )


@pytest.mark.asyncio
async def test_drift_dials_connection_ip_not_hostname():
    """Bug V (drift side): scan_drift must call get_proxmox_client with
    the row's connection_ip, NOT the hostname.

    Mirror tests/test_drift_detection.py:37-77 pattern.
    """
    db_adapter = MagicMock()
    db_adapter.get_all_devices.return_value = [
        {
            "hostname": "pve",
            "connection_ip": "192.168.10.20",
            "proxmox_credential_id": "uuid-prox",
            "ssh_credential_id": "uuid-ssh",
            "status": "success",
            "last_seen": datetime.now(UTC).isoformat(),
        }
    ]

    captured: dict = {}

    async def fake_get_client(host, *, session=None, credential_id=None):
        captured["host"] = host
        client = MagicMock()
        client.get = AsyncMock(return_value=[])
        return client

    with (
        patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
        patch("homelab_mcp.drift_detection._bulk_universal_core_probes", AsyncMock(return_value={})),
    ):
        from homelab_mcp.drift_detection import scan_drift

        await scan_drift(session=None, db_adapter=db_adapter)

    assert captured.get("host") == "192.168.10.20", (
        f"Bug V: drift dialed {captured.get('host')!r}, expected row.connection_ip='192.168.10.20'"
    )


@pytest.mark.asyncio
async def test_error_envelope_carries_hostname():
    """Bug BB (envelope layer): ssh_connection_wrapper error envelopes must
    include a "hostname" field.

    Currently envelopes carry "connection_ip" but NOT a separate "hostname"
    field; Plan 04 will add it.
    """

    @ssh_connection_wrapper(timeout_seconds=0.01)
    async def slow(hostname):
        import asyncio

        await asyncio.sleep(1.0)
        return "{}"

    result = await slow(hostname="pve")
    envelope = json.loads(result)
    assert envelope.get("hostname") == "pve", f"Bug BB envelope: missing/wrong hostname field; got {envelope!r}"
