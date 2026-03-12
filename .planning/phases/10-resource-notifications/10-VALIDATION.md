---
phase: 10
slug: resource-notifications
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_mcp_resources.py -x` |
| **Full suite command** | `uv run pytest tests/ -m "not integration" -x` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_mcp_resources.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration" -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | RES-07 | unit | `uv run pytest tests/test_mcp_resources.py::test_discover_and_map_sends_list_changed -x` | ❌ W0 | ⬜ pending |
| 10-01-02 | 01 | 1 | RES-07 | unit | `uv run pytest tests/test_mcp_resources.py::test_bulk_discover_and_map_sends_list_changed -x` | ❌ W0 | ⬜ pending |
| 10-01-03 | 01 | 1 | RES-07 | unit | `uv run pytest tests/test_mcp_resources.py::test_dry_run_does_not_send_notification -x` | ❌ W0 | ⬜ pending |
| 10-01-04 | 01 | 1 | RES-07 | unit | `uv run pytest tests/test_mcp_resources.py::test_ssh_discover_no_notification -x` | ❌ W0 | ⬜ pending |
| 10-01-05 | 01 | 1 | RES-07 | unit | `uv run pytest tests/test_mcp_resources.py::test_error_result_no_notification -x` | ❌ W0 | ⬜ pending |
| 10-01-06 | 01 | 1 | RES-07 | unit | `uv run pytest tests/test_mcp_resources.py::test_no_context_no_crash -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_mcp_resources.py` — add 6 notification dispatch test stubs (file exists, extend it)

*All Wave 0 gaps are additions to an existing test file — no new files needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Client cache stays coherent after device discovery | RES-07 | Requires real MCP client connection | Connect Claude Desktop, run `discover_and_map`, observe resource list refresh |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
