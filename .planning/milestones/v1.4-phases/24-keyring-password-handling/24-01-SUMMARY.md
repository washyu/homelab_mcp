---
phase: 24-keyring-password-handling
plan: 01
subsystem: ssh
tags: [keyring, credentials, ssh, resolve_ssh_credentials, setup_mcp_admin, update_mcp_admin_groups]

# Dependency graph
requires:
  - phase: 22-agent-guidance
    provides: resolve_ssh_credentials function and keyring credential lookup tier
  - phase: 23-workflow-completeness
    provides: connect_to_device onboarding workflow context
provides:
  - setup_mcp_admin accepts optional username/password and resolves from keyring automatically
  - update_mcp_admin_groups accepts optional username/password/key_path and resolves from keyring automatically
  - Both tool schemas require only hostname
affects: [future ssh tool refactoring, agent onboarding workflows]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "resolve_ssh_credentials pattern applied to setup_mcp_admin and update_mcp_admin_groups, matching ssh_discover_system"

key-files:
  created: []
  modified:
    - src/homelab_mcp/tool_schemas/ssh_tools_schema.py
    - src/homelab_mcp/ssh_tools.py

key-decisions:
  - "Make username/password optional in both functions (str | None = None) to allow keyring auto-injection"
  - "Add key_path parameter to update_mcp_admin_groups to match full SSHCredentials contract"
  - "Do not add ValueError guard after resolve_ssh_credentials — CredentialNotFoundError propagates cleanly through ssh_connection_wrapper"

patterns-established:
  - "resolve_ssh_credentials pattern: call before ssh_connect, pass creds.hostname/username/port/password/key_path"

requirements-completed: [SETUP-01, SETUP-02, SETUP-03, GROUPS-01, GROUPS-02]

# Metrics
duration: 1min
completed: 2026-03-15
---

# Phase 24 Plan 01: Keyring-based password handling for setup_mcp_admin and update_mcp_admin_groups Summary

**setup_mcp_admin and update_mcp_admin_groups now auto-resolve SSH credentials from keyring via resolve_ssh_credentials(), matching the pattern established in ssh_discover_system**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-15T19:03:36Z
- **Completed:** 2026-03-15T19:04:42Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Both tool schemas now require only `hostname`; username, password, and key_path are optional with keyring guidance in descriptions
- `setup_remote_mcp_admin` signature changed to `username: str | None = None, password: str | None = None`; credentials resolved via `resolve_ssh_credentials()` before `ssh_connect`
- `update_mcp_admin_groups` signature changed to accept optional username, password, key_path; credentials resolved via `resolve_ssh_credentials()` before `ssh_connect`
- Agents can now bootstrap new hosts with `setup_mcp_admin(hostname="...")` when credentials are stored in keyring

## Task Commits

Each task was committed atomically:

1. **Task 1: Update schemas for setup_mcp_admin and update_mcp_admin_groups** - `be3fed0` (feat)
2. **Task 2: Refactor setup_remote_mcp_admin and update_mcp_admin_groups to use resolve_ssh_credentials** - `e6daaf2` (feat)

## Files Created/Modified
- `src/homelab_mcp/tool_schemas/ssh_tools_schema.py` - Updated required fields to `["hostname"]` for both tools; added keyring guidance to descriptions; added key_path property to update_mcp_admin_groups
- `src/homelab_mcp/ssh_tools.py` - Made username/password optional in both functions; added key_path to update_mcp_admin_groups; added resolve_ssh_credentials() call before ssh_connect in both functions

## Decisions Made
- Make username/password optional (str | None = None) rather than removing them — preserves backward compatibility for callers that pass credentials explicitly
- Add key_path to update_mcp_admin_groups to fully match the SSHCredentials contract and allow key-based auth
- Do not add ValueError guard after resolve_ssh_credentials — CredentialNotFoundError already propagates cleanly through ssh_connection_wrapper

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Both tools now support keyring-based credential lookup for full onboarding workflows
- Agents no longer need to re-enter credentials when keyring is populated via `credentials add`
- No blockers for remaining phase 24 plans

---
*Phase: 24-keyring-password-handling*
*Completed: 2026-03-15*
