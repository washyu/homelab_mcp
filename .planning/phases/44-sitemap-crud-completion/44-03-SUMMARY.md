---
phase: 44-sitemap-crud-completion
plan: 03
subsystem: testing
tags: [ast-guard, docs, wording-sweep, regression-test, decommission_device, sitemap-crud, tool-reference]

requires:
  - phase: 44-sitemap-crud-completion
    plan: 01
    provides: handle_remove_device + handle_remove_device_preview + delete_device_by_id (SQLite + Postgres) — the four named functions guarded by TestPhase44RemoveDeviceCallPath.
  - phase: 44-sitemap-crud-completion
    plan: 02
    provides: handle_purge_devices + handle_purge_devices_preview + purge_failed_discoveries alias schema description (already carrying the contrast block) — Plan 03 docs sweep extends the contrast block to the docs entry too.
  - phase: 37-drift-output-shape-error-hygiene
    provides: PROXMOX_HOST whole-tree AST guard pattern (TestPhase37DriftHygiene) — Plan 03 wording sweep MUST not introduce that forbidden literal; verified post-sweep.
  - phase: 38.1-sitemap-keystore-credential-binding
    provides: body-level AST walk template (TestPhase381CredBinding::test_scan_drift_no_continue_in_row_loop_phase38_1) — Plan 03 TestPhase44RemoveDeviceCallPath mirrors this idiom.
