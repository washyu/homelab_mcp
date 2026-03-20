---
phase: 28
slug: fix-prompt-parameter-names
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 28 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_mcp_prompts.py -v` |
| **Full suite command** | `uv run pytest tests/ -m "not integration"` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_mcp_prompts.py -v`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration"`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 28-01-01 | 01 | 0 | TOFU-03 | unit | `uv run pytest tests/test_mcp_prompts.py::test_connect_to_device_prompt_parameter_names -x` | ❌ W0 | ⬜ pending |
| 28-01-02 | 01 | 0 | TOFU-03 | unit | `uv run pytest tests/test_mcp_prompts.py::test_deploy_service_workflow_prompt_parameter_names -x` | ❌ W0 | ⬜ pending |
| 28-01-03 | 01 | 1 | TOFU-03 | unit | `uv run pytest tests/test_mcp_prompts.py -k "parameter_names" -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_mcp_prompts.py` — add `test_connect_to_device_prompt_parameter_names` (new function in existing file)
- [ ] `tests/test_mcp_prompts.py` — add `test_deploy_service_workflow_prompt_parameter_names` (new function in existing file)

*Framework install: not needed — pytest already installed and configured.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Agent successfully executes connect_to_device E2E | TOFU-03 | Requires live MCP agent + real host | Run connect_to_device prompt via MCP client against a test host; verify no schema validation errors |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
