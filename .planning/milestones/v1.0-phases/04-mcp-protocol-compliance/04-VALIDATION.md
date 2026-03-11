---
phase: 4
slug: mcp-protocol-compliance
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/ -m "not integration" -x` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -m "not integration" -x`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | MCP-03 | unit | `uv run pytest tests/test_server.py -x -k logging` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | MCP-03 | unit | `uv run pytest tests/test_logging_notifications.py -x` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | MCP-03 | unit | `uv run pytest tests/test_logging_notifications.py -x -k no_context` | ❌ W0 | ⬜ pending |
| 04-01-04 | 01 | 1 | MCP-03 | unit | `uv run pytest tests/test_logging_notifications.py -x -k bulk` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 1 | MCP-04 | unit | `uv run pytest tests/test_http_app.py -x -k origin` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 1 | MCP-04 | unit | `uv run pytest tests/test_http_app.py -x -k origin_allowed` | ❌ W0 | ⬜ pending |
| 04-02-03 | 02 | 1 | MCP-04 | unit | `uv run pytest tests/test_http_app.py -x -k no_origin` | ❌ W0 | ⬜ pending |
| 04-02-04 | 02 | 1 | MCP-04 | integration | `uv run pytest tests/test_http_app.py -x -k session` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_logging_notifications.py` — stubs for MCP-03 (emit_progress, level filtering, graceful degradation)
- [ ] `tests/test_http_app.py` — new test cases for Origin validation (MCP-04)

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
