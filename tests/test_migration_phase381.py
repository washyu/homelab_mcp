"""Phase 38.1 Wave 0 RED scaffolds (Plan 01 Task 3): destructive migration tests.

These tests pin down the contract for Plan 04's drop-and-recreate migration:
- D-19 version stamp idempotency
- D-20 ordering (backup before drop, stamp last)
- D-21 three-block stderr banner with W5 explicit discovery_history mention
- D-22 microsecond-precision timestamp on backup filename
- W5 FK-dependent discovery_history rows clear on SQLite
- I8 backup file mode preservation (T-38.1-04-02 scaffold)

All tests fail or error until Plan 04 (Wave 2) lands the destructive migration
helpers (`_phase_38_1_applied`, `_stamp_migration`, `_PHASE_38_1_KEY`,
`_MIGRATION_STATE_PATH`) inside `src/homelab_mcp/migration.py`.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime
from pathlib import Path

import pytest

from homelab_mcp.database import SQLiteAdapter


def _seed_registry(registry_path: Path) -> None:
    registry_path.write_text(
        json.dumps(
            [
                {
                    "hostname": "pve",
                    "username": "root",
                    "credential_type": "proxmox",
                    "auth_type": "password",
                    "scope": "node",
                    "cluster_name": "",
                }
            ]
        ),
        encoding="utf-8",
    )


def _bootstrap_sqlite(db_path: Path) -> SQLiteAdapter:
    adapter = SQLiteAdapter(str(db_path))
    adapter.connect()
    adapter.init_schema()
    return adapter


def _reset_phase_38_1_state(stamp_path: Path, registry_path: Path) -> None:
    """After ``_bootstrap_sqlite``, ``init_schema`` already fired the destructive
    migration once. To exercise the destructive path again under controlled
    state, clear the stamp file and re-seed the registry so the second
    ``run_sqlite_migrations`` call sees a fresh first-run condition.
    """
    stamp_path.unlink(missing_ok=True)
    if not registry_path.exists():
        _seed_registry(registry_path)


def _seed_device_and_history(adapter: SQLiteAdapter) -> int:
    device_id = adapter.store_device(
        {
            "hostname": "pve",
            "connection_ip": "10.0.0.10",
            "last_seen": datetime.now().isoformat(),
            "status": "success",
        }
    )
    assert adapter.connection is not None
    adapter.connection.execute(
        "INSERT INTO discovery_history (device_id, discovery_data) VALUES (?, ?)",
        (device_id, json.dumps({"status": "success"})),
    )
    adapter.connection.commit()
    return int(device_id)


def _install_legacy_devices_table(adapter: SQLiteAdapter) -> int:
    """Recreate the ``devices`` table in its pre-Phase-38.1 ("legacy") shape.

    Plan 04 added a CR-01/WR-09 defense-in-depth guard at migration.py:208-227:
    the destructive R10 block only fires when a pre-existing ``devices`` table
    EXISTS WITHOUT the binding columns (``ssh_credential_id``,
    ``proxmox_credential_id``). ``SQLiteAdapter.init_schema`` now creates the
    table with binding columns built in, so ``_bootstrap_sqlite`` produces a
    state where the guard correctly skips the destructive path.

    To exercise the destructive path under controlled state, this helper
    drops the migrated-shape table and recreates it in the legacy schema
    (no binding columns), then seeds one device row and one
    discovery_history row using direct SQL (``adapter.store_device``
    targets the migrated schema, so we INSERT manually). Returns the
    inserted device id.
    """
    assert adapter.connection is not None
    cursor = adapter.connection.cursor()
    cursor.execute("DROP TABLE IF EXISTS discovery_history")
    cursor.execute("DROP TABLE IF EXISTS devices")
    # Legacy schema: NO ssh_credential_id / proxmox_credential_id columns.
    cursor.executescript(
        """
        CREATE TABLE devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hostname TEXT NOT NULL,
            connection_ip TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            status TEXT NOT NULL,
            cpu_model TEXT,
            cpu_cores INTEGER,
            memory_total TEXT, memory_used TEXT, memory_free TEXT, memory_available TEXT,
            disk_filesystem TEXT, disk_size TEXT, disk_used TEXT, disk_available TEXT,
            disk_use_percent TEXT, disk_mount TEXT,
            network_interfaces TEXT,
            usb_devices TEXT, pci_devices TEXT, block_devices TEXT,
            fingerprint TEXT,
            uptime TEXT,
            os_info TEXT,
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE discovery_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER,
            discovery_data TEXT,
            data_hash TEXT,
            discovered_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (device_id) REFERENCES devices (id)
        );
        CREATE INDEX IF NOT EXISTS idx_devices_hostname ON devices (hostname);
        CREATE INDEX IF NOT EXISTS idx_history_device_id ON discovery_history (device_id);
        """
    )
    cursor.execute(
        """
        INSERT INTO devices (hostname, connection_ip, last_seen, status)
        VALUES (?, ?, ?, ?)
        """,
        ("pve", "10.0.0.10", datetime.now().isoformat(), "success"),
    )
    device_id = int(cursor.lastrowid or 0)
    cursor.execute(
        "INSERT INTO discovery_history (device_id, discovery_data) VALUES (?, ?)",
        (device_id, json.dumps({"status": "success"})),
    )
    adapter.connection.commit()
    return device_id


def test_first_run_archives_registry_to_bak_phase381(tmp_path, monkeypatch, capsys):
    """R10/D-21: first run archives `_REGISTRY_PATH` to `.bak.<microsecond_ts>`."""
    from homelab_mcp.migration import run_sqlite_migrations

    registry_path = tmp_path / "credential_registry.json"
    stamp_path = tmp_path / "migration_state.json"
    _seed_registry(registry_path)
    monkeypatch.setattr("homelab_mcp.credential_store._REGISTRY_PATH", registry_path)
    monkeypatch.setattr("homelab_mcp.migration._MIGRATION_STATE_PATH", stamp_path, raising=False)

    db_path = tmp_path / "sitemap.db"
    adapter = _bootstrap_sqlite(db_path)
    # Per CR-01/WR-09 guard: the destructive path only fires when the live
    # devices table is in legacy shape. Install legacy schema, then reset
    # the stamp so the next migration call exercises the destructive block.
    _install_legacy_devices_table(adapter)
    _reset_phase_38_1_state(stamp_path, registry_path)
    try:
        run_sqlite_migrations(_connection=adapter.connection)
    finally:
        adapter.close()

    bak_files = sorted(tmp_path.glob("credential_registry.json.bak.*"))
    assert len(bak_files) == 1, (
        f"Phase 38.1 R10/D-21: expected exactly one .bak file in {tmp_path}, found {[p.name for p in bak_files]}"
    )
    assert not registry_path.exists(), (
        "Phase 38.1 R10/D-20: original credential_registry.json must be archived (renamed), not copied"
    )

    captured = capsys.readouterr()
    assert "Archived credential registry to" in captured.err
    assert "v1.7" in captured.err and "credential uuid" in captured.err.lower()
    assert "Recovery" in captured.err


def test_first_run_drops_devices_table_phase381(tmp_path, monkeypatch):
    """R10: first run drops the `devices` table (rows do not survive)."""
    from homelab_mcp.migration import run_sqlite_migrations

    registry_path = tmp_path / "credential_registry.json"
    stamp_path = tmp_path / "migration_state.json"
    _seed_registry(registry_path)
    monkeypatch.setattr("homelab_mcp.credential_store._REGISTRY_PATH", registry_path)
    monkeypatch.setattr("homelab_mcp.migration._MIGRATION_STATE_PATH", stamp_path, raising=False)

    db_path = tmp_path / "sitemap.db"
    adapter = _bootstrap_sqlite(db_path)
    # CR-01/WR-09 guard: only fires when devices table lacks binding columns.
    # Install legacy schema (no bindings) + seed a row + reset stamp so the
    # destructive path actually runs and we can assert on its post-state.
    _install_legacy_devices_table(adapter)
    _reset_phase_38_1_state(stamp_path, registry_path)
    try:
        run_sqlite_migrations(_connection=adapter.connection)
        assert adapter.connection is not None
        count = adapter.connection.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
    finally:
        adapter.close()

    assert count == 0, f"Phase 38.1 R10: expected 0 rows in devices after destructive migration, got {count}"


def test_first_run_clears_discovery_history_phase381(tmp_path, monkeypatch):
    """W5: FK-dependent discovery_history rows are cleared on SQLite (banner block 1 promises this)."""
    from homelab_mcp.migration import run_sqlite_migrations

    registry_path = tmp_path / "credential_registry.json"
    stamp_path = tmp_path / "migration_state.json"
    _seed_registry(registry_path)
    monkeypatch.setattr("homelab_mcp.credential_store._REGISTRY_PATH", registry_path)
    monkeypatch.setattr("homelab_mcp.migration._MIGRATION_STATE_PATH", stamp_path, raising=False)

    db_path = tmp_path / "sitemap.db"
    adapter = _bootstrap_sqlite(db_path)
    # CR-01/WR-09 guard: legacy table required to fire destructive path.
    _install_legacy_devices_table(adapter)
    _reset_phase_38_1_state(stamp_path, registry_path)
    try:
        run_sqlite_migrations(_connection=adapter.connection)
        assert adapter.connection is not None
        history_count = adapter.connection.execute("SELECT COUNT(*) FROM discovery_history").fetchone()[0]
    finally:
        adapter.close()

    assert history_count == 0, (
        f"Phase 38.1 W5: expected 0 rows in discovery_history after migration, got {history_count}"
    )


def test_first_run_writes_version_stamp_phase381(tmp_path, monkeypatch):
    """D-19: stamp file written after successful drop."""
    from homelab_mcp.migration import run_sqlite_migrations

    registry_path = tmp_path / "credential_registry.json"
    _seed_registry(registry_path)
    stamp_path = tmp_path / "migration_state.json"
    monkeypatch.setattr("homelab_mcp.credential_store._REGISTRY_PATH", registry_path)
    monkeypatch.setattr("homelab_mcp.migration._MIGRATION_STATE_PATH", stamp_path, raising=False)

    db_path = tmp_path / "sitemap.db"
    adapter = _bootstrap_sqlite(db_path)
    try:
        run_sqlite_migrations(_connection=adapter.connection)
    finally:
        adapter.close()

    assert stamp_path.exists(), f"Phase 38.1 D-19: expected migration stamp at {stamp_path}, not found"
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    assert stamp.get("phase_38_1_credential_binding_applied") is True, (
        f"Phase 38.1 D-19: stamp missing phase_38_1_credential_binding_applied=true, got {stamp!r}"
    )


def test_second_run_is_noop_after_stamp_phase381(tmp_path, monkeypatch):
    """D-19: idempotency — second invocation does NOT re-archive or re-drop."""
    from homelab_mcp.migration import run_sqlite_migrations

    registry_path = tmp_path / "credential_registry.json"
    _seed_registry(registry_path)
    monkeypatch.setattr("homelab_mcp.credential_store._REGISTRY_PATH", registry_path)
    monkeypatch.setattr(
        "homelab_mcp.migration._MIGRATION_STATE_PATH",
        tmp_path / "migration_state.json",
        raising=False,
    )

    db_path = tmp_path / "sitemap.db"
    adapter = _bootstrap_sqlite(db_path)
    try:
        run_sqlite_migrations(_connection=adapter.connection)
        bak_after_first = sorted(tmp_path.glob("credential_registry.json.bak.*"))

        device_id = _seed_device_and_history(adapter)
        run_sqlite_migrations(_connection=adapter.connection)

        assert adapter.connection is not None
        survived = adapter.connection.execute("SELECT COUNT(*) FROM devices WHERE id = ?", (device_id,)).fetchone()[0]
    finally:
        adapter.close()

    bak_after_second = sorted(tmp_path.glob("credential_registry.json.bak.*"))
    assert bak_after_second == bak_after_first, "Phase 38.1 D-19: second run must NOT create another .bak file"
    assert survived == 1, "Phase 38.1 D-19: second run must NOT re-drop devices — post-migration row vanished"


def test_drop_failure_leaves_stamp_unwritten_phase381(tmp_path, monkeypatch):
    """D-20: if drop fails, stamp is not written, but backup IS written (ordering safety).

    Patches the connection's ``cursor()`` method so the cursor's ``execute()``
    raises on ``DROP TABLE``. Real ``sqlite3.Connection.execute`` is read-only;
    we proxy the cursor instead, which is what the migration code actually uses.
    """
    from unittest.mock import MagicMock

    from homelab_mcp import migration as migration_module

    registry_path = tmp_path / "credential_registry.json"
    _seed_registry(registry_path)
    stamp_path = tmp_path / "migration_state.json"
    monkeypatch.setattr("homelab_mcp.credential_store._REGISTRY_PATH", registry_path)
    monkeypatch.setattr("homelab_mcp.migration._MIGRATION_STATE_PATH", stamp_path, raising=False)

    db_path = tmp_path / "sitemap.db"
    adapter = _bootstrap_sqlite(db_path)
    # CR-01/WR-09 guard: drop failure is only observable when destructive
    # path runs. Install legacy table + reset stamp so the migration's
    # DROP TABLE attempt is reachable through the failing-cursor proxy.
    _install_legacy_devices_table(adapter)
    _reset_phase_38_1_state(stamp_path, registry_path)
    for prior_bak in tmp_path.glob("credential_registry.json.bak.*"):
        prior_bak.unlink()
    try:
        real_cursor = adapter.connection.cursor()

        def _execute_failing_drop(sql, *args, **kwargs):
            if isinstance(sql, str) and "DROP TABLE" in sql.upper():
                raise RuntimeError("simulated drop failure (D-20 ordering test)")
            return real_cursor.execute(sql, *args, **kwargs)

        proxy_cursor = MagicMock(wraps=real_cursor)
        proxy_cursor.execute = _execute_failing_drop
        proxy_cursor.fetchone = real_cursor.fetchone
        proxy_cursor.fetchall = real_cursor.fetchall

        proxy_conn = MagicMock(wraps=adapter.connection)
        proxy_conn.cursor = lambda: proxy_cursor
        proxy_conn.commit = adapter.connection.commit

        with pytest.raises(RuntimeError):
            migration_module.run_sqlite_migrations(_connection=proxy_conn)
    finally:
        adapter.close()

    bak_files = list(tmp_path.glob("credential_registry.json.bak.*"))
    assert len(bak_files) == 1, (
        f"Phase 38.1 D-20: backup must be written BEFORE drop attempt; got {[p.name for p in bak_files]}"
    )
    assert not stamp_path.exists(), "Phase 38.1 D-20: stamp must NOT be written when drop fails"


def test_bak_filename_collision_uses_microsecond_timestamp_per_d22(tmp_path, monkeypatch):
    """D-22: pre-existing second-resolution .bak does NOT block; microsecond timestamp wins."""
    from homelab_mcp.migration import run_sqlite_migrations

    registry_path = tmp_path / "credential_registry.json"
    stamp_path = tmp_path / "migration_state.json"
    _seed_registry(registry_path)

    second_resolution_collision = tmp_path / "credential_registry.json.bak.20260427000000"
    second_resolution_collision.write_text("preexisting", encoding="utf-8")

    monkeypatch.setattr("homelab_mcp.credential_store._REGISTRY_PATH", registry_path)
    monkeypatch.setattr("homelab_mcp.migration._MIGRATION_STATE_PATH", stamp_path, raising=False)

    db_path = tmp_path / "sitemap.db"
    adapter = _bootstrap_sqlite(db_path)
    # CR-01/WR-09 guard: backup file is only written by the destructive
    # path. Install legacy table + reset stamp so the migration archives
    # the registry to a fresh microsecond-stamped .bak.
    _install_legacy_devices_table(adapter)
    _reset_phase_38_1_state(stamp_path, registry_path)
    try:
        run_sqlite_migrations(_connection=adapter.connection)
    finally:
        adapter.close()

    assert second_resolution_collision.read_text(encoding="utf-8") == "preexisting", (
        "Phase 38.1 D-22: existing .bak file must NOT be overwritten"
    )
    new_baks = [p for p in tmp_path.glob("credential_registry.json.bak.*") if p != second_resolution_collision]
    assert len(new_baks) == 1, (
        f"Phase 38.1 D-22: expected one new microsecond-stamped .bak, got {[p.name for p in new_baks]}"
    )
    suffix = new_baks[0].name.rsplit(".bak.", 1)[-1]
    assert len(suffix) >= 17 and any(c == "_" or c.isdigit() for c in suffix), (
        f"Phase 38.1 D-22: backup suffix {suffix!r} should embed microsecond precision"
    )


def test_banner_printed_to_stderr_3_blocks_per_d21(tmp_path, monkeypatch, capsys):
    """D-21 + W5: banner emits 3 stderr blocks; block 1 names devices AND discovery_history."""
    from homelab_mcp.migration import run_sqlite_migrations

    registry_path = tmp_path / "credential_registry.json"
    stamp_path = tmp_path / "migration_state.json"
    _seed_registry(registry_path)
    monkeypatch.setattr("homelab_mcp.credential_store._REGISTRY_PATH", registry_path)
    monkeypatch.setattr("homelab_mcp.migration._MIGRATION_STATE_PATH", stamp_path, raising=False)

    db_path = tmp_path / "sitemap.db"
    adapter = _bootstrap_sqlite(db_path)
    # CR-01/WR-09 guard: banner is only emitted by the destructive path.
    _install_legacy_devices_table(adapter)
    _reset_phase_38_1_state(stamp_path, registry_path)
    try:
        run_sqlite_migrations(_connection=adapter.connection)
    finally:
        adapter.close()

    err = capsys.readouterr().err
    blocks = [b for b in err.split("\n\n") if b.strip()]
    assert len(blocks) >= 3, f"Phase 38.1 D-21: banner must emit at least 3 stderr blocks, got {len(blocks)}: {err!r}"

    block1 = blocks[0].lower()
    assert "devices" in block1 and "discovery_history" in block1, (
        f"Phase 38.1 W5: block 1 must explicitly name BOTH `devices` and `discovery_history`; got {blocks[0]!r}"
    )


def test_backup_file_mode_preserved_phase381(tmp_path, monkeypatch):
    """I8 / T-38.1-04-02: Path.rename() preserves the source file's permission bits.

    Skipped on Windows where os.chmod() doesn't honour POSIX modes.
    """
    if os.name == "nt":
        pytest.skip("POSIX file modes are not meaningful on Windows")

    from homelab_mcp.migration import run_sqlite_migrations

    registry_path = tmp_path / "credential_registry.json"
    _seed_registry(registry_path)
    os.chmod(registry_path, 0o600)

    monkeypatch.setattr("homelab_mcp.credential_store._REGISTRY_PATH", registry_path)
    monkeypatch.setattr(
        "homelab_mcp.migration._MIGRATION_STATE_PATH",
        tmp_path / "migration_state.json",
        raising=False,
    )

    db_path = tmp_path / "sitemap.db"
    adapter = _bootstrap_sqlite(db_path)
    try:
        run_sqlite_migrations(_connection=adapter.connection)
    finally:
        adapter.close()

    bak_files = list(tmp_path.glob("credential_registry.json.bak.*"))
    assert len(bak_files) == 1
    bak_mode = stat.S_IMODE(os.stat(bak_files[0]).st_mode)
    assert bak_mode == 0o600, f"Phase 38.1 I8: backup mode must be preserved at 0o600, got {oct(bak_mode)}"
