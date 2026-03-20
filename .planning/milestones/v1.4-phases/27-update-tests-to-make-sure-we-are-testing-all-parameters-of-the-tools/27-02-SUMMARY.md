---
phase: 27-update-tests-to-make-sure-we-are-testing-all-parameters-of-the-tools
plan: "02"
subsystem: testing
tags: [pytest, schema, regression, tool-schemas, proxmox, ssh]

requires:
  - phase: 26-sync-tool-schema-file-to-match-current-tool-parameters
    provides: Proxmox and SSH schema parameters aligned to handler signatures (sockets, cdrom, net0, ostype, swap, ssh_public_keys, unprivileged, timeout, key_path); phantom port removed from service tools

provides:
  - Schema presence tests for all Phase 26 parameter additions (8 new test functions)
  - Regression guard preventing re-introduction of phantom port on service tools
  - Structural audit covering all tool schemas for well-formed property definitions

affects: [future-schema-changes, service-tools, proxmox-tools, ssh-tools]

tech-stack:
  added: []
  patterns:
    - "Schema regression guard: assert property not in schema (prevents phantom param re-introduction)"
    - "Schema audit: iterate all tools and validate each property is a dict with type/description"

key-files:
  created: []
  modified:
    - tests/test_tools.py

key-decisions:
  - "Use 'verify_mcp_admin' (not 'verify_mcp_admin_access') as tool key — SSH schema dict key does not match function name"
  - "cdrom and ssh_public_keys have no default in schema (None in handler only) — assertions omit default check"
  - "Structural audit accepts oneOf/anyOf in addition to type/description to handle JSON Schema polymorphic properties"

patterns-established:
  - "Regression guard pattern: import SOURCE dict directly to guard against specific property presence"
  - "Schema audit pattern: iterate get_available_tools() and validate structural integrity of all properties"

requirements-completed: [TEST-SCH-01, TEST-SCH-02, TEST-SCH-03, TEST-SCH-04, TEST-SCH-05, TEST-AUDIT-01]

duration: 3min
completed: 2026-03-19
---

# Phase 27 Plan 02: Update Tests - Schema Presence Tests Summary

**8 schema regression tests covering all Phase 26 parameter changes: sockets/cdrom/net0/ostype on create_proxmox_vm, swap/ssh_public_keys/unprivileged on create_proxmox_lxc, timeout on setup_mcp_admin and verify_mcp_admin, timeout absence guard on ssh_execute_command, key_path on update_mcp_admin_groups, plus port regression guard across all SERVICE_TOOLS and structural audit across all tool schemas.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-19T20:17:59Z
- **Completed:** 2026-03-19T20:20:34Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Added 8 new test functions in tests/test_tools.py covering all Phase 26 parameter additions
- Port regression guard prevents phantom `port` from returning to SERVICE_TOOLS schemas
- Structural audit validates every property in all tool schemas is a well-formed dict

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Proxmox and SSH schema presence tests** - `b729890` (test)
2. **Task 2: Add service port regression guard and structural audit** - `4fa9431` (test)

**Plan metadata:** (final docs commit — see below)

## Files Created/Modified

- `tests/test_tools.py` - Added 8 new test functions (schema presence, regression guard, structural audit)

## Decisions Made

- Used `"verify_mcp_admin"` as the tool key (not `"verify_mcp_admin_access"`) — the SSH schema dict uses the shorter form as the key, while the Python function is named `verify_mcp_admin_access`
- `cdrom` and `ssh_public_keys` have no `default` key in the schema (they default to `None` in the handler only) — assertions check for property presence but not a default value
- Structural audit accepts `oneOf`/`anyOf` in addition to `type`/`description` so it does not false-positive on valid JSON Schema polymorphic property definitions

## Deviations from Plan

None - plan executed exactly as written. The tool key correction (`verify_mcp_admin` vs `verify_mcp_admin_access`) was noted in the plan's action block and resolved as documented there.

## Issues Encountered

None.

## Next Phase Readiness

- Phase 27 plan 02 complete — all Phase 26 parameter changes are now covered by schema-level regression tests
- Full non-integration test suite passes: 680 tests, 0 failures

---
*Phase: 27-update-tests-to-make-sure-we-are-testing-all-parameters-of-the-tools*
*Completed: 2026-03-19*
