---
phase: 14
slug: mcp-prompts
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (installed) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_mcp_prompts.py -x` |
| **Full suite command** | `uv run pytest tests/ -m "not integration"` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_mcp_prompts.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration"`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 0 | PRMT-01 | unit | `uv run pytest tests/test_mcp_prompts.py::test_prompts_capability_advertised -x` | ❌ W0 | ⬜ pending |
| 14-01-02 | 01 | 0 | PRMT-01 | unit | `uv run pytest tests/test_mcp_prompts.py::test_list_prompts_returns_prompts -x` | ❌ W0 | ⬜ pending |
| 14-01-03 | 01 | 0 | PRMT-02 | unit | `uv run pytest tests/test_mcp_prompts.py::test_decommission_workflow_prompt -x` | ❌ W0 | ⬜ pending |
| 14-01-04 | 01 | 0 | PRMT-03 | unit | `uv run pytest tests/test_mcp_prompts.py::test_deploy_service_workflow_prompt -x` | ❌ W0 | ⬜ pending |
| 14-01-05 | 01 | 0 | PRMT-04 | unit | `uv run pytest tests/test_mcp_prompts.py::test_health_check_prompt_resources -x` | ❌ W0 | ⬜ pending |
| 14-01-06 | 01 | 0 | PRMT-01 | unit | `uv run pytest tests/test_mcp_prompts.py::test_get_unknown_prompt_raises_mcp_error -x` | ❌ W0 | ⬜ pending |
| 14-02-01 | 02 | 1 | PRMT-01 | unit | `uv run pytest tests/test_mcp_prompts.py::test_prompts_capability_advertised -x` | ✅ | ⬜ pending |
| 14-02-02 | 02 | 1 | PRMT-01 | unit | `uv run pytest tests/test_mcp_prompts.py::test_list_prompts_returns_prompts -x` | ✅ | ⬜ pending |
| 14-03-01 | 03 | 1 | PRMT-02 | unit | `uv run pytest tests/test_mcp_prompts.py::test_decommission_workflow_prompt -x` | ✅ | ⬜ pending |
| 14-03-02 | 03 | 1 | PRMT-03 | unit | `uv run pytest tests/test_mcp_prompts.py::test_deploy_service_workflow_prompt -x` | ✅ | ⬜ pending |
| 14-03-03 | 03 | 1 | PRMT-04 | unit | `uv run pytest tests/test_mcp_prompts.py::test_health_check_prompt_resources -x` | ✅ | ⬜ pending |
| 14-03-04 | 03 | 1 | PRMT-01 | unit | `uv run pytest tests/test_mcp_prompts.py::test_get_unknown_prompt_raises_mcp_error -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_mcp_prompts.py` — stub tests for PRMT-01, PRMT-02, PRMT-03, PRMT-04
- [ ] `src/homelab_mcp/prompt_registry.py` — does not exist yet (Wave 0 tests import it as a stub)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `initialize` response includes `"prompts"` key via live MCP client | PRMT-01 | Requires a real MCP client/inspector session | Run `uv run python run_server.py` and connect with MCP Inspector; confirm `initialize` response capabilities |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
