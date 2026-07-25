"""Database abstraction layer using SQLAlchemy ORM.

Replaces the legacy sqlite3/psycopg2 direct connection approach with SQLAlchemy 2.0 ORM.
Provides type-safe models and automatic migration support via Alembic.

Maintains backward compatibility with the DatabaseAdapter interface used throughout
the codebase.
"""

from __future__ import annotations

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .models import Device, DiscoveryHistory, DriftBaseline, SSHCredential

logger = logging.getLogger(__name__)

# Try to import psycopg2 for PostgreSQL support (optional)
try:
    import psycopg2  # noqa: F401

    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False


class DatabaseAdapter(ABC):
    """Abstract base class for database adapters.

    Provides a consistent interface for database operations regardless of backend.
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish database connection."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close database connection."""
        pass

    @abstractmethod
    def init_schema(self) -> None:
        """Initialize database schema."""
        pass

    @abstractmethod
    def store_device(self, device_data: dict[str, Any]) -> int:
        """Store or update a device record."""
        pass

    @abstractmethod
    def get_all_devices(self) -> list[dict[str, Any]]:
        """Get all devices from the database."""
        pass

    @abstractmethod
    def store_discovery_history(self, device_id: int, discovery_data: str, data_hash: str) -> None:
        """Store discovery history record."""
        pass

    @abstractmethod
    def get_device_changes(self, device_id: int, limit: int = 10) -> list[dict[str, Any]]:
        """Get change history for a device."""
        pass

    @abstractmethod
    def execute_query(self, query: str, params: tuple | None = None) -> list[dict[str, Any]]:
        """Execute a query and return results."""
        pass

    # SSH Credentials CRUD methods
    @abstractmethod
    def add_credential(
        self,
        hostname: str,
        username: str = "mcp_admin",
        key_path: str | None = None,
        port: int = 22,
        display_name: str | None = None,
        device_id: int | None = None,
    ) -> int:
        """Add a new SSH credential record."""
        pass

    @abstractmethod
    def get_credential(self, credential_id: int) -> dict[str, Any] | None:
        """Get a credential by its ID."""
        pass

    @abstractmethod
    def get_credential_by_hostname(self, hostname: str, username: str | None = None) -> dict[str, Any] | None:
        """Get credential by hostname and optionally username."""
        pass

    @abstractmethod
    def update_credential(self, credential_id: int, **kwargs: Any) -> bool:
        """Update a credential record."""
        pass

    @abstractmethod
    def delete_credential(self, credential_id: int) -> bool:
        """Delete a credential record."""
        pass

    @abstractmethod
    def list_credentials(self, active_only: bool = True) -> list[dict[str, Any]]:
        """List all credentials."""
        pass

    @abstractmethod
    def update_last_verified(self, credential_id: int) -> bool:
        """Update the last_verified timestamp for a credential."""
        pass

    # Drift baseline CRUD methods
    @abstractmethod
    def upsert_drift_baseline(
        self,
        node: str,
        vmid: int,
        vm_type: str,
        baseline_config: dict[str, Any],
        recorded_by: str,
    ) -> None:
        """Insert or replace a drift baseline for the given (node, vmid, vm_type)."""
        pass

    @abstractmethod
    def get_drift_baseline(
        self,
        node: str,
        vmid: int,
        vm_type: str,
    ) -> dict[str, Any] | None:
        """Return the baseline dict for (node, vmid, vm_type), or None if absent."""
        pass

    @abstractmethod
    def get_all_drift_baselines(self) -> list[dict[str, Any]]:
        """Return all stored drift baselines ordered by node, vmid."""
        pass


