# Requirements: Homelab MCP Server

**Defined:** 2026-03-13
**Core Value:** Every tool in the server actually works — a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.

## v1.4 Requirements

Requirements for v1.4 Real-World Reliability. Each maps to roadmap phases.

### Interactive Shell

- [x] **SHELL-01**: Interactive shell streams PTY output to browser in real time (non-blocking read loop)
- [x] **SHELL-02**: Interactive shell uses correct terminal dimensions (80 cols x 24 rows)
- [x] **SHELL-03**: Browser receives explicit EOF/error notification instead of hanging silently
- [x] **SHELL-04**: `start_interactive_shell` returns actionable error in stdio mode instead of dead URL
- [x] **SHELL-05**: `start_interactive_shell` schema description states browser-only requirement

### SSH Credential Flow

- [x] **CRED-01**: `resolve_ssh_credentials` raises actionable error naming `credentials add` and `register_server` when all tiers miss
- [x] **CRED-02**: Agent can inspect keyring credential state via `list_keyring_credentials` MCP tool
- [x] **CRED-03**: `ssh_discover` and `ssh_execute_command` schema descriptions include credential recovery guidance

### TOFU Known Hosts

- [x] **TOFU-01**: `known_hosts` entries written with correct format (algorithm + base64 only, no comment field)
- [x] **TOFU-02**: `_tofu_lock` replaced with `threading.Lock` (dead `asyncio.Lock` removed)
- [x] **TOFU-03**: `connect_to_device` MCP prompt sequences full device onboarding workflow
- [x] **TOFU-04**: Warning logged when registry entry exists but keyring returns None (desync detection)

### Keyring-based Password Handling

- [x] **SETUP-01**: `setup_mcp_admin` resolves credentials from keyring when no password argument is passed
- [x] **SETUP-02**: `setup_mcp_admin` accepts explicit password for backward compatibility (positional args still work)
- [x] **SETUP-03**: `setup_mcp_admin` schema has only `hostname` in `required` array (password and username optional)
- [x] **GROUPS-01**: `update_mcp_admin_groups` resolves credentials from keyring when no password argument is passed
- [x] **GROUPS-02**: `update_mcp_admin_groups` schema has only `hostname` in `required` array (password and username optional)
- [x] **AUDIT-01**: No tool schema in the project has `password` in its `required` array (regression guard)

### Sudo Password Piping

- [ ] **SUDO-01**: `_sudo_run` helper function pipes password via `conn.run(input=...)` when `creds.password` is available, falls back to plain `sudo` when no password
- [ ] **SUDO-02**: All `sudo` calls in `setup_remote_mcp_admin` use `_sudo_run` instead of raw `conn.run("sudo ...")`
- [ ] **SUDO-03**: All `sudo` calls in `update_mcp_admin_groups` use `_sudo_run` instead of raw `conn.run("sudo ...")`
- [ ] **SUDO-04**: Sudo failure produces actionable error distinguishing "wrong password" from "timeout" from "not in sudoers"
- [ ] **SUDO-05**: `ssh_execute_command` sudo path uses `conn.run(input=...)` instead of `echo password | sudo -S` shell injection

## Future Requirements

### Deferred from v1.4

- **TOFU-D1**: `trust_host_key` dedicated tool — only if transparent TOFU fix proves insufficient
- **CRED-D1**: `credentials verify <host>` CLI command — diagnostic tool
- **CRED-D2**: `ssh_credential_setup` prompt — full workflow walkthrough

## Out of Scope

| Feature | Reason |
|---------|--------|
| Rewrite SSH connection layer | Bugs are call-site fixes, not architectural — existing asyncssh integration is sound |
| New runtime dependencies | All fixes are code-level in existing stack |
| Credential migration tool | Two credential paths (keyring + DB) are complementary by design, not redundant |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SHELL-01 | Phase 21 | Complete |
| SHELL-02 | Phase 21 | Complete |
| SHELL-03 | Phase 21 | Complete |
| SHELL-04 | Phase 22 | Complete |
| SHELL-05 | Phase 22 | Complete |
| CRED-01 | Phase 22 | Complete |
| CRED-02 | Phase 22 | Complete |
| CRED-03 | Phase 22 | Complete |
| TOFU-01 | Phase 21 | Complete |
| TOFU-02 | Phase 21 | Complete |
| TOFU-03 | Phase 23 | Complete |
| TOFU-04 | Phase 23 | Complete |
| SETUP-01 | Phase 24 | Complete |
| SETUP-02 | Phase 24 | Complete |
| SETUP-03 | Phase 24 | Complete |
| GROUPS-01 | Phase 24 | Complete |
| GROUPS-02 | Phase 24 | Complete |
| AUDIT-01 | Phase 24 | Complete |
| SUDO-01 | Phase 25 | Planned |
| SUDO-02 | Phase 25 | Planned |
| SUDO-03 | Phase 25 | Planned |
| SUDO-04 | Phase 25 | Planned |
| SUDO-05 | Phase 25 | Planned |

**Coverage:**
- v1.4 requirements: 23 total
- Mapped to phases: 23
- Unmapped: 0

---
*Requirements defined: 2026-03-13*
*Last updated: 2026-03-15 after Phase 25 planning*
