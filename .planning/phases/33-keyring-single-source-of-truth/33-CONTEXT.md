# Phase 33: Keyring Single Source of Truth - Context

**Gathered:** 2026-04-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the OS keyring the only place remote SSH credentials are stored on the server side. Delete the parallel `ssh_credentials` DB table, remove the `mcp_admin` hardcoded default-key fallback, remove the `setup_mcp_admin` MCP tool, and close the `register_server` verify-bypass. After this phase, no MCP tool writes credentials and no credential path inside the server reads from SQLite.

Scope anchors: CRED-04, CRED-05, CRED-06, CRED-07.

Out of this phase: fresh-device bootstrap of the `mcp_admin` OS user (deferred); cluster-scoped Proxmox tokens (Phase 34); auto-migration of legacy DB rows into the keyring (explicit Out of Scope in `REQUIREMENTS.md`).

</domain>

<decisions>
## Implementation Decisions

### DB Table Removal (CRED-04)
- **D-01:** Active drop on startup. `migration.py` runs `DROP TABLE IF EXISTS ssh_credentials` as a one-time migration step on both SQLite and Postgres adapters. Clean visible schema, no orphan rows left behind.
- **D-02:** Remove the credential-specific methods from both database adapters entirely — `add_credential`, `get_credential_by_hostname`, `get_credential_by_id`, `update_credential`, `delete_credential`, `list_credentials` (database-side), and the `is_active` toggle. Any future re-introduction of SSH credentials in the DB would have to rebuild the method surface from scratch.
- **D-02a:** Keep non-credential DB methods (drift_baselines, devices, etc.) unchanged — only credential helpers are removed.

### `register_server` (CRED-07)
- **D-03:** `register_server` becomes **verify-only**. Accepts `hostname`, `username`, `port`, `display_name`. Does NOT accept `password` or `key_path`. Does NOT write anywhere.
- **D-04:** Behavior: calls `resolve_ssh_credentials()` (keyring-only resolver after D-08), opens one SSH verify connection, returns `{status, hostname, username, verified: true|false}`. No `verify_connection=False` escape hatch — verification is mandatory.
- **D-05:** On missing keyring entry OR verify failure, returns an actionable error naming `homelab-mcp credentials add <hostname> <username>` as the fix. No silent pass-through, no default-user retry.
- **D-06 (guiding principle):** **Passwords never enter chat.** The MCP tool surface has zero write paths for credentials after this phase. All credential CRUD (add / list / remove / update) goes through the `homelab-mcp credentials` CLI subcommand, which reads secrets from TTY stdin with echo suppression.
- **D-07:** The `verify_connection` flag parameter and its code path are removed from `register_server`. The test suite loses the `verify_connection=False` test path.

### `mcp_admin` Default Fallback (CRED-05)
- **D-08:** Remove the implicit `mcp_admin` + default-key fallback in `resolve_ssh_credentials()` entirely. Delete the code block that injects `~/.ssh/mcp/mcp_admin_key` when `username == "mcp_admin"` (current ssh_tools.py lines ~128–138 and the matching `not resolved_key_path and username == "mcp_admin"` branch at lines ~112–116). After this change, `resolve_ssh_credentials()` has exactly two tiers: explicit args, then keyring. No third tier.
- **D-09:** Extend the `credentials add` CLI with a `--key-path <path>` flag. Keyring stores the path string (a filesystem pointer, not a secret) under the same `(hostname, username, type=ssh)` key used for passwords. The JSON hostname registry gains an `auth_type: "password" | "key"` field. This gives key-auth users a CLI-managed hostname→key-path mapping, parity with password-auth users.
- **D-09a:** The `~/.ssh/mcp/mcp_admin_key` key file itself is NOT deleted or auto-generated in this phase. Whatever currently generates it on first run can stay; it just stops being implicitly auto-injected. Users who want to use it must explicitly attach it via `credentials add <host> mcp_admin --key-path ~/.ssh/mcp/mcp_admin_key`.

