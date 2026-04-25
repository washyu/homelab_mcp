# Milestones

## v1.6 Credential Architecture Cleanup (Shipped: 2026-04-24)

**Phases completed:** 4 phases (33, 33.1 INSERTED, 34, 35 INSERTED), 18 plans
**Timeline:** 4 days active (Apr 20 - Apr 24, 2026)
**Stats:** 108 commits, 100 files changed, +23,042 / -3,368 lines | 15,887 LOC src + 19,554 LOC tests
**Tools:** 51 (down from 56 — removed `setup_mcp_admin`, `update_server_credentials`, `remove_server`, `update_mcp_admin_groups`, `verify_mcp_admin_access`)
**Audit verdict:** `passed` — 5/5 requirements satisfied, 7/7 wirings PASS, 4/4 E2E flows WIRED

**Key accomplishments:**
1. **CRED-04** — Dropped DB `ssh_credentials` table on both adapters; deleted all DB credential read/write methods. Keyring is the only remaining credential storage layer
2. **CRED-05** — `resolve_ssh_credentials` raises `CredentialNotFoundError` with `homelab-mcp credentials add <hostname>` pointer instead of falling back to `mcp_admin`. Two-tier resolution: explicit args → keyring → actionable miss
3. **CRED-06** — Removed `setup_mcp_admin`, `update_server_credentials`, `remove_server` MCP tools. Device onboarding routes through the `credentials add` CLI and the existing `connect_to_device` prompt; no MCP tool writes credentials
4. **CRED-07** — `register_server` reduced to a verify-only schema (hostname/username/port/display_name); calls `resolve_ssh_credentials` then `asyncssh.connect`. No code path accepts a registration without verified credentials
5. **CRED-08** — Cluster-scoped Proxmox tokens via `credentials add --type proxmox --scope cluster:<name>`; new async `resolve_proxmox_credentials` walks node→cluster→error with `_HOST_CLUSTER_CACHE` short-circuit; per-node tokens take precedence
6. **Phase 33.1 (INSERTED)** — SSH tool family uniformity: deleted `update_mcp_admin_groups` + `verify_mcp_admin_access` lock-step across 7 surfaces (schema/handler/dispatch/2 annotation shapes/openapi allowlist/openapi category); `sitemap.discover_and_store` and `bulk_discover_and_store` route through `resolve_ssh_credentials`; AST meta-tests guard against `mcp_admin` defaults reintroducing
7. **Phase 35 (INSERTED)** — Sitemap + discovery reliability: `discover_and_map` field-loss closed (cpu.cores/memory.*/disk.*/usb/pci/block reach the row); hostname-only upsert with degenerate-hostname fallback (no zombie rows on IP change); per-subprocess SSH timeout via `_run_with_timeout(10s)` on every `conn.run` probe (eliminates 4+ minute hangs); `bulk_discover_and_store` parallelized with `Semaphore(10)` + `asyncio.gather`; null-defensive analyzers via `_has_threshold_data` helper
8. **AST meta-tests as v1.6's regression guard pattern** — 4 new AST guards (33.1 D-08 mcp_admin defaults; 35 D-14 hostname-only upsert; 35 D-15 every `conn.run` is timeout-wrapped; 35 D-16 no `device.get(field) or 0` coercion in analyzer bodies). Class of bugs that no positive regression test catches

**Scope-expansion phases (no original v1.6 REQ-ID):**
- Phase 33.1 SSH Tool Family Keyring Uniformity — surfaced by Phase 33 live testing 2026-04-21; 5 plans, VERIFICATION 13/13
- Phase 35 Sitemap + Discovery Reliability — surfaced by Phase 33 live testing 2026-04-21; 4 plans, VERIFICATION 32/32

**Known gaps (deferred tech_debt — non-blocking):**
- `33-VERIFICATION.md` missing — phase merged on plan-SUMMARY evidence (same pattern as Phase 31). Goal-backward verification supplied retroactively by milestone integration checker (all CRED-04..07 wiring PASS)
- 4 missing/partial Nyquist VALIDATION.md files (33 draft, 33.1/34/35 missing) — non-blocking; revert-proof regression pattern + AST meta-tests provide equivalent coverage per CLAUDE.md regression-test scope policy
- Cross-cutting `mcp_admin` hardcodes in non-resolver code paths (~20 sites across 6 files: `infrastructure_crud.py`, `vm_operations.py`, `ssh_connection.py`, `ssh_tools.py:565/583`, `service_installer.py`, `tool_schemas/service_tools_schema.py`). NONE on the credential-resolution path; downstream consumers. Strong v1.7 candidate
- Carried from v1.5 close: 31-VERIFICATION.md missing, 31/32-VALIDATION.md gaps, SUMMARY frontmatter shape inconsistency

**v1.7 candidates (deferred):** SSH-04 per-call timeout to handshake, QUAL-01 Proxmox iso/cdrom mutual exclusivity, HTTP-01 truthy variants, SSH-03 disambiguation (partially shipped — verify scope), SSH-05 (NOTE: `verify_mcp_admin_access` was deleted in 33.1; revisit), ERR-02 resolver error wrapping, cross-cutting mcp_admin cleanup

