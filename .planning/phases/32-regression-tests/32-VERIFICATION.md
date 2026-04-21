---
phase: 32-regression-tests
verified: 2026-04-20T00:00:00Z
status: gaps_found
score: 4/5 must-haves verified
overrides_applied: 0
gaps:
  - truth: "A test verifies the password assertion in test_ssh_tools.py fails when password is not propagated — the test is not unconditionally passing (REG-01 SC #4)"
    status: partial
    reason: "The AST detector in test_ssh02_no_disjunctive_always_true_assertions catches simple literal tautologies (`assert X or \"literal\"`) but does NOT catch the exact mutation form that commit d25c915 fixed. The pre-fix d25c915 form `assert \"No credentials\" in err or \"other\" in err[\"error\"]` parses the RHS to `Compare(left=Constant, ops=[In()], comparators=[Subscript])`. The detector's Compare branch requires `all(isinstance(c, ast.Constant) for c in node.comparators)`, which is False for Subscript — so the mutation is silently ignored. Reintroducing the exact d25c915 defect would NOT trigger this regression test, violating the REG-01 contract. Confirmed empirically by running the detector logic against the reconstructed pre-fix source."
    artifacts:
      - path: "tests/test_ssh_tools.py"
        issue: "`_is_structurally_always_true` Compare branch at line ~1146-1149 only flags Compare nodes when all comparators are ast.Constant. For the `In` operator a Subscript, Attribute, Name, or Call comparator with a Constant left-hand literal is always a tautology (the LHS string is always 'in' a non-empty container being asserted elsewhere in the same disjunction). The d25c915 mutation form uses exactly this shape (Constant `in` Subscript)."
    missing:
      - "Extend `_is_structurally_always_true` to treat a Compare node as structurally always true when `isinstance(node.left, ast.Constant)` AND `node.ops[0]` is `ast.In`, regardless of the comparator type. This matches the actual d25c915 defect pattern."
      - "After extending, re-run the mutation experiment against the exact d25c915 pre-fix line (`assert \"No credentials\" in result_data[\"error\"] or \"other\" in result_data[\"error\"]`) and confirm the detector now flags it."
      - "Update the docstring / decision note to reflect the broadened Compare coverage so future reviewers understand why `In` + Constant LHS is special-cased."

deferred: []
---

# Phase 32: Regression Tests Verification Report

