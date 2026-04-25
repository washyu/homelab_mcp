---
phase: 35-sitemap-discovery-reliability-fix-discover-and-map-field-los
verified: 2026-04-24T23:30:54Z
status: passed
score: 32/32 must-haves verified
overrides_applied: 0
---

# Phase 35 Verification

**All 32 observable truths across 4 plans verified against the post-execution codebase. The four ROADMAP §Phase 35 bugs plus the stale-constraint addendum and the B1 pre-existing defect are all mitigated. Phase goal achieved.**

## Phase Goal

Close the four reliability gaps in `discover_and_map` / `bulk_discover_and_map` / `analyze_network_topology`:

1. Align `ssh_discover_system` producer field names to sitemap consumer contract (cpu/memory/disk/usb/pci/block).
2. Flip `store_device` to hostname-only upsert (no zombie rows on IP change).
3. Wrap every per-subprocess SSH probe with a 10s timeout and parallelize bulk discovery at Semaphore(10).
4. Defensive null-skip in analyzers.

## Goal Achievement

### Observable Truths — Plan 01 (ssh_tools.py)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Every `conn.run(...)` inside `ssh_discover_system` is bounded by a per-cmd timeout | VERIFIED | `_run_with_timeout` defined at `ssh_tools.py:493`; 12 references (1 def + 11 call sites); zero bare `conn.run` in the function body scope |
| 2 | `partial: true` + `timed_out_commands` only appear when a timeout fires | VERIFIED | Conditional injection at line 488 (`payload["partial"] = True`); accumulator `timed_out_commands: list[str] = []` at line 261 |
| 3 | `data.cpu` uses key `cores` (not `count`) | VERIFIED | `cpu_info["cores"]` at line 277; zero `cpu_info["count"]` matches |
| 4 | `data.memory` emits `total/used/free/available` Gi-suffixed strings | VERIFIED | 7 `Gi"` matches in file (4 memory + 3 disk f-strings) |
| 5 | `data.disk` emits `filesystem/size/used/available/use_percent/mount` | VERIFIED | `df -B1 -T /` command at line 318; field names align with `sitemap.py:88-94` consumer contract |
| 6 | `@ssh_connection_wrapper(timeout_seconds=120.0)` on `ssh_discover_system` | VERIFIED | Line 227 — exact decorator |
| 7 | Back-compat: clean run produces no `partial`/`timed_out_commands` keys | VERIFIED | Conditional-key injection; D-06 back-compat test `test_ssh_discover_system_omits_partial_keys_on_clean_run_phase35` PASSES |
| 8 | B1 dedent: hostname probe timeout does NOT suppress subsequent probes | VERIFIED | `cpu_info: dict[str, Any] = {}` at line 272 (8-space function-body indent, inside `async with`); `if hostname_result and ...:` block contains ONLY the `actual_hostname = cast(...)` override; W4 functional test `test_ssh_discover_system_hostname_timeout_does_not_suppress_probes_phase35` PASSES |

### Observable Truths — Plan 02 (sitemap.py)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 9 | NetworkDevice carries `usb_devices`/`pci_devices`/`block_devices` JSON-string fields | VERIFIED | `sitemap.py:55-57` — exact `str | None = None` declarations |
| 10 | `parse_discovery_output` writes the three new JSON-string fields | VERIFIED | 3 `device.(usb|pci|block)_devices = json.dumps` matches |
| 11 | `bulk_discover_and_store` runs parallel under `Semaphore(10)` | VERIFIED | `sitemap.py:405` `semaphore = asyncio.Semaphore(10)`; line 412 `async with semaphore:`; line 409 `async def _discover_one(target):` |
| 12 | Analyzers skip null `cpu_cores`/`memory_total` | VERIFIED | `_has_threshold_data` defined at line 17; 3 references (1 def + 2 call sites in `suggest_deployments`) |
| 13 | No `cpu_cores or 0` / `memory_total or ""` coercion remains | VERIFIED | Both forbidden-pattern grep counts return 0 |
| 14 | `asyncio.gather(..., return_exceptions=True)` per CONTEXT D-07 | VERIFIED | `sitemap.py:452` |

### Observable Truths — Plan 03 (database.py + migration.py)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 15 | `SQLiteAdapter.store_device` matches on hostname alone | VERIFIED | `database.py:235` primary SELECT `SELECT id FROM devices WHERE hostname = ?`; line 230 degenerate-hostname fallback |
| 16 | `PostgreSQLAdapter.store_device` matches on hostname alone | VERIFIED | `database.py:672` primary SELECT `SELECT id FROM devices WHERE hostname = %s`; line 667 degenerate fallback |
| 17 | Same hostname + new IP → updates row in place (no zombie) | VERIFIED | `test_store_device_updates_in_place_on_ip_change_phase35` PASSES (id1 == id2, connection_ip overwritten) |
| 18 | SQLite has `usb_devices/pci_devices/block_devices TEXT` columns | VERIFIED | `database.py:157-159` |
| 19 | Postgres `system_info` JSONB carries new keys + flatten on read | VERIFIED | `database.py:645-647` `_maybe_json_load(device_data.get("X_devices"))` for all 3; flatten at `get_all_devices` adds top-level `usb_devices`/`pci_devices`/`block_devices` |
| 20 | SQLite `get_all_devices` JSON-decodes new columns with `[]` fallback | VERIFIED | `database.py:348-354` — explicit decode loop |
| 21 | `UNIQUE(hostname, connection_ip)` constraint dropped from both adapters | VERIFIED | Zero constraint matches in `database.py` init_schema bodies |
| 22 | `idx_devices_hostname` non-unique replacement index in both adapters | VERIFIED | `database.py:185` (SQLite), `database.py:582` (Postgres) |
| 23 | Migration step is idempotent | VERIFIED | `dedupe_zombie_device_rows` (2 matches), `drop_stale_hostname_ip_unique` (2 matches) in `migration.py`; D-17b functional test PASSES (first run applies, second run is no-op) |
| 24 | Degenerate-hostname rows excluded from dedup | VERIFIED | 2 matches for `hostname NOT IN ('', 'unknown')` in `migration.py` |
| 25 | Dedup merges non-null sibling values | VERIFIED | D-17b test asserts `cpu_cores=4` preserved from sibling row with non-null-wins merge |

