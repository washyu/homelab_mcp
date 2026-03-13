---
phase: 12
slug: pypi-distribution
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x with pytest-asyncio |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_packaging.py -x -v` |
| **Full suite command** | `uv run pytest tests/ -m "not integration" -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_packaging.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration" -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 1 | PKG-01 | unit | `uv run pytest tests/test_packaging.py::test_main_help -x` | ❌ W0 | ⬜ pending |
| 12-01-02 | 01 | 1 | PKG-01 | unit | `uv run pytest tests/test_packaging.py::test_main_module_entry -x` | ❌ W0 | ⬜ pending |
| 12-02-01 | 01 | 1 | PKG-02 | unit | `uv run pytest tests/test_packaging.py::test_version_unified -x` | ❌ W0 | ⬜ pending |
| 12-02-02 | 01 | 1 | PKG-02 | unit | `uv run pytest tests/test_packaging.py::test_server_version_dynamic -x` | ❌ W0 | ⬜ pending |
| 12-03-01 | 01 | 2 | PKG-03 | unit | `uv run pytest tests/test_service_installer.py -x -k "templates"` | ⚠️ partial | ⬜ pending |
| 12-03-02 | 01 | 2 | PKG-03 | manual | See Manual-Only Verifications | manual | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_packaging.py` — new file covering PKG-01 (`test_main_help`, `test_main_module_entry`) and PKG-02 (`test_version_unified`, `test_server_version_dynamic`)
- [ ] `tests/test_service_installer.py` — update patch target from module-level `TEMPLATES_DIR` constant to importlib.resources-based approach (constant is removed in this phase)

*Wave 0 must be committed before any implementation tasks.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Wheel zip contains `homelab_mcp/service_templates/*.yaml` | PKG-03 | Requires building the wheel artifact, cannot be tested in unit tests | Run `uv build && python -c "import zipfile, glob; whl=glob.glob('dist/*.whl')[0]; print([f for f in zipfile.ZipFile(whl).namelist() if 'service_templates' in f])"` — verify 10+ yaml files listed |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
