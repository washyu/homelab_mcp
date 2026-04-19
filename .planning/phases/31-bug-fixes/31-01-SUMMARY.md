---
phase: 31-bug-fixes
plan: 01
subsystem: testing
tags: [error-handling, json-schema, pytest, asyncio, mcp-tools, coderabbit]

# Dependency graph
requires:
  - phase: PR #39 CodeRabbit review
    provides: Identified bug locations (ERR-01, SSH-02, SCH-01)
provides:
  - Corrected timeout error message reporting the computed effective_timeout value
  - JSON Schema enum constraint on list_keyring_credentials credential_type parameter
  - Non-disjunctive password-propagation test assertion that actually fails on regression
affects: [31-bug-fixes/31-02 (websocket zombie fix — independent), future phase that touches error_handling.py timeout messages, future phase adding credential types beyond ssh/proxmox]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Report computed/derived values in error messages, not raw decorator parameters"
    - "JSON Schema enum keyword for fixed-choice string parameters in MCP tool schemas"
    - "Non-disjunctive assertions when one operand is structurally always-true"

key-files:
  created:
    - ".planning/phases/31-bug-fixes/31-01-SUMMARY.md"
    - ".planning/phases/31-bug-fixes/deferred-items.md"
  modified:
    - "src/homelab_mcp/error_handling.py"
    - "src/homelab_mcp/tool_schemas/credential_tools_schema.py"
    - "tests/test_ssh_tools.py"

key-decisions:
  - "Applied minimal one-line fix for ERR-01 (effective_timeout substitution) — no additional regression test added this plan; existing tests already green"
  - "Applied minimal one-line fix for SCH-01 (enum addition) — no schema-validation regression test added; existing schema tests remain green"
  - "Applied single-assertion replacement for SSH-02 — chose option A (keep just 'No credentials' assertion) because production error message reliably contains that prefix and the test mocks the DB adapter to guarantee the no-credentials path"

patterns-established:
  - "Report effective (possibly overridden) values in error messages: callers need to know what was actually enforced, not the default"
  - "Always use `enum` in JSON Schema when string property has a closed set of valid values — MCP framework validates at call-edge before handler runs"
  - "Assertion hygiene: `A or B` where B is structurally always-true hides failures in A — use a single assertion on the discriminating substring"

requirements-completed: [ERR-01, SSH-02, SCH-01]

# Metrics
duration: 2min
completed: 2026-04-19
---

# Phase 31 Plan 01: CodeRabbit PR #39 Bug Triad Summary

**Three-line surgical fix for CodeRabbit PR #39 findings: timeout message now reports effective_timeout, credential_type schema now enum-constrained to ["ssh","proxmox"], and password-propagation test assertion is no longer trivially-true.**

## Performance

- **Duration:** ~2 min (109 s)
- **Started:** 2026-04-19T20:39:36Z
- **Completed:** 2026-04-19T20:41:25Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- **ERR-01 fixed:** `error_handling.py` timeout_wrapper now reports `effective_timeout` in its f-string error message, so callers that pass a dict-arg timeout override see the value that was actually enforced (not the decorator default). This materially changes the error message under override — previously misleading.
- **SCH-01 fixed:** `list_keyring_credentials` inputSchema gains `"enum": ["ssh", "proxmox"]` on `credential_type`, pushing validation from handler code to the MCP framework edge. Arbitrary strings are rejected before reaching Python.
- **SSH-02 fixed:** `test_ssh_discover_no_credentials` assertion at line 191 replaced the `"A in err or B in err"` form (where B was structurally always-true) with a single non-disjunctive check on `"No credentials"`. The test will now correctly fail if the production error message drops the `"No credentials"` prefix.

## Task Commits

Each task committed atomically:

1. **Task 1: ERR-01 + SCH-01 (error message + enum)** — `bdb76bb` (fix)
2. **Task 2: SSH-02 (assertion fix)** — `d25c915` (fix)

_Note:_ Commit `b0a5f33` (fix(31-02): close websocket on EOF and error paths) interleaved between my two commits on the same branch. It is a sibling plan's work, not part of 31-01; listed here only to explain the git log ordering.

## Files Created/Modified

- `src/homelab_mcp/error_handling.py` — Line 58 in `timeout_wrapper.wrapper`: replaced `{timeout_seconds}` with `{effective_timeout}` in the timeout error message f-string.
- `src/homelab_mcp/tool_schemas/credential_tools_schema.py` — `list_keyring_credentials` inputSchema, `credential_type` property: added `"enum": ["ssh", "proxmox"]`.
- `tests/test_ssh_tools.py` — Line 191 in `test_ssh_discover_no_credentials`: replaced disjunctive assertion with `assert "No credentials" in result_data["error"]`.
- `.planning/phases/31-bug-fixes/deferred-items.md` — New; logs pre-existing out-of-scope breakage (`SSHCompletedProcess[str]` subscript error at ssh_tools.py:656 owned by sibling SSH-01 plan).

