---
phase: 16
slug: quality-gate
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Direct tool invocation (ruff, mypy, bandit) + pytest 8.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run ruff check src/ tests/ && uv run mypy src/ && uv run bandit -r src/` |
| **Full suite command** | `uv run pytest tests/ -m "not integration" -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run ruff check src/ tests/ && uv run mypy src/ && uv run bandit -r src/`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration" -q`
- **Before `/gsd:verify-work`:** All three quality tools must exit 0
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 01 | 1 | QA-01 | smoke | `uv run mypy src/` | ✅ pyproject.toml | ⬜ pending |
| 16-01-02 | 01 | 1 | QA-01 | smoke | `uv run bandit -r src/` | ✅ src/homelab_mcp/config.py | ⬜ pending |
| 16-01-03 | 01 | 1 | QA-01 | smoke | `uv run bandit -r src/` | ✅ src/homelab_mcp/database.py | ⬜ pending |
| 16-01-04 | 01 | 1 | QA-01 | smoke | `uv run bandit -r src/` | ✅ src/homelab_mcp/infrastructure_crud.py | ⬜ pending |
| 16-01-05 | 01 | 1 | QA-01 | smoke | `uv run ruff check src/ tests/ && uv run mypy src/ && uv run bandit -r src/` | ✅ all | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

*No new test files needed — quality checks are the verification mechanism for this phase.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| bandit auto-detects pyproject.toml | QA-01 | Exit code behavior depends on project root config auto-detection | Run `uv run bandit -r src/` from project root; observe whether B101/B601 skips apply without `-c pyproject.toml` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
