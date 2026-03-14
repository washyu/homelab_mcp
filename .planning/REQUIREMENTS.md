# Requirements: Homelab MCP Server

**Defined:** 2026-03-14
**Core Value:** Every tool in the server actually works — a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.

## v1.3 Requirements

### Credential Store

- [ ] **CRED-01**: User can store SSH credentials for a host with `homelab-mcp credentials add <host> <user>` (password prompted securely, never via CLI arg)
- [ ] **CRED-02**: User can list stored SSH credential hostnames with `homelab-mcp credentials list`
- [ ] **CRED-03**: User can remove stored SSH credentials with `homelab-mcp credentials remove <host>`
- [ ] **CRED-04**: User can store Proxmox credentials with `homelab-mcp credentials add --type proxmox <host> <user>` (token/password prompted securely)
- [ ] **CRED-05**: User can list stored Proxmox credential hosts with `homelab-mcp credentials list --type proxmox`
- [ ] **CRED-06**: User can remove stored Proxmox credentials with `homelab-mcp credentials remove --type proxmox <host>`
- [ ] **CRED-07**: Server warns and falls back gracefully to env-var-only mode when OS keyring is unavailable (headless Linux, no D-Bus)

### Credential Auto-Inject

- [ ] **INJECT-01**: SSH tools automatically fill username/password from keyring when hostname matches a stored credential
- [ ] **INJECT-02**: Explicitly passed tool arguments take precedence over stored credentials (explicit > keyring > default key)
- [ ] **INJECT-03**: Proxmox connection falls back to keyring when PROXMOX_HOST/PROXMOX_TOKEN env vars are absent

### Release Automation

- [ ] **CICD-01**: PyPI publish triggered automatically when a `v*` git tag is pushed to main
- [ ] **CICD-02**: Publish uses OIDC trusted publishing — no API tokens stored in GitHub secrets
- [ ] **CICD-03**: Publish job only runs after the test-and-quality job passes

### CLI Polish

- [ ] **CLI-01**: `homelab-mcp --version` prints the installed package version
- [ ] **CLI-02**: `decommission_device_workflow` prompt instructs AI to resolve hostname → device_id before calling the decommission tool (fixes PRMT-02)

## Future Requirements

### Credential Store

- **CRED-F01**: Encrypted JSON fallback store for environments with no OS keyring support
- **CRED-F02**: Import credentials from a plain JSON file (bulk load for initial setup)
- **CRED-F03**: Per-credential SSH key path storage (separate from password)

### Release

- **CICD-F01**: Git-tag-derived versioning via `hatch-vcs` (eliminates version/tag mismatch risk)
- **CICD-F02**: Automated changelog generation from commit messages on release

## Out of Scope

| Feature | Reason |
|---------|--------|
| Credential encryption at rest (beyond OS keyring) | OS keyring provides system-level encryption; adding a second layer adds complexity without value for single-user homelab |
| Multi-user credential namespacing | Homelab is single-operator — out of scope per existing PROJECT.md constraint |
| Web UI for credential management | MCP clients provide the interface |
| Credential rotation / expiry | Not needed for homelab SSH/Proxmox credentials |
| `--password` CLI flag | Shell history exposure risk; always use `getpass.getpass()` instead |
| Separate `publish.yml` workflow file | Research recommends adding publish job to existing `main.yml` with strict tag filter |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CRED-01 | — | Pending |
| CRED-02 | — | Pending |
| CRED-03 | — | Pending |
| CRED-04 | — | Pending |
| CRED-05 | — | Pending |
| CRED-06 | — | Pending |
| CRED-07 | — | Pending |
| INJECT-01 | — | Pending |
| INJECT-02 | — | Pending |
| INJECT-03 | — | Pending |
| CICD-01 | — | Pending |
| CICD-02 | — | Pending |
| CICD-03 | — | Pending |
| CLI-01 | — | Pending |
| CLI-02 | — | Pending |

**Coverage:**
- v1.3 requirements: 15 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 15 ⚠️

---
*Requirements defined: 2026-03-14*
*Last updated: 2026-03-14 after initial definition*
