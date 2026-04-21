# Homelab MCP Server

## What This Is

A production-ready Python MCP (Model Context Protocol) server that gives AI assistants the ability to manage homelab infrastructure — discovering devices via SSH, managing VMs and containers, installing services, tracking network topology, and interacting with Proxmox. Ships with 56 tools across 7 categories, comprehensive documentation, security hardening, safe preview variants for all destructive operations, infrastructure drift detection, live infrastructure state via MCP Resources, four workflow prompt templates, and a secure credential store with OS keyring integration. Available via `uvx homelab-mcp` or `pip install homelab-mcp`. Targets homelabbers running Proxmox VE who want AI-powered infrastructure management through any MCP-compatible client.

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
- ✓ PyPI distribution — `uvx homelab-mcp` and `pip install homelab-mcp` — v1.2
- ✓ Version unified via `importlib.metadata` across all modules — v1.2
- ✓ `service_templates/*.yaml` bundled in wheel via `importlib.resources` — v1.2
- ✓ `homelab://drift/latest` MCP Resource with `notifications/resources/updated` — v1.2
- ✓ MCP Prompts capability — `prompts/list` and `prompts/get` with 3 workflow templates — v1.2
- ✓ 6 `*_preview` tool variants with `readOnlyHint=True` for confirmation-free dry runs — v1.2
- ✓ Schema/annotation parity enforced by CI (56/56 tools) — v1.2
- ✓ `credential_store.py` with headless-safe OS keyring integration — v1.3
- ✓ `homelab-mcp credentials add/list/remove` CLI subcommands (SSH and Proxmox types) — v1.3
- ✓ `homelab-mcp --version` flag — v1.3
- ✓ Credential auto-inject into SSH tools and Proxmox client — v1.3
- ✓ Automated PyPI publish via GitHub Actions OIDC trusted publishing on `git tag v*` — v1.3
- ✓ `decommission_device_workflow` prompt resolves hostname→`device_id` before calling decommission — v1.3
- ✓ TOFU known_hosts writes correct 3-field format (no comment leak); `asyncio.Lock` replaced with `threading.Lock` — v1.4
- ✓ PTY interactive shell streams in real time with correct 80×24 dimensions and explicit EOF notification — v1.4
- ✓ `connect_to_device` onboarding prompt — full 6-step device setup sequence — v1.4
- ✓ Keyring desync detection — warning logged when registry entry exists but keyring returns None — v1.4
- ✓ `setup_mcp_admin` and `update_mcp_admin_groups` resolve credentials from keyring (no explicit password required) — v1.4
- ✓ All sudo calls use `_sudo_run` helper with `sudo -S` stdin piping; distinct error for wrong password vs not-in-sudoers — v1.4
- ✓ All tool schemas synced to function signatures — phantom `port` removed, SSH timeouts fixed, 7 hidden Proxmox params exposed — v1.4
- ✓ `host=` → `hostname=` fixed in all prompt tool calls; phantom `list_installed_services` replaced with `get_service_status` — v1.4
- ✓ Regression guard tests for all prompt parameter names and phantom tool references — v1.4
- ✓ Shell command injection in `setup_mcp_admin` eliminated — public key delivered via SFTP tmpfile, never interpolated into shell strings — v1.4.1
- ✓ TOFU race condition closed — `threading.Lock` covers entire check+store TOCTOU window in `validate_host_public_key` — v1.4.1
- ✓ WebSocket PTY reader closes the socket on EOF and error paths — `contextlib.suppress(Exception)` around `websocket.close()` — v1.5
- ✓ Timeout error message reports computed `effective_timeout` (e.g., `35.0 seconds`), not the raw `timeout_seconds` decorator default — v1.5
- ✓ `_sudo_run` helper with consistent `check=` forwarding in both password and no-password sudo branches — v1.5
- ✓ `test_ssh_tools.py` password-propagation assertion fixed — broken disjunctive ternary replaced with explicit check, AST meta-guard added to catch reintroduction — v1.5
- ✓ `credential_type` parameter constrained to `enum: ["ssh", "proxmox"]` in `list_keyring_credentials` schema — v1.5
- ✓ Revert-proof regression tests guard all 5 v1.5 fixes; integration checker verified 0 broken / 0 weak wirings — v1.5

### Active

