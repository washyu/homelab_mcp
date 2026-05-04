"""Phase 44: purge_failed_discoveries alias parity tests (D-07, D-08).

After Phase 44 Task 1b refactors SQLiteAdapter.purge_failed_devices to delegate
to _purge_devices_by_filter via the 'failed_discovery' sentinel, the alias
must produce byte-identical results to the underlying helper. This locks the
refactor and prevents future drift between the alias and the shared path.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from homelab_mcp.database import (
    SQLiteAdapter,
    _purge_devices_by_filter,
)
from homelab_mcp.tool_handlers.network_handlers import handle_purge_failed_discoveries


@pytest.fixture
def seeded_with_failed_rows(tmp_path: Path) -> SQLiteAdapter:
    """Seed: status=error row + zombie hostname='' row + good row + 'unknown' hostname row.
    D-08 4-clause OR semantics: failed_discovery filter should match the
    broken/zombie/unknown rows but NOT the good row."""
    db_path = tmp_path / "alias_parity.db"
    adapter = SQLiteAdapter(db_path=str(db_path))
    adapter.init_schema()
    now = datetime.now(UTC).isoformat()
    adapter.store_device(
        {"hostname": "good-host", "connection_ip": "192.168.1.10", "status": "success", "last_seen": now}
    )
    adapter.store_device(
        {"hostname": "broken-host", "connection_ip": "192.168.1.11", "status": "error", "last_seen": now}
    )
    adapter.store_device({"hostname": "", "connection_ip": "192.168.1.12", "status": "success", "last_seen": now})
    adapter.store_device(
        {"hostname": "unknown", "connection_ip": "192.168.1.13", "status": "success", "last_seen": now}
    )
    return adapter


class TestPhase44AliasParity:
    def test_purge_failed_devices_equals_failed_discovery_filter_dry_run(
        self, seeded_with_failed_rows: SQLiteAdapter
    ) -> None:
        """D-07: refactored adapter delegates via 'failed_discovery' sentinel.
        Byte-identical row sets on the same seeded DB."""
        via_adapter = seeded_with_failed_rows.purge_failed_devices(dry_run=True)
        via_helper = _purge_devices_by_filter(seeded_with_failed_rows, "sqlite", "failed_discovery", None, dry_run=True)
        assert via_adapter == via_helper
        # And it picks up exactly the 3 non-good rows (D-08 4-clause OR).
        hostnames = {r["hostname"] for r in via_adapter}
        assert hostnames == {"broken-host", "", "unknown"}
        assert "good-host" not in hostnames

    def test_purge_failed_devices_equals_failed_discovery_filter_live(
        self, seeded_with_failed_rows: SQLiteAdapter
    ) -> None:
        """Live deletion parity — both code paths leave the same DB state."""
        # Snapshot the rows that should be deleted (via dry_run preview).
        preview = _purge_devices_by_filter(seeded_with_failed_rows, "sqlite", "failed_discovery", None, dry_run=True)
        # Now delete via the alias.
        removed = seeded_with_failed_rows.purge_failed_devices(dry_run=False)
        assert removed == preview
        # Only good-host remains.
        assert seeded_with_failed_rows.connection is not None
        cur = seeded_with_failed_rows.connection.execute("SELECT hostname FROM devices ORDER BY id")
        remaining = [row[0] for row in cur.fetchall()]
        assert remaining == ["good-host"]

    def test_purge_failed_devices_delegates_through_helper(self, seeded_with_failed_rows: SQLiteAdapter) -> None:
        """Issue 11 lock: the refactored adapter MUST invoke
        _purge_devices_by_filter with the exact delegation shape.

        Catches future drift where someone "fixes" the delegation by inlining
        SQL again — the mock assertion fails immediately on shape divergence.
        """
        with patch(
            "homelab_mcp.database._purge_devices_by_filter",
            wraps=_purge_devices_by_filter,
        ) as mock_helper:
            seeded_with_failed_rows.purge_failed_devices(dry_run=True)
        mock_helper.assert_called_once_with(
            seeded_with_failed_rows,
            "sqlite",
            "failed_discovery",
            None,
            dry_run=True,
        )

    @pytest.mark.asyncio
    async def test_handler_envelope_unchanged_after_refactor(self, seeded_with_failed_rows: SQLiteAdapter) -> None:
        """D-07: external behavior of handle_purge_failed_discoveries is byte-identical
        to the pre-Phase-44 envelope. status, dry_run, purged_count, purged_devices keys."""
        with patch("homelab_mcp.tool_handlers.network_handlers.NetworkSiteMap") as MockSM:
            MockSM.return_value.db_adapter = seeded_with_failed_rows
            MockSM.return_value.purge_failed_devices = seeded_with_failed_rows.purge_failed_devices
            result = await handle_purge_failed_discoveries({"dry_run": True})
        payload = json.loads(result["content"][0]["text"])
        assert set(payload.keys()) == {"status", "dry_run", "purged_count", "purged_devices"}
        assert payload["status"] == "success"
        assert payload["dry_run"] is True
        assert payload["purged_count"] == 3
        assert len(payload["purged_devices"]) == 3
