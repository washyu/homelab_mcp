---
phase: 22-agent-guidance
plan: "02"
subsystem: agent-guidance
tags: [mcp, ssh, credentials, keyring, interactive-shell, tool-descriptions]

# Dependency graph
requires: []
provides:
  - stdio guard in handle_start_interactive_shell returning actionable error
  - start_interactive_shell schema description mentions --http flag requirement
  - ssh_discover and ssh_execute_command descriptions include credential recovery guidance
  - list_keyring_credentials tool for viewing stored keyring credentials
affects: [agent-guidance, ssh-tools, credential-tools]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "stdio guard pattern: check MCP_HTTP_ENABLED before proceeding with HTTP-only operations"
    - "agent guidance pattern: tool descriptions include recovery steps for common failure modes"

key-files:
  created: []
  modified:
    - src/homelab_mcp/tool_handlers/ssh_handlers.py
    - src/homelab_mcp/tool_schemas/ssh_tools_schema.py
    - src/homelab_mcp/tool_handlers/credential_handlers.py
    - src/homelab_mcp/tool_schemas/credential_tools_schema.py
    - src/homelab_mcp/tool_handlers/__init__.py
    - src/homelab_mcp/tool_annotations.py
    - tests/test_shell_session.py
    - tests/test_tools.py

key-decisions:
  - "SHELL-04: Check os.getenv('MCP_HTTP_ENABLED', 'false').lower() != 'true' as the canonical stdio guard — matches server.py's existing usage"
  - "list_keyring_credentials reads credential_store.list_credentials() (existing function) — no new storage mechanism needed"
  - "list_keyring_credentials annotated as read-only (readOnlyHint=True) — it only queries, never modifies"
  - "Linter-driven additions accepted: list_keyring_credentials schema, handler, and registry wiring added by pre-commit hooks were correct implementations needed to make the tool work"

patterns-established:
  - "stdio guard pattern: HTTP-only tools check MCP_HTTP_ENABLED before proceeding"
  - "credential recovery pattern: SSH tool descriptions reference list_keyring_credentials for self-diagnosis"

requirements-completed: [CRED-03, SHELL-04, SHELL-05]

# Metrics
duration: 6min
completed: 2026-03-15
---

# Phase 22 Plan 02: Agent Guidance — Credential Recovery and stdio Guard Summary

**stdio mode guard for interactive shell returning `stdio_mode_unsupported` error, credential recovery guidance in SSH tool descriptions, and `list_keyring_credentials` tool backed by existing credential_store registry**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-03-15T18:19:07Z
- **Completed:** 2026-03-15T18:25:01Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- SHELL-04: `handle_start_interactive_shell` returns `stdio_mode_unsupported` error with `--http` restart instructions when MCP_HTTP_ENABLED is not "true"
- SHELL-05: `start_interactive_shell` schema description now states the `--http` flag requirement and stdio fallback behavior
- CRED-03: `ssh_discover` and `ssh_execute_command` descriptions now guide agents to call `list_keyring_credentials` or run `credentials add` when auth fails
- `list_keyring_credentials` tool implemented, wired, and annotated (read-only) to enable agent self-diagnosis of stored credentials

## Task Commits

Each task was committed atomically:

1. **TDD RED: stdio guard and schema tests** - `77fea60` (test)
2. **SHELL-04 + SHELL-05 implementation** - `b8e291e` (feat)
3. **CRED-03 + list_keyring_credentials tool** - `e0e1a9d` (feat)
4. **list_keyring_credentials read-only annotation** - `2a57f98` (feat)

**Plan metadata:** (docs commit — see final_commit below)

_Note: TDD task had separate RED test commit before GREEN implementation._

## Files Created/Modified
- `src/homelab_mcp/tool_handlers/ssh_handlers.py` - stdio guard added before session creation
- `src/homelab_mcp/tool_schemas/ssh_tools_schema.py` - descriptions updated for ssh_discover, ssh_execute_command, start_interactive_shell
- `src/homelab_mcp/tool_handlers/credential_handlers.py` - handle_list_keyring_credentials added
- `src/homelab_mcp/tool_schemas/credential_tools_schema.py` - list_keyring_credentials schema added
- `src/homelab_mcp/tool_handlers/__init__.py` - list_keyring_credentials wired into TOOL_HANDLERS
- `src/homelab_mcp/tool_annotations.py` - list_keyring_credentials added to _READ_ONLY_TOOLS (57 tools total)
- `tests/test_shell_session.py` - TestStdioModeGuard class with 3 tests
- `tests/test_tools.py` - schema description assertions + list_keyring_credentials tests

## Decisions Made
- `MCP_HTTP_ENABLED` env var is the canonical stdio/HTTP mode signal (matches server.py line 604 usage)
- `list_keyring_credentials` reads from `credential_store.list_credentials()` which already existed — no new storage mechanism needed
- Tool annotated as read-only since it only reads the credential registry JSON file
- Response format: `{status, credential_type, count, credentials: [{hostname, username}]}` — password fields deliberately excluded for security

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Implemented list_keyring_credentials tool**
- **Found during:** Task 2 (CRED-03 credential recovery guidance)
- **Issue:** Tool descriptions we wrote tell agents to "call `list_keyring_credentials`" but the tool didn't exist. Pointing agents at a non-existent tool would be misleading and break the self-diagnosis flow.
- **Fix:** Implemented `handle_list_keyring_credentials` in credential_handlers.py, added schema to credential_tools_schema.py, wired into TOOL_HANDLERS, annotated as read-only in tool_annotations.py
- **Files modified:** credential_handlers.py, credential_tools_schema.py, tool_handlers/__init__.py, tool_annotations.py
- **Verification:** All 654 non-integration tests pass including new list_keyring_credentials tests added by linter
- **Committed in:** e0e1a9d, 2a57f98

---

**Total deviations:** 1 auto-fixed (Rule 2 - missing critical functionality)
**Impact on plan:** Essential for correctness — the descriptions we wrote actively referenced the tool. No scope creep beyond making referenced functionality exist.

## Issues Encountered
- Pre-commit linter updated tool count in test_get_available_tools from 56 to 57 before the tool existed — caused a brief test failure. Fixed by completing the list_keyring_credentials implementation.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All three requirements (CRED-03, SHELL-04, SHELL-05) satisfied
- Agent guidance phase 22 plan 02 complete
- Phase 23 can proceed with any remaining planned work

---
*Phase: 22-agent-guidance*
*Completed: 2026-03-15*