---

## v1.5 Critical Bug Fixes (Shipped: 2026-04-20)

**Phases completed:** 2 phases, 7 plans
**Timeline:** 19 days elapsed (Apr 2 - Apr 20, 2026); active work Apr 19-20
**Stats:** 43 commits, 82 files changed, +11,987 / -87 lines
**Audit verdict:** `tech_debt` — all functional coverage sound; 4 process-level bookkeeping items accepted as deferred debt

**Key accomplishments:**
1. **WS-01** — WebSocket PTY handler closes socket on EOF/error paths; `contextlib.suppress(Exception)` for idempotent cleanup eliminates zombie shell sessions
2. **SSH-01** — Extracted `_sudo_run` helper with consistent `check=` forwarding across both password and no-password sudo branches; non-zero exits now raise in both paths
3. **ERR-01** — Timeout error messages report computed `effective_timeout` value (e.g., `35.0 seconds`) instead of raw `timeout_seconds` decorator default
4. **SCH-01** — `credential_type` in `list_keyring_credentials` schema constrained to `enum: ["ssh", "proxmox"]`; MCP framework rejects arbitrary strings before handler runs
5. **SSH-02** — Fixed broken always-passing ternary assertion in `test_ssh_tools.py`; added AST meta-guard that fails on `assert X or <structurally-always-true>` patterns, extended in 32-05 to catch the `Compare(Constant in X)` form
6. **REG-01** — 5/5 revert-proof regression tests across `test_http_app.py`, `test_ssh_tools.py`, `test_error_handling.py`, `test_tools.py`; integration checker verified 0 broken / 0 weak wirings

**Known gaps (deferred tech_debt):**
- Missing `31-VERIFICATION.md` — Phase 31 merged on plan-SUMMARY evidence; Phase 32 regressions re-prove each fix via integration, but the phase-level gate was skipped
- `31-VALIDATION.md` status: draft; `nyquist_compliant: false`
- Missing `32-VALIDATION.md` entirely
- SUMMARY frontmatter inconsistency: `32-01` flat `requirements-completed:` vs `32-02..05` nested `requirements:` — both parse but extraction inconsistent
- Known deferred items at close: 7 false-positive quick-task audits from earlier milestones (see STATE.md Deferred Items)

---

## v1.4.1 Security Patch (Shipped: 2026-04-01)

**Phases completed:** 1 phase, 2 plans
**Timeline:** 1 day (Apr 1, 2026)
**Stats:** 11 commits, 4 files changed, +479 / -587 lines

**Key accomplishments:**
1. Closed TOFU TOCTOU race condition (SEC-02) — `threading.Lock` widened to cover entire check+store sequence in `validate_host_public_key`; concurrent first-connections can no longer write conflicting known_hosts entries
2. Eliminated shell command injection in `setup_remote_mcp_admin` (SEC-01) — public key content now delivered via SFTP tmpfile; `grep -Ff` and `cat` read from file instead of f-string interpolation

**Known gaps (deferred):**
- SSH-01: Keyring auto-injection disambiguation for multiple credentials per hostname
- SSH-02: Per-call timeout forwarding to `ssh_connect()` handshake
- SSH-03: `verify_mcp_admin_access()` not using resolved port/credentials
- ERR-01: `resolve_ssh_credentials()` unhandled exception path
- ERR-02: WebSocket PTY reader not closing on EOF/error
- QUAL-01: Proxmox `iso`/`cdrom` mutual exclusivity not enforced
- QUAL-02: `test_http_app.py` EOF test exercising local copy

---

## v1.4 Real-World Reliability (Shipped: 2026-03-20)

**Phases completed:** 9 phases, 16 plans
**Timeline:** 5 days (Mar 15-19, 2026)
**Stats:** 91 commits, 86 files changed, +11,406 / -230 lines | ~15,554 LOC src + ~17,569 LOC tests

**Key accomplishments:**
1. Fixed SSH TOFU known_hosts corruption — `export_public_key()` comment field leak stripped; dead `asyncio.Lock` replaced with `threading.Lock` so TOFU lock actually works
2. Fixed PTY interactive shell — inverted dimensions (24×80 → 80×24), blocking read replaced with `asyncio.wait_for`, explicit `[Connection closed]` EOF notification
3. Added `connect_to_device` onboarding prompt — 6-step sequence covering setup, registration, credentials, discovery, and verification; includes keyring desync warning log
4. Keyring auto-resolve for admin tools — `setup_mcp_admin` and `update_mcp_admin_groups` resolve credentials from keyring; no explicit password required
5. Sudo password piping via stdin (`sudo -S`) — eliminates shell injection and bootstrap timeout for password-based sudo users; distinct errors for wrong password vs not-in-sudoers
6. Synced all tool schemas to function signatures — removed phantom `port` from SERVICE_TOOLS, fixed SSH timeout mismatches, made `username` optional in discover tools, exposed 7 hidden Proxmox VM/LXC parameters
7. Fixed phantom tools in prompts — `list_installed_services` replaced with `get_service_status`; `host=` → `hostname=` fixed in both `connect_to_device` and `deploy_service_workflow` prompts; regression guards added

---

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
