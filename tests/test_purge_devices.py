"""Phase 44: purge_devices tool tests (D-01..D-08, D-11, D-14).

Covers:
  - Per-filter_type behavior: hostname (exact match, D-02), status (D-05),
    last_seen_older_than_days (D-04 boundary), ip_range (CIDR membership D-03,
    IPv6 + single-IP /32 + non-IP skip D-03a).
  - Dry-run preview shape (D-01a).
  - Zero-match returns success with empty list (D-01c).
  - Bad value shape returns structured-error envelope with hint (D-01b).
  - Bad filter_type returns structured-error envelope.
  - status='error' filter does NOT match zombie-hostname rows (D-08).
  - Preview thin-delegate (D-11).
  - Dedicated _row_in_cidr unit tests (Issue 7 split — Task 1a behavior coverage).
"""

from __future__ import annotations

import ipaddress
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from homelab_mcp.database import (
    SQLiteAdapter,
    _build_filter_clause,
    _purge_devices_by_filter,
    _row_in_cidr,
)
from homelab_mcp.tool_handlers.network_handlers import (
    handle_purge_devices,
    handle_purge_devices_preview,
)

NSM_PATH = "homelab_mcp.tool_handlers.network_handlers.NetworkSiteMap"


@pytest.fixture
def fresh_adapter(tmp_path: Path) -> SQLiteAdapter:
    db_path = tmp_path / "test_sitemap.db"
    adapter = SQLiteAdapter(db_path=str(db_path))
    adapter.init_schema()
    return adapter


@pytest.fixture
def seeded_diverse(fresh_adapter: SQLiteAdapter) -> SQLiteAdapter:
    """Seed: 1 success row pve-test 192.168.10.20; 1 error row pve-fail 10.0.0.5;
    1 zombie row hostname='' connection_ip=''; 1 stale row pve-old 192.168.20.30
    with last_seen 30 days ago; 1 IPv6 row v6host fe80::1.

    Total: 5 seeded rows."""
    now = datetime.now(UTC).isoformat()
    old = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    rows = [
        {"hostname": "pve-test", "connection_ip": "192.168.10.20", "status": "success", "last_seen": now},
        {"hostname": "pve-fail", "connection_ip": "10.0.0.5", "status": "error", "last_seen": now},
        {"hostname": "", "connection_ip": "", "status": "success", "last_seen": now},
        {"hostname": "pve-old", "connection_ip": "192.168.20.30", "status": "success", "last_seen": old},
        {"hostname": "v6host", "connection_ip": "fe80::1", "status": "success", "last_seen": now},
    ]
    for row in rows:
        fresh_adapter.store_device(row)
    return fresh_adapter


class TestPhase44RowInCidr:
    """Issue 7 split — dedicated unit tests for _row_in_cidr (Task 1a)."""

    def test_ipv4_inside_subnet(self) -> None:
        net = ipaddress.ip_network("192.168.1.0/24")
        assert _row_in_cidr({"connection_ip": "192.168.1.5"}, net) is True

    def test_ipv4_outside_subnet(self) -> None:
        net = ipaddress.ip_network("192.168.1.0/24")
        assert _row_in_cidr({"connection_ip": "10.0.0.5"}, net) is False

    def test_ipv6_inside_subnet(self) -> None:
        net = ipaddress.ip_network("fe80::/10")
        assert _row_in_cidr({"connection_ip": "fe80::1"}, net) is True

    def test_single_ip_slash_32(self) -> None:
        net = ipaddress.ip_network("192.168.1.5/32")
        assert _row_in_cidr({"connection_ip": "192.168.1.5"}, net) is True
        assert _row_in_cidr({"connection_ip": "192.168.1.6"}, net) is False

    def test_empty_connection_ip_skipped(self) -> None:
        """D-03a: empty string connection_ip is silently skipped (no raise)."""
        net = ipaddress.ip_network("0.0.0.0/0")
        assert _row_in_cidr({"connection_ip": ""}, net) is False

    def test_missing_connection_ip_key_skipped(self) -> None:
        """D-03a: missing key is silently skipped (no KeyError)."""
        net = ipaddress.ip_network("0.0.0.0/0")
        assert _row_in_cidr({}, net) is False

    def test_unparseable_connection_ip_skipped(self) -> None:
        """D-03a: hostname-fallback row connection_ip='not-an-ip' silently skipped."""
        net = ipaddress.ip_network("0.0.0.0/0")
        assert _row_in_cidr({"connection_ip": "not-an-ip"}, net) is False


