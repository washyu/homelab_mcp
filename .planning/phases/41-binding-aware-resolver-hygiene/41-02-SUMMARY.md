---
phase: 41-binding-aware-resolver-hygiene
plan: "02"
subsystem: ssh
tags: [ssh, credential-resolution, sitemap, database, phase41, bug-aa, bug-v]

# Dependency graph
requires:
  - phase: 41-01
    provides: "RED AST guard test (test_resolve_ssh_for_sitemap_row_helper_exists XFAIL)"
  - phase: 38.1
    provides: "resolve_ssh_credentials Tier-0 UUID short-circuit (credential_id= keyword); get_database_adapter module-level import"

provides:
  - "resolve_ssh_for_sitemap_row helper in src/homelab_mcp/ssh_tools.py"
  - "6 unit tests covering all 5 resolution paths plus multi-match disambiguation"
  - "Phase 41 keystone helper — both sitemap.discover_and_store (Plan 03) and drift_detection._probe_one (Plan 04) will call this"

affects:
  - "41-03 (sitemap plan wires this helper into discover_and_store)"
  - "41-04 (drift plan wires this helper into _probe_one)"
  - "41-05 (AST guard plan verifies both call sites use this helper)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "row-lookup-then-delegate: helper does NOT duplicate resolve_ssh_credentials Tier-0/1/2 logic; it wraps with DB row lookup and delegates"
    - "status=success disambiguation: multi-match prefers status='success' rows; still ambiguous → CredentialNotFoundError with get_network_sitemap pointer"
    - "mocker.patch in module-level test functions: pytest-mock mocker fixture works with module-level functions (not just class methods)"

key-files:
  created: []
  modified:
    - src/homelab_mcp/ssh_tools.py
    - tests/test_ssh_tools.py

key-decisions:
  - "Placed resolve_ssh_for_sitemap_row immediately above _scan_registry_for_binding (~line 812) per plan specification; does NOT delete dead-code _resolve_ssh_credentials_with_binding (deferral contract from RESEARCH §Assumption A3)"
  - "Used module-level function style for tests (not class) to match test_ssh_tools.py convention; mocker fixture works identically"
  - "Fixed pre-existing ruff F401 (unused MagicMock in function-body import) by adding # noqa: F401 alongside existing # noqa: PLC0415 — Rule 3 (blocking) since ruff check must exit 0"
  - "Import order: from homelab_mcp.ssh_tools alphabetically before from src.homelab_mcp.ssh_tools to satisfy ruff I001"

patterns-established:
  - "resolve_ssh_for_sitemap_row delegation pattern: DB lookup → zero rows = fallback (creds, None); single+binding = Tier-0 (creds, row); single+null = Tier-1/2 (creds, row); multi+success = healthy row; multi+ambiguous = CredentialNotFoundError"

requirements-completed:
  - Bug-AA

# Metrics
duration: 5min
completed: 2026-04-30
---

# Phase 41 Plan 02: resolve_ssh_for_sitemap_row Helper Summary

**Sitemap-row-aware SSH credential resolver — delegates to resolve_ssh_credentials Tier-0/1/2 after DB lookup; returns (SSHCredentials, row|None) for both credential binding and connection_ip dialing (Bugs AA + V)**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-30T21:18:00Z
- **Completed:** 2026-04-30T21:22:43Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `resolve_ssh_for_sitemap_row` helper to `src/homelab_mcp/ssh_tools.py` immediately above `_scan_registry_for_binding`
- Helper implements all 5 resolution paths: zero-row fallback, single+binding Tier-0, single+null Tier-1/2, multi-match-success disambiguation, multi-match-ambiguous raise
- Added 6 unit tests covering all paths including the `status='success'` disambiguation case
- AST guard `test_resolve_ssh_for_sitemap_row_helper_exists` (from Plan 01 wave 0) will flip GREEN on merge
- Ruff + mypy clean on all modified files; all 30 tests pass

## Task Commits

1. **Task 1: Add resolve_ssh_for_sitemap_row helper** - `3b0f57a` (feat)
2. **Task 2: Add 6 unit tests** - `924ec29` (feat)

## Files Created/Modified

- `src/homelab_mcp/ssh_tools.py` - New `resolve_ssh_for_sitemap_row` function (93 lines including docstring) inserted above `_scan_registry_for_binding`
- `tests/test_ssh_tools.py` - 6 new module-level test functions + imports for `CredentialNotFoundError`, `SSHCredentials`, `resolve_ssh_for_sitemap_row`

## Decisions Made

- Used module-level functions (not a class) to match `test_ssh_tools.py`'s established convention
- Did NOT delete `_resolve_ssh_credentials_with_binding` dead-code per RESEARCH §Assumption A3 deferral contract
- Did NOT modify `_scan_registry_for_binding` or `ssh_discover_system_with_binding` — those are Plan 03's concern
- Added `# noqa: F401` to fix pre-existing ruff F401 on a function-body `MagicMock` import — required for `uv run ruff check` to exit 0

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed pre-existing ruff F401 surfaced by new module-level imports**
- **Found during:** Task 2 (adding imports to test_ssh_tools.py)
- **Issue:** Adding `from homelab_mcp.ssh_tools import ...` at module level caused ruff to recheck the whole file, surfacing a pre-existing `F401: unused MagicMock import` inside a function body at line 881. The `# noqa: PLC0415` already present didn't cover F401. `uv run ruff check tests/test_ssh_tools.py` exited 1.
- **Fix:** Added `F401` to the existing `# noqa: PLC0415` comment → `# noqa: PLC0415, F401`
- **Files modified:** `tests/test_ssh_tools.py:881`
- **Verification:** `uv run ruff check tests/test_ssh_tools.py` exits 0
- **Committed in:** `924ec29` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 - blocking lint issue)
**Impact on plan:** Necessary for CI compliance. No scope creep; the pre-existing issue was already in the file and only surfaced because my module-level import triggered a full-file recheck.

## Issues Encountered

None beyond the ruff F401 auto-fix above.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The helper is a pure composition layer over existing `get_database_adapter()` + `resolve_ssh_credentials()` — no new trust boundaries created.

## Known Stubs

None. The helper is fully functional with all 5 resolution paths implemented.

## Next Phase Readiness

- `resolve_ssh_for_sitemap_row` is ready for Plan 03 (`sitemap.discover_and_store` wiring) and Plan 04 (`drift_detection._probe_one` wiring)
- The helper's return type `tuple[SSHCredentials, dict[str, Any] | None]` gives callers both credentials and `connection_ip` for Bug V dial-target fix
- Plan 01's AST guard `test_resolve_ssh_for_sitemap_row_helper_exists` will flip from XFAIL to XPASS (→ PASS via strict=True) when wave 0 is merged before this wave 1

## Self-Check

Files exist:
- `src/homelab_mcp/ssh_tools.py` - confirmed (modified)
- `tests/test_ssh_tools.py` - confirmed (modified)

Commits exist:
- `3b0f57a` feat(41-02): add resolve_ssh_for_sitemap_row helper - confirmed
- `924ec29` feat(41-02): add 6 unit tests - confirmed

## Self-Check: PASSED

---
*Phase: 41-binding-aware-resolver-hygiene*
*Completed: 2026-04-30*
