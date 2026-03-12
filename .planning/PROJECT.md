# Homelab MCP Server

## What This Is

A production-ready Python MCP (Model Context Protocol) server that gives AI assistants the ability to manage homelab infrastructure — discovering devices via SSH, managing VMs and containers, installing services, tracking network topology, and interacting with Proxmox. Ships with 50 tools across 7 categories, comprehensive documentation, security hardening, dry-run previews for destructive operations, infrastructure drift detection, and live infrastructure state via MCP Resources. Targets homelabbers running Proxmox VE who want AI-powered infrastructure management through any MCP-compatible client.

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
- ✓ ResourceManager.proxmox_session consumed by handler chain — v1.1
- ✓ API key authentication enforced on HTTP transport endpoints — v1.1
- ✓ vm_providers error paths return structured error dicts — v1.1
- ✓ Dry-run preview for all 6 destructive operations with structured response — v1.1
- ✓ Infrastructure drift detection — config drift (CPU, memory, network) — v1.1
- ✓ Infrastructure drift detection — state drift (services stopped, VMs offline) — v1.1
- ✓ On-demand `scan_infrastructure_drift` tool with structured report — v1.1
- ✓ MCP Resources exposing live infrastructure state (VMs, devices, services) — v1.1
- ✓ `notifications/resources/list_changed` after device discovery mutations — v1.1

## Current Milestone: v1.2 Protocol Completeness

**Goal:** Complete MCP protocol surface — Prompts, Resources, and correct dry-run tool semantics — plus PyPI distribution for easier installation.

**Target features:**
- Dry-run tool split (6 destructive tools → `*_preview` variants with `readOnlyHint: true`)
- MCP Prompts (`prompts/list` + `prompts/get` with homelab workflow templates)
- PyPI distribution (`uvx homelab-mcp` install path)
- Drift MCP Resource (`homelab://drift/latest` live resource)

### Active

<!-- Populated during requirements definition -->

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
- Resource subscriptions with `notifications/resources/updated` — deferred to v1.2 (DRY-08, RES-08, RES-09)
- Drift report via MCP Resource (`homelab://drift/latest`) — deferred to v1.2 (DRFT-07)

## Context

- Shipped v1.1 with ~14,300 LOC Python (src/) | 115 files changed from v1.0 baseline
- Tech stack: Python 3.12+, uv, asyncssh, mcp[cli], aiohttp, SQLite
- 50 tools organized into 7 categories: SSH, network, VM, service, infrastructure, credential, Proxmox
- MCP SDK lowlevel.Server with stdio and Streamable HTTP transports
- New modules added in v1.1: `dry_run.py`, `drift_detection.py`, `resource_readers.py`
- SQLite schema extended with `drift_baselines` table (node, vmid, vm_type, config JSON, upsert via INSERT OR REPLACE)
- Mypy upgraded to v1.18.1 with asyncssh/aiohttp stubs — pre-commit hook now runs clean

## Constraints

- **Tech stack**: Python 3.12+, uv, asyncssh, mcp[cli] — established, not changing
- **Distribution**: Clone + uv sync for v1.x (PyPI planned for future)
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
| All tools must work | "Everything works" bar — no stubs, no broken tools | ✓ Good — 50 tools annotated and functional |
| MCP SDK lowlevel.Server (not FastMCP) | Maximum control over protocol details | ✓ Good — enabled custom lifespan, annotations, ToolError pattern |
| ResourceManager with module-level accessor | Avoids threading request_context through every handler | ✓ Good — proxmox_session now fully threaded (DEBT-01 fixed in v1.1) |
| Pure ASGI middleware for Origin validation | Better performance than BaseHTTPMiddleware | ✓ Good — clean integration with Starlette middleware stack |
| APIKeyAuth as conditional ASGI wrapper | HTTP auth only activates when MCP_API_KEY is set | ✓ Good — stdio deployments unaffected; HTTP deployments secured |
| Local import of get_resource_manager in handlers | Avoids server.py → tool_handlers → server.py circular import | ✓ Good — clean pattern, established in Phase 06, reused in 09/11 |
| Dry-run handlers return flat dict | build_dry_run_response() not content-wrapped — _convert_result fallback handles it | ⚠️ Revisit — low severity but inconsistent with live-execution response format |
| drift_baselines uses UNIQUE(node, vmid, vm_type) + INSERT OR REPLACE | Upsert entirely in SQL, no application-level conflict handling | ✓ Good — clean, SQLite-idiomatic |
| scan_drift labels state findings as point-in-time observations | Avoids false positives from transient VM reboot states | ✓ Good — honest reporting design |

---
*Last updated: 2026-03-12 after v1.2 milestone start*
