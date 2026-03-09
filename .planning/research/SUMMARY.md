# Project Research Summary

**Project:** Homelab MCP Server - Production 1.0
**Domain:** Infrastructure management MCP server (SSH/Proxmox homelab automation)
**Researched:** 2026-03-08
**Confidence:** HIGH

## Executive Summary

This is a Python MCP server providing 44 tools for homelab infrastructure management via SSH and Proxmox APIs. The existing codebase has a sound layered architecture (transport, registry, handlers, domain logic, database) and the right async-first design for an I/O-heavy server. The core technical problem for 1.0 is not missing functionality -- most tools exist -- but that the server has critical security gaps and operational roughness that make it unsuitable for managing real infrastructure. The project already depends on the MCP SDK (v1.9.4) but does not use it, instead implementing its own JSON-RPC protocol manually. Adopting the SDK eliminates ~200 lines of protocol code and gains transport negotiation, tool annotations, and protocol version management for free.

The recommended approach is to harden what exists rather than build new features. The highest-priority work is security: SSH host key verification is disabled across 19 call sites, Proxmox SSL defaults to unverified, input validation is absent, and the HTTP transport binds to all interfaces with weak auth defaults. These are ship-blockers. The second priority is operational reliability: connection pooling, stub implementation, silent exception fixes, and graceful shutdown. Only after these foundations are solid should the project consider differentiating MCP features like Resources, Prompts, and structured output schemas.

The key architectural recommendation is to introduce a ResourceManager that centralizes all external connections (SSH, HTTP, database). This eliminates the connection-per-call anti-pattern, provides a single enforcement point for security policies (host key verification, SSL), enables graceful shutdown, and reduces the 19 SSH connection sites to one. Every other improvement -- security hardening, stub implementation, performance -- becomes easier once connections are centralized.

## Key Findings

### Recommended Stack

The existing stack is correct and needs no major technology changes. Python 3.12+, asyncssh, aiohttp, SQLite, and uv are all the right choices. The critical stack decision is to actually use the MCP SDK that is already installed -- migrate from the hand-rolled JSON-RPC implementation to `lowlevel.Server` (mechanical migration) with a future path to `FastMCP` (deeper refactor). Pydantic (already a transitive dependency via MCP SDK) should replace jsonschema for input validation. Consider adding structlog for structured logging.

**Core technologies:**
- **mcp[cli] 1.9.4** (lowlevel.Server): MCP protocol handling -- stop reimplementing what the SDK provides
- **asyncssh 2.21.0**: Async SSH operations -- only viable async SSH library, but must fix known_hosts=None
- **aiohttp 3.12.13**: Proxmox API client -- already integrated, must add connection pooling
- **pydantic 2.11.7** (transitive): Input validation -- replace jsonschema, use for hostname/IP/port validation
- **SQLite** (stdlib): Device tracking -- correct for single-user homelab, no need for PostgreSQL

**Remove:** jsonschema (redundant with SDK adoption), standalone bandit (replace with ruff S rules)

### Expected Features

**Must have (table stakes for 1.0):**
- SSH host key verification (TOFU model) -- security blocker, cannot ship without
- Proxmox SSL verification enabled by default -- same reasoning
- Input validation for hostnames, IPs, ports -- command injection prevention
- Stub functions implemented (3 stubs called in production paths)
- Tool annotations (readOnlyHint, destructiveHint) -- low effort, high value for MCP clients
- isError flag on all error responses -- MCP protocol compliance
- Silent exception handlers replaced with logging -- 9 instances of swallowed errors
- HTTP connection pooling for Proxmox -- performance baseline
- Setup guide (clone to first tool call) -- no docs = no users

**Should have (strong 1.0):**
- MCP logging capability for progress notifications
- Tool reference documentation (auto-generated from schemas)
- Configuration validation on startup (fail fast)
- Graceful shutdown with resource cleanup
- Streamable HTTP transport compliance audit

**Defer to post-1.0:**
- MCP Resources (high value but high complexity)
- MCP Prompts (nice-to-have)
- Structured output schemas (backwards compatible, add incrementally)
- Dry-run mode for destructive operations
- Infrastructure drift detection
- PyPI distribution (explicit PROJECT.md decision)

### Architecture Approach