<!-- v1.6 Credential Architecture Cleanup -->
- [ ] SSH credentials stored exclusively in OS keyring — DB `ssh_credentials` table removed
- [ ] SSH tools no longer fall back to `mcp_admin` hardcoded defaults — explicit keyring entries required
- [ ] `setup_mcp_admin` MCP tool removed; device onboarding via `credentials add` CLI + `connect_to_device` prompt
- [ ] `register_server` validates credentials through standard resolve path — no verify-bypass
- [ ] Cluster-scoped Proxmox API tokens — one datacenter-wide token serves N cluster nodes

<!-- Deferred to future milestone -->
- [ ] SSH-03: Keyring auto-injection disambiguates multiple usernames per hostname
- [ ] SSH-04: SSH timeout propagated to `ssh_connect()` — per-call timeout covers handshake, not just outer `wait_for`
- [ ] SSH-05: `verify_mcp_admin_access()` uses resolved port/credentials from `resolve_ssh_credentials()`
- [ ] ERR-02: `resolve_ssh_credentials()` wrapped in error handler — raises return JSON error payloads, not raw exceptions
- [ ] QUAL-01: Proxmox schema enforces `iso`/`cdrom` exclusivity via `oneOf`
- [ ] HTTP-01: HTTP mode flag accepts common truthy variants (`1`, `yes`, `on`), not just literal `"true"`
<!-- QUAL-02 closed by v1.5 Phase 32-01 — WS-01 regression uses production `handle_shell_websocket` -->
<!-- Phase-31 VERIFICATION.md retroactive pass — tech debt from v1.5 close -->
<!-- 31/32 Nyquist VALIDATION.md finalization — tech debt from v1.5 close -->
<!-- SUMMARY frontmatter normalization (`requirements-completed` vs `requirements:`) — tech debt from v1.5 close -->

### Out of Scope

- Mobile/web UI — MCP clients provide the interface
- Multi-user / RBAC — homelab is single-operator
- PostgreSQL as default — SQLite is correct for single-user homelab
- Rate limiting — homelabbers won't overwhelm their own infra
- Kubernetes management — fundamentally different from Proxmox VMs/LXC
- Real-time monitoring/alerting — not Prometheus; expose point-in-time queries
- Offline mode — real-time is core value
- Per-device drift resources (`homelab://drift/device/{id}`) — requires per-device scans; single report sufficient
- Dynamic prompts (runtime-generated) — complexity without value for single-operator homelab
- FastMCP migration — would lose subscribe/unsubscribe, send_resource_list_changed, and ASGI middleware control
- Auto-detect drift with periodic background checks — on-demand scan is sufficient for now

## Context

- Shipped v1.5 Critical Bug Fixes — 5 CodeRabbit PR #39 findings closed (WS-01, SSH-01, SSH-02, ERR-01, SCH-01) with 5 revert-proof regression tests
- v1.5 audit verdict: `tech_debt` — functional coverage sound (6/6 requirements satisfied, 5/5 integrations WIRED); 4 process-level bookkeeping items deferred (missing Phase-31 VERIFICATION.md, both VALIDATION.md files incomplete, SUMMARY frontmatter shape inconsistency)
- v1.5 stats: 43 commits, 82 files changed, +11,987 / -87 lines; active work Apr 19-20 on top of scope defined Apr 2
- v1.4 baseline: ~15,554 LOC Python (src/) + ~17,569 LOC tests
- Tech stack: Python 3.12+, uv, asyncssh, mcp[cli], aiohttp, keyring, SQLite
- 56 tools: 50 original + 6 `*_preview` variants, organized into 7 categories
- Available on PyPI as `homelab-mcp` 1.4.0 — install via `uvx homelab-mcp` or `pip install homelab-mcp`
- MCP protocol surface complete: Tools + Resources + Prompts + Notifications
- 4 workflow prompts: `connect_to_device`, `decommission_device_workflow`, `deploy_service_workflow`, `homelab_health_check`
- All prompts use correct parameter names (`hostname=`) with regression tests guarding against regressions
- Key patterns now in production: `_sudo_run` helper for all sudo calls with consistent `check=` forwarding, `asyncio.wait_for` for non-blocking PTY reads, `threading.Lock` for TOFU host key validation, `contextlib.suppress(Exception)` for idempotent websocket cleanup, AST meta-tests for lint-style regression guards

## Constraints