**Phase Goal:** All 5 fixed bugs have dedicated regression tests that will catch any recurrence before it ships
**Verified:** 2026-04-20
**Status:** gaps_found (1 partial of 5 success criteria)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | WebSocket PTY reader cancels its paired task and closes the socket on EOF — reverting the fix causes the test to fail | ✓ VERIFIED | `tests/test_http_app.py:313` — `test_ws01_reader_closes_socket_on_pty_eof`. Drives production `handle_shell_websocket` E2E via `TestClient.websocket_connect`. Asserts `[Connection closed]` frame emitted, then `pytest.raises(WebSocketDisconnect)` on next `receive_text()`. Revert-proof recorded in 32-01-SUMMARY.md: reverting b0a5f33 causes test to hang (external 30s timeout kill) — without the three `await websocket.close()` calls the client `receive_text` blocks forever. Test passes on HEAD (PASSED [ 20%] in 0.58s combined run). |
| 2 | Timeout error message contains the effective_timeout value — reverting the fix causes the test to fail | ✓ VERIFIED | `tests/test_error_handling.py:421` — `test_err01_timeout_message_reports_effective_value`. Uses `@timeout_wrapper(timeout_seconds=2.0)` + `{"timeout": 30}` override (effective 35.0s). Monkeypatches `src.homelab_mcp.error_handling.asyncio.wait_for` to raise TimeoutError immediately. Asserts `"35.0 seconds"` in error string AND `"2.0 seconds"` NOT in error string. Revert-proof in 32-03-SUMMARY.md: reverting bdb76bb line-58 variable rename produces `"Operation 'op' timed out after 2.0 seconds"` — assertion fails. Production `error_handling.py:58` confirmed still uses `{effective_timeout}`. Test passes on HEAD (PASSED [ 80%]). |
| 3 | `_sudo_run(check=True)` raises on non-zero exit in the password branch — reverting the fix causes the test to fail | ✓ VERIFIED | `tests/test_ssh_tools.py:1060` — `test_ssh01_sudo_run_check_raises_in_password_branch`. Calls `_sudo_run(mock_conn, "ls", password="pw", check=True)` with `mock_conn.run.side_effect = asyncssh.ProcessError(...)`. Asserts exception propagates AND `mock_conn.run.call_args.kwargs["check"] is True`. Production `ssh_tools.py:651-667` confirmed still calls `conn.run(full_command, check=check)` in the single return path (both branches share the `check=` forwarding). Revert-proof documented in commit `e50cda1` body. Test passes on HEAD (PASSED [ 40%]). |
| 4 | Password assertion in `test_ssh_tools.py` fails when password is not propagated — the test is not unconditionally passing | ✗ PARTIAL | `tests/test_ssh_tools.py:1107` — `test_ssh02_no_disjunctive_always_true_assertions`. AST meta-guard catches simple literal tautologies (`assert X or "literal"`, `assert X or True`, `assert X or 1`, `assert X or ("a" == "a")`) but NOT the exact d25c915 mutation form `assert "No credentials" in err or "other" in err["error"]`. Root cause: the RHS parses to `Compare(left=Constant("other"), ops=[In()], comparators=[Subscript(err, "error")])`, and the detector requires `all(isinstance(c, ast.Constant) for c in node.comparators)` — Subscript fails this check. Empirically confirmed by parsing the exact pre-fix string through the detector logic (result: `flagged? False`). Plan 32-02's SUMMARY.md self-reports this gap (see `flags: [detector_scope_gap]` in frontmatter). Additionally, the D-05 verbatim-FAILED-paste was blocked by sandbox restrictions — the commit body contains an analytical substitute rather than the verbatim failure output required by the plan. Test passes on HEAD against the conservative subset (PASSED [ 60%]), but does NOT close the REG-01 contract for the specific bug it is supposed to guard. |
| 5 | Credentials tool schema rejects non-enum credential_type values — reverting the fix causes the test to fail | ✓ VERIFIED | `tests/test_tools.py:878` — `test_sch01_credential_type_rejects_non_enum_values`. Asserts `prop["type"] == "string"`, exact list equality `prop["enum"] == ["ssh", "proxmox"]`, and `prop["default"] == "ssh"`. Production `credential_tools_schema.py:130` confirmed still carries `"enum": ["ssh", "proxmox"]`. Revert-proof in 32-04-SUMMARY.md and commit `f03e585` body: deleting the enum line reproduces `KeyError: 'enum'`. Test passes on HEAD (PASSED [100%]). |

**Score:** 4/5 truths fully verified; 1 partial.

### Deferred Items

