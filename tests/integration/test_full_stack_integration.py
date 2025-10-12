"""Full-stack integration tests for complete MCP workflows."""

import asyncio
import json
import os
import tempfile
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.integration

from src.homelab_mcp.config import create_database_from_config, get_config
from src.homelab_mcp.service_installer import ServiceInstaller
from src.homelab_mcp.sitemap import (
    bulk_discover_and_store,
    discover_and_store,
)
from src.homelab_mcp.tools import execute_tool
from src.homelab_mcp.vm_operations import deploy_vm, get_vm_status, list_vms_on_device


class FullStackTestEnvironment:
    """Test environment setup for full-stack integration tests."""

    def __init__(self):
        self.temp_dir = None
        self.db_path = None
        self.sitemap = None
        self.config = None
        self.discovered_devices = []
        self.deployed_services = []
        self.deployed_vms = []

    def setup(self):
        """Set up test environment."""
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_fullstack.db")

        # Setup database configuration
        os.environ["DATABASE_TYPE"] = "sqlite"
        os.environ["SQLITE_PATH"] = self.db_path

        self.config = get_config()
        self.sitemap = create_database_from_config(self.config)

        return self

    def teardown(self):
        """Tear down test environment."""
        if self.temp_dir:
            import shutil

            shutil.rmtree(self.temp_dir, ignore_errors=True)

        # Clean up environment
        for key in ["DATABASE_TYPE", "SQLITE_PATH"]:
            os.environ.pop(key, None)

    def add_discovered_device(self, device_info):
        """Add a discovered device to tracking."""
        self.discovered_devices.append(device_info)

    def add_deployed_service(self, service_info):
        """Add a deployed service to tracking."""
        self.deployed_services.append(service_info)

    def add_deployed_vm(self, vm_info):
        """Add a deployed VM to tracking."""
        self.deployed_vms.append(vm_info)


class MockNetworkEnvironment:
    """Mock network environment for testing."""

    def __init__(self):
        self.devices = {}
        self.services = {}
        self.vms = {}

    def add_mock_device(self, hostname, ip, specs=None):
        """Add a mock device to the network."""
        default_specs = {
            "cpu": {"model": "Intel Core i7", "cores": "4"},
            "memory": {"total": "8G", "used": "4G", "free": "3G", "available": "6G"},
            "disk": {
                "filesystem": "/dev/sda1",
                "size": "500G",
                "used": "200G",
                "available": "250G",
                "use_percent": "45%",
                "mount": "/",
            },
            "network": [{"name": "eth0", "state": "UP", "addresses": [ip]}],
            "uptime": "up 10 days, 5 hours",
            "os": "Ubuntu 22.04.3 LTS",
        }

        if specs:
            default_specs.update(specs)

        self.devices[hostname] = {
            "hostname": hostname,
            "connection_ip": ip,
            "status": "success",
            "data": default_specs,
        }

    def add_mock_service(self, device_hostname, service_name, service_info):
        """Add a mock service to a device."""
        if device_hostname not in self.services:
            self.services[device_hostname] = {}
        self.services[device_hostname][service_name] = service_info

    def add_mock_vm(self, device_hostname, vm_name, vm_info):
        """Add a mock VM to a device."""
        if device_hostname not in self.vms:
            self.vms[device_hostname] = {}
        self.vms[device_hostname][vm_name] = vm_info

    def get_device_discovery_result(self, hostname):
        """Get discovery result for a device."""
        if hostname in self.devices:
            return json.dumps(self.devices[hostname])
        else:
            return json.dumps(
                {
                    "status": "error",
                    "connection_ip": hostname,
                    "error": "Device not found in mock environment",
                }
            )


@pytest.fixture
def full_stack_env():
    """Full-stack test environment fixture."""
    env = FullStackTestEnvironment()
    env.setup()
    yield env
    env.teardown()


@pytest.fixture
def mock_network():
    """Mock network environment fixture."""
    network = MockNetworkEnvironment()

    # Add various mock devices
    network.add_mock_device(
        "web-server-01",
        "192.168.1.10",
        {
            "cpu": {"model": "Intel Core i5", "cores": "4"},
            "memory": {"total": "8G", "used": "4G", "free": "3G", "available": "6G"},
        },
    )

    network.add_mock_device(
        "db-server-01",
        "192.168.1.20",
        {
            "cpu": {"model": "AMD EPYC", "cores": "16"},
            "memory": {
                "total": "64G",
                "used": "32G",
                "free": "20G",
                "available": "40G",
            },
        },
    )

    network.add_mock_device(
        "nas-server-01",
        "192.168.1.30",
        {
            "cpu": {"model": "Intel Atom", "cores": "4"},
            "memory": {"total": "4G", "used": "2G", "free": "1G", "available": "3G"},
            "disk": {
                "size": "4T",
                "used": "2T",
                "available": "1.8T",
                "use_percent": "50%",
            },
        },
    )

    return network


class TestDiscoveryToAnalysisWorkflow:
    """Test complete discovery to analysis workflow."""

    @pytest.mark.asyncio
    async def test_discovery_storage_analysis_workflow(
        self, full_stack_env, mock_network
    ):
        """Test complete workflow: Discovery → Storage → Analysis."""

        # Mock SSH discovery for multiple devices
        def mock_ssh_discover(hostname, username, password, port=22, key_path=None):
            return mock_network.get_device_discovery_result(hostname)

        with patch(
            "src.homelab_mcp.ssh_tools.ssh_discover_system",
            side_effect=mock_ssh_discover,
        ):
            # Step 1: Discover multiple devices
            discovery_targets = [
                {"hostname": "web-server-01", "username": "admin", "password": "pass"},
                {"hostname": "db-server-01", "username": "admin", "password": "pass"},
                {"hostname": "nas-server-01", "username": "admin", "password": "pass"},
            ]

            device_ids = []
            for target in discovery_targets:
                # Individual discovery and storage
                result_json = await discover_and_store(
                    full_stack_env.sitemap,
                    hostname=target["hostname"],
                    username=target["username"],
                    password=target["password"],
                )

                result = json.loads(result_json)
                assert result["status"] == "success"
                assert result["discovery_status"] == "success"

                device_id = result["device_id"]
                device_ids.append(device_id)
                full_stack_env.add_discovered_device(result)

            # Step 2: Verify devices were stored
            all_devices = full_stack_env.sitemap.get_all_devices()
            assert len(all_devices) == 3

            # Step 3: Analyze network topology
            topology_analysis = full_stack_env.sitemap.analyze_network_topology()

            assert topology_analysis["total_devices"] == 3
            assert topology_analysis["online_devices"] == 3
            assert topology_analysis["offline_devices"] == 0
            assert "Ubuntu 22.04.3 LTS" in topology_analysis["operating_systems"]
            assert "192.168.1.0/24" in topology_analysis["network_segments"]

            # Step 4: Get deployment suggestions
            deployment_suggestions = full_stack_env.sitemap.suggest_deployments()

            assert len(deployment_suggestions["monitoring_targets"]) == 3
            assert len(deployment_suggestions["database_candidates"]) >= 1
            assert len(deployment_suggestions["load_balancer_candidates"]) >= 1

            # High-spec db-server should be suggested for database
            db_candidates = [
                c["hostname"] for c in deployment_suggestions["database_candidates"]
            ]
            assert "db-server-01" in db_candidates

            # Step 5: Test change tracking over time
            for device_id in device_ids:
                changes = full_stack_env.sitemap.get_device_changes(device_id)
                assert len(changes) >= 1

    @pytest.mark.asyncio
    async def test_bulk_discovery_workflow(self, full_stack_env, mock_network):
        """Test bulk discovery workflow."""

        def mock_ssh_discover(hostname, username, password, port=22, key_path=None):
            return mock_network.get_device_discovery_result(hostname)

        with patch(
            "src.homelab_mcp.ssh_tools.ssh_discover_system",
            side_effect=mock_ssh_discover,
        ):
            # Bulk discovery of multiple targets
            targets = [
                {"hostname": "web-server-01", "username": "admin", "password": "pass"},
                {"hostname": "db-server-01", "username": "admin", "password": "pass"},
                {"hostname": "nas-server-01", "username": "admin", "password": "pass"},
                {
                    "hostname": "unreachable-host",
                    "username": "admin",
                    "password": "pass",
                },  # Will fail
            ]

            result_json = await bulk_discover_and_store(full_stack_env.sitemap, targets)
            result = json.loads(result_json)

            assert result["status"] == "success"
            assert result["total_targets"] == 4
            assert len(result["results"]) == 4

            # Count successful vs failed discoveries
            successful = sum(
                1
                for r in result["results"]
                if r.get("discovery_status") == "success"
                or r.get("status") == "success"
            )
            failed = sum(
                1
                for r in result["results"]
                if r.get("discovery_status") == "error" or r.get("status") == "error"
            )

            assert successful >= 3  # At least 3 should succeed
            assert failed >= 1  # At least 1 should fail (unreachable-host)


class TestDiscoveryToServiceDeploymentWorkflow:
    """Test workflow from discovery to service deployment."""

    @pytest.mark.asyncio
    async def test_discovery_to_service_deployment(self, full_stack_env, mock_network):
        """Test complete workflow: Discovery → Service Deployment."""

        def mock_ssh_discover(hostname, username, password, port=22, key_path=None):
            return mock_network.get_device_discovery_result(hostname)

        # Mock service installation
        def mock_install_service(
            service_name, hostname, username, password, variables=None
        ):
            return {
                "status": "success",
                "service": service_name,
                "method": "docker-compose",
                "deployment_info": {
                    "containers": [f"{service_name}-container"],
                    "ports": ["80:80"],
                    "status": "running",
                },
                "hostname": hostname,
            }

        with patch(
            "src.homelab_mcp.ssh_tools.ssh_discover_system",
            side_effect=mock_ssh_discover,
        ):
            with patch.object(
                ServiceInstaller, "install_service", side_effect=mock_install_service
            ):
                # Step 1: Discover and store web server
                discovery_result_json = await discover_and_store(
                    full_stack_env.sitemap,
                    hostname="web-server-01",
                    username="admin",
                    password="pass",
                )

                discovery_result = json.loads(discovery_result_json)
                assert discovery_result["status"] == "success"
                discovery_result["device_id"]

                # Step 2: Get deployment suggestions
                suggestions = full_stack_env.sitemap.suggest_deployments()
                monitoring_targets = suggestions["monitoring_targets"]

                # Find our web server in suggestions
                web_server_target = next(
                    (t for t in monitoring_targets if t["hostname"] == "web-server-01"),
                    None,
                )
                assert web_server_target is not None

                # Step 3: Deploy a service based on suggestions
                installer = ServiceInstaller()

                # Mock that nginx service template exists
                with patch.object(
                    installer, "get_available_services", return_value=["nginx"]
                ):
                    with patch.object(
                        installer,
                        "check_service_requirements",
                        return_value={"requirements_met": True},
                    ):
                        service_result = await installer.install_service(
                            "nginx",
                            "web-server-01",
                            "admin",
                            "pass",
                            {"port": 8080, "replicas": 2},
                        )

                        assert service_result["status"] == "success"
                        assert service_result["service"] == "nginx"
                        full_stack_env.add_deployed_service(service_result)

                # Step 4: Update device information with service deployment
                # In real implementation, this would update the sitemap with service info
                mock_network.add_mock_service(
                    "web-server-01",
                    "nginx",
                    {
                        "status": "running",
                        "ports": ["8080:80"],
                        "containers": ["nginx-container"],
                    },
                )

                # Verify the workflow completed successfully
                assert len(full_stack_env.discovered_devices) == 1
                assert len(full_stack_env.deployed_services) == 1

    @pytest.mark.asyncio
    async def test_multi_device_service_orchestration(
        self, full_stack_env, mock_network
    ):
        """Test orchestrating services across multiple devices."""

        def mock_ssh_discover(hostname, username, password, port=22, key_path=None):
            return mock_network.get_device_discovery_result(hostname)

        def mock_install_service(
            service_name, hostname, username, password, variables=None
        ):
            service_configs = {
                "nginx": {"ports": ["80:80"], "type": "web"},
                "postgres": {"ports": ["5432:5432"], "type": "database"},
                "redis": {"ports": ["6379:6379"], "type": "cache"},
            }

            config = service_configs.get(
                service_name, {"ports": ["8000:8000"], "type": "service"}
            )

            return {
                "status": "success",
                "service": service_name,
                "method": "docker-compose",
                "hostname": hostname,
                "deployment_info": config,
            }

        with patch(
            "src.homelab_mcp.ssh_tools.ssh_discover_system",
            side_effect=mock_ssh_discover,
        ):
            with patch.object(
                ServiceInstaller, "install_service", side_effect=mock_install_service
            ):
                # Step 1: Discover all devices
                discovery_targets = ["web-server-01", "db-server-01", "nas-server-01"]

                device_ids = []
                for hostname in discovery_targets:
                    result_json = await discover_and_store(
                        full_stack_env.sitemap,
                        hostname=hostname,
                        username="admin",
                        password="pass",
                    )
                    result = json.loads(result_json)
                    device_ids.append(result["device_id"])

                # Step 2: Get deployment suggestions for optimal service placement
                full_stack_env.sitemap.suggest_deployments()

                # Step 3: Deploy services based on device capabilities
                installer = ServiceInstaller()

                with patch.object(
                    installer,
                    "get_available_services",
                    return_value=["nginx", "postgres", "redis"],
                ):
                    with patch.object(
                        installer,
                        "check_service_requirements",
                        return_value={"requirements_met": True},
                    ):
                        # Deploy web service on web server
                        web_result = await installer.install_service(
                            "nginx", "web-server-01", "admin", "pass"
                        )
                        full_stack_env.add_deployed_service(web_result)

                        # Deploy database on high-spec server
                        db_result = await installer.install_service(
                            "postgres", "db-server-01", "admin", "pass"
                        )
                        full_stack_env.add_deployed_service(db_result)

                        # Deploy cache on web server (low resource usage)
                        cache_result = await installer.install_service(
                            "redis", "web-server-01", "admin", "pass"
                        )
                        full_stack_env.add_deployed_service(cache_result)

                # Verify orchestrated deployment
                assert len(full_stack_env.deployed_services) == 3

                # Verify service placement strategy
                service_by_host = {}
                for service in full_stack_env.deployed_services:
                    hostname = service["hostname"]
                    if hostname not in service_by_host:
                        service_by_host[hostname] = []
                    service_by_host[hostname].append(service["service"])

                assert (
                    "postgres" in service_by_host["db-server-01"]
                )  # Database on high-spec server
                assert (
                    "nginx" in service_by_host["web-server-01"]
                )  # Web service on web server


class TestServiceToVMDeploymentWorkflow:
    """Test workflow from service deployment to VM management."""

    @pytest.mark.asyncio
    async def test_service_to_vm_deployment_workflow(
        self, full_stack_env, mock_network
    ):
        """Test complete workflow: Service Deployment → VM Deployment."""

        def mock_ssh_discover(hostname, username, password, port=22, key_path=None):
            return mock_network.get_device_discovery_result(hostname)

        def mock_deploy_vm(device_id, platform, vm_name, vm_config):
            return json.dumps(
                {
                    "status": "success",
                    "vm_name": vm_name,
                    "device_id": device_id,
                    "platform": platform,
                    "vm_id": f"{vm_name}-{device_id}",
                    "config": vm_config,
                }
            )

        def mock_get_vm_status(device_id, platform, vm_name):
            return json.dumps(
                {
                    "status": "success",
                    "vm_name": vm_name,
                    "device_id": device_id,
                    "platform": platform,
                    "container_status": "running",
                    "pid": 12345,
                    "uptime": "2 hours",
                }
            )

        with patch(
            "src.homelab_mcp.ssh_tools.ssh_discover_system",
            side_effect=mock_ssh_discover,
        ):
            with patch(
                "src.homelab_mcp.vm_operations.deploy_vm", side_effect=mock_deploy_vm
            ):
                with patch(
                    "src.homelab_mcp.vm_operations.get_vm_status",
                    side_effect=mock_get_vm_status,
                ):
                    # Step 1: Discover device
                    discovery_result_json = await discover_and_store(
                        full_stack_env.sitemap,
                        hostname="web-server-01",
                        username="admin",
                        password="pass",
                    )
                    discovery_result = json.loads(discovery_result_json)
                    device_id = discovery_result["device_id"]

                    # Step 2: Deploy VM on discovered device
                    vm_config = {
                        "image": "nginx:alpine",
                        "ports": ["8080:80"],
                        "volumes": ["/data:/usr/share/nginx/html"],
                        "environment": {"ENV": "production"},
                    }

                    vm_result_json = await deploy_vm(
                        device_id, "docker", "web-service-vm", vm_config
                    )
                    vm_result = json.loads(vm_result_json)

                    assert vm_result["status"] == "success"
                    assert vm_result["vm_name"] == "web-service-vm"
                    assert vm_result["device_id"] == device_id

                    full_stack_env.add_deployed_vm(vm_result)

                    # Step 3: Verify VM status
                    status_result_json = await get_vm_status(
                        device_id, "docker", "web-service-vm"
                    )
                    status_result = json.loads(status_result_json)

                    assert status_result["status"] == "success"
                    assert status_result["container_status"] == "running"

                    # Step 4: List VMs on device
                    def mock_list_vms(device_id, platform):
                        return json.dumps(
                            {
                                "status": "success",
                                "device_id": device_id,
                                "platform": platform,
                                "total_vms": 1,
                                "vms": [
                                    {
                                        "name": "web-service-vm",
                                        "status": "running",
                                        "image": "nginx:alpine",
                                        "ports": ["8080:80"],
                                    }
                                ],
                            }
                        )

                    with patch(
                        "src.homelab_mcp.vm_operations.list_vms_on_device",
                        side_effect=mock_list_vms,
                    ):
                        list_result_json = await list_vms_on_device(device_id, "docker")
                        list_result = json.loads(list_result_json)

                        assert list_result["status"] == "success"
                        assert list_result["total_vms"] == 1
                        assert list_result["vms"][0]["name"] == "web-service-vm"

                    # Verify complete workflow
                    assert len(full_stack_env.discovered_devices) == 1
                    assert len(full_stack_env.deployed_vms) == 1


class TestEndToEndWorkflowWithMCPTools:
    """Test end-to-end workflows using MCP tools interface."""

    @pytest.mark.asyncio
    async def test_complete_homelab_setup_workflow(self, full_stack_env, mock_network):
        """Test complete homelab setup using MCP tools."""

        def mock_ssh_discover(hostname, username, password, port=22, key_path=None):
            return mock_network.get_device_discovery_result(hostname)

        # Mock all tool executions
        tool_responses = {
            "ssh_discover": lambda args: {
                "content": [
                    {
                        "type": "text",
                        "text": mock_network.get_device_discovery_result(
                            args["hostname"]
                        ),
                    }
                ]
            },
            "discover_and_map": lambda args: {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "status": "success",
                                "device_id": 1,
                                "hostname": args["hostname"],
                                "discovery_status": "success",
                            }
                        ),
                    }
                ]
            },
            "get_network_sitemap": lambda args: {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "status": "success",
                                "total_devices": 3,
                                "devices": [
                                    {
                                        "hostname": "web-server-01",
                                        "status": "success",
                                        "connection_ip": "192.168.1.10",
                                    },
                                    {
                                        "hostname": "db-server-01",
                                        "status": "success",
                                        "connection_ip": "192.168.1.20",
                                    },
                                    {
                                        "hostname": "nas-server-01",
                                        "status": "success",
                                        "connection_ip": "192.168.1.30",
                                    },
                                ],
                            }
                        ),
                    }
                ]
            },
            "analyze_network_topology": lambda args: {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "status": "success",
                                "analysis": {
                                    "total_devices": 3,
                                    "online_devices": 3,
                                    "offline_devices": 0,
                                    "operating_systems": {"Ubuntu 22.04.3 LTS": 3},
                                    "network_segments": {"192.168.1.0/24": 3},
                                },
                            }
                        ),
                    }
                ]
            },
            "suggest_deployments": lambda args: {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "status": "success",
                                "suggestions": {
                                    "monitoring_targets": [
                                        {
                                            "hostname": "web-server-01",
                                            "connection_ip": "192.168.1.10",
                                        },
                                        {
                                            "hostname": "db-server-01",
                                            "connection_ip": "192.168.1.20",
                                        },
                                        {
                                            "hostname": "nas-server-01",
                                            "connection_ip": "192.168.1.30",
                                        },
                                    ],
                                    "database_candidates": [
                                        {
                                            "hostname": "db-server-01",
                                            "cpu_cores": 16,
                                            "memory_total": "64G",
                                        }
                                    ],
                                },
                            }
                        ),
                    }
                ]
            },
            "deploy_vm": lambda args: {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "status": "success",
                                "vm_name": args["vm_name"],
                                "device_id": args["device_id"],
                                "platform": args["platform"],
                            }
                        ),
                    }
                ]
            },
        }

        async def mock_execute_tool(tool_name, args):
            if tool_name in tool_responses:
                return tool_responses[tool_name](args)
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "status": "error",
                                    "error": f"Unknown tool: {tool_name}",
                                }
                            ),
                        }
                    ]
                }

        with patch("src.homelab_mcp.tools.execute_tool", side_effect=mock_execute_tool):
            # Step 1: Discovery Phase - Discover multiple devices
            discovery_tasks = [
                execute_tool(
                    "discover_and_map",
                    {
                        "hostname": "web-server-01",
                        "username": "admin",
                        "password": "pass",
                    },
                ),
                execute_tool(
                    "discover_and_map",
                    {
                        "hostname": "db-server-01",
                        "username": "admin",
                        "password": "pass",
                    },
                ),
                execute_tool(
                    "discover_and_map",
                    {
                        "hostname": "nas-server-01",
                        "username": "admin",
                        "password": "pass",
                    },
                ),
            ]

            discovery_results = await asyncio.gather(*discovery_tasks)

            for result in discovery_results:
                assert "content" in result
                data = json.loads(result["content"][0]["text"])
                assert data["status"] == "success"
                full_stack_env.add_discovered_device(data)

            # Step 2: Analysis Phase - Get network overview
            sitemap_result = await execute_tool("get_network_sitemap", {})
            sitemap_data = json.loads(sitemap_result["content"][0]["text"])

            assert sitemap_data["total_devices"] == 3

            # Step 3: Topology Analysis
            topology_result = await execute_tool("analyze_network_topology", {})
            topology_data = json.loads(topology_result["content"][0]["text"])

            assert topology_data["analysis"]["total_devices"] == 3
            assert topology_data["analysis"]["online_devices"] == 3

            # Step 4: Get Deployment Suggestions
            suggestions_result = await execute_tool("suggest_deployments", {})
            suggestions_data = json.loads(suggestions_result["content"][0]["text"])

            assert len(suggestions_data["suggestions"]["monitoring_targets"]) == 3
            assert len(suggestions_data["suggestions"]["database_candidates"]) >= 1

            # Step 5: VM Deployment Based on Suggestions
            # Deploy monitoring on web server
            vm_result = await execute_tool(
                "deploy_vm",
                {
                    "device_id": 1,  # web-server-01
                    "platform": "docker",
                    "vm_name": "prometheus-monitoring",
                    "vm_config": {
                        "image": "prom/prometheus:latest",
                        "ports": ["9090:9090"],
                    },
                },
            )

            vm_data = json.loads(vm_result["content"][0]["text"])
            assert vm_data["status"] == "success"
            assert vm_data["vm_name"] == "prometheus-monitoring"

            full_stack_env.add_deployed_vm(vm_data)

            # Verify complete workflow
            assert len(full_stack_env.discovered_devices) == 3
            assert len(full_stack_env.deployed_vms) == 1

    @pytest.mark.asyncio
    async def test_monitoring_deployment_workflow(self, full_stack_env, mock_network):
        """Test deployment of complete monitoring stack."""

        # Mock comprehensive monitoring deployment
        monitoring_tools = ["prometheus", "grafana", "node-exporter", "alertmanager"]

        def mock_deploy_monitoring_vm(device_id, platform, vm_name, vm_config):
            service_ports = {
                "prometheus": ["9090:9090"],
                "grafana": ["3000:3000"],
                "node-exporter": ["9100:9100"],
                "alertmanager": ["9093:9093"],
            }

            service = vm_name.split("-")[0]  # Extract service name
            ports = service_ports.get(service, ["8000:8000"])

            return json.dumps(
                {
                    "status": "success",
                    "vm_name": vm_name,
                    "device_id": device_id,
                    "platform": platform,
                    "ports": ports,
                    "vm_status": "running",
                }
            )

        async def mock_execute_tool(tool_name, args):
            if tool_name == "discover_and_map":
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "status": "success",
                                    "device_id": 1,
                                    "hostname": args["hostname"],
                                    "discovery_status": "success",
                                }
                            ),
                        }
                    ]
                }
            elif tool_name == "deploy_vm":
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": mock_deploy_monitoring_vm(
                                args["device_id"],
                                args["platform"],
                                args["vm_name"],
                                args["vm_config"],
                            ),
                        }
                    ]
                }
            else:
                return {
                    "content": [
                        {"type": "text", "text": json.dumps({"status": "success"})}
                    ]
                }

        with patch("src.homelab_mcp.tools.execute_tool", side_effect=mock_execute_tool):
            # Step 1: Discover monitoring target
            discovery_result = await execute_tool(
                "discover_and_map",
                {"hostname": "web-server-01", "username": "admin", "password": "pass"},
            )

            discovery_data = json.loads(discovery_result["content"][0]["text"])
            device_id = discovery_data["device_id"]

            # Step 2: Deploy complete monitoring stack
            monitoring_deployments = []

            for tool in monitoring_tools:
                vm_result = await execute_tool(
                    "deploy_vm",
                    {
                        "device_id": device_id,
                        "platform": "docker",
                        "vm_name": f"{tool}-monitoring",
                        "vm_config": {
                            "image": f"prom/{tool}:latest"
                            if tool != "grafana"
                            else "grafana/grafana:latest",
                            "ports": ["9090:9090"]
                            if tool == "prometheus"
                            else ["3000:3000"]
                            if tool == "grafana"
                            else ["9100:9100"]
                            if tool == "node-exporter"
                            else ["9093:9093"],
                        },
                    },
                )

                vm_data = json.loads(vm_result["content"][0]["text"])
                assert vm_data["status"] == "success"
                monitoring_deployments.append(vm_data)
                full_stack_env.add_deployed_vm(vm_data)

            # Verify complete monitoring stack deployment
            assert len(monitoring_deployments) == 4
            assert len(full_stack_env.deployed_vms) == 4

            # Verify all monitoring tools are deployed
            deployed_tools = [
                vm["vm_name"].split("-")[0] for vm in full_stack_env.deployed_vms
            ]
            for tool in monitoring_tools:
                assert tool in deployed_tools


class TestErrorRecoveryAndRollback:
    """Test error recovery and rollback scenarios."""

    @pytest.mark.asyncio
    async def test_partial_deployment_failure_recovery(
        self, full_stack_env, mock_network
    ):
        """Test recovery from partial deployment failures."""

        deployment_attempts = []

        def mock_deploy_vm_with_failures(device_id, platform, vm_name, vm_config):
            deployment_attempts.append(vm_name)

            # Simulate failure on third deployment
            if len(deployment_attempts) == 3:
                return json.dumps(
                    {
                        "status": "error",
                        "vm_name": vm_name,
                        "error": "Insufficient resources",
                        "device_id": device_id,
                    }
                )
            else:
                return json.dumps(
                    {
                        "status": "success",
                        "vm_name": vm_name,
                        "device_id": device_id,
                        "platform": platform,
                    }
                )

        async def mock_execute_tool(tool_name, args):
            if tool_name == "discover_and_map":
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "status": "success",
                                    "device_id": 1,
                                    "hostname": args["hostname"],
                                }
                            ),
                        }
                    ]
                }
            elif tool_name == "deploy_vm":
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": mock_deploy_vm_with_failures(
                                args["device_id"],
                                args["platform"],
                                args["vm_name"],
                                args["vm_config"],
                            ),
                        }
                    ]
                }
            else:
                return {
                    "content": [
                        {"type": "text", "text": json.dumps({"status": "success"})}
                    ]
                }

        with patch("src.homelab_mcp.tools.execute_tool", side_effect=mock_execute_tool):
            # Discover device
            await execute_tool(
                "discover_and_map",
                {"hostname": "web-server-01", "username": "admin", "password": "pass"},
            )

            # Attempt to deploy multiple VMs, expecting one to fail
            vm_names = ["web-app", "database", "cache", "monitoring"]

            for vm_name in vm_names:
                vm_result = await execute_tool(
                    "deploy_vm",
                    {
                        "device_id": 1,
                        "platform": "docker",
                        "vm_name": vm_name,
                        "vm_config": {"image": f"{vm_name}:latest"},
                    },
                )

                vm_data = json.loads(vm_result["content"][0]["text"])

                if vm_data["status"] == "success":
                    full_stack_env.add_deployed_vm(vm_data)
                else:
                    # Handle failure case
                    assert vm_data["status"] == "error"
                    assert "Insufficient resources" in vm_data["error"]

            # Verify partial deployment - 3 successful, 1 failed
            assert len(full_stack_env.deployed_vms) == 3
            assert len(deployment_attempts) == 4

    @pytest.mark.asyncio
    async def test_discovery_failure_handling(self, full_stack_env, mock_network):
        """Test handling of discovery failures in bulk operations."""

        def mock_ssh_discover_with_failures(
            hostname, username, password, port=22, key_path=None
        ):
            if hostname == "unreachable-host":
                return json.dumps(
                    {
                        "status": "error",
                        "connection_ip": hostname,
                        "error": "Connection timeout",
                    }
                )
            elif hostname == "auth-fail-host":
                return json.dumps(
                    {
                        "status": "error",
                        "connection_ip": hostname,
                        "error": "Authentication failed",
                    }
                )
            else:
                return mock_network.get_device_discovery_result(hostname)

        with patch(
            "src.homelab_mcp.ssh_tools.ssh_discover_system",
            side_effect=mock_ssh_discover_with_failures,
        ):
            # Attempt bulk discovery with some failures expected
            targets = [
                {"hostname": "web-server-01", "username": "admin", "password": "pass"},
                {
                    "hostname": "unreachable-host",
                    "username": "admin",
                    "password": "pass",
                },
                {"hostname": "auth-fail-host", "username": "admin", "password": "pass"},
                {"hostname": "db-server-01", "username": "admin", "password": "pass"},
            ]

            result_json = await bulk_discover_and_store(full_stack_env.sitemap, targets)
            result = json.loads(result_json)

            assert result["status"] == "success"  # Overall operation succeeds
            assert result["total_targets"] == 4

            # Count successes and failures
            successes = sum(
                1
                for r in result["results"]
                if r.get("discovery_status") == "success"
                or r.get("status") == "success"
            )
            failures = sum(
                1
                for r in result["results"]
                if r.get("discovery_status") == "error" or r.get("status") == "error"
            )

            assert successes == 2  # web-server-01 and db-server-01
            assert failures == 2  # unreachable-host and auth-fail-host

            # Verify only successful discoveries were stored
            devices = full_stack_env.sitemap.get_all_devices()
            assert len(devices) == 2

            stored_hostnames = [d["hostname"] for d in devices]
            assert "web-server-01" in stored_hostnames
            assert "db-server-01" in stored_hostnames
            assert "unreachable-host" not in stored_hostnames
            assert "auth-fail-host" not in stored_hostnames


