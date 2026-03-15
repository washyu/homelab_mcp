# Milestones

## v1.3 Credentials & Release Automation (Shipped: 2026-03-15)

**Phases completed:** 4 phases, 9 plans
**Timeline:** 1 day (Mar 14-15, 2026)
**Stats:** 41 files changed, +5,433 / -86 lines | 15,229 LOC src

**Key accomplishments:**
1. Built headless-safe `credential_store.py` with OS keyring + JSON hostname registry — every function catches `NoKeyringError`/`RuntimeError` with safe fallback; no D-Bus probing at server startup
2. Added `homelab-mcp credentials add/list/remove` CLI subcommands for SSH and Proxmox credentials with secure password prompting (no echo); `--type proxmox` flag for Proxmox-specific storage
3. Added `homelab-mcp --version` flag printing installed package version via `importlib.metadata`; bare `homelab-mcp` unchanged
4. Wired credential auto-inject into `resolve_ssh_credentials()` (Tier 2 keyring fallback) and `get_proxmox_client()` — stored credentials used automatically when no explicit args passed; log-safe (password never appears in output)
5. Automated PyPI releases via GitHub Actions OIDC trusted publishing — `git tag v1.3.0` push triggers publish job; no stored secrets; gated on test-and-quality passing first
6. Fixed PRMT-02: `decommission_device_workflow` prompt now instructs AI to call `get_network_sitemap` to resolve hostname→`device_id` before calling `decommission_device` — eliminates schema validation errors

---

## v1.2 Protocol Completeness (Shipped: 2026-03-13)

**Phases completed:** 5 phases, 10 plans
**Timeline:** 1 day (Mar 13, 2026)
**Stats:** 72 files changed, +8,519 / -481 lines | 14,944 LOC src | 15,924 LOC tests

**Key accomplishments:**
1. Published homelab-mcp 1.2.0 to PyPI — `uvx homelab-mcp` and `pip install homelab-mcp` now work; version unified via `importlib.metadata` across all modules
2. Added `homelab://drift/latest` MCP Resource with live `notifications/resources/updated` push after each drift scan — clients can subscribe and cache
3. Implemented MCP Prompts capability (`prompts/list` + `prompts/get`) with three workflow templates: decommission preview workflow, deploy service pre-flight, and homelab health check referencing all three resources
4. Split 6 destructive tools into `*_preview` variants annotated `readOnlyHint=True, destructiveHint=False` — MCP clients skip confirmation dialogs for preview calls; 56 total tools
5. ruff and mypy both exit 0 across full source tree; 9 targeted bandit nosec annotations suppress pre-existing medium findings without masking new ones

**Tech debt carried forward:**
- PRMT-02 parameter mismatch: `decommission_device_workflow` prompt uses `hostname=` but tool schema requires `device_id=` — AI following prompt will encounter a validation error
- All 5 Nyquist VALIDATION.md files exist but remain in draft status (nyquist_compliant: false)
- SUMMARY.md files lack `requirements_completed` frontmatter — 3-source audit cross-reference fell back to VERIFICATION.md evidence

---

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
