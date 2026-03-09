# Homelab MCP Server

## What This Is

A Python MCP (Model Context Protocol) server that gives AI assistants the ability to manage homelab infrastructure — discovering devices via SSH, managing VMs and containers, installing services, tracking network topology, and interacting with Proxmox. Targets homelabbers running Proxmox VE who want AI-powered infrastructure management through any MCP-compatible client.

## Core Value

Every tool in the server actually works when a user calls it — a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. Inferred from existing codebase. -->

- ✓ MCP server with JSON-RPC 2.0 protocol over stdio — existing
- ✓ HTTP/SSE transport with API key authentication — existing
- ✓ Tool registry pattern with schema/handler separation (34+ tools) — existing
- ✓ SSH-based device discovery and hardware detection — existing
- ✓ Network sitemap and device tracking with SQLite persistence — existing
- ✓ VM/container management via Docker and LXD providers — existing
- ✓ Service installation framework with Terraform and Ansible methods — existing
- ✓ Proxmox API integration (nodes, VMs, storage, tasks) — existing
- ✓ SSH credential management with priority resolution — existing
- ✓ Interactive shell sessions via WebSocket — existing
- ✓ Infrastructure lifecycle management (deploy/update/decommission) — existing
- ✓ Error handling with timeout/retry decorators — existing
- ✓ Health monitoring endpoint — existing
- ✓ Database migration system — existing

### Active

<!-- Current scope. Making this production-ready for 1.0 release. -->

- [ ] All 34+ tools validated end-to-end against real Proxmox environment
- [ ] SSH host key verification enabled (19 instances currently disabled)
- [ ] Proxmox SSL verification on by default (configurable override)
- [ ] Stub functions implemented (`_update_sitemap_after_deployment`, `_rediscover_device_after_config`, `_install_with_script`)
- [ ] Silent exception handlers replaced with proper logging (9 instances)
- [ ] HTTP client connection pooling for Proxmox API
- [ ] Input validation for hostnames, IPs, and port ranges
- [ ] Clean install experience (clone → configure → run works first try)
- [ ] User-facing documentation (setup guide, tool reference, configuration)

### Out of Scope

<!-- Explicit boundaries for 1.0. -->

- Audit logging — useful but not required for initial release
- Rate limiting — homelabbers won't overwhelm their own infra
- PostgreSQL as default — SQLite is fine for single-user homelab
- Session persistence across restarts — acceptable limitation for 1.0
- Mobile/web UI — MCP clients provide the interface
- Multi-user support — homelab is single-operator

## Context

- Brownfield project with ~11.9K LOC in source, ~9K LOC in tests (386 test functions)
- Well-structured codebase: layered architecture, async-first, typed with mypy
- 34+ tools organized into 7 categories: SSH, network, VM, service, infrastructure, credential, Proxmox
- Integration tests exist with Docker-based SSH testing
- Real Proxmox environment available for end-to-end validation
- Codebase mapping completed — see `.planning/codebase/` for detailed analysis

## Constraints

- **Tech stack**: Python 3.12+, uv, asyncssh, mcp[cli] — established, not changing
- **Distribution**: Clone + uv sync for 1.0 (PyPI later)
- **Target platform**: Linux primary (Proxmox hosts are Linux)
- **MCP compatibility**: Must work with any MCP-compatible client, not just Claude
- **Security**: Must not ship with known vulnerabilities (disabled host key verification, disabled SSL)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fix security before 1.0 | Users shouldn't be vulnerable to MITM on their own network | — Pending |
| Implement all stubs | Called code that does nothing is a bug, not tech debt | — Pending |
| Clone + uv sync distribution | Simplest path to 1.0, PyPI can come later | — Pending |
| Target Proxmox users | Clear persona, existing integration, testable | — Pending |
| All tools must work | "Everything works" bar — no stubs, no broken tools | — Pending |

---
*Last updated: 2026-03-08 after initialization*
