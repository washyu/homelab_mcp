---
phase: 31-bug-fixes
plan: 02
subsystem: infra
tags: [websocket, asyncssh, starlette, pty, sudo]

requires:
  - phase: 30-initial-v1.4
    provides: http_app.py WebSocket PTY handler; ssh_tools.py ssh_execute_command
provides:
  - WebSocket PTY handler closes the socket on EOF and error paths, preventing zombie sessions
  - _sudo_run helper in ssh_tools.py with consistent check= semantics across both sudo auth paths
affects: [31-bug-fixes, future-callers-of-ssh_execute_command, shell-pty-sessions]

tech-stack:
  added: []
  patterns:
    - "contextlib.suppress(Exception) around websocket.close() for idempotent cleanup"
    - "Extracted _sudo_run helper: single code path, both auth branches forward check="
    - "Quoted return type annotation to defer evaluation when third-party class is non-subscriptable at runtime"

key-files:
  created: []
  modified:
    - src/homelab_mcp/http_app.py
    - src/homelab_mcp/ssh_tools.py

key-decisions:
  - "Used contextlib.suppress(Exception) around websocket.close() rather than try/except — cleaner idiom, already matches module's existing contextlib usage"
  - "Quoted _sudo_run return annotation as 'asyncssh.SSHCompletedProcess' — the class is not subscriptable at runtime and mypy stubs have no generic support; quoting defers evaluation safely"
  - "Preserved check=False behavior for existing ssh_execute_command callers — no behavior change, only opens the door for future callers who need check=True"

patterns-established:
  - "read_output coroutines close the websocket themselves on EOF/error so the outer receive_text() loop raises WebSocketDisconnect and the finally block runs"
  - "Sudo command construction lives in a single helper (_sudo_run) — both password and no-password auth paths share the same execution line and check= forwarding"

requirements-completed: [WS-01, SSH-01]

duration: 9min
completed: 2026-04-19
---

# Phase 31 Plan 02: CodeRabbit Structural Bug Fixes Summary

**Closed the WebSocket PTY zombie-session leak on EOF/error and extracted a shared _sudo_run helper so both sudo auth paths honor check= consistently.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-04-19T20:32:00Z (approx)
- **Completed:** 2026-04-19T20:41:42Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- WS-01: `read_output` in `http_app.py` now calls `await websocket.close()` (wrapped in `contextlib.suppress(Exception)`) in all three break paths: EOF, no-stdout, and error. This triggers `WebSocketDisconnect` in the outer `receive_text()` loop, which lets the `finally` block cancel the paired `output_task`. No more zombie WebSocket sessions.
- SSH-01: New private async helper `_sudo_run(conn, command, password, check)` in `ssh_tools.py`. Both the password and no-password branches construct the full command and then call `conn.run(full_command, check=check)` on the same line, so `check=True` semantics are structurally identical. `ssh_execute_command` sudo branch delegates to this helper.
- All existing tests still pass (`tests/test_http_app.py` 15/15, `tests/test_ssh_tools.py` 21/21).

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix zombie WebSocket PTY sessions (WS-01)** - `b0a5f33` (fix)
2. **Task 2: Extract _sudo_run helper with check parameter (SSH-01)** - `9f752c0` (fix)

## Files Created/Modified
- `src/homelab_mcp/http_app.py` - `read_output()` closes the websocket on EOF, no-stdout, and error paths (3 new `await websocket.close()` calls, each wrapped in `contextlib.suppress(Exception)`)
- `src/homelab_mcp/ssh_tools.py` - Added `_sudo_run` helper (7 new lines for the function body); replaced 9 lines of inline sudo command construction in `ssh_execute_command` with 5 lines delegating to `_sudo_run`

## Decisions Made
- **Idiom for idempotent close:** Wrapped `await websocket.close()` in `with contextlib.suppress(Exception):` rather than `try/except Exception: pass`. The file already imports `contextlib` at module scope and uses it in `lifespan`, so this matches local style.
- **Return type annotation:** Initially wrote `-> asyncssh.SSHCompletedProcess[str]` per the plan. The class is not subscriptable at runtime in the installed asyncssh version, and mypy rejects the subscript on the stub. Resolution: quote the annotation and drop the `[str]` parameterization → `"asyncssh.SSHCompletedProcess"`. Both runtime and mypy accept this.
- **Preserve existing call behavior:** `ssh_execute_command` still passes `check=False` explicitly to `_sudo_run`. The helper simply makes `check=True` available for future callers without changing any current call path.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Return type annotation not evaluable at runtime/mypy**
- **Found during:** Task 2 (SSH-01)
- **Issue:** The plan specified `-> asyncssh.SSHCompletedProcess[str]`. At collection time this raised `TypeError: type 'SSHCompletedProcess' is not subscriptable`, blocking all test imports through the module-load chain. After quoting the annotation the import succeeded, but the mypy pre-commit hook then rejected the subscript with `"SSHCompletedProcess" expects no type arguments  [type-arg]`.
- **Fix:** Quoted the annotation and dropped the generic parameter → `"asyncssh.SSHCompletedProcess"`. This matches the plan's own Pitfall 4 guidance in `31-RESEARCH.md` and keeps the helper callable and type-checkable.
- **Files modified:** `src/homelab_mcp/ssh_tools.py`
- **Verification:** `uv run --no-sync pytest tests/test_http_app.py tests/test_ssh_tools.py --no-cov -q` → 36/36 pass; pre-commit mypy hook passes.
- **Committed in:** `9f752c0` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Deviation was purely a type-annotation mechanics issue — no behavioral change vs. the plan. All acceptance criteria still met (helper exists with the prescribed parameters, `check=check` is forwarded, password branch has `# nosec B608`, both sudo branches delegate to `_sudo_run`).

## Issues Encountered
None — both fixes were surgical and the verification tests (15 http_app + 21 ssh_tools) all pass.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- WS-01 and SSH-01 are resolved. The remaining CodeRabbit items from Phase 31 (ERR-01, SSH-02, SCH-01) are being handled by Plan 31-01 in parallel (different files, no overlap).
- `ssh_execute_command`'s public signature is unchanged; no downstream callers need updates. Future callers that want raise-on-failure sudo can now call `_sudo_run(..., check=True)` directly.

## Self-Check: PASSED
- `src/homelab_mcp/http_app.py` exists and contains 3 `await websocket.close()` calls inside `read_output` (lines 203, 207, 218), each wrapped in `contextlib.suppress(Exception)`. Verified.
- `src/homelab_mcp/ssh_tools.py` exists and contains `async def _sudo_run(` at line 651, with `return await conn.run(full_command, check=check)` at line 667, and `# nosec B608` annotation on the password f-string. Verified.
- Commits `b0a5f33` and `9f752c0` both present in `git log`. Verified.
- `uv run --no-sync pytest tests/test_http_app.py tests/test_ssh_tools.py --no-cov -q` → 36/36 pass. Verified.

---
*Phase: 31-bug-fixes*
*Completed: 2026-04-19*
