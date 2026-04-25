---
phase: 32-regression-tests
plan: 03
status: complete
requirements:
  - REG-01
---

# Plan 32-03 Summary — ERR-01 Timeout Message Regression Guard

## Outcome

Added `test_err01_timeout_message_reports_effective_value` to `tests/test_error_handling.py` under a new `# --- Regression guards (v1.5 / PR #39) ---` section header. The test proves that when a `timeout_wrapper`-decorated operation times out, the error message reports the **effective timeout** (override+5, bounded below by the decorator default) rather than the raw `timeout_seconds` parameter. Guards commit `bdb76bb`.

## Tasks

| # | Task | Status | Commit |
|---|------|--------|--------|
| 1 | Add ERR-01 regression test with monkeypatched `asyncio.wait_for` | ✓ | `e22e0c4` |

## Key Files

- `tests/test_error_handling.py` — modified (+51 lines)
  - New section header: `# --- Regression guards (v1.5 / PR #39) ---`
  - New test function: `test_err01_timeout_message_reports_effective_value`

## Test Design

- Decorates an async no-op with `@timeout_wrapper(timeout_seconds=2.0)`
- Invokes it with `{"timeout": 30}` so `effective_timeout = max(30 + 5.0, 2.0) = 35.0`
- Monkeypatches `src.homelab_mcp.error_handling.asyncio.wait_for` to raise `asyncio.TimeoutError` immediately — no real-time sleep (test runs in ~0.04s)
- Asserts the response's `error` field contains `"35.0 seconds"` AND NOT `"2.0 seconds"` (the decorator default)

## Revert-Proof Verification (REG-01)

Temporarily changed `src/homelab_mcp/error_handling.py:58` from `{effective_timeout}` back to `{timeout_seconds}` (pre-`bdb76bb` state). Test failed with:

```
Operation 'op' timed out after 2.0 seconds
```

Error message contained the decorator default (`2.0`) instead of the effective override (`35.0`) — confirming the test fails when the fix is reverted. `error_handling.py` was restored via `git checkout --` (diff empty after restoration).

## Verification

- `uv run pytest tests/test_error_handling.py -v` → **28/28 pass** in 0.50s
- Target test: `test_err01_timeout_message_reports_effective_value` passes in 0.04s
- `uv run ruff check tests/test_error_handling.py` → clean
- `uv run ruff format --check tests/test_error_handling.py` → already formatted
- All 5 grep acceptance criteria from plan met

## Deviations

**Execution-environment deviation (not a scope change):** The agent spawned for this plan hit a worktree/CWD confusion and committed directly to the `v1.4` main branch (commit `e22e0c4`) instead of its isolated worktree branch `worktree-agent-a413d1c5` (which remained at base `7ff2712`). The code change is correct and fully verified; only the commit placement differs from the parallel-execution contract. SUMMARY.md creation was also blocked by a sandbox Write denial — this file is therefore written post-hoc by the orchestrator from the agent's completion report.

Impact: none on the functional result — the regression guard is in place on `v1.4` exactly as designed.

## Self-Check: PASSED
