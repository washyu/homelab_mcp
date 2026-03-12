---
phase: 7
slug: mcp-resources-plumbing
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x with pytest-asyncio |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_mcp_resources.py -x -v` |
| **Full suite command** | `uv run pytest tests/ -m "not integration"` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_mcp_resources.py -x -v`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration"`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 0 | RES-01, RES-05, RES-06 | unit | `uv run pytest tests/test_mcp_resources.py -x` | ❌ W0 | ⬜ pending |
| 7-02-01 | 02 | 1 | RES-01 | unit | `uv run pytest tests/test_mcp_resources.py::test_list_resources_returns_resources -x` | ❌ W0 | ⬜ pending |
| 7-02-02 | 02 | 1 | RES-01 | unit | `uv run pytest tests/test_mcp_resources.py::test_capabilities_include_resources -x` | ❌ W0 | ⬜ pending |
| 7-03-01 | 03 | 1 | RES-05 | unit | `uv run pytest tests/test_mcp_resources.py::test_read_known_resource_returns_json -x` | ❌ W0 | ⬜ pending |
| 7-03-02 | 03 | 1 | RES-06 | unit | `uv run pytest tests/test_mcp_resources.py::test_read_unknown_resource_raises_mcp_error -x` | ❌ W0 | ⬜ pending |
| 7-04-01 | 04 | 1 | (subscribe) | unit | `uv run pytest tests/test_mcp_resources.py::test_subscribe_adds_to_tracker -x` | ❌ W0 | ⬜ pending |
| 7-04-02 | 04 | 1 | (subscribe) | unit | `uv run pytest tests/test_mcp_resources.py::test_unsubscribe_removes_from_tracker -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_mcp_resources.py` — stubs for RES-01, RES-05, RES-06, and subscribe/unsubscribe
- [ ] Verify `str(AnyUrl("homelab://vms"))` stringification behavior

*Existing test infrastructure in `tests/test_server.py` covers tools plumbing as a reference pattern. No fixture changes needed — tests call handler functions directly as async functions.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
