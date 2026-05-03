---
phase: 44-sitemap-crud-completion
plan: 02
subsystem: database
tags: [sitemap, crud, mcp-tool, sqlite, postgres, async, ipaddress, alias, purge_devices]

requires:
  - phase: 44-sitemap-crud-completion
    plan: 01
    provides: handle_remove_device + handle_remove_device_preview already in network_handlers.py; this plan appends handle_purge_devices + preview after them and shares the schema-table position adjacent to purge_failed_discoveries.
  - phase: 38-sitemap-fingerprint-schema
    provides: adapter-method-pattern (DatabaseAdapter ABC + SQLite + Postgres) and *_preview thin-delegation convention reused for handle_purge_devices_preview.
  - phase: 35-sitemap-discovery-reliability-fix
    provides: hostname-only sitemap upsert; Phase 44 D-08 alias preserves the 4-clause OR (status='error' OR hostname IN (NULL,'','unknown')) so the zombie-hostname recovery path that Phase 35 introduced still works post-refactor.
provides:
  - _build_filter_clause + _row_in_cidr + _FAILED_DISCOVERY_WHERE pure helpers (Task 1a) — zero adapter coupling, dialect-parametrized SQL fragment generation; importable + unit-testable in isolation.
  - _purge_devices_by_filter orchestrator (Task 1b) with explicit dialect: Literal["sqlite", "postgres"] parameter — zero isinstance branching on adapter class.
  - SQLiteAdapter.purge_failed_devices + PostgreSQLAdapter.purge_failed_devices refactored to one-line delegates (Task 1b, D-07) preserving public signature/return shape/behavior.
  - handle_purge_devices + handle_purge_devices_preview MCP handlers in network_handlers.py (D-12) plus _adapter_dialect + _value_hint_for + _VALID_FILTER_TYPES handler-private helpers.
  - purge_devices + purge_devices_preview registered in TOOL_HANDLERS (58-tool parity), TOOL_ANNOTATIONS, openapi_app STANDALONE_TOOLS + Network Discovery category, and network_tools_schema with the canonical D-09 contrast block.
  - purge_failed_discoveries description updated with D-07 parenthetical + D-09 contrast block (Issue 6 four-tool extension).
  - 31 functional tests in tests/test_purge_devices.py (5 classes covering _row_in_cidr unit, per-filter behavior, dry_run, zero-match, _build_filter_clause validation, handler-level envelopes).
  - 4 alias parity tests in tests/test_purge_failed_discoveries_alias.py locking byte-identical row sets + delegation-shape mock assertion (Issue 11).
affects: [44-03-decommission-wording-and-ast-guard]

tech-stack:
  added: []
  patterns:
    - "Explicit-dialect SQL helper pattern: dialect: Literal['sqlite', 'postgres'] parameter on _build_filter_clause + _purge_devices_by_filter eliminates isinstance branching on adapter class. Caller (handler) computes the dialect string once via _adapter_dialect — the only Phase-44-introduced isinstance check, lives at handler boundary not orchestrator."
    - "Python-side CIDR membership scan via ipaddress.ip_network + ip_address: SQL CANNOT reliably do CIDR membership across mixed connection_ip formats (IPv4/IPv6/hostname-fallback). Orchestrator reads via adapter.get_all_devices() then applies _row_in_cidr per row — silent skip on empty/unparseable per D-03a."
    - "Delegation-shape mock-patch lock: patch('module._helper', wraps=_helper) records the actual invocation so a future inlining-the-SQL-back regression fails on the assert_called_once_with shape — even if the inlined SQL happened to produce byte-identical rows, the delegation lock catches the structural drift."

key-files:
  created:
    - tests/test_purge_devices.py
    - tests/test_purge_failed_discoveries_alias.py
  modified:
    - src/homelab_mcp/database.py
    - src/homelab_mcp/tool_handlers/network_handlers.py
    - src/homelab_mcp/tool_schemas/network_tools_schema.py
    - src/homelab_mcp/tool_handlers/__init__.py
    - src/homelab_mcp/tool_annotations.py
    - src/homelab_mcp/openapi_app.py
    - tests/test_tools.py

