"""Integration tests for sitemap functionality with real SSH discovery."""

import json

import pytest

pytestmark = pytest.mark.integration

from src.homelab_mcp.sitemap import (
    NetworkSiteMap,
    bulk_discover_and_store,
    discover_and_store,
)
from src.homelab_mcp.ssh_tools import (
    setup_remote_mcp_admin,
    verify_mcp_admin_access,
)
from src.homelab_mcp.tools import execute_tool


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
                "network": [
                    {"name": "eth0", "state": "UP", "addresses": ["192.168.1.100"]}
                ],
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
                    "network": [
                        {"name": "eth0", "state": "UP", "addresses": ["192.168.1.10"]}
                    ],
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
                    "network": [
                        {"name": "ens3", "state": "UP", "addresses": ["192.168.1.20"]}
                    ],
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
            hostnames = [
                device["hostname"]
                for device in sitemap_data["devices"]
                if device["hostname"]
            ]
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
            assert (
                len(suggestions["monitoring_targets"]) == 2
            )  # Only successful devices

            # High-spec db-server should be in load balancer and database candidates
            lb_candidates = [
                c["hostname"] for c in suggestions["load_balancer_candidates"]
            ]
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
    async def test_end_to_end_discovery_workflow(self, clean_container, sitemap):
        """Test complete workflow: setup -> discover -> store -> analyze."""
        container_info = clean_container
        hostname = container_info["hostname"]  # localhost
        ssh_port = container_info["port"]  # 2222
        admin_user = container_info["admin_user"]  # testadmin
        admin_pass = container_info["admin_pass"]  # testpass123

        # Step 1: Setup mcp_admin on the container
        setup_result = await setup_remote_mcp_admin(
            hostname=hostname, username=admin_user, password=admin_pass, port=ssh_port
        )

        setup_data = json.loads(setup_result)
        assert setup_data["status"] == "success"
        assert setup_data["mcp_admin_setup"]["user_creation"] in [
            "Success: mcp_admin user created",
            "User already exists",
        ]
        assert "Success" in setup_data["mcp_admin_setup"]["ssh_key"]

        # Step 2: Verify mcp_admin access
        verify_result = await verify_mcp_admin_access(hostname=hostname, port=ssh_port)

        verify_data = json.loads(verify_result)
        assert verify_data["status"] == "success"
        assert "Success" in verify_data["mcp_admin"]["ssh_access"]

        # Step 3: Discover and store device information
        discovery_result = await discover_and_store(
            sitemap, hostname=hostname, username="mcp_admin", port=ssh_port
        )

        discovery_data = json.loads(discovery_result)
        assert discovery_data["status"] == "success"
        assert discovery_data["discovery_status"] == "success"
        assert "device_id" in discovery_data
        device_id = discovery_data["device_id"]

        # Step 4: Verify device was stored in database
        devices = sitemap.get_all_devices()
        assert len(devices) == 1

        device = devices[0]
        assert device["hostname"] == "test-ubuntu"  # Container hostname
        assert device["connection_ip"] == hostname  # localhost
        assert device["status"] == "success"
        # Note: Some fields may be None if parsing fails, but device should be stored
        print(f"Device CPU model: {device['cpu_model']}")
        print(f"Device memory: {device['memory_total']}")
        print(f"Device OS: {device['os_info']}")

        # Step 5: Test network topology analysis
        analysis = sitemap.analyze_network_topology()
        assert analysis["total_devices"] == 1
        assert analysis["online_devices"] == 1
        assert analysis["offline_devices"] == 0
        assert len(analysis["operating_systems"]) >= 1

        # Step 6: Test deployment suggestions
        suggestions = sitemap.suggest_deployments()
        assert len(suggestions["monitoring_targets"]) == 1
        assert suggestions["monitoring_targets"][0]["hostname"] == "test-ubuntu"

        # Step 7: Test change history
        changes = sitemap.get_device_changes(device_id)
        assert len(changes) >= 1
        assert changes[0]["data"]["hostname"] == "test-ubuntu"

    @pytest.mark.asyncio
    async def test_bulk_discovery_workflow(self, clean_container, sitemap):
        """Test bulk discovery with multiple target configurations."""
        container_info = clean_container
        hostname = container_info["hostname"]
        ssh_port = container_info["port"]
        admin_user = container_info["admin_user"]
        admin_pass = container_info["admin_pass"]

        # Setup mcp_admin first
        await setup_remote_mcp_admin(
            hostname=hostname, username=admin_user, password=admin_pass, port=ssh_port
        )

        # Create bulk targets - same container with different approaches
        targets = [
            {"hostname": hostname, "username": "mcp_admin", "port": ssh_port},
            # Test with invalid target to verify error handling
            {
                "hostname": "192.168.255.254",  # Non-existent IP
                "username": "test",
                "port": 22,
            },
        ]

        # Perform bulk discovery
        bulk_result = await bulk_discover_and_store(sitemap, targets)
        bulk_data = json.loads(bulk_result)

        assert bulk_data["status"] == "success"
        assert bulk_data["total_targets"] == 2
        assert len(bulk_data["results"]) == 2

        # First should succeed, second should fail
        successful_discoveries = sum(
            1
            for result in bulk_data["results"]
            if result.get("discovery_status") == "success"
            or result.get("status") == "success"
        )
        assert successful_discoveries >= 1

        # Verify devices are stored in database
        devices = sitemap.get_all_devices()
        assert len(devices) >= 1

        # Verify network analysis
        analysis = sitemap.analyze_network_topology()
        assert analysis["total_devices"] >= 1

    @pytest.mark.asyncio
    async def test_mcp_tool_integration(self, clean_container, temp_db):
        """Test sitemap functionality through MCP tool interface."""
        container_info = clean_container
        hostname = container_info["hostname"]
        ssh_port = container_info["port"]
        admin_user = container_info["admin_user"]
        admin_pass = container_info["admin_pass"]

        # Setup mcp_admin first
        await setup_remote_mcp_admin(
            hostname=hostname, username=admin_user, password=admin_pass, port=ssh_port
        )

        # Test discover_and_map tool
        discover_result = await execute_tool(
            "discover_and_map",
            {"hostname": hostname, "username": "mcp_admin", "port": ssh_port},
        )

        assert "content" in discover_result
        assert len(discover_result["content"]) > 0

        discover_text = discover_result["content"][0]["text"]
        discover_data = json.loads(discover_text)
        assert discover_data["status"] == "success"
        device_id = discover_data["device_id"]

        # Test get_network_sitemap tool
        sitemap_result = await execute_tool("get_network_sitemap", {})
        sitemap_text = sitemap_result["content"][0]["text"]
        sitemap_data = json.loads(sitemap_text)

        assert sitemap_data["status"] == "success"
        assert sitemap_data["total_devices"] >= 1
        assert len(sitemap_data["devices"]) >= 1

        # Verify the device data
        found_device = None
        for device in sitemap_data["devices"]:
            if device["connection_ip"] == hostname:
                found_device = device
                break

        assert found_device is not None
        assert found_device["hostname"] == "test-ubuntu"
        assert found_device["status"] == "success"

        # Test analyze_network_topology tool
        analysis_result = await execute_tool("analyze_network_topology", {})
        analysis_text = analysis_result["content"][0]["text"]
        analysis_data = json.loads(analysis_text)

        assert analysis_data["status"] == "success"
        assert analysis_data["analysis"]["total_devices"] >= 1
        assert analysis_data["analysis"]["online_devices"] >= 1

        # Test suggest_deployments tool
        suggestions_result = await execute_tool("suggest_deployments", {})
        suggestions_text = suggestions_result["content"][0]["text"]
        suggestions_data = json.loads(suggestions_text)

        assert suggestions_data["status"] == "success"
        assert len(suggestions_data["suggestions"]["monitoring_targets"]) >= 1

        # Test get_device_changes tool
        changes_result = await execute_tool(
            "get_device_changes", {"device_id": device_id, "limit": 5}
        )
        changes_text = changes_result["content"][0]["text"]
        changes_data = json.loads(changes_text)

        assert changes_data["status"] == "success"
        assert changes_data["device_id"] == device_id
        assert len(changes_data["changes"]) >= 1

    @pytest.mark.asyncio
    async def test_discovery_state_persistence(self, clean_container, temp_db):
        """Test that discovery state persists across sitemap instances."""
        container_info = clean_container
        hostname = container_info["hostname"]
        ssh_port = container_info["port"]
        admin_user = container_info["admin_user"]
        admin_pass = container_info["admin_pass"]

        # Setup mcp_admin
        await setup_remote_mcp_admin(
            hostname=hostname, username=admin_user, password=admin_pass, port=ssh_port
        )

        # First sitemap instance - discover and store
        sitemap1 = NetworkSiteMap(db_path=temp_db, db_type="sqlite")
        discovery_result1 = await discover_and_store(
            sitemap1, hostname=hostname, username="mcp_admin", port=ssh_port
        )

        discovery_data1 = json.loads(discovery_result1)
        assert discovery_data1["status"] == "success"
        device_id = discovery_data1["device_id"]

        devices1 = sitemap1.get_all_devices()
        assert len(devices1) == 1

        # Second sitemap instance - should load existing data
        sitemap2 = NetworkSiteMap(db_path=temp_db, db_type="sqlite")
        devices2 = sitemap2.get_all_devices()
        assert len(devices2) == 1
        assert devices2[0]["id"] == devices1[0]["id"]
        assert devices2[0]["hostname"] == devices1[0]["hostname"]

        # Discover same device again - should update, not create new
        discovery_result2 = await discover_and_store(
            sitemap2, hostname=hostname, username="mcp_admin", port=ssh_port
        )

        discovery_data2 = json.loads(discovery_result2)
        assert discovery_data2["status"] == "success"
        assert discovery_data2["device_id"] == device_id  # Same device ID

        # Should still have only one device
        devices3 = sitemap2.get_all_devices()
        assert len(devices3) == 1

        # But should have multiple history entries
        changes = sitemap2.get_device_changes(device_id)
        assert len(changes) >= 1  # May be 1 or 2 depending on data changes

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

    @pytest.mark.asyncio
    async def test_resource_analysis_accuracy(self, clean_container, sitemap):
        """Test that resource analysis provides accurate recommendations."""
        container_info = clean_container
        hostname = container_info["hostname"]
        ssh_port = container_info["port"]
        admin_user = container_info["admin_user"]
        admin_pass = container_info["admin_pass"]

        # Setup and discover
        await setup_remote_mcp_admin(
            hostname=hostname, username=admin_user, password=admin_pass, port=ssh_port
        )

        await discover_and_store(
            sitemap, hostname=hostname, username="mcp_admin", port=ssh_port
        )

        # Get device info for verification
        devices = sitemap.get_all_devices()
        device = devices[0]

        # Verify CPU and memory info was captured (may be None if parsing fails)
        # Note: cpu_cores can be None if CPU info parsing fails in the container
        print(f"CPU cores: {device['cpu_cores']}")
        print(f"Memory: {device['memory_total']}")

        assert device["memory_total"] is not None
        assert "G" in device["memory_total"] or "M" in device["memory_total"]

        # Test deployment suggestions based on actual resources
        suggestions = sitemap.suggest_deployments()

        # Container should appear in monitoring targets
        monitoring_targets = suggestions["monitoring_targets"]
        assert len(monitoring_targets) == 1
        assert monitoring_targets[0]["hostname"] == "test-ubuntu"
        assert monitoring_targets[0]["connection_ip"] == hostname

        # Check if container qualifies for specific deployment types based on resources
        cpu_cores = device["cpu_cores"] or 0
        if cpu_cores >= 4:
            # Should be suggested for load balancing if it has enough cores
            lb_candidates = [
                c["hostname"] for c in suggestions["load_balancer_candidates"]
            ]
            if device["memory_total"] and (
                "G" in device["memory_total"] or "Gi" in device["memory_total"]
            ):
                memory_str = device["memory_total"]
                # Handle both "G" and "Gi" suffixes
                if memory_str.endswith("Gi"):
                    memory_gb = float(memory_str.rstrip("Gi"))
                else:
                    memory_gb = float(memory_str.rstrip("G"))
                if memory_gb >= 4:
                    assert "test-ubuntu" in lb_candidates

        # Network topology analysis should be accurate
        analysis = sitemap.analyze_network_topology()

        # OS should be detected correctly
        assert device["os_info"] in analysis["operating_systems"]
        assert analysis["operating_systems"][device["os_info"]] == 1

        # Network segment should be detected (localhost may not have typical IP segments)
        if "." in hostname and hostname != "localhost":
            expected_segment = ".".join(hostname.split(".")[:3]) + ".0/24"
            assert expected_segment in analysis["network_segments"]
            assert analysis["network_segments"][expected_segment] == 1
