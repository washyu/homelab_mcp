---
phase: 29
slug: fix-deploy-service-workflow-phantom-tool
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 29 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x with pytest-asyncio |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_mcp_prompts.py -v` |
| **Full suite command** | `uv run pytest tests/ -m "not integration" -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_mcp_prompts.py -v`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration" -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 29-01-01 | 01 | 1 | gap-closure | unit | `uv run pytest tests/test_mcp_prompts.py -v` | ✅ | ⬜ pending |
| 29-01-02 | 01 | 1 | gap-closure | unit | `uv run pytest tests/test_mcp_prompts.py -v` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. `tests/test_mcp_prompts.py` already exists and tests the deploy_service_workflow prompt. No new test files or fixtures required.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