- **Tech stack**: Python 3.12+, uv, asyncssh, mcp[cli] — established, not changing
- **Distribution**: PyPI (`uvx homelab-mcp`) as of v1.2; OIDC auto-publish as of v1.3
- **Target platform**: Linux primary (Proxmox hosts are Linux); headless-safe credential store
- **MCP compatibility**: Must work with any MCP-compatible client, not just Claude
- **Security**: SSH TOFU, Proxmox SSL, input validation, credential redaction all enforced

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fix security before 1.0 | Users shouldn't be vulnerable to MITM on their own network | ✓ Good — SSH TOFU, SSL default, validation, redaction all shipped |
| Implement all stubs | Called code that does nothing is a bug, not tech debt | ✓ Good — sitemap auto-update, device rediscovery, script install all working |
| Clone + uv sync distribution | Simplest path to 1.0, PyPI can come later | ✓ Good — proven; superseded by PyPI in v1.2 |
| Target Proxmox users | Clear persona, existing integration, testable | ✓ Good — clear scope, 10 Proxmox-specific tools |
| All tools must work | "Everything works" bar — no stubs, no broken tools | ✓ Good — 56 tools annotated and functional |
| MCP SDK lowlevel.Server (not FastMCP) | Maximum control over protocol details | ✓ Good — enabled custom lifespan, annotations, ToolError pattern; confirmed correct in v1.2 when FastMCP would have lost subscribe/unsubscribe |
| ResourceManager with module-level accessor | Avoids threading request_context through every handler | ✓ Good — proxmox_session fully threaded (DEBT-01 fixed in v1.1) |
| Pure ASGI middleware for Origin validation | Better performance than BaseHTTPMiddleware | ✓ Good — clean integration with Starlette middleware stack |
| APIKeyAuth as conditional ASGI wrapper | HTTP auth only activates when MCP_API_KEY is set | ✓ Good — stdio deployments unaffected; HTTP deployments secured |
| Local import of get_resource_manager in handlers | Avoids server.py → tool_handlers → server.py circular import | ✓ Good — clean pattern, reused in v1.1 (09/11) and v1.2 (13) |
| Dry-run handlers return flat dict | build_dry_run_response() not content-wrapped — _convert_result fallback handles it | ⚠️ Revisit — low severity but inconsistent with live-execution response format |
| drift_baselines uses UNIQUE(node, vmid, vm_type) + INSERT OR REPLACE | Upsert entirely in SQL, no application-level conflict handling | ✓ Good — clean, SQLite-idiomatic |
| scan_drift labels state findings as point-in-time observations | Avoids false positives from transient VM reboot states | ✓ Good — honest reporting design |
| homelab-mcp package name (vs homelab-mcp-server) | Shorter, cleaner; enables `uvx homelab-mcp` directly | ✓ Good — confirmed correct at publish time |
| importlib.metadata for version unification | Single source of truth in pyproject.toml, no version drift | ✓ Good — all 4 version-reporting sites unified |
| importlib.resources for service_templates | Required for PyPI wheel bundling — __file__ paths fail when installed | ✓ Good — 10 YAML files confirmed in wheel |
| Wave-0 TDD pattern (RED tests before implementation) | Contract-first development, forces API decisions before coding | ✓ Good — established in v1.1, scaled cleanly to 3 phases in v1.2, used in all 4 v1.3 phases |
| Preview handlers as thin delegation wrappers | dry_run=True injection is transparent; all dry-run logic stays in parent | ✓ Good — 3-line handlers, zero duplication |
| Lazy keyring import inside each function body | Prevents D-Bus probing during server startup on headless Linux | ✓ Good — server starts cleanly; keyring errors surfaced only at first lookup |
| JSON hostname registry alongside OS keyring | `list_credentials` needs enumerable host list; keyring has no enumerate API | ✓ Good — clean separation: keyring stores secrets, registry stores hostnames |
| `_SERVICE_NAMES` dict for credential namespacing | ssh/proxmox credentials in same keyring service need distinct service names | ✓ Good — clean namespace isolation; `_SERVICE_NAME` kept for backward compat |
| Module-level imports in ssh_tools/proxmox_api for monkeypatching | Function-body imports can't be patched by pytest-mock at test time | ✓ Good — module-level import in production modules; lazy pattern still used in credential_store itself |
| `set_defaults(func=_run_server)` argparse dispatch | Prevents bare `homelab-mcp` regression when subparsers added | ✓ Good — clean dispatch, bare invocation regression-tested |
| OIDC trusted publishing for PyPI | No stored secrets in GitHub; verified at publish time | ✓ Good — requires one-time manual trusted publisher registration at pypi.org before first tag push |
| `decommission_device_workflow` uses get_network_sitemap for device_id | Fixes PRMT-02: tool schema requires device_id, not hostname | ✓ Good — 5-step workflow; AI no longer hits schema validation errors |
| `_sudo_run` helper with `sudo -S` stdin piping | Shell injection risk and bootstrap timeout for password-based sudo | ✓ Good — clean abstraction, covers both setup_mcp_admin and update_mcp_admin_groups; distinct error messages |
| `threading.Lock` for TOFU `validate_host_public_key` | `asyncio.Lock` can't be acquired from sync callback context — was completely ineffective | ✓ Good — correct primitive for sync callback; existing asyncio call sites unaffected |
| `asyncio.wait_for(..., timeout=0.05)` for PTY reads | Blocking `stdout.read(4096)` would not return until 4096 bytes or EOF — browser saw nothing | ✓ Good — real-time streaming with tunable timeout |
| Gap-closure phases (26-29) added mid-milestone via audit | Audit revealed schema/prompt bugs not in original scope; extending milestone cleaner than deferring | ✓ Good — 4 extra phases closed all audit gaps before v1.5 planning |
| `contextlib.suppress(Exception)` around `websocket.close()` (v1.5 WS-01) | Idempotent cleanup without try/except boilerplate; matches module's existing contextlib usage | ✓ Good — eliminates zombie PTY sessions cleanly |
| Quoted return annotation `'asyncssh.SSHCompletedProcess'` on `_sudo_run` (v1.5 SSH-01) | Class is not subscriptable at runtime; mypy stubs have no generic support; string quoting defers evaluation | ✓ Good — type-safe under both mypy and runtime |
| AST meta-tests for lint-style regression guards (v1.5 SSH-02) | Tautological-assertion class of bugs can't be caught by a single positive regression test — parse the test file itself and walk the AST | ✓ Good — 32-02 detector extended in 32-05 to cover `Compare(Constant in X)` pre-fix form; guards future reintroduction |
| Report computed/derived values in error messages, not raw decorator parameters (v1.5 ERR-01) | Users see the actual number they were subject to (`effective_timeout`), not the unrelated input constant | ✓ Good — single-variable substitution, no helper refactor needed |
| JSON Schema `enum` for fixed-choice MCP tool parameters (v1.5 SCH-01) | MCP framework validates JSON Schema before handler runs; cheaper than handler-side validation and self-documenting | ✓ Good — `credential_type` rejects arbitrary strings at protocol boundary |
| Closed v1.5 with `tech_debt` verdict (not blocking) after inline ROADMAP reconcile | Revert-proof Phase-32 regressions make missing Phase-31 VERIFICATION.md a paperwork gap, not a risk gap | ⚠️ Revisit — if a future milestone repeats this pattern, consider building a retroactive verifier skill |

