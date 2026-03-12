# Milestones

## v1.1 Safety & Observability (Shipped: 2026-03-12)

**Phases completed:** 6 phases, 16 plans
**Timeline:** 2 days (Mar 11-12, 2026)
**Stats:** 115 files changed, +14,818 / -1,183 lines | ~14,300 LOC src | 77 commits

**Key accomplishments:**
1. Fixed three v1.0 architectural bugs: Proxmox shared aiohttp session threaded through all 8 handler call sites (DEBT-01), API key auth wired into HTTP transport via conditional ASGI middleware (DEBT-02), vm_providers structured error dicts replacing raw str(e) (DEBT-03)
2. Wired full MCP Resources protocol: `resources/list`, `resources/read`, subscribe/unsubscribe with live Proxmox, SQLite, and SSH data behind `homelab://vms`, `homelab://devices`, and `homelab://services/{name}` URIs
3. Added dry-run mode to all 6 destructive tools — users can preview decommission, VM deletion, server removal, Terraform destroy, and rollback before committing; structured `{mode, would_affect, risk_level, reversible}` response contract
4. Built `scan_infrastructure_drift` tool with config drift (CPU/memory/network changed outside MCP) and state drift (VMs/services offline), backed by `drift_baselines` SQLite table that auto-updates after every mutation
5. Wired `notifications/resources/list_changed` after device discovery operations so MCP client caches stay coherent
6. Upgraded mypy to v1.18.1 with asyncssh/aiohttp stubs, eliminating the pre-commit hook version conflict that caused --no-verify workarounds in v1.0

**Tech debt carried forward:**
- Dry-run handlers return flat dict (not content-wrapped format) — functional, low severity
- Phases 06-10 Nyquist compliance partial (VALIDATION.md files exist but nyquist_compliant: false); Phase 11 fully compliant
- 2 drift detection verification items require live Proxmox: end-to-end drift scan and baseline auto-update

---

## v1.0 MVP (Shipped: 2026-03-11)

**Phases completed:** 5 phases, 15 plans, 30 tasks
**Timeline:** 3 days (Mar 8-11, 2026)
**Stats:** 93 files changed, 12,594 insertions, 1,885 deletions | 13K LOC src + 13K LOC tests | 479 unit tests

**Key accomplishments:**
1. Migrated from hand-rolled JSON-RPC to MCP SDK lowlevel.Server with ResourceManager lifecycle and graceful shutdown
2. Hardened security: SSH TOFU host key verification, Proxmox SSL by default, input validation across all handlers, credential redaction in all error paths
3. Completed all stub functions (sitemap auto-update, device rediscovery, script service install), eliminated silent exception handlers, added tool annotations on all 49 tools
4. Added MCP logging notifications with emit_progress for long-running operations, Origin validation middleware, localhost-only HTTP bind default
5. Created complete user documentation: setup guide (clone → first tool call), tool reference (49 tools), configuration reference (28 env vars + 7 CLI args), slimmed README

**Known tech debt:**
- ResourceManager.proxmox_session created but never consumed by handler chain (ARCH-02/FUNC-05 partial wiring)
- API key authentication not wired into new HTTP app
- vm_providers layer still uses raw str(e) in error dicts

---