provides:
  - TestPhase44RemoveDeviceCallPath AST guard with 15 per-symbol test methods × 4 guarded functions (Issue 12 — handle_remove_device + handle_remove_device_preview + SQLiteAdapter.delete_device_by_id + PostgreSQLAdapter.delete_device_by_id).
  - Canonical D-09 contrast-block sentence in decommission_device schema description (the FOURTH carrier in source code; Plans 01/02 added the other three — remove_device, purge_devices, purge_failed_discoveries schemas).
  - Wording-parity sweep across drift_detection.py (_EMPTY_SCAN_GUIDANCE + _classify_probe_failure missing-branch + _classify_credential_failure degenerate-branch) and server.py (homelab://drift/latest resource description + credentials-link CLI duplicate-row error) — adds remove_device / purge_devices pointers WITHOUT introducing the verbatim contrast block (Issue 4 scope clarification).
  - Five new docs/tool-reference.md entries (remove_device, remove_device_preview, purge_devices, purge_devices_preview, purge_failed_discoveries) with example invocations covering happy path + dry_run + per-filter cases (hostname, stale-row sweep, status, CIDR).
  - Updated decommission_device docs entry with canonical contrast block + See-also cross-reference per D-09a.
  - Verified four-tool contrast block byte-identical across 4 schema files + 4 docs entries (Issue 6 four-tool extension).
affects: []

tech-stack:
  added: []
  patterns:
    - "Multi-target body-level AST guard: 3-tuple (rel_path, class_name | None, func_name) as the GUARDED_FUNCTIONS row shape handles BOTH top-level functions AND class methods in one helper. _load_function_subtree scopes to ClassDef first when class_name is non-None."
    - "Two scan helpers (_scan_for_name + _scan_for_attribute) compose into per-symbol test methods. Bare-name helper covers Name/Attribute/Import shapes; attribute helper covers value_id.attr_name pairs (keyring.delete_password, subprocess.run). Per D-10b one test per symbol means failures pinpoint the regressed symbol."
    - "Wording-parity tiered scope (Issue 4): the verbatim canonical sentence (D-09) carries in 4 schema files + 4 docs entries; drift error messages and CLI errors get ad-hoc updates that mention the new tools but are NOT verbatim copies. Keeps drift error messages contextual ('here's how to fix this drift row') vs tool-catalogue prose ('here's how to choose between these tools')."

key-files:
  created: []
  modified:
    - tests/test_ast_regression.py
    - src/homelab_mcp/tool_schemas/infrastructure_tools_schema.py
    - src/homelab_mcp/drift_detection.py
    - src/homelab_mcp/server.py
    - docs/tool-reference.md

key-decisions:
  - "AST guard scope per Issue 12: 4 guarded functions (handle_remove_device + handle_remove_device_preview + SQLiteAdapter.delete_device_by_id + PostgreSQLAdapter.delete_device_by_id). The preview's 1-line delegate body trivially passes today, but including it future-proofs against drift where someone extends the preview body with logic touching a forbidden symbol."
  - "Each per-symbol test method internally iterates over all 4 guarded functions — 15 tests × 4 functions = 60 lookups per run. Each lookup is sub-millisecond (T-44-16 acceptance). A single test failure pinpoints BOTH the regressed symbol AND the offending guarded function via the assertion message."
  - "Issue 4 scope clarification applied: the verbatim D-09 contrast block sentence appears ONLY in 4 schema files (network_tools_schema.py 3x + infrastructure_tools_schema.py 1x = 4 schema-file occurrences across the four delete-tool schemas) + 4 docs entries (Issue 6 four-tool extension). Drift error messages and CLI errors carry wording-parity updates that mention the new tools but NOT the canonical sentence — verified by negative grep (`grep -c \"Use ...\" drift_detection.py server.py` returns 0)."
  - "Issue 6 four-tool contrast extension: purge_failed_discoveries gains the contrast block in BOTH the schema (Plan 02) AND the new docs entry (this plan). The alias IS a delete tool too; the parenthetical disambiguates the alias from the bare status filter."
  - "Rule 3 auto-fix: docs/tool-reference.md had no pre-existing `### purge_failed_discoveries` entry — only a passing mention in scan_infrastructure_drift's description. Created the new entry as the fourth carrier of the contrast block per Issue 6. The plan's `read_first` step said 'locate the existing purge_failed_discoveries entry' — none existed; Rule 3 created it to satisfy the four-tool extension contract."

patterns-established:
  - "Multi-target AST guard with class-method scoping: the (rel_path, class_name | None, func_name) 3-tuple shape supports both top-level and class-scoped FunctionDef lookups via a single helper. Reusable for any future guard that targets adapter methods on multiple concrete classes (e.g., a future T-44-XX guard on SQLiteAdapter.X + PostgreSQLAdapter.X pair)."
  - "Tiered wording-parity scope: verbatim canonical sentence carriers (high-trust catalogue locations like tool descriptions and docs entries) vs ad-hoc mentions (operational/error messages where context dominates). Preserves consistency where the catalogue lives, preserves contextual nuance where the user is mid-task."

requirements-completed:
  - SC-4
  - SC-5
  - SC-6

duration: ~25min
completed: 2026-05-03
---

# Phase 44 Plan 03: AST Guard + Wording Sweep + docs/tool-reference.md Summary

**`TestPhase44RemoveDeviceCallPath` AST guard locks the call-path safety contract for the new sitemap-CRUD tools shipped in Plans 01 + 02 — 15 per-symbol tests × 4 guarded functions catch any future drift where someone "just calls decommission internally"; canonical D-09 contrast block sentence now carries verbatim across 4 schema files + 4 docs entries (Issue 6 four-tool extension); drift error messages and CLI errors gain remove_device / purge_devices pointers via wording-parity sweep (Issue 4 scope clarification — contextual mentions, NOT verbatim contrast block); Phase 44 collectively closes SC-1 through SC-6 across Plans 01/02/03.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-03T01:00:00Z (worktree base)
- **Completed:** 2026-05-03T01:16:32Z
- **Tasks:** 4 / 4 completed (Task 1: AST guard | Task 2: wording sweep | Task 3: docs | Task 4: quality gate)
- **Files modified:** 5 files (0 created, 5 modified)

## Accomplishments

- New `TestPhase44RemoveDeviceCallPath` test class in `tests/test_ast_regression.py` (sibling to existing `TestPhase37/38.1/40/41/41_1` classes). 15 per-symbol `test_*` methods (D-10b) × 4 guarded functions (Issue 12 — `handle_remove_device` + `handle_remove_device_preview` + `SQLiteAdapter.delete_device_by_id` + `PostgreSQLAdapter.delete_device_by_id`). Body-level scope per D-10a; transitive call graph NOT walked. Forbidden symbols: 8 bare names (`ssh_connect`, `asyncssh`, `decommission_network_device`, `_stop_all_device_services`, `_remove_from_clusters`, `_execute_migration_plan`, `delete_credential`, `delete_proxmox_credential`) + 7 attribute pairs (`keyring.delete_password`, `keyring.set_password`, `subprocess.run/Popen/call/check_call/check_output`).
- `decommission_device` schema description in `infrastructure_tools_schema.py` updated to include the canonical D-09 contrast-block sentence (verbatim copy from `remove_device` and `purge_devices` schemas added in Plans 01/02). This is the THIRD source-file carrier of the verbatim contrast block (after Plans 01/02 added it to network_tools_schema.py 3x).
- Wording-parity sweep applied to `drift_detection.py`:
  - `_EMPTY_SCAN_GUIDANCE` updated to mention `remove_device` and `purge_devices` alongside the existing `purge_failed_discoveries` and `decommission_device` pointers.
  - `_classify_probe_failure` missing-branch message updated to point at `remove_device` (with `get_network_sitemap` lookup hint), `purge_devices`, and `decommission_device` while preserving the existing `purge_failed_discoveries` pointer.
  - `_classify_credential_failure` degenerate-branch updated to mention `purge_failed_discoveries`, `purge_devices(filter_type='hostname', value='unknown')`, and `remove_device`.
- Wording-parity sweep applied to `server.py`:
  - `homelab://drift/latest` resource description updated to enumerate `remove_device` / `purge_devices` / `decommission_device` alongside the existing `discover_and_map` / `get_network_sitemap` / `purge_failed_discoveries` pointers.
  - Credentials-link CLI duplicate-row error (anchored by unique substring `"multiple sitemap rows match hostname"` per Issue 10) updated to point at `remove_device <device_id>` (precise) AND `purge_failed_discoveries` (bulk failed-discovery cleanup). The line-1055 credentials-unlink variant was NOT touched (per plan scope — it doesn't currently mention any tool).
- 5 new entries in `docs/tool-reference.md`: `### remove_device`, `### remove_device_preview`, `### purge_devices`, `### purge_devices_preview`, `### purge_failed_discoveries` (the 5th was created as a Rule 3 auto-fix — see Deviations). Each new entry has Description + Annotations + Arguments table + Example block(s) + Returns line per the existing `### decommission_device` template at lines 493+. `purge_devices` carries 4 example variants (hostname / stale-row sweep / status / CIDR).
- Existing `### decommission_device` docs entry updated with the canonical contrast-block sentence + `See also: \`remove_device\` for inventory-only deletion (no host-side cleanup).` cross-reference per D-09a.
- Final quality gate: 994 tests passing (+15 from Plan 02 baseline 979), 15 skipped, 0 new regressions. Per-file Phase-44 counts hold (Issue 13).

## Task Commits

Each task was committed atomically:

1. **Task 1: TestPhase44RemoveDeviceCallPath AST guard (15 per-symbol tests × 4 guarded functions)** — `64f3ad1` (test)
2. **Task 2: Wording sweep across infrastructure_tools_schema.py + drift_detection.py + server.py** — `93c05d9` (docs)
3. **Task 3: docs/tool-reference.md — 5 new entries + decommission_device cross-reference + four-tool contrast block (Issue 6)** — `46410e3` (docs)
4. **Task 4: Final quality gate verification (no source change)** — no commit needed

## Files Created/Modified

- `tests/test_ast_regression.py` — Appended new `TestPhase44RemoveDeviceCallPath` class (220 lines) at file end, sibling to existing `TestPhase37/38.1/40/41/41_1` classes. Uses 3-tuple `_GUARDED_FUNCTIONS` (rel_path, class_name | None, func_name) shape so the same helper handles top-level functions AND class methods in one walk. `_load_function_subtree` scopes to `ClassDef` first when class_name is non-None. Per-symbol assertions (`_assert_no_forbidden_name`, `_assert_no_forbidden_attribute`) iterate over all 4 guarded functions.
- `src/homelab_mcp/tool_schemas/infrastructure_tools_schema.py` — `decommission_device` description expanded from a one-liner (`"Safely remove a device from the network infrastructure"`) to a 3-sentence multi-line form ending with the canonical D-09 contrast block. Schema `inputSchema` block untouched.
- `src/homelab_mcp/drift_detection.py` — 3 message updates:
  - `_EMPTY_SCAN_GUIDANCE` (lines 56-63 → 56-65): added `remove_device` + `purge_devices` mid-list; existing tool pointers preserved.
  - `_classify_probe_failure` missing-branch (lines 223-230 → 223-234): expanded message to point at `remove_device` with `get_network_sitemap` lookup hint, `purge_devices`, `decommission_device`, and `purge_failed_discoveries` (alias).
  - `_classify_credential_failure` degenerate-branch (lines 123-127 → 123-129): added `purge_devices(filter_type='hostname', value='unknown')` + `remove_device` alongside `purge_failed_discoveries`.
- `src/homelab_mcp/server.py` — 2 updates:
  - `homelab://drift/latest` resource description (lines 152-158): added `remove_device` + `purge_devices` + `decommission_device` to the recovery tool list.
  - Credentials-link CLI duplicate-row error (lines 1018-1025): replaced bare `purge_failed_discoveries` mention with two-tool list — `remove_device <device_id>` (precise) and `purge_failed_discoveries` (bulk).
- `docs/tool-reference.md` — 5 new sections inserted after `### update_device_fingerprint_preview` (line 420 area) and before `## Infrastructure Tools` (line 422 → line 608 after edits). `### decommission_device` updated with contrast block + See-also cross-reference. Total +186 lines net.

## Decisions Made

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 3-tuple `_GUARDED_FUNCTIONS` row shape `(rel_path, class_name | None, func_name)` | Need to handle both top-level functions (`handle_remove_device` in network_handlers.py) AND class methods (`delete_device_by_id` in `SQLiteAdapter` + `PostgreSQLAdapter` ClassDefs) in one helper. The optional class_name slot keeps the helper polymorphic without two parallel iteration loops. | Single `_load_function_subtree` helper handles both cases; per-symbol assertions iterate over all 4 guarded functions in one loop. |
| `_scan_for_name` covers Name + Attribute (attr) + Import shapes; `_scan_for_attribute` covers `value_id.attr_name` pairs | Bare-name forbidden symbols (e.g., `decommission_network_device`) can appear as `decommission_network_device(...)` (Name) or `module.decommission_network_device(...)` (Attribute attr) or `from X import decommission_network_device` (Import alias). The keyring/subprocess cases need a value-anchored attribute walk to distinguish `keyring.delete_password` from a hypothetical `something_else.delete_password`. | Two scan helpers cover the union of forbidden-symbol shapes; per-symbol tests pick the right one. |
| Created NEW `### purge_failed_discoveries` docs entry as a Rule 3 auto-fix | Plan said "locate the existing purge_failed_discoveries entry" but no such entry existed in `docs/tool-reference.md` — only a passing mention inside `scan_infrastructure_drift`'s description. The four-tool contrast block (Issue 6) requires `purge_failed_discoveries` to be the fourth carrier; without an entry, the count would be 3, not 4. | Created the entry adjacent to the four new ones, carrying the D-07 parenthetical + canonical contrast block. Total contrast-block carriers in docs = 4 (matches Issue 6 acceptance). |
| Wording-parity sweep updates are NOT verbatim contrast block (Issue 4 scope clarification) | Drift error messages live in operational context ("here's how to fix this drift row"); pasting the tool-catalogue contrast sentence verbatim would dilute the contextual specificity. The four-tool list in `_EMPTY_SCAN_GUIDANCE` and the per-message hints in `_classify_*` give the user the right tool for the right situation without over-quoting the catalogue. | Drift/server messages mention `remove_device` / `purge_devices` in context; verified by negative grep `grep -c "Use \`remove_device\` for inventory-only deletion of one row" drift_detection.py server.py` returns 0. |
| line-1055 credentials-unlink CLI error NOT touched | Plan scope explicitly anchored Step E at line ~1020 (the credentials-link variant that already mentions `purge_failed_discoveries`). Line ~1055 (credentials-unlink) doesn't currently mention any cleanup tool — adding one would expand scope beyond the plan's wording-parity sweep. | Two `multiple sitemap rows match hostname` occurrences exist in server.py (lines 1020 + 1055); only line 1020 was updated. Negative confirms via grep — line 1055 still has its original text. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] `### purge_failed_discoveries` docs entry did not exist**
- **Found during:** Task 3 — locating the existing entry per the plan's `read_first` step.
- **Issue:** The plan's Step C said "Update existing `### purge_failed_discoveries` entry" but no such section existed in `docs/tool-reference.md`. Only a passing mention inside `scan_infrastructure_drift`'s description (line 676 + the example guidance text at line 752). Without creating the section, the four-tool contrast-block extension (Issue 6) couldn't be satisfied — the count would be 3 (remove_device + purge_devices + decommission_device), not the required 4.
- **Fix:** Created a new `### purge_failed_discoveries` entry adjacent to the four new sections (after `### purge_devices_preview` and before `## Infrastructure Tools`). Entry carries the D-07 parenthetical describing equivalence to `purge_devices` with the failed-discovery filter + the canonical D-09 contrast-block sentence (Issue 6 four-tool extension).
- **Files modified:** `docs/tool-reference.md`
- **Verification:** `grep -c "Use \`remove_device\` for inventory-only deletion of one row" docs/tool-reference.md` returns 4 (matches Issue 6 acceptance criterion).
- **Committed in:** `46410e3` (Task 3 commit, since the missing entry was discovered during Task 3 execution).

### CONTEXT.md / Plan Scope Clarifications Applied (recorded as deviations per plan's `<objective>` section)

**Issue 4 scope clarification — wording-parity vs verbatim contrast block:**
- The verbatim D-09 contrast-block sentence is reserved for the FOUR tool-description locations in source code (`remove_device`, `purge_devices`, `decommission_device`, `purge_failed_discoveries`) + the FOUR `docs/tool-reference.md` overview entries.
- Wording-parity sweep on `drift_detection.py` and `server.py` uses ad-hoc updates that MENTION the new tools (`remove_device`, `purge_devices`) but do NOT necessarily reuse the canonical sentence verbatim. This keeps drift error messages contextual rather than tool-catalogue prose.
- Verified by negative grep: `grep -c "Use \`remove_device\` for inventory-only deletion of one row" src/homelab_mcp/drift_detection.py src/homelab_mcp/server.py` returns 0.

**Issue 6 four-tool contrast extension:**
- Including `purge_failed_discoveries` in the contrast-block carriers extends D-09 from a three-tool to a four-tool contrast block. Pragmatic upgrade — the alias IS a delete tool too. Plan 02 already added the contrast block to the `purge_failed_discoveries` schema description; this plan's docs sweep extends it to the docs entry too.
- Verified: contrast block appears in 4 docs entries (`remove_device`, `purge_devices`, `purge_failed_discoveries`, `decommission_device`) + 4 schema-file occurrences (3 in `network_tools_schema.py` + 1 in `infrastructure_tools_schema.py`).

## Auth Gates

None — pure code/docs change with no external infrastructure interaction.

## Verification

| Check | Status | Evidence |
|-------|--------|----------|
| `uv run pytest tests/test_ast_regression.py::TestPhase44RemoveDeviceCallPath -v` | PASS | 15/15 tests pass; each iterates over all 4 guarded functions per Issue 12. |
| `uv run pytest tests/test_ast_regression.py -v` | PASS | 45/45 tests pass (30 prior + 15 new); no regression in Phase 37/38.1/40/41/41.1 guards. |
| `uv run ruff check src/ tests/` | BASELINE | 7 pre-existing baseline errors in tests/test_credential_store.py + tests/test_credentials_cli.py + tests/test_database.py — out of scope (different files; matches Plan 01/02 documented baseline). Files modified by this plan are clean. |
| `uv run mypy src/` | BASELINE | 1 pre-existing baseline error (`openapi_app.py:18 [import-untyped] jsonschema`) — matches Plan 01/02 documented baseline. Files modified by this plan are clean. |
| `uv run pytest tests/ -m "not integration"` | PASS | 994 passed (+15 from Plan 02 baseline 979), 15 skipped, 0 new regressions. |
| `uv run pytest tests/ -k "drift" -m "not integration"` | PASS | 125/125 drift-related tests pass; wording sweep didn't break drift assertions. |
| Per-file Phase-44 collection counts (Issue 13) | PASS | test_remove_device.py: 8 tests (≥8) ✓; test_purge_devices.py: 31 tests (≥25) ✓; test_purge_failed_discoveries_alias.py: 4 tests (≥4) ✓; TestPhase44RemoveDeviceCallPath: 15 tests (≥15) ✓. |
| All 4 new tools in `TOOL_HANDLERS` | PASS | `from homelab_mcp.tool_handlers import TOOL_HANDLERS` shows all 4 present; total = 58 (matches Plan 02 baseline). |
| Contrast block schema-file count (≥3) | PASS | network_tools_schema.py: 3 (remove_device + purge_devices + purge_failed_discoveries); infrastructure_tools_schema.py: 1 (decommission_device). Total: 4. |
| Contrast block in drift_detection.py + server.py (==0; Issue 4 negative) | PASS | Both files return 0; wording-parity sweep does NOT carry the verbatim contrast-block sentence per Issue 4 scope clarification. |
| Contrast block in docs/tool-reference.md (≥4 — Issue 6 four-tool extension) | PASS | 4 occurrences (remove_device + purge_devices + purge_failed_discoveries + decommission_device entries). |
| `grep -c "multiple sitemap rows match hostname" src/homelab_mcp/server.py` | PASS | Returns 2 (lines 1020 + 1055 unchanged in count); line 1020 contains `remove_device` post-edit (per plan); line 1055 unchanged (per plan scope). |
| `grep -c "PROXMOX_HOST" src/homelab_mcp/drift_detection.py src/homelab_mcp/server.py` | PASS | Returns 0 in both files; Phase 37 D-11 invariant preserved through wording sweep. |
| `uv run ruff check` on the 4 modified source files (test + 3 src) | PASS | All 4 files clean. |
| `uv run mypy` on the 3 modified src files | PASS | All 3 files clean (no new errors beyond the pre-existing openapi_app.py jsonschema baseline). |

## Phase 44 Collective Close-Out

Phase 44 collectively closes SC-1 through SC-6 across Plans 01/02/03:

- **SC-1 (remove_device tool registered):** Plan 01 — `remove_device` + `remove_device_preview` registered in TOOL_HANDLERS / TOOL_ANNOTATIONS / openapi_app + schema with the canonical contrast block.
- **SC-2 (credential-preservation invariant):** Plan 01 — `tests/test_remove_device.py::TestPhase44RemoveDeviceCredentialPreservation` asserts `keyring.delete_password` and `keyring.set_password` are NOT called after `remove_device` runs. Plan 03 AST guard locks this at parse time too (forbidden-symbol set includes both).
- **SC-3 (purge_devices tool with 4 filters + alias):** Plan 02 — `purge_devices` + `purge_devices_preview` shipped with `hostname` / `last_seen_older_than_days` / `status` / `ip_range` filter types; `purge_failed_discoveries` refactored to delegate through the shared `_purge_devices_by_filter` helper using the `failed_discovery` sentinel filter. 31 + 4 tests in Plan 02.
- **SC-4 (three-tool/four-tool contrast block wording-parity):** Plans 01 + 02 + 03 — canonical D-09 sentence appears verbatim in 4 schema files (network_tools_schema.py 3x + infrastructure_tools_schema.py 1x) + 4 docs entries (Issue 6 four-tool extension). Wording-parity sweep on drift_detection.py + server.py mentions the new tools without verbatim copy (Issue 4).
- **SC-5 (docs/tool-reference.md entries):** Plan 03 — 5 new sections (4 new tools + purge_failed_discoveries created via Rule 3 auto-fix) with example invocations covering happy + dry_run + per-filter cases. decommission_device entry gets See-also cross-reference per D-09a.
- **SC-6 (full-suite quality gate ≥907 + AST guard):** Plan 03 — `TestPhase44RemoveDeviceCallPath` AST guard ships with 15 per-symbol tests × 4 guarded functions; full unit suite shows 994 passing (well above SC-6's 907 floor); no new skips; ruff + mypy clean on Phase-44-modified files.

## Pointer to v1.7 Milestone Close

Phase 44 is the final phase of the v1.7 detection→correction loop. With Plan 03 landed:

- The drift detection→correction loop is closed: drift surfaces a divergence (Phase 39); the user/agent now has 4 distinct delete-tool surfaces (`remove_device` for one row inventory, `purge_devices` for bulk filter inventory, `decommission_device` for host-side cleanup + DELETE, `purge_failed_discoveries` for the broader 4-clause failed-discovery set) with consistent D-09 disambiguation wording across schema descriptions, recovery error messages, and `docs/tool-reference.md`.
- AST-guard suite covers the four guarded function bodies — any future "let's just call decommission internally" drift fails at parse time (D-10 footgun-class meta-test).
- v1.7 milestone-close UAT can now exercise: (a) `remove_device` with credential preservation (SC-2), (b) `purge_devices` per-filter behavior (SC-3), (c) drift report → recovery tool surfacing via the updated wording (SC-4), (d) docs cross-reference completeness (SC-5).

## Tooling Notes

The Edit tool worked correctly on this Windows worktree session for ALL of Plan 03's edits using Windows backslash paths (e.g. `C:\Users\washy\projects\mcp_python_server\.claude\worktrees\agent-aae4c8591151e11eb\tests\test_ast_regression.py`). No cache-desync incidents — the Plan 01 SUMMARY's diagnosis (use Windows backslash paths, not forward slashes) held throughout. All grep verifications were passive safety-checks; the Edit tool persisted writes correctly on first attempt for every modification.

## Self-Check: PASSED

All claimed files exist on disk:
- tests/test_ast_regression.py (modified)
- src/homelab_mcp/tool_schemas/infrastructure_tools_schema.py (modified)
- src/homelab_mcp/drift_detection.py (modified)
- src/homelab_mcp/server.py (modified)
- docs/tool-reference.md (modified)
- .planning/phases/44-sitemap-crud-completion/44-03-SUMMARY.md (this file, created)

All claimed commits present in git log:
- 64f3ad1 (Task 1: AST guard)
- 93c05d9 (Task 2: wording sweep)
- 46410e3 (Task 3: docs/tool-reference.md)
