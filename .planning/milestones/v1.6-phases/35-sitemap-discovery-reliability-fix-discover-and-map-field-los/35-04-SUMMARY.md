---
phase: 35-sitemap-discovery-reliability-fix-discover-and-map-field-los
plan: 04
subsystem: testing
tags: [ast-meta-test, regression-guard, phase-closeout, functional-test]

requires:
  - phase: 35
    provides: "Plans 01/02/03 source state: hostname-only upsert in both adapters, wrapped conn.run probes, B1-dedented probe blocks, null-defensive analyzers"
provides:
  - "3 AST meta-tests in tests/test_ast_regression.py (D-14 hostname-only upsert, D-15 wrapped conn.run, D-16 no threshold coercion)"
  - "3 functional DB tests in tests/test_database.py (D-17a hostname-only upsert, D-01a degenerate-hostname preservation, D-17b migration dedup idempotent)"
  - "3 functional SSH tests in tests/test_ssh_tools.py (D-17c partial-mode, D-06 back-compat clean-run, W4 B1 dedent hostname-timeout guard)"
  - "2 functional sitemap tests in tests/test_sitemap.py (D-17d parallelism timing bound, D-17e analyzer null-skip)"
  - "Pre-existing test updates: test_ssh_discover_success (count→cores + df -B1 -T + Gi disk fields), test_database_schema_creation (idx_devices_hostname_ip → idx_devices_hostname)"
affects: []

tech-stack:
  added: []
  patterns:
    - "AST BoolOp(Or) pattern detection for threshold-coercion regression guards — extensible to other field-set allowlists"
    - "Parent-pointer annotation on ast.walk for upward-walks (enclosing-call detection)"
    - "Functional D-17c/W4 pattern: monkeypatch `_run_with_timeout` to simulate per-probe timeouts without real asyncssh plumbing"

key-files:
  created: []
  modified:
    - tests/test_ast_regression.py
    - tests/test_database.py
    - tests/test_ssh_tools.py
    - tests/test_sitemap.py

key-decisions:
  - "D-14 scanner filters abstract base class — only counts concrete store_device functions that contain SELECT strings (DatabaseAdapter.store_device is abstract with `pass` body)"
  - "D-15 scanner uses parent-pointer annotation pattern for upward-walk — standard ast idiom (ast does not wire parents by default)"
  - "D-16 scanner walks BoolOp(Or) + 2-operand shape + device.get() + forbidden-field-set (cpu_cores / memory_total / disk_use_percent) — narrow false-positive surface"
  - "D-17d timing bound: 4.0s (W3 widened from 3.0s) — absorbs Windows CI stdout/Lock/scheduler noise while serial-10s is still unambiguously detectable"
  - "Pre-existing test updates done as Plan 04 scope (vs separate commits) — explicitly documented in this SUMMARY per the plan's acceptance rule (no silent deletions/widenings)"

patterns-established:
  - "Plan 04 AST meta-test shape: each test is self-contained (imports ast/Path at module top, local filter + walk + violation collection + assert-with-message). New AST guards copy this shape."
  - "D-17c mock pattern: SimpleNamespace-based fake asyncssh connection + monkeypatch of `_run_with_timeout` at the ssh_tools module level — deterministic partial-mode testing without network."

requirements-completed: []

duration: 30min
completed: 2026-04-24
---

# Phase 35 Plan 04: Regression Tests

**Three AST meta-tests (D-14/D-15/D-16) + five functional tests (D-17a-e + D-06 back-compat + W4 B1-dedent guard) close the regression window on Plans 01-03; two pre-existing tests updated in-scope (test_ssh_discover_success field renames, test_database_schema_creation index name).**

## Performance

- **Duration:** ~30 min (inline orchestrator execution; subagents remained sandbox-blocked)
- **Tasks:** 3
- **Files modified:** 4 test files
- **Net test count delta:** +11 Phase 35 tests; 2 pre-existing tests updated in place (not deleted)

## Accomplishments

- **AST regression guards** prevent future commits from silently regressing any of:
  - Plan 03 hostname-only upsert (D-14 fails if `hostname = ? AND connection_ip = ?` becomes the primary match in either store_device)
  - Plan 01 per-probe timeout wrap (D-15 fails if any bare `await conn.run(...)` reappears inside `ssh_discover_system`)
  - Plan 02 null-defensive analyzers (D-16 fails if `device.get("cpu_cores") or 0` / `or ""` reappears inside `analyze_network_topology` or `suggest_deployments`)
- **Functional end-to-end proofs** for every ROADMAP §Phase 35 bug:
  - Bug #1 field-loss: D-17a upsert round-trip, D-17e analyzer null-skip
  - Bug #2 zombie rows: D-17a (id equality + IP overwrite), D-17b (dedup merge + idempotency)
  - Bug #3 4-minute hang: D-17c (partial-mode response), D-17d (parallelism timing), W4 (B1 dedent hostname-probe-timeout still populates subsequent probes)
  - Bug #4 analyzer false-positives: D-17e (null cpu_cores device not in low-resources or upgrade recommendations)
