---
phase: 9
slug: mcp-resources-live-data
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | `pytest.ini` / `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_resources.py -v` |
| **Full suite command** | `uv run pytest tests/ -m "not integration" -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_resources.py -v`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration" -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 9-01-01 | 01 | 1 | RES-02 | unit | `uv run pytest tests/test_resources.py::test_vms_resource_returns_live_data -v` | ❌ W0 | ⬜ pending |
| 9-01-02 | 01 | 1 | RES-02 | unit | `uv run pytest tests/test_resources.py::test_vms_resource_has_scanned_at -v` | ❌ W0 | ⬜ pending |
| 9-02-01 | 02 | 1 | RES-03 | unit | `uv run pytest tests/test_resources.py::test_devices_resource_returns_live_data -v` | ❌ W0 | ⬜ pending |
| 9-02-02 | 02 | 1 | RES-03 | unit | `uv run pytest tests/test_resources.py::test_devices_resource_has_last_seen -v` | ❌ W0 | ⬜ pending |
| 9-03-01 | 03 | 2 | RES-04 | unit | `uv run pytest tests/test_resources.py::test_services_resource_returns_status -v` | ❌ W0 | ⬜ pending |
| 9-03-02 | 03 | 2 | RES-04 | unit | `uv run pytest tests/test_resources.py::test_services_resource_uri_template -v` | ❌ W0 | ⬜ pending |
| 9-04-01 | 04 | 2 | RES-02,03,04 | unit | `uv run pytest tests/test_resources.py::test_all_resources_have_scanned_at -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_resources.py` — stubs for RES-02, RES-03, RES-04 (live data, scanned_at timestamp, URI template dispatch)
- [ ] `tests/conftest.py` — update shared fixtures with mock db_adapter, mock resource_manager

*Existing pytest infrastructure covers the framework; only test stubs are new.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `homelab://services/{name}` returns live SSH status against a real host | RES-04 | Requires live SSH host and running service | Run `uv run python run_server.py`, call `resources/read` with `homelab://services/nginx`, verify `running` field |
| `homelab://vms` returns VMs from real Proxmox API | RES-02 | Requires live Proxmox instance | Configure `PROXMOX_HOST` env var, call `resources/read` with `homelab://vms`, verify non-empty VM list |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