### `setup_mcp_admin` Removal (CRED-06)
- **D-10:** Remove `setup_mcp_admin` from the MCP tool surface: delete the schema entry in `tool_schemas/ssh_tools_schema.py`, delete the handler in `tool_handlers/ssh_handlers.py` (`handle_setup_mcp_admin`), delete the dispatch entry in `tool_handlers/__init__.py`, delete the annotation entry in `tool_annotations.py`, delete the two `setup_mcp_admin` string references in `openapi_app.py` (lines ~70 and ~146). MCP clients see one fewer tool at `tools/list`.
- **D-11:** Delete `setup_remote_mcp_admin` implementation from `ssh_tools.py` and its associated helpers that exist solely to support it. Keep `update_mcp_admin_groups` and `verify_mcp_admin_access` — they remain valid operations against an already-bootstrapped `mcp_admin` user.
- **D-12:** Out-of-band bootstrap of the `mcp_admin` OS user on a fresh device (previously what `setup_mcp_admin` did) is OUT of scope for v1.6. Documentation in `docs/` must describe the manual path (user SSHs in as root or an existing sudoer, creates `mcp_admin`, adds the MCP pubkey to `authorized_keys`, grants sudoers). A proper CLI-driven bootstrap (`homelab-mcp bootstrap <host>`) is a deferred idea for v1.7+.

### `connect_to_device` Prompt Rewrite (forced by D-10, D-03)
- **D-13:** Rewrite the prompt in `prompt_registry.py` (`_build_connect_to_device_result`). New step sequence:
  1. (Manual / out-of-band) Ensure `mcp_admin` exists on the device with the MCP pubkey installed. Document link instead of a tool call.
  2. Run CLI `homelab-mcp credentials add <hostname> mcp_admin` (password or `--key-path`).
  3. Call `register_server` with `hostname="<hostname>"` — this verifies the stored credential end-to-end.
  4. Call `ssh_discover` with `hostname="<hostname>"` — hardware/system info.
  5. Call `discover_and_map` with `hostname="<hostname>"` — sitemap.
  6. Call `verify_mcp_admin` with `hostname="<hostname>"` — confirm sudo/admin access.
- **D-14:** The prompt no longer tells the AI to call `setup_mcp_admin` or `register_server --username=... --verify_connection=False`. Any regression that re-introduces those calls is caught by existing prompt-parameter regression tests (v1.4 pattern).

### Regression Guards
- **D-15:** AST meta-test extending the Phase 32 pattern — scans `src/homelab_mcp/**/*.py` and fails if any non-test file contains the string `ssh_credentials` or references a removed DB method (`add_credential`, `get_credential_by_hostname`, etc.). Revert-proof: if a future change re-introduces the DB path, the meta-test fires at test time.
- **D-16:** Positive keyring-path tests: assert `resolve_ssh_credentials()` returns the keyring-backed credential when a registry entry exists, and raises `CredentialNotFoundError` with the CLI-pointing message when it doesn't. Covers both password-auth and key-path-auth cases after D-09.
- **D-17:** Negative `mcp_admin`-fallback test: monkeypatch `list_credentials` to return empty, call `resolve_ssh_credentials(hostname="anything", username="mcp_admin")`, assert `CredentialNotFoundError` is raised (no silent default-key injection).

