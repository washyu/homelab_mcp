"""Centralized resource and connection lifecycle management.

ResourceManager owns the lifecycle of all shared connections:
- aiohttp.ClientSession for Proxmox API calls
- DatabaseAdapter for SQLite/PostgreSQL operations

All connections are created during initialize() and cleaned up during shutdown().
Supports async context manager protocol for automatic lifecycle management.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import aiohttp

from .database import DatabaseAdapter, get_database_adapter

if TYPE_CHECKING:
    from .config import MCPConfig

logger = logging.getLogger(__name__)


class ResourceManager:
    """Centralizes connection lifecycle for the MCP server.

    Usage::

        config = MCPConfig()
        async with ResourceManager(config) as rm:
            session = rm.proxmox_session
            db = rm.db_adapter
    """

    def __init__(self, config: MCPConfig) -> None:
        self._config = config
        self._initialized = False
        self._proxmox_session: aiohttp.ClientSession | None = None
        self._db_adapter: DatabaseAdapter | None = None

    async def initialize(self) -> None:
        """Create and connect all managed resources.

        Creates an aiohttp.ClientSession with connection pooling for Proxmox API
        calls, and initializes the database adapter with schema.
        """
        logger.info("Initializing ResourceManager")

        # Create aiohttp session with connection pooling and SSL configuration
        ssl_context = self._config.create_ssl_context()
        connector = aiohttp.TCPConnector(
            limit=10,
            limit_per_host=5,
            ttl_dns_cache=300,
            enable_cleanup_closed=True,
            ssl=ssl_context,
        )
        self._proxmox_session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=30),
        )
        logger.debug("Created aiohttp.ClientSession with connection pooling")

        # Initialize database
        db_params = self._config.database.get_database_params()
        self._db_adapter = get_database_adapter(**db_params)
        self._db_adapter.connect()
        self._db_adapter.init_schema()
        logger.debug("Database adapter connected and schema initialized")

        self._initialized = True
        logger.info("ResourceManager initialized successfully")

    async def shutdown(self) -> None:
        """Close all managed resources.

        Safe to call multiple times (idempotent).
        """
        logger.info("Shutting down ResourceManager")

        if self._proxmox_session is not None:
            await self._proxmox_session.close()
            self._proxmox_session = None
            logger.debug("Closed aiohttp.ClientSession")

        if self._db_adapter is not None:
            self._db_adapter.close()
            self._db_adapter = None
            logger.debug("Closed database adapter")

        self._initialized = False
        logger.info("ResourceManager shut down")

    @property
    def proxmox_session(self) -> aiohttp.ClientSession:
        """Get the shared aiohttp.ClientSession for Proxmox API calls.

        Raises:
            RuntimeError: If ResourceManager has not been initialized.
        """
        if not self._initialized or self._proxmox_session is None:
            raise RuntimeError("ResourceManager not initialized")
        return self._proxmox_session

    @property
    def db_adapter(self) -> DatabaseAdapter:
        """Get the database adapter.

        Raises:
            RuntimeError: If ResourceManager has not been initialized.
        """
        if not self._initialized or self._db_adapter is None:
            raise RuntimeError("ResourceManager not initialized")
        return self._db_adapter

    async def __aenter__(self) -> ResourceManager:
        """Initialize resources on context entry."""
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Shut down resources on context exit."""
        await self.shutdown()
