"""Tests for drift detection — Phase 36 (sitemap-as-baseline 2-bucket interim)."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homelab_mcp.drift_detection import scan_drift
from homelab_mcp.proxmox_api import CredentialNotFoundError


class TestScanDrift2Bucket:
    """Phase 36 D-01/D-02/D-09: scan_drift 2-bucket sitemap-iteration shape."""

    @pytest.mark.asyncio
    async def test_three_row_classification(self):
        """3-row sitemap: pve1 -> probed_ok, truenas1 -> silently skipped, pi-lab -> unreachable."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"},
            {"hostname": "truenas1", "connection_ip": "10.0.0.11", "status": "success"},
            {"hostname": "pi-lab", "connection_ip": "10.0.0.12", "status": "success"},
        ]

        async def fake_get_client(host, session=None):
            if host == "pve1":
                client = MagicMock()
                client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
                return client
            if host == "truenas1":
                raise CredentialNotFoundError(f"no creds for {host}")
            if host == "pi-lab":
                client = MagicMock()
                client.get = AsyncMock(side_effect=aiohttp.ClientError("connection refused to pve.home"))
                return client
            raise AssertionError(f"unexpected host: {host}")

        async def fake_resolve(host, session=None):
            if host == "pve1":
                return ("token@node", "node", None)
            if host == "pi-lab":
                return ("token@cluster", "cluster", "homelab-prod")
            raise AssertionError(f"unexpected host: {host}")

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["status"] == "success"
        assert result["scanned"] == 2  # pve1 + pi-lab; truenas1 silently skipped
        assert len(result["probed_ok"]) == 1
        assert result["probed_ok"][0]["hostname"] == "pve1"
        assert result["probed_ok"][0]["scope"] == "node"
        assert result["probed_ok"][0]["cluster_name"] is None
        assert result["probed_ok"][0]["status"] == "probed-ok"
        assert result["probed_ok"][0]["error"] is None
        assert len(result["unreachable"]) == 1
        assert result["unreachable"][0]["hostname"] == "pi-lab"
        assert result["unreachable"][0]["scope"] == "cluster"
        assert result["unreachable"][0]["cluster_name"] == "homelab-prod"
        assert "connection refused" in result["unreachable"][0]["error"].lower()
        all_hostnames = [r["hostname"] for r in result["probed_ok"] + result["unreachable"]]
        assert "truenas1" not in all_hostnames

    @pytest.mark.asyncio
    async def test_empty_sitemap_returns_success(self):
        """D-03: zero rows -> successful empty result, never an error."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = []

        result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["status"] == "success"
        assert result["scanned"] == 0
        assert result["probed_ok"] == []
        assert result["unreachable"] == []
        assert "scan_timestamp" in result

    @pytest.mark.asyncio
    async def test_degenerate_rows_excluded(self):
        """D-10a: rows with status=='error' OR hostname in ('', 'unknown', None) skipped pre-resolve."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "", "connection_ip": "10.0.0.1", "status": "success"},
            {"hostname": "unknown", "connection_ip": "10.0.0.2", "status": "success"},
            {"hostname": None, "connection_ip": "10.0.0.3", "status": "success"},
            {"hostname": "errored-host", "connection_ip": "10.0.0.4", "status": "error"},
        ]

        # If degenerate-skip works, get_proxmox_client is never called
        with patch("homelab_mcp.drift_detection.get_proxmox_client") as mock_client:
            result = await scan_drift(session=None, db_adapter=db_adapter)

        mock_client.assert_not_called()
        assert result["scanned"] == 0
        assert result["probed_ok"] == []
        assert result["unreachable"] == []

    @pytest.mark.asyncio
    async def test_silent_skip_on_credential_not_found(self):
        """D-10: CredentialNotFoundError on get_proxmox_client -> row excluded from both buckets."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "not-a-proxmox-host", "connection_ip": "10.0.0.1", "status": "success"},
        ]

        async def fake_get_client(host, session=None):
            raise CredentialNotFoundError("no proxmox creds")

        with patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["scanned"] == 0
        assert result["probed_ok"] == []
        assert result["unreachable"] == []

    @pytest.mark.asyncio
    async def test_unreachable_error_is_sanitized(self):
        """D-09a: probe exception messages pass through sanitize_error."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "leaky", "connection_ip": "10.0.0.1", "status": "success"},
        ]

        async def fake_get_client(host, session=None):
            client = MagicMock()
            # Simulate an exception that contains a "secret-looking" token
            client.get = AsyncMock(
                side_effect=aiohttp.ClientError(
                    "connection refused (token=PVEAPIToken=user@pam!id=secretsecret)"
                )
            )
            return client

        async def fake_resolve(host, session=None):
            return ("token", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert len(result["unreachable"]) == 1
        # The raw secret string should not appear verbatim in the sanitized error
        # (sanitize_error redacts PVEAPIToken=...)
        err = result["unreachable"][0]["error"]
        assert "secretsecret" not in err

    @pytest.mark.asyncio
    async def test_inert_filter_passthrough(self):
        """D-04: node and vm_type kwargs are accepted but inert in Phase 36."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = []

        # Pass filter args; assert they don't break or produce errors
        result = await scan_drift(
            session=None, db_adapter=db_adapter, node="pve1", vm_type="qemu"
        )
        assert result["status"] == "success"

        result = await scan_drift(
            session=None, db_adapter=db_adapter, node=None, vm_type="all"
        )
        assert result["status"] == "success"