### Claude's Discretion
- Exact file-layout of the DROP TABLE migration step (new migration module vs inline in `init_schema`) — planner chooses; must be idempotent on repeated startups.
- Exact error-message wording for `CredentialNotFoundError` variants — existing message already names the CLI; minor wording polish is planner's call.
- How documentation pages are laid out for the manual `mcp_admin` bootstrap description — docs location and structure are planner's call so long as it's discoverable from the onboarding flow.
- Whether `--key-path` validation (file exists? readable? permissions 0600?) is strict or permissive — planner picks; strict is preferred for actionable errors.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope
- `.planning/ROADMAP.md` §Phase 33 — Goal + 5 success criteria (DB table gone, no `mcp_admin` fallback, `setup_mcp_admin` removed, `register_server` uses standard resolve path, tests pass).
- `.planning/REQUIREMENTS.md` §v1.6 Requirements — CRED-04 / CRED-05 / CRED-06 / CRED-07 definitions plus the Out-of-Scope table entries ("no auto-migration", "no per-request credential override", "no new SSH/Proxmox features").
- `.planning/PROJECT.md` §Key Decisions — `credential_store.py` no-homelab_mcp-imports constraint, keyring lazy-import pattern, JSON hostname registry decision, `_SERVICE_NAMES` namespacing.

### Keyring Foundation (v1.3 background)
- `.planning/milestones/v1.3-phases/17-credential-store-foundation/17-01-SUMMARY.md` — Original `credential_store.py` contract: `get_credential` / `set_credential` / `list_credentials` / `delete_credential`, headless-safe exception handling, JSON hostname registry.
- `.planning/milestones/v1.3-phases/19-credential-auto-inject/19-01-SUMMARY.md`, `.planning/milestones/v1.3-phases/19-credential-auto-inject/19-02-SUMMARY.md` — How keyring entries are auto-resolved in SSH tools and Proxmox client (the tier ordering pattern).

### Keyring Hardening (v1.4 background)
- `.planning/milestones/v1.4-phases/24-keyring-password-handling/24-01-SUMMARY.md`, `.planning/milestones/v1.4-phases/24-keyring-password-handling/24-02-SUMMARY.md` — Password-based keyring auto-inject for `setup_mcp_admin` / `update_mcp_admin_groups`; desync detection warning pattern.

### Regression Guard Pattern
- `.planning/milestones/v1.5-phases/32-regression-tests/32-CONTEXT.md` + Phase 32 AST-meta-test summaries — template for the D-15 revert-proof meta-test.

### Source Files Affected
- `src/homelab_mcp/database.py` (~lines 220–640 SQLite, ~lines 780–1230 Postgres) — DROP TABLE + method deletion.
- `src/homelab_mcp/migration.py` (~lines 27–150) — SQLite + Postgres migration paths.
- `src/homelab_mcp/ssh_tools.py` (~lines 42–144 `resolve_ssh_credentials`, ~lines 700–750 `setup_remote_mcp_admin`, ~lines 870–950+ `register_server`).
- `src/homelab_mcp/tool_schemas/ssh_tools_schema.py` (~line 33 `setup_mcp_admin` schema).
- `src/homelab_mcp/tool_handlers/ssh_handlers.py` (~line 24 handler), `tool_handlers/__init__.py` (~lines 61, 85 dispatch), `tool_annotations.py` (~line 92).
- `src/homelab_mcp/prompt_registry.py` (~lines 125–147 `_build_connect_to_device_result`).
- `src/homelab_mcp/openapi_app.py` (~lines 70, 146 tool allow-lists).
- `src/homelab_mcp/shell_session.py` (~line 89) — indirect consumer of `resolve_ssh_credentials`; verify behavior after D-08.
- `src/homelab_mcp/tool_handlers/credential_handlers.py` (~line 15) — `register_server` MCP handler needs signature trim to match D-03.
- CLI: the existing `homelab-mcp credentials add` subcommand (check `src/homelab_mcp/__main__.py` and any `cli/` module) — gains `--key-path` flag per D-09.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `credential_store.py` — `get_credential`, `set_credential`, `delete_credential`, `list_credentials` already exist and meet v1.6 needs. No new module required.
- `CredentialNotFoundError` in `ssh_tools.py` already carries an actionable message naming `credentials add`. Keep as-is; planner only confirms the message wording still matches post-change code paths.
- Phase 32 AST-meta-test harness in `tests/` — template for D-15 (scan-source-for-forbidden-strings pattern).
- `_sudo_run` helper in `ssh_tools.py` — unchanged, continues to serve `update_mcp_admin_groups` and `verify_mcp_admin_access` after `setup_remote_mcp_admin` is deleted.