key-decisions:
  - "Explicit dialect string parameter on _purge_devices_by_filter eliminates the need for isinstance(adapter, ...) branching in the helper body. The single isinstance check (in _adapter_dialect) lives at the handler-side consumer boundary where the concrete adapter taxonomy is already known."
  - "_build_filter_clause raises ValueError on bad value shape and the handler wraps it into the structured-error envelope (with per-filter hint via _value_hint_for) — keeps validation errors out of the call stack and consistent with Phase 38's update_device_fingerprint envelope shape."
  - "ip_range path uses Python-side ipaddress filtering after adapter.get_all_devices(), NOT SQL string-match — SQL string-match on connection_ip is fragile across IPv4/IPv6/hostname-fallback formats; D-03a silent-skip for unparseable rows is implicit in the per-row try/except."
  - "purge_failed_discoveries description carries BOTH the D-07 parenthetical AND the D-09 contrast block (four-tool extension per Issue 6). The contrast block names only three tools (remove/purge/decommission) but the parenthetical above explicitly disambiguates the alias from the bare status filter."
  - "Test fixture uses datetime.now(UTC).isoformat() for last_seen — matches Phase 42 W2 canonical UTC convention. Bool rejection on last_seen_older_than_days needs the explicit isinstance(value, bool) guard because isinstance(True, int) is True in Python."
  - "Delegation-shape mock-patch test (test_purge_failed_devices_delegates_through_helper) catches structural drift even when byte-identical row-set assertion would still pass — locks the refactor against future inlining-the-SQL-back regressions."

patterns-established:
  - "Dialect-parametrized SQL helper: any future shared SQL helper that needs SQLite + Postgres support can copy this Literal[...] dialect approach instead of branching on adapter type."
  - "Python-side CIDR membership scan with silent-skip on unparseable rows: stdlib ipaddress idiom for any future tool that filters sitemap rows by IP range (no third-party dep needed)."
  - "Delegation-shape mock lock pattern: patch('module._helper', wraps=_helper) + assert_called_once_with as a refactor guard for shared-helper extractions."

requirements-completed:
  - SC-3
  - SC-6 (partial — purge_devices + alias coverage; remove_device coverage already shipped in Plan 01)

duration: ~12min
completed: 2026-05-03
---

# Phase 44 Plan 02: purge_devices Bulk-Delete Tool + Alias Refactor Summary

**`purge_devices` shipped as a registered MCP tool — generalized 4-mode bulk delete (`hostname` exact, `last_seen_older_than_days`, `status`, `ip_range` CIDR) with single-filter API. The existing `purge_failed_discoveries` alias was refactored to delegate through the same shared `_purge_devices_by_filter` orchestrator using a `failed_discovery` sentinel filter, preserving its broader 4-clause OR semantics by construction. Closes the bulk-delete half of the v1.7 detection→correction loop while keeping the explicit-dialect helper free of `isinstance(adapter, ...)` coupling.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-03T00:52:04Z
- **Completed:** 2026-05-03T01:03:36Z
- **Tasks:** 5 / 5 completed (Task 1a + Task 1b + Task 2 + Task 3 + Task 4)
- **Files modified:** 9 files (2 created, 7 modified)

## Accomplishments

- New pure helpers in `database.py` (zero adapter coupling): `_build_filter_clause` returns `(where, params)` fragment with `?` (sqlite) or `%s` (postgres) placeholder per `dialect: Literal["sqlite", "postgres"]`, raises ValueError on bad value shape; `_row_in_cidr` does per-row CIDR membership with D-03a silent skip on empty/unparseable connection_ip; `_FAILED_DISCOVERY_WHERE` constant carries the 4-clause OR for the alias path. Module-top imports extended with `ipaddress`, `UTC`, `timedelta`, `Literal`.
- New orchestrator `_purge_devices_by_filter(adapter, dialect, filter_type, value, dry_run)` — branches on the `dialect` STRING (not on adapter class), dispatches `ip_range` to Python-side filter via `adapter.get_all_devices()`, otherwise uses `_build_filter_clause` for SQL-side filter. Two-step DELETE cascade per D-06c (discovery_history first, then devices, single commit).
- `SQLiteAdapter.purge_failed_devices` + `PostgreSQLAdapter.purge_failed_devices` refactored to one-line delegates passing their own dialect string to the unified path. Public signature, return shape, and behavior unchanged.
- New `handle_purge_devices` + `handle_purge_devices_preview` async handlers in `network_handlers.py` (D-12). Schema, registry, annotations, and OpenAPI catalogue updated for 58-tool parity (was 56). `_adapter_dialect` is the only Phase-44-introduced `isinstance` check — lives at handler boundary, not orchestrator.
- `purge_failed_discoveries` schema description prepended with the D-07 parenthetical + the D-09 contrast block (Issue 6 four-tool extension — three tools named in the contrast block, plus the parenthetical disambiguating the alias).
- 31 functional tests in `tests/test_purge_devices.py` across 5 classes (TestPhase44RowInCidr, TestPhase44PurgeDevicesFilters, TestPhase44PurgeDevicesDryRun, TestPhase44PurgeDevicesZeroMatch, TestPhase44BuildFilterClauseValidation, TestPhase44PurgeDevicesHandler). Locks D-08 distinction (status='error' does NOT match zombie hostnames), D-04 N=0 boundary semantics, IPv6 + single-IP /32 CIDR, bool-rejection on `last_seen_older_than_days`.
- 4 alias parity tests in `tests/test_purge_failed_discoveries_alias.py`: byte-identical row sets via dry_run AND live deletion paths; delegation-shape mock lock (Issue 11) using `patch(..., wraps=...)` so future "inline the SQL back" regressions fail immediately on `assert_called_once_with` shape; handler envelope keys + counts unchanged after refactor.

