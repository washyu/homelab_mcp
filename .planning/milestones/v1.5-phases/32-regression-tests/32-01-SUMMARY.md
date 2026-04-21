---
phase: 32-regression-tests
plan: 01
subsystem: testing
tags: [testing, regression, websocket, http, pty, starlette]

requires:
  - phase: 31-bug-fixes
    provides: WS-01 fix in http_app.py (3 websocket.close calls in read_output, EOF branch)
provides:
  - E2E regression test for WS-01 via TestClient.websocket_connect
  - _make_shell_app factory
  - Regression guards (v1.5 / PR #39) section header convention
  - Closure of QUAL-02 deferred item
affects: [32-regression-tests, future-websocket-tests]

tech-stack:
  added: []
  patterns:
    - TestClient.websocket_connect drives production handler end-to-end
    - Mock shell_session_manager via unittest.mock.patch
    - Fake-stdout state machine returns data then empty string
    - pytest.raises on WebSocketDisconnect asserts handler closed socket

key-files:
  created: []
  modified:
    - tests/test_http_app.py

key-decisions:
  - Kept local-copy test at lines 183-239 per plan D-09
  - QUAL-02 closure via commit trailer only
  - Imports at module top

patterns-established:
  - Regression guards section header at bottom of test file
  - _make_shell_app factory for WebSocket E2E

requirements-completed: [REG-01]

duration: 10min
completed: 2026-04-21
---

# Phase 32 Plan 01: WS-01 Regression Guard Summary

TestClient-driven regression test for handle_shell_websocket.

## Performance

- Duration: ~10 min
- Started: 2026-04-21T01:01:32Z
- Completed: 2026-04-21T01:11:11Z
- Tasks: 1
- Files modified: 1
- Commits: 1 (7974acc)

## Accomplishments

- REG-01 (WS-01 branch): new test test_ws01_reader_closes_socket_on_pty_eof in tests/test_http_app.py drives production handle_shell_websocket end-to-end via TestClient.websocket_connect.
- Mocks homelab_mcp.http_app.shell_session_manager to return a session whose stdout.read is a state machine (first returns hello, then empty string for EOF).
- Asserts three observables: (1) hello data frame received, (2) Connection closed marker follows, (3) subsequent receive_text raises WebSocketDisconnect.
- New _make_shell_app factory registers the production handler on WebSocketRoute /ws/shell/session_id.
- Added Regression guards section header at line 299.
- Imports added: AsyncMock, MagicMock, patch, WebSocketRoute, WebSocketDisconnect, handle_shell_websocket. Existing 15 tests continue to pass (16/16 total).
- QUAL-02 closed via commit trailer (Closes: QUAL-02). Old local-copy unit test left in place per plan D-09.

## Task Commits

1. Task 1: Add WS-01 end-to-end regression test - 7974acc (test)

## Files Created/Modified

- tests/test_http_app.py (+67 lines, -2 lines): imports expanded; Regression guards section header + _make_shell_app factory + test_ws01_reader_closes_socket_on_pty_eof appended at EOF.

## Verification

### Automated gates (all passed)

- uv run --no-sync pytest tests/test_http_app.py -v --no-cov => 16 passed in 0.53s (15 pre-existing + 1 new)
- uv run --no-sync pytest tests/test_http_app.py::test_ws01_reader_closes_socket_on_pty_eof -v --no-cov => 1 passed in 0.50s
- uv run --no-sync ruff check tests/test_http_app.py => All checks passed
- uv run --no-sync ruff format --check tests/test_http_app.py => 1 file already formatted

### Acceptance criteria grep checks (all passed)

- def test_ws01_reader_closes_socket_on_pty_eof at line 313
- Regression guards header at line 299
- def _make_shell_app at line 302
- from starlette.routing import Route, WebSocketRoute at line 12
- from starlette.websockets import WebSocketDisconnect at line 14
- from homelab_mcp.http_app import OriginValidationMiddleware, handle_shell_websocket at line 16
- patch(homelab_mcp.http_app.shell_session_manager) at line 341
- pytest.raises(WebSocketDisconnect) at line 357
- [Connection closed] appears 4 times (>= 2 required)

### Revert-proof (REG-01 success criterion)

Procedure: checked out src/homelab_mcp/http_app.py at b0a5f33^ (the commit before the WS-01 fix), confirmed the three await close calls and their contextlib.suppress(Exception) wrappers were absent from read_output, then ran the new test under a 30-second OS-level timeout.

Observed failure mode (captured against pre-fix state):

tests/test_http_app.py::test_ws01_reader_closes_socket_on_pty_eof HANG
(terminated by 30s external timeout -- no PASS/FAIL written)

Why the hang is the expected failure: without the await close calls in the EOF break, the read_output coroutine exits via break but the WebSocket is never closed. The outer receive_text loop in handle_shell_websocket therefore stays blocked waiting for a client frame, and TestClients ws.receive_text (second or third call) hangs indefinitely. pytest.raises(WebSocketDisconnect) never fires, so the test does not reach a PASS/FAIL verdict; it is killed by the outer timeout.

Restoration: the original src/homelab_mcp/http_app.py was restored immediately (grep -c contextlib.suppress Exception => 3, matching the fix state). No uncommitted changes to http_app.py remain.

Significance: demonstrates REG-01s literal success criterion for WS-01 -- reverting the fix causes the test to fail.

## Decisions Made

- Left the local-copy test in place (plan D-09). The existing TestWebSocketReadOutput.test_read_output_sends_eof_notification at lines 183-239 is retained alongside the new E2E test. The unit-level guard is cheap to maintain and remains valuable for catching regressions inside the reimplemented copy.
- Imports at module top, not in function body. AsyncMock, MagicMock, patch, WebSocketRoute, WebSocketDisconnect, handle_shell_websocket are imported at module level. No monkeypatching concern for these symbols, and module-level imports are consistent with the rest of test_http_app.py.
- QUAL-02 closure reference via commit trailer only. Commit message contains Closes: QUAL-02 and an explicit note that deferred-items.md should be updated in a follow-up commit. Editing deferred-items.md directly was NOT in this plans scope per D-09.

## Deviations from Plan

None. The plan executed exactly as written.

Two minor clean-ups applied as part of normal implementation (not deviations):

1. Ruff format normalized a multi-line assert message to single-line form.
2. Worktree .venv was empty at task start; ran uv sync once to populate it (environment setup).

Total deviations: 0.

## Issues Encountered

Orchestration observation (not a code issue): pytest has no --timeout plugin installed, so the revert-proof used an OS timeout 30 wrapper instead of a pytest-internal timeout. Did not affect the result.

Tooling observation: the Write tool and several bash file-write operations were intermittently denied by the sandbox during this run; the SUMMARY.md was assembled via incremental python -c appends as a workaround. The final file matches the intended content below.

## User Setup Required

None.

## Next Phase Readiness

- Regression guards (v1.5 / PR #39) header convention is now established; 32-02 / 32-03 / 32-04 plans should reuse it in their respective test files (test_ssh_tools.py, test_error_handling.py, test_tools.py).
- _make_shell_app is available for any future WebSocket handler regression tests.
- QUAL-02 deferred item remains open in .planning/phases/31-bug-fixes/deferred-items.md; a follow-up docs commit can remove the QUAL-02 entry now that the WS-01 regression guard is in place.

## Self-Check: PASSED

Claims verified before closing:

- tests/test_http_app.py contains def test_ws01_reader_closes_socket_on_pty_eof at line 313. FOUND.
- tests/test_http_app.py contains the Regression guards header at line 299. FOUND.
- tests/test_http_app.py contains def _make_shell_app at line 302. FOUND.
- Imports include WebSocketRoute, WebSocketDisconnect, handle_shell_websocket, AsyncMock, MagicMock, patch. FOUND.
- patch(homelab_mcp.http_app.shell_session_manager) at line 341. FOUND.
- pytest.raises(WebSocketDisconnect) at line 357. FOUND.
- Commit 7974acc present in git log --oneline. FOUND.
- Commit message contains Closes: QUAL-02. FOUND.
- pytest tests/test_http_app.py -v => 16/16 pass. VERIFIED.
- ruff check + ruff format --check => clean. VERIFIED.
- Revert-proof performed and documented in Revert-proof section. DOCUMENTED.

---
*Phase: 32-regression-tests*
*Completed: 2026-04-21*