None. The partial on SC #4 is an in-phase gap (detector scope bug), not a later-phase concern.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/test_http_app.py` | `test_ws01_reader_closes_socket_on_pty_eof` + `_make_shell_app` factory + regression-guards header | ✓ VERIFIED | Function at line 313, factory at line 302, header at line 299. Imports include `WebSocketRoute`, `WebSocketDisconnect`, `handle_shell_websocket`, `AsyncMock`, `MagicMock`, `patch`. |
| `tests/test_ssh_tools.py` | `test_ssh01_sudo_run_check_raises_in_password_branch` + `test_ssh02_no_disjunctive_always_true_assertions` + regression-guards header | ⚠ PARTIAL | Both functions exist (lines 1060, 1107), header at 1056. SSH-01 is fully substantive. SSH-02 detector has a scope gap (does not catch the d25c915 mutation form). |
| `tests/test_error_handling.py` | `test_err01_timeout_message_reports_effective_value` + regression-guards header | ✓ VERIFIED | Function at line 421, header at line 417. Uses monkeypatch + `asyncio.wait_for` indirection — no real-time sleep. |
| `tests/test_tools.py` | `test_sch01_credential_type_rejects_non_enum_values` + regression-guards header | ✓ VERIFIED | Function at line 878, header at line 875. Asserts exact enum list equality and default value. |
| `src/homelab_mcp/http_app.py` | WS-01 fix still present (three `await websocket.close()` in `read_output` + EOF path) | ✓ VERIFIED | Three close() calls at lines 203, 207, 218, each wrapped in `contextlib.suppress(Exception)`. |
| `src/homelab_mcp/ssh_tools.py` | `_sudo_run` helper with `check` parameter forwarded | ✓ VERIFIED | `_sudo_run` at line 651-667 with `check: bool = False` parameter and single `return await conn.run(full_command, check=check)` at line 667 (both branches share forwarding). |
| `src/homelab_mcp/error_handling.py` | Error f-string uses `effective_timeout`, not `timeout_seconds` | ✓ VERIFIED | Line 58: `error_msg = f"Operation '{func.__name__}' timed out after {effective_timeout} seconds"`. The variable is computed at line 50/53 via `max(float(arg["timeout"]) + 5.0, timeout_seconds)`. |
| `src/homelab_mcp/tool_schemas/credential_tools_schema.py` | `credential_type` has `enum: ["ssh", "proxmox"]` | ✓ VERIFIED | Line 130: `"enum": ["ssh", "proxmox"],` still present, with `type: "string"` and `default: "ssh"` at lines 127-129. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `test_ws01_reader_closes_socket_on_pty_eof` | `handle_shell_websocket` | `WebSocketRoute` on `_make_shell_app` + `TestClient.websocket_connect` | ✓ WIRED | Imports, factory registration, and `client.websocket_connect("/ws/shell/test-session")` all present. |
| `test_ws01_reader_closes_socket_on_pty_eof` | `shell_session_manager` | `patch("homelab_mcp.http_app.shell_session_manager")` | ✓ WIRED | Line 341. `mock_mgr.get_session.return_value = mock_session` provides the session; `mock_mgr.resize_terminal = AsyncMock()` handles stdin path. |
| `test_ssh01_sudo_run_check_raises_in_password_branch` | `_sudo_run` | Direct import from `src.homelab_mcp.ssh_tools` | ✓ WIRED | `mock_conn.run.side_effect = asyncssh.ProcessError(...)` at line 1094, invocation at line 1097, forwarding check at line 1102. |
| `test_ssh02_no_disjunctive_always_true_assertions` | `tests/test_ssh_tools.py` (self) | `ast.parse(Path(__file__).read_text())` | ⚠ PARTIAL | AST walker runs correctly; detector scope is too narrow (see gap). |
| `test_err01_timeout_message_reports_effective_value` | `timeout_wrapper` + `asyncio.wait_for` | `@timeout_wrapper` decorator + `monkeypatch.setattr("src.homelab_mcp.error_handling.asyncio.wait_for", fake_wait_for)` | ✓ WIRED | Monkeypatch target matches the production import path; `fake_wait_for` closes the coro and raises TimeoutError immediately. |
| `test_sch01_credential_type_rejects_non_enum_values` | `get_available_tools` | Direct call in test body | ✓ WIRED | `tools = get_available_tools()`; navigation to `tools["list_keyring_credentials"]["inputSchema"]["properties"]["credential_type"]` at line 892-900. |

### Data-Flow Trace (Level 4)

Not applicable — phase 32 produces test code that exercises production data flow, not new user-facing renderers. The production code paths under test (WS-01 close, ERR-01 message, SSH-01 check propagation, SCH-01 enum) all produce real behavior, verified by the tests themselves.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 5 new regression tests pass | `uv run --no-sync pytest tests/test_http_app.py::test_ws01_reader_closes_socket_on_pty_eof tests/test_ssh_tools.py::test_ssh01_sudo_run_check_raises_in_password_branch tests/test_ssh_tools.py::test_ssh02_no_disjunctive_always_true_assertions tests/test_error_handling.py::test_err01_timeout_message_reports_effective_value tests/test_tools.py::test_sch01_credential_type_rejects_non_enum_values -v --no-cov` | `5 passed in 0.58s` | ✓ PASS |
| Detector scope gap: does detector flag the exact d25c915 mutation form? | Python AST parse of `assert "No credentials" in err["error"] or "other" in err["error"]` run through `_is_structurally_always_true` | `flagged? False` for the RHS operand | ✗ FAIL (this confirms the gap — detector does NOT catch the specific bug it was written to guard) |
| Production WS-01 close() calls still present | Grep `contextlib.suppress` + `websocket.close` in `http_app.py` | 3 matching pairs at lines 202-203, 206-207, 217-218 | ✓ PASS |
| Production ERR-01 f-string uses effective_timeout | Grep `effective_timeout` in `error_handling.py` | 5 hits including `timed out after {effective_timeout} seconds` at line 58 | ✓ PASS |
| Production SSH-01 forwards check= in both branches | Read `_sudo_run` at ssh_tools.py:651-667 | Single `return await conn.run(full_command, check=check)` at line 667, reached from both password and no-password branches | ✓ PASS |
| Production SCH-01 enum still present | Grep `"enum":` in `credential_tools_schema.py` | `"enum": ["ssh", "proxmox"]` at line 130 | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| REG-01 | 32-01, 32-02, 32-03, 32-04 | Regression tests exist for all 5 fixes above, preventing recurrence of each specific bug | ⚠ PARTIAL | 4/5 success criteria fully satisfied. SC #4 (SSH-02 regression) has a detector scope gap — catches simple tautologies but not the specific d25c915 mutation form, so reintroducing the exact pre-fix defect would silently pass. |

