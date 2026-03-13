---
phase: 13
slug: drift-resource
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_drift_resource.py -v` |
| **Full suite command** | `uv run pytest tests/ -m "not integration" -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_drift_resource.py -v`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration" -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 0 | DRFT-07 | unit | `uv run pytest tests/test_drift_resource.py::test_drift_resource_registered -v` | ❌ W0 | ⬜ pending |
| 13-01-02 | 01 | 0 | DRFT-08 | unit | `uv run pytest tests/test_drift_resource.py::test_drift_resource_empty_state -v` | ❌ W0 | ⬜ pending |
| 13-01-03 | 01 | 0 | DRFT-09 | unit | `uv run pytest tests/test_drift_resource.py::test_drift_resource_after_scan -v` | ❌ W0 | ⬜ pending |
| 13-01-04 | 01 | 0 | DRFT-10 | unit | `uv run pytest tests/test_drift_resource.py::test_drift_resource_notification -v` | ❌ W0 | ⬜ pending |
| 13-02-01 | 02 | 1 | DRFT-07 | unit | `uv run pytest tests/test_drift_resource.py::test_drift_resource_registered -v` | ✅ | ⬜ pending |
| 13-02-02 | 02 | 1 | DRFT-08 | unit | `uv run pytest tests/test_drift_resource.py::test_drift_resource_empty_state -v` | ✅ | ⬜ pending |
| 13-02-03 | 02 | 1 | DRFT-09 | unit | `uv run pytest tests/test_drift_resource.py::test_drift_resource_after_scan -v` | ✅ | ⬜ pending |
| 13-02-04 | 02 | 1 | DRFT-10 | unit | `uv run pytest tests/test_drift_resource.py::test_drift_resource_notification -v` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_drift_resource.py` — stubs for DRFT-07, DRFT-08, DRFT-09, DRFT-10

*Wave 0 plan creates RED tests before any implementation.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| MCP client receives `notifications/resources/updated` | DRFT-10 | Requires live MCP client session | Start server, subscribe to resource updates, run scan, verify notification received |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
