---
phase: 38-sitemap-fingerprint-schema
plan: 03
subsystem: database
tags: [sqlite, postgres, jsonb, sitemap, fingerprint, drift-detection, adapter, round-trip]

# Dependency graph
requires:
  - phase: 35-sitemap-discovery-reliability
    provides: "Phase 35 D-09b column-grouping convention for JSON-string columns (usb/pci/block); _maybe_json_load helper for Postgres adapter; hostname-as-natural-key UPSERT path; test_store_device_jsonb mock-cursor pattern at tests/test_database.py:171"
  - phase: 38-sitemap-fingerprint-schema
    plan: 02
    provides: "fingerprint TEXT column on SQLite devices table (init_schema CREATE TABLE + idempotent ALTER TABLE migration); NetworkDevice.fingerprint dataclass field; parse_discovery_output JSON-serialize branch"
provides:
  - "SQLiteAdapter.store_device UPDATE branch writes fingerprint column (device_data.get('fingerprint'))"
  - "SQLiteAdapter.store_device INSERT branch writes fingerprint column"
  - "SQLiteAdapter.get_all_devices decodes fingerprint JSON-string back to Python dict on read (JSONDecodeError default = {} not [], since fingerprint is dict per Phase 38 D-02)"
  - "PostgreSQLAdapter.store_device places fingerprint inside system_info JSONB via _maybe_json_load (no DDL change — JSONB accommodates new sub-key)"
  - "PostgreSQLAdapter.get_all_devices flattens system_info['fingerprint'] to top-level row key (SQLite parity per Phase 35 D-09b)"
  - "homelab://devices MCP resource auto-surfaces fingerprint via db.get_all_devices() — verified zero extra wiring required (RESEARCH.md §3)"
affects: [38-04, 38-05, 38-06, 39, drift-detection-changed-bucket, mcp-devices-resource]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Phase 38 D-09 SQLite UPDATE+INSERT column-grouping for fingerprint (mirrors Phase 35 D-09b usb/pci/block layout — fingerprint placed between block_devices and uptime)"
    - "Phase 38 D-09a Postgres JSONB sub-key write via _maybe_json_load helper (handles JSON-string from parse_discovery_output + already-decoded dict from future update_device_fingerprint tool)"
    - "Phase 38 D-10 SQLite get_all_devices fingerprint JSON-decode with dict default (`{}`) — distinct from usb/pci/block list default (`[]`) loop"
    - "Phase 38 D-10 Postgres get_all_devices flatten — adds 'fingerprint' to the system_info → top-level row-dict update() call (mirrors Phase 35 D-09b usb/pci/block flatten)"

key-files:
  created: []
  modified:
    - "src/homelab_mcp/database.py (UPDATE branch SET clause line 226, UPDATE param tuple line 249, INSERT column list line 267, INSERT VALUES tuple line 291, SQLite get_all_devices JSON-decode lines 335-339, Postgres system_info dict line 598, Postgres get_all_devices flatten line 726)"
    - "tests/test_database.py (TestSQLiteAdapter: test_store_and_retrieve_fingerprint_phase38_sqlite + test_store_device_update_branch_writes_fingerprint_phase38_sqlite at lines 135-176; TestPostgreSQLAdapter: test_store_device_jsonb_includes_fingerprint_phase38 + test_store_device_update_branch_includes_fingerprint_phase38_postgres + test_get_all_devices_flattens_fingerprint_phase38_postgres at lines 240-365)"

key-decisions:
  - "JSON-decode default `{}` for fingerprint (vs `[]` for usb/pci/block) — fingerprint is a dict per Phase 38 D-02 schema; using a list default would silently flip the type on JSON corruption. Implemented as a separate `if/try/except` block AFTER the existing usb/pci/block loop rather than refactoring the loop."
  - "Postgres write via `_maybe_json_load` (Phase 35 D-09b helper) rather than a new path — _maybe_json_load already accepts both JSON-string AND already-decoded dict, which is exactly what Plan 04's update_device_fingerprint tool will need. Single helper, two callers."
  - "Postgres test convention is mock-cursor.execute.assert_called pattern (not live-DB round-trip) — established by test_store_device_jsonb at line 171; the codebase has zero live-Postgres test fixtures and zero tests under tests/integration/ for Postgres. Plan 03 follows the established convention verbatim."
  - "Out-of-scope ruff-format reformatting on drift_detection.py / test_ast_regression.py / test_migration.py reverted via `git checkout HEAD --` per executor SCOPE BOUNDARY rule. Pre-existing format drift unrelated to Phase 38 D-09."

