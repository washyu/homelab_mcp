"""
Tests for ResourceManager connection lifecycle management.

Tests the centralized resource management for SSH, HTTP (Proxmox),
and database connections.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from src.homelab_mcp.resource_manager import ResourceManager


class TestResourceManagerInitialization:
    """Test ResourceManager construction and initialization."""

    def test_constructor_stores_config(self):
        """Test that ResourceManager stores config and starts uninitialized."""
        # GIVEN: A valid MCPConfig
        config = MagicMock()

        # WHEN: Creating a ResourceManager
        rm = ResourceManager(config)

        # THEN: Config is stored and manager is not initialized
        assert rm._config is config
        assert rm._initialized is False

    @pytest.mark.asyncio
    async def test_initialize_creates_session(self):
        """Test that initialize() creates aiohttp.ClientSession."""
        # GIVEN: A ResourceManager with mocked config
        config = MagicMock()
        config.http = MagicMock()
        config.http.enabled = False
        config.database = MagicMock()
        config.database.get_database_params.return_value = {"db_type": "sqlite", "db_path": ":memory:"}
        rm = ResourceManager(config)

        # WHEN: Initializing with mocked dependencies
        mock_session = MagicMock()
        mock_adapter = MagicMock()
        with (
            patch("src.homelab_mcp.resource_manager.aiohttp.TCPConnector") as mock_connector,
            patch(
                "src.homelab_mcp.resource_manager.aiohttp.ClientSession", return_value=mock_session
            ) as mock_session_cls,
            patch("src.homelab_mcp.resource_manager.get_database_adapter", return_value=mock_adapter),
        ):
            await rm.initialize()

        # THEN: Session should have been created
        assert rm._initialized is True
        mock_connector.assert_called_once()
        mock_session_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_creates_database_adapter(self):
        """Test that initialize() creates and connects database adapter."""
        # GIVEN: A ResourceManager with config
        config = MagicMock()
        config.http = MagicMock()
        config.http.enabled = False
        config.database = MagicMock()
        config.database.get_database_params.return_value = {"db_type": "sqlite", "db_path": ":memory:"}
        rm = ResourceManager(config)

        # WHEN: Initializing
        mock_session = MagicMock()
        mock_adapter = MagicMock()
        with (
            patch("src.homelab_mcp.resource_manager.aiohttp.TCPConnector"),
            patch("src.homelab_mcp.resource_manager.aiohttp.ClientSession", return_value=mock_session),
            patch("src.homelab_mcp.resource_manager.get_database_adapter", return_value=mock_adapter),
        ):
            await rm.initialize()

        # THEN: Database adapter should be connected and schema initialized
        mock_adapter.connect.assert_called_once()
        mock_adapter.init_schema.assert_called_once()


class TestResourceManagerSSL:
    """Test SSL context wiring in ResourceManager."""

    @pytest.mark.asyncio
    async def test_initialize_passes_ssl_context_to_connector(self):
        """Test that ResourceManager passes SSL context from config to TCPConnector."""
        # GIVEN: A config where create_ssl_context returns True
        config = MagicMock()
        config.http = MagicMock()
        config.http.enabled = False
        config.database = MagicMock()
        config.database.get_database_params.return_value = {"db_type": "sqlite", "db_path": ":memory:"}
        config.create_ssl_context.return_value = True
        rm = ResourceManager(config)

        # WHEN: Initializing
        mock_session = MagicMock()
        mock_adapter = MagicMock()
        with (
            patch("src.homelab_mcp.resource_manager.aiohttp.TCPConnector") as mock_connector,
            patch("src.homelab_mcp.resource_manager.aiohttp.ClientSession", return_value=mock_session),
            patch("src.homelab_mcp.resource_manager.get_database_adapter", return_value=mock_adapter),
        ):
            await rm.initialize()

            # THEN: TCPConnector should be called with ssl=True
            mock_connector.assert_called_once_with(
                limit=10,
                limit_per_host=5,
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
                ssl=True,
            )

    @pytest.mark.asyncio
    async def test_initialize_passes_ssl_false_when_disabled(self):
        """Test that ResourceManager passes ssl=False when verification is disabled."""
        # GIVEN: A config where create_ssl_context returns False
        config = MagicMock()
        config.http = MagicMock()
        config.http.enabled = False
        config.database = MagicMock()
        config.database.get_database_params.return_value = {"db_type": "sqlite", "db_path": ":memory:"}
        config.create_ssl_context.return_value = False
        rm = ResourceManager(config)

        # WHEN: Initializing
        mock_session = MagicMock()
        mock_adapter = MagicMock()
        with (
            patch("src.homelab_mcp.resource_manager.aiohttp.TCPConnector") as mock_connector,
            patch("src.homelab_mcp.resource_manager.aiohttp.ClientSession", return_value=mock_session),
            patch("src.homelab_mcp.resource_manager.get_database_adapter", return_value=mock_adapter),
        ):
            await rm.initialize()

            # THEN: TCPConnector should be called with ssl=False
            mock_connector.assert_called_once_with(
                limit=10,
                limit_per_host=5,
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
                ssl=False,
            )


class TestResourceManagerAccessors:
    """Test typed accessor properties."""

    @pytest.mark.asyncio
    async def test_proxmox_session_after_initialize(self):
        """Test proxmox_session returns ClientSession after initialize()."""
        # GIVEN: An initialized ResourceManager
        config = MagicMock()
        config.http = MagicMock()
        config.http.enabled = False
        config.database = MagicMock()
        config.database.get_database_params.return_value = {"db_type": "sqlite", "db_path": ":memory:"}
        rm = ResourceManager(config)

        mock_session = MagicMock(spec=aiohttp.ClientSession)
        mock_adapter = MagicMock()
        with (
            patch("src.homelab_mcp.resource_manager.aiohttp.TCPConnector"),
            patch("src.homelab_mcp.resource_manager.aiohttp.ClientSession", return_value=mock_session),
            patch("src.homelab_mcp.resource_manager.get_database_adapter", return_value=mock_adapter),
        ):
            await rm.initialize()

        # WHEN/THEN: Accessing proxmox_session should return the session
        assert rm.proxmox_session is mock_session

    def test_proxmox_session_before_initialize_raises(self):
        """Test proxmox_session raises RuntimeError before initialize()."""
        # GIVEN: An uninitialized ResourceManager
        config = MagicMock()
        rm = ResourceManager(config)

        # WHEN/THEN: Accessing proxmox_session should raise
        with pytest.raises(RuntimeError, match="ResourceManager not initialized"):
            _ = rm.proxmox_session

    @pytest.mark.asyncio
    async def test_db_adapter_after_initialize(self):
        """Test db_adapter returns DatabaseAdapter after initialize()."""
        # GIVEN: An initialized ResourceManager
        config = MagicMock()
        config.http = MagicMock()
        config.http.enabled = False
        config.database = MagicMock()
        config.database.get_database_params.return_value = {"db_type": "sqlite", "db_path": ":memory:"}
        rm = ResourceManager(config)

        mock_session = MagicMock()
        mock_adapter = MagicMock()
        with (
            patch("src.homelab_mcp.resource_manager.aiohttp.TCPConnector"),
            patch("src.homelab_mcp.resource_manager.aiohttp.ClientSession", return_value=mock_session),
            patch("src.homelab_mcp.resource_manager.get_database_adapter", return_value=mock_adapter),
        ):
            await rm.initialize()

        # WHEN/THEN: Accessing db_adapter should return the adapter
        assert rm.db_adapter is mock_adapter

    def test_db_adapter_before_initialize_raises(self):
        """Test db_adapter raises RuntimeError before initialize()."""
        # GIVEN: An uninitialized ResourceManager
        config = MagicMock()
        rm = ResourceManager(config)

        # WHEN/THEN: Accessing db_adapter should raise
        with pytest.raises(RuntimeError, match="ResourceManager not initialized"):
            _ = rm.db_adapter


class TestResourceManagerShutdown:
    """Test shutdown and cleanup behavior."""

    @pytest.mark.asyncio
    async def test_shutdown_closes_session_and_adapter(self):
        """Test that shutdown() closes proxmox session and database adapter."""
        # GIVEN: An initialized ResourceManager
        config = MagicMock()
        config.http = MagicMock()
        config.http.enabled = False
        config.database = MagicMock()
        config.database.get_database_params.return_value = {"db_type": "sqlite", "db_path": ":memory:"}
        rm = ResourceManager(config)

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_adapter = MagicMock()
        with (
            patch("src.homelab_mcp.resource_manager.aiohttp.TCPConnector"),
            patch("src.homelab_mcp.resource_manager.aiohttp.ClientSession", return_value=mock_session),
            patch("src.homelab_mcp.resource_manager.get_database_adapter", return_value=mock_adapter),
        ):
            await rm.initialize()

        # WHEN: Shutting down
        await rm.shutdown()

        # THEN: Session and adapter should be closed
        mock_session.close.assert_awaited_once()
        mock_adapter.close.assert_called_once()
        assert rm._initialized is False

    @pytest.mark.asyncio
    async def test_shutdown_is_idempotent(self):
        """Test that calling shutdown() twice does not raise."""
        # GIVEN: An initialized ResourceManager
        config = MagicMock()
        config.http = MagicMock()
        config.http.enabled = False
        config.database = MagicMock()
        config.database.get_database_params.return_value = {"db_type": "sqlite", "db_path": ":memory:"}
        rm = ResourceManager(config)

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_adapter = MagicMock()
        with (
            patch("src.homelab_mcp.resource_manager.aiohttp.TCPConnector"),
            patch("src.homelab_mcp.resource_manager.aiohttp.ClientSession", return_value=mock_session),
            patch("src.homelab_mcp.resource_manager.get_database_adapter", return_value=mock_adapter),
        ):
            await rm.initialize()

        # WHEN: Shutting down twice
        await rm.shutdown()
        await rm.shutdown()  # Should not raise

        # THEN: No exception was raised (test passes)


class TestResourceManagerContextManager:
    """Test async context manager support."""

    @pytest.mark.asyncio
    async def test_context_manager_initializes_and_shuts_down(self):
        """Test that ResourceManager works as async context manager."""
        # GIVEN: A ResourceManager with mocked deps
        config = MagicMock()
        config.http = MagicMock()
        config.http.enabled = False
        config.database = MagicMock()
        config.database.get_database_params.return_value = {"db_type": "sqlite", "db_path": ":memory:"}

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_adapter = MagicMock()

        with (
            patch("src.homelab_mcp.resource_manager.aiohttp.TCPConnector"),
            patch("src.homelab_mcp.resource_manager.aiohttp.ClientSession", return_value=mock_session),
            patch("src.homelab_mcp.resource_manager.get_database_adapter", return_value=mock_adapter),
        ):
            # WHEN: Using as context manager
            async with ResourceManager(config) as rm:
                # THEN: Should be initialized inside context
                assert rm._initialized is True
                assert rm.proxmox_session is mock_session
                assert rm.db_adapter is mock_adapter

        # THEN: Should be shut down after context
        mock_session.close.assert_awaited_once()
        mock_adapter.close.assert_called_once()
