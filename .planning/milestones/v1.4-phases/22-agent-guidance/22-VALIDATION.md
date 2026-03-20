---
phase: 22
slug: agent-guidance
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-15
---

# Phase 22 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_ssh_credentials.py tests/test_tools.py tests/test_shell_session.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -m "not integration" -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_ssh_credentials.py tests/test_tools.py tests/test_shell_session.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration" -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 22-01-01 | 01 | 1 | CRED-01 | unit | `uv run pytest tests/test_ssh_credentials.py::TestResolveSSHCredentials -x -k "no_credentials_raises"` | ✅ (new case) | ⬜ pending |
| 22-01-02 | 01 | 1 | CRED-02 | unit | `uv run pytest tests/test_tools.py -x -k "keyring"` | ✅ (new case) | ⬜ pending |
| 22-02-01 | 02 | 1 | CRED-03 | unit | `uv run pytest tests/test_tools.py -x -k "schema"` | ✅ (new case) | ⬜ pending |
| 22-02-02 | 02 | 1 | SHELL-04 | unit | `uv run pytest tests/test_shell_session.py -x -k "stdio"` | ✅ (new case) | ⬜ pending |
| 22-02-03 | 02 | 1 | SHELL-05 | unit | `uv run pytest tests/test_tools.py -x -k "schema"` | ✅ (new case) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ssh_credentials.py` — new test case for CRED-01 (raise on miss)
- [ ] `tests/test_tools.py` — new test cases for CRED-02 (tool count 56→57, tool registered), CRED-03/SHELL-05 (description checks)
- [ ] `tests/test_shell_session.py` — new test case for SHELL-04 (stdio guard error)

*Existing infrastructure covers all framework requirements; only new test cases needed.*

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
