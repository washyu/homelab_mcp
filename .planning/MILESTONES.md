# Milestones

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