## Current State

**Shipped:** v1.5 Critical Bug Fixes (2026-04-20) — all 5 CodeRabbit PR #39 findings closed with revert-proof regression tests. Audit verdict: `tech_debt` (functional coverage sound; 4 process-level bookkeeping items deferred).

**Latest PyPI:** `homelab-mcp` 1.4.0 (v1.5 did not bump the PyPI version — v1.5 scope was bug fixes inside the 1.4.x line; next release tag will be cut when a future milestone ships).

## Current Milestone: v1.6 Credential Architecture Cleanup

**Goal:** The OS keyring becomes the single source of truth for remote credentials. The parallel DB `ssh_credentials` table, `mcp_admin` hardcoded defaults, and `setup_mcp_admin` bootstrap tool are removed. Proxmox API tokens can be stored at cluster scope so one credential serves all nodes in a datacenter.

**Target features:**
- Keyring-only SSH credential storage — drop the DB `ssh_credentials` table; no parallel store
- Remove `mcp_admin` hardcoded fallback — explicit keyring entries required (actionable error otherwise)
- Remove `setup_mcp_admin` MCP tool — device onboarding flows through `credentials add` CLI and the existing `connect_to_device` prompt
- Fix `register_server` verify-path bypass — registration validates credentials via the standard resolve path
- Cluster-scoped Proxmox API tokens — one datacenter-wide token shared across N nodes; per-node tokens remain supported

**Why this milestone:**
- v1.3 shipped keyring (`credential_store.py`) as a parallel layer next to the DB table for a fast, non-breaking rollout
- v1.4/v1.4.1 added keyring auto-inject to specific tools but kept the DB fallback
- v1.6 finishes the migration — keyring primary, DB removed, hardcoded fallbacks gone, Proxmox cluster model corrected

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-20 after v1.6 milestone start*
