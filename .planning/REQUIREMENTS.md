# Requirements: Homelab MCP Server

**Defined:** 2026-03-08
**Core Value:** Every tool in the server actually works when a user calls it — a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.

## v1 Requirements

Requirements for 1.0 release. Each maps to roadmap phases.

### Security

- [ ] **SEC-01**: SSH connections use host key verification with trust-on-first-use (TOFU) model
- [x] **SEC-02**: Proxmox API connections verify SSL certificates by default with configurable override
- [ ] **SEC-03**: All tool inputs validated for hostnames, IP addresses, and port ranges
- [ ] **SEC-04**: Sensitive credentials never appear in log output or error responses

### MCP Protocol

- [ ] **MCP-01**: All tools annotated with readOnlyHint, destructiveHint, and idempotentHint
- [ ] **MCP-02**: All error responses include isError: true per MCP spec
- [ ] **MCP-03**: Server emits MCP logging notifications for long-running operations
- [ ] **MCP-04**: HTTP transport complies with Streamable HTTP spec (session management, Origin validation)

### Architecture

- [x] **ARCH-01**: Server uses MCP SDK (lowlevel.Server) instead of hand-rolled JSON-RPC
- [x] **ARCH-02**: ResourceManager centralizes SSH, HTTP, and database connection lifecycle
- [x] **ARCH-03**: Server shuts down gracefully on SIGTERM/SIGINT with resource cleanup

### Functional Completeness

- [ ] **FUNC-01**: Sitemap updates automatically after infrastructure deployment
- [ ] **FUNC-02**: Device info refreshes after configuration changes
- [ ] **FUNC-03**: Script-based service installation works end-to-end
- [ ] **FUNC-04**: Silent exception handlers replaced with debug/warning logging
- [x] **FUNC-05**: Proxmox API client reuses HTTP connections via session pooling

### Documentation

- [ ] **DOCS-01**: Setup guide covers clone, install, configure, connect, and verify
- [ ] **DOCS-02**: Tool reference documents all tools with arguments, returns, and examples
- [ ] **DOCS-03**: Configuration reference lists all environment variables with defaults

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### MCP Advanced Features

- **MCPV2-01**: Infrastructure state exposed as MCP Resources with subscriptions
- **MCPV2-02**: Pre-built MCP Prompts for common workflows (deploy, diagnose, plan)
- **MCPV2-03**: Structured output schemas on tools for programmatic result parsing
- **MCPV2-04**: Progress notifications during long operations (subnet scans, bulk deploys)

### Homelab Enhancements

- **HOMEV2-01**: Infrastructure drift detection (compare current vs last known state)
- **HOMEV2-02**: Dry-run mode for destructive operations
- **HOMEV2-03**: Network diagram generation from sitemap data
- **HOMEV2-04**: Backup verification (test restore after backup)

### Distribution

- **DISTV2-01**: PyPI package (`pip install homelab-mcp`)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Web UI / Dashboard | MCP clients ARE the UI — building a dashboard duplicates what they provide |
| Multi-user / RBAC | Homelabs are single-operator; use reverse proxy for multi-user |
| Plugin system | 34+ tools is enough; let people fork instead |
| Real-time monitoring / alerting | Not Prometheus — expose point-in-time queries, let users use existing monitoring |
| Kubernetes management | Fundamentally different model from Proxmox VMs/LXC; keep k3s template only |
| PostgreSQL as default | SQLite is correct for single-user homelab |
| Session persistence | Shell sessions are ephemeral; acceptable for 1.0 |
| Rate limiting | Homelabbers won't overwhelm their own infrastructure |
| Audit logging | Standard logging sufficient for single operator |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEC-01 | Phase 2 | Pending |
| SEC-02 | Phase 2 | Complete |
| SEC-03 | Phase 2 | Pending |
| SEC-04 | Phase 2 | Pending |
| MCP-01 | Phase 3 | Pending |
| MCP-02 | Phase 3 | Pending |
| MCP-03 | Phase 4 | Pending |
| MCP-04 | Phase 4 | Pending |
| ARCH-01 | Phase 1 | Complete |
| ARCH-02 | Phase 1 | Complete |
| ARCH-03 | Phase 1 | Complete |
| FUNC-01 | Phase 3 | Pending |
| FUNC-02 | Phase 3 | Pending |
| FUNC-03 | Phase 3 | Pending |
| FUNC-04 | Phase 3 | Pending |
| FUNC-05 | Phase 1 | Complete |
| DOCS-01 | Phase 5 | Pending |
| DOCS-02 | Phase 5 | Pending |
| DOCS-03 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0

---
*Requirements defined: 2026-03-08*
*Last updated: 2026-03-08 after roadmap creation*
