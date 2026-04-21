---
phase: 32-regression-tests
verified: 2026-04-20T00:00:00Z
re_verified: 2026-04-21T03:15:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "A test verifies the password assertion in test_ssh_tools.py fails when password is not propagated — the test is not unconditionally passing (REG-01 SC #4)"
  gaps_remaining: []
  regressions: []
gaps: []
deferred: []
human_verification: []
---

# Phase 32: Regression Tests Verification Report

**Phase Goal:** All 5 fixed bugs have dedicated regression tests that will catch any recurrence before it ships
**Verified (initial):** 2026-04-20 — status `gaps_found` (4/5)
**Re-verified (post 32-05 gap closure):** 2026-04-21 — status `passed` (5/5)
**Re-verification:** Yes — initial verification at commit `b4bd12c` produced `gaps_found` (1 partial against REG-01 SC #4); plan 32-05 executed in commits `94b977a` + `b8a81ad`, merged at `5cba2cc`, tracking updated at `3b24d6f`. This re-verification closes the gap and re-confirms the 4 previously-verified success criteria.

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | WebSocket PTY reader cancels its paired task and closes the socket on EOF — reverting the fix causes the test to fail | ✓ VERIFIED | `tests/test_http_app.py::test_ws01_reader_closes_socket_on_pty_eof` — passes in isolated re-verification run (PASSED [25%] in 4-test spot-check batch). Production `http_app.py` still has the 3 `contextlib.suppress(Exception) + await websocket.close()` pairs at lines 202-203, 206-207, 217-218 (grep confirmed). Revert-proof documented in 32-01-SUMMARY.md. No regression from 32-05. |
| 2 | Timeout error message contains the effective_timeout value — reverting the fix causes the test to fail | ✓ VERIFIED | `tests/test_error_handling.py::test_err01_timeout_message_reports_effective_value` — passes in re-verification (PASSED [75%]). Production `error_handling.py:58` still contains `timed out after {effective_timeout} seconds` (grep confirmed — 5 hits for `effective_timeout` at lines 50, 53, 55, 58, 241). Revert-proof documented in 32-03-SUMMARY.md. No regression from 32-05. |
| 3 | `_sudo_run(check=True)` raises on non-zero exit in the password branch — reverting the fix causes the test to fail | ✓ VERIFIED | `tests/test_ssh_tools.py::test_ssh01_sudo_run_check_raises_in_password_branch` — passes in re-verification (PASSED [50%]). Production `ssh_tools.py` still has `check: bool = False` at line 655 and `return await conn.run(full_command, check=check)` at line 667 (grep confirmed). Revert-proof documented in commit `e50cda1`. No regression from 32-05. |
| 4 | Password assertion in `test_ssh_tools.py` fails when password is not propagated — the test is not unconditionally passing | ✓ VERIFIED (gap closed) | `tests/test_ssh_tools.py::test_ssh02_no_disjunctive_always_true_assertions` — passes on clean HEAD (PASSED [100%] in both isolated and full-file runs). **Gap from initial verification closed by plan 32-05.** Extended `_is_structurally_always_true` helper now contains the broadened Compare branch (b): `isinstance(node.left, ast.Constant) and node.ops and isinstance(node.ops[0], ast.In)` at line 1171. Empirically re-confirmed: parsing the exact d25c915 pre-fix source `assert "No credentials" in result_data["error"] or "other" in result_data["error"]` through the extended detector yields `flagged? True` for the RHS operand AND `flagged? True` for the full BoolOp (via Or-recursion). Mutation experiment in 32-05-SUMMARY.md provides verbatim pytest FAILED output: `line 192: assert 'No credentials' in result_data['error'] or 'other' in result_data['error']`. REG-01 SC #4 is now fully revert-proof. |
| 5 | Credentials tool schema rejects non-enum credential_type values — reverting the fix causes the test to fail | ✓ VERIFIED | `tests/test_tools.py::test_sch01_credential_type_rejects_non_enum_values` — passes in re-verification (PASSED [100%]). Production `credential_tools_schema.py:130` still contains `"enum": ["ssh", "proxmox"]` (grep confirmed). Revert-proof documented in 32-04-SUMMARY.md and commit `f03e585`. No regression from 32-05. |

**Score:** 5/5 truths verified. Phase goal achieved.

### Deferred Items

None.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/test_http_app.py` | `test_ws01_reader_closes_socket_on_pty_eof` + `_make_shell_app` factory + regression-guards header | ✓ VERIFIED | Re-confirmed — test passes unchanged; no touch by 32-05. |
| `tests/test_ssh_tools.py` | `test_ssh01_sudo_run_check_raises_in_password_branch` + `test_ssh02_no_disjunctive_always_true_assertions` with extended detector + regression-guards header | ✓ VERIFIED | SSH-01 test unchanged by 32-05 and still passes. SSH-02 test extended: `_is_structurally_always_true` now at lines 1135-1173 with broadened docstring (lines 1136-1153), original Constant-vs-Constant Compare rule preserved at line 1161, new Constant-in-Anything Compare rule at line 1171. All 23 tests in file pass. |
| `tests/test_error_handling.py` | `test_err01_timeout_message_reports_effective_value` + regression-guards header | ✓ VERIFIED | Re-confirmed — unchanged by 32-05. |
| `tests/test_tools.py` | `test_sch01_credential_type_rejects_non_enum_values` + regression-guards header | ✓ VERIFIED | Re-confirmed — unchanged by 32-05. |
| `.planning/phases/32-regression-tests/32-CONTEXT.md` | D-10 decision note documenting the broadened Compare coverage | ✓ VERIFIED | D-10 inserted at line 45, inside `<decisions>` block, between D-05 (line 44) and the "### WS-01 Test Depth" subsection (line 47). Contains exact anchors required by plan: `d25c915 pre-fix defect`, `ast.In`, `plan 32-05`, `isinstance(node.left, ast.Constant)`. D-01..D-09 unchanged (`grep -c "^- \*\*D-0"` returns 9). |
| `src/homelab_mcp/http_app.py` | WS-01 fix still present (three `await websocket.close()` in `read_output` EOF/error paths) | ✓ VERIFIED | Grep confirms 3 close() calls at 203, 207, 218 + guard close at 176. |
| `src/homelab_mcp/ssh_tools.py` | `_sudo_run` helper with `check` parameter forwarded | ✓ VERIFIED | `check: bool = False` at line 655, single-path return `check=check` at line 667. |
| `src/homelab_mcp/error_handling.py` | Error f-string uses `effective_timeout` | ✓ VERIFIED | Line 58 contains `timed out after {effective_timeout} seconds`. |
| `src/homelab_mcp/tool_schemas/credential_tools_schema.py` | `credential_type` has `enum: ["ssh", "proxmox"]` | ✓ VERIFIED | Line 130. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `test_ws01_reader_closes_socket_on_pty_eof` | `handle_shell_websocket` | `WebSocketRoute` on `_make_shell_app` + `TestClient.websocket_connect` | ✓ WIRED | Unchanged since initial verification. |
| `test_ssh01_sudo_run_check_raises_in_password_branch` | `_sudo_run` | Direct import from `src.homelab_mcp.ssh_tools` | ✓ WIRED | Unchanged since initial verification. |
| `test_ssh02_no_disjunctive_always_true_assertions` | `tests/test_ssh_tools.py` (self) | `ast.parse(Path(__file__).read_text())` + extended `_is_structurally_always_true` helper | ✓ WIRED (gap closed) | Detector now catches the d25c915 pre-fix mutation form. Empirical proof: `flagged? True` for the exact pre-fix Compare node, verified live in this verification run. |
| `test_err01_timeout_message_reports_effective_value` | `timeout_wrapper` + `asyncio.wait_for` | Monkeypatch | ✓ WIRED | Unchanged. |
| `test_sch01_credential_type_rejects_non_enum_values` | `get_available_tools` | Direct call in test body | ✓ WIRED | Unchanged. |
| `.planning/phases/32-regression-tests/32-CONTEXT.md` D-10 | `_is_structurally_always_true` in `test_ssh_tools.py` | Decision note references `ast.In`, `Constant in X`, d25c915 pre-fix defect; test helper docstring references D-10 | ✓ WIRED | Both ends present. `grep -q "D-10" tests/test_ssh_tools.py` exit 0 (2 hits: docstring line 1152 + inline comment line 1170). `grep -q "^- \*\*D-10\*\*" .planning/phases/32-regression-tests/32-CONTEXT.md` exit 0 (line 45). |

### Data-Flow Trace (Level 4)

Not applicable — phase 32 produces test code that exercises production data flow, not new user-facing renderers. Status unchanged from initial verification.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full `test_ssh_tools.py` regression | `uv run --no-sync pytest tests/test_ssh_tools.py -v --no-cov` | 23 passed in 0.25s | ✓ PASS |
| SSH-02 test in isolation | `uv run --no-sync pytest tests/test_ssh_tools.py::test_ssh02_no_disjunctive_always_true_assertions -v --no-cov` | 1 passed in 0.17s | ✓ PASS |
| All 4 other regression tests still pass | `uv run --no-sync pytest tests/test_http_app.py::test_ws01_reader_closes_socket_on_pty_eof tests/test_ssh_tools.py::test_ssh01_sudo_run_check_raises_in_password_branch tests/test_error_handling.py::test_err01_timeout_message_reports_effective_value tests/test_tools.py::test_sch01_credential_type_rejects_non_enum_values -v --no-cov` | 4 passed in 0.57s | ✓ PASS |
| Extended detector flags d25c915 pre-fix form | In-memory AST parse of `assert "No credentials" in result_data["error"] or "other" in result_data["error"]` through the extended `_is_structurally_always_true` helper | `RHS node: Compare(left=Constant('other'), ops=[In()], comparators=[Subscript(...)])` → `flagged? True`; full-BoolOp `flagged? True` | ✓ PASS (was FAIL in initial verification — gap closed) |
| Detector-extension pattern grep | `grep -n "isinstance(node.ops\[0\], ast.In)" tests/test_ssh_tools.py` | `1171:            if isinstance(node.left, ast.Constant) and node.ops and isinstance(node.ops[0], ast.In):` | ✓ PASS (exit 0) |
| D-10 docstring anchor grep | `grep -n "D-10" tests/test_ssh_tools.py` | `1152:        See .planning/phases/32-regression-tests/32-CONTEXT.md decision D-10.` + `1170:            # See CONTEXT.md decision D-10 for the full rationale.` | ✓ PASS (exit 0) |
| d25c915 inline-comment anchor grep | `grep -n "d25c915 pre-fix defect" tests/test_ssh_tools.py` | docstring line 1149 + inline comment line 1166 | ✓ PASS (exit 0) |
| CONTEXT.md D-10 bullet grep | `grep -n "^- \*\*D-10\*\*" .planning/phases/32-regression-tests/32-CONTEXT.md` | `45:- **D-10** *(added 2026-04-20 via Phase 32 gap closure — plan 32-05...)*: Extend ...` | ✓ PASS (exit 0) |
| CONTEXT.md D-01..D-09 unchanged | `grep -c "^- \*\*D-0" .planning/phases/32-regression-tests/32-CONTEXT.md` | `9` | ✓ PASS |
| Production WS-01 close() calls still present | `grep -n "websocket.close\|contextlib.suppress" src/homelab_mcp/http_app.py` | 3 close() at lines 203, 207, 218 + guard at 176; 3 suppress() pairs at 202, 206, 217 | ✓ PASS |
| Production ERR-01 f-string uses effective_timeout | `grep -n "effective_timeout" src/homelab_mcp/error_handling.py` | 5 hits including `timed out after {effective_timeout} seconds` at line 58 | ✓ PASS |
| Production SSH-01 forwards check= | `grep -n "check=check\|check: bool" src/homelab_mcp/ssh_tools.py` | `check: bool = False` at 655, `check=check` at 667 | ✓ PASS |
| Production SCH-01 enum still present | `grep -n "enum.*ssh.*proxmox" src/homelab_mcp/tool_schemas/credential_tools_schema.py` | `"enum": ["ssh", "proxmox"]` at line 130 | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| REG-01 | 32-01, 32-02, 32-03, 32-04, 32-05 | Regression tests exist for all 5 fixes above, preventing recurrence of each specific bug | ✓ SATISFIED | All 5 ROADMAP success criteria verified. Plan 32-05 closed the one partial (SC #4, SSH-02 detector scope) by broadening the AST detector's Compare branch to flag `Constant in <anything>`. Verbatim mutation FAILED output in 32-05-SUMMARY.md demonstrates revert-proof. Four of four other regression tests still pass in re-verification. |

REQUIREMENTS.md line 63 maps REG-01 exclusively to Phase 32. No orphaned requirements — all five plans declare `requirements: [REG-01]` in frontmatter, and 32-05 was the gap-closure plan for REG-01 SC #4.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (None) | — | No new anti-patterns introduced by 32-05 | ℹ Info | Re-scan of files modified by 32-05 (`tests/test_ssh_tools.py`, `.planning/phases/32-regression-tests/32-CONTEXT.md`) found no TODO/FIXME/stub patterns. The previously-noted detector scope gap at lines 1146-1149 is now resolved — the `ast.In` branch closes it. |
| tests/test_ssh_tools.py | 981 | Drive-by fix: previous `assert "grep -Ff" in grep_cmd or "-Ff" in grep_cmd` simplified to `assert "-Ff" in grep_cmd` | ℹ Info | Not a regression — documented in 32-05-SUMMARY.md "Deviations #1" as a Rule 1 auto-fix. The extended detector would have flagged the original pattern (superstring LHS implies substring RHS is tautologically true), and the plan's explicit guidance ("that legitimate pattern IS the SSH-02 anti-pattern and must be fixed separately") authorized the simplification. `test_setup_mcp_admin_uses_grep_ff` still passes with intent preserved. Verified by re-reading line 981 (now: `assert "-Ff" in grep_cmd, ...`) and running the full suite. |

### Known Deviations Documented in Summaries

- **32-02-SUMMARY.md** flagged the detector scope gap in the initial pass. That flag drove the creation of plan 32-05. **Now resolved** — re-verification confirms the gap is closed.
- **32-02-SUMMARY.md** "Deviations" section noted D-05 verbatim-FAILED-paste could not be captured due to sandbox restrictions in the original detection pass. Plan 32-05 **captured the verbatim FAILED output** in 32-05-SUMMARY.md (shown below), retroactively strengthening the D-05 paper trail:

  ```
  tests/test_ssh_tools.py::test_ssh02_no_disjunctive_always_true_assertions FAILED [100%]
  ...
  E   AssertionError: Found `assert X or <always-true>` anti-pattern(s) in test_ssh_tools.py.
  E     Replace with explicit single-check asserts (see SSH-02 fix in commit d25c915):
  E     line 192: assert 'No credentials' in result_data['error'] or 'other' in result_data['error']
  ```

  The mutation matches the exact d25c915 pre-fix form (substituting `result_data["error"]` for `err`, `err["error"]`), is self-consistent with the line-192 anchor against the same `test_ssh_discover_no_credentials` target used in D-05, and was confirmed reverted before commit (`git diff` check in plan verification step 4).
- **32-03-SUMMARY.md** documentary-only note about worktree CWD confusion during ERR-01 execution; functionally correct outcome.
- **32-05-SUMMARY.md** "Deviations #2" — ruff reformatted the new `if` block to single lines. Semantically identical; grep patterns still match (confirmed in this re-verification).

### Environmental / Pre-Existing Failures

- **`tests/test_packaging.py::test_version_unified` — environmental, pre-existing, out of scope.** The installed package (1.3.2) is pinned stale behind `pyproject.toml` (1.4.0). This failure existed at commit `b4bd12c` before 32-05 and is NOT a regression from this gap closure. Explicitly outside REG-01 scope (Phase 32's contract is the 5 SCs above; packaging version unification is a separate concern). Not flagged as a phase-32 gap.

### Gap Closure Audit (32-05 deliverables vs the partial it was meant to close)

| 32-05 Deliverable | Plan Spec | Actual Delivery | Status |
|-------------------|-----------|-----------------|--------|
| Extend `_is_structurally_always_true` to catch `Compare(left=Constant, ops=[In()])` | Mandatory (Task 1 core edit) | Line 1171: `if isinstance(node.left, ast.Constant) and node.ops and isinstance(node.ops[0], ast.In): return True` | ✓ DELIVERED |
| Updated docstring explaining broadened coverage | Mandatory (Task 1 Edit 2) | Lines 1136-1153: docstring rewritten with TWO bullets (Constant-vs-Constant + Constant-in-Anything) and pointer to D-10 | ✓ DELIVERED |
| Inline comment anchoring "d25c915 pre-fix defect" | Acceptance criterion grep | Lines 1163-1170: inline comment block explaining the Compare-in branch with explicit reference to `d25c915 pre-fix defect` and the exact assertion shape | ✓ DELIVERED |
| Decision note D-10 in CONTEXT.md | Mandatory (Task 2) | Line 45, between D-05 and "### WS-01 Test Depth" heading, inside `<decisions>` XML block. Records: broadening rationale, exact d25c915 pre-fix reference, supersedes-D-03-for-In-only clause, plan 32-05 origin stamp. | ✓ DELIVERED |
| D-01..D-09 preserved unchanged | Acceptance criterion | `grep -c "^- \*\*D-0"` returns 9 | ✓ DELIVERED |
| Mutation experiment proving extended detector flags exact d25c915 pre-fix shape | Mandatory (plan verification step 4) | 32-05-SUMMARY.md "SSH-02 Mutation Experiment" section: verbatim pytest FAILED output with AssertionError citing `line 192: assert 'No credentials' in result_data['error'] or 'other' in result_data['error']`. Mutation not committed (`git diff` confirms). Re-confirmed live in this verification via in-memory AST parse: `flagged? True` for the RHS Compare node. | ✓ DELIVERED |
| Conservative subset still caught — no regression in existing detection | Plan verification step 6 | 32-05-SUMMARY.md "Conservative-Subset Matrix" table with 7 shapes all matching expected (4 offenders / 2 non-offenders + 1 d25c915 pre-fix shape). Live re-confirmed: the existing Constant branch and Compare-over-Constants branch are preserved unchanged. | ✓ DELIVERED |
| Scope respected — no edits outside the two authorized files, no production-code edits, no new test functions | Plan "Out of scope" guardrail | Only `tests/test_ssh_tools.py` and `.planning/phases/32-regression-tests/32-CONTEXT.md` modified. Line 981 drive-by fix is an authorized Rule 1 auto-fix inside the allowed file scope, with explicit plan guidance covering it. | ✓ DELIVERED |
| Full `test_ssh_tools.py` suite still passes | Acceptance criterion | 23 passed in 0.25s (live re-run) | ✓ DELIVERED |
| REG-01 SC #4 revert-proof | Exit condition for plan | Mutation experiment FAILED output in 32-05-SUMMARY.md + live AST parse = reintroducing the exact d25c915 defect now fails the guard. | ✓ DELIVERED |

**Audit conclusion:** Plan 32-05 delivered every item in its acceptance criteria. The verbatim FAILED mutation output in 32-05-SUMMARY.md is self-consistent with the detector extension and the d25c915 pre-fix reference target (line 192 of `test_ssh_discover_no_credentials` — the exact test D-05 was recorded against). The gap identified in the initial verification is fully closed; no new gaps were introduced; no regressions in the 4 previously-verified SCs.

### Human Verification Required

None. All five regression tests pass programmatically on current HEAD. The SSH-02 detector extension is confirmed revert-proof via two independent methods: (a) the mutation experiment with verbatim pytest FAILED output captured in 32-05-SUMMARY.md, and (b) an in-memory AST parse run live during this re-verification. No visual, real-time, or external-service behavior requires human testing — this phase is 100% test-code with direct programmatic observables.

### Gaps Summary

None. Phase 32 is now at 5/5 ROADMAP success criteria VERIFIED. The single partial (SC #4 — SSH-02 detector scope) identified in the initial verification at commit `b4bd12c` has been closed by plan 32-05 (commits `94b977a` + `b8a81ad`, merged at `5cba2cc`). The REG-01 requirement is fully satisfied: every one of the 5 Phase-31 bug fixes (WS-01, ERR-01, SSH-01, SSH-02, SCH-01) has a dedicated regression test whose revert-proof is documented either by explicit mutation experiment (SSH-02) or by revert-causes-test-fail analysis in the corresponding plan summary (WS-01, ERR-01, SSH-01, SCH-01).

Phase goal achieved: **"All 5 fixed bugs have dedicated regression tests that will catch any recurrence before it ships."**

---

*Initially verified: 2026-04-20 (status gaps_found, 4/5)*
*Re-verified: 2026-04-21 (status passed, 5/5) after 32-05 gap closure*
*Verifier: Claude (gsd-verifier)*
