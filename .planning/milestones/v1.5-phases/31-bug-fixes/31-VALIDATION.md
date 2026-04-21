---
phase: 31
slug: bug-fixes
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-02
---

# Phase 31 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (with pytest-asyncio) |
| **Config file** | `pytest.ini` |
| **Quick run command** | `uv run pytest tests/test_ssh_tools.py tests/test_error_handling.py tests/test_tools.py tests/test_http_app.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -m "not integration" -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_ssh_tools.py tests/test_error_handling.py tests/test_tools.py tests/test_http_app.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration" -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 31-01-01 | 01 | 1 | WS-01 | unit | `uv run pytest tests/test_http_app.py -k "websocket" -x` | Partial | ⬜ pending |
| 31-02-01 | 02 | 1 | ERR-01 | unit | `uv run pytest tests/test_error_handling.py -k "timeout" -x` | Partial | ⬜ pending |
| 31-03-01 | 03 | 1 | SSH-01 | unit | `uv run pytest tests/test_ssh_tools.py -k "sudo_run" -x` | ❌ W0 | ⬜ pending |
| 31-04-01 | 04 | 1 | SSH-02 | unit | `uv run pytest tests/test_ssh_tools.py -k "no_credentials" -x` | Fix existing | ⬜ pending |
| 31-05-01 | 05 | 1 | SCH-01 | unit | `uv run pytest tests/test_tools.py -k "credential" -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ssh_tools.py` — add `test_sudo_run_check_true_raises_with_password` and `test_sudo_run_check_true_raises_without_password` (SSH-01)
- [ ] `tests/test_tools.py` — add `test_credential_type_schema_has_enum` (SCH-01)
- [ ] `tests/test_error_handling.py` — add `test_timeout_wrapper_reports_effective_timeout_on_override` (ERR-01)
- [ ] `tests/test_http_app.py` — add `test_handle_shell_websocket_eof_closes_socket_and_cancels_task` (WS-01)
- [ ] Fix existing test: `tests/test_ssh_tools.py` line 191 — remove always-true `or` branch (SSH-02)

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