patterns-established:
  - "Phase 38 D-09/D-10 fingerprint adapter round-trip — the canonical 5-site change for any future single-column JSON-string addition: (1) SQLite UPDATE SET, (2) SQLite UPDATE param tuple, (3) SQLite INSERT column list + VALUES tuple, (4) SQLite get_all_devices JSON-decode block, (5) Postgres system_info dict + get_all_devices flatten dict. Plan 02 already covered the schema substrate (init_schema + migration); Plan 03 covers the round-trip. Together they're the full Phase 35 D-09b mirror for a single-column dict-shaped JSON field."

requirements-completed: [DRFT-20]

# Metrics
duration: ~30min
completed: 2026-04-26
---

# Phase 38 Plan 03: Adapter Fingerprint Round-Trip Summary

**SQLite + Postgres adapters now round-trip fingerprint through both store_device branches and get_all_devices flatten — what Plan 02's parse_discovery_output stores actually persists, and Phase 39's `changed` detection reads `device['fingerprint']` as a top-level dict regardless of which adapter is active.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-04-26 (sequential executor on credential-cleanup branch)
- **Completed:** 2026-04-26
- **Tasks:** 2 (TDD: RED gate + GREEN gate)
- **Files modified:** 2 (1 source, 1 test)

## Accomplishments

