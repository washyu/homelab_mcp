---
phase: 23-workflow-completeness
plan: "02"
subsystem: auth
tags: [ssh, credentials, keyring, logging, warning, desync]

# Dependency graph
requires:
  - phase: 22-agent-guidance
    provides: CredentialNotFoundError, keyring credential injection (INJECT-01), list_credentials/get_credential module-level imports
provides:
  - Desync warning log in resolve_ssh_credentials when registry entry exists but keyring returns None
  - test_desync_warning_logged proving warning is emitted with hostname and username
affects: [future phases touching resolve_ssh_credentials, credential diagnostics tooling]

# Tech tracking
tech-stack:
  added: []
  patterns: [TDD RED-then-GREEN for warning log assertions, caplog.at_level for logger-scoped log capture]

key-files:
  created: []
  modified:
    - src/homelab_mcp/ssh_tools.py
    - tests/test_ssh_credentials.py

key-decisions:
  - "Warning placed inside if matched block after if keyring_password block — fires only on desync, never on normal keyring hit or total miss"
  - "Warning is non-blocking — control falls through to DB tier after the warning"
  - "caplog.at_level scoped to 'homelab_mcp.ssh_tools' logger to avoid noise from other loggers"

patterns-established:
  - "Desync detection pattern: registry match + falsy keyring result = WARNING with hostname, username, and CLI fix command"

requirements-completed: [TOFU-04]

# Metrics
duration: 1min
completed: 2026-03-15
---

# Phase 23 Plan 02: Credential Desync Warning Summary

**WARNING log added to resolve_ssh_credentials when credential registry has a host entry but OS keyring returns None, including hostname, username, and CLI remediation command**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-15T18:48:54Z
- **Completed:** 2026-03-15T18:50:21Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `logger.warning` in `resolve_ssh_credentials` at the desync path (registry entry exists, keyring returns None)
- Warning includes hostname, username, and the exact `homelab-mcp credentials add` CLI command to restore
- Warning is non-blocking — credential resolution continues to DB tier fallthrough
- TDD RED-then-GREEN: failing test committed first, implementation brings it GREEN with full suite passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Write RED test for desync warning** - `e390ea7` (test)
2. **Task 2: Implement desync warning and go GREEN** - `d87de4d` (feat)

**Plan metadata:** (docs commit follows)

_Note: TDD tasks have two commits (test RED → feat GREEN)_

## Files Created/Modified

- `src/homelab_mcp/ssh_tools.py` - Added `logger.warning(...)` call in desync path inside `if matched:` block
- `tests/test_ssh_credentials.py` - Added `import logging` and `test_desync_warning_logged` method to `TestCredentialNotFoundError`

## Decisions Made

- Warning placed inside `if matched:` block, after `if keyring_password:` return — executes only on desync, not on normal keyring hit or total miss
- Warning is non-blocking: code falls through to DB tier unchanged after the warning
- `caplog.at_level` scoped to `homelab_mcp.ssh_tools` logger for precise log capture in tests

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- TOFU-04 requirement satisfied: operators now see a WARNING in server logs when credential store is out of sync
- Warning includes actionable CLI fix command (`homelab-mcp credentials add <hostname> <username>`)
- Ready for any follow-on phases in 23-workflow-completeness

---
*Phase: 23-workflow-completeness*
*Completed: 2026-03-15*
