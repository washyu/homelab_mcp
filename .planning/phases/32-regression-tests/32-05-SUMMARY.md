---
phase: 32-regression-tests
plan: 05
status: complete
closes_gap: SSH-02 detector scope (VERIFICATION.md REG-01 SC #4)
requirements:
  - REG-01
tags:
  - testing
  - regression
  - gap-closure
  - ast
  - ssh
subsystem: tests/test_ssh_tools.py — SSH-02 AST meta-guard
one_liner: "Extend `_is_structurally_always_true` to treat `Compare(left=Constant, ops=[In()], comparators=[<any>])` as a tautology; closes d25c915 detector-scope gap"
dependency_graph:
  requires:
    - 32-02 (SSH-02 baseline meta-guard + detector_scope_gap flag)
  provides:
    - Extended AST detector covering the exact d25c915 pre-fix mutation form
    - CONTEXT.md D-10 decision record
  affects:
    - tests/test_ssh_tools.py::test_ssh02_no_disjunctive_always_true_assertions
    - tests/test_ssh_tools.py::test_setup_mcp_admin_uses_grep_ff (drive-by anti-pattern fix)
tech_stack:
  added: []
  patterns:
    - AST-based lint-style meta-test (extension of pattern established in D-03)
key_files:
  created: []
  modified:
    - tests/test_ssh_tools.py
    - .planning/phases/32-regression-tests/32-CONTEXT.md
decisions:
  - D-10 (CONTEXT.md): broaden Compare detection to `Constant in <anything>` regardless of comparator type; supersedes D-03 for the `In` operator only
metrics:
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
  commits: 2
  duration_minutes: ~20
  completed_utc: 2026-04-21T02:58:00Z
---

# Phase 32 Plan 05: SSH-02 Detector Scope Gap Closure Summary

## Outcome

Closed the single remaining gap from `.planning/phases/32-regression-tests/32-VERIFICATION.md` (status `gaps_found`, REG-01 SC #4 `partial`). The SSH-02 AST meta-guard in `tests/test_ssh_tools.py::test_ssh02_no_disjunctive_always_true_assertions` now catches the **exact d25c915 pre-fix mutation form**:

```python
assert "No credentials" in result_data["error"] or "other" in result_data["error"]
```

This was previously missed because the detector's `Compare` branch required `all(isinstance(c, ast.Constant) for c in node.comparators)` — false for the `Subscript` comparator in the actual bug. Extension: when `node.left` is `ast.Constant` AND `node.ops[0]` is `ast.In`, treat the Compare as always-true regardless of comparator type. In the context of a disjunctive `or` assert (the only invocation site), this is a sound tautology because the other branch is the actual semantic check.

## Tasks

| # | Task | Status | Commit  |
|---|------|--------|---------|
| 1 | Extend `_is_structurally_always_true` + update docstring + run mutation experiment | ✓ | `94b977a` |
| 2 | Add decision note D-10 to `.planning/phases/32-regression-tests/32-CONTEXT.md` | ✓ | `b8a81ad` |

## Key Files

### `tests/test_ssh_tools.py` — modified

- **Lines 1134-1177** (post-change): `_is_structurally_always_true` helper extended:
  - Expanded docstring documenting both Compare rules + pointer to D-10 (lines 1136-1154).
  - Compare branch (a): existing Constant-vs-Constant rule preserved (line 1160).
  - Compare branch (b) — NEW: `isinstance(node.left, ast.Constant) and node.ops and isinstance(node.ops[0], ast.In)` (line 1170). Inline comment anchors the d25c915 pre-fix defect (lines 1162-1169).
- **Line 981** (drive-by Rule 1 fix): `assert "grep -Ff" in grep_cmd or "-Ff" in grep_cmd` → `assert "-Ff" in grep_cmd`. The original form was a latent SSH-02 anti-pattern (the LHS superstring `"grep -Ff"` logically implies the RHS substring `"-Ff"`); the extended detector would correctly flag it as a false offender. Simplified to the single stronger check; `test_setup_mcp_admin_uses_grep_ff` still passes with intent preserved (grep must use `-Ff` flag).

### `.planning/phases/32-regression-tests/32-CONTEXT.md` — modified

- **Line 45** (new): D-10 bullet inserted between D-05 (line 44) and `### WS-01 Test Depth` (line 47), inside the `<decisions>` XML block (lines 25..68). Records the broadening rationale, references the exact d25c915 pre-fix shape, and explicitly states D-10 supersedes D-03 for the `In` operator only (Constant-vs-Constant rule preserved for other operators). No other decision renumbered or modified.

## SSH-02 Mutation Experiment (D-10 re-run — d25c915 exact pre-fix form)

Procedure:
1. After the Task 1 detector extension: confirm `test_ssh02_no_disjunctive_always_true_assertions` PASSES against HEAD (0 offenders).
2. Transiently mutate line 192 of `tests/test_ssh_tools.py` from:
   ```python
   assert "No credentials" in result_data["error"]
   ```
   to the exact d25c915 pre-fix shape:
   ```python
   assert "No credentials" in result_data["error"] or "other" in result_data["error"]
   ```
3. Re-run the test. Expected: FAILED (offender reported at line 192).
4. Revert the mutation. Confirm `git diff tests/test_ssh_tools.py` shows only the detector-extension + line-981 drive-by fix.
5. Mutation was **not committed**.

### Verbatim pytest failure output (mutation applied)

```
tests/test_ssh_tools.py::test_ssh02_no_disjunctive_always_true_assertions FAILED [100%]

================================== FAILURES ===================================
______________ test_ssh02_no_disjunctive_always_true_assertions _______________
tests\test_ssh_tools.py:1185: in test_ssh02_no_disjunctive_always_true_assertions
    assert not offenders, (
E   AssertionError: Found `assert X or <always-true>` anti-pattern(s) in test_ssh_tools.py.
E     Replace with explicit single-check asserts (see SSH-02 fix in commit d25c915):
E     line 192: assert 'No credentials' in result_data['error'] or 'other' in result_data['error']
E   assert not ["line 192: assert 'No credentials' in result_data['error'] or 'other' in result_data['error']"]
=========================== short test summary info ===========================
FAILED tests/test_ssh_tools.py::test_ssh02_no_disjunctive_always_true_assertions - AssertionError: Found `assert X or <always-true>` anti-pattern(s) in test_ssh_tools.py.
  Replace with explicit single-check asserts (see SSH-02 fix in commit d25c915):
  line 192: assert 'No credentials' in result_data['error'] or 'other' in result_data['error']
============================== 1 failed in 0.24s ==============================
```

This is the REG-01 SC #4 revert-proof. Reintroducing the exact d25c915 defect now fails the regression guard — the bug cannot silently ship.

After mutation revert: `uv run pytest tests/test_ssh_tools.py::test_ssh02_no_disjunctive_always_true_assertions -v --no-cov` → `1 passed in 0.19s` (0 offenders on clean HEAD).

## Conservative-Subset Matrix (Verification Step 6)

Six shapes run through the extended detector (extracting the RHS of `assert X or <Y>` and calling `_is_structurally_always_true(Y)`), plus a bonus check for the d25c915 pre-fix form:

| Shape                                                          | Expected | Got   | Status | Notes                                              |
|----------------------------------------------------------------|----------|-------|--------|----------------------------------------------------|
| `assert x or "literal"`                                         | True     | True  | OK     | Existing Constant branch                           |
| `assert x or True`                                              | True     | True  | OK     | Existing Constant branch                           |
| `assert x or ("a" == "a")`                                      | True     | True  | OK     | Existing Compare-over-Constants branch             |
| `assert x or ("other" in y)` where `y` is Name                  | True     | True  | OK     | **NEW** Constant-in-Anything branch                |
| `assert x or foo` where `foo` is Name                           | False    | False | OK     | Dynamic Name — correctly NOT flagged               |
| `assert x or (a in b)` where `a`, `b` are Names                 | False    | False | OK     | Dynamic LHS `in` — correctly NOT flagged           |
| `assert "No credentials" in err or "other" in err["error"]`     | True     | True  | OK     | d25c915 pre-fix exact shape — flagged              |

**All seven cases match expected.** No regression in existing detection; the d25c915 pre-fix shape is now flagged; dynamic-expression patterns are still correctly treated as non-tautologies.

## Verification

| Check | Command | Result |
|-------|---------|--------|
| SSH-02 regression test isolated | `uv run pytest tests/test_ssh_tools.py::test_ssh02_no_disjunctive_always_true_assertions -v --no-cov` | PASSED (0 offenders, 0.19s) |
| Full `test_ssh_tools.py` suite | `uv run pytest tests/test_ssh_tools.py -v --no-cov` | 23 passed in 0.21s |
| Lint | `uv run ruff check tests/test_ssh_tools.py` | All checks passed! |
| Format | `uv run ruff format --check tests/test_ssh_tools.py` | 1 file already formatted |
| Detector scope grep | `grep -q "isinstance(node.ops\[0\], ast.In)" tests/test_ssh_tools.py` | exit 0 |
| D-10 docstring anchor | `grep -q "D-10" tests/test_ssh_tools.py` | exit 0 |
| d25c915 inline comment anchor | `grep -q "d25c915 pre-fix defect" tests/test_ssh_tools.py` | exit 0 |
| File parseable | `python -c "import ast, pathlib; ast.parse(pathlib.Path('tests/test_ssh_tools.py').read_text())"` | exit 0 |
| CONTEXT.md D-10 bullet | `grep -q "^- \*\*D-10\*\*" .planning/phases/32-regression-tests/32-CONTEXT.md` | exit 0 |
| CONTEXT.md d25c915 anchor | `grep -q "d25c915 pre-fix defect" .planning/phases/32-regression-tests/32-CONTEXT.md` | exit 0 |
| CONTEXT.md ast.In ref | `grep -q "ast.In" .planning/phases/32-regression-tests/32-CONTEXT.md` | exit 0 |
| CONTEXT.md plan 32-05 ref | `grep -q "plan 32-05" .planning/phases/32-regression-tests/32-CONTEXT.md` | exit 0 |
| CONTEXT.md D-01..D-09 unchanged | `grep -c "^- \*\*D-0" .planning/phases/32-regression-tests/32-CONTEXT.md` | 9 |

## Deviations from Plan

### 1. Rule 1 auto-fix — drive-by SSH-02 anti-pattern at line 981

**Found during:** Task 1, after applying the detector extension and running the pytest sanity check.

**Issue:** The plan asserted (per VERIFICATION.md) that `tests/test_ssh_tools.py` contained "exactly zero such offenders today beyond the gap case itself." Running the extended detector revealed one offender: line 981, `assert "grep -Ff" in grep_cmd or "-Ff" in grep_cmd`, introduced by commit `34bf920` (pre-Phase-32). This IS a latent SSH-02 anti-pattern — the LHS superstring `"grep -Ff"` logically implies the RHS substring `"-Ff"`, so the disjunction has no independent semantic value; the weaker branch is redundant. The verifier's empirical check pre-dated the detector extension and therefore did not catch it.

**Fix:** Per Rule 1 and the plan's explicit guidance ("that legitimate pattern IS the SSH-02 anti-pattern and must be fixed separately"), simplified line 981 to `assert "-Ff" in grep_cmd`. The test `test_setup_mcp_admin_uses_grep_ff` still passes; the intent (grep command must use the `-Ff` flag) is preserved — `"-Ff"` is a substring of any valid `-Ff <file>`-style invocation.

**Files modified:** `tests/test_ssh_tools.py` (line 981, 1-line edit within the same commit as the detector extension).

**Commit:** `94b977a` (Task 1 commit — deviation documented in commit body under `## Deviations`).

**Scope respected:** Edit is inside the allowed scope (`tests/test_ssh_tools.py`). Not a new test function. Not production code.

### 2. Ruff reformatted the new `if` block to single lines

**Found during:** Task 1, post-edit verification.

**Issue:** My initial edit used multi-line `if` blocks for the `Compare` branches. `ruff format --check` reported the file would be reformatted — ruff's line-length rules collapsed the conditions onto single lines.

**Fix:** Ran `uv run ruff format tests/test_ssh_tools.py`. Result is semantically identical; all acceptance-criteria grep patterns still match (the `isinstance(node.ops[0], ast.In)` substring survives the collapse). Tests still pass.

**Commit:** `94b977a` (embedded in the Task 1 commit — final formatted state is what was committed).

## Self-Check: PASSED

Files created/modified verification:

- `tests/test_ssh_tools.py` — MODIFIED (committed in `94b977a`)
- `.planning/phases/32-regression-tests/32-CONTEXT.md` — MODIFIED (committed in `b8a81ad`)
- `.planning/phases/32-regression-tests/32-05-SUMMARY.md` — CREATED (this file)

Commits verification:

- `94b977a` — Task 1 present in `git log --oneline` (verified)
- `b8a81ad` — Task 2 present in `git log --oneline` (verified)

### REG-01 Success Criterion #4 closure check

| Requirement | Before (32-VERIFICATION.md) | After (this plan) |
|-------------|-----------------------------|-------------------|
| Password assertion in `test_ssh_tools.py` fails when password is not propagated — test is not unconditionally passing | ⚠ PARTIAL — detector catches simple tautologies but NOT the exact d25c915 mutation form | ✓ SATISFIED — detector now flags the exact d25c915 pre-fix shape (`Compare(left=Constant, ops=[In], comparators=[<any>])`), proven via mutation experiment with verbatim FAILED pytest output captured above |

REG-01 SC #4 is now fully satisfied. Phase 32 REG-01 coverage advances from 4/5 VERIFIED to 5/5 VERIFIED.

## Known Stubs

None. No stub patterns introduced or present in the files touched.

## Threat Flags

None. This plan extends a test-file lint meta-guard; it introduces no new network endpoints, auth paths, file access patterns, or schema changes. No new security-relevant surface.