- **SQLite UPDATE branch writes fingerprint.** `fingerprint = ?` added to SET clause between `block_devices = ?` and `uptime = ?` (matching the Phase 35 D-09b column-grouping convention); `device_data.get("fingerprint")` added to the parameter tuple at the matching position. Re-storing the same hostname now correctly persists the fingerprint column.
- **SQLite INSERT branch writes fingerprint.** `fingerprint` added to the column list and `device_data.get("fingerprint")` to the VALUES tuple at the matching position. Column count (24) matches the parameter count after the edit.
- **SQLite get_all_devices decodes fingerprint JSON-string back to dict.** Separate `if/try/except` block AFTER the existing usb/pci/block loop, with `{}` JSONDecodeError default (vs `[]` for the list-shaped columns). Mirrors RESEARCH.md/PATTERNS.md guidance verbatim.
- **Postgres store_device places fingerprint inside system_info JSONB.** Single line added inside the `system_info` dict literal: `"fingerprint": _maybe_json_load(device_data.get("fingerprint"))`. The helper accepts both JSON-string (from Plan 02's parse_discovery_output branch) and already-decoded dict (anticipating Plan 04's update_device_fingerprint adapter method). No Postgres DDL change — JSONB column accommodates new sub-keys.
- **Postgres get_all_devices flattens system_info['fingerprint'] to top-level row key.** Single line added inside the row-dict update() call: `"fingerprint": system_info.get("fingerprint")`. Mirrors the Phase 35 D-09b usb/pci/block flatten convention. SQLite and Postgres now return identical row shapes.
- **homelab://devices MCP resource auto-surfaces the new field.** Verified via RESEARCH.md §3 — `read_devices_resource()` calls `db.get_all_devices()` and returns each row dict whole-cloth; the new `fingerprint` top-level key flows through without any resource-side wiring change. Plan 04's `update_device_fingerprint` tool will fire `notifications/resources/list_changed` so subscribed clients see the update — that wiring is Plan 04's responsibility.
- **TDD discipline observed.** RED gate (Task 1) verified before GREEN (Task 2): all 5 fingerprint_phase38 tests written first, all confirmed RED (2 SQLite real failures + 3 Postgres mock-cursor cleanly skipped on local Windows tree where psycopg2 isn't installed), then Task 2 made all 5 GREEN.

## Task Commits

Each task committed atomically with pre-commit hooks (no `--no-verify`):

1. **Task 1: Wave-0 RED tests for adapter round-trip** — `df964b6` (test)
2. **Task 2: Wire fingerprint through both adapters (GREEN)** — `89c2f66` (feat)

_Note: This is a TDD plan (RED at Task 1, GREEN at Task 2). No REFACTOR commit was needed — the GREEN implementation follows the established Phase 35 D-09b column-grouping pattern verbatim and warranted no cleanup pass._

## Files Created/Modified

### `src/homelab_mcp/database.py`

| Change | Branch | Line | Description |
| --- | --- | --- | --- |
| Add `fingerprint = ?` | SQLite UPDATE SET clause | 226 | Between `block_devices = ?` and `uptime = ?` (column-grouping by JSON-string convention) |
| Add `device_data.get("fingerprint")` | SQLite UPDATE param tuple | 249 | Matching position to the SET clause insertion |
| Add `fingerprint` | SQLite INSERT column list | 267 | Between `block_devices` and `uptime` columns |
| Add `device_data.get("fingerprint")` | SQLite INSERT VALUES tuple | 291 | Matching position; the VALUES `?` count was bumped from 23 → 24 |
| Add fingerprint JSON-decode block | SQLite get_all_devices | 335-339 | Dict default `{}` on JSONDecodeError (distinct from usb/pci/block list default) |
| Add `"fingerprint": _maybe_json_load(...)` | Postgres system_info dict | 598 | After `block_devices` line; uses Phase 35 D-09b helper |
| Add `"fingerprint": system_info.get(...)` | Postgres get_all_devices flatten | 726 | After `block_devices` flatten line; SQLite parity |

### `tests/test_database.py`

| Test | Class | Lines (final) | Purpose |
| --- | --- | --- | --- |
| `test_store_and_retrieve_fingerprint_phase38_sqlite` | TestSQLiteAdapter | 135-160 | Real round-trip: store with `"fingerprint": json.dumps({...})` → `get_all_devices` → assert dict-shape and nested capabilities preserved |
| `test_store_device_update_branch_writes_fingerprint_phase38_sqlite` | TestSQLiteAdapter | 162-176 | Re-store same hostname (UPDATE branch) — proves UPDATE SET clause writes the column (would fail if only INSERT was wired) |
| `test_store_device_jsonb_includes_fingerprint_phase38` | TestPostgreSQLAdapter | 240-289 | Mock cursor.execute.call_args_list inspection — INSERT call's system_info JSON arg must contain fingerprint sub-dict |
| `test_store_device_update_branch_includes_fingerprint_phase38_postgres` | TestPostgreSQLAdapter | 291-322 | Mock cursor.execute inspection on UPDATE branch (existing device) — system_info JSONB carries fingerprint |
| `test_get_all_devices_flattens_fingerprint_phase38_postgres` | TestPostgreSQLAdapter | 324-365 | Prime mock fetchall with row whose system_info has fingerprint sub-dict — assert returned row has top-level `fingerprint` key |

## Decisions Made

- **JSON-decode default `{}` for fingerprint.** Phase 38 D-02 says fingerprint is a dict (`{kernel_name, kernel_version, capabilities: {...}}`). The existing usb/pci/block loop uses `[]` as the JSONDecodeError default because those are lists. Using `[]` for fingerprint would silently change the type on corruption. Implemented as a separate block AFTER the loop rather than refactoring the loop into a generic structure — keeps the change minimal and the intent explicit.
- **Postgres write via `_maybe_json_load`, not a new path.** The helper already accepts JSON-string AND already-decoded dict. Plan 04's `update_device_fingerprint` tool will need to write a Python dict (post-merge). Reusing _maybe_json_load means single-helper / two-callers — no Plan 04 surprise.
- **Postgres test pattern is mock-cursor inspection, not round-trip.** The codebase has zero live-Postgres test fixtures (`grep -r psycopg2 tests/integration/` returns nothing). The established convention is `mock_cursor.execute.assert_called_with` / `mock_cursor.execute.call_args_list` introspection — proven by the 2-year-old `test_store_device_jsonb` at line 171. Plan 03 follows this verbatim. The 3 Postgres tests skip cleanly when psycopg2 is not installed (TestPostgreSQLAdapter is gated by `@pytest.mark.skipif(not POSTGRESQL_AVAILABLE)`).
- **Out-of-scope ruff-format reformatting reverted.** The pre-commit `ruff-format` hook reformatted three pre-existing files unrelated to Plan 38-03 (`src/homelab_mcp/drift_detection.py`, `tests/test_ast_regression.py`, `tests/test_migration.py`). Per executor SCOPE BOUNDARY rule, those reverts via `git checkout HEAD -- <files>` happened before the Task 2 commit. Final commits in this plan touch exactly the two intended files.

## Deviations from Plan

None — plan executed exactly as written.

The two RED tests landed verbatim with the assertion structure described in the plan; all five Task 2 source edits mirror the Phase 35 D-09b/D-09c patterns the plan referenced.

The only out-of-band activity was the ruff-format reformat-and-revert dance documented above, which is plan-anticipated behavior under the executor SCOPE BOUNDARY rule (the plan's `<sequential_execution>` block explicitly warned about pre-commit reformatting unrelated files and instructed `git checkout -- <file>` recovery).

## Verification Results

```
uv run pytest tests/test_database.py -k fingerprint_phase38 -x         → 2 passed, 3 skipped (psycopg2 not on local Windows tree)
uv run pytest tests/test_database.py -m "not integration" -x           → 24 passed, 7 skipped
uv run pytest tests/ -m "not integration" -x --tb=line                 → 738 passed, 11 skipped, 19 deselected
uv run pytest tests/test_ast_regression.py -x                          → 11 passed (incl. test_store_device_matches_on_hostname_alone_phase35)
uv run mypy src/homelab_mcp/database.py                                → Success: no issues found in 1 source file
uv run ruff check src/homelab_mcp/database.py tests/test_database.py   → All checks passed!
./scripts/quality-check.sh                                             → All checks passed
```

### Manual greps (acceptance criteria from plan)

```
grep -n 'fingerprint = ?' src/homelab_mcp/database.py                              → line 226 (UPDATE SET clause)
grep -c 'device_data.get("fingerprint")' src/homelab_mcp/database.py               → 3 (UPDATE param, INSERT VALUES, Postgres system_info)
grep -n 'device_dict\["fingerprint"\] = json.loads' src/homelab_mcp/database.py    → line 337
grep -n '"fingerprint": _maybe_json_load' src/homelab_mcp/database.py              → line 598
grep -n '"fingerprint": system_info\.get' src/homelab_mcp/database.py              → line 726
```

All five acceptance-criteria greps return the expected lines/counts.

## Success Criteria Coverage

- [x] SQLiteAdapter.store_device writes fingerprint on both UPDATE and INSERT branches (proven by `test_store_device_update_branch_writes_fingerprint_phase38_sqlite` + `test_store_and_retrieve_fingerprint_phase38_sqlite`)
- [x] SQLiteAdapter.get_all_devices returns fingerprint as a Python dict (proven by `assert isinstance(fp_back, dict)` in `test_store_and_retrieve_fingerprint_phase38_sqlite`)
- [x] PostgreSQLAdapter.store_device places fingerprint inside system_info JSONB (proven by `test_store_device_jsonb_includes_fingerprint_phase38` mock-cursor inspection of INSERT call's system_info JSON arg)
- [x] PostgreSQLAdapter.get_all_devices flattens system_info['fingerprint'] to top-level row key (proven by `test_get_all_devices_flattens_fingerprint_phase38_postgres` priming `mock_cursor.fetchall` with system_info JSONB containing fingerprint sub-dict)
- [x] Both adapter test classes have round-trip green (SQLite tests pass on Windows; Postgres tests cleanly skip when psycopg2 unavailable; both expected-pass on CI where psycopg2 is installed)
- [x] Full unit suite + quality-check green (738 passed, 11 skipped, 19 deselected; quality-check.sh exits 0)

## Threat Model Coverage

| Threat ID | Plan disposition | Implementation outcome |
| --------- | ---------------- | ---------------------- |
| T-38-03-01 | mitigate (UPDATE/INSERT parameterization) | Confirmed: every `device_data.get("fingerprint")` value flows through `?` (sqlite3) or `%s` (psycopg2) parameter binding — same convention as every other column on the table; no string interpolation, no SQL injection vector |
| T-38-03-02 | accept (fingerprint exposure via homelab://devices) | Intended behavior — drift detection requires reading these. RESEARCH.md §3 confirmed auto-surface; no extra wiring |
| T-38-03-03 | accept (oversized fingerprint JSON DoS) | Probe sizes already bounded; SQLite TEXT and Postgres JSONB both handle multi-MB without issue |
| T-38-03-04 | mitigate (Postgres jsonb merge semantics) | Confirmed: Plan 03 only does dict-replace on `system_info["fingerprint"]` — the entire system_info dict is rewritten on every store_device call, NOT a partial JSONB merge. The full merge logic for update_device_fingerprint is Plan 04's responsibility with its own threat model |

## Threat Flags

None — Plan 03 introduces no new network endpoints, auth paths, file access patterns, or trust-boundary crossings. The fingerprint column writes/reads on the existing devices table use the same parameterization convention as every other column on the same table.

## Known Stubs

None — every code path lands real data. The `fingerprint` column reads as `None` only when the device's last discovery succeeded against a host where ALL four Plan 01 probes failed (uname-s + uname-r + os-release + dpkg) — which already trips Phase 35 `partial: True` semantics. That is the intended Phase 35 D-09a partial-payload behavior, not a stub.

## Notes for Plan 04

- **`update_device_fingerprint` adapter method (D-11) is unblocked.** Plan 03 has wired the read+write path. Plan 04's adapter method (or handler-side merge if it picks D-11 Option B) will:
  1. Read existing fingerprint via `get_all_devices` (Plan 03 returns dict for SQLite, dict via flatten for Postgres).
  2. Deep-merge per Phase 38 D-05 (top-level overwrite, capabilities deep-merge).
  3. Write back via `store_device` with a JSON-string fingerprint (SQLite path) OR an already-decoded dict (Postgres path — `_maybe_json_load` accepts both).
  4. Plan 03 verified `_maybe_json_load` handles dict pass-through for the Postgres write path.
- **Postgres adapter must NOT use `jsonb_set` / `||` for the merge.** RESEARCH.md Pitfall 4 explicitly warns against in-SQL merge for path-parity with SQLite. Plan 04's adapter method should: (a) SELECT system_info, (b) merge in Python, (c) UPDATE devices SET system_info = %s. Plan 03's `_maybe_json_load`-based write path provides the substrate for this.
- **AST guard at `tests/test_ast_regression.py:392`** (hostname-natural-key SELECT FROM devices) was NOT triggered by Plan 03: this plan adds UPDATE/INSERT logic but no new SELECT-by-hostname queries. Plan 04 WILL need a new SELECT-by-hostname query for `update_device_fingerprint` and must use the Phase 35 D-01 hostname-alone + degenerate-fallback pattern (mirror `database.py:200-211`).

## User Setup Required

None — no external service configuration required. SQLite migration is automatic on next `NetworkSiteMap` instantiation (already shipped in Plan 02).

## Next Phase Readiness

- **Plan 04 (update_device_fingerprint adapter method + MCP tool) unblocked.** Plan 03 has wired the read+write substrate; Plan 04 layers the deep-merge logic on top.
- **Plan 05 (configure_host_fingerprint MCP prompt) unblocked.** The prompt body references `update_device_fingerprint` (Plan 04) which references the adapter method (Plan 03); both ready.
- **Phase 39 (changed bucket detection — DRFT-19) unblocked on the read-side parity.** Both adapters return `device['fingerprint']` as a top-level dict; Phase 39 can diff stored vs current with no adapter-specific branching.

## Self-Check

- [x] `src/homelab_mcp/database.py` UPDATE SET clause has `fingerprint = ?` at line 226 — VERIFIED (grep)
- [x] `src/homelab_mcp/database.py` has 3 occurrences of `device_data.get("fingerprint")` (UPDATE param, INSERT VALUES, Postgres system_info) — VERIFIED (grep -c returned 3)
- [x] `src/homelab_mcp/database.py` SQLite get_all_devices has `device_dict["fingerprint"] = json.loads(...)` at line 337 — VERIFIED (grep)
- [x] `src/homelab_mcp/database.py` Postgres system_info dict has `"fingerprint": _maybe_json_load(...)` at line 598 — VERIFIED (grep)
- [x] `src/homelab_mcp/database.py` Postgres get_all_devices flatten has `"fingerprint": system_info.get(...)` at line 726 — VERIFIED (grep)
- [x] `tests/test_database.py` contains all 5 fingerprint_phase38 tests — VERIFIED (pytest --collect-only -k fingerprint_phase38 reports 5 tests)
- [x] Commit `df964b6` (test RED gate) exists — VERIFIED
- [x] Commit `89c2f66` (feat GREEN gate) exists — VERIFIED
- [x] All 5 fingerprint_phase38 tests pass when psycopg2 available; the 3 Postgres ones skip cleanly otherwise — VERIFIED (2 passed, 3 skipped on local Windows tree)
- [x] Full unit test suite green (738 passed) — VERIFIED
- [x] AST regression guards (11/11) green — VERIFIED
- [x] mypy on src/homelab_mcp/database.py clean — VERIFIED
- [x] ruff check on src/ tests/ clean — VERIFIED
- [x] ./scripts/quality-check.sh exits 0 — VERIFIED
- [x] Only `src/homelab_mcp/database.py` modified in Task 2 commit (no out-of-scope reformat noise leaked in) — VERIFIED

## Self-Check: PASSED

---
*Phase: 38-sitemap-fingerprint-schema*
*Completed: 2026-04-26*
