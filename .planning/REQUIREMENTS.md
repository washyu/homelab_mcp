# Requirements: Homelab MCP Server

**Defined:** 2026-04-20
**Core Value:** Every tool in the server actually works when a user calls it — a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.

## v1.6 Requirements

Requirements for the **Credential Architecture Cleanup** milestone. Makes the OS keyring the single source of truth for remote credentials; removes the parallel DB storage layer and hardcoded fallbacks that cause credential desync and silent wrong-user logins; adds cluster-scoped Proxmox API tokens.

### Credential Storage

- [ ] **CRED-04**: SSH credentials are stored exclusively in the OS keyring — the database `ssh_credentials` table is removed; no parallel credential storage exists in the server
- [ ] **CRED-05**: SSH tools no longer fall back to `mcp_admin` hardcoded defaults — when keyring returns no credential for a host, the tool raises an actionable error naming `credentials add`, not a silent default login

### Onboarding Surfaces

- [ ] **CRED-06**: The `setup_mcp_admin` MCP tool is removed from the server — device onboarding routes through the `credentials add` CLI and the existing `connect_to_device` prompt; no MCP tool writes credentials
- [ ] **CRED-07**: `register_server` validates credentials via the standard `resolve_ssh_credentials()` path before accepting registration — no verify-bypass path exists; registrations with missing/invalid credentials are rejected with an actionable error

### Cluster-Scoped Credentials

- [ ] **CRED-08**: Proxmox API tokens can be stored at cluster scope — one cluster credential automatically serves all N nodes in the same Proxmox datacenter; per-node tokens remain supported and take precedence when both exist

## Future Requirements

Deferred from v1.4.1/v1.5 and from v1.6 scoping discussions:

- **SSH-03**: Keyring auto-injection raises disambiguation error when multiple credentials match a hostname
- **SSH-04**: Per-call `timeout` forwarded to `ssh_connect()` handshake (not just outer `wait_for`)
- **SSH-05**: `verify_mcp_admin_access()` uses resolved port/credentials from `resolve_ssh_credentials()`
- **ERR-02**: `resolve_ssh_credentials()` wrapped in error handler — returns JSON error payloads, not raw exceptions
- **QUAL-01**: Proxmox VM creation schema enforces `iso`/`cdrom` mutual exclusivity via `oneOf`
- **HTTP-01**: HTTP mode flag accepts common truthy variants (`1`, `yes`, `on`), not just literal `"true"`

## Out of Scope

| Feature | Reason |
|---------|--------|
| Auto-migration tool for existing DB `ssh_credentials` rows → keyring | Users with credentials in the dropped DB table must re-add via `credentials add`; migration complexity not worth it for single-user homelab scope |
| Encrypted keyring backups / export | Homelab users manage their own keyring; backup is a platform concern, not an MCP concern |
| Per-request credential override via MCP tool args | Credentials resolved server-side only — no tool parameter accepts passwords; prevents credential leakage through protocol surfaces |
| Credential sharing between hosts (e.g., bastion + target) | Each hostname gets its own keyring entry; bastion chains out of scope for v1.6 |
| New SSH/Proxmox features | v1.6 is cleanup-only; new capabilities deferred to v1.7+ |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CRED-04 | Phase 33 | Pending |
| CRED-05 | Phase 33 | Pending |
| CRED-06 | Phase 33 | Pending |
| CRED-07 | Phase 33 | Pending |
| CRED-08 | Phase 34 | Pending |

**Coverage:**
- v1.6 requirements: 5 total
- Mapped to phases: 5
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-20*
*Last updated: 2026-04-20 after roadmap creation (Phases 33-34)*
