---
phase: 32-regression-tests
plan: 02
status: complete
requirements:
  - REG-01
flags:
  - detector_scope_gap
---

# Plan 32-02 Summary — SSH-01 + SSH-02 Regression Guards

## Outcome

Added two regression tests to `tests/test_ssh_tools.py` under a new `# --- Regression guards (v1.5 / PR #39) ---` section header:

1. **SSH-01 regression** — proves `_sudo_run(conn, command, password="...", check=True)` forwards `check=True` to `conn.run`, so a non-zero exit raised as `asyncssh.ProcessError` propagates to the caller. Guards commit `9f752c0`.
2. **SSH-02 AST meta-test** — parses `tests/test_ssh_tools.py` itself and fails if any `assert X or <structurally-always-true>` pattern is present. Guards commit `d25c915`.

## Tasks

| # | Task | Status | Commit |
|---|------|--------|--------|
| 1 | Add SSH-01 `_sudo_run(check=True)` forwarding regression | ✓ | `e50cda1` |
| 2 | Add SSH-02 AST meta-regression on disjunctive-always-true asserts | ✓ | `7f7ea8e` |

## Key Files

- `tests/test_ssh_tools.py` — modified (two new test functions + section header)
  - `test_ssh01_sudo_run_check_raises_in_password_branch`
  - `test_ssh02_no_disjunctive_always_true_assertions`

## Verification

- `uv run pytest tests/test_ssh_tools.py -v` → **23/23 pass** in 0.24s
- `uv run ruff check tests/test_ssh_tools.py` → clean
- `uv run ruff format --check tests/test_ssh_tools.py` → already formatted

## Revert-Proof Evidence (REG-01)

**SSH-01:** Executed with verbatim FAILED output captured in commit `e50cda1` message, confirming the test fails when `_sudo_run` does not forward `check=True` to `conn.run`.

**SSH-02:** See "Deviations" below — the D-05 mutation experiment was blocked by sandbox restrictions; commit `7f7ea8e` contains an analytical substitute for the literal FAILED paste.

## Deviations from Plan

### 1. D-05 mutation experiment blocked by sandbox (not a scope change)

All six mutation approaches (`Edit` of the target line x2, `Bash` with in-memory string scan, `Bash` with `/tmp` copy, `Bash` with `git stash`, `Write` of probe scripts x2) were denied by the execution sandbox. The literal "paste verbatim FAILED output into commit message" requirement from decision D-05 was NOT met. The commit message contains an analytical substitute describing the expected failure mode.

### 2. CRITICAL planning gap — SSH-02 detector scope does not cover d25c915's actual mutation form

While preparing the D-05 deviation note, static analysis revealed that the conservative detector specified in decision D-03 **does not catch the specific mutation pattern that `d25c915` actually fixed**:

- `d25c915`'s pre-fix assertion was `assert "No credentials" in err or "other" in err`
- The RHS `"other" in err` parses to `Compare(left=Constant("other"), ops=[In()], comparators=[Subscript(err, 'error')])`
- The detector's `Compare` branch requires `all(isinstance(c, ast.Constant) for c in node.comparators)`, which is `False` for `Subscript`
- Therefore the detector returns `False` for this Compare and the mutation is NOT flagged
- REG-01 success criterion #4 is only **partially satisfied** — simpler tautologies like `assert X or "literal"` ARE flagged; the exact `d25c915` form is NOT

**Recommended follow-up:** Extend `_is_structurally_always_true` to also treat a `Compare` node as always-true when `node.left` is `ast.Constant` AND `node.ops[0]` is `ast.In`, regardless of what the comparator expression is. A follow-up gap-closure plan should either (a) implement this extension, or (b) update REG-01 #4's wording to match the detector's actual scope.

### 3. SUMMARY.md creation blocked by sandbox

All `Write` tool operations (including creation of this file) were denied to the subagent. This file is therefore written post-hoc by the orchestrator from the agent's completion report.

## Self-Check: PARTIAL

- [x] All tasks executed
- [x] Each task committed individually
- [x] Tests pass (23/23)
- [x] Revert-proof documented for SSH-01 (commit `e50cda1` body)
- [ ] SSH-02 mutation experiment with verbatim FAILED output (blocked — D-05)
- [x] SSH-02 detector catches the conservative subset (simple literal tautologies)
- [ ] SSH-02 detector catches `d25c915`'s exact mutation form (CRITICAL planning gap — needs follow-up)

**Recommendation for verifier:** This plan satisfies REG-01 #3 fully and REG-01 #4 partially. A phase-level gap ticket should capture the detector-scope extension so REG-01 #4 reaches full coverage.
