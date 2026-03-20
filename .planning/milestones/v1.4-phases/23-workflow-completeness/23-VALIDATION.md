---
phase: 23
slug: workflow-completeness
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-15
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_mcp_prompts.py tests/test_ssh_credentials.py -x` |
| **Full suite command** | `uv run pytest tests/ -m "not integration"` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_mcp_prompts.py tests/test_ssh_credentials.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration"`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 23-01-01 | 01 | 0 | TOFU-03 | unit | `uv run pytest tests/test_mcp_prompts.py -k connect_to_device -x` | ❌ W0 | ⬜ pending |
| 23-01-02 | 01 | 1 | TOFU-03 | unit | `uv run pytest tests/test_mcp_prompts.py -k connect_to_device -x` | ❌ W0 | ⬜ pending |
| 23-02-01 | 02 | 0 | TOFU-04 | unit | `uv run pytest tests/test_ssh_credentials.py -k desync -x` | ❌ W0 | ⬜ pending |
| 23-02-02 | 02 | 1 | TOFU-04 | unit | `uv run pytest tests/test_ssh_credentials.py -k desync -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_mcp_prompts.py::test_connect_to_device_prompt` — stubs for TOFU-03
- [ ] `tests/test_ssh_credentials.py::TestResolveSSHCredentials::test_desync_warning_logged` — stubs for TOFU-04

*Existing infrastructure covers all framework requirements.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
