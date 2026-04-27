"""Tests for network sitemap functionality."""

import json
from unittest.mock import patch

import pytest

from src.homelab_mcp.sitemap import (
    NetworkDevice,
    NetworkSiteMap,
    bulk_discover_and_store,
    discover_and_store,
)


@pytest.fixture
def temp_db():
    """Create an in-memory database for testing."""
    yield ":memory:"


@pytest.fixture
def sitemap(temp_db):
    """Create a NetworkSiteMap instance with temporary database."""
    return NetworkSiteMap(db_path=temp_db, db_type="sqlite")


@pytest.fixture
def sample_ssh_discovery_success():
    """Sample successful SSH discovery output."""
    return json.dumps(
        {
            "status": "success",
            "hostname": "test-server",
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
                "fingerprint": {
                    "kernel_name": "Linux",
                    "kernel_version": "6.5.13-1-pve",
                    "os_name": "Proxmox VE 8.2.4",
                    "os_version": "8.2.4",
                    "package_fingerprint": "sha256:abc123def456",
                },
            },
        }
    )


@pytest.fixture
def sample_ssh_discovery_error():
    """Sample failed SSH discovery output."""
    return json.dumps(
        {
            "status": "error",
            "connection_ip": "192.168.1.101",
            "error": "SSH authentication failed",
        }
    )


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
            cpu_cores=4,
        )

        assert device.hostname == "test-host"
        assert device.connection_ip == "192.168.1.10"
        assert device.status == "success"
        assert device.cpu_cores == 4


