---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Safety & Observability
status: planning
stopped_at: "Completed 08-01-PLAN.md: dry_run contract builder and TDD test scaffold"
last_updated: "2026-03-12T01:19:17.573Z"
last_activity: 2026-03-11 — v1.1 roadmap created, 22/22 requirements mapped
progress:
  total_phases: 6
  completed_phases: 2
  total_plans: 8
  completed_plans: 5
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-11)

**Core value:** Every tool in the server actually works -- a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.
**Current focus:** Phase 6 — Tech Debt Cleanup

## Current Position

Phase: 6 of 11 (Tech Debt Cleanup)
Plan: — (not yet planned)
Status: Ready to plan
Last activity: 2026-03-11 — v1.1 roadmap created, 22/22 requirements mapped

Progress: [░░░░░░░░░░] 0%

## Accumulated Context

### Decisions

Full v1.0 decision log in .planning/milestones/v1.0-ROADMAP.md.
Key v1.1 decisions:
- Phase 6 before all features: proxmox_session wiring is a load-bearing prerequisite for Phases 9 and 11
- Phase 8 (Dry-Run) independent of Phase 7 (Resources Plumbing) — can proceed in parallel after Phase 6
- Phase 11 (Drift) last: most complex, needs stable session management and notification infrastructure
- [Phase 06]: _format_error accepts str | Exception for backward compatibility; error_type derived from exception class name; detail uses sanitize_error for credential safety
- [Phase 06]: VM provider list_vms bare exception handlers fixed inline with error_type and detail; test mocks target _run_command not conn.run since _run_command absorbs connection exceptions
- [Phase 06-tech-debt-cleanup]: Local import of get_resource_manager inside each handler function avoids circular import; session param added as last kwarg for backward compatibility
- [Phase 06-02]: Exclude '/' from APIKeyAuth exclude_paths — it uses prefix matching and '/' matches all paths; only use exact paths or paths ending in '/' for real prefix routes
- [Phase 06-02]: APIKeyAuth wrapping is conditional: create_http_app() returns Starlette | APIKeyAuth; callers receive ASGI-compatible object in both cases
- [Phase 07-01]: AnyUrl('homelab://vms') stringifies without triple slash in pydantic v2; RESOURCE_NOT_FOUND=-32002 constant added; subscribe/unsubscribe use set for idempotency
- [Phase 08-dry-run-mode]: build_dry_run_response() returns flat dict with mode, tool, would_affect, risk_level, reversible; preview merged only when preview_details given
- [Phase 08-dry-run-mode]: get_resource_manager patched at homelab_mcp.server (not proxmox_handlers) since it is a local import; remove_server uses MagicMock not AsyncMock (sync function)

### Pending Todos

None.

### Blockers/Concerns

- [Phase 7 research flag]: Verify `@server.subscribe_resource()` decorator and `send_resource_updated` method availability in installed mcp 1.9.4 before planning Phase 7
- [Phase 11 research flag]: SQLite schema for drift baselines needs explicit design before coding — read database.py and migration.py at phase start

## Session Continuity

Last session: 2026-03-12T01:19:17.570Z
Stopped at: Completed 08-01-PLAN.md: dry_run contract builder and TDD test scaffold
Resume file: None
