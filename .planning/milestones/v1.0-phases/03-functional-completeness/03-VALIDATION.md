---
phase: 3
slug: functional-completeness
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | pyproject.toml (pytest section) |
| **Quick run command** | `uv run pytest tests/ -m "not integration" -x -q` |
| **Full suite command** | `uv run pytest tests/ -m "not integration" -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -m "not integration" -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration" -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | FUNC-01 | unit | `uv run pytest tests/test_infrastructure_crud.py -k "sitemap_after_deploy" -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | FUNC-02 | unit | `uv run pytest tests/test_infrastructure_crud.py -k "rediscover_after_change" -x` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | FUNC-03 | unit | `uv run pytest tests/test_service_installer.py -k "install_script" -x` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | FUNC-04 | unit | `uv run pytest tests/test_silent_exceptions.py -x` | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 2 | MCP-01 | unit | `uv run pytest tests/test_server.py -k "annotations" -x` | ❌ W0 | ⬜ pending |
| 03-03-02 | 03 | 2 | MCP-02 | unit | `uv run pytest tests/test_server.py -k "is_error" -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_infrastructure_crud.py` — add tests for `_update_sitemap_after_deployment` and `_rediscover_device_after_changes`
- [ ] `tests/test_service_installer.py` — add test for `_install_script_service` with mocked SSH
- [ ] `tests/test_silent_exceptions.py` — AST-based test scanning for bare `except: pass` patterns
- [ ] `tests/test_server.py` — add tests for ToolAnnotations presence and isError on error results

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Script install on real host | FUNC-03 | Requires live SSH target | Deploy k3s on test VM via `install_service` tool |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
