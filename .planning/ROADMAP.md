# Roadmap: Homelab MCP Server 1.0

## Overview

Take an existing 34+ tool MCP server from "works in development" to "production-ready 1.0 release." The codebase has sound architecture but ships with disabled security, stub functions, silent failures, and no documentation. The path to 1.0 is: centralize connection management, harden security, complete missing functionality, achieve MCP spec compliance, then document the stable result.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Architecture Foundation** - Centralize resource lifecycle and migrate to MCP SDK
- [ ] **Phase 2: Security Hardening** - Enable host key verification, SSL, input validation, and secrets redaction
- [ ] **Phase 3: Functional Completeness** - Implement stubs, fix silent exceptions, add tool annotations and error flags
- [ ] **Phase 4: MCP Protocol Compliance** - Add logging notifications and Streamable HTTP compliance
- [ ] **Phase 5: Documentation** - Setup guide, tool reference, and configuration reference

## Phase Details

### Phase 1: Architecture Foundation
**Goal**: All external connections (SSH, HTTP, database) are managed through a central ResourceManager, the server uses the MCP SDK instead of hand-rolled JSON-RPC, and the process shuts down cleanly
**Depends on**: Nothing (first phase)
**Requirements**: ARCH-01, ARCH-02, ARCH-03, FUNC-05
**Success Criteria** (what must be TRUE):
  1. Server starts and handles tool calls using MCP SDK lowlevel.Server (not custom JSON-RPC parsing)
  2. SSH connections, Proxmox HTTP sessions, and database connections are obtained from ResourceManager, not created ad-hoc in each tool handler
  3. Proxmox API calls reuse HTTP connections via session pooling (no new connection per request)
  4. Server shuts down cleanly on SIGTERM/SIGINT with all connections closed and no orphaned resources
  5. Existing test suite passes against the new architecture
**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md — ResourceManager + Proxmox session pooling
- [x] 01-02-PLAN.md — MCP SDK migration (server, transports, tool registration)
- [x] 01-03-PLAN.md — Graceful shutdown + test suite verification

### Phase 2: Security Hardening
**Goal**: Users can trust that their SSH and Proxmox connections are not vulnerable to interception, tool inputs are validated, and credentials never leak into logs
**Depends on**: Phase 1
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04
**Success Criteria** (what must be TRUE):
  1. SSH connections verify host keys using trust-on-first-use (TOFU) -- first connection prompts/stores, subsequent connections reject mismatches
  2. Proxmox API connections verify SSL certificates by default, with a documented configuration override for self-signed certs
  3. Tool inputs for hostnames, IP addresses, and port ranges are validated before use -- malformed or hostile inputs are rejected with clear error messages
  4. Passwords, API tokens, and SSH keys never appear in log output or error responses returned to the MCP client
**Plans:** 3 plans

Plans:
- [ ] 02-01-PLAN.md — Input validation module + credential redaction logging filter
- [ ] 02-02-PLAN.md — Proxmox SSL verification default flip + CA cert support
- [ ] 02-03-PLAN.md — SSH TOFU host key verification + replace all insecure connect calls

### Phase 3: Functional Completeness
**Goal**: Every tool that can be called actually works end-to-end -- no stubs, no swallowed errors, and MCP clients can distinguish read-only from destructive tools
**Depends on**: Phase 2
**Requirements**: FUNC-01, FUNC-02, FUNC-03, FUNC-04, MCP-01, MCP-02
**Success Criteria** (what must be TRUE):
  1. After deploying infrastructure, the sitemap automatically reflects the new device without manual refresh
  2. After changing device configuration, device info reflects the updated state without manual refresh
  3. Script-based service installation (the _install_with_script path) completes successfully on a target host
  4. All previously-silent exception handlers now emit log messages at debug or warning level -- no bare except:pass remains
  5. Every tool has readOnlyHint, destructiveHint, and idempotentHint annotations visible to MCP clients, and all error responses include isError: true
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD

### Phase 4: MCP Protocol Compliance
**Goal**: The server fully complies with MCP protocol expectations for logging and HTTP transport
**Depends on**: Phase 3
**Requirements**: MCP-03, MCP-04
**Success Criteria** (what must be TRUE):
  1. Long-running operations (subnet scans, bulk deployments) emit MCP logging notifications that clients can display as progress
  2. HTTP transport implements Streamable HTTP spec requirements: session management, Origin header validation, and proper content-type handling
**Plans**: TBD

Plans:
- [ ] 04-01: TBD

### Phase 5: Documentation
**Goal**: A new user can go from zero to managing their homelab with this server by following the documentation
**Depends on**: Phase 4
**Requirements**: DOCS-01, DOCS-02, DOCS-03
**Success Criteria** (what must be TRUE):
  1. A user can follow the setup guide from clone through first successful tool call without needing to read source code
  2. Every tool is documented with its arguments, return format, and at least one usage example
  3. All environment variables and configuration options are listed with their defaults and descriptions
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Architecture Foundation | 3/3 | Complete |  |
| 2. Security Hardening | 0/3 | Not started | - |
| 3. Functional Completeness | 0/? | Not started | - |
| 4. MCP Protocol Compliance | 0/? | Not started | - |
| 5. Documentation | 0/? | Not started | - |
