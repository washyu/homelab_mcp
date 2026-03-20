---
phase: 21
slug: core-ssh-reliability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 21 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x with pytest-asyncio |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_ssh_connection.py tests/test_shell_session.py -v` |
| **Full suite command** | `uv run pytest tests/ -m "not integration" -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_ssh_connection.py tests/test_shell_session.py -v`
- **After every plan wave:** Run `uv run pytest tests/ -m "not integration" -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 21-01-01 | 01 | 1 | TOFU-01 | unit | `uv run pytest tests/test_ssh_connection.py -k "known_hosts_format" -v` | ❌ W0 | ⬜ pending |
| 21-01-02 | 01 | 1 | TOFU-02 | unit | `uv run pytest tests/test_ssh_connection.py -k "tofu_lock" -v` | ❌ W0 | ⬜ pending |
| 21-02-01 | 02 | 1 | SHELL-02 | unit | `uv run pytest tests/test_shell_session.py -k "term_size" -v` | ❌ W0 | ⬜ pending |
| 21-02-02 | 02 | 1 | SHELL-01 | unit | `uv run pytest tests/test_shell_session.py -k "streaming" -v` | ❌ W0 | ⬜ pending |
| 21-02-03 | 02 | 1 | SHELL-03 | unit | `uv run pytest tests/test_shell_session.py -k "eof_notification" -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ssh_connection.py` — add TOFU-01 known_hosts format test and TOFU-02 threading.Lock test
- [ ] `tests/test_shell_session.py` — create new file with SHELL-01 streaming, SHELL-02 term_size, SHELL-03 EOF notification tests

*Existing test_ssh_connection.py exists but lacks format-verification tests.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Interactive shell streams in browser | SHELL-01 | Requires running HTTP server + browser WebSocket | Start server with `MCP_HTTP_PORT=8080`, open shell URL in browser, verify characters appear as typed |
| SSH discover on keyring-only host | TOFU-01 | Requires real SSH target | Run `homelab-mcp credentials add`, then call `ssh_discover` via MCP client |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