class TestPhase44PurgeDevicesFilters:
    """Per-filter_type behavior tests (D-02, D-04, D-05, D-03)."""

    def test_hostname_exact_match(self, seeded_diverse: SQLiteAdapter) -> None:
        removed = _purge_devices_by_filter(seeded_diverse, "sqlite", "hostname", "pve-test")
        assert len(removed) == 1
        assert removed[0]["hostname"] == "pve-test"

    def test_hostname_no_glob_no_like(self, seeded_diverse: SQLiteAdapter) -> None:
        # 'pve-%' or 'pve*' should NOT match anything (D-02 — no wildcards).
        removed = _purge_devices_by_filter(seeded_diverse, "sqlite", "hostname", "pve-%")
        assert removed == []

    def test_status_error_matches_only_status_error(self, seeded_diverse: SQLiteAdapter) -> None:
        """D-08: bare status='error' does NOT pick up zombie-hostname rows."""
        removed = _purge_devices_by_filter(seeded_diverse, "sqlite", "status", "error")
        assert len(removed) == 1
        assert removed[0]["status"] == "error"
        assert removed[0]["hostname"] == "pve-fail"
        # zombie row (hostname='') is NOT in the removed set even though
        # purge_failed_discoveries would have caught it.

    def test_last_seen_older_than_days(self, seeded_diverse: SQLiteAdapter) -> None:
        removed = _purge_devices_by_filter(seeded_diverse, "sqlite", "last_seen_older_than_days", 7)
        assert len(removed) == 1
        assert removed[0]["hostname"] == "pve-old"

    def test_last_seen_zero_matches_all_seeded_rows(self, seeded_diverse: SQLiteAdapter) -> None:
        """D-04 N=0 sanity-check filter — matches ALL rows whose `last_seen` is
        strictly less than `datetime.now(UTC)` at query time. Since seeded rows
        are inserted microseconds before the query runs, all 5 seeded rows match
        (including the just-inserted 'now' rows). This is the documented D-04
        behavior — useful as a 'purge anything stale right now' filter.

        The boundary is exclusive (`<`). The exclusivity matters when a row's
        `last_seen` ties exactly with the query-time `now`, but in practice the
        query-time `now` is microseconds after row insertion, so the strict-less-than
        comparison succeeds for every seeded row."""
        removed = _purge_devices_by_filter(seeded_diverse, "sqlite", "last_seen_older_than_days", 0, dry_run=True)
        # Five rows seeded; all five match because each was inserted microseconds
        # before this query computed `now`. The 30-day-old row (pve-old) is
        # included alongside the four "now" rows.
        assert len(removed) == 5
        hostnames = {r["hostname"] for r in removed}
        # All seeded hostnames present (including the empty-string zombie).
        assert hostnames == {"pve-test", "pve-fail", "", "pve-old", "v6host"}

    def test_ip_range_cidr_v4(self, seeded_diverse: SQLiteAdapter) -> None:
        removed = _purge_devices_by_filter(seeded_diverse, "sqlite", "ip_range", "192.168.0.0/16")
        hostnames = {r["hostname"] for r in removed}
        assert "pve-test" in hostnames
        assert "pve-old" in hostnames
        assert "pve-fail" not in hostnames  # 10.0.0.5 outside /16

    def test_ip_range_cidr_v6(self, seeded_diverse: SQLiteAdapter) -> None:
        removed = _purge_devices_by_filter(seeded_diverse, "sqlite", "ip_range", "fe80::/10")
        assert any(r["hostname"] == "v6host" for r in removed)

    def test_ip_range_single_ip_slash_32(self, seeded_diverse: SQLiteAdapter) -> None:
        removed = _purge_devices_by_filter(seeded_diverse, "sqlite", "ip_range", "192.168.10.20/32")
        assert len(removed) == 1
        assert removed[0]["hostname"] == "pve-test"

    def test_ip_range_skips_unparseable_connection_ip(self, seeded_diverse: SQLiteAdapter) -> None:
        """D-03a: zombie row with connection_ip='' is silently skipped — never matches."""
        removed = _purge_devices_by_filter(seeded_diverse, "sqlite", "ip_range", "0.0.0.0/0", dry_run=True)
        # 0.0.0.0/0 matches all valid IPv4. Zombie row's '' is skipped.
        hostnames = {r["hostname"] for r in removed}
        assert "" not in hostnames


class TestPhase44PurgeDevicesDryRun:
    def test_dry_run_does_not_delete(self, seeded_diverse: SQLiteAdapter) -> None:
        removed = _purge_devices_by_filter(seeded_diverse, "sqlite", "hostname", "pve-test", dry_run=True)
        assert len(removed) == 1
        # Row still present.
        assert seeded_diverse.connection is not None
        cur = seeded_diverse.connection.execute("SELECT COUNT(*) FROM devices WHERE hostname = ?", ("pve-test",))
        assert cur.fetchone()[0] == 1


class TestPhase44PurgeDevicesZeroMatch:
    def test_zero_match_returns_success_empty(self, seeded_diverse: SQLiteAdapter) -> None:
        """D-01c: zero-match is success, never error."""
        removed = _purge_devices_by_filter(seeded_diverse, "sqlite", "hostname", "no-such-host")
        assert removed == []


