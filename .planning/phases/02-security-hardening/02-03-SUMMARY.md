---
phase: 02-security-hardening
plan: 03
subsystem: ssh
tags: [asyncssh, tofu, host-key-verification, ssh, security]

# Dependency graph
requires:
  - phase: 01-architecture-foundation
    provides: ResourceManager centralizes where security policies are enforced
provides:
  - Centralized ssh_connect() helper with TOFU host key verification
  - TOFUSSHClient for asyncssh with file-based known_hosts
  - KNOWN_HOSTS_PATH constant for SSH host key storage
affects: [03-functional-completeness, 04-protocol-compliance]

# Tech tracking
tech-stack:
  added: []
  patterns: [TOFU host key verification, centralized SSH connection helper]

key-files:
  created:
    - src/homelab_mcp/ssh_connection.py
    - tests/test_ssh_connection.py
  modified:
    - src/homelab_mcp/ssh_tools.py
    - src/homelab_mcp/vm_operations.py
    - src/homelab_mcp/infrastructure_crud.py
    - src/homelab_mcp/shell_session.py
    - tests/test_ssh_tools.py
    - tests/test_vm_operations.py
    - tests/test_infrastructure_crud.py

key-decisions:
  - "validate_host_public_key is synchronous (not async) since asyncssh calls it in a sync context"
  - "Known hosts file at ~/.homelab_mcp/known_hosts alongside existing DB, not ~/.ssh/known_hosts"
  - "Non-standard ports use [host]:port format per OpenSSH convention"

patterns-established:
  - "All SSH connections via ssh_connect() from ssh_connection module"
  - "TOFU pattern: accept-and-store on first connect, reject on key change"

requirements-completed: [SEC-01]

# Metrics
duration: 10min
completed: 2026-03-09
---

# Phase 2 Plan 3: SSH Host Key Verification Summary

**TOFU SSH host key verification via centralized ssh_connect() helper replacing 21 insecure asyncssh.connect(known_hosts=None) calls**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-09T15:28:11Z
- **Completed:** 2026-03-09T15:38:28Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- Created ssh_connection.py with TOFUSSHClient implementing trust-on-first-use host key verification
- Replaced all 21 asyncssh.connect(known_hosts=None) calls across 4 source files with ssh_connect()
- Zero known_hosts=None remaining in production code; all connections go through centralized helper
- Updated all test mocks across 3 test files; full suite passes (423 tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create ssh_connection.py with TOFU and tests** (TDD)
   - `df82aa2` test(02-03): add failing tests for TOFU SSH host key verification
   - `2ed2c84` feat(02-03): implement TOFU SSH host key verification module
2. **Task 2: Replace all asyncssh.connect(known_hosts=None) calls** - `c1b646c` (feat)

## Files Created/Modified
- `src/homelab_mcp/ssh_connection.py` - Centralized SSH connect helper with TOFU host key verification
- `tests/test_ssh_connection.py` - Unit tests for TOFU behavior (7 tests)
- `src/homelab_mcp/ssh_tools.py` - 6 call sites replaced with ssh_connect()
- `src/homelab_mcp/vm_operations.py` - 6 call sites replaced with ssh_connect()
- `src/homelab_mcp/infrastructure_crud.py` - 8 call sites replaced with ssh_connect()
- `src/homelab_mcp/shell_session.py` - 1 call site replaced with ssh_connect()
- `tests/test_ssh_tools.py` - Updated mocks to patch ssh_connect instead of asyncssh.connect
- `tests/test_vm_operations.py` - Updated mocks to patch ssh_connect
- `tests/test_infrastructure_crud.py` - Updated mocks to patch ssh_connect

## Decisions Made
- validate_host_public_key is synchronous (asyncssh calls it in a sync context from its event loop)
- Known hosts stored at ~/.homelab_mcp/known_hosts alongside existing homelab database
- Non-standard ports use [host]:port format per OpenSSH convention for known_hosts entries

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed unused import and import ordering in shell_session.py**
- **Found during:** Task 2 (replacing asyncssh.connect calls)
- **Issue:** Removing connect_kwargs dict left `typing.Any` unused; import ordering violated ruff rules
- **Fix:** Removed unused import, reordered imports
- **Files modified:** src/homelab_mcp/shell_session.py
- **Verification:** ruff check passes
- **Committed in:** c1b646c (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Trivial cleanup. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- SSH host key verification complete (SEC-01)
- Phase 2 security hardening foundation established
- Ready for Phase 3 functional completeness work

---
*Phase: 02-security-hardening*
*Completed: 2026-03-09*
