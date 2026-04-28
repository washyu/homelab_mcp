"""Phase 39 shared test fixtures for drift detection.

Provides the deterministic substrate (frozen clock, mocked SSH probes, sitemap
row factories, Proxmox cluster-resources mocks) that Plans 01/02/03 of Phase 39
compose into RED tests for ``scan_drift``'s unknown / missing / changed buckets.

All datetimes use UTC. ``freeze_now`` monkeypatches
``homelab_mcp.drift_detection.datetime`` so any helper that calls
``datetime.now(UTC)`` inside ``drift_detection`` sees a fixed wall-clock.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def freeze_now(monkeypatch: pytest.MonkeyPatch) -> datetime:
    """Freeze ``datetime.now`` inside ``homelab_mcp.drift_detection`` to
    2026-04-27T12:00:00Z. Returns the frozen aware datetime.

    Tests that call helpers requiring a ``now`` parameter pass the returned
    value explicitly. Helpers that read ``datetime.now(UTC)`` internally see
    the frozen clock automatically.
    """
    frozen = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)

    class _FakeDatetime(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
            if tz is not None:
                return frozen
            return frozen.replace(tzinfo=None)

    monkeypatch.setattr("homelab_mcp.drift_detection.datetime", _FakeDatetime)
    return frozen


@pytest.fixture
def mock_universal_core_probe_response() -> dict[str, Any]:
    """Canonical universal-core probe result for a clean Proxmox host."""
    return {
        "kernel_name": "Linux",
        "kernel_version": "6.5.13-1-pve",
        "os_name": "Proxmox VE",
        "os_version": "8.2.4",
        "package_fingerprint": "sha256:abc123",
    }


@pytest.fixture
def mock_universal_core_probe_drifted() -> dict[str, Any]:
    """Same shape as ``mock_universal_core_probe_response`` but with a kernel
    bump and package-fingerprint shift — used to drive DRFT-19 changed-bucket
    fixtures in Plan 03.
    """
    return {
        "kernel_name": "Linux",
        "kernel_version": "6.8.4-2-pve",
        "os_name": "Proxmox VE",
        "os_version": "8.2.4",
        "package_fingerprint": "sha256:def456",
    }


@pytest.fixture
def mock_cluster_resources_response() -> list[dict[str, Any]]:
    """``GET /cluster/resources`` shape — three VM/LXC entries plus one
    node-type record (filtered out by ``_enumerate_unknown_vms``).

    Used by DRFT-17 unknown-bucket tests to mock per-cluster enumeration.
    """
    return [
        {"type": "qemu", "vmid": 100, "name": "ubuntu-prod", "node": "pve1", "status": "running"},
        {"type": "qemu", "vmid": 110, "name": "ubuntu-test", "node": "pve1", "status": "stopped"},
        {"type": "lxc", "vmid": 200, "name": "pi-hole", "node": "pve1", "status": "running"},
        {"type": "node", "node": "pve1", "status": "online"},
    ]


@pytest.fixture
def sitemap_row_old_last_seen(freeze_now: datetime) -> dict[str, Any]:
    """Sitemap row with ``last_seen`` 12 days before frozen now — promotes
    to ``status: "missing"`` under the default 7-day threshold.

    ``last_seen`` is naive isoformat (no tzinfo) per Phase 35 sitemap.py:84;
    helpers must normalize via ``_parse_last_seen``.
    """
    naive_now = freeze_now.replace(tzinfo=None)
    return {
        "hostname": "pi-lab",
        "connection_ip": "10.0.0.12",
        "status": "success",
        "ssh_credential_id": "11111111-1111-1111-1111-111111111111",
        "proxmox_credential_id": None,
        "last_seen": (naive_now - timedelta(days=12)).isoformat(),
        "fingerprint": {},
    }


@pytest.fixture
def sitemap_row_recent_last_seen(freeze_now: datetime) -> dict[str, Any]:
    """Sitemap row with ``last_seen`` 1 day before frozen now — stays in
    ``unreachable`` (not promoted to missing)."""
    naive_now = freeze_now.replace(tzinfo=None)
    return {
        "hostname": "pi-lab",
        "connection_ip": "10.0.0.12",
        "status": "success",
        "ssh_credential_id": "11111111-1111-1111-1111-111111111111",
        "proxmox_credential_id": None,
        "last_seen": (naive_now - timedelta(days=1)).isoformat(),
        "fingerprint": {},
    }


@pytest.fixture
def sitemap_row_with_stored_fingerprint(
    mock_universal_core_probe_response: dict[str, Any],
) -> dict[str, Any]:
    """Sitemap row with full Phase 38 fingerprint blob INCLUDING agent-curated
    capabilities sub-tree — exercises the D-09a leaf-level "present in both"
    diff rule.
    """
    fingerprint = dict(mock_universal_core_probe_response)
    fingerprint["capabilities"] = {"vulkan": {"available": True}}
    return {
        "hostname": "pve1",
        "connection_ip": "10.0.0.10",
        "status": "success",
        "ssh_credential_id": "22222222-2222-2222-2222-222222222222",
        "proxmox_credential_id": "33333333-3333-3333-3333-333333333333",
        "last_seen": "2026-04-27T11:00:00",
        "fingerprint": fingerprint,
    }


@pytest.fixture
def mock_resolve_ssh_credentials() -> MagicMock:
    """Mock for ``resolve_ssh_credentials`` — returns a credential record
    matching what the Phase 38.1 R6 resolver produces.
    """
    creds = MagicMock()
    creds.hostname = "10.0.0.12"
    creds.username = "mcp_admin"
    creds.port = 22
    creds.password = None
    creds.key_path = "/tmp/fake-key"  # noqa: S108 (test fixture path, not a secret)
    return creds


@pytest.fixture
def mock_ssh_connect() -> MagicMock:
    """Async-context-manager mock for ``asyncssh.connect``.

    ``__aenter__`` returns a conn whose ``.run`` is an ``AsyncMock`` that
    returns ``MagicMock(exit_status=0, stdout="Linux")`` by default. Tests
    that need per-command stdouts override ``conn.run.side_effect``.
    """
    cm = MagicMock()
    conn = MagicMock()
    conn.run = AsyncMock(return_value=MagicMock(exit_status=0, stdout="Linux"))
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm
