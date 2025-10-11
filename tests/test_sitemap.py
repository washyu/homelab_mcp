"""Tests for network sitemap functionality."""

import json
import pytest
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.homelab_mcp.sitemap import (
    NetworkSiteMap, 
    NetworkDevice, 
    discover_and_store, 
    bulk_discover_and_store
)


@pytest.fixture
def temp_db():
    """Create an in-memory database for testing."""
    yield ":memory:"


@pytest.fixture
def sitemap(temp_db):
    """Create a NetworkSiteMap instance with temporary database."""
    return NetworkSiteMap(db_path=temp_db, db_type='sqlite')


@pytest.fixture
def sample_ssh_discovery_success():
    """Sample successful SSH discovery output."""
    return json.dumps({
        "status": "success",
        "hostname": "test-server",
        "connection_ip": "192.168.1.100",
        "data": {
            "cpu": {
                "model": "Intel Core i7-9700K",
                "cores": "8"
            },
            "memory": {
                "total": "16G",
                "used": "8G",
                "free": "6G",
                "available": "12G"
            },
            "disk": {
                "filesystem": "/dev/sda1",
                "size": "1T",
                "used": "400G",
                "available": "500G",
                "use_percent": "45%",
                "mount": "/"
            },
            "network": [
                {
                    "name": "eth0",
                    "state": "UP",
                    "addresses": ["192.168.1.100"]
                }
            ],
            "uptime": "up 5 days, 2 hours, 30 minutes",
            "os": "Ubuntu 22.04.3 LTS"
        }
    })


@pytest.fixture
def sample_ssh_discovery_error():
    """Sample failed SSH discovery output."""
    return json.dumps({
        "status": "error",
        "connection_ip": "192.168.1.101",
        "error": "SSH authentication failed"
    })


class TestNetworkDevice:
    """Test NetworkDevice dataclass."""
    
    def test_network_device_creation(self):
        """Test creating a NetworkDevice instance."""
        device = NetworkDevice(
            hostname="test-host",
            connection_ip="192.168.1.10",
            last_seen="2024-01-01T12:00:00",
            status="success",
            cpu_model="Intel i7",
            cpu_cores=4
        )
        
        assert device.hostname == "test-host"
        assert device.connection_ip == "192.168.1.10"
        assert device.status == "success"
        assert device.cpu_cores == 4


class TestNetworkSiteMap:
    """Test NetworkSiteMap class."""
    
    def test_init_creates_database(self, temp_db):
        """Test that initialization creates database tables."""
        sitemap = NetworkSiteMap(db_path=temp_db, db_type='sqlite')
        
        # For in-memory database, just test that we can get empty devices list
        # This confirms the database was initialized successfully
        devices = sitemap.get_all_devices()
        assert devices == []
    
    def test_parse_discovery_output_success(self, sitemap, sample_ssh_discovery_success):
        """Test parsing successful SSH discovery output."""
        device = sitemap.parse_discovery_output(sample_ssh_discovery_success)
        
        assert device.hostname == "test-server"
        assert device.connection_ip == "192.168.1.100"
        assert device.status == "success"
        assert device.cpu_model == "Intel Core i7-9700K"
        assert device.cpu_cores == 8
        assert device.memory_total == "16G"
        assert device.memory_used == "8G"
        assert device.disk_size == "1T"
        assert device.disk_use_percent == "45%"
        assert device.os_info == "Ubuntu 22.04.3 LTS"
        assert device.uptime == "up 5 days, 2 hours, 30 minutes"
        
        # Test network interfaces are stored as JSON
        network_data = json.loads(device.network_interfaces)
        assert len(network_data) == 1
        assert network_data[0]["name"] == "eth0"
        assert network_data[0]["addresses"] == ["192.168.1.100"]
    
    def test_parse_discovery_output_error(self, sitemap, sample_ssh_discovery_error):
        """Test parsing failed SSH discovery output."""
        device = sitemap.parse_discovery_output(sample_ssh_discovery_error)
        
        assert device.connection_ip == "192.168.1.101"
        assert device.status == "error"
        assert device.error_message == "SSH authentication failed"
        assert device.cpu_model is None
        assert device.memory_total is None
    
    def test_parse_invalid_json(self, sitemap):
        """Test parsing invalid JSON creates error device."""
        device = sitemap.parse_discovery_output("invalid json")
        
        assert device.status == "error"
        assert "JSON parse error" in device.error_message
    
    def test_store_device_new(self, sitemap, sample_ssh_discovery_success):
        """Test storing a new device."""
        device = sitemap.parse_discovery_output(sample_ssh_discovery_success)
        device_id = sitemap.store_device(device)
        
        assert isinstance(device_id, int)
        assert device_id > 0
        
        # Verify device was stored
        devices = sitemap.get_all_devices()
        assert len(devices) == 1
        assert devices[0]["hostname"] == "test-server"
        assert devices[0]["cpu_cores"] == 8
    
    def test_store_device_update_existing(self, sitemap, sample_ssh_discovery_success):
        """Test updating an existing device."""
        # Store initial device
        device = sitemap.parse_discovery_output(sample_ssh_discovery_success)
        device_id1 = sitemap.store_device(device)
        
        # Update device with new information
        updated_data = json.loads(sample_ssh_discovery_success)
        updated_data["data"]["memory"]["used"] = "12G"  # Changed memory usage
        
        updated_device = sitemap.parse_discovery_output(json.dumps(updated_data))
        device_id2 = sitemap.store_device(updated_device)
        
        # Should be same device ID (updated, not new)
        assert device_id1 == device_id2
        
        # Verify only one device exists with updated info
        devices = sitemap.get_all_devices()
        assert len(devices) == 1
        assert devices[0]["memory_used"] == "12G"
    
    def test_store_discovery_history(self, sitemap, sample_ssh_discovery_success):
        """Test storing discovery history."""
        device = sitemap.parse_discovery_output(sample_ssh_discovery_success)
        device_id = sitemap.store_device(device)
        
        # Store history
        sitemap.store_discovery_history(device_id, sample_ssh_discovery_success)
        
        # Get history
        changes = sitemap.get_device_changes(device_id)
        assert len(changes) == 1
        assert changes[0]["data"]["hostname"] == "test-server"
    
    def test_store_discovery_history_duplicate_detection(self, sitemap, sample_ssh_discovery_success):
        """Test that duplicate discovery data is not stored."""
        device = sitemap.parse_discovery_output(sample_ssh_discovery_success)
        device_id = sitemap.store_device(device)
        
        # Store same history twice
        sitemap.store_discovery_history(device_id, sample_ssh_discovery_success)
        sitemap.store_discovery_history(device_id, sample_ssh_discovery_success)
        
        # Should only have one entry
        changes = sitemap.get_device_changes(device_id)
        assert len(changes) == 1
    
    def test_analyze_network_topology_empty(self, sitemap):
        """Test network analysis with no devices."""
        analysis = sitemap.analyze_network_topology()
        
        assert analysis["total_devices"] == 0
        assert analysis["online_devices"] == 0
        assert analysis["offline_devices"] == 0
        assert analysis["operating_systems"] == {}
        assert analysis["network_segments"] == {}
    
    def test_analyze_network_topology_with_devices(self, sitemap, sample_ssh_discovery_success):
        """Test network analysis with devices."""
        # Add a successful device
        device = sitemap.parse_discovery_output(sample_ssh_discovery_success)
        sitemap.store_device(device)
        
        # Add a failed device
        error_data = json.dumps({
            "status": "error",
            "connection_ip": "192.168.1.102",
            "error": "Connection timeout"
        })
        error_device = sitemap.parse_discovery_output(error_data)
        sitemap.store_device(error_device)
        
        analysis = sitemap.analyze_network_topology()
        
        assert analysis["total_devices"] == 2
        assert analysis["online_devices"] == 1
        assert analysis["offline_devices"] == 1
        assert "Ubuntu 22.04.3 LTS" in analysis["operating_systems"]
        assert analysis["operating_systems"]["Ubuntu 22.04.3 LTS"] == 1
        assert "192.168.1.0/24" in analysis["network_segments"]
    
    def test_suggest_deployments_empty(self, sitemap):
        """Test deployment suggestions with no devices."""
        suggestions = sitemap.suggest_deployments()
        
        assert suggestions["load_balancer_candidates"] == []
        assert suggestions["database_candidates"] == []
        assert suggestions["monitoring_targets"] == []
        assert suggestions["upgrade_recommendations"] == []
    
    def test_suggest_deployments_with_devices(self, sitemap):
        """Test deployment suggestions with capable devices."""
        # Create a high-spec device
        high_spec_data = {
            "status": "success",
            "hostname": "high-spec-server",
            "connection_ip": "192.168.1.200",
            "data": {
                "cpu": {"cores": "16"},
                "memory": {"total": "32G"},
                "disk": {"use_percent": "20%"},
                "os": "Ubuntu 22.04.3 LTS"
            }
        }
        
        device = sitemap.parse_discovery_output(json.dumps(high_spec_data))
        sitemap.store_device(device)
        
        suggestions = sitemap.suggest_deployments()
        
        # Should suggest this server for load balancing and database
        assert len(suggestions["load_balancer_candidates"]) == 1
        assert suggestions["load_balancer_candidates"][0]["hostname"] == "high-spec-server"
        assert len(suggestions["database_candidates"]) == 1
        assert suggestions["database_candidates"][0]["hostname"] == "high-spec-server"
        assert len(suggestions["monitoring_targets"]) == 1