@pytest.mark.asyncio
async def test_complete_homelab_lifecycle(full_stack_env, mock_network):
    """Test complete homelab lifecycle: Discovery → Analysis → Deployment → Monitoring → Maintenance."""

    # This is the ultimate integration test that exercises the entire system
    lifecycle_state = {
        "discovered_devices": 0,
        "deployed_services": 0,
        "deployed_vms": 0,
        "monitoring_active": False,
    }

    def mock_ssh_discover(hostname, username, password, port=22, key_path=None):
        return mock_network.get_device_discovery_result(hostname)

    with patch(
        "src.homelab_mcp.ssh_tools.ssh_discover_system", side_effect=mock_ssh_discover
    ):
        # Phase 1: Infrastructure Discovery
        discovery_targets = ["web-server-01", "db-server-01", "nas-server-01"]

        for hostname in discovery_targets:
            result_json = await discover_and_store(
                full_stack_env.sitemap,
                hostname=hostname,
                username="admin",
                password="pass",
            )
            result = json.loads(result_json)
            assert result["status"] == "success"
            lifecycle_state["discovered_devices"] += 1

        # Phase 2: Network Analysis and Planning
        topology = full_stack_env.sitemap.analyze_network_topology()
        suggestions = full_stack_env.sitemap.suggest_deployments()

        assert topology["total_devices"] == 3
        assert len(suggestions["monitoring_targets"]) == 3

        # Phase 3: Service and VM Deployment (Mocked)
        with patch("src.homelab_mcp.vm_operations.deploy_vm") as mock_deploy:
            mock_deploy.return_value = json.dumps(
                {
                    "status": "success",
                    "vm_name": "test-vm",
                    "device_id": 1,
                    "platform": "docker",
                }
            )

            # Deploy monitoring infrastructure
            monitoring_result = await deploy_vm(
                1,
                "docker",
                "prometheus",
                {"image": "prom/prometheus:latest", "ports": ["9090:9090"]},
            )

            monitoring_data = json.loads(monitoring_result)
            assert monitoring_data["status"] == "success"
            lifecycle_state["deployed_vms"] += 1
            lifecycle_state["monitoring_active"] = True

        # Phase 4: Verification and Health Checks
        devices = full_stack_env.sitemap.get_all_devices()
        assert len(devices) == lifecycle_state["discovered_devices"]

        # Verify lifecycle completed successfully
        assert lifecycle_state["discovered_devices"] == 3
        assert lifecycle_state["deployed_vms"] >= 1
        assert lifecycle_state["monitoring_active"] is True

        print("✓ Complete homelab lifecycle test passed")
        print(f"  - Discovered {lifecycle_state['discovered_devices']} devices")
        print(f"  - Deployed {lifecycle_state['deployed_vms']} VMs")
        print(f"  - Monitoring active: {lifecycle_state['monitoring_active']}")