class SQLAlchemyAdapter(DatabaseAdapter):
    """SQLAlchemy-based database adapter.

    Uses SQLAlchemy 2.0 ORM with async-style synchronous sessions for simplicity.
    Supports both SQLite (default) and PostgreSQL backends.
    """

    def __init__(
        self,
        db_type: str = "sqlite",
        db_path: str | None = None,
        connection_params: dict[str, Any] | None = None,
    ) -> None:
        self._db_type = db_type.lower()
        self._engine: Engine | None = None
        self._SessionLocal: sessionmaker[Session] | None = None
        self._connection_params = connection_params or {}

        # Determine database URL
        if self._db_type == "postgresql":
            if not POSTGRESQL_AVAILABLE:
                raise ImportError(
                    "PostgreSQL support requires psycopg2-binary. Install with: pip install psycopg2-binary"
                )
            self._database_url = self._build_postgres_url()
        else:
            # SQLite
            if db_path is None:
                try:
                    home_dir = Path.home()
                    mcp_dir = home_dir / ".mcp"
                    mcp_dir.mkdir(exist_ok=True)
                    db_path = str(mcp_dir / "sitemap.db")
                except (RuntimeError, OSError):
                    current_dir = Path.cwd()
                    mcp_dir = current_dir / ".mcp"
                    mcp_dir.mkdir(exist_ok=True)
                    db_path = str(mcp_dir / "sitemap.db")
            self._database_url = f"sqlite:///{db_path}"

    def _build_postgres_url(self) -> str:
        """Build PostgreSQL database URL from connection params."""
        host = self._connection_params.get("host", "localhost")
        port = self._connection_params.get("port", 5432)
        database = self._connection_params.get("database", "homelab_mcp")
        user = self._connection_params.get("user", "postgres")
        password = self._connection_params.get("password", "")

        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    def connect(self) -> None:
        """Establish database connection and create engine."""
        if self._engine is not None:
            return

        echo = False  # Set to True for debugging SQL queries
        if self._db_type == "sqlite":
            self._engine = create_engine(self._database_url, echo=echo, future=True)
        else:
            self._engine = create_engine(
                self._database_url,
                echo=echo,
                future=True,
                pool_pre_ping=True,
                pool_recycle=3600,
            )

        self._SessionLocal = sessionmaker(bind=self._engine, autocommit=False, autoflush=False)
        logger.debug(
            "Database engine created: %s",
            self._database_url.split("@")[-1] if "@" in self._database_url else self._database_url,
        )

    def close(self) -> None:
        """Close database connection and dispose engine."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._SessionLocal = None
            logger.debug("Database engine disposed")

    def init_schema(self) -> None:
        """Initialize database schema using SQLAlchemy metadata."""
        if self._engine is None:
            self.connect()
        if self._engine is None:
            raise RuntimeError("Database not connected. Call connect() first.")

        from .models import Base

        Base.metadata.create_all(self._engine)
        logger.debug("Database schema initialized")

    def _get_session(self) -> Session:
        """Get a new database session."""
        if self._SessionLocal is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._SessionLocal()

    def store_device(self, device_data: dict[str, Any]) -> int:
        """Store or update a device in the database."""
        session = self._get_session()
        try:
            # Try to find existing device
            existing = (
                session.query(Device)
                .filter(
                    Device.hostname == device_data["hostname"],
                    Device.connection_ip == device_data["connection_ip"],
                )
                .first()
            )

            if existing:
                # Update existing device
                for field in [
                    "last_seen",
                    "status",
                    "cpu_model",
                    "cpu_cores",
                    "memory_total",
                    "memory_used",
                    "memory_free",
                    "memory_available",
                    "disk_filesystem",
                    "disk_size",
                    "disk_used",
                    "disk_available",
                    "disk_use_percent",
                    "disk_mount",
                    "network_interfaces",
                    "uptime",
                    "os_info",
                    "error_message",
                ]:
                    if field in device_data:
                        setattr(existing, field, device_data.get(field))
                existing.updated_at = datetime.now().isoformat()
                session.commit()
                return existing.id
            else:
                # Create new device
                device = Device(**{k: v for k, v in device_data.items() if hasattr(Device, k)})
                session.add(device)
                session.commit()
                session.refresh(device)
                return device.id
        except Exception as e:
            session.rollback()
            logger.error("Error storing device: %s", e)
            raise
        finally:
            session.close()

    def get_all_devices(self) -> list[dict[str, Any]]:
        """Get all devices from the database."""
        session = self._get_session()
        try:
            devices = session.query(Device).order_by(Device.hostname, Device.connection_ip).all()
            return [device.to_dict() for device in devices]
        finally:
            session.close()

    def store_discovery_history(self, device_id: int, discovery_data: str, data_hash: str) -> None:
        """Store discovery history in the database."""
        session = self._get_session()
        try:
            # Check if this exact data was already stored recently
            existing = (
                session.query(DiscoveryHistory)
                .filter(
                    DiscoveryHistory.device_id == device_id,
                    DiscoveryHistory.data_hash == data_hash,
                )
                .order_by(DiscoveryHistory.discovered_at.desc())
                .first()
            )

            if not existing:
                history = DiscoveryHistory(
                    device_id=device_id,
                    discovery_data=discovery_data,
                    data_hash=data_hash,
                    discovered_at=datetime.now().isoformat(),
                )
                session.add(history)
                session.commit()
        except Exception as e:
            session.rollback()
            logger.error("Error storing discovery history: %s", e)
            raise
        finally:
            session.close()

    def get_device_changes(self, device_id: int, limit: int = 10) -> list[dict[str, Any]]:
        """Get device change history from the database."""
        session = self._get_session()
        try:
            history = (
                session.query(DiscoveryHistory)
                .filter(DiscoveryHistory.device_id == device_id)
                .order_by(DiscoveryHistory.discovered_at.desc())
                .limit(limit)
                .all()
            )

            changes = []
            for record in history:
                try:
                    data = json.loads(record.discovery_data)
                    changes.append({"data": data, "discovered_at": record.discovered_at})
                except (json.JSONDecodeError, TypeError):
                    logger.debug("Failed to parse discovery history JSON for record at %s", record.discovered_at)

            return changes
        finally:
            session.close()

    def execute_query(self, query: str, params: tuple | None = None) -> list[dict[str, Any]]:
        """Execute a raw SQL query and return results."""
        session = self._get_session()
        try:
            from sqlalchemy import text

            if params:
                result = session.execute(text(query), {"params": params})
            else:
                result = session.execute(text(query))

            columns = result.keys()
            return [dict(zip(columns, row, strict=False)) for row in result]
        except Exception as e:
            logger.error("Error executing query: %s", e)
            raise
        finally:
            session.close()

    # SSH Credentials CRUD methods

    def add_credential(
        self,
        hostname: str,
        username: str = "mcp_admin",
        key_path: str | None = None,
        port: int = 22,
        display_name: str | None = None,
        device_id: int | None = None,
    ) -> int:
        """Add a new SSH credential record."""
        session = self._get_session()
        try:
            credential = SSHCredential(
                hostname=hostname,
                username=username,
                key_path=key_path,
                port=port,
                display_name=display_name,
                device_id=device_id,
                is_active=True,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
            )
            session.add(credential)
            session.commit()
            session.refresh(credential)
            return credential.id
        except IntegrityError as e:
            session.rollback()
            raise ValueError(f"Credential for {hostname}@{username} already exists") from e
        except Exception as e:
            session.rollback()
            logger.error("Error adding credential: %s", e)
            raise
        finally:
            session.close()

    def get_credential(self, credential_id: int) -> dict[str, Any] | None:
        """Get a credential by its ID."""
        session = self._get_session()
        try:
            credential = session.query(SSHCredential).filter(SSHCredential.id == credential_id).first()
            if credential:
                return credential.to_dict()
            return None
        finally:
            session.close()

    def get_credential_by_hostname(self, hostname: str, username: str | None = None) -> dict[str, Any] | None:
        """Get credential by hostname and optionally username."""
        session = self._get_session()
        try:
            query = session.query(SSHCredential).filter(
                SSHCredential.hostname == hostname,
                SSHCredential.is_active == True,  # noqa: E712  (SQLAlchemy needs the comparison, not a truth check)
            )

            if username:
                query = query.filter(SSHCredential.username == username)

            credential = query.order_by(SSHCredential.id.desc()).first()

            if credential:
                return credential.to_dict()
            return None
        finally:
            session.close()

    def update_credential(self, credential_id: int, **kwargs: Any) -> bool:
        """Update a credential record."""
        session = self._get_session()
        try:
            allowed_fields = {
                "hostname",
                "username",
                "key_path",
                "port",
                "display_name",
                "device_id",
                "is_active",
            }
            # dict[Any, Any]: Query.update() types its keys as column descriptors,
            # but accepts plain column-name strings at runtime.
            update_data: dict[Any, Any] = {k: v for k, v in kwargs.items() if k in allowed_fields}

            if not update_data:
                return False

            update_data["updated_at"] = datetime.now().isoformat()

            result = session.query(SSHCredential).filter(SSHCredential.id == credential_id).update(update_data)
            session.commit()
            return result > 0
        except Exception as e:
            session.rollback()
            logger.error("Error updating credential: %s", e)
            raise
        finally:
            session.close()

    def delete_credential(self, credential_id: int) -> bool:
        """Delete a credential record."""
        session = self._get_session()
        try:
            result = session.query(SSHCredential).filter(SSHCredential.id == credential_id).delete()
            session.commit()
            return result > 0
        except Exception as e:
            session.rollback()
            logger.error("Error deleting credential: %s", e)
            raise
        finally:
            session.close()

    def list_credentials(self, active_only: bool = True) -> list[dict[str, Any]]:
        """List all credentials."""
        session = self._get_session()
        try:
            query = session.query(SSHCredential)
            if active_only:
                query = query.filter(SSHCredential.is_active == True)  # noqa: E712

            credentials = query.order_by(SSHCredential.hostname).all()
            return [cred.to_dict() for cred in credentials]
        finally:
            session.close()

    def update_last_verified(self, credential_id: int) -> bool:
        """Update the last_verified timestamp for a credential."""
        session = self._get_session()
        try:
            now = datetime.now().isoformat()
            result = (
                session.query(SSHCredential)
                .filter(SSHCredential.id == credential_id)
                .update({"last_verified": now, "updated_at": now})
            )
            session.commit()
            return result > 0
        except Exception as e:
            session.rollback()
            logger.error("Error updating last_verified: %s", e)
            raise
        finally:
            session.close()

    # Drift baseline CRUD methods

    def upsert_drift_baseline(
        self,
        node: str,
        vmid: int,
        vm_type: str,
        baseline_config: dict[str, Any],
        recorded_by: str,
    ) -> None:
        """Insert or replace a drift baseline."""
        session = self._get_session()
        try:
            existing = (
                session.query(DriftBaseline)
                .filter(
                    DriftBaseline.node == node,
                    DriftBaseline.vmid == vmid,
                    DriftBaseline.vm_type == vm_type,
                )
                .first()
            )

            if existing:
                existing.baseline_config = json.dumps(baseline_config)
                existing.recorded_at = datetime.now().isoformat()
                existing.recorded_by = recorded_by
            else:
                baseline = DriftBaseline(
                    node=node,
                    vmid=vmid,
                    vm_type=vm_type,
                    baseline_config=json.dumps(baseline_config),
                    recorded_at=datetime.now().isoformat(),
                    recorded_by=recorded_by,
                )
                session.add(baseline)

            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("Error upserting drift baseline: %s", e)
            raise
        finally:
            session.close()

    def get_drift_baseline(
        self,
        node: str,
        vmid: int,
        vm_type: str,
    ) -> dict[str, Any] | None:
        """Return the baseline dict for (node, vmid, vm_type), or None if absent."""
        session = self._get_session()
        try:
            baseline = (
                session.query(DriftBaseline)
                .filter(
                    DriftBaseline.node == node,
                    DriftBaseline.vmid == vmid,
                    DriftBaseline.vm_type == vm_type,
                )
                .first()
            )

            if baseline:
                return {
                    "node": baseline.node,
                    "vmid": baseline.vmid,
                    "vm_type": baseline.vm_type,
                    "baseline_config": json.loads(baseline.baseline_config),
                    "recorded_at": baseline.recorded_at,
                    "recorded_by": baseline.recorded_by,
                }
            return None
        finally:
            session.close()

    def get_all_drift_baselines(self) -> list[dict[str, Any]]:
        """Return all stored drift baselines ordered by node, vmid."""
        session = self._get_session()
        try:
            baselines = session.query(DriftBaseline).order_by(DriftBaseline.node, DriftBaseline.vmid).all()

            results = []
            for baseline in baselines:
                entry = {
                    "node": baseline.node,
                    "vmid": baseline.vmid,
                    "vm_type": baseline.vm_type,
                    "baseline_config": json.loads(baseline.baseline_config),
                    "recorded_at": baseline.recorded_at,
                    "recorded_by": baseline.recorded_by,
                }
                results.append(entry)
            return results
        finally:
            session.close()


def get_database_adapter(db_type: str | None = None, **kwargs: Any) -> DatabaseAdapter:
    """Factory function to get the appropriate database adapter.

    Args:
        db_type: Database type ("sqlite" or "postgresql"). Auto-detects from env if None.
        **kwargs: Additional parameters (db_path for SQLite, connection_params for PostgreSQL).

    Returns:
        DatabaseAdapter instance configured for the specified backend.
    """
    if db_type is None:
        db_type = "sqlite"

    if db_type not in ("sqlite", "postgresql"):
        raise ValueError(f"Unsupported database type: {db_type}. Must be 'sqlite' or 'postgresql'")

    if db_type == "postgresql":
        return SQLAlchemyAdapter(db_type="postgresql", connection_params=kwargs.get("connection_params"))
    else:
        return SQLAlchemyAdapter(db_type="sqlite", db_path=kwargs.get("db_path"))


def calculate_data_hash(discovery_data: str) -> str:
    """Calculate SHA-256 hash of discovery data for change detection."""
    return hashlib.sha256(discovery_data.encode()).hexdigest()


# No SQLiteAdapter/PostgreSQLAdapter aliases here on purpose. They looked
# compatible but were not: the old adapters took a path or a params dict as the
# first positional arg, while SQLAlchemyAdapter takes db_type. `SQLiteAdapter(path)`
# therefore silently fell back to the default database instead of the requested
# one, and `PostgreSQLAdapter(params)` raised AttributeError on dict.lower().
# Use get_database_adapter() — it routes the kwargs to the right place.
