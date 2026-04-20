# Phase 32: Regression Tests - Context

**Gathered:** 2026-04-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Add 5 pytest regression tests that lock down the Phase 31 bug fixes (WS-01, ERR-01, SSH-01, SSH-02, SCH-01). Each test must fail if the corresponding fix is reverted — one test per requirement, matching the literal phase success criteria.

Phase 31 is complete (both plans shipped on branch `v1.4` as commits `b0a5f33`, `9f752c0`, `bdb76bb`, `d25c915`). Tests are retroactive regression guards, not TDD Wave-0.

**In scope:**
- One regression test per requirement (5 total)
- An AST-based meta-test for SSH-02 (guards against test-assertion anti-pattern recurrence)
- Closing QUAL-02 deferred item as a natural side effect of the WS-01 E2E test

**Out of scope:**
- New product features
- Hardening tests for medium/low CodeRabbit findings (SSH-03 through HTTP-01) — deferred per REQUIREMENTS.md
- Broader lint-style anti-pattern scans across `tests/` — SSH-02 guard is scoped to `test_ssh_tools.py` only

</domain>

<decisions>
## Implementation Decisions

### Test File Placement
- **D-01:** Co-locate each regression in its subject test file following project convention:
  - WS-01 → `tests/test_http_app.py`
  - SSH-01, SSH-02 → `tests/test_ssh_tools.py`
  - ERR-01 → `tests/test_error_handling.py`
  - SCH-01 → `tests/test_tools.py` (where other schema-shape assertions live)
- **D-02:** Name every regression test with a bug-ID prefix so they are greppable and trace back to REQUIREMENTS.md:
  - `test_ws01_reader_closes_socket_on_pty_eof`
  - `test_err01_timeout_message_reports_effective_value`
  - `test_ssh01_sudo_run_check_raises_in_password_branch`
  - `test_ssh02_no_disjunctive_always_true_assertions` (the AST meta-test)
  - `test_sch01_credential_type_rejects_non_enum_values`

### SSH-02 Meta-Test Approach
- **D-03:** Implement SSH-02 as an AST-based lint-style test. The test opens `tests/test_ssh_tools.py`, parses it with `ast.parse`, walks every function body, and fails if any `ast.Assert` node's `test` is an `ast.BoolOp(op=Or, ...)` whose right operand is structurally always-true (e.g., a `BoolOp`/non-empty-string literal/other tautology).
- **D-04:** Scope the AST scan to `tests/test_ssh_tools.py` only — matches the literal REG-01 requirement wording ("password assertion in `test_ssh_tools.py` fails when password is not propagated"). Broader scans belong in a future test-hardening phase.
- **D-05:** The guard's own regression proof: the test is paired (in-commit) with a demonstration that the fixed `test_ssh_discover_no_credentials` assertion at line 191 passes the guard, AND a throwaway mutation (captured in the plan/commit message only, not checked in) showing the guard rejects `assert "No credentials" in err or "other" in err` when "other" is a tautological literal.

### WS-01 Test Depth
- **D-06:** Drive production `handle_shell_websocket` end-to-end using Starlette's `TestClient.websocket_connect()` against a minimal test app that registers `handle_shell_websocket` with a mocked `shell_session_manager`. Do NOT copy the handler into the test module (this is the behavior QUAL-02 flagged as a deferred issue).
- **D-07:** Cover the EOF path only — `session.process.stdout.read(4096)` returns empty bytes/string. The test asserts:
  1. The websocket receives the `"[Connection closed]"` marker before disconnect.
  2. The outer `receive_text()` loop raises `WebSocketDisconnect` (verifiable via `TestClient` context-manager exit or a status check).
  3. The paired `output_task` is cancelled — capture a reference to it via a test hook or assert via a `finally`-block observable (e.g., a flag set after `output_task.cancel()`).
- **D-08:** Error-path and no-stdout-path branches are accepted as out of scope for this phase. The EOF test exercises the same `contextlib.suppress(Exception)` close idiom — if that idiom regresses, the EOF test catches it. Future hardening can add the other two branches.

### QUAL-02 (Deferred Item, resolved as side effect)
- **D-09:** The WS-01 E2E test closes QUAL-02 ("`test_http_app.py` EOF regression test drives production `handle_shell_websocket`"). No separate plan required. Note this explicitly in the plan's commit message so `deferred-items.md` can be updated.

