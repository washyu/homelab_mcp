"""Integration tests for sitemap functionality with real SSH discovery."""

import json

import pytest

from src.homelab_mcp.sitemap import (
    NetworkSiteMap,
    bulk_discover_and_store,
    discover_and_store,
)
from src.homelab_mcp.tools import execute_tool

pytestmark = pytest.mark.integration


# Tests that depended on setup_remote_mcp_admin were removed in Phase 33 (D-11)
# when the function was deleted as part of the keyring-only credential migration.
# The remaining tests exercise sitemap behavior with mock discovery data and
# error paths that don't require the deleted onboarding helper.


class TestSitemapIntegration:
    """Integration tests for sitemap functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create an in-memory database for testing."""
        yield ":memory:"

    @pytest.fixture
    def sitemap(self, temp_db):
        """Create a NetworkSiteMap instance with temporary database."""
        return NetworkSiteMap(db_path=temp_db, db_type="sqlite")

    @pytest.mark.asyncio
    async def test_sitemap_workflow_with_mock_discovery(self, sitemap):
        """Test sitemap workflow with mocked SSH discovery data."""
        # Simulate a successful SSH discovery result
        mock_discovery_data = {
            "status": "success",
            "hostname": "mock-server",
            "connection_ip": "192.168.1.100",
            "data": {
                "cpu": {"model": "Intel Core i7-9700K", "cores": "8"},
                "memory": {
                    "total": "16G",
                    "used": "8G",
                    "free": "6G",
                    "available": "12G",
                },
                "disk": {
                    "filesystem": "/dev/sda1",
                    "size": "1T",
                    "used": "400G",
                    "available": "500G",
                    "use_percent": "45%",
                    "mount": "/",
                },
                "network": [{"name": "eth0", "state": "UP", "addresses": ["192.168.1.100"]}],
                "uptime": "up 5 days, 2 hours, 30 minutes",
                "os": "Ubuntu 22.04.3 LTS",
            },
        }

        # Parse and store the mock discovery data
        device = sitemap.parse_discovery_output(json.dumps(mock_discovery_data))
        device_id = sitemap.store_device(device)
        sitemap.store_discovery_history(device_id, json.dumps(mock_discovery_data))

        # Verify device was stored correctly
        devices = sitemap.get_all_devices()
        assert len(devices) == 1

        stored_device = devices[0]
        assert stored_device["hostname"] == "mock-server"
        assert stored_device["connection_ip"] == "192.168.1.100"
        assert stored_device["status"] == "success"
        assert stored_device["cpu_model"] == "Intel Core i7-9700K"
        assert stored_device["cpu_cores"] == 8
        assert stored_device["memory_total"] == "16G"
        assert stored_device["os_info"] == "Ubuntu 22.04.3 LTS"

        # Test network topology analysis
        analysis = sitemap.analyze_network_topology()
        assert analysis["total_devices"] == 1
        assert analysis["online_devices"] == 1
        assert analysis["offline_devices"] == 0
        assert "Ubuntu 22.04.3 LTS" in analysis["operating_systems"]
        assert "192.168.1.0/24" in analysis["network_segments"]

        # Test deployment suggestions
        suggestions = sitemap.suggest_deployments()
        assert len(suggestions["monitoring_targets"]) == 1
        assert suggestions["monitoring_targets"][0]["hostname"] == "mock-server"

        # High-spec device should be suggested for load balancing and database
        lb_candidates = [c["hostname"] for c in suggestions["load_balancer_candidates"]]
        db_candidates = [c["hostname"] for c in suggestions["database_candidates"]]
        assert "mock-server" in lb_candidates
        assert "mock-server" in db_candidates

        # Test change history
        changes = sitemap.get_device_changes(device_id)
        assert len(changes) == 1
        assert changes[0]["data"]["hostname"] == "mock-server"

    @pytest.mark.asyncio
    async def test_mcp_tools_integration_with_mock_data(self, temp_db):
        """Test MCP tool integration with pre-populated mock data."""
        from unittest.mock import patch

        # Create sitemap and populate with mock data
        sitemap = NetworkSiteMap(db_path=temp_db, db_type="sqlite")

        # Add multiple mock devices for comprehensive testing
        mock_devices = [
            {
                "status": "success",
                "hostname": "web-server-01",
                "connection_ip": "192.168.1.10",
                "data": {
                    "cpu": {"model": "Intel Core i5", "cores": "4"},
                    "memory": {
                        "total": "8G",
                        "used": "4G",
                        "free": "3G",
                        "available": "6G",
                    },
                    "disk": {
                        "filesystem": "/dev/sda1",
                        "size": "500G",
                        "used": "200G",
                        "available": "250G",
                        "use_percent": "45%",
                        "mount": "/",
                    },
                    "network": [{"name": "eth0", "state": "UP", "addresses": ["192.168.1.10"]}],
                    "uptime": "up 10 days, 5 hours",
                    "os": "Ubuntu 20.04.6 LTS",
                },
            },
            {
                "status": "success",
                "hostname": "db-server-01",
                "connection_ip": "192.168.1.20",
                "data": {
                    "cpu": {"model": "AMD EPYC", "cores": "16"},
                    "memory": {
                        "total": "64G",
                        "used": "32G",
                        "free": "20G",
                        "available": "40G",
                    },
                    "disk": {
                        "filesystem": "/dev/nvme0n1p1",
                        "size": "2T",
                        "used": "800G",
                        "available": "1T",
                        "use_percent": "40%",
                        "mount": "/",
                    },
                    "network": [{"name": "ens3", "state": "UP", "addresses": ["192.168.1.20"]}],
                    "uptime": "up 30 days, 12 hours",
                    "os": "Ubuntu 22.04.3 LTS",
                },
            },
            {
                "status": "error",
                "connection_ip": "192.168.1.99",
                "error": "SSH connection timeout",
            },
        ]

        # Store mock devices
        device_ids = []
        for mock_device in mock_devices:
            device = sitemap.parse_discovery_output(json.dumps(mock_device))
            device_id = sitemap.store_device(device)
            device_ids.append(device_id)
            sitemap.store_discovery_history(device_id, json.dumps(mock_device))

        # Test get_network_sitemap tool with patched sitemap
        with patch("src.homelab_mcp.tools.NetworkSiteMap") as mock_sitemap_class:
            mock_sitemap_class.return_value = sitemap

            sitemap_result = await execute_tool("get_network_sitemap", {})
            sitemap_text = sitemap_result["content"][0]["text"]
            sitemap_data = json.loads(sitemap_text)

            assert sitemap_data["status"] == "success"
            assert sitemap_data["total_devices"] == 3
            assert len(sitemap_data["devices"]) == 3

            # Verify device data
            hostnames = [device["hostname"] for device in sitemap_data["devices"] if device["hostname"]]
            assert "web-server-01" in hostnames
            assert "db-server-01" in hostnames

            # Test analyze_network_topology tool
            analysis_result = await execute_tool("analyze_network_topology", {})
            analysis_text = analysis_result["content"][0]["text"]
            analysis_data = json.loads(analysis_text)

            assert analysis_data["status"] == "success"
            analysis = analysis_data["analysis"]
            assert analysis["total_devices"] == 3
            assert analysis["online_devices"] == 2
            assert analysis["offline_devices"] == 1
            assert "Ubuntu 20.04.6 LTS" in analysis["operating_systems"]
            assert "Ubuntu 22.04.3 LTS" in analysis["operating_systems"]
            assert "192.168.1.0/24" in analysis["network_segments"]

            # Test suggest_deployments tool
            suggestions_result = await execute_tool("suggest_deployments", {})
            suggestions_text = suggestions_result["content"][0]["text"]
            suggestions_data = json.loads(suggestions_text)

            assert suggestions_data["status"] == "success"
            suggestions = suggestions_data["suggestions"]
            assert len(suggestions["monitoring_targets"]) == 2  # Only successful devices

            # High-spec db-server should be in load balancer and database candidates
            lb_candidates = [c["hostname"] for c in suggestions["load_balancer_candidates"]]
            db_candidates = [c["hostname"] for c in suggestions["database_candidates"]]
            assert "db-server-01" in lb_candidates  # 16 cores, 64G RAM
            assert "db-server-01" in db_candidates  # Low disk usage, high RAM

            # Test get_device_changes tool
            changes_result = await execute_tool(
                "get_device_changes",
                {
                    "device_id": device_ids[0],  # web-server-01
                    "limit": 5,
                },
            )
            changes_text = changes_result["content"][0]["text"]
            changes_data = json.loads(changes_text)

            assert changes_data["status"] == "success"
            assert changes_data["device_id"] == device_ids[0]
            assert len(changes_data["changes"]) >= 1
            assert changes_data["changes"][0]["data"]["hostname"] == "web-server-01"

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, sitemap):
        """Test sitemap error handling with real network scenarios."""
        # Test discovery of non-existent host
        discovery_result = await discover_and_store(
            sitemap,
            hostname="192.168.255.254",  # Non-existent IP
            username="test",
            password="test",
            port=22,
        )

        discovery_data = json.loads(discovery_result)
        assert discovery_data["status"] == "success"  # Function succeeds
        assert discovery_data["discovery_status"] == "error"  # But discovery fails

        # Verify error device is stored
        devices = sitemap.get_all_devices()
        assert len(devices) == 1
        assert devices[0]["status"] == "error"
        assert devices[0]["error_message"] is not None

        # Test network analysis with error devices
        analysis = sitemap.analyze_network_topology()
        assert analysis["total_devices"] == 1
        assert analysis["online_devices"] == 0
        assert analysis["offline_devices"] == 1

        # Test bulk discovery with mixed success/failure
        targets = [
            {
                "hostname": "192.168.255.253",
                "username": "test",
                "password": "test",
            },  # Will fail - invalid host
            {
                "hostname": "192.168.255.252",
                "username": "test",
                "password": "test",
            },  # Will also fail - invalid host
        ]

        bulk_result = await bulk_discover_and_store(sitemap, targets)
        bulk_data = json.loads(bulk_result)

        assert bulk_data["status"] == "success"
        assert bulk_data["total_targets"] == 2
        assert len(bulk_data["results"]) == 2

        # Both should have errors but function should handle gracefully
        for result in bulk_data["results"]:
            assert result["status"] == "success"  # Function succeeds
            # But discovery status may be error