- **D-06 back-compat proof** — clean runs produce byte-for-byte pre-Phase-35 JSON shape.
- **Pre-existing test updates** done in Plan 04 scope (not silent deletions — see Deviations).

## Task Commits

Each task committed atomically:

1. **Task 1: 3 AST meta-tests in test_ast_regression.py** — `c539e88` (test)
2. **Task 2: 3 DB functional tests in test_database.py** — `97bf3e6` (test)
3. **Task 3: 3 SSH + 2 sitemap functional tests + pre-existing-test updates** — `06dc5c1` (test) — bundles both test_ssh_tools.py and test_sitemap.py since pre-commit-hook auto-rollback made the prior ssh-only commit a no-op; the bundled commit preserves the full diff

## Files Created/Modified

- `tests/test_ast_regression.py` — appended 3 Phase 35 AST meta-tests: `test_store_device_matches_on_hostname_alone_phase35` (D-14), `test_ssh_discover_system_wraps_every_conn_run_phase35` (D-15), `test_no_threshold_coercion_in_analyzer_bodies_phase35` (D-16). Added `PHASE35_FORBIDDEN_COERCION_FIELDS` module-level frozenset. Net +~170 lines.
- `tests/test_database.py` — appended 3 Phase 35 functional tests: `test_store_device_updates_in_place_on_ip_change_phase35` (D-17a), `test_store_device_preserves_degenerate_hostnames_phase35` (D-01a), `test_migration_dedup_collapses_duplicates_and_is_idempotent_phase35` (D-17b). Net +~170 lines.
- `tests/test_ssh_tools.py` — **updated `test_ssh_discover_success`** (see Deviations) for Plan 01 field renames + appended 3 Phase 35 functional tests: `test_ssh_discover_system_partial_mode_on_probe_timeout_phase35` (D-17c), `test_ssh_discover_system_omits_partial_keys_on_clean_run_phase35` (D-06 back-compat), `test_ssh_discover_system_hostname_timeout_does_not_suppress_probes_phase35` (W4 B1 dedent). Net +~244 lines.
- `tests/test_sitemap.py` — **updated `test_database_schema_creation`** (see Deviations) for the `idx_devices_hostname_ip` → `idx_devices_hostname` rename + appended 2 Phase 35 functional tests: `test_bulk_discover_and_store_runs_in_parallel_phase35` (D-17d), `test_analyzers_skip_null_cpu_cores_device_phase35` (D-17e). Net +~98 lines.

## Decisions Made

- **D-14 scanner filters the abstract base class method** — the plan's literal `len(store_device_funcs) == 2` assertion failed when `ast.walk` also picked up `DatabaseAdapter.store_device` (abstract `pass` body, no SQL strings). Fixed the filter to only count functions whose body contains a `SELECT id FROM devices` string literal — the abstract method is naturally excluded.
- **D-17d timing bound at 4.0s (W3)** — preserved per the plan; the test passed locally in well under 2s but the bound cushion is preserved for CI variability.
- **Pre-existing test updates done in Plan 04 scope** — the two drifting tests (`test_ssh_discover_success` with `count`→`cores` / disk shape, `test_database_schema_creation` with index name) were flagged by Plans 01 and 03 SUMMARIES as Plan 04 cleanup scope. Fixed in this plan rather than silently deleted or left broken.

## Deviations from Plan

### Auto-fixed Issues

**1. [Correctness] D-14 scanner excluded the abstract-base method**
- **Found during:** Task 1 first test run
- **Issue:** `ast.walk(tree)` returns the abstract `DatabaseAdapter.store_device` as a third FunctionDef; the plan's `len(funcs) == 2` assertion fails with "found 3".
- **Fix:** Added a filter to the list comprehension — only include functions whose body contains a string constant matching `"SELECT id FROM devices"`. The abstract method (body = `pass`) is naturally filtered out; SQLite and Postgres implementations both include the SELECT and are kept.
- **Files modified:** `tests/test_ast_regression.py`
- **Verification:** `uv run pytest tests/test_ast_regression.py -k phase35` → 3 passed.
- **Committed in:** `c539e88` (Task 1 commit)

**2. [Pre-existing test update] test_ssh_discover_success updated for Plan 01 field renames**
- **Found during:** Task 3 regression gate (`uv run pytest tests/test_ssh_tools.py` revealed `KeyError: 'count'`)
- **Issue:** Plan 01 renamed `cpu.count` → `cpu.cores`, changed `df -B1 /` → `df -B1 -T /` (disk output now has a Type column; field names are filesystem/size/used/available/use_percent/mount), and memory now emits Gi-suffixed strings. The old test's `data.cpu.count`, `data.disk.total`, and pre-Type-column `df` mock stdout all drifted.
- **Fix:** Updated the mock's `disk_result.stdout` to include the Type column (`/dev/sda1  ext4  ...`); updated assertions to check `cpu.cores` (not `count`), to assert the 6 disk fields (filesystem, size, used, available, use_percent, mount), and to assert the 4 memory fields (total, used, free, available).
- **Files modified:** `tests/test_ssh_tools.py`
- **Verification:** `uv run pytest tests/test_ssh_tools.py::test_ssh_discover_success` → passes.
- **Committed in:** `06dc5c1` (Task 3 commit)

