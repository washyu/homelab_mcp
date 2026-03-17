---
gsd_state_version: 1.0
milestone: v1.4
milestone_name: Real-World Reliability
status: planning
stopped_at: Completed 26-01-PLAN.md
last_updated: "2026-03-17T07:25:25.169Z"
last_activity: 2026-03-13 — Roadmap created, phases 21-23 defined
progress:
  total_phases: 7
  completed_phases: 6
  total_plans: 10
  completed_plans: 10
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-13)

**Core value:** Every tool in the server actually works — a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.
**Current focus:** v1.4 Real-World Reliability — Phase 21: Core SSH Reliability

## Current Position

Phase: 21 of 23 (Core SSH Reliability)
Plan: — of — in current phase
Status: Ready to plan
Last activity: 2026-03-13 — Roadmap created, phases 21-23 defined

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0 (v1.4, starting)
- Average duration: — min
- Total execution time: — hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 21-core-ssh-reliability P01 | 4 | 2 tasks | 2 files |
| Phase 21-core-ssh-reliability P02 | 7 | 2 tasks | 4 files |
| Phase 22-agent-guidance P02 | 6 | 2 tasks | 8 files |
| Phase 22-agent-guidance P01 | 5 | 2 tasks | 7 files |
| Phase 23-workflow-completeness P01 | 8 | 2 tasks | 2 files |
| Phase 23-workflow-completeness P02 | 1 | 2 tasks | 2 files |
| Phase 24-keyring-password-handling P01 | 1 | 2 tasks | 2 files |
| Phase 24-keyring-password-handling P02 | 4 | 2 tasks | 2 files |
| Phase 25 P01 | 3 | 2 tasks | 2 files |
| Phase 26-sync-tool-schema-file-to-match-current-tool-parameters P01 | 3 | 2 tasks | 1 files |

## Accumulated Context

### Decisions

Full v1.0-v1.3 decision logs in `.planning/milestones/`.

Key constraints for v1.4 (from research):
- `asyncio.Lock` in `TOFUSSHClient._tofu_lock` is dead code — must become `threading.Lock` to avoid deadlock
- `export_public_key()` may include a comment field — strip to two parts (algorithm + base64) before writing `known_hosts`
- `resolve_ssh_credentials` fallthrough change will break tests relying on `mcp_admin` fallthrough — audit `git grep "mcp_admin" tests/` before Phase 22 implementation
- `session_manager` singleton in `shell_session.py` is created at import time — do not add `asyncio.create_task()` calls at module level or in `__init__`
- `start_interactive_shell` stdio detection: check `MCP_HTTP_PORT` env var or server-level flag before returning URL
- Wave-0 TDD pattern: RED tests committed before implementation (established in v1.1, used in all v1.2/v1.3 phases)
- Module-level imports in `ssh_tools.py` required for monkeypatching — do not switch to function-body imports
- [Phase 21-core-ssh-reliability]: Use threading.Lock not asyncio.Lock — validate_host_public_key is a synchronous callback, asyncio.Lock is dead code there
- [Phase 21-core-ssh-reliability]: Strip known_hosts comment by splitting export_public_key output and joining only parts[:2] — known_hosts format requires exactly algorithm + base64
- [Phase 21-02]: asyncio.wait_for(timeout=0.05) for non-blocking PTY reads — TimeoutError logged at DEBUG level to satisfy no-silent-exception project rule
- [Phase 21-02]: term_size=(80, 24) — cols first, rows second — matches asyncssh create_process convention
- [Phase 21-02]: EOF test exercises read_output logic directly to avoid WebSocketDisconnect task-cancellation race condition
- [Phase 22-agent-guidance]: SHELL-04: Check MCP_HTTP_ENABLED env var as canonical stdio guard — matches server.py usage
- [Phase 22-agent-guidance]: list_keyring_credentials reads credential_store.list_credentials (existing function) and is annotated read-only
- [Phase 22-agent-guidance]: CredentialNotFoundError extends RuntimeError — propagates cleanly through ssh_connection_wrapper except Exception catch
- [Phase 22-agent-guidance]: list_keyring_credentials marked read-only in tool_annotations.py — queries keyring state, no side effects
- [Phase 23-workflow-completeness]: connect_to_device prompt lists all 6 onboarding tools/commands in order: setup_mcp_admin, credentials add, register_server, ssh_discover, discover_and_map, verify_mcp_admin
- [Phase 23-workflow-completeness]: Hostname interpolated into each step via f-string so prompt is actionable without further substitution
- [Phase 23-workflow-completeness]: [Phase 23-workflow-completeness]: Desync warning placed inside if matched block after if keyring_password block — fires only on desync, never on normal keyring hit or total miss; non-blocking fallthrough to DB tier
- [Phase 24-keyring-password-handling]: Make username/password optional in setup_remote_mcp_admin and update_mcp_admin_groups (str | None = None) to allow keyring auto-injection while preserving backward compatibility
- [Phase 24-keyring-password-handling]: Add key_path parameter to update_mcp_admin_groups to match full SSHCredentials contract
- [Phase 24-keyring-password-handling]: Do not add ValueError guard after resolve_ssh_credentials in setup/groups — CredentialNotFoundError propagates cleanly through ssh_connection_wrapper
- [Phase 24-keyring-password-handling]: Mock resolve_ssh_credentials in all setup_mcp_admin tests to prevent real keyring/DB access in unit tests
- [Phase 24-keyring-password-handling]: test_no_tool_has_password_required as schema audit guard across all 57 tools — update allowlist if a future tool legitimately needs required password
- [Phase 25]: _sudo_run uses conn.run(input=password+'\n') with sudo -S to pipe password via stdin, preventing shell echo leak
- [Phase 25]: ssh_execute_command keeps direct conn.run(input=...) instead of _sudo_run to preserve JSON error responses
- [Phase 25]: Piped-tee commands restructured to bash -c approach so sudo wraps entire operation without pipe complexity
- [Phase 26]: Remove port from service tool schemas entirely — ServiceInstaller has no port parameter and handlers pass **arguments directly causing TypeError at runtime

### Roadmap Evolution

- Phase 24 added: Keyring-based password handling — fix setup_mcp_admin and audit all tools for passed-password anti-pattern
- Phase 25 added: Sudo password piping — fix setup_mcp_admin sudo timeout when connecting user lacks NOPASSWD
- Phase 26 added: Sync tool schema file to match current tool parameters
- Phase 27 added: Update tests to make sure we are testing all parameters of the tools

### Pending Todos

None.

### Blockers/Concerns

- Phase 21 TOFU key format fix (MEDIUM confidence): verify `export_public_key()` actually includes comment field with a live test before finalizing fix approach
- Phase 22 pre-implementation: run `git grep "resolve_ssh_credentials\|get_credential_by_hostname\|mcp_admin" tests/` to audit tests before changing fallthrough behavior

## Session Continuity

Last session: 2026-03-17T07:25:25.167Z
Stopped at: Completed 26-01-PLAN.md
Resume file: None
