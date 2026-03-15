---
phase: 21-core-ssh-reliability
plan: "01"
subsystem: ssh
tags: [ssh, tofu, threading, known_hosts, asyncssh]

# Dependency graph
requires: []
provides:
  - TOFU known_hosts entries limited to exactly 3 fields (hostname algorithm base64) — comment stripped
  - threading.Lock protecting _store_host_key file writes against concurrent TOFU races
  - asyncio import removed from ssh_connection.py (unused after lock change)
affects:
  - 21-core-ssh-reliability (plan 02, 03 — both depend on ssh_connection reliability)
  - Any future phase using TOFUSSHClient or known_hosts file format

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD RED-then-GREEN: failing tests committed before implementation, both committed atomically per task"
    - "threading.Lock for synchronous callbacks: asyncio.Lock is dead code in synchronous validate_host_public_key callbacks"

key-files:
  created: []
  modified:
    - src/homelab_mcp/ssh_connection.py
    - tests/test_ssh_connection.py

key-decisions:
  - "Use threading.Lock not asyncio.Lock — validate_host_public_key is a synchronous callback, asyncio.Lock cannot be acquired there"
  - "Strip comment by splitting export_public_key output and joining only parts[:2] — known_hosts format requires exactly algorithm + base64"
  - "Wrap entire file write in with _tofu_lock: context manager — prevents duplicate entries from concurrent TOFU on first connection"

patterns-established:
  - "Known_hosts entries: always strip trailing comment field from export_public_key before writing"
  - "TOFU lock: use threading.Lock for synchronous SSH callback protection"

requirements-completed: [TOFU-01, TOFU-02]

# Metrics
duration: 3min
completed: 2026-03-15
---

# Phase 21 Plan 01: Core SSH Reliability — TOFU Key Format and Threading Lock Summary

**Fixed known_hosts corruption (comment field leaked into entries) and dead asyncio.Lock replaced with threading.Lock in TOFUSSHClient._store_host_key**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-15T17:49:53Z
- **Completed:** 2026-03-15T17:53:30Z
- **Tasks:** 2 (RED + GREEN, TDD)
- **Files modified:** 2

## Accomplishments

- Identified and fixed known_hosts corruption: `export_public_key()` returns `"algorithm base64 user@host"` (3 parts), but known_hosts requires exactly `"hostname algorithm base64"` — the comment `user@host` was leaking into the file causing SSH verification to fail on subsequent connections
- Replaced dead `asyncio.Lock()` with `threading.Lock()` — `validate_host_public_key` is a synchronous callback; `asyncio.Lock` can never be acquired from a sync context, making the original lock completely ineffective
- All 638 non-integration tests pass (10 in test_ssh_connection.py including 3 new)

## Task Commits

Each task was committed atomically:

1. **Task 1: RED tests for TOFU-01 and TOFU-02** - `70517d1` (test)
2. **Task 2: GREEN — Fix ssh_connection.py** - `9264698` (fix)

_Note: TDD tasks have two commits (test RED → fix GREEN)_

## Files Created/Modified

- `src/homelab_mcp/ssh_connection.py` — Removed `asyncio` import, added `threading`; replaced `asyncio.Lock()` with `threading.Lock()`; added comment-stripping logic in `_store_host_key`; wrapped file write in `with _tofu_lock:`
- `tests/test_ssh_connection.py` — Added `mock_ssh_key_with_comment` fixture, `TestTOFUKeyFormat` class, `TestTOFULock` class with 3 new tests

## Decisions Made

- Used `threading.Lock` because `validate_host_public_key` is called synchronously by asyncssh during connection establishment — no event loop is running in that callback context
- Stripped comment by splitting on whitespace and joining only `parts[:2]` — simple and correct regardless of comment content
- Kept `asyncio` removed since `ssh_connect` is `async def` but doesn't use the `asyncio` module directly (only `await asyncssh.connect(...)`)

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

A stash pop during verification temporarily introduced uncommitted changes from plan 21-02's RED tests (test_shell_session.py, test_http_app.py). These were restored to HEAD state before final verification. The `test_shell_session.py::TestShellSessionTermSize` RED test is pre-committed from plan 21-02 — expected to fail until that plan's GREEN phase runs.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 21-01 complete: TOFU key storage is now correct and thread-safe
- Ready for plan 21-02: shell session terminal size and non-blocking read fixes
- No blockers introduced

## Self-Check: PASSED

All files and commits verified present.

---
*Phase: 21-core-ssh-reliability*
*Completed: 2026-03-15*
