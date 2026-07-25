"""SQLAlchemy ORM models for homelab_mcp database.

Defines the schema for devices, discovery_history, ssh_credentials, and drift_baselines
tables using SQLAlchemy 2.0 ORM with type-safe column definitions.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class Device(Base):
    """Represents a discovered host in the homelab network.

    Mirrors the legacy `devices` table schema with backward-compatible field names.
    """

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    connection_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    last_seen: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)

    # CPU
    cpu_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cpu_cores: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Memory (stored as strings for cross-platform compatibility)
    memory_total: Mapped[str | None] = mapped_column(String(50), nullable=True)
    memory_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    memory_free: Mapped[str | None] = mapped_column(String(50), nullable=True)
    memory_available: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Disk
    disk_filesystem: Mapped[str | None] = mapped_column(String(100), nullable=True)
    disk_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    disk_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    disk_available: Mapped[str | None] = mapped_column(String(50), nullable=True)
    disk_use_percent: Mapped[str | None] = mapped_column(String(20), nullable=True)
    disk_mount: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Network interfaces (JSON)
    network_interfaces: Mapped[str | None] = mapped_column(Text, nullable=True)

    # System info
    uptime: Mapped[str | None] = mapped_column(String(255), nullable=True)
    os_info: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[str] = mapped_column(String(50), default=lambda: datetime.now().isoformat())
    updated_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.now().isoformat(), onupdate=lambda: datetime.now().isoformat()
    )

    # Relationships
    discovery_history: Mapped[list[DiscoveryHistory]] = relationship(
        "DiscoveryHistory", back_populates="device", cascade="all, delete-orphan"
    )
    credential: Mapped[SSHCredential | None] = relationship("SSHCredential", back_populates="device")

    __table_args__ = (
        Index("idx_devices_hostname_ip", "hostname", "connection_ip"),
        Index("idx_devices_status", "status"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, parsing JSON fields."""
        data = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        if data.get("network_interfaces"):
            try:
                data["network_interfaces"] = json.loads(data["network_interfaces"])
            except (json.JSONDecodeError, TypeError):
                data["network_interfaces"] = []
        return data


class DiscoveryHistory(Base):
    """Stores discovery history for change detection.

    Mirrors the legacy `discovery_history` table schema.
    """

    __tablename__ = "discovery_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
    discovery_data: Mapped[str] = mapped_column(Text, nullable=False)
    data_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    discovered_at: Mapped[str] = mapped_column(String(50), default=lambda: datetime.now().isoformat())

    # Relationships
    device: Mapped[Device | None] = relationship("Device", back_populates="discovery_history")

    __table_args__ = (
        Index("idx_history_device_id", "device_id"),
        Index("idx_history_hash", "data_hash"),
    )


class SSHCredential(Base):
    """Stores SSH credentials for persistent host access.

    Mirrors the legacy `ssh_credentials` table schema.
    """

    __tablename__ = "ssh_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("devices.id", ondelete="SET NULL"), nullable=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False, default="mcp_admin")
    key_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    port: Mapped[int] = mapped_column(Integer, default=22)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_verified: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[str] = mapped_column(String(50), default=lambda: datetime.now().isoformat())
    updated_at: Mapped[str] = mapped_column(
        String(50), default=lambda: datetime.now().isoformat(), onupdate=lambda: datetime.now().isoformat()
    )

    # Relationships
    device: Mapped[Device | None] = relationship("Device", back_populates="credential")

    __table_args__ = (
        Index("idx_ssh_credentials_hostname", "hostname"),
        Index("idx_ssh_credentials_device_id", "device_id"),
        Index("idx_ssh_credentials_active", "is_active"),
        Index("uq_ssh_credentials_host_user", "hostname", "username", unique=True),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "device_id": self.device_id,
            "hostname": self.hostname,
            "username": self.username,
            "key_path": self.key_path,
            "port": self.port,
            "display_name": self.display_name,
            "is_active": self.is_active,
            "last_verified": self.last_verified,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class DriftBaseline(Base):
    """Stores drift baseline configurations for VMs.

    Mirrors the legacy `drift_baselines` table schema.
    """

    __tablename__ = "drift_baselines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node: Mapped[str] = mapped_column(String(255), nullable=False)
    vmid: Mapped[int] = mapped_column(Integer, nullable=False)
    vm_type: Mapped[str] = mapped_column(String(50), default="qemu")
    baseline_config: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[str] = mapped_column(String(50), nullable=False)
    recorded_by: Mapped[str] = mapped_column(String(255), nullable=False)

    __table_args__ = (
        Index("idx_drift_baselines_node_vmid", "node", "vmid", "vm_type"),
        Index("uq_drift_baselines_node_vmid_type", "node", "vmid", "vm_type", unique=True),
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "node": self.node,
            "vmid": self.vmid,
            "vm_type": self.vm_type,
            "baseline_config": json.loads(self.baseline_config),
            "recorded_at": self.recorded_at,
            "recorded_by": self.recorded_by,
        }
