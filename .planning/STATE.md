---
gsd_state_version: 1.0
milestone: v1.5
milestone_name: Security & Correctness Hardening
status: executing
stopped_at: Phase 30 context gathered
last_updated: "2026-04-01T22:07:25.994Z"
last_activity: 2026-04-01 -- Phase 30 execution started
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 2
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-20)

**Core value:** Every tool in the server actually works — a Proxmox homelabber can install this, connect it to any MCP client, and reliably manage their infrastructure through AI.
**Current focus:** Phase 30 — security-fixes

## Current Position

Phase: 30 (security-fixes) — EXECUTING
Plan: 1 of 2
Status: Executing Phase 30
Last activity: 2026-04-01 -- Phase 30 execution started

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 0 (v1.5, starting)
- Average duration: — min
- Total execution time: — hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

*Updated after each plan completion*

## Accumulated Context

### Decisions

Key constraints for v1.5 (from PR review findings):

- SEC-01: Use tmpfile or heredoc for public key delivery — never interpolate key content into remote shell string
- SEC-02: Both existence check and append must execute under `_tofu_lock` — `threading.Lock` (not asyncio) per Phase 21 decision
- SSH-01: Disambiguation error must name conflicting entries — not a silent fallback or silent pick-first
- SSH-02: `timeout` must be forwarded to `ssh_connect()` keyword argument — outer `asyncio.wait_for` alone is insufficient
- SSH-03: `verify_mcp_admin_access()` must call `resolve_ssh_credentials()` and use returned port/creds
- ERR-01: `resolve_ssh_credentials()` call sites must be inside the error-handled section — `CredentialNotFoundError` → JSON payload
- ERR-02: PTY reader EOF/error must close websocket and cancel paired task — no orphaned sessions
- QUAL-01: Use JSON Schema `oneOf` to enforce iso/cdrom exclusivity in proxmox_tools_schema.py
- QUAL-02: EOF test must import and call `handle_shell_websocket` from `http_app` — local copy is invisible to CI

### Pending Todos

None.

### Blockers/Concerns

None identified at roadmap creation time.

## Session Continuity

Last session: 2026-04-01T08:54:26.257Z
Stopped at: Phase 30 context gathered
Resume file: .planning/phases/30-security-fixes/30-CONTEXT.md