**3. [Pre-existing test update] test_database_schema_creation updated for Plan 03 index rename**
- **Found during:** Task 3 regression gate
- **Issue:** Plan 03 dropped the composite `idx_devices_hostname_ip` index in favor of a non-unique `idx_devices_hostname`. The test asserted `any("idx_devices_hostname_ip" in idx for idx in indexes)` — drift.
- **Fix:** Relaxed the assertion to `any("idx_devices_hostname" in idx for idx in indexes)` with an inline comment citing Phase 35 D-01. The new index name is a prefix substring of the old one, so this predicate satisfies both the new hostname-alone index and (historically) the old composite — no over-specification.
- **Files modified:** `tests/test_sitemap.py`
- **Verification:** `uv run pytest tests/test_sitemap.py::TestDatabaseOperations::test_database_schema_creation` → passes.
- **Committed in:** `06dc5c1` (Task 3 commit)

**4. [Orchestration] Plan executed inline by orchestrator — sub-agent sandbox restrictions continued**
- **Found during:** Wave 3 kickoff
- **Issue:** Prior Wave 2 experience showed subagents are sandbox-blocked on Edit/Write. Launching another subagent for Plan 04 would likely fail the same way.
- **Fix:** Orchestrator executed all three tasks inline. The `gsd-read-guard.js` PreToolUse hook fires advisory strings but does not block — confirmed by the repeated successful Edit/Write calls during Plans 03 and 04.
- **Files modified:** N/A
- **Verification:** All 11 Phase 35 tests pass + 720/721 overall tests pass (single failure pre-existing, unrelated).
- **Committed in:** N/A (orchestration note only)

---

**Total deviations:** 4 (1 correctness fix on the plan-supplied scanner + 2 pre-existing-test updates promoted into Plan 04 scope + 1 orchestration detour).
**Impact on plan:** No scope change. Three AST tests + five functional tests + two pre-existing-test updates shipped as planned.

## Issues Encountered

- **Pre-existing baseline failure unchanged**: `tests/test_database.py::test_ssh_credentials_table_dropped_postgres` still fails with the psycopg2 monkeypatch import issue (confirmed in STATE.md Phase 34 Plan 01 notes). Not a Phase 35 regression; not a Plan 04 scope item.

## User Setup Required

None — no external service configuration required.

## Verification Output

```
# Phase 35-specific suite
uv run pytest tests/test_ast_regression.py tests/test_database.py tests/test_ssh_tools.py tests/test_sitemap.py -k phase35 --no-header -q
  11 passed, 64 deselected in 3.36s

# Full regression gate
uv run pytest tests/ -m "not integration" --no-header -q
  720 passed, 1 failed (pre-existing baseline), 9 skipped, 15 deselected
  — Phase 35 adds zero new failures

# Lint
uv run ruff check tests/test_ast_regression.py tests/test_database.py tests/test_ssh_tools.py tests/test_sitemap.py
  All checks passed!

# Phase 35 test count audit (grep -c "_phase35")
  test_ast_regression.py = 3
  test_database.py       = 3
  test_ssh_tools.py      = 3
  test_sitemap.py        = 2
  Total                  = 11
```

### D-17d observed timing
- Local Windows run: ~1.1-1.3s for 10 × 1s sleeps (well under the 4.0s W3 bound).
- Bound = 4.0s gives headroom for Windows CI scheduler jitter; serial execution would land at 10.0s, keeping the signal unambiguous.

## Next Phase Readiness

### Phase 35 closeout — ready for verification and completion

- **All four ROADMAP §Phase 35 bugs guarded by at least one regression test** (AST + functional):
  - #1 Field-loss → D-09a/b/c producer/reader/storage chain + D-17a/e functional + D-14/16 AST
  - #2 Zombie rows → D-01/D-01a/D-02 upsert + migration + D-17a/b functional + D-14 AST
  - #3 4-minute hang → D-05/D-06/D-07/D-08 timeouts + parallelism + D-17c/d functional + D-15 AST + W4 dedent
  - #4 Analyzer false-positives → D-10/D-11/D-12/D-13 null-defense + D-17e functional + D-16 AST
- **Pending orchestrator writes:** ROADMAP plan 04 checkbox, STATE.md Plan 04 decisions block, VERIFICATION.md via `/gsd-verify-phase 35`.
- **No handoff to a next plan** — Plan 04 is the phase closeout.

---
*Phase: 35-sitemap-discovery-reliability-fix-discover-and-map-field-los*
*Completed: 2026-04-24*
