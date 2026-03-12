---
phase: 11
slug: drift-detection
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `pyproject.toml` (existing) |
| **Quick run command** | `uv run pytest tests/test_drift_detection.py -x -v` |
| **Full suite command** | `uv run pytest tests/ -m "not integration"` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_drift_detection.py -x -v`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration"`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 0 | DRFT-01, DRFT-02, DRFT-03, DRFT-04, DRFT-05 | unit | `uv run pytest tests/test_drift_detection.py -x -v` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 | 0 | DRFT-04 | unit | `uv run pytest tests/test_database.py::TestDriftBaselines -x` | ❌ W0 | ⬜ pending |
| 11-02-01 | 02 | 1 | DRFT-04 | unit | `uv run pytest tests/test_database.py::TestDriftBaselines -x` | ❌ W0 | ⬜ pending |
| 11-02-02 | 02 | 1 | DRFT-03 | unit | `uv run pytest tests/test_drift_detection.py::TestConfigDrift -x` | ❌ W0 | ⬜ pending |
| 11-03-01 | 03 | 1 | DRFT-01, DRFT-02, DRFT-03 | unit | `uv run pytest tests/test_drift_detection.py -x -v` | ❌ W0 | ⬜ pending |
| 11-04-01 | 04 | 2 | DRFT-05 | unit | `uv run pytest tests/test_drift_detection.py::TestBaselineUpdate -x` | ❌ W0 | ⬜ pending |
| 11-05-01 | 05 | 2 | DRFT-01 | unit | `uv run pytest tests/test_drift_detection.py::TestScanDriftReport -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_drift_detection.py` — stubs for DRFT-01, DRFT-02, DRFT-03, DRFT-05 (new file)
- [ ] `tests/test_database.py::TestDriftBaselines` — stubs for DRFT-04 (add class to existing file)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SSH probe for state drift returns correct VM status | DRFT-02 | Requires live Proxmox + SSH environment | Start a VM, record baseline, stop VM via Proxmox UI, run `scan_infrastructure_drift`, verify VM appears in `state_drift` list |
| Config drift detected after manual CPU change in Proxmox | DRFT-03 | Requires live Proxmox environment | Create VM via MCP (baseline stored), change CPU count directly in Proxmox UI, run `scan_infrastructure_drift`, verify finding appears |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