## Task Commits

Each task was committed atomically:

1. **Task 1a: Pure helpers `_build_filter_clause` + `_row_in_cidr` + `_FAILED_DISCOVERY_WHERE` (no adapter coupling)** — `8c3e3e7` (feat)
2. **Task 1b: Orchestrator `_purge_devices_by_filter` + adapter delegate refactors** — `8d3818d` (feat)
3. **Task 2: Handlers + schema + registry + annotations + openapi_app** — `b43cd2d` (feat)
4. **Task 3: Functional + unit tests for purge_devices (31 tests)** — `d5cba13` (test)
5. **Task 4: Alias parity tests with delegation-shape mock lock (4 tests)** — `92668cd` (test)

## Files Created/Modified

- `src/homelab_mcp/database.py` — Module-top imports extended with `ipaddress`, `UTC`, `timedelta`, `Literal`. Added `_FAILED_DISCOVERY_WHERE`, `_build_filter_clause`, `_row_in_cidr`, `_purge_devices_by_filter`. SQLite + Postgres `purge_failed_devices` impls refactored to one-line delegates. (+217 lines net)
- `src/homelab_mcp/tool_handlers/network_handlers.py` — Added `_VALID_FILTER_TYPES`, `_adapter_dialect`, `_value_hint_for`, `handle_purge_devices`, `handle_purge_devices_preview`. Imports extended with `Literal` from typing and `PostgreSQLAdapter`/`SQLiteAdapter`/`_purge_devices_by_filter` from `..database`. (+113 lines)
- `src/homelab_mcp/tool_schemas/network_tools_schema.py` — Added `purge_devices` and `purge_devices_preview` schema entries adjacent to `purge_failed_discoveries`. Updated `purge_failed_discoveries` description with D-07 parenthetical + D-09 contrast block (Issue 6 four-tool extension). (+81 lines)
- `src/homelab_mcp/tool_handlers/__init__.py` — Imported and registered both new handlers in `TOOL_HANDLERS`. (+4 lines)
- `src/homelab_mcp/tool_annotations.py` — `purge_devices_preview` added to `_READ_ONLY_TOOLS`; `purge_devices` added to `_DESTRUCTIVE_TOOLS`. Module docstring count bumped 57 → 58. (+2 lines, 1 modified)
- `src/homelab_mcp/openapi_app.py` — Both new tools added to `STANDALONE_TOOLS` (local-DB-only) and `TOOL_CATEGORIES["Network Discovery"]`. (+4 lines)
- `tests/test_tools.py` — Bumped `len(tools) == 56` assertion to `== 58` and added the two new tool-presence assertions per Rule 3 (in-scope blocking issue from new tool registration). (+4 lines, 1 modified)
- `tests/test_purge_devices.py` — Created. 31 tests across 5 test classes per D-15. (331 lines)
- `tests/test_purge_failed_discoveries_alias.py` — Created. 4 tests in TestPhase44AliasParity class per D-15 + Issue 11 lock. (125 lines)

