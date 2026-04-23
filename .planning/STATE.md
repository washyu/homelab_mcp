---
gsd_state_version: 1.0
milestone: v1.6
milestone_name: Credential Architecture Cleanup
status: "Phase 34 complete — all 4/4 plans done. get_proxmox_client async + INJECT-03 deleted + resolver wired."
stopped_at: Phase 34 Plan 03 complete — async get_proxmox_client wiring (D-10, D-12), INJECT-03 deleted, 9 await call sites propagated
last_updated: "2026-04-23T21:00:00.000Z"
last_activity: "2026-04-23 -- Phase 34 Plan 03 executed: async get_proxmox_client wiring (fd218e4, 708e5fb); Phase 34 all 4/4 plans complete"
progress:
  total_phases: 8
  completed_phases: 2
  total_plans: 14
  completed_plans: 14
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-20 after v1.6 start)

**Core value:** Every tool in the server actually works — a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.
**Current focus:** Phase 34 complete (Cluster-Scoped Proxmox Credentials) — v1.6 milestone at 14/14 plans; next up Phase 35 when ready

## Current Position

Phase: 34 (Cluster-Scoped Proxmox Credentials) — COMPLETE
Plan: 4 of 4 complete; 0 remaining
Status: Plan 03 complete — async get_proxmox_client wired to resolver, INJECT-03 shortcut deleted (D-12), 9 await call sites propagated. Phase 34 all 4 plans done.
Last activity: 2026-04-23 -- Phase 34 Plan 03 executed (fd218e4, 708e5fb)

Progress: [█████████░] 93% (13/14 plans) — Phase 34 Plan 04 done

## Milestone Origin

v1.6 anchors on the Phase 33 idea originally drafted at commit `8ac2270` on 2026-04-19 (credential-cleanup branch). That commit's narrative labeled v1.4/v1.5 as "parked/broken" — superseded. v1.4/v1.4.1/v1.5 all shipped cleanly. v1.6 picks up the actual credential cleanup scope from that commit's SPEC without the stale narrative.

## Deferred Items (carried from v1.5 close)

| Category | Item | Status | Notes |
|----------|------|--------|-------|
| tech_debt | 31-VERIFICATION.md missing | deferred | Phase 31 merged on plan-SUMMARY evidence; Phase 32 revert-proof regressions re-prove each fix via integration |
| tech_debt | 31-VALIDATION.md draft | deferred | Nyquist validation incomplete |
| tech_debt | 32-VALIDATION.md missing | deferred | No Nyquist VALIDATION.md for regression-tests phase |
| tech_debt | SUMMARY frontmatter shape inconsistency | deferred | 32-01 flat vs 32-02..05 nested |
| v1.7_candidate | SSH-04 per-call timeout handshake | deferred | Not credential-architecture; v1.7 candidate |
| v1.7_candidate | QUAL-01 Proxmox iso/cdrom exclusivity | deferred | Schema correctness; v1.7 candidate |
| v1.7_candidate | HTTP-01 HTTP flag truthy variants | deferred | Ergonomic polish; v1.7 candidate |
| v1.7_candidate | SSH-03/SSH-05/ERR-02 credential-adjacent | deferred | Scoped out of v1.6 Tier A — could fit v1.6.x or v1.7 |

## Accumulated Context

### Decisions

Full v1.0-v1.5 decision logs in `.planning/milestones/v{X.Y}-ROADMAP.md`.

Active patterns established through v1.5:

- `contextlib.suppress(Exception)` around `websocket.close()` — idempotent cleanup for PTY session teardown
- Quoted return annotations for non-subscriptable third-party classes (e.g., `'asyncssh.SSHCompletedProcess'`) — defers evaluation safely under mypy and runtime
- AST meta-tests for lint-style regression guards — catches tautological-assertion bugs that no single positive regression test can catch
- Report computed/derived values in error messages (`effective_timeout`), not raw decorator parameters
- JSON Schema `enum` keyword for fixed-choice MCP tool parameters — validated at framework boundary before handler runs

Phase 34 Plan 03 decisions (added 2026-04-23):

