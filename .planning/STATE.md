---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Safety & Observability
status: planning
stopped_at: "Completed 11-05-PLAN.md: MCP server wiring for drift detection"
last_updated: "2026-03-12T18:57:53.796Z"
last_activity: 2026-03-11 — v1.1 roadmap created, 22/22 requirements mapped
progress:
  total_phases: 6
  completed_phases: 6
  total_plans: 16
  completed_plans: 16
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
- [Phase 08-02]: dry-run handlers return build_dry_run_response() directly (not content-wrapped); tests assert result.get('mode') == 'dry_run' on raw handler return value
- [Phase 08-03]: dry-run handlers return raw build_dry_run_response() dict directly (not content-wrapped); filter dry_run key from args before passing to remove_server(); get_database_adapter() not DatabaseManager
- [Phase 08-04]: pre-commit mirrors-mypy upgraded v1.13.0 to v1.18.1 with asyncssh/aiohttp stubs to resolve mypy version conflict; dry-run handlers return raw dict; test stubs need get_proxmox_vm_status and plan_terraform_service AsyncMock setup
- [Phase 09-01]: Module-level import of get_resource_manager used (not local/deferred) because server.py does not import resource_readers — no circular import exists and tests can patch at module level
- [Phase 09-02]: Deferred/local import of get_resource_manager inside reader functions to break circular import; test_resource_readers.py patches updated to homelab_mcp.server.get_resource_manager
- [Phase 09-02]: HOMELAB_RESOURCES stub keys removed; handle_read_resource now dispatches to live readers; homelab://services/{name} supported as template URI
- [Phase 10-01]: MUTATING_TOOLS frozenset for immutable O(1) membership check before notification dispatch
- [Phase 10-01]: Test mock uses src.homelab_mcp.server patch path and PropertyMock on type(server) for request_context
- [Phase 10-01]: LookupError from request_context swallowed silently at DEBUG level for out-of-lifecycle callers
- [Phase 11-drift-detection]: Module-level import in test_drift_detection.py causes ImportError at collection time — valid RED state for Wave-0 TDD scaffolding
- [Phase 11-drift-detection]: TestDriftBaselines uses real in-memory SQLite with init_schema() so tests go GREEN automatically once schema migration runs
- [Phase 11-drift-detection]: test_ssh_probe_unreachable patches homelab_mcp.drift_detection.asyncssh.connect and get_proxmox_vm_status to isolate SSH probe failure path
- [Phase 11-drift-detection]: drift_baselines table added to init_schema() (not just migration.py) because TestDriftBaselines fixture uses :memory: SQLite via init_schema()
- [Phase 11-drift-detection]: PostgreSQLAdapter drift baseline stubs raise NotImplementedError — explicit failure is better than silent no-op for Phase 11 SQLite-only scope
- [Phase 11-drift-detection]: UNIQUE(node, vmid, vm_type) + INSERT OR REPLACE keeps upsert logic entirely in SQL with no application-level conflict handling
- [Phase 11-drift-detection]: [Phase 11-03]: get_proxmox_vm_config follows get_proxmox_vm_status pattern exactly — same signature, same error handling, only endpoint differs (/config vs /status/current)
- [Phase 11-drift-detection]: Exception handling around proxmox API calls in scan_drift: get_proxmox_client raises ValueError before try block when PROXMOX_HOST missing; scan_drift wraps calls to gracefully degrade
- [Phase 11-drift-detection]: asyncssh.connect() called directly in drift_detection.py (not ssh_connect wrapper) so test can patch at homelab_mcp.drift_detection.asyncssh.connect
- [Phase 11-drift-detection]: Local inline import of update_baseline_after_mutation in handlers to avoid circular import risk; try/except swallows baseline errors so handler always returns result

### Pending Todos

None.

### Blockers/Concerns

- [Phase 7 research flag]: Verify `@server.subscribe_resource()` decorator and `send_resource_updated` method availability in installed mcp 1.9.4 before planning Phase 7
- [Phase 11 research flag]: SQLite schema for drift baselines needs explicit design before coding — read database.py and migration.py at phase start

## Session Continuity

Last session: 2026-03-12T18:57:53.794Z
Stopped at: Completed 11-05-PLAN.md: MCP server wiring for drift detection
Resume file: None
