---
phase: 1
slug: architecture-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.5+ with pytest-asyncio 0.23.0+ |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `uv run pytest tests/ -m "not integration" -x --no-header -q` |
| **Full suite command** | `uv run pytest tests/ -m "not integration" -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -m "not integration" -x --no-header -q`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration" -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | ARCH-02 | unit | `uv run pytest tests/test_resource_manager.py -x` | No -- Wave 0 | pending |
| 01-01-02 | 01 | 1 | ARCH-02 | unit | `uv run pytest tests/test_tools.py -x` | Partial | pending |
| 01-02-01 | 02 | 1 | ARCH-01 | unit | `uv run pytest tests/test_server.py -x` | Yes (needs rewrite) | pending |
| 01-02-02 | 02 | 1 | ARCH-01 | unit | `uv run pytest tests/test_tools.py -x` | Yes (needs rewrite) | pending |
| 01-03-01 | 03 | 2 | FUNC-05 | unit | `uv run pytest tests/test_proxmox_api.py -x` | Yes (needs update) | pending |
| 01-04-01 | 04 | 2 | ARCH-03 | unit | `uv run pytest tests/test_server.py::test_graceful_shutdown -x` | No -- Wave 0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_resource_manager.py` -- stubs for ARCH-02 (ResourceManager init, connection provision, shutdown)
- [ ] `tests/test_server.py` -- needs rewrite for SDK-based server (covers ARCH-01, ARCH-03)
- [ ] `tests/test_proxmox_api.py` -- needs update for session pooling (covers FUNC-05)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Server handles SIGTERM/SIGINT in production | ARCH-03 | Requires signal delivery to running process | Start server, send SIGTERM, verify clean exit with no error output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
