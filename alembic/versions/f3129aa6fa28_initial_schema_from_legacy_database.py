"""Initial schema from legacy database

Revision ID: f3129aa6fa28
Revises:
Create Date: 2026-07-11

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3129aa6fa28"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create initial schema tables."""

    # Devices table
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("connection_ip", sa.String(length=45), nullable=False),
        sa.Column("last_seen", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("cpu_model", sa.String(length=255), nullable=True),
        sa.Column("cpu_cores", sa.Integer(), nullable=True),
        sa.Column("memory_total", sa.String(length=50), nullable=True),
        sa.Column("memory_used", sa.String(length=50), nullable=True),
        sa.Column("memory_free", sa.String(length=50), nullable=True),
        sa.Column("memory_available", sa.String(length=50), nullable=True),
        sa.Column("disk_filesystem", sa.String(length=100), nullable=True),
        sa.Column("disk_size", sa.String(length=50), nullable=True),
        sa.Column("disk_used", sa.String(length=50), nullable=True),
        sa.Column("disk_available", sa.String(length=50), nullable=True),
        sa.Column("disk_use_percent", sa.String(length=20), nullable=True),
        sa.Column("disk_mount", sa.String(length=255), nullable=True),
        sa.Column("network_interfaces", sa.Text(), nullable=True),
        sa.Column("uptime", sa.String(length=255), nullable=True),
        sa.Column("os_info", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=50), nullable=False),
        sa.Column("updated_at", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("idx_devices_hostname_ip", "hostname", "connection_ip"),
        sa.Index("idx_devices_status", "status"),
    )

    # Discovery history table
    op.create_table(
        "discovery_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("discovery_data", sa.Text(), nullable=False),
        sa.Column("data_hash", sa.String(length=64), nullable=False),
        sa.Column("discovered_at", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.Index("idx_history_device_id", "device_id"),
        sa.Index("idx_history_hash", "data_hash"),
    )

    # SSH credentials table
    op.create_table(
        "ssh_credentials",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False, server_default="mcp_admin"),
        sa.Column("key_path", sa.String(length=500), nullable=True),
        sa.Column("port", sa.Integer(), nullable=False, server_default="22"),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("last_verified", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.String(length=50), nullable=False),
        sa.Column("updated_at", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.Index("idx_ssh_credentials_hostname", "hostname"),
        sa.Index("idx_ssh_credentials_device_id", "device_id"),
        sa.Index("idx_ssh_credentials_active", "is_active"),
        sa.Index("uq_ssh_credentials_host_user", "hostname", "username", unique=True),
    )

    # Drift baselines table
    op.create_table(
        "drift_baselines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("node", sa.String(length=255), nullable=False),
        sa.Column("vmid", sa.Integer(), nullable=False),
        sa.Column("vm_type", sa.String(length=50), nullable=False, server_default="qemu"),
        sa.Column("baseline_config", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.String(length=50), nullable=False),
        sa.Column("recorded_by", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("idx_drift_baselines_node_vmid", "node", "vmid", "vm_type"),
        sa.Index("uq_drift_baselines_node_vmid_type", "node", "vmid", "vm_type", unique=True),
    )


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("drift_baselines")
    op.drop_table("ssh_credentials")
    op.drop_table("discovery_history")
    op.drop_table("devices")
