---
phase: 44-sitemap-crud-completion
plan: 01
subsystem: database
tags: [sitemap, crud, mcp-tool, sqlite, postgres, async, remove_device]

requires:
  - phase: 35-sitemap-discovery-reliability-fix
    provides: hostname-natural-key sitemap upsert that distinguishes id (surrogate PK) from hostname (natural key) — D-06 leverages this distinction.
  - phase: 38-sitemap-fingerprint-schema
    provides: adapter-method-pattern (DatabaseAdapter ABC + SQLite + Postgres) and *_preview thin-delegation convention reused for delete_device_by_id and remove_device_preview.
provides:
  - delete_device_by_id adapter method (ABC + SQLite + Postgres) with manual two-step cascade to discovery_history.
  - handle_remove_device + handle_remove_device_preview MCP handlers in network_handlers.py (NOT infrastructure_handlers.py per D-12).
  - remove_device + remove_device_preview registered in TOOL_HANDLERS (56-tool parity), TOOL_ANNOTATIONS, openapi_app STANDALONE_TOOLS + Network Discovery category, and network_tools_schema with the canonical D-09 contrast block.
  - 8 functional tests across 3 classes in tests/test_remove_device.py covering adapter round-trip, handler envelopes, and SC-2 credential-preservation invariant.
affects: [44-02-purge-devices, 44-03-decommission-wording-and-ast-guard, drift_detection-recovery-pointers]