## Decisions Made

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Adapter param annotated `Any` (not `DatabaseAdapter`) on `_purge_devices_by_filter` | The abstract `DatabaseAdapter` does not declare `connection` (concrete impls carry it); using `Any` matches the existing accessor pattern in adapter implementations and avoids needing to declare `connection: Any` on the ABC just for one helper. | mypy clean; no false-positive `[attr-defined]` errors. |
| Explicit `dialect: Literal["sqlite", "postgres"]` parameter instead of `isinstance(adapter, ...)` branching in the orchestrator | Decouples helper from adapter taxonomy; the single concrete-class check lives at the handler boundary (`_adapter_dialect`) where the consumer already knows the adapter set. | Zero new isinstance lines on the adapter class inside `_purge_devices_by_filter`; orchestrator branches purely on the dialect string. |
| Bool rejection in `_build_filter_clause` for `last_seen_older_than_days` requires `isinstance(value, bool)` AFTER the `isinstance(value, int)` check | Python: `isinstance(True, int)` is `True` (bool subclass of int); without the explicit bool guard, `purge_devices(filter_type='last_seen_older_than_days', value=True)` would pass through as N=1 day. | `test_last_seen_rejects_bool` passes; documented in code comment. |
| `purge_failed_discoveries` description carries BOTH the D-07 parenthetical AND the D-09 contrast block (Issue 6 four-tool extension) | The alias IS a delete tool too; agents disambiguating between four delete tools benefit from seeing the contrast block on every entry. The verbatim contrast block names only three tools — the parenthetical above adds the alias-vs-bare-status distinction explicitly. | `grep -c "Use \`remove_device\` for inventory-only..."` returns 3 in the schema file. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] tests/test_tools.py expected 56 tools, found 58 after registration**
- **Found during:** Task 2 verification (full unit-suite run after registration).
- **Issue:** `test_get_available_tools` asserts `len(tools) == 56` but adding `purge_devices` + `purge_devices_preview` brings total to 58.
- **Fix:** Updated assertion to 58 and appended `assert "purge_devices" in tools` + `assert "purge_devices_preview" in tools` plus a comment update naming Phase 44 Plan 02 as the source of the increment. Same pattern Plan 01 used for the 54→56 bump.
- **Files modified:** `tests/test_tools.py`
- **Verification:** `uv run pytest tests/test_tools.py::test_get_available_tools` exits 0; full unit suite went from 944 → 979 passing (+35 new = 31 purge_devices + 4 alias; 0 regressions).
- **Committed in:** `b43cd2d` (Task 2 commit, since the test breakage was caused by the tool registration in that task).

**2. [Rule 3 - Blocking issue] mypy `[attr-defined]` on `_purge_devices_by_filter` adapter param annotated as `DatabaseAdapter`**
- **Found during:** Task 1b first mypy run.
- **Issue:** mypy flagged `adapter.connection` and similar accesses as "DatabaseAdapter has no attribute connection" — the abstract ABC does not declare the `connection` attribute (concrete impls carry it).
- **Fix:** Changed annotation from `"DatabaseAdapter"` (forward ref) to `Any`, with a docstring note explaining the rationale (`"adapter: a SQLiteAdapter or PostgreSQLAdapter instance — used for connection and get_all_devices() only. Annotated as Any because the abstract DatabaseAdapter does not declare .connection (concrete impls carry it)."`).
- **Files modified:** `src/homelab_mcp/database.py`
- **Verification:** mypy now reports zero issues on database.py.
- **Committed in:** `8d3818d` (Task 1b commit, fixed before commit).

**3. [Rule 3 - Process consistency] tool_annotations.py module docstring updated 57 → 58**
- **Found during:** Task 2 — tool count went from 56 (test_tools.py) to 58 in `TOOL_HANDLERS` and `TOOL_ANNOTATIONS` after Plan 02 registration. The module docstring at top of `tool_annotations.py` said "57" (presumably stale from a prior phase that incremented inconsistently).
- **Issue:** Documentation drift — the docstring undercounted by 1 even before Plan 02; would undercount by 2 after registration.
- **Fix:** Bumped docstring "Maps all 57 tool names" → "Maps all 58 tool names" — matches actual `len(TOOL_ANNOTATIONS)`.
- **Files modified:** `src/homelab_mcp/tool_annotations.py`
- **Verification:** `uv run python -c "from homelab_mcp.tool_annotations import TOOL_ANNOTATIONS; print(len(TOOL_ANNOTATIONS))"` returns 58.
- **Committed in:** `b43cd2d` (Task 2 commit).

## Auth Gates