class TestPhase44BuildFilterClauseValidation:
    """Direct unit tests on _build_filter_clause shape (D-01b)."""

    def test_last_seen_must_be_int(self) -> None:
        with pytest.raises(ValueError, match="must be int"):
            _build_filter_clause("last_seen_older_than_days", "7", "sqlite")

    def test_last_seen_rejects_bool(self) -> None:
        """bool is a subclass of int in Python — explicitly reject."""
        with pytest.raises(ValueError, match="must be int"):
            _build_filter_clause("last_seen_older_than_days", True, "sqlite")

    def test_hostname_must_be_str(self) -> None:
        with pytest.raises(ValueError, match="must be str"):
            _build_filter_clause("hostname", 42, "sqlite")

    def test_status_must_be_str(self) -> None:
        with pytest.raises(ValueError, match="must be str"):
            _build_filter_clause("status", 1, "sqlite")

    def test_unknown_filter_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown filter_type"):
            _build_filter_clause("unknown", "x", "sqlite")

    def test_postgres_dialect_uses_percent_s(self) -> None:
        where, _params = _build_filter_clause("hostname", "h", "postgres")
        assert "%s" in where
        assert "?" not in where

    def test_sqlite_dialect_uses_question_mark(self) -> None:
        where, _params = _build_filter_clause("hostname", "h", "sqlite")
        assert "?" in where
        assert "%s" not in where


class TestPhase44PurgeDevicesHandler:
    """Handler-level tests for handle_purge_devices + preview."""

    @pytest.mark.asyncio
    async def test_happy_path_envelope(self, seeded_diverse: SQLiteAdapter) -> None:
        with patch(NSM_PATH) as MockSM:
            MockSM.return_value.db_adapter = seeded_diverse
            result = await handle_purge_devices({"filter_type": "hostname", "value": "pve-test"})
        payload = json.loads(result["content"][0]["text"])
        assert payload["status"] == "success"
        assert payload["dry_run"] is False
        assert payload["purged_count"] == 1
        assert len(payload["purged_devices"]) == 1

    @pytest.mark.asyncio
    async def test_zero_match_success(self, seeded_diverse: SQLiteAdapter) -> None:
        with patch(NSM_PATH) as MockSM:
            MockSM.return_value.db_adapter = seeded_diverse
            result = await handle_purge_devices({"filter_type": "hostname", "value": "no-such-host"})
        payload = json.loads(result["content"][0]["text"])
        assert payload["status"] == "success"
        assert payload["purged_count"] == 0
        assert payload["purged_devices"] == []

    @pytest.mark.asyncio
    async def test_invalid_filter_type_returns_error_envelope(self, seeded_diverse: SQLiteAdapter) -> None:
        with patch(NSM_PATH) as MockSM:
            MockSM.return_value.db_adapter = seeded_diverse
            result = await handle_purge_devices({"filter_type": "bogus", "value": "x"})
        payload = json.loads(result["content"][0]["text"])
        assert payload["status"] == "error"
        assert "Invalid filter_type" in payload["error"]
        assert "hostname" in payload["error"]  # lists valid options

    @pytest.mark.asyncio
    async def test_bad_value_shape_returns_error_envelope(self, seeded_diverse: SQLiteAdapter) -> None:
        with patch(NSM_PATH) as MockSM:
            MockSM.return_value.db_adapter = seeded_diverse
            result = await handle_purge_devices({"filter_type": "last_seen_older_than_days", "value": "not-int"})
        payload = json.loads(result["content"][0]["text"])
        assert payload["status"] == "error"
        assert "must be int" in payload["error"]
        assert "integer day count" in payload["hint"]

    @pytest.mark.asyncio
    async def test_invalid_cidr_returns_error_envelope(self, seeded_diverse: SQLiteAdapter) -> None:
        with patch(NSM_PATH) as MockSM:
            MockSM.return_value.db_adapter = seeded_diverse
            result = await handle_purge_devices({"filter_type": "ip_range", "value": "not-a-cidr"})
        payload = json.loads(result["content"][0]["text"])
        assert payload["status"] == "error"
        assert "Invalid CIDR" in payload["error"]
        assert "192.168" in payload["hint"]  # CIDR example in hint

    @pytest.mark.asyncio
    async def test_preview_is_thin_delegate(self, seeded_diverse: SQLiteAdapter) -> None:
        with patch(NSM_PATH) as MockSM:
            MockSM.return_value.db_adapter = seeded_diverse
            result = await handle_purge_devices_preview({"filter_type": "hostname", "value": "pve-test"})
        payload = json.loads(result["content"][0]["text"])
        assert payload["status"] == "success"
        assert payload["dry_run"] is True
        # Row still present after preview.
        assert seeded_diverse.connection is not None
        cur = seeded_diverse.connection.execute("SELECT COUNT(*) FROM devices WHERE hostname = ?", ("pve-test",))
        assert cur.fetchone()[0] == 1