### Established Patterns
- **Lazy keyring import** inside each function body — must be preserved in any new code that touches the keyring (headless-Linux D-Bus safety).
- **JSON hostname registry alongside keyring** — D-09's `auth_type` field is a registry JSON change, not a keyring schema change. Backward compat for existing password-only entries needed (missing `auth_type` defaults to `"password"`).
- **Module-level imports in ssh_tools / proxmox_api for monkeypatching** — preserve when editing `resolve_ssh_credentials()` so pytest-mock tests still work.
- **Revert-proof regression tests** (v1.5 pattern) — every decision in this CONTEXT must have at least one test that fails if the change is reverted.

### Integration Points
- `resolve_ssh_credentials()` is the single funnel — every SSH-touching module (`ssh_tools.py`, `shell_session.py`, `proxmox_api.py` indirectly via its own resolver) flows through it. Change this function and the rest of the server follows.
- `migration.py` runs once per server startup via `init_schema()` call paths. The DROP TABLE migration attaches here.
- `tool_schemas/`, `tool_handlers/`, `tool_annotations.py`, and `openapi_app.py` must all lose `setup_mcp_admin` in lock-step — the quality-gate CI from v1.2 (schema/annotation parity enforced) will fail otherwise, which is intentional safety net.
- `prompt_registry.py` `_build_connect_to_device_result` is the only prompt that names `setup_mcp_admin` / `register_server`-as-write; no other prompt needs rewriting.

</code_context>

<specifics>
## Specific Ideas

- **Password redirection rule, verbatim from the user:** "I don't really want password to be typed in chat with the agent; it should redirect to the CLI to do CRUD actions on the keyring." — This is an absolute principle for the phase. Any MCP tool that would otherwise accept a `password=` argument must instead return an error pointing to `homelab-mcp credentials add`.
- **Keyring-first failure mode, verbatim from the user:** "Since the keyring is source of truth, if agent is asked to take an action on a server with hostname, it should fail if there isn't a keyring entry and fall back to asking user to use the CLI." — Drives D-05, D-06, D-17.
- Key-auth users get CLI parity via `--key-path` (D-09) so they have one consistent surface: `homelab-mcp credentials add <host> <user> [--key-path PATH]`. No second code path where key-auth is a privileged side-channel.

</specifics>

<deferred>
## Deferred Ideas

- **Fresh-device `mcp_admin` bootstrap CLI** — `homelab-mcp bootstrap <host> --admin-user <existing-user>` that prompts for the existing sudoer's password on the terminal (never via MCP), SSHs in, creates `mcp_admin`, installs MCP pubkey, sets sudoers. Previously implicit in `setup_mcp_admin`. Candidate for v1.7 milestone scoping. (v1.6 docs describe the manual out-of-band path instead.)
- **Auto-migration of legacy DB rows into the keyring** — explicit Out of Scope per `REQUIREMENTS.md`. Users with credentials stored only in the dropped DB table re-add via `credentials add`. A future phase could add a one-shot `homelab-mcp migrate-credentials` CLI that walks a legacy `.homelab_mcp/homelab.db` and emits `credentials add` commands to stdout (leaving the user in control of what gets written to the keyring).
- **Encrypted keyring backups / export** — explicit Out of Scope (homelab user manages their own keyring).
- **Provisioning script shipped with the package** (`scripts/bootstrap-mcp-admin.sh`) — simpler alternative to the `bootstrap` CLI for v1.7; captured as a candidate approach.
- **Per-tool-call credential override via MCP args** — rejected in Out of Scope; kept out permanently by D-06.

</deferred>

---

*Phase: 33-keyring-single-source-of-truth*
*Context gathered: 2026-04-20*
