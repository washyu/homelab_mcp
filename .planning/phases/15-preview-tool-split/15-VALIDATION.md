---
phase: 15
slug: preview-tool-split
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `pyproject.toml` (pytest section) |
| **Quick run command** | `uv run pytest tests/test_server.py tests/test_tools.py -x` |
| **Full suite command** | `uv run pytest tests/ -m "not integration"` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_server.py tests/test_tools.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration"`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 15-01-01 | 01 | 0 | PREV-01..08 | unit | `uv run pytest tests/test_preview_tools.py -x` | ❌ W0 | ⬜ pending |
| 15-01-02 | 01 | 0 | PREV-07 | unit | `uv run pytest tests/test_server.py::test_annotation_count_matches_tool_count -x` | ✅ | ⬜ pending |
| 15-01-03 | 01 | 0 | PREV-01..08 | unit | `uv run pytest tests/test_tools.py -x` (count update) | ✅ | ⬜ pending |
| 15-02-01 | 02 | 1 | PREV-01 | unit | `uv run pytest tests/test_preview_tools.py::test_decommission_device_preview_returns_dry_run -x` | ❌ W0 | ⬜ pending |
| 15-02-02 | 02 | 1 | PREV-02 | unit | `uv run pytest tests/test_preview_tools.py::test_delete_proxmox_vm_preview_returns_dry_run -x` | ❌ W0 | ⬜ pending |
| 15-02-03 | 02 | 1 | PREV-03 | unit | `uv run pytest tests/test_preview_tools.py::test_remove_vm_preview_returns_dry_run -x` | ❌ W0 | ⬜ pending |
| 15-02-04 | 02 | 1 | PREV-04 | unit | `uv run pytest tests/test_preview_tools.py::test_remove_server_preview_returns_dry_run -x` | ❌ W0 | ⬜ pending |
| 15-02-05 | 02 | 1 | PREV-05 | unit | `uv run pytest tests/test_preview_tools.py::test_destroy_terraform_service_preview_returns_dry_run -x` | ❌ W0 | ⬜ pending |
| 15-02-06 | 02 | 1 | PREV-06 | unit | `uv run pytest tests/test_preview_tools.py::test_rollback_infrastructure_changes_preview_returns_dry_run -x` | ❌ W0 | ⬜ pending |
| 15-03-01 | 03 | 1 | PREV-07 | unit | `uv run pytest tests/test_preview_tools.py::test_preview_tools_have_readonly_annotation -x` | ❌ W0 | ⬜ pending |
| 15-03-02 | 03 | 1 | PREV-08 | unit | `uv run pytest tests/test_preview_tools.py::test_original_destructive_tools_still_present -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_preview_tools.py` — stubs for PREV-01 through PREV-08 (new file, local imports inside test function bodies)
- [ ] Update `tests/test_tools.py` line ~16 assertion: `len(tools) == 50` → `len(tools) == 56`

*Wave 0 stubs are RED at commit — they go GREEN after implementation in Wave 1.*

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
