# Requirements: Homelab MCP Server

**Defined:** 2026-03-20
**Core Value:** Every tool in the server actually works when a user calls it — a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.

## v1.5 Requirements

Requirements for the Security & Correctness Hardening milestone. All requirements sourced from CodeRabbit review of PR #39.

### Security

- [x] **SEC-01**: The `setup_mcp_admin` and `add_to_sudoers` commands never interpolate public key content directly into remote shell strings — keys are transferred via a safe transport (tmpfile or heredoc)
- [x] **SEC-02**: The TOFU existence check and append both execute under `_tofu_lock` — concurrent first-connections cannot write conflicting keys for the same host

### SSH Reliability

- [ ] **SSH-01**: Keyring auto-injection raises a disambiguation error when multiple credentials exist for a hostname and no `username` is specified — no silent wrong-user logins
- [ ] **SSH-02**: The per-call `timeout` argument is forwarded to `ssh_connect()` so the connection handshake respects the caller's timeout, not only the outer `asyncio.wait_for`
- [ ] **SSH-03**: `verify_mcp_admin_access()` uses the port and credentials returned by `resolve_ssh_credentials()` — not the raw caller-supplied arguments

### Error Handling

- [ ] **ERR-01**: `resolve_ssh_credentials()` is called inside the error-handled section of every function that uses it — `CredentialNotFoundError` returns a JSON error payload, never an unhandled exception
- [ ] **ERR-02**: The WebSocket PTY reader closes the websocket and cancels the paired task when it hits EOF or an error — no dead sessions left open indefinitely

### Schema & Tests

- [ ] **QUAL-01**: The Proxmox VM creation schema enforces that `iso` and `cdrom` are mutually exclusive — the API rejects requests that specify both
- [ ] **QUAL-02**: The `test_http_app.py` EOF regression test drives the production `handle_shell_websocket` function — not a locally duplicated `read_output()` copy

## Future Requirements

None identified at this time.

## Out of Scope

| Feature | Reason |
|---------|--------|
| New SSH tools or capabilities | v1.5 is fixes-only; new features deferred to v1.6+ |
| Refactoring beyond PR findings | Scope limited to the 9 CodeRabbit findings |
| Performance improvements | No performance issues identified in review |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEC-01 | Phase 30 | Complete |
| SEC-02 | Phase 30 | Complete |
| SSH-01 | Phase 31 | Pending |
| SSH-02 | Phase 31 | Pending |
| SSH-03 | Phase 31 | Pending |
| ERR-01 | Phase 32 | Pending |
| ERR-02 | Phase 32 | Pending |
| QUAL-01 | Phase 32 | Pending |
| QUAL-02 | Phase 32 | Pending |

**Coverage:**
- v1.5 requirements: 9 total
- Mapped to phases: 9
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-20*
*Last updated: 2026-03-20 after roadmap creation*