class TestNetworkSiteMap:
    """Test NetworkSiteMap class."""

    def test_init_creates_database(self, temp_db):
        """Test that initialization creates database tables."""
        sitemap = NetworkSiteMap(db_path=temp_db, db_type="sqlite")

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

    def test_parse_discovery_output_fingerprint_phase38(self, sitemap, sample_ssh_discovery_success):
        """Phase 38 D-04c: parse_discovery_output stores fingerprint as JSON string."""
        device = sitemap.parse_discovery_output(sample_ssh_discovery_success)
        assert device.fingerprint is not None, "fingerprint should be populated from data['fingerprint']"
        fp = json.loads(device.fingerprint)
        assert fp["kernel_name"] == "Linux"
        assert fp["kernel_version"] == "6.5.13-1-pve"
        assert fp["os_name"] == "Proxmox VE 8.2.4"
        assert fp["os_version"] == "8.2.4"
        assert fp["package_fingerprint"] == "sha256:abc123def456"

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
        error_data = json.dumps(
            {
                "status": "error",
                "connection_ip": "192.168.1.102",
                "error": "Connection timeout",
            }
        )
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
                "os": "Ubuntu 22.04.3 LTS",
            },
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
    @patch("src.homelab_mcp.ssh_tools.ssh_discover_system")
    async def test_discover_and_store(self, mock_ssh_discover, temp_db, sample_ssh_discovery_success):
        """Test discover_and_store function."""
        mock_ssh_discover.return_value = sample_ssh_discovery_success

        sitemap = NetworkSiteMap(db_path=temp_db, db_type="sqlite")
        result = await discover_and_store(sitemap, hostname="test-host", username="test-user", password="test-pass")

        # Verify SSH discovery was called
        mock_ssh_discover.assert_called_once_with("test-host", "test-user", "test-pass", None, 22)

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
    @patch("src.homelab_mcp.sitemap.discover_and_store")
    async def test_bulk_discover_and_store(self, mock_discover_and_store, temp_db):
        """Test bulk_discover_and_store function."""
        # Mock successful discovery
        mock_discover_and_store.return_value = json.dumps(
            {"status": "success", "device_id": 1, "hostname": "test-host"}
        )

        sitemap = NetworkSiteMap(db_path=temp_db, db_type="sqlite")
        targets = [
            {"hostname": "host1", "username": "user1", "password": "pass1"},
            {"hostname": "host2", "username": "user2", "password": "pass2"},
        ]

        result = await bulk_discover_and_store(sitemap, targets)

        # Verify both targets were processed
        assert mock_discover_and_store.call_count == 2

        result_data = json.loads(result)
        assert result_data["status"] == "success"
        assert result_data["total_targets"] == 2
        assert len(result_data["results"]) == 2

    @pytest.mark.asyncio
    @patch("src.homelab_mcp.sitemap.discover_and_store")
    async def test_bulk_discover_and_store_with_errors(self, mock_discover_and_store, temp_db):
        """Test bulk discovery handling errors."""
        # Mock one success, one failure
        mock_discover_and_store.side_effect = [
            json.dumps({"status": "success", "device_id": 1, "hostname": "host1"}),
            Exception("Connection failed"),
        ]

        sitemap = NetworkSiteMap(db_path=temp_db, db_type="sqlite")
        targets = [
            {"hostname": "host1", "username": "user1"},
            {"hostname": "host2", "username": "user2"},
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

    def test_sitemap_signature_has_no_mcp_admin_default(self) -> None:
        """D-06: discover_and_store must not default username to 'mcp_admin'.

        Phase 33.1 Plan 04 — signature introspection guard. The literal
        ``"mcp_admin"`` default is gone; the parameter defaults to ``None`` so
        the ssh_tools resolver's registry-scan branch (Plan 01) picks the
        registered user from the keyring.
        """
        import inspect

        from src.homelab_mcp.sitemap import discover_and_store

        sig = inspect.signature(discover_and_store)
        assert sig.parameters["username"].default is None, (
            f"D-06: discover_and_store username default must be None, not {sig.parameters['username'].default!r}"
        )

    @pytest.mark.asyncio
    async def test_discover_and_store_passes_none_username_when_omitted(self, monkeypatch, temp_db) -> None:
        """D-06/D-07: omitting username passes None through to ssh_discover_system.

        sitemap.discover_and_store lazy-imports ssh_discover_system from the
        ssh_tools module, so we monkeypatch the attribute on that module.
        """
        import src.homelab_mcp.ssh_tools as ssh_tools_mod

        captured: dict = {}

        async def fake_ssh_discover(hostname, username, password, key_path, port):
            captured["hostname"] = hostname
            captured["username"] = username
            captured["password"] = password
            captured["key_path"] = key_path
            captured["port"] = port
            return json.dumps(
                {
                    "status": "success",
                    "hostname": "h.example.com",
                    "connection_ip": "10.0.0.5",
                    "data": {},
                }
            )

        monkeypatch.setattr(ssh_tools_mod, "ssh_discover_system", fake_ssh_discover)

        sitemap = NetworkSiteMap(db_path=temp_db, db_type="sqlite")
        await discover_and_store(sitemap, hostname="h.example.com")

        assert captured["username"] is None, f"D-06: expected username=None when omitted; got {captured['username']!r}"
        assert captured["hostname"] == "h.example.com"
        assert captured["password"] is None
        assert captured["key_path"] is None
        assert captured["port"] == 22

    @pytest.mark.asyncio
    async def test_bulk_discover_and_store_passes_none_username_when_omitted(self, monkeypatch, temp_db) -> None:
        """D-07: bulk target with no 'username' key flows None down to
        ssh_discover_system — no silent 'mcp_admin' fallback from
        ``target.get("username", "mcp_admin")``.
        """
        import src.homelab_mcp.ssh_tools as ssh_tools_mod

        captured_calls: list[dict] = []

        async def fake_ssh_discover(hostname, username, password, key_path, port):
            captured_calls.append(
                {
                    "hostname": hostname,
                    "username": username,
                    "password": password,
                    "key_path": key_path,
                    "port": port,
                }
            )
            return json.dumps(
                {
                    "status": "success",
                    "hostname": hostname,
                    "connection_ip": "10.0.0.5",
                    "data": {},
                }
            )

        monkeypatch.setattr(ssh_tools_mod, "ssh_discover_system", fake_ssh_discover)

        sitemap = NetworkSiteMap(db_path=temp_db, db_type="sqlite")
        # Omit 'username' from target — bulk path must pass None, not 'mcp_admin'.
        await bulk_discover_and_store(sitemap, [{"hostname": "h.example.com"}])

        assert len(captured_calls) == 1
        assert captured_calls[0]["username"] is None, (
            "D-07: bulk_discover_and_store must propagate target.get('username') "
            f"as None when omitted; got {captured_calls[0]['username']!r}"
        )

    @pytest.mark.asyncio
    async def test_discover_and_store_resolves_username_from_keyring(self, monkeypatch, temp_db) -> None:
        """End-to-end proof (WARNING 4): monkeypatches ONLY the keyring boundary
        (list_credentials + get_credential) and the SSH boundary (ssh_connect).
        The full stack ``discover_and_store -> ssh_discover_system ->
        resolve_ssh_credentials -> _resolve_username_from_registry -> ssh_connect``
        executes for real — proving the keyring-registered username reaches the
        SSH connection layer without a literal ``mcp_admin`` intermediary.
        """
        from unittest.mock import AsyncMock, MagicMock

        import src.homelab_mcp.ssh_tools as ssh_tools_mod

        # 1. Register a single keyring entry for the hostname (D-04 single-match).
        def fake_list_credentials(credential_type: str = "ssh"):
            return [
                {
                    "hostname": "h.example.com",
                    "username": "alice",
                    "credential_type": "ssh",
                    "auth_type": "password",
                }
            ]

        def fake_get_credential(hostname, username, credential_type="ssh"):
            if hostname == "h.example.com" and username == "alice":
                return "keyring-password"
            return None

        monkeypatch.setattr(ssh_tools_mod, "list_credentials", fake_list_credentials)
        monkeypatch.setattr(ssh_tools_mod, "get_credential", fake_get_credential)

        # 2. Spy the SSH boundary — ssh_connect is imported into ssh_tools
        # at module load; monkeypatch that attribute so no real network call.
        captured_ssh_kwargs: dict = {}

        async def fake_ssh_connect(*args, **kwargs):
            captured_ssh_kwargs.update(kwargs)
            # Return an async-context-manager-compatible mock connection.
            conn = MagicMock()
            conn.__aenter__ = AsyncMock(return_value=conn)
            conn.__aexit__ = AsyncMock(return_value=False)
            # ssh_discover_system only calls conn.run(...) and inspects
            # .exit_status / .stdout. Return a benign non-zero so the
            # discovery body short-circuits cleanly without demanding a
            # full shape from every command.
            benign = MagicMock()
            benign.exit_status = 1
            benign.stdout = ""
            conn.run = AsyncMock(return_value=benign)
            return conn

        monkeypatch.setattr(ssh_tools_mod, "ssh_connect", fake_ssh_connect)

        sitemap = NetworkSiteMap(db_path=temp_db, db_type="sqlite")

        # 3. Act — call with hostname ONLY. The full resolver stack must
        # execute and land the keyring-registered username at ssh_connect.
        await discover_and_store(sitemap, hostname="h.example.com")

        # 4. Assert the SSH boundary saw the keyring-registered credentials.
        assert captured_ssh_kwargs.get("username") == "alice", (
            "end-to-end: expected keyring-registered username 'alice' at "
            f"ssh_connect; got {captured_ssh_kwargs.get('username')!r}"
        )
        assert captured_ssh_kwargs.get("password") == "keyring-password", (
            "end-to-end: expected keyring-registered password at ssh_connect; "
            f"got {captured_ssh_kwargs.get('password')!r}"
        )
        assert captured_ssh_kwargs.get("hostname") == "h.example.com"


class TestDatabaseOperations:
    """Test database-specific operations."""

    def test_database_schema_creation(self, temp_db):
        """Test that all required tables are created."""
        sitemap = NetworkSiteMap(db_path=temp_db, db_type="sqlite")

        # Use the existing database adapter connection
        cursor = sitemap.db_adapter.connection.cursor()

        # Check that devices table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='devices'")
        assert cursor.fetchone() is not None

        # Check that discovery_history table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='discovery_history'")
        assert cursor.fetchone() is not None

        # Check that indexes exist
        # Phase 35 D-01: composite idx_devices_hostname_ip was replaced by the
        # non-unique hostname-alone idx_devices_hostname (store_device now
        # matches on hostname alone — see Plan 03).
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]
        assert any("idx_devices_hostname" in idx for idx in indexes)
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
            modified_data["data"]["memory"]["used"] = f"{i + 4}G"
            sitemap.store_discovery_history(device_id, json.dumps(modified_data))

        # Test limit
        changes = sitemap.get_device_changes(device_id, limit=3)
        assert len(changes) <= 3

        # Test default limit
        changes = sitemap.get_device_changes(device_id)
        assert len(changes) <= 10