tech-stack:
  added: []
  patterns:
    - Single-row DELETE adapter method returning dict|None (vs purge_failed_devices' list[dict] bulk shape) — drives structured-error envelope in handler.
    - patch(NSM_PATH) NetworkSiteMap injection idiom — module-level import in network_handlers.py allows clean fixture-DB swap-in for handler tests.

key-files:
  created:
    - tests/test_remove_device.py
  modified:
    - src/homelab_mcp/database.py
    - src/homelab_mcp/tool_handlers/network_handlers.py
    - src/homelab_mcp/tool_schemas/network_tools_schema.py
    - src/homelab_mcp/tool_handlers/__init__.py
    - src/homelab_mcp/tool_annotations.py
    - src/homelab_mcp/openapi_app.py
    - tests/test_tools.py

key-decisions:
  - "delete_device_by_id returns dict|None (single row), NOT list[dict] (bulk) — drives the handler's missing-id branch via None check rather than try/except (D-13)"
  - "Handlers placed in network_handlers.py per D-12 — keeps the handler module distinct from infrastructure_handlers.py where decommission_device's host-side semantics live (file-placement is half the AST-guard safety story)"
  - "SELECT * FROM devices instead of column subset — returns the full row payload for caller audit; Postgres uses RealDictCursor for the same shape"
  - "Test fixture binds ssh_credential_id via the dedicated set_device_credential_binding adapter method, not via store_device kwargs — store_device's INSERT does not write credential-binding columns (Phase 38.1 R3/R4/R8/R9)"

patterns-established:
  - "Single-row delete cascade pattern: SELECT row → branch on dry_run → DELETE FROM discovery_history WHERE device_id = ? → DELETE FROM devices WHERE id = ? → commit. Single transaction, no FK CASCADE on schema (D-06c)."
  - "NetworkSiteMap-injection test pattern: with patch(NSM_PATH) as MockSM: MockSM.return_value.db_adapter = fresh_adapter — clean DB swap for handler-level tests without touching the user's home directory ~/.mcp/sitemap.db."

requirements-completed:
  - SC-1
  - SC-2
  - SC-6

duration: 35min
completed: 2026-05-02
---

# Phase 44 Plan 01: remove_device Inventory-Only Delete Tool Summary

**`remove_device` shipped as a registered MCP tool — pure SQL DELETE on a sitemap row keyed by `device_id`, manual cascade to `discovery_history`, no SSH/Ansible/Terraform/keyring touch on the call path; closes half of the v1.7 detection→correction loop.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-05-03T00:26:01Z (worktree base)
- **Completed:** 2026-05-03T00:42:00Z
- **Tasks:** 3 / 3 completed
- **Files modified:** 7 files (1 created, 6 modified)

## Accomplishments

- New `DatabaseAdapter.delete_device_by_id` ABC method with SQLite + Postgres implementations using parametrized single-row DELETE (`WHERE id = ?` / `= %s`) and manual two-step cascade to `discovery_history`. Returns the full row dict or `None` on missing-id (drives the handler's structured-error branch).
- New `handle_remove_device` and `handle_remove_device_preview` async handlers in `tool_handlers/network_handlers.py` per D-12. Schema, registry, annotations, and OpenAPI catalogue updated for 56-tool parity (was 54).
- 8 functional tests covering: adapter round-trip (3) — happy delete + dry_run + missing id; handler envelope shapes (4) — success, dry_run, exact-string missing-id error/hint, preview thin-delegate parity; credential preservation invariant (1) — `keyring.delete_password` and `keyring.set_password` asserted-not-called after `remove_device` runs (SC-2).
- Tool description carries the canonical D-09 three-tool contrast block verbatim — `remove_device` (one-row inventory) vs `purge_devices` (bulk filter inventory) vs `decommission_device` (host-side cleanup). Plan 03 will copy this exact sentence into the other two tool descriptions.

## Task Commits

Each task was committed atomically:

1. **Task 1: Adapter method `delete_device_by_id` (ABC + SQLite + Postgres)** — `9fb6c8c` (feat)
2. **Task 2: Handlers + schema + registry + annotations + openapi_app** — `85ddc12` (feat)
3. **Task 3: Functional + credential-preservation tests** — `40690be` (test)

## Files Created/Modified

- `src/homelab_mcp/database.py` — Added `delete_device_by_id` ABC + SQLite impl + Postgres impl. Single-row variant of `purge_failed_devices` two-step DELETE pattern. (+82 lines)
- `src/homelab_mcp/tool_handlers/network_handlers.py` — Appended `handle_remove_device` (D-06) and `handle_remove_device_preview` (D-11) async handlers. (+50 lines)
- `src/homelab_mcp/tool_schemas/network_tools_schema.py` — Added `remove_device` and `remove_device_preview` schema entries adjacent to `purge_failed_discoveries` with the canonical D-09 contrast block in the `remove_device` description. (+50 lines)
- `src/homelab_mcp/tool_handlers/__init__.py` — Imported and registered both new handlers in `TOOL_HANDLERS`. (+4 lines)
- `src/homelab_mcp/tool_annotations.py` — `remove_device_preview` added to `_READ_ONLY_TOOLS`; `remove_device` added to `_DESTRUCTIVE_TOOLS` (mirrors `decommission_device` / `purge_failed_discoveries`). (+2 lines)
- `src/homelab_mcp/openapi_app.py` — Both new tools added to `STANDALONE_TOOLS` (local-DB-only) and `TOOL_CATEGORIES["Network Discovery"]`. (+4 lines)
- `tests/test_tools.py` — Bumped `len(tools) == 54` assertion to `== 56` and added the two new tool-presence assertions per Rule 3 (in-scope blocking issue from new tool registration). (+4 lines)
- `tests/test_remove_device.py` — Created. 8 tests across 3 classes per D-15 — adapter, handler, credential-preservation. (190 lines)

## Decisions Made

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| `SELECT *` returning full row payload (vs column subset like `purge_failed_devices`) | Caller may want to audit the full row before/after delete; matches D-06a's "full row payload" requirement | Postgres uses `RealDictCursor` for shape parity; SQLite's `sqlite3.Row` already returns the full row dict |
| Test fixture uses `set_device_credential_binding` adapter call instead of passing `ssh_credential_id` to `store_device` | `store_device`'s INSERT statement does not include the credential-binding columns (`ssh_credential_id` / `proxmox_credential_id`) — passing the kwarg silently drops it | Fixture mirrors production code path; assertion that the row carries the credential ID after delete now passes |
| `patch(NSM_PATH)` for handler tests instead of fixturing the user's `~/.mcp/sitemap.db` | Handler instantiates `NetworkSiteMap()` internally which would read the user's home dir DB; mocking the constructor and injecting our `fresh_adapter` keeps tests hermetic | Phase 38 used the same idiom for fingerprint-handler tests |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] tests/test_tools.py expected 54 tools, found 56 after registration**
- **Found during:** Task 2 verification (full unit-suite run after registration)
- **Issue:** `test_get_available_tools` asserts `len(tools) == 54` but adding `remove_device` + `remove_device_preview` brings total to 56.
- **Fix:** Updated assertion to 56 and appended `assert "remove_device" in tools` + `assert "remove_device_preview" in tools` plus comment update naming Phase 44 Plan 01 as the source of the increment. Pattern follows Phase 38 / Phase 33.1 conventions for tool-count maintenance.
- **Files modified:** `tests/test_tools.py`
- **Verification:** `uv run pytest tests/test_tools.py::test_get_available_tools` exits 0; full unit suite went from 936 → 944 passing (+8 new + 0 regressions).
- **Committed in:** `85ddc12` (Task 2 commit, since the test breakage was caused by the tool registration in that task).

**2. [Rule 1 - Bug] Test fixture passed `ssh_credential_id` to `store_device` but the binding wasn't persisted**
- **Found during:** Task 3 first test run.
- **Issue:** First adapter test failed with `AssertionError: assert None == 'test-cred-uuid-44'` because `store_device`'s INSERT does not include the credential-binding columns.
- **Fix:** Added explicit `set_device_credential_binding(device_id, "ssh", "test-cred-uuid-44")` call in the `seeded_device` fixture, mirroring the production code path (Phase 38.1 R3/R4/R8/R9 added the dedicated binding method). Removed the misleading `ssh_credential_id` kwarg from the `store_device` call.
- **Files modified:** `tests/test_remove_device.py`
- **Verification:** All 8 tests pass after the fix.
- **Committed in:** `40690be` (Task 3 commit, fixed before commit so fixture is correct from first commit).

**3. [Rule 1 - Bug] mypy `[no-any-return]` on `seeded_device` fixture return**
- **Found during:** Task 3 mypy run after first test pass.
- **Issue:** `store_device` returns `Any` (lacks py.typed marker), causing `return device_id` to fail strict `[no-any-return]` mypy check.
- **Fix:** Cast to `int(device_id)` explicitly. The remaining `[import-untyped]` errors are pre-existing baseline (matches every other test file that imports `homelab_mcp.*`).
- **Files modified:** `tests/test_remove_device.py`
- **Verification:** mypy now reports only the 2 baseline `[import-untyped]` errors that match `tests/test_drift_detection.py` baseline.
- **Committed in:** `40690be` (Task 3 commit).

## Auth Gates

None — pure DB-only feature.

## Verification

| Check | Status | Evidence |
|-------|--------|----------|
| `uv run ruff check` on modified files | PASS | All 7 touched source/test files clean. Pre-existing 7 ruff errors in `test_credential_store.py` / `test_credentials_cli.py` / `test_database.py` — out of scope (different files). |
| `uv run mypy` on modified src files | PASS | `database.py`, `network_handlers.py`, `__init__.py` — clean. The pre-existing `openapi_app.py:18 [import-untyped] jsonschema` baseline is unrelated. |
| `uv run pytest tests/test_remove_device.py -v` | PASS | 8/8 tests pass. |
| `uv run pytest tests/ -m "not integration"` | PASS | 944 passed (+8 from baseline 936), 15 skipped, 0 new regressions. |
| `TOOL_HANDLERS` round-trip via Python import | PASS | Both new tools present; tool/handler/annotation parity 56/56/56. |
| Schema description contains canonical D-09 contrast block | PASS | `grep -c "Use \`remove_device\` for inventory-only deletion of one row"` returns 1. |

## Pointer to Plan 03

The `TestPhase44RemoveDeviceCallPath` AST guard (D-10) lands in **Plan 03** (decommission-wording-and-ast-guard), per the phase decomposition. Plan 01 ships the runtime contract; Plan 03 enforces it at parse time. The handler body in `network_handlers.py` and the adapter method body in `database.py` are both kept symbol-clean (no `ssh_connect`, `asyncssh`, `subprocess.*`, `keyring.delete_password`, `decommission_network_device`, etc.) so the AST guard will lock cleanly when Plan 03 lands.

## Tooling Notes

The Edit and Write tools showed cache desync on this Windows worktree session — first edits to `src/homelab_mcp/database.py` reported success but did not write to disk. The diagnosis: when paths used forward slashes (`C:/Users/...`) the writes silently dropped; switching to Windows backslash paths (`C:\Users\...`) resolved Write-tool persistence. All Task 1 + Task 2 edits were ultimately applied via Python scripts run through `Bash` to bypass the cache layer. The on-disk content was repeatedly verified via `Bash`/`grep -c` after each edit. No content was lost; final commits reflect the actual on-disk state.

## Self-Check: PASSED

All claimed files exist on disk:
- src/homelab_mcp/database.py
- src/homelab_mcp/tool_handlers/network_handlers.py
- src/homelab_mcp/tool_schemas/network_tools_schema.py
- src/homelab_mcp/tool_handlers/__init__.py
- src/homelab_mcp/tool_annotations.py
- src/homelab_mcp/openapi_app.py
- tests/test_tools.py
- tests/test_remove_device.py

All claimed commits present in git log:
- 9fb6c8c (Task 1: adapter)
- 85ddc12 (Task 2: handlers + registry)
- 40690be (Task 3: tests)
