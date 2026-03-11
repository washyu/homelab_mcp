# Homelab MCP Server

## What This Is

A production-ready Python MCP (Model Context Protocol) server that gives AI assistants the ability to manage homelab infrastructure — discovering devices via SSH, managing VMs and containers, installing services, tracking network topology, and interacting with Proxmox. Ships with 49 tools across 7 categories, comprehensive documentation, and security hardening. Targets homelabbers running Proxmox VE who want AI-powered infrastructure management through any MCP-compatible client.

## Core Value

Every tool in the server actually works when a user calls it — a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.

## Requirements

### Validated

- ✓ MCP SDK lowlevel.Server with ResourceManager lifecycle — v1.0
- ✓ Graceful shutdown on SIGTERM/SIGINT with resource cleanup — v1.0
- ✓ SSH TOFU host key verification (trust-on-first-use) — v1.0
- ✓ Proxmox SSL verification on by default with configurable override — v1.0
- ✓ Input validation for hostnames, IPs, port ranges across all handlers — v1.0
- ✓ Credential redaction in all log output and error responses — v1.0
- ✓ 49 tools with readOnlyHint, destructiveHint, idempotentHint annotations — v1.0
- ✓ isError: true on all error responses per MCP spec — v1.0
- ✓ MCP logging notifications for long-running operations — v1.0
- ✓ Streamable HTTP with Origin validation and localhost bind — v1.0
- ✓ Setup guide from clone to first tool call — v1.0
- ✓ Tool reference for all 49 tools with examples — v1.0
- ✓ Configuration reference for all env vars and CLI args — v1.0
- ✓ Sitemap auto-update after deployment, device refresh after config changes — v1.0
- ✓ Script-based service installation working end-to-end — v1.0
- ✓ All silent exception handlers replaced with debug/warning logging — v1.0
- ✓ Tool registry with schema/handler separation — existing
- ✓ SSH-based device discovery and hardware detection — existing
- ✓ Network sitemap and device tracking with SQLite persistence — existing
- ✓ VM/container management via Docker and LXD providers — existing
- ✓ Service installation framework with Terraform and Ansible methods — existing
- ✓ Proxmox API integration (nodes, VMs, storage, tasks) — existing
- ✓ Interactive shell sessions via WebSocket — existing
- ✓ Infrastructure lifecycle management (deploy/update/decommission) — existing

### Active

<!-- v1.1 Safety & Observability -->

- [ ] Dry-run preview for destructive operations (show what would happen before executing)
- [ ] Infrastructure drift detection — config drift (CPU, memory, network changed outside MCP)
- [ ] Infrastructure drift detection — state drift (services stopped, VMs offline unexpectedly)
- [ ] On-demand drift scan tool with structured report
- [ ] MCP Resources exposing live infrastructure state (VM list, service status, device inventory)
- [ ] MCP Resource subscriptions for state change notifications
- [ ] Fix: ResourceManager.proxmox_session wiring (created but never consumed by handler chain)
- [ ] Fix: API key authentication wired into HTTP transport
- [ ] Fix: vm_providers error handling (replace raw str(e) with structured errors)

### Out of Scope

- Mobile/web UI — MCP clients provide the interface
- Multi-user / RBAC — homelab is single-operator
- PostgreSQL as default — SQLite is correct for single-user homelab
- Rate limiting — homelabbers won't overwhelm their own infra
- Kubernetes management — fundamentally different from Proxmox VMs/LXC
- Real-time monitoring/alerting — not Prometheus; expose point-in-time queries
- Offline mode — real-time is core value
- Pre-built MCP Prompts — deferred to v1.2
- PyPI package distribution — deferred to v1.2
- Auto-detect drift with periodic background checks — deferred, start with on-demand scan
- Full workflow simulation (dry-run beyond destructive ops) — deferred, start with destructive preview

## Current Milestone: v1.1 Safety & Observability

**Goal:** Make the server trustworthy for real use — preview before breaking things, detect when reality drifts from expectations, expose live infra state via MCP Resources, and clean up v1.0 tech debt.

**Target features:**
- Dry-run preview for destructive operations (delete, stop, restart show what would happen first)
- Infrastructure drift detection — config and state drift with on-demand scan
- MCP Resources for live infrastructure state with subscriptions
- Tech debt cleanup (proxmox_session wiring, API key auth, vm_providers errors)

## Context

- Shipped v1.0 with 13K LOC Python (src/) + 13K LOC tests (479 unit tests passing)
- Tech stack: Python 3.12+, uv, asyncssh, mcp[cli], aiohttp, SQLite
- 49 tools organized into 7 categories: SSH, network, VM, service, infrastructure, credential, Proxmox
- MCP SDK lowlevel.Server with stdio and Streamable HTTP transports
- Integration tests exist with Docker-based SSH testing
- Documentation: setup guide, tool reference (49 tools), configuration reference

## Constraints

- **Tech stack**: Python 3.12+, uv, asyncssh, mcp[cli] — established, not changing
- **Distribution**: Clone + uv sync for 1.0 (PyPI planned for future)
- **Target platform**: Linux primary (Proxmox hosts are Linux)
- **MCP compatibility**: Must work with any MCP-compatible client, not just Claude
- **Security**: SSH TOFU, Proxmox SSL, input validation, credential redaction all enforced

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fix security before 1.0 | Users shouldn't be vulnerable to MITM on their own network | ✓ Good — SSH TOFU, SSL default, validation, redaction all shipped |
| Implement all stubs | Called code that does nothing is a bug, not tech debt | ✓ Good — sitemap auto-update, device rediscovery, script install all working |
| Clone + uv sync distribution | Simplest path to 1.0, PyPI can come later | ✓ Good — works, documented in setup guide |
| Target Proxmox users | Clear persona, existing integration, testable | ✓ Good — clear scope, 10 Proxmox-specific tools |
| All tools must work | "Everything works" bar — no stubs, no broken tools | ✓ Good — 49 tools annotated and functional |
| MCP SDK lowlevel.Server (not FastMCP) | Maximum control over protocol details | ✓ Good — enabled custom lifespan, annotations, ToolError pattern |
| ResourceManager with module-level accessor | Avoids threading request_context through every handler | ⚠️ Revisit — proxmox_session never consumed by handler chain |
| Pure ASGI middleware for Origin validation | Better performance than BaseHTTPMiddleware | ✓ Good — clean integration with Starlette middleware stack |

---
*Last updated: 2026-03-11 after v1.1 milestone initialization*