# ─────────────────────────────────────────────────────────────────────────────
# Phase 35 functional tests (D-17d parallelism + D-17e analyzer null-skip)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_discover_and_store_runs_in_parallel_phase35(tmp_path, monkeypatch):
    """D-17d: bulk_discover_and_store completes in ~1.5x single-host timeout (CONTEXT D-17d).

    Per CONTEXT D-17d, parallelism with Semaphore(10) means 10 unreachable hosts complete
    in ~1.5x single-host timeout, not 10x. We bound at 4.0s (4x ideal 1.0s) to absorb
    Windows CI noise and emit_progress stdout overhead while still proving parallel execution.
    """
    import asyncio as _asyncio
    import json as _json
    import time

    from src.homelab_mcp import sitemap as _sitemap

    async def _slow_discover(sitemap, hostname, username, password, key_path, port):
        await _asyncio.sleep(1.0)
        return _json.dumps({"status": "error", "hostname": hostname, "error": "unreachable"})

    monkeypatch.setattr(_sitemap, "discover_and_store", _slow_discover)

    targets = [{"hostname": f"unreachable-{i}.example"} for i in range(10)]
    sitemap_instance = _sitemap.NetworkSiteMap(db_path=str(tmp_path / "p35_d17d.db"), db_type="sqlite")

    start = time.monotonic()
    result_str = await _sitemap.bulk_discover_and_store(sitemap_instance, targets)
    elapsed = time.monotonic() - start

    result = _json.loads(result_str)
    assert result["total_targets"] == 10
    assert len(result["results"]) == 10
    # W3: 4.0s bound absorbs Windows CI noise (emit_progress stdout + asyncio.Lock
    # contention + scheduler jitter). Serial execution would take 10.0s.
    assert elapsed < 4.0, (
        f"Phase 35 D-17d regression: bulk_discover_and_store took {elapsed:.2f}s "
        f"for 10 × 1s sleeps — parallelism (Semaphore(10) + gather) appears broken"
    )