The existing layered architecture is correct. The main evolution needed is a ResourceManager that centralizes connection lifecycle management. Three modules exceed 1,000 lines (infrastructure_crud.py, service_installer.py, ssh_tools.py) and should be decomposed into sub-packages, but this is lower priority than security and reliability work.

**Major components:**
1. **ResourceManager** (NEW) -- owns SSH pool, HTTP session, DB connection; provides connections to domain logic via context managers; enforces security policies centrally
2. **Transport Layer** (EVOLVE) -- migrate from manual JSON-RPC to MCP SDK lowlevel.Server; gains stdio, SSE, and Streamable HTTP transport support
3. **Tool Registry** (EVOLVE) -- add tool annotations, wire handler dispatch through SDK patterns
4. **Domain Modules** (HARDEN) -- SSH, Proxmox, VM, Infrastructure, Service, Network -- implement stubs, fix silent exceptions, use pooled connections

### Critical Pitfalls

1. **Disabled SSH host key verification** -- 19 instances of `known_hosts=None`. Implement TOFU model via ResourceManager. Fix first because enabling it post-launch is a breaking change for users.
2. **Silent exception swallowing** -- 9 bare `except: pass` blocks mask infrastructure failures. AI reports success when operations partially failed. Audit and categorize each instance.
3. **Stub functions in production paths** -- 3 stubs silently do nothing, causing sitemap divergence from reality. Implement or remove call sites.
4. **Command injection via unvalidated inputs** -- tool arguments from AI can contain hostile content. Validate hostnames, IPs, ports, and paths at handler boundary.
5. **HTTP transport security defaults** -- binds to 0.0.0.0 with weak auth. Default to 127.0.0.1, enforce API key strength on startup.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Resource Lifecycle and SDK Migration
**Rationale:** Everything else depends on centralized connection management and proper protocol handling. ResourceManager makes security fixes apply everywhere from one place. SDK migration eliminates protocol maintenance burden.
**Delivers:** ResourceManager with SSH pool and HTTP session pooling; MCP SDK lowlevel.Server integration replacing manual JSON-RPC; graceful startup/shutdown with signal handlers.
**Addresses:** HTTP connection pooling (table stakes), graceful shutdown (should-have), protocol compliance foundation.
**Avoids:** Connection-per-call anti-pattern (Pitfall 6), no graceful shutdown (Pitfall 10).

### Phase 2: Security Hardening
**Rationale:** Depends on Phase 1 (ResourceManager centralizes connection creation so security policies apply everywhere). These are ship-blockers -- the project cannot release without them.
**Delivers:** SSH host key verification (TOFU); Proxmox SSL verification default; input validation module; HTTP transport defaults (localhost binding, API key strength enforcement); secrets redaction in logs.
**Addresses:** SSH host key verification, SSL verification, input validation, secrets handling (all table stakes).
**Avoids:** Disabled host key verification (Pitfall 1), command injection (Pitfall 4), weak HTTP auth (Pitfall 5).

### Phase 3: Functional Completeness
**Rationale:** Depends on Phase 2 (stubs need secure SSH connections). Implements missing functionality and fixes silent failures.
**Delivers:** Stub functions implemented; silent exception handlers replaced with logging; tool annotations added; isError flag audit; hardcoded mcp_admin username removed; per-tool-category timeouts.
**Addresses:** Stub implementation, silent exceptions, tool annotations, isError flag, error message quality (all table stakes).
**Avoids:** Stub functions in production (Pitfall 3), silent exception swallowing (Pitfall 2), hardcoded username (Pitfall 8), global timeout (Pitfall 9).

### Phase 4: MCP Protocol Compliance and Polish
**Rationale:** With working, secure tools in place, add MCP protocol features that improve the user experience and bring the server up to spec compliance.
**Delivers:** MCP logging capability with progress notifications; Streamable HTTP transport compliance; configuration validation on startup; structured error messages.
**Addresses:** MCP logging (should-have), Streamable HTTP audit (should-have), config validation (should-have).
**Avoids:** Poor user experience during long operations.

### Phase 5: Documentation and Distribution
**Rationale:** Document what works. Cannot write accurate docs until tools are functional and APIs are stable.
**Delivers:** Setup guide (clone to first tool call); tool reference documentation (auto-generated from schemas); configuration reference; CHANGELOG for 1.0.
**Addresses:** Setup guide (table stakes), tool reference (should-have), config reference (should-have).
**Avoids:** Documentation that describes unfinished features.

