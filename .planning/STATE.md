---
gsd_state_version: 1.0
milestone: v1.4
milestone_name: Real-World Reliability
status: planning
stopped_at: Completed 21-core-ssh-reliability 21-01-PLAN.md
last_updated: "2026-03-15T17:54:36.462Z"
last_activity: 2026-03-13 — Roadmap created, phases 21-23 defined
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 2
  completed_plans: 1
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

### Pending Todos

None.

### Blockers/Concerns

- Phase 21 TOFU key format fix (MEDIUM confidence): verify `export_public_key()` actually includes comment field with a live test before finalizing fix approach
- Phase 22 pre-implementation: run `git grep "resolve_ssh_credentials\|get_credential_by_hostname\|mcp_admin" tests/` to audit tests before changing fallthrough behavior

## Session Continuity

Last session: 2026-03-15T17:54:36.460Z
Stopped at: Completed 21-core-ssh-reliability 21-01-PLAN.md
Resume file: None