def test_analyzers_skip_null_cpu_cores_device_phase35(tmp_path):
    """Phase 35 D-17e: a device with cpu_cores=None MUST NOT appear in
    analyze_network_topology's low_resources list NOR in suggest_deployments's
    upgrade_recommendations list (false-positive fix via D-11 helper).
    """
    from src.homelab_mcp import sitemap as _sitemap

    sm = _sitemap.NetworkSiteMap(db_path=str(tmp_path / "p35_d17e.db"), db_type="sqlite")

    sm.store_device(
        _sitemap.NetworkDevice(
            hostname="full-device",
            connection_ip="10.0.0.10",
            last_seen="2026-01-01T00:00:00",
            status="success",
            cpu_cores=1,
            memory_total="2Gi",
            os_info="Debian 12",
        )
    )
    sm.store_device(
        _sitemap.NetworkDevice(
            hostname="null-cpu-device",
            connection_ip="10.0.0.11",
            last_seen="2026-01-01T00:00:00",
            status="success",
            cpu_cores=None,
            memory_total=None,
            os_info="Debian 12",
        )
    )

    topology = sm.analyze_network_topology()
    suggestions = sm.suggest_deployments()

    low_resource_hostnames = {entry["hostname"] for entry in topology["resource_utilization"]["low_resources"]}
    upgrade_hostnames = {entry["hostname"] for entry in suggestions["upgrade_recommendations"]}

    assert "null-cpu-device" not in low_resource_hostnames, (
        "Phase 35 D-17e regression: analyze_network_topology included a "
        "device with cpu_cores=None in low_resources (false positive — "
        "D-10/D-13 coercion still happening somewhere)"
    )
    assert "null-cpu-device" not in upgrade_hostnames, (
        "Phase 35 D-17e regression: suggest_deployments recommended upgrading "
        "a device with cpu_cores=None (false positive — the None → 0 "
        "coercion pattern must have returned)"
    )


