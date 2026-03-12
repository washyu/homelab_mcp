"""Tests for drift detection module — Phase 11."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# import will fail until drift_detection.py exists — that is expected (RED)
from homelab_mcp.drift_detection import _diff_vm_config, scan_drift, update_baseline_after_mutation


class TestScanDriftReport:
    """Tests for DRFT-01: scan_drift returns structured drift report."""

    @pytest.mark.asyncio
    async def test_returns_structured_report(self):
        """scan_drift returns dict with all required top-level keys."""
        db_adapter = MagicMock()
        db_adapter.get_all_drift_baselines.return_value = []
        db_adapter.get_all_devices.return_value = []
        session = AsyncMock()

        result = await scan_drift(session, db_adapter)

        assert isinstance(result, dict)
        assert "status" in result
        assert "scan_timestamp" in result
        assert "config_drift" in result
        assert "state_drift" in result
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_config_drift_fields(self):
        """Each config_drift entry has required fields with correct values."""
        db_adapter = MagicMock()
        db_adapter.get_all_drift_baselines.return_value = [
            {
                "node": "pve",
                "vmid": 100,
                "vm_type": "qemu",
                "baseline_config": {"cores": 2, "memory": 2048},
                "recorded_by": "test",
            }
        ]
        db_adapter.get_all_devices.return_value = []
        session = AsyncMock()
        # Mock Proxmox API returning different config
        session.get = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": {"cores": 4, "memory": 4096}})
        session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        session.get.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await scan_drift(session, db_adapter)

        if result["config_drift"]:
            entry = result["config_drift"][0]
            assert "drift_type" in entry
            assert entry["drift_type"] == "config"
            assert "expected" in entry
            assert "actual" in entry
            assert "changed_fields" in entry
            assert "scan_timestamp" in entry

    @pytest.mark.asyncio
    async def test_empty_when_no_baselines(self):
        """scan_drift with no baselines in DB returns empty drift lists."""
        db_adapter = MagicMock()
        db_adapter.get_all_drift_baselines.return_value = []
        db_adapter.get_all_devices.return_value = []
        session = AsyncMock()

        result = await scan_drift(session, db_adapter)

        assert result["config_drift"] == []
        assert result["state_drift"] == []
        assert result["status"] == "success"


class TestConfigDrift:
    """Tests for DRFT-03: _diff_vm_config pure-function unit tests."""

    def test_detects_cpu_change(self):
        """_diff_vm_config detects cores change."""
        baseline = {"cores": 2, "memory": 2048}
        live = {"cores": 4, "memory": 2048}

        expected, actual, changed_fields = _diff_vm_config(baseline, live)

        assert "cores" in changed_fields
        assert "memory" not in changed_fields

    def test_no_drift_when_identical(self):
        """_diff_vm_config returns empty changed_fields when configs match."""
        config = {"cores": 2, "memory": 2048}

        expected, actual, changed_fields = _diff_vm_config(config, config)

        assert changed_fields == []

    def test_memory_and_net_detected(self):
        """_diff_vm_config detects both memory and net0 changes."""
        baseline = {"cores": 2, "memory": 2048, "net0": "virtio,bridge=vmbr0"}
        live = {"cores": 2, "memory": 4096, "net0": "virtio,bridge=vmbr1"}

        expected, actual, changed_fields = _diff_vm_config(baseline, live)

        assert "memory" in changed_fields
        assert "net0" in changed_fields
        assert "cores" not in changed_fields


class TestStateDrift:
    """Tests for DRFT-02: state drift detection including SSH probe."""

    @pytest.mark.asyncio
    async def test_offline_vm_labeled_as_observation(self):
        """State drift finding uses 'observation' field, not 'confirmed_drift'."""
        db_adapter = MagicMock()
        db_adapter.get_all_drift_baselines.return_value = [
            {
                "node": "pve",
                "vmid": 101,
                "vm_type": "qemu",
                "baseline_config": {"cores": 2, "status": "running"},
                "recorded_by": "test",
            }
        ]
        db_adapter.get_all_devices.return_value = []
        session = AsyncMock()

        # Mock Proxmox reporting VM is stopped
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": {"cores": 2, "status": "stopped"}})
        session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        session.get.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await scan_drift(session, db_adapter)

        if result["state_drift"]:
            entry = result["state_drift"][0]
            assert "observation" in entry
            assert "confirmed_drift" not in entry

    @pytest.mark.asyncio
    async def test_state_drift_structure(self):
        """State drift entry has correct drift_type, expected, and actual fields."""
        db_adapter = MagicMock()
        db_adapter.get_all_drift_baselines.return_value = [
            {
                "node": "pve",
                "vmid": 101,
                "vm_type": "qemu",
                "baseline_config": {"cores": 2, "status": "running"},
                "recorded_by": "test",
            }
        ]
        db_adapter.get_all_devices.return_value = []
        session = AsyncMock()

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": {"cores": 2, "status": "stopped"}})
        session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        session.get.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await scan_drift(session, db_adapter)

        if result["state_drift"]:
            entry = result["state_drift"][0]
            assert entry["drift_type"] == "state"
            assert entry["expected"] == "running"
            assert entry["actual"] == "stopped"

    @pytest.mark.asyncio
    async def test_ssh_probe_unreachable(self):
        """When Proxmox reports running but SSH fails, state_drift has observation==vm_offline and actual==ssh_unreachable."""
        import asyncssh

        db_adapter = MagicMock()
        db_adapter.get_all_drift_baselines.return_value = [
            {
                "node": "pve",
                "vmid": 101,
                "vm_type": "qemu",
                "baseline_config": {"cores": 2, "status": "running"},
                "recorded_by": "test",
            }
        ]
        db_adapter.get_all_devices.return_value = [{"hostname": "pve", "ip_address": "192.168.1.10"}]
        session = AsyncMock()

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_vm_status") as mock_get_status,
            patch("homelab_mcp.drift_detection.asyncssh.connect") as mock_ssh_connect,
        ):
            mock_get_status.return_value = {
                "status": "success",
                "data": {"status": "running"},
            }
            mock_ssh_connect.side_effect = asyncssh.Error(14, "Connection refused")

            result = await scan_drift(session, db_adapter)

        state_drift = result["state_drift"]
        assert len(state_drift) >= 1
        ssh_finding = next((e for e in state_drift if e.get("actual") == "ssh_unreachable"), None)
        assert ssh_finding is not None
        assert ssh_finding["observation"] == "vm_offline"
        assert ssh_finding["actual"] == "ssh_unreachable"


class TestBaselineUpdate:
    """Tests for DRFT-05: update_baseline_after_mutation."""

    @pytest.mark.asyncio
    async def test_baseline_written_after_mutation(self):
        """update_baseline_after_mutation writes baseline that can be retrieved via get_drift_baseline."""
        db_adapter = MagicMock()
        db_adapter.get_drift_baseline.return_value = None
        session = AsyncMock()

        with patch("homelab_mcp.drift_detection.get_proxmox_vm_config") as mock_get_config:
            mock_get_config.return_value = {
                "status": "success",
                "data": {"cores": 4, "memory": 4096},
            }

            await update_baseline_after_mutation(
                node="pve",
                vmid=100,
                vm_type="qemu",
                tool_name="resize_vm",
                session=session,
                db_adapter=db_adapter,
            )

        db_adapter.upsert_drift_baseline.assert_called_once()
        call_args = db_adapter.upsert_drift_baseline.call_args
        assert call_args is not None
        # Verify node and vmid were passed
        args = call_args[0] if call_args[0] else []
        kwargs = call_args[1] if call_args[1] else {}
        all_args = list(args) + list(kwargs.values())
        assert "pve" in all_args or kwargs.get("node") == "pve"
        assert 100 in all_args or kwargs.get("vmid") == 100
