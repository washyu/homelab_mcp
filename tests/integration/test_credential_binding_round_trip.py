"""Phase 38.1 Wave 0 RED scaffolds (Plan 01 Task 3): integration round-trip.

Pins the SPEC §Acceptance Criteria headline: `credentials add` → `discover_and_map`
→ `scan_drift` produces `counts.probed_ok >= 1` regardless of identifier form
(IP, short hostname, FQDN) or order (add-first vs discover-first).

All tests fail or error until Wave 1-4 lands the credential-binding mechanism;
Plan 09 (Wave 5) wires the assertions and stubs the Proxmox API.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_add_then_discover_then_drift_succeeds_with_ip_phase381(
    tmp_path, monkeypatch
):
    """SPEC §Acceptance: register by IP → discover_and_map → scan_drift sees probed_ok."""
    monkeypatch.setattr(
        "homelab_mcp.credential_store._REGISTRY_PATH",
        tmp_path / "credential_registry.json",
    )
    from homelab_mcp.credential_store import register_credential

    register_credential("192.168.10.20", "root@pam!tok", credential_type="proxmox")

    from src.homelab_mcp.database import SQLiteAdapter
    from src.homelab_mcp.drift_detection import scan_drift
    from src.homelab_mcp.sitemap import NetworkSiteMap, discover_and_store

    adapter = SQLiteAdapter(str(tmp_path / "sitemap.db"))
    adapter.connect()
    adapter.init_schema()
    sitemap = NetworkSiteMap(db_path=str(tmp_path / "sitemap.db"), db_type="sqlite")

    fake_client = MagicMock()
    fake_client.get_cluster_status = AsyncMock(return_value=[
        {"type": "node", "name": "pve", "online": 1}
    ])

    with (
        patch(
            "src.homelab_mcp.ssh_tools.ssh_discover_system",
            return_value={
                "status": "success",
                "hostname": "pve",
                "connection_ip": "192.168.10.20",
            },
        ),
        patch(
            "homelab_mcp.drift_detection.get_proxmox_client",
            new=AsyncMock(return_value=fake_client),
        ),
    ):
        await discover_and_store(
            sitemap,
            hostname="192.168.10.20",
            username="root@pam!tok",
            password="secret",
        )
        result = await scan_drift(session=None, db_adapter=adapter)

    adapter.close()

    assert result["counts"]["probed_ok"] >= 1, (
        f"Phase 38.1 SPEC §Acceptance: round-trip with IP identifier must produce "
        f"probed_ok >= 1; got {result['counts']!r}"
    )


@pytest.mark.asyncio
async def test_add_then_discover_then_drift_succeeds_with_short_hostname_phase381(
    tmp_path, monkeypatch
):
    """Identifier-form independence: short hostname registration round-trips."""
    monkeypatch.setattr(
        "homelab_mcp.credential_store._REGISTRY_PATH",
        tmp_path / "credential_registry.json",
    )
    from homelab_mcp.credential_store import register_credential

    register_credential("pve", "root@pam!tok", credential_type="proxmox")

    from src.homelab_mcp.database import SQLiteAdapter
    from src.homelab_mcp.drift_detection import scan_drift
    from src.homelab_mcp.sitemap import NetworkSiteMap, discover_and_store

    adapter = SQLiteAdapter(str(tmp_path / "sitemap.db"))
    adapter.connect()
    adapter.init_schema()
    sitemap = NetworkSiteMap(db_path=str(tmp_path / "sitemap.db"), db_type="sqlite")

    fake_client = MagicMock()
    fake_client.get_cluster_status = AsyncMock(return_value=[
        {"type": "node", "name": "pve", "online": 1}
    ])
    with (
        patch(
            "src.homelab_mcp.ssh_tools.ssh_discover_system",
            return_value={
                "status": "success",
                "hostname": "pve",
                "connection_ip": "192.168.10.20",
            },
        ),
        patch(
            "homelab_mcp.drift_detection.get_proxmox_client",
            new=AsyncMock(return_value=fake_client),
        ),
    ):
        await discover_and_store(
            sitemap, hostname="pve", username="root@pam!tok", password="secret"
        )
        result = await scan_drift(session=None, db_adapter=adapter)
    adapter.close()

    assert result["counts"]["probed_ok"] >= 1, (
        f"Phase 38.1 SPEC: short-hostname round-trip must produce probed_ok >= 1; got {result['counts']!r}"
    )


@pytest.mark.asyncio
async def test_add_then_discover_then_drift_succeeds_with_fqdn_phase381(
    tmp_path, monkeypatch
):
    """Identifier-form independence: FQDN registration round-trips."""
    monkeypatch.setattr(
        "homelab_mcp.credential_store._REGISTRY_PATH",
        tmp_path / "credential_registry.json",
    )
    from homelab_mcp.credential_store import register_credential

    register_credential("pve.lan.example.com", "root@pam!tok", credential_type="proxmox")

    from src.homelab_mcp.database import SQLiteAdapter
    from src.homelab_mcp.drift_detection import scan_drift
    from src.homelab_mcp.sitemap import NetworkSiteMap, discover_and_store

    adapter = SQLiteAdapter(str(tmp_path / "sitemap.db"))
    adapter.connect()
    adapter.init_schema()
    sitemap = NetworkSiteMap(db_path=str(tmp_path / "sitemap.db"), db_type="sqlite")

    fake_client = MagicMock()
    fake_client.get_cluster_status = AsyncMock(return_value=[
        {"type": "node", "name": "pve.lan.example.com", "online": 1}
    ])
    with (
        patch(
            "src.homelab_mcp.ssh_tools.ssh_discover_system",
            return_value={
                "status": "success",
                "hostname": "pve.lan.example.com",
                "connection_ip": "192.168.10.20",
            },
        ),
        patch(
            "homelab_mcp.drift_detection.get_proxmox_client",
            new=AsyncMock(return_value=fake_client),
        ),
    ):
        await discover_and_store(
            sitemap,
            hostname="pve.lan.example.com",
            username="root@pam!tok",
            password="secret",
        )
        result = await scan_drift(session=None, db_adapter=adapter)
    adapter.close()

    assert result["counts"]["probed_ok"] >= 1, (
        f"Phase 38.1 SPEC: FQDN round-trip must produce probed_ok >= 1; got {result['counts']!r}"
    )


@pytest.mark.asyncio
async def test_discover_first_then_add_phase381(tmp_path, monkeypatch):
    """Order independence: discover_and_map first, credentials add second, still GREEN."""
    monkeypatch.setattr(
        "homelab_mcp.credential_store._REGISTRY_PATH",
        tmp_path / "credential_registry.json",
    )

    from src.homelab_mcp.database import SQLiteAdapter
    from src.homelab_mcp.drift_detection import scan_drift
    from src.homelab_mcp.sitemap import NetworkSiteMap, discover_and_store

    adapter = SQLiteAdapter(str(tmp_path / "sitemap.db"))
    adapter.connect()
    adapter.init_schema()
    sitemap = NetworkSiteMap(db_path=str(tmp_path / "sitemap.db"), db_type="sqlite")

    fake_client = MagicMock()
    fake_client.get_cluster_status = AsyncMock(return_value=[
        {"type": "node", "name": "pve", "online": 1}
    ])
    with patch(
        "src.homelab_mcp.ssh_tools.ssh_discover_system",
        return_value={
            "status": "success",
            "hostname": "pve",
            "connection_ip": "192.168.10.20",
        },
    ):
        await discover_and_store(
            sitemap, hostname="192.168.10.20", username="root", password="secret"
        )

    from homelab_mcp.credential_store import register_credential

    register_credential("192.168.10.20", "root@pam!tok", credential_type="proxmox")
    # Plan 07 _cmd_credentials_add will auto-bind here in the real CLI flow;
    # for the scaffold we replicate the post-bind condition explicitly.
    devices = adapter.get_all_devices()
    assert devices, "discover_and_store must have created a row"

    with patch(
        "homelab_mcp.drift_detection.get_proxmox_client",
        new=AsyncMock(return_value=fake_client),
    ):
        result = await scan_drift(session=None, db_adapter=adapter)
    adapter.close()

    assert result["counts"]["probed_ok"] >= 1, (
        f"Phase 38.1 SPEC: discover-first/add-second round-trip must produce "
        f"probed_ok >= 1; got {result['counts']!r}"
    )