## Decisions Made

- **ERR-01 regression test not added this plan** — the plan explicitly scopes to the one-line substitution and the existing `test_error_handling.py` suite (27 tests) stays green. The override-path regression test (mentioned in 31-RESEARCH.md as a Wave 0 gap) belongs to a follow-up test-hardening plan or the phase-level validation plan.
- **SCH-01 regression test not added this plan** — same rationale; plan scope is the schema edit. `test_tools.py` (36 tests) verifies tool registry structure and stays green.
- **SSH-02 chose plain assertion over two-assertion replacement** — the research doc listed two options; the simpler `assert "No credentials" in result_data["error"]` is sufficient because the preceding `assert result_data["status"] == "error"` at line 189 already guarantees the error path was taken.

## Deviations from Plan

None — plan executed exactly as written. All three fixes are byte-for-byte the substitutions specified in the task `<action>` blocks. Pre-commit hooks (ruff/mypy) passed on both commits without reformatting.

## Issues Encountered

### Out-of-scope pre-existing breakage (logged, not fixed)

Running the broader `uv run --no-sync pytest tests/ -m "not integration"` suite surfaces a collection-time `TypeError: type 'SSHCompletedProcess' is not subscriptable` at `src/homelab_mcp/ssh_tools.py:656`. This `_sudo_run` helper is owned by a sibling SSH-01 plan and predates 31-01 execution — it was committed before this plan started. It does not affect the three verification test files (`test_error_handling.py`, `test_ssh_tools.py`, `test_tools.py`), which all pass cleanly in isolation (84/84 green).

Per GSD scope-boundary rules, this is logged to `.planning/phases/31-bug-fixes/deferred-items.md` for the phase owner and explicitly NOT fixed from this plan.

Two pre-existing dev-only failures (`test_packaging.py::test_version_unified`, `test_proxmox_api.py::TestGetProxmoxClient::test_client_missing_host`) are expected per the execution prompt and were not run.

## User Setup Required

None — all changes are code-only, no external service configuration needed.

## Verification

**Task-level:**
- `uv run --no-sync pytest tests/test_error_handling.py tests/test_tools.py --no-cov -x -q` — 63 passed
- `uv run --no-sync pytest tests/test_ssh_tools.py::test_ssh_discover_no_credentials --no-cov -x -v` — 1 passed
- Combined: `uv run --no-sync pytest tests/test_error_handling.py tests/test_ssh_tools.py tests/test_tools.py --no-cov -q` — **84 passed in 1.08s**

**Grep-level (per plan `<verification>`):**
- `grep "effective_timeout" src/homelab_mcp/error_handling.py` — shows corrected variable in error message (confirmed at line 58)
- `grep "enum" src/homelab_mcp/tool_schemas/credential_tools_schema.py` — shows enum constraint at line 130
- `grep "No credentials" tests/test_ssh_tools.py` — shows assertion without the `or` branch at line 191

## Next Phase Readiness

- PR #39 CodeRabbit findings ERR-01, SSH-02, SCH-01 are closed.
- Sibling 31-02 plan (WS-01 websocket zombie fix) is independently complete per its own commit (`b0a5f33`).
- Phase 31 remaining scope: SSH-01 (`_sudo_run check=True` propagation). The `_sudo_run` helper function exists but has a broken type annotation (`SSHCompletedProcess[str]`) — this is the deferred item that the SSH-01 plan owner should address when they run their fix.
- No blockers for Phase 31 completion verification. Recommend the phase verifier fix the `_sudo_run` annotation (drop the `[str]` subscript) as part of SSH-01 so the full non-integration suite becomes collectable again.

## Self-Check: PASSED

Verified post-write:
- `src/homelab_mcp/error_handling.py` — exists, line 58 contains `effective_timeout` (not `timeout_seconds`)
- `src/homelab_mcp/tool_schemas/credential_tools_schema.py` — exists, line 130 contains `"enum": ["ssh", "proxmox"]`
- `tests/test_ssh_tools.py` — exists, line 191 contains `assert "No credentials" in result_data["error"]` with no `or` branch
- Commit `bdb76bb` — exists in git log on branch v1.4
- Commit `d25c915` — exists in git log on branch v1.4
- `.planning/phases/31-bug-fixes/deferred-items.md` — exists
- All 84 tests across the three verification files pass

---
*Phase: 31-bug-fixes*
*Completed: 2026-04-19*