# ─────────────────────────────────────────────────────────────────────────────
# v1.6.x post-milestone regression tests for memory/disk format and analyzer
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_memory_gb_handles_raw_bytes(tmp_path):
    """Producer now emits raw byte ints; parser must accept them.

    SQLite TEXT columns coerce ints to digit strings on store; both forms
    must round-trip cleanly through ``_parse_memory_gb``.
    """
    sm = NetworkSiteMap(db_path=str(tmp_path / "fmt.db"), db_type="sqlite")

    # Raw int (in-memory dict from new producer)
    assert sm._parse_memory_gb(8 * 1024**3) == pytest.approx(8.0, rel=1e-3)
    # Digit string (after SQLite TEXT coercion)
    assert sm._parse_memory_gb(str(8 * 1024**3)) == pytest.approx(8.0, rel=1e-3)
    # Legacy "Gi" string (pre-fix rows that haven't been re-discovered yet)
    assert sm._parse_memory_gb("8Gi") == pytest.approx(8.0, rel=1e-3)
    # Legacy "G" string
    assert sm._parse_memory_gb("8G") == pytest.approx(8.0, rel=1e-3)
    # Sub-GiB precision (the bug #18 case)
    assert sm._parse_memory_gb(360 * 1024**2) == pytest.approx(0.351, rel=1e-2)
    # Empty / None / garbage
    assert sm._parse_memory_gb(None) == 0.0
    assert sm._parse_memory_gb("") == 0.0
    assert sm._parse_memory_gb("not-a-size") == 0.0


def test_analyzer_flags_high_memory_usage(tmp_path):
    """Bug #14: pve2 with 86% memory pressure must appear in high_memory_usage."""
    sm = NetworkSiteMap(db_path=str(tmp_path / "memhi.db"), db_type="sqlite")

    # Simulate post-fix producer output: raw byte ints
    sm.store_device(
        NetworkDevice(
            hostname="pve2",
            connection_ip="10.0.0.21",
            last_seen="2026-04-25T00:00:00",
            status="success",
            cpu_model="AMD EPYC",
            cpu_cores=32,
            memory_total=str(7 * 1024**3),  # 7 GiB
            memory_used=str(6 * 1024**3),  # 6 GiB used = 85.7%
            memory_available=str(1 * 1024**3),
            os_info="Debian 13",
        )
    )

    topology = sm.analyze_network_topology()
    high_mem = topology["resource_utilization"]["high_memory_usage"]
    assert any(entry["hostname"] == "pve2" for entry in high_mem), (
        f"Bug #14 regression: pve2 at 85.7% memory not flagged in high_memory_usage; got {high_mem}"
    )


def test_analyzer_renders_null_cpu_model_as_unknown(tmp_path):
    """Bug #16: device with null cpu_model must bucket as 'Unknown', not 'null'.

    Prior regression: ``device.get("cpu_model", "Unknown")`` only fell back to
    "Unknown" when the key was MISSING — when the key existed with value None
    (as Pi 4 currently does for ARM CPUs), it returned None which JSON-serialized
    as the literal string "null" in the cpu_architectures bucket.
    """
    sm = NetworkSiteMap(db_path=str(tmp_path / "nullcpu.db"), db_type="sqlite")

    sm.store_device(
        NetworkDevice(
            hostname="pi-dac",
            connection_ip="10.0.0.84",
            last_seen="2026-04-25T00:00:00",
            status="success",
            cpu_model=None,  # ARM Pi 4: cpu_model parser couldn't extract
            cpu_cores=4,
            memory_total=str(4 * 1024**3),
            memory_used=str(1 * 1024**3),
            os_info="Debian 12",
        )
    )

    topology = sm.analyze_network_topology()
    arches = topology["cpu_architectures"]
    assert "null" not in arches, f"Bug #16 regression: 'null' key in cpu_architectures: {arches}"
    assert arches.get("Unknown") == 1, f"Expected one Unknown CPU; got {arches}"


