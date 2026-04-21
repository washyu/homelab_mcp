# Phase 32: Regression Tests - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-20
**Phase:** 32-regression-tests
**Areas discussed:** Test file placement, SSH-02 meta-test approach, WS-01 test depth

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Test file placement | Co-locate vs dedicated regression file | ✓ |
| SSH-02 meta-test approach | AST lint / behavioral / regex / none | ✓ |
| WS-01 test depth | Unit read_output / E2E handle_shell_websocket / both | ✓ |
| Coverage depth + markers | 5-test minimal vs paired; marker choice | |

**User skipped:** Coverage depth + markers — defaulted in CONTEXT.md "Claude's Discretion".

---

## Test File Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Co-locate in existing files (Recommended) | Regression tests live next to the code they guard, matching project convention | ✓ |
| Dedicated tests/test_pr39_regressions.py | Single file grouping all 5 guards; breaks co-location, better for audits | |
| Hybrid: co-locate + reference index | Co-locate + grep-friendly comment block | |

**User's choice:** Co-locate in existing files.
**Notes:** Matches tests/test_<module>.py convention already established across 20 unit test files.

### Follow-up — Naming

| Option | Description | Selected |
|--------|-------------|----------|
| Bug-ID prefix (Recommended) | test_ws01_*, test_err01_*, test_ssh01_*, test_ssh02_*, test_sch01_* — greppable, traceable | ✓ |
| Descriptive only | Natural language; loses requirement link | |
| Descriptive + docstring reference | Natural name plus "Regression guard for WS-01" in docstring | |

**User's choice:** Bug-ID prefix.
**Notes:** Enables `pytest -k ws01` and links tests directly to REQUIREMENTS.md entries without needing a custom marker.

---

## SSH-02 Meta-Test Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Static AST lint-style test (Recommended) | ast.parse on test_ssh_tools.py; fail on `assert X or Y` where Y is always-true | ✓ |
| Behavioral test only | Correct assertion + reviewer discipline; no automated meta-guard | |
| Regex-based guard | Text-level parse; quicker, more false positives | |
| No automated guard | Document in PR only; no recurrence protection | |

**User's choice:** Static AST lint-style test.
**Notes:** Automated guard with reasonable precision; uses stdlib ast module, no new dependencies.

### Follow-up — Scan scope

| Option | Description | Selected |
|--------|-------------|----------|
| Only test_ssh_tools.py (Recommended) | Matches literal REG-01 wording; tight scope | ✓ |
| All tests/ files | Broader safety net; expands scope | |
| All tests/ files, warn-only first | Hedge with cleanup pass; extra work | |

**User's choice:** Only test_ssh_tools.py.
**Notes:** Keeps Phase 32 scope locked to the listed 5 bugs; broader lint belongs in a future test-hardening phase.

---

## WS-01 Test Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Drive production handle_shell_websocket E2E (Recommended) | Starlette TestClient + mocked asyncssh; closes QUAL-02 | ✓ |
| Unit-test read_output alone | Mock websocket + mock session; simpler but does not prove finally-block cancellation | |
| Both | Unit coverage per break path + one E2E for task cancellation | |

**User's choice:** Drive production handle_shell_websocket E2E.
**Notes:** Side benefit — resolves QUAL-02 deferred item ("test_http_app.py EOF test drives production handler") without a separate plan.

### Follow-up — Break paths

| Option | Description | Selected |
|--------|-------------|----------|
| EOF only (Recommended) | Literal match for success criterion #1 | ✓ |
| EOF + error path | Two tests covering the two most-likely-to-regress locations | |
| All three break paths | EOF + no-stdout + error; matches the 3 new close() calls | |

**User's choice:** EOF only.
**Notes:** Literal success-criteria reading; error-path and no-stdout-path coverage deferred to future hardening.

---

## Claude's Discretion

Areas where the user deferred to Claude's judgement (recorded in CONTEXT.md D-defaults, not asked):

- **Coverage depth** — minimal 5 tests + 1 SSH-02 meta-test (paired negatives only if trivially cheap).
- **Pytest marker** — no custom `@pytest.mark.regression`; bug-ID prefix sufficient.
- **ERR-01 test mechanics** — dict-arg override path, assert message contains `effective_timeout`.
- **SCH-01 test mechanics** — schema-level enum assertion; framework-level rejection optional.
- **SSH-01 test mechanics** — positive-case only (password branch, `check=True`, non-zero exit → raises).

## Deferred Ideas

- Broader AST lint across all tests/ files — future test-hardening phase.
- Paired negative cases for SSH-01/SCH-01/WS-01 — add only if fixture reuse is free.
- `@pytest.mark.regression` marker — not needed for v1.5; revisit if REG-02+ lands.
- Medium/low CodeRabbit findings (SSH-03 through HTTP-01) — already deferred in REQUIREMENTS.md.