class TestAsyncFunctions:
    """Test async discovery functions."""
    
    @pytest.mark.asyncio
    @patch('src.homelab_mcp.ssh_tools.ssh_discover_system')
    async def test_discover_and_store(self, mock_ssh_discover, temp_db, sample_ssh_discovery_success):
        """Test discover_and_store function."""
        mock_ssh_discover.return_value = sample_ssh_discovery_success
        
        sitemap = NetworkSiteMap(db_path=temp_db, db_type='sqlite')
        result = await discover_and_store(
            sitemap,
            hostname="test-host",
            username="test-user",
            password="test-pass"
        )
        
        # Verify SSH discovery was called
        mock_ssh_discover.assert_called_once_with(
            "test-host", "test-user", "test-pass", None, 22
        )
        
        # Verify result
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["hostname"] == "test-server"
        assert result_data["discovery_status"] == "success"
        assert "device_id" in result_data
        
        # Verify device was stored
        devices = sitemap.get_all_devices()
        assert len(devices) == 1
        assert devices[0]["hostname"] == "test-server"
    
    @pytest.mark.asyncio
    @patch('src.homelab_mcp.sitemap.discover_and_store')
    async def test_bulk_discover_and_store(self, mock_discover_and_store, temp_db):
        """Test bulk_discover_and_store function."""
        # Mock successful discovery
        mock_discover_and_store.return_value = json.dumps({
            "status": "success",
            "device_id": 1,
            "hostname": "test-host"
        })
        
        sitemap = NetworkSiteMap(db_path=temp_db, db_type='sqlite')
        targets = [
            {"hostname": "host1", "username": "user1", "password": "pass1"},
            {"hostname": "host2", "username": "user2", "password": "pass2"}
        ]
        
        result = await bulk_discover_and_store(sitemap, targets)
        
        # Verify both targets were processed
        assert mock_discover_and_store.call_count == 2
        
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["total_targets"] == 2
        assert len(result_data["results"]) == 2
    
    @pytest.mark.asyncio
    @patch('src.homelab_mcp.sitemap.discover_and_store')
    async def test_bulk_discover_and_store_with_errors(self, mock_discover_and_store, temp_db):
        """Test bulk discovery handling errors."""
        # Mock one success, one failure
        mock_discover_and_store.side_effect = [
            json.dumps({"status": "success", "device_id": 1, "hostname": "host1"}),
            Exception("Connection failed")
        ]
        
        sitemap = NetworkSiteMap(db_path=temp_db, db_type='sqlite')
        targets = [
            {"hostname": "host1", "username": "user1"},
            {"hostname": "host2", "username": "user2"}
        ]
        
        result = await bulk_discover_and_store(sitemap, targets)
        
        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["total_targets"] == 2
        assert len(result_data["results"]) == 2
        
        # First should succeed, second should have error
        assert result_data["results"][0]["status"] == "success"
        assert result_data["results"][1]["status"] == "error"
        assert "Connection failed" in result_data["results"][1]["error"]


class TestDatabaseOperations:
    """Test database-specific operations."""
    
    def test_database_schema_creation(self, temp_db):
        """Test that all required tables are created."""
        sitemap = NetworkSiteMap(db_path=temp_db, db_type='sqlite')
        
        # Use the existing database adapter connection
        cursor = sitemap.db_adapter.connection.cursor()
        
        # Check that devices table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='devices'")
        assert cursor.fetchone() is not None
        
        # Check that discovery_history table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='discovery_history'")
        assert cursor.fetchone() is not None
        
        # Check that indexes exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]
        assert any("idx_devices_hostname_ip" in idx for idx in indexes)
        assert any("idx_history_device_id" in idx for idx in indexes)
    
    def test_device_unique_constraint(self, sitemap, sample_ssh_discovery_success):
        """Test that hostname+connection_ip combination is unique."""
        device = sitemap.parse_discovery_output(sample_ssh_discovery_success)
        
        # Store device twice - should update, not create duplicate
        device_id1 = sitemap.store_device(device)
        device_id2 = sitemap.store_device(device)
        
        assert device_id1 == device_id2
        
        devices = sitemap.get_all_devices()
        assert len(devices) == 1
    
    def test_get_device_changes_limit(self, sitemap, sample_ssh_discovery_success):
        """Test limiting device change history."""
        device = sitemap.parse_discovery_output(sample_ssh_discovery_success)
        device_id = sitemap.store_device(device)
        
        # Store multiple different discovery results
        for i in range(5):
            modified_data = json.loads(sample_ssh_discovery_success)
            modified_data["data"]["memory"]["used"] = f"{i+4}G"
            sitemap.store_discovery_history(device_id, json.dumps(modified_data))
        
        # Test limit
        changes = sitemap.get_device_changes(device_id, limit=3)
        assert len(changes) <= 3
        
        # Test default limit
        changes = sitemap.get_device_changes(device_id)
        assert len(changes) <= 10