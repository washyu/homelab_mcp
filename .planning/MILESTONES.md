# Milestones

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