### Phase 6: Post-1.0 Enhancements (Future)
**Rationale:** High-value features that are not required for a credible 1.0 release.
**Delivers:** MCP Resources for infrastructure state; MCP Prompts for workflows; dry-run mode; module decomposition of large files; PyPI distribution.
**Addresses:** All deferred differentiator features.

### Phase Ordering Rationale

- Phase 1 before Phase 2: Centralizing connections via ResourceManager means SSH host key verification is implemented once, not across 19 call sites. Security policies become configuration, not code changes.
- Phase 2 before Phase 3: Stubs need SSH connections to implement. Those connections must be secure before writing new code that uses them.
- Phase 3 before Phase 4: MCP protocol features (logging, annotations) depend on tools that actually work and report errors correctly.
- Phase 5 last before release: Documentation written against stable, complete functionality is documentation that stays accurate.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1:** MCP SDK migration needs careful mapping of current JSON-RPC handling to lowlevel.Server patterns. Research the exact SDK API for handler registration, error propagation, and transport setup.
- **Phase 2:** SSH TOFU implementation with asyncssh -- verify the exact API for known_hosts file management, host key callbacks, and first-connect behavior.
- **Phase 4:** Streamable HTTP compliance -- verify session management (Mcp-Session-Id), protocol version header, and Origin validation requirements against latest MCP spec.

Phases with standard patterns (skip research-phase):
- **Phase 3:** Stub implementation, exception handling, input validation -- all well-documented Python patterns.
- **Phase 5:** Documentation generation -- standard tooling, no novel research needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Verified by direct inspection of installed SDK, pyproject.toml, uv.lock, and source code. All recommendations based on actual codebase state. |
| Features | MEDIUM-HIGH | Based on MCP specification 2025-06-18 (official) and codebase analysis. Homelab ecosystem expectations based on training data. |
| Architecture | HIGH | Based on direct codebase analysis. ResourceManager and connection pooling are established patterns. |
| Pitfalls | HIGH | All pitfalls verified by grep/inspection of actual source code. Security patterns based on established OWASP guidelines. |

**Overall confidence:** HIGH

### Gaps to Address

- **asyncssh known_hosts API:** Exact API for TOFU pattern (host key callbacks, known_hosts file format) needs verification against asyncssh documentation during Phase 2 planning.
- **pytest-asyncio 1.0 migration:** Locked version jumped to 1.0.0 with breaking API changes (strict mode default). Verify test suite compatibility before Phase 1.
- **MCP SDK lowlevel.Server API:** Exact handler registration pattern, error propagation, and transport setup need verification during Phase 1 planning. Code examples in STACK.md are from training data, not verified.
- **Streamable HTTP session requirements:** Session management, Origin header validation, and DNS rebinding protection requirements need verification against current MCP spec during Phase 4.
- **Hardware detection cross-distro compatibility:** Parsing of lsblk, /proc/cpuinfo output varies across Linux distributions. No cross-distro testing data available. Flag for integration testing.

## Sources

### Primary (HIGH confidence)
- MCP SDK source code v1.9.4 (direct inspection of .venv/lib/python3.12/site-packages/mcp/)
- Project source code (direct inspection of src/homelab_mcp/)
- Project configuration (pyproject.toml, uv.lock -- direct inspection)
- MCP Specification 2025-06-18: https://modelcontextprotocol.io/specification/2025-06-18/
- Codebase analysis: .planning/codebase/ARCHITECTURE.md, .planning/codebase/CONCERNS.md

### Secondary (MEDIUM confidence)
- asyncssh known_hosts documentation (training data -- verify API details)
- pytest-asyncio 1.0 migration (training data -- verify changelog)
- aiohttp ClientSession best practices (training data -- well-documented but not verified for this version)
- OWASP command injection prevention guidelines (training data -- established patterns)

### Tertiary (LOW confidence)
- structlog recommendation (training data -- standard library but not validated for this project's specific logging needs)
- Homelab ecosystem expectations (training data -- not verified against current ecosystem)

---
*Research completed: 2026-03-08*
*Ready for roadmap: yes*