- get_proxmox_client converted to async def; INJECT-03 'first registry entry' shortcut block deleted entirely (D-12); resolver call inserted for host-known + no-auth path (D-10); explicit api_token or username+password bypasses resolver (SC-5).
- All 9 internal call sites in proxmox_api.py updated to await get_proxmox_client(host=host, session=session) via replace_all edit.
- Patch target for new TestGetProxmoxClientAsync tests is src.homelab_mcp.proxmox_api.resolve_proxmox_credentials (matches test file import convention); homelab_mcp.proxmox_api path does not intercept the call.
- All @patch("src.homelab_mcp.proxmox_api.get_proxmox_client") decorators in consumer-function test classes changed to new_callable=AsyncMock — MagicMock cannot be awaited.
- test_client_missing_credentials changed from ValueError('Must provide...') to CredentialNotFoundError raised by mocked resolver — behavior change is correct since host+no-auth now routes through resolver.
- test_get_proxmox_client_keyring_fallback (INJECT-03 test) deleted; replaced with explanatory comment per D-16a (no AST meta-test for shortcut removal in greenfield phase).
- CredentialNotFoundError imported via src.homelab_mcp.ssh_tools in test body to avoid headless home-dir RuntimeError from lazy module-level path expansion in credential_store.py.

Phase 34 Plan 04 decisions (added 2026-04-23):

- post-parse validation chosen over subparsers for conditional-positional: hostname made nargs="?" on add/remove; _parse_scope_arg() rejects ill-formed combinations after argparse runs. Matches --key-path precedent.
- _parse_scope_arg placed as module-level private def above _cmd_credentials_add; raises ValueError for callers to translate to stderr + exit(1).
- unregister_cluster_credential added to credential_store.py (not inlined in server.py) to keep registry mutation logic encapsulated in the store module.
- Per-node paths in all three handlers byte-for-byte equivalent to pre-Plan-04 behavior — SC-5 CLI back-compat maintained.
- tests/test_credential_handlers.py created fresh (did not exist before Plan 04); 4 tests for D-17a handler display tweak.
- tools.py / tool_schemas/ not touched — D-17 schema-unchanged proof: git diff 42151c5..HEAD shows empty diff for both schema files.

Phase 34 Plan 02 decisions (added 2026-04-23):

