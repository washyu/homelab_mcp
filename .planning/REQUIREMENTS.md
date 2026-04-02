# Requirements: Homelab MCP Server

**Defined:** 2026-04-02
**Core Value:** Every tool in the server actually works when a user calls it — a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.

## v1.5 Requirements

Requirements for the Critical Bug Fixes milestone. All sourced from CodeRabbit review of PR #39 (critical and high priority only).

### WebSocket

- [ ] **WS-01**: The PTY reader closes the websocket and cancels the paired task when it hits EOF or an error — no zombie sessions left open indefinitely

### Error Handling

- [ ] **ERR-01**: The timeout error message in `error_handling.py` reports the computed `effective_timeout` value, not the raw `timeout_seconds` parameter

### SSH Tools

- [ ] **SSH-01**: `_sudo_run` with `check=True` raises an error on non-zero exit code in the password branch — not just in the no-password branch
- [ ] **SSH-02**: The `test_ssh_tools.py` password propagation assertion uses explicit checks, not a broken ternary that passes unconditionally

### Schema

- [ ] **SCH-01**: The `credential_type` parameter in the credentials tool schema is constrained to `enum: ["ssh", "proxmox"]` — arbitrary strings rejected

### Regression Tests

- [ ] **REG-01**: Regression tests exist for all 5 fixes above, preventing recurrence of each specific bug

## Future Requirements

Deferred from v1.4.1 and CodeRabbit review (medium/low priority):

- **SSH-03**: Keyring auto-injection raises disambiguation error for multiple credentials per hostname
- **SSH-04**: Per-call `timeout` forwarded to `ssh_connect()` handshake
- **SSH-05**: `verify_mcp_admin_access()` uses resolved port/credentials from `resolve_ssh_credentials()`
- **ERR-02**: `resolve_ssh_credentials()` called inside error-handled section — returns JSON error, not unhandled exception
- **QUAL-01**: Proxmox VM creation schema enforces `iso`/`cdrom` mutual exclusivity
- **QUAL-02**: `test_http_app.py` EOF regression test drives production `handle_shell_websocket`
- **HTTP-01**: HTTP mode flag accepts common truthy variants (`1`, `yes`, `on`), not just literal `"true"`

## Out of Scope

| Feature | Reason |
|---------|--------|
| New tools or capabilities | v1.5 is fixes-only; new features deferred to v1.6+ |
| SSH reliability improvements | Medium priority; deferred to future milestone |
| Refactoring beyond PR findings | Scope limited to critical/high CodeRabbit findings |
| Performance improvements | No performance issues identified in review |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| WS-01 | — | Pending |
| ERR-01 | — | Pending |
| SSH-01 | — | Pending |
| SSH-02 | — | Pending |
| SCH-01 | — | Pending |
| REG-01 | — | Pending |

**Coverage:**
- v1.5 requirements: 6 total
- Mapped to phases: 0
- Unmapped: 6 ⚠️

---
*Requirements defined: 2026-04-02*
*Last updated: 2026-04-02 after initial definition*