# ─────────────────────────────────────────────────────────────────────────────
# purge_failed_discoveries — sitemap CRUD completion (v1.6.x)
# ─────────────────────────────────────────────────────────────────────────────


def test_purge_failed_discoveries_removes_error_and_zombie_rows(tmp_path):
    """purge_failed_devices must remove status='error' rows AND degenerate-hostname
    rows, leave successful rows untouched, and clean up corresponding history rows.
    """
    sm = NetworkSiteMap(db_path=str(tmp_path / "purge.db"), db_type="sqlite")

    # Healthy row — must survive
    healthy_id = sm.store_device(
        NetworkDevice(
            hostname="pve",
            connection_ip="10.0.0.20",
            last_seen="2026-04-25T00:00:00",
            status="success",
            cpu_cores=64,
        )
    )
    sm.store_discovery_history(healthy_id, '{"hello":"world"}')

    # Error row — must be purged
    error_id = sm.store_device(
        NetworkDevice(
            hostname="bad-host",
            connection_ip="10.0.0.99",
            last_seen="2026-04-25T00:00:00",
            status="error",
            error_message="Connection refused",
        )
    )
    sm.store_discovery_history(error_id, '{"err":"refused"}')

    # Zombie row — empty hostname, status='error', no IP. Classic id=1 case.
    zombie_id = sm.store_device(
        NetworkDevice(
            hostname="",
            connection_ip="unknown",
            last_seen="2026-04-25T00:00:00",
            status="error",
            error_message="No hostname resolved",
        )
    )

    # Dry run — return candidates without modifying
    candidates = sm.purge_failed_devices(dry_run=True)
    candidate_ids = {row["id"] for row in candidates}
    assert candidate_ids == {error_id, zombie_id}, candidates
    assert len(sm.get_all_devices()) == 3, "dry_run must not delete"

    # Live run — actual delete
    purged = sm.purge_failed_devices(dry_run=False)
    purged_ids = {row["id"] for row in purged}
    assert purged_ids == {error_id, zombie_id}, purged

    surviving = sm.get_all_devices()
    assert len(surviving) == 1, surviving
    assert surviving[0]["id"] == healthy_id

    # History for the deleted devices must also be gone (no orphan FK)
    assert sm.get_device_changes(error_id) == []
    # Healthy device's history is preserved
    assert len(sm.get_device_changes(healthy_id)) == 1

    # Idempotent: re-running on a clean state returns []
    assert sm.purge_failed_devices(dry_run=False) == []


def test_purge_failed_discoveries_handler_dry_run_default_false(tmp_path, monkeypatch):
    """Tool handler defaults dry_run to false and returns the expected JSON shape."""
    import asyncio
    import json

    from src.homelab_mcp.tool_handlers.network_handlers import handle_purge_failed_discoveries

    # Force the handler's NetworkSiteMap() to use our temp DB instead of ~/.mcp/sitemap.db
    db_path = str(tmp_path / "handler.db")
    sm_init = NetworkSiteMap(db_path=db_path, db_type="sqlite")
    sm_init.store_device(
        NetworkDevice(
            hostname="",
            connection_ip="unknown",
            last_seen="2026-04-25T00:00:00",
            status="error",
            error_message="probe failed",
        )
    )

    # Patch NetworkSiteMap inside the handler module to point at our temp DB
    monkeypatch.setattr(
        "src.homelab_mcp.tool_handlers.network_handlers.NetworkSiteMap",
        lambda: NetworkSiteMap(db_path=db_path, db_type="sqlite"),
    )

    # Default args (no dry_run kwarg) → dry_run=false → actually deletes
    result = asyncio.run(handle_purge_failed_discoveries({}))
    payload = json.loads(result["content"][0]["text"])
    assert payload["status"] == "success"
    assert payload["dry_run"] is False
    assert payload["purged_count"] == 1
    assert len(payload["purged_devices"]) == 1
    assert payload["purged_devices"][0]["status"] == "error"

    # Subsequent call returns 0 — idempotent
    result2 = asyncio.run(handle_purge_failed_discoveries({"dry_run": True}))
    payload2 = json.loads(result2["content"][0]["text"])
    assert payload2["purged_count"] == 0
    assert payload2["dry_run"] is True


