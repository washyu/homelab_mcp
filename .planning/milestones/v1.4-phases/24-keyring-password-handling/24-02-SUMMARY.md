---
phase: 24-keyring-password-handling
plan: 02
subsystem: testing
tags: [ssh, keyring, mcp, pytest, mock, schema]

# Dependency graph
requires:
  - phase: 24-keyring-password-handling plan 01
    provides: resolve_ssh_credentials integration in setup_remote_mcp_admin and update_mcp_admin_groups
provides:
  - Keyring resolution unit tests for setup_mcp_admin and update_mcp_admin_groups
  - Schema regression guard preventing any tool from requiring password
  - Audit test covering all 57 tools in the registry
affects: [future-tool-additions, schema-audits, 24-keyring-password-handling]

# Tech tracking
tech-stack:
  added: []
  patterns: [mock resolve_ssh_credentials in all setup_mcp_admin tests, schema audit pattern via get_available_tools()]

key-files:
  created: []
  modified:
    - tests/test_ssh_tools.py
    - tests/test_tools.py

key-decisions:
  - "Mock resolve_ssh_credentials in all 4 existing setup_mcp_admin tests to prevent real keyring/DB access"
  - "Use force_update_key=False in keyring test to keep mock chain minimal (5 commands vs 9)"
  - "Add updated_groups_result mock for update_mcp_admin_groups (function calls groups twice: before and after updates)"

patterns-established:
  - "Pattern: Always mock resolve_ssh_credentials when testing functions that call setup_remote_mcp_admin or update_mcp_admin_groups"
  - "Pattern: test_no_tool_has_password_required as schema audit guard — update allowlist if a future tool legitimately needs required password"

requirements-completed: [SETUP-01, SETUP-02, GROUPS-01, AUDIT-01]

# Metrics
duration: 4min
completed: 2026-03-15
---

# Phase 24 Plan 02: Keyring Password Handling Tests Summary

**Keyring resolution tests for setup_mcp_admin/update_mcp_admin_groups plus schema audit guard preventing any tool from requiring password**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-15T19:27:17Z
- **Completed:** 2026-03-15T19:30:51Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Updated all 4 existing setup_mcp_admin tests to mock resolve_ssh_credentials (prevents real keyring/DB access during tests)
- Added test_setup_remote_mcp_admin_uses_keyring: verifies keyring auto-inject path when no password passed
- Added test_update_mcp_admin_groups_uses_keyring: verifies keyring auto-inject path for groups tool
- Added 3 schema regression guard tests: two per-tool guards plus full 57-tool audit preventing any tool requiring password

## Task Commits

Each task was committed atomically:

1. **Task 1: Update existing tests and add keyring resolution tests** - `697574f` (feat)
2. **Task 2: Add schema regression guard tests** - `be18439` (feat)

## Files Created/Modified
- `tests/test_ssh_tools.py` - Added SSHCredentials/update_mcp_admin_groups imports, mocked resolve_ssh_credentials in 4 existing tests, added 2 new keyring tests
- `tests/test_tools.py` - Added 3 schema regression guard tests

## Decisions Made
- Used `force_update_key=False` in `test_setup_remote_mcp_admin_uses_keyring` to keep the mock sequence minimal (5 commands). The default `force_update_key=True` with an already-existing key requires 9 mock responses, which is unrelated to what this test exercises (keyring resolution).
- Added `updated_groups_result` mock to `test_update_mcp_admin_groups_uses_keyring` because `update_mcp_admin_groups` calls `groups mcp_admin` twice: once to get current groups and once after updates.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mock count in test_setup_remote_mcp_admin_uses_keyring**
- **Found during:** Task 1 (verification)
- **Issue:** Plan specified 4 mock responses but the function needs 5 commands when `force_update_key=False` (user_check, sudo_group, key_check, sudoers_setup, test_conn)
- **Fix:** Added `sudoers_setup` mock and used `force_update_key=False` to match the 5-command path
- **Files modified:** tests/test_ssh_tools.py
- **Verification:** All 20 test_ssh_tools tests pass
- **Committed in:** 697574f (Task 1 commit)

**2. [Rule 1 - Bug] Fixed mock count in test_update_mcp_admin_groups_uses_keyring**
- **Found during:** Task 1 (verification)
- **Issue:** Plan specified 6 mock responses but function calls `groups mcp_admin` twice (7 total)
- **Fix:** Added `updated_groups_result` mock for the final groups query
- **Files modified:** tests/test_ssh_tools.py
- **Verification:** All 20 test_ssh_tools tests pass
- **Committed in:** 697574f (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (Rule 1 - mock count mismatches)
**Impact on plan:** Both fixes necessary for test correctness. No scope creep.

## Issues Encountered
None beyond the mock count mismatches documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 24 complete: keyring credential resolution fully tested
- Schema audit guard in place — future tool additions will fail CI if password is added to required array
- All 661+ unit tests passing

---
*Phase: 24-keyring-password-handling*
*Completed: 2026-03-15*
