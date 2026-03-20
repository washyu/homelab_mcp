---
phase: 24
slug: keyring-password-handling
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-15
---

# Phase 24 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `pyproject.toml` (asyncio_mode = "auto") |
| **Quick run command** | `uv run pytest tests/test_ssh_tools.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -m "not integration" -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_ssh_tools.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration" -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 24-01-01 | 01 | 1 | SETUP-01 | unit | `uv run pytest tests/test_ssh_tools.py::test_setup_remote_mcp_admin_uses_keyring -x` | ❌ W0 | ⬜ pending |
| 24-01-02 | 01 | 1 | SETUP-02 | unit | `uv run pytest tests/test_ssh_tools.py::test_setup_remote_mcp_admin_explicit_password -x` | ❌ W0 | ⬜ pending |
| 24-01-03 | 01 | 1 | SETUP-03 | unit | `uv run pytest tests/test_tools.py -k setup_mcp_admin -x` | ❌ W0 | ⬜ pending |
| 24-01-04 | 01 | 1 | GROUPS-01 | unit | `uv run pytest tests/test_ssh_tools.py::test_update_mcp_admin_groups_uses_keyring -x` | ❌ W0 | ⬜ pending |
| 24-01-05 | 01 | 1 | GROUPS-02 | unit | `uv run pytest tests/test_tools.py -k update_mcp_admin_groups -x` | ❌ W0 | ⬜ pending |
| 24-01-06 | 01 | 1 | AUDIT-01 | unit | `uv run pytest tests/test_tools.py::test_no_tool_has_password_required -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ssh_tools.py::test_setup_remote_mcp_admin_uses_keyring` — covers SETUP-01
- [ ] `tests/test_ssh_tools.py::test_update_mcp_admin_groups_uses_keyring` — covers GROUPS-01
- [ ] `tests/test_tools.py::test_setup_mcp_admin_schema_password_not_required` — covers SETUP-03
- [ ] `tests/test_tools.py::test_update_mcp_admin_groups_schema_password_not_required` — covers GROUPS-02
- [ ] `tests/test_tools.py::test_no_tool_has_password_required` — covers AUDIT-01 (regression guard)

*Existing infrastructure covers framework setup — only test stubs needed.*

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