# ---------------------------------------------------------------------------
# Phase 38.1 R7: eligibility field round-trip via NetworkSiteMap (Task 2 TDD)
# ---------------------------------------------------------------------------


def test_eligibility_field_phase381(temp_db):
    """Phase 38.1 R7/D-10: NetworkSiteMap.get_sitemap rows must carry eligibility:{ssh, proxmox}."""
    import asyncio
    from datetime import datetime

    from src.homelab_mcp.database import SQLiteAdapter

    sitemap = NetworkSiteMap(db_path=temp_db, db_type="sqlite")
    # Store a device directly via the adapter
    adapter: SQLiteAdapter = sitemap.db_adapter  # type: ignore[assignment]
    device_id = adapter.store_device({
        "hostname": "test-node",
        "connection_ip": "10.1.1.1",
        "last_seen": datetime.now().isoformat(),
        "status": "success",
    })

    # With no credential binding both flags should be False
    devices = adapter.get_all_devices()
    assert len(devices) == 1
    device = devices[0]
    assert "eligibility" in device, "get_all_devices must emit eligibility key"
    assert device["eligibility"]["ssh"] is False
    assert device["eligibility"]["proxmox"] is False

    # After binding ssh the flag should flip
    adapter.set_device_credential_binding(device_id, "ssh", "some-uuid")
    devices_after = adapter.get_all_devices()
    assert devices_after[0]["eligibility"]["ssh"] is True
    assert devices_after[0]["eligibility"]["proxmox"] is False


# ---------------------------------------------------------------------------
# Phase 38.1 R3 RED scaffold (Plan 01 Task 2): discover_and_store writes
# the registry entry's credential_id onto the devices row's ssh_credential_id
# column. Lands GREEN in Plan 08. Until then this test fails.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.homelab_mcp.ssh_tools.ssh_discover_system")
async def test_discover_writes_credential_id_phase381(
    mock_ssh_discover, temp_db, sample_ssh_discovery_success, tmp_path, monkeypatch,
):
    """R3: after discover_and_store, the devices row carries ssh_credential_id from the registry entry.

    Plan 08 (Wave 4) wires this side-effect — until then this test fails because
    discover_and_store never calls set_device_credential_binding with the resolver's UUID.
    """
    monkeypatch.setattr(
        "homelab_mcp.credential_store._REGISTRY_PATH", tmp_path / "registry.json"
    )
    from src.homelab_mcp.credential_store import register_credential

    cred_id = register_credential("test-host", "test-user", credential_type="ssh")
    assert isinstance(cred_id, str), "Plan 02 prerequisite: register_credential must return UUID"

    mock_ssh_discover.return_value = sample_ssh_discovery_success
    sitemap = NetworkSiteMap(db_path=temp_db, db_type="sqlite")

    await discover_and_store(
        sitemap, hostname="test-host", username="test-user", password="test-pass"
    )

    devices = sitemap.get_all_devices()
    assert len(devices) == 1
    row = devices[0]
    assert row.get("ssh_credential_id") == cred_id, (
        f"Phase 38.1 R3: expected ssh_credential_id={cred_id!r} on the discovered "
        f"devices row, got {row.get('ssh_credential_id')!r}. Plan 08 must wire "
        "set_device_credential_binding into discover_and_store's post-upsert side-effect."
    )
