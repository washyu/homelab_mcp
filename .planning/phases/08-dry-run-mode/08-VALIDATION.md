---
phase: 08
slug: dry-run-mode
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 08 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_dry_run.py -v` |
| **Full suite command** | `uv run pytest tests/ -m "not integration"` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_dry_run.py -v`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration"`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | DRY-07 | unit | `uv run pytest tests/test_dry_run.py::test_build_dry_run_response -v` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | DRY-01 | unit | `uv run pytest tests/test_dry_run.py::test_decommission_device_dry_run -v` | ❌ W0 | ⬜ pending |
| 08-01-03 | 01 | 1 | DRY-02 | unit | `uv run pytest tests/test_dry_run.py::test_remove_vm_dry_run -v` | ❌ W0 | ⬜ pending |
| 08-01-04 | 01 | 1 | DRY-03 | unit | `uv run pytest tests/test_dry_run.py::test_remove_server_dry_run -v` | ❌ W0 | ⬜ pending |
| 08-01-05 | 01 | 1 | DRY-04 | unit | `uv run pytest tests/test_dry_run.py::test_delete_proxmox_vm_dry_run -v` | ❌ W0 | ⬜ pending |
| 08-01-06 | 01 | 1 | DRY-05 | unit | `uv run pytest tests/test_dry_run.py::test_destroy_terraform_service_dry_run -v` | ❌ W0 | ⬜ pending |
| 08-01-07 | 01 | 1 | DRY-06 | unit | `uv run pytest tests/test_dry_run.py::test_rollback_infrastructure_dry_run -v` | ❌ W0 | ⬜ pending |
| 08-01-08 | 01 | 1 | DRY-01–06 | unit | `uv run pytest tests/test_dry_run.py::test_real_execution_unaffected -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_dry_run.py` — stubs for DRY-01 through DRY-07 (created before implementation tasks begin)
- [ ] `src/homelab_mcp/dry_run.py` — shared `build_dry_run_response()` helper skeleton

*Wave 0 must exist before Wave 1 implementation begins.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `dry_run: true` field visible in tool schema via MCP introspection | DRY-07 | Requires live MCP client | Connect Claude Desktop; call `tools/list`; inspect parameter schema for `decommission_device` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