- Top-level import of CredentialNotFoundError from .ssh_tools used (no circular import — ssh_tools does not import proxmox_api). noqa: F401 suppresses "imported but unused" since the name is re-exported for consumers.
- ProxmoxAPIClient.get() strips the "data" wrapper (returns list directly from line 175). Defensive rows = status if isinstance(status, list) else [] branch is sufficient; dict fallback not needed.
- Throwaway ProxmoxAPIClient per candidate cluster entry for /cluster/status probe — reuses all auth header/session logic with zero new HTTP plumbing (PATTERNS.md §3 pattern).
- Plain dict for _HOST_CLUSTER_CACHE — allows _HOST_CLUSTER_CACHE.clear() in test autouse fixture; functools.lru_cache not used (Claude's Discretion per CONTEXT.md).
- resolve_proxmox_credentials placed at line 194, immediately above get_proxmox_client, for locality with the consumer.

Phase 34 Plan 01 decisions (added 2026-04-23):

- scope/cluster_name added as keyword-only params (after `*`) to `register_credential`, `store_credential`, `get_credential`, `delete_credential` — preserves all existing positional call sites unchanged.
- Cluster entry upsert dedup key is `(cluster_name, username, credential_type)` per D-08a — hostname intentionally not compared so re-running with a different host arg (or `""`) still upserts the same cluster row.
- `_keyring_key(username, hostname, scope, cluster_name)` is a plain module-level private def inserted just above `store_credential` — single source of truth for the `@cluster:` key form (D-03).
- `identity` variable used in all three keyring-helper fallback log messages so cluster calls log `cluster:<name>` instead of empty string.
- Pre-existing failures in `test_database.py::test_ssh_credentials_table_dropped_postgres` and `test_proxmox_api.py::TestGetProxmoxClient::test_client_missing_host` confirmed pre-existing on baseline; out of scope for Plan 01 (scope-boundary rule).

Phase 33.1 Plan 04 decisions (added 2026-04-23):

- End-to-end unit-test keyring resolution proof: monkeypatch the KEYRING boundary (`list_credentials`/`get_credential`) and the NETWORK boundary (`ssh_connect`) — do NOT monkeypatch the resolver or the discovery helper. Full call stack executes, regressions in any intermediate layer surface as test failures.
- Lazy-import monkeypatch target: when a module lazy-imports a name inside a function body (like `sitemap.py`'s `from .ssh_tools import ssh_discover_system`), tests must monkeypatch on the SOURCE module (`ssh_tools`), not the IMPORTING module (`sitemap`) — the name resolves against the source at call time.
- Docstring `mcp_admin` cleanup: when removing a hardcoded default, also strip the quoted literal from explanatory docstrings/comments so grep-based audits (Phase 33 D-13 intent) stay clean. Future-proof against confusion in retroactive audits.

Phase 33.1 Plan 03 decisions (added 2026-04-23):

- Two-shape MCP tool-surface deletion: when removing a tool, `tool_annotations.py` needs BOTH a list-entry deletion (`_READ_ONLY_TOOLS`) AND a dict-entry deletion (`_MUTATING_ANNOTATIONS`) — the structural shape differs per mutating-hint profile. Import-time parity assertion must explicitly test `tool_name not in TOOL_ANNOTATIONS` to catch both shapes (extends Phase 33 5-way to 7-way parity: schema + handler + dispatch + annotation-list + annotation-dict + openapi allowlist + openapi category).
- Orphan-test pruning scope: when deleting an MCP tool schema, ALL tests that key into the removed schema must be deleted alongside the explicit plan list — not just the ones the plan enumerates. Rule-3 blocking (KeyError prevents test sweep pass) forces the sweep. Phase-33 convention: delete tests, don't skip them, and replace with 1-3 line comment citing the removal decision (D-05).
- `ssh_execute_command(command="sudo -n true")` as the generic "does this user have sudo" check replaces the removed `verify_mcp_admin` tool in the `connect_to_device` prompt. Exit code 0 = passwordless sudo available; non-zero = not configured. Works for any registered user, not just the literal mcp_admin account.
- Scope-boundary finding for Phase 33.2: `infrastructure_crud.py:30` and `vm_operations.py:25` carry dict-literal `"username": "mcp_admin"` in `get_device_connection_info()` returns — pre-existing, not in Phase 33.1's `files_modified`, and bypasses the Phase 33.1 D-08 AST guard because they aren't function-signature defaults. Recommend Phase 33.2 either extend `DEFERRED_MCP_ADMIN_DEFAULT_FILES` to include them OR fix both sites during the service-tool + downstream-infrastructure sweep.

Key constraints carried forward:

- `credential_store.py` must have no homelab_mcp imports — circular import prevention
- Every keyring call path must catch `NoKeyringError`, `RuntimeError`, and `Exception` — headless Linux primary deploy target
- `_sudo_run` helper is the only path for sudo invocation — single consistent `check=` forwarding
- PyPI OIDC trusted publisher registered at pypi.org; `git tag v*` push triggers publish

### Pending Todos

None.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 5 | we are missing the new cli arguments for the keystore in the command line help output | 2026-03-15 | 88e972f | [5-we-are-missing-the-new-cli-arguments-for](./quick/5-we-are-missing-the-new-cli-arguments-for/) |
| 6 | update README and setup docs to reflect v1.3 (PyPI/uvx, credentials CLI, Python 3.12+) | 2026-03-15 | 1357903 | [6-update-readme-and-setup-docs-to-reflect-](./quick/6-update-readme-and-setup-docs-to-reflect-/) |
| 7 | fix ssh tool schemas so the model knows about keyring auto-inject | 2026-03-15 | d261600 | [7-fix-ssh-tool-schemas-so-the-model-knows-](./quick/7-fix-ssh-tool-schemas-so-the-model-knows-/) |

### Blockers/Concerns

- PyPI OIDC trusted publisher must remain registered at pypi.org/manage/project/homelab-mcp/settings/publishing/ for future `git tag v*` pushes
- Human-only verifiable items: `homelab-mcp --version` in installed env, TTY echo suppression for `credentials add` — cannot be automated in headless CI
- v1.6 migration implications: users with credentials stored only in the DB `ssh_credentials` table will need to re-add via `credentials add` after the drop — no auto-migration planned (homelab scope, single-user)

## Session Continuity

Last session: 2026-04-23T21:00:00.000Z
Stopped at: Phase 34 Plan 03 complete — all 4/4 Phase 34 plans done. v1.6 milestone complete.
Resume command: /gsd-execute-phase 35 (next phase when ready)