None — pure DB-only feature.

## Verification

| Check | Status | Evidence |
|-------|--------|----------|
| `uv run ruff check` on modified files | PASS | All 9 touched source/test files clean. Pre-existing 7 ruff errors remain in `test_credential_store.py` / `test_credentials_cli.py` / `test_database.py` — out of scope (different files; matches Plan 01 baseline). |
| `uv run mypy src/` | PASS | Zero issues on the 5 modified `src/` files. The single pre-existing baseline error (`openapi_app.py:18 [import-untyped] jsonschema`) is unrelated to Phase 44 work. |
| `uv run pytest tests/test_purge_devices.py -v` | PASS | 31/31 tests pass. |
| `uv run pytest tests/test_purge_failed_discoveries_alias.py -v` | PASS | 4/4 tests pass. |
| `uv run pytest tests/ -m "not integration"` | PASS | 979 passed (+35 from Plan 01 baseline 944), 15 skipped, 0 new regressions. |
| `TOOL_HANDLERS` round-trip via Python import | PASS | Both new tools present; tool/handler/annotation parity 58/58/58. |
| Schema descriptions contain canonical D-09 contrast block | PASS | `grep -c "Use \`remove_device\` for inventory-only deletion of one row"` returns 3 (`remove_device` + `purge_devices` + `purge_failed_discoveries` four-tool extension). |
| Helper signature has zero adapter-class coupling | PASS | `_purge_devices_by_filter` takes `dialect: Literal["sqlite", "postgres"]` and branches on the string; no `isinstance(adapter, ...)` calls inside the helper body. The only Phase-44-introduced isinstance check is `_adapter_dialect` at handler boundary. |
| Module-top imports for `ipaddress`, `UTC`, `timedelta`, `Literal` | PASS | `head -15 src/homelab_mcp/database.py` shows all four at module level (not inside function bodies). |
| `_row_in_cidr` annotation precision | PASS | Annotated as `ipaddress.IPv4Network | ipaddress.IPv6Network` (NOT `Any`, NOT `_BaseNetwork`). |

## Pointer to Plan 03

The `TestPhase44RemoveDeviceCallPath` AST guard (D-10) lands in **Plan 03** (decommission-wording-and-ast-guard), per the phase decomposition. Plan 02 ships the runtime contract for `purge_devices`; Plan 03 will:
- Add the AST guard scoped to `handle_remove_device` body + `delete_device_by_id` adapter method body (D-10 forbidden-symbol set).
- Apply the SC-4 wording-parity sweep across `decommission_device` schema description, `docs/tool-reference.md`, `drift_detection.py` recovery pointers, and `server.py` error messages.
- Note that `handle_purge_devices` body is intentionally NOT in the AST guard's named-function list (per Plan 02 threat-model T-44-12) — the bulk-delete tool legitimately needs DB adapter access; SQL injection is its primary threat (T-44-07) and is addressed by parametrized queries (`_build_filter_clause` only emits `column OP placeholder` shapes; `value` is always bound).

## Tooling Notes

The Edit and Write tools worked correctly on this Windows worktree session for ALL of Plan 02's edits using Windows backslash paths (`C:\Users\washy\projects\mcp_python_server\.claude\worktrees\agent-a51b63e473642114c\src\...`). No cache-desync incidents — the diagnosis from Plan 01 SUMMARY (use Windows backslash paths, not forward slashes) held throughout. All grep verifications were redundant safety-checks; the Edit tool persisted writes correctly on first attempt.

## Self-Check: PASSED

All claimed files exist on disk:
- src/homelab_mcp/database.py
- src/homelab_mcp/tool_handlers/network_handlers.py
- src/homelab_mcp/tool_schemas/network_tools_schema.py
- src/homelab_mcp/tool_handlers/__init__.py
- src/homelab_mcp/tool_annotations.py
- src/homelab_mcp/openapi_app.py
- tests/test_tools.py
- tests/test_purge_devices.py
- tests/test_purge_failed_discoveries_alias.py

All claimed commits present in git log:
- 8c3e3e7 (Task 1a: pure helpers)
- 8d3818d (Task 1b: orchestrator + adapter delegate refactors)
- b43cd2d (Task 2: handlers + schema + registry + annotations + openapi)
- d5cba13 (Task 3: 31 functional tests)
- 92668cd (Task 4: 4 alias parity tests with delegation-shape mock lock)