### Observable Truths — Plan 04 (regression tests)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 26 | AST D-14 fails on composite-primary match | VERIFIED | `test_store_device_matches_on_hostname_alone_phase35` PASSES |
| 27 | AST D-15 fails on bare `conn.run` inside `ssh_discover_system` | VERIFIED | `test_ssh_discover_system_wraps_every_conn_run_phase35` PASSES |
| 28 | AST D-16 fails on threshold coercion in analyzer bodies | VERIFIED | `test_no_threshold_coercion_in_analyzer_bodies_phase35` PASSES |
| 29 | Functional D-17a hostname-only upsert | VERIFIED | `test_store_device_updates_in_place_on_ip_change_phase35` + `test_store_device_preserves_degenerate_hostnames_phase35` PASS |
| 30 | Functional D-17b migration dedup idempotency | VERIFIED | `test_migration_dedup_collapses_duplicates_and_is_idempotent_phase35` PASSES |
| 31 | Functional D-17c partial-mode + W4 B1 dedent guard | VERIFIED | 3 tests in `test_ssh_tools.py` PASS (partial-mode, D-06 back-compat, W4 dedent) |
| 32 | Functional D-17d parallelism + D-17e analyzer null-skip | VERIFIED | `test_bulk_discover_and_store_runs_in_parallel_phase35` (CONTEXT D-17d cited; `elapsed < 4.0` bound) + `test_analyzers_skip_null_cpu_cores_device_phase35` PASS |

**Score:** 32/32 observable truths verified.

## Behavioral Spot-Checks

| Behavior | Result | Status |
|----------|--------|--------|
| Phase 35 marker tests (11 tests across 4 files) | 11 passed, 64 deselected in 3.32s | PASS |
| Full unit suite | 720 passed, 1 failed, 9 skipped, 15 deselected | PASS (single failure = pre-existing baseline, not Phase 35) |
| `ruff check` on 4 modified source files | All checks passed! | PASS |
| `mypy` on 4 modified source files | Success: no issues found | PASS |
| NetworkDevice dataclass import round-trip | OK (usb_devices/pci_devices/block_devices attrs present) | PASS |
| `_has_threshold_data` semantics | OK (None/""/0/valid cases all correct) | PASS |

## Requirements Coverage

Phase 35 has no REQ-IDs (surfaced by Phase 33 live testing, not v1.6 requirements). Coverage mapped to ROADMAP §Phase 35 bug list:

| Bug | Status | Evidence |
|-----|--------|----------|
| #1 Field-loss (cpu/memory/disk/usb/pci/block missing from sitemap row) | SATISFIED | D-09a/b/c producer/reader/storage chain + D-17a functional + D-14/D-16 AST |
| #2 Zombie sitemap rows on IP change | SATISFIED | D-01/D-01a upsert + D-02 dedup migration + D-17a/D-17b functional + D-14 AST |
| #3 Tool hangs 4+ minutes | SATISFIED | D-05 per-cmd timeout + D-06 partial-mode + D-07/D-07a parallelism + D-08 wrapper bump + D-17c/D-17d functional + D-15 AST + W4 B1 dedent |
| #4 Analyzer null-threshold false-positives | SATISFIED | D-10/D-11/D-12/D-13 null-defense via `_has_threshold_data` + D-17e functional + D-16 AST |
| Stale-constraint addendum | SATISFIED | UNIQUE dropped from both adapters in `init_schema`; `idx_devices_hostname` non-unique replacement in both adapters |
| B1 pre-existing defect (hostname probe timeout suppressed subsequent probes) | SATISFIED | Plan 01 dedent applied; W4 functional test `test_ssh_discover_system_hostname_timeout_does_not_suppress_probes_phase35` proves it |

## Anti-Patterns Found

None. All targeted anti-pattern greps return 0 matches:

- Bare `await conn.run` in `ssh_discover_system` body: **0**
- `cpu_info["count"]`: **0**
- `device.get("cpu_cores") or 0`: **0**
- `device.get("memory_total") or ""`: **0**
- Serial `for i, target in enumerate(targets):` in `bulk_discover_and_store`: **0**
- `UNIQUE(hostname, connection_ip)` in `database.py` init_schema bodies: **0**

## Human Verification Required

None. All work is structurally verifiable (AST + grep + functional pytest). No UI / visual / external-service surface was introduced — Phase 33 already exercised the live discovery path that surfaced these bugs; Plans 01-03 are deterministic source-code fixes; Plan 04 supplies regression coverage.

## Gaps Summary

No gaps found. All 32 observable truths verified, all artifacts present and substantive, all key-links wired, all data flows real, all behavioral spot-checks pass.

The single non-Phase-35 test failure (`test_ssh_credentials_table_dropped_postgres`, psycopg2 monkeypatch import issue) is a documented Phase 34 pre-existing baseline (STATE.md Phase 34 Plan 01 decisions) — explicitly out of Phase 35 scope.

---

**Verifier:** gsd-verifier subagent (2026-04-24)
**Written to disk by:** orchestrator (subagent Write was sandbox-blocked)
**Phase closeout ready:** ROADMAP checkbox + STATE.md phase-complete update to follow in the `update_roadmap` step.