No orphaned requirements — REQUIREMENTS.md line 63 maps REG-01 to Phase 32, and all four plans declare `requirements: [REG-01]` in frontmatter. No additional requirements expected.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| tests/test_ssh_tools.py | 1146-1149 | Detector's Compare branch over-restricts to all-Constant comparators | ⚠ Warning | The AST meta-guard fails to catch the exact mutation pattern it was created to detect. Simple tautologies are caught, but the `Constant in Subscript/Attribute/Name` form (the actual d25c915 pre-fix) is not. A recurrence would ship silently. |
| (None) | — | No TODO/FIXME/stub anti-patterns found in the new test code or adjacent production code | ℹ Info | Pre-existing `SSHCompletedProcess[str]` subscription concern was a deferred pre-existing item per 32-02-PLAN; untouched by this phase. |

### Known Deviations Documented in Summaries

- **32-02-SUMMARY.md** explicitly flags the detector scope gap (`flags: [detector_scope_gap]`) and recommends a follow-up to extend `_is_structurally_always_true` to treat `Compare(left=Constant, ops=[In()])` as structurally always true regardless of the comparator. This is the same gap confirmed empirically during verification.
- **32-02-SUMMARY.md** notes the D-05 mutation experiment could not paste verbatim FAILED output due to sandbox restrictions; the commit body contains an analytical substitute. This does NOT independently fail any ROADMAP success criterion (the test itself passes and does catch the conservative subset), but it weakens the paper-trail quality of the REG-01 proof.
- **32-03-SUMMARY.md** notes an execution-environment deviation where the agent committed to `v1.4` main branch instead of its isolated worktree branch due to CWD confusion. Functional result is correct — the regression guard is in place and verified — so this is documentary only.

### Human Verification Required

None. All verification paths are programmatically exercised:
- The 5 new regression tests pass on HEAD.
- The revert-proofs are documented in commit bodies / SUMMARY.md.
- The detector scope gap was confirmed empirically by re-parsing the exact pre-fix source through the detector logic during verification.

### Gaps Summary

One partial against ROADMAP Success Criterion #4. The SSH-02 AST meta-test exists and passes, and it correctly catches simple literal tautologies — but it does NOT catch the specific mutation pattern that commit d25c915 fixed (`assert "No credentials" in err or "other" in err["error"]`). The detector's `Compare` branch requires all comparators to be `ast.Constant`, which is false for the `Subscript` comparator in the actual bug. This means the REG-01 contract for SC #4 is only partially satisfied: a future developer could silently reintroduce the exact d25c915 defect and the guard would not catch it.

**Fix:** extend `_is_structurally_always_true` to treat `Compare` as structurally always true when `isinstance(node.left, ast.Constant)` AND `node.ops[0]` is `ast.In`, regardless of the comparator type. This is a ~4-line change with zero false-positive risk (a constant literal being `in` anything dynamic is still a tautology in the context of a disjunctive `or` assert where the other branch is the actual check).

The other four success criteria pass cleanly. Phase 32 is 80% complete against its roadmap contract; gap closure is narrow and well-scoped.

---

*Verified: 2026-04-20*
*Verifier: Claude (gsd-verifier)*