### Claude's Discretion

The user did not select "Coverage depth + markers" for discussion. Planner and researcher have latitude on the following, with these suggested defaults:

- **Coverage depth:** Minimal — one test per requirement (5 tests + 1 SSH-02 meta-test = 6 new tests total). Matches literal success criteria. Add negatives (e.g., `check=False` does not raise; valid `credential_type` values ARE accepted) only if they fall out naturally from fixture reuse.
- **Pytest marker:** No custom `@pytest.mark.regression` — bug-ID prefixes already make tests greppable via `pytest -k ws01` etc. Existing project markers (`unit`, `integration`, `slow`, etc.) are sufficient.
- **ERR-01 test mechanics:** Exercise `timeout_wrapper` with a dict-arg override (so `effective_timeout != timeout_seconds`), trigger `asyncio.TimeoutError`, and assert the error response's message contains the override value, not the decorator default.
- **SCH-01 test mechanics:** Assert at the schema level (read `list_keyring_credentials` inputSchema dict, verify `properties.credential_type.enum == ["ssh", "proxmox"]`). Optional second assertion: MCP framework rejects a call with `credential_type="bogus"` before the handler runs. Schema-level assertion alone meets REG-01; framework-level assertion is nice-to-have if simple.
- **SSH-01 test mechanics:** Positive test only — call `_sudo_run` with `password="pw"`, `check=True`, and a mocked `asyncssh.SSHClientConnection.run` that returns a non-zero exit (or raises `asyncssh.ProcessError`). Assert the error propagates. A paired `check=False` negative test is optional.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` — REG-01 and the 5 upstream bug requirements (WS-01, ERR-01, SSH-01, SSH-02, SCH-01). Section "v1.5 Requirements" is the source of truth.
- `.planning/ROADMAP.md` §"Phase 32: Regression Tests" — success criteria (5 reverted-fix-causes-test-fail items).

### Phase 31 Fix Record (what must be guarded)
- `.planning/phases/31-bug-fixes/31-01-SUMMARY.md` — documents ERR-01, SCH-01, SSH-02 fixes and their exact file/line locations. Explicitly notes ERR-01/SCH-01 regression tests were punted to "a follow-up test-hardening plan" = this phase.
- `.planning/phases/31-bug-fixes/31-02-SUMMARY.md` — documents WS-01 and SSH-01 fixes, including the 3 `websocket.close()` call sites in `read_output` and the `_sudo_run` helper structure.
- `.planning/phases/31-bug-fixes/deferred-items.md` — QUAL-02 note about the locally-copied `handle_shell_websocket` in current tests; WS-01 E2E test closes this.

### Source Files Under Test
- `src/homelab_mcp/http_app.py:185-240` — `handle_shell_websocket` and inner `read_output` coroutine; the 3 new `websocket.close()` calls are at lines 203, 207, 218.
- `src/homelab_mcp/ssh_tools.py:651-667` — `_sudo_run` helper with `check` parameter forwarding.
- `src/homelab_mcp/error_handling.py:50-58` — `timeout_wrapper` inner `wrapper` function; `effective_timeout` computed at line 50-53 and referenced in the error f-string at line 58.
- `src/homelab_mcp/tool_schemas/credential_tools_schema.py:~130` — `list_keyring_credentials.inputSchema.properties.credential_type.enum = ["ssh", "proxmox"]`.
- `tests/test_ssh_tools.py:180-192` — `test_ssh_discover_no_credentials`; the SSH-02 AST guard parses this file to verify no `assert X or <always-true>` recurrence.

### Commits That Introduced the Fixes
- `bdb76bb` (ERR-01 + SCH-01)
- `d25c915` (SSH-02)
- `b0a5f33` (WS-01)
- `9f752c0` (SSH-01)

### Test Framework & Conventions
- `.planning/codebase/TESTING.md` — pytest/pytest-asyncio config, mocking patterns (`@patch`, `AsyncMock`, fixtures), marker conventions.
- `pyproject.toml` §`[tool.pytest.ini_options]` — pytest config and marker list.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **pytest-asyncio + `AsyncMock`** — already used throughout `test_ssh_tools.py` and `test_http_app.py`; reuse the same `@patch("src.homelab_mcp.<module>.<symbol>", new_callable=AsyncMock)` decorator shape.
- **`test_http_app.py`** — 15 existing tests; one is the QUAL-02-flagged local-copy EOF test that the WS-01 regression replaces/supplements with an E2E driver.
- **`test_ssh_tools.py`** — 21 existing tests; `test_ssh_discover_no_credentials` at line 180-191 is the exact test SSH-02 was recorded against; `conn.run` mocking patterns from other tests apply directly to `_sudo_run`.
- **`test_error_handling.py`** — 27 existing tests for `timeout_wrapper`/`retry_wrapper`; ERR-01 test reuses the same decorator-invocation fixtures.
- **`test_tools.py`** — 36 existing tests for tool registry / schema shape; SCH-01 schema-level test reuses the tool-schema lookup pattern.

### Established Patterns
- **Co-location convention:** `tests/test_<module>.py` mirrors `src/homelab_mcp/<module>.py`. Phase 32 respects this strictly (D-01).
- **Module-level import for monkeypatching:** Confirmed in phases 18-19 accumulated context — patching requires production module to import symbols at module level, not lazily inside function bodies. Relevant for WS-01 mocking of `shell_session_manager` and for any asyncssh mocking.
- **Wave-0 TDD:** Not applicable here — this phase is retroactive regression (fixes already shipped). Tests are written GREEN from day 1; the "reverted fix causes test fail" proof happens outside the commit (in the plan's verification step).

### Integration Points
- **Starlette `TestClient.websocket_connect()`** — needs a minimal test app that registers the production `handle_shell_websocket` route; no existing fixture in `tests/test_http_app.py` today, so Phase 32 may introduce one.
- **AST walker for SSH-02** — `ast.parse(Path("tests/test_ssh_tools.py").read_text())` + `ast.walk`; pure stdlib, no new test dependency.
- **ERR-01 override shape** — `timeout_wrapper` accepts per-call overrides via dict args; the existing test file already demonstrates the override fixture shape.

</code_context>

<specifics>
## Specific Ideas

- **SSH-02 AST check reference:** The rejected anti-pattern shape is `ast.Assert(test=ast.BoolOp(op=ast.Or(), values=[<something>, <structurally_always_true>]))`. "Structurally always true" includes: non-empty `ast.Constant(value=str)`, another `ast.BoolOp(op=ast.Or())` where one side is a literal, or `ast.Compare` over two literal operands. Keep the detector conservative (high precision) so it does not flag legitimate `assert a or b` where both sides are dynamic.
- **WS-01 task-cancellation observable:** If asserting `output_task.cancelled()` directly is awkward inside `TestClient` context, set a flag in a `try/finally` patch injected via `monkeypatch` on the `read_output` inner function, or assert the `WebSocketDisconnect` exception is raised in the client. Planner to pick the simplest observable.
- **Naming:** All tests use snake_case bug-ID prefix followed by a human-readable slug (D-02). Ordering in files: place regression tests at the bottom of the existing file under a `# --- Regression guards (v1.5 / PR #39) ---` comment header for visual grouping without changing import structure.

</specifics>

<deferred>
## Deferred Ideas

- **Broader AST lint coverage** — scan all `tests/test_*.py` for `assert X or <always-true>` anti-patterns. Out of scope for Phase 32 (REG-01 is scoped to `test_ssh_tools.py`). Belongs in a future test-hardening or quality-gate phase.
- **Paired negative cases** — e.g., `_sudo_run(check=False)` does NOT raise; valid `credential_type` values ARE accepted; EOF vs error vs no-stdout coverage for WS-01. Optional; may be added if trivially cheap via fixture reuse, otherwise skip.
- **`@pytest.mark.regression` marker** — rejected for Phase 32 (bug-ID prefix is sufficient). Revisit if REG-02+ phases materialize and CI needs a dedicated regression selector.
- **Medium/low CodeRabbit items (SSH-03 → HTTP-01)** — already deferred in REQUIREMENTS.md "Future Requirements"; not in v1.5 scope.

</deferred>

---

*Phase: 32-regression-tests*
*Context gathered: 2026-04-20*
