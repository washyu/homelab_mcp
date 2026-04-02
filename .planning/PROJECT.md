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

### Active

<!-- v1.5 Critical Bug Fixes -->
- [ ] WebSocket PTY reader closes websocket on EOF/error — no zombie sessions left open
- [ ] Timeout error message uses `effective_timeout` (not raw `timeout_seconds`) in `error_handling.py`
- [ ] `_sudo_run` with `check=True` raises on non-zero exit in password branch
- [ ] `credential_type` schema constrained to `enum: ["ssh", "proxmox"]`
- [ ] `test_ssh_tools.py` password assertion fixed — broken ternary replaced with explicit check
- [ ] Regression tests guard all 5 fixes against recurrence

<!-- Deferred to future milestone -->
- [ ] Keyring auto-injection disambiguates multiple usernames per hostname — no silent wrong-user logins
- [ ] SSH timeout propagated to `ssh_connect()` — per-call timeout covers handshake, not just outer `wait_for`
- [ ] `verify_mcp_admin_access()` uses resolved port/credentials from `resolve_ssh_credentials()`
- [ ] `resolve_ssh_credentials()` wrapped in error handler — raises return JSON error payloads, not raw exceptions
- [ ] Proxmox schema enforces `iso`/`cdrom` exclusivity via `oneOf`
- [ ] `test_http_app.py` EOF test drives production `handle_shell_websocket` instead of a local copy
- [ ] HTTP mode flag accepts common truthy variants (`1`, `yes`, `on`), not just literal `"true"`

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

- Shipped v1.4.1 security patch on top of v1.4 — 2 critical security fixes (SEC-01 shell injection, SEC-02 TOFU race condition)
- v1.4 baseline: ~15,554 LOC Python (src/) + ~17,569 LOC tests | 86 files changed from v1.3 baseline
- Tech stack: Python 3.12+, uv, asyncssh, mcp[cli], aiohttp, keyring, SQLite
- 56 tools: 50 original + 6 `*_preview` variants, organized into 7 categories
- Available on PyPI as `homelab-mcp` 1.4.0 — install via `uvx homelab-mcp` or `pip install homelab-mcp`
- MCP protocol surface complete: Tools + Resources + Prompts + Notifications
- 4 workflow prompts: `connect_to_device`, `decommission_device_workflow`, `deploy_service_workflow`, `homelab_health_check`
- All prompts now use correct parameter names (`hostname=`) with regression tests guarding against regressions
- Key v1.4 patterns: `_sudo_run` helper for all sudo calls, `asyncio.wait_for` for non-blocking PTY reads, `threading.Lock` for TOFU host key validation

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

## Current Milestone: v1.5 Critical Bug Fixes

**Goal:** Close all critical and high-priority bugs from CodeRabbit PR #39 review with regression tests to prevent recurrence.

**Target fixes:**
- WebSocket PTY reader zombie session closure (ERR-02)
- Timeout error reporting using wrong variable
- `_sudo_run` `check=True` not checking exit code in password branch
- `credential_type` schema enum constraint
- Broken test assertion (always-passing ternary)
- Regression tests for all 5 fixes

---
*Last updated: 2026-04-02 after v1.5 milestone start*
