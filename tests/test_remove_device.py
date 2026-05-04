"""Phase 44: remove_device tool tests (D-06, D-06a, D-06b, D-06c, D-11, D-13).

Covers:
  - delete_device_by_id adapter round-trip on SQLite (happy + dry_run + missing).
  - handle_remove_device handler envelope shapes (success + error).
  - handle_remove_device_preview thin-delegate parity.
  - Credential-preservation invariant (SC-2): no keyring delete, ssh_credential_id
    keyring entry survives row delete by construction.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from homelab_mcp.database import SQLiteAdapter
from homelab_mcp.tool_handlers.network_handlers import (
    handle_remove_device,
    handle_remove_device_preview,
)

NSM_PATH = "homelab_mcp.tool_handlers.network_handlers.NetworkSiteMap"


@pytest.fixture
def fresh_adapter(tmp_path: Path) -> SQLiteAdapter:
    """Fresh SQLite adapter on a temp file DB; schema initialized."""
    db_path = tmp_path / "test_sitemap.db"
    adapter = SQLiteAdapter(db_path=str(db_path))
    adapter.init_schema()
    return adapter


@pytest.fixture
def seeded_device(fresh_adapter: SQLiteAdapter) -> int:
    """Insert one device row + a discovery_history row; return the device id.

    Includes ``last_seen`` per the schema requirement (mirrors the
    ``seeded_diverse`` fixture in tests/test_purge_devices.py from Plan 02 -
    cross-plan fixture-shape consistency).
    """
    device_id = fresh_adapter.store_device(
        {
            "hostname": "pve-test",
            "connection_ip": "192.168.10.20",
            "status": "success",
            "last_seen": datetime.now(UTC).isoformat(),
            # Other fields default to NULL - sufficient for delete tests.
        }
    )
    # Bind ssh_credential_id via the dedicated adapter method (store_device
    # does not write the credential-binding columns; Phase 38.1 R3/R4/R8/R9).
    fresh_adapter.set_device_credential_binding(device_id, "ssh", "test-cred-uuid-44")
    # Add a discovery_history row to assert cascade.
    assert fresh_adapter.connection is not None
    fresh_adapter.connection.execute(
        "INSERT INTO discovery_history (device_id, discovery_data, data_hash) VALUES (?, ?, ?)",
        (device_id, '{"k":"v"}', "abc123"),
    )
    fresh_adapter.connection.commit()
    return int(device_id)


class TestPhase44RemoveDeviceAdapter:
    """Adapter-level tests for SQLiteAdapter.delete_device_by_id (D-13)."""

    def test_delete_existing_row_returns_dict_and_removes_row(
        self, fresh_adapter: SQLiteAdapter, seeded_device: int
    ) -> None:
        removed = fresh_adapter.delete_device_by_id(seeded_device, dry_run=False)
        assert removed is not None
        assert removed["id"] == seeded_device
        assert removed["hostname"] == "pve-test"
        assert removed["ssh_credential_id"] == "test-cred-uuid-44"
        # Row gone from devices.
        assert fresh_adapter.connection is not None
        cur = fresh_adapter.connection.execute("SELECT COUNT(*) FROM devices WHERE id = ?", (seeded_device,))
        assert cur.fetchone()[0] == 0
        # Cascade deleted discovery_history.
        cur = fresh_adapter.connection.execute(
            "SELECT COUNT(*) FROM discovery_history WHERE device_id = ?",
            (seeded_device,),
        )
        assert cur.fetchone()[0] == 0

    def test_dry_run_returns_dict_and_leaves_tables_untouched(
        self, fresh_adapter: SQLiteAdapter, seeded_device: int
    ) -> None:
        removed = fresh_adapter.delete_device_by_id(seeded_device, dry_run=True)
        assert removed is not None
        assert removed["id"] == seeded_device
        assert fresh_adapter.connection is not None
        cur = fresh_adapter.connection.execute("SELECT COUNT(*) FROM devices WHERE id = ?", (seeded_device,))
        assert cur.fetchone()[0] == 1
        cur = fresh_adapter.connection.execute(
            "SELECT COUNT(*) FROM discovery_history WHERE device_id = ?",
            (seeded_device,),
        )
        assert cur.fetchone()[0] == 1

    def test_missing_id_returns_none(self, fresh_adapter: SQLiteAdapter) -> None:
        assert fresh_adapter.delete_device_by_id(999_999, dry_run=False) is None
        assert fresh_adapter.delete_device_by_id(999_999, dry_run=True) is None


class TestPhase44RemoveDeviceHandler:
    """Handler-level tests for handle_remove_device + preview (D-06, D-06a, D-06b)."""

    @pytest.mark.asyncio
    async def test_happy_path_success_envelope(self, fresh_adapter: SQLiteAdapter, seeded_device: int) -> None:
        with patch(NSM_PATH) as MockSM:
            MockSM.return_value.db_adapter = fresh_adapter
            result = await handle_remove_device({"device_id": seeded_device})
        payload = json.loads(result["content"][0]["text"])
        assert payload["status"] == "success"
        assert payload["dry_run"] is False
        assert payload["removed_device"]["id"] == seeded_device
        assert payload["removed_device"]["hostname"] == "pve-test"

    @pytest.mark.asyncio
    async def test_dry_run_does_not_delete(self, fresh_adapter: SQLiteAdapter, seeded_device: int) -> None:
        with patch(NSM_PATH) as MockSM:
            MockSM.return_value.db_adapter = fresh_adapter
            result = await handle_remove_device({"device_id": seeded_device, "dry_run": True})
        payload = json.loads(result["content"][0]["text"])
        assert payload["status"] == "success"
        assert payload["dry_run"] is True
        assert payload["removed_device"]["id"] == seeded_device
        # Row still present.
        assert fresh_adapter.connection is not None
        cur = fresh_adapter.connection.execute("SELECT COUNT(*) FROM devices WHERE id = ?", (seeded_device,))
        assert cur.fetchone()[0] == 1

    @pytest.mark.asyncio
    async def test_handle_remove_device_missing_id_phase44(self, fresh_adapter: SQLiteAdapter) -> None:
        """D-06b: missing device_id returns structured-error envelope, not exception.

        Asserts the EXACT error string and hint substring per the
        NOTE comment in network_handlers.py::handle_remove_device.
        """
        with patch(NSM_PATH) as MockSM:
            MockSM.return_value.db_adapter = fresh_adapter
            result = await handle_remove_device({"device_id": 999_999})
        payload = json.loads(result["content"][0]["text"])
        assert payload["status"] == "error"
        assert payload["error"] == "Device 999999 not found in sitemap"
        assert payload["hint"] == "Run get_network_sitemap to see current device IDs."

    @pytest.mark.asyncio
    async def test_preview_is_thin_delegate_with_dry_run_injected(
        self, fresh_adapter: SQLiteAdapter, seeded_device: int
    ) -> None:
        with patch(NSM_PATH) as MockSM:
            MockSM.return_value.db_adapter = fresh_adapter
            result = await handle_remove_device_preview({"device_id": seeded_device})
        payload = json.loads(result["content"][0]["text"])
        assert payload["status"] == "success"
        assert payload["dry_run"] is True
        # Row still present after preview.
        assert fresh_adapter.connection is not None
        cur = fresh_adapter.connection.execute("SELECT COUNT(*) FROM devices WHERE id = ?", (seeded_device,))
        assert cur.fetchone()[0] == 1


class TestPhase44RemoveDeviceCredentialPreservation:
    """SC-2: remove_device must NOT touch the keyring.

    Mock keyring delete-class symbols and assert no calls were made.
    The handler body should not even import keyring - this test belt-and-braces
    against future drift (the AST guard in Plan 03 enforces the import-level
    contract; this test enforces the runtime behavior).
    """

    @pytest.mark.asyncio
    async def test_remove_device_does_not_call_keyring_delete(
        self, fresh_adapter: SQLiteAdapter, seeded_device: int
    ) -> None:
        with (
            patch(NSM_PATH) as MockSM,
            patch("keyring.delete_password") as mock_del,
            patch("keyring.set_password") as mock_set,
        ):
            MockSM.return_value.db_adapter = fresh_adapter
            await handle_remove_device({"device_id": seeded_device})
        mock_del.assert_not_called()
        mock_set.assert_not_called()
