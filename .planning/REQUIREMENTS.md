# Requirements: Homelab MCP Server

**Defined:** 2026-03-13
**Core Value:** Every tool in the server actually works — a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.

## v1.4 Requirements

Requirements for v1.4 Real-World Reliability. Each maps to roadmap phases.

### Interactive Shell

- [x] **SHELL-01**: Interactive shell streams PTY output to browser in real time (non-blocking read loop)
- [x] **SHELL-02**: Interactive shell uses correct terminal dimensions (80 cols x 24 rows)
- [x] **SHELL-03**: Browser receives explicit EOF/error notification instead of hanging silently
- [ ] **SHELL-04**: `start_interactive_shell` returns actionable error in stdio mode instead of dead URL
- [ ] **SHELL-05**: `start_interactive_shell` schema description states browser-only requirement

### SSH Credential Flow

- [ ] **CRED-01**: `resolve_ssh_credentials` raises actionable error naming `credentials add` and `register_server` when all tiers miss
- [ ] **CRED-02**: Agent can inspect keyring credential state via `list_keyring_credentials` MCP tool
- [ ] **CRED-03**: `ssh_discover` and `ssh_execute_command` schema descriptions include credential recovery guidance

### TOFU Known Hosts

- [x] **TOFU-01**: `known_hosts` entries written with correct format (algorithm + base64 only, no comment field)
- [x] **TOFU-02**: `_tofu_lock` replaced with `threading.Lock` (dead `asyncio.Lock` removed)
- [ ] **TOFU-03**: `connect_to_device` MCP prompt sequences full device onboarding workflow
- [ ] **TOFU-04**: Warning logged when registry entry exists but keyring returns None (desync detection)

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
| SHELL-04 | Phase 22 | Pending |
| SHELL-05 | Phase 22 | Pending |
| CRED-01 | Phase 22 | Pending |
| CRED-02 | Phase 22 | Pending |
| CRED-03 | Phase 22 | Pending |
| TOFU-01 | Phase 21 | Complete |
| TOFU-02 | Phase 21 | Complete |
| TOFU-03 | Phase 23 | Pending |
| TOFU-04 | Phase 23 | Pending |

**Coverage:**
- v1.4 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-13*
*Last updated: 2026-03-13 after roadmap creation*
