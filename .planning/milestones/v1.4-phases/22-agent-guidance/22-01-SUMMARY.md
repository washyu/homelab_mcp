---
phase: 22-agent-guidance
plan: "01"
subsystem: credential-resolution
tags: [credentials, error-handling, mcp-tools, tdd]
dependency_graph:
  requires: []
  provides: [CredentialNotFoundError, list_keyring_credentials-tool]
  affects: [ssh_tools.resolve_ssh_credentials, credential_handlers, tool_annotations]
tech_stack:
  added: []
  patterns: [TDD-RED-GREEN, raise-on-miss, read-only-tool-annotation]
key_files:
  created: []
  modified:
    - src/homelab_mcp/ssh_tools.py
    - src/homelab_mcp/tool_schemas/credential_tools_schema.py
    - src/homelab_mcp/tool_handlers/credential_handlers.py
    - src/homelab_mcp/tool_handlers/__init__.py
    - src/homelab_mcp/tool_annotations.py
    - tests/test_ssh_credentials.py
    - tests/test_tools.py
decisions:
  - "CredentialNotFoundError extends RuntimeError — propagates cleanly through ssh_connection_wrapper except Exception catch"
  - "list_keyring_credentials marked read-only in tool_annotations.py — queries keyring state, no side effects"
  - "list_credentials import hoisted to module level in credential_handlers.py to enable standard patch path in tests"
metrics:
  duration_minutes: 5
  completed_date: "2026-03-15"
  tasks_completed: 2
  files_modified: 7
---

# Phase 22 Plan 01: Credential Error Recovery Summary

**One-liner:** CredentialNotFoundError raised with actionable CLI/tool guidance on credential miss; list_keyring_credentials tool added for proactive credential state inspection.

## What Was Built

### CRED-01: CredentialNotFoundError on credential miss

`resolve_ssh_credentials` previously fell through to a silent `return SSHCredentials(hostname, username, port)` when all credential tiers missed — no password, no key, no guidance. This left the agent with an SSH authentication failure and no path forward.

Now it raises `CredentialNotFoundError` (a `RuntimeError` subclass) with a message naming both recovery paths:
- `homelab-mcp credentials add <hostname> <username>` (CLI)
- `register_server` MCP tool

The exception propagates through `ssh_connection_wrapper`'s `except Exception as e` block, which calls `sanitize_error(e)` (simple string redaction — no truncation). The message reaches the agent intact inside the JSON error response.

### CRED-02: list_keyring_credentials MCP tool

New read-only tool that exposes keyring state to the agent. Before calling `ssh_discover` or `ssh_execute_command`, an agent can call `list_keyring_credentials` to see which hosts have stored credentials.

Returns structured JSON: `{status, credential_type, count, credentials: [{hostname, username}]}`. Accepts optional `credential_type` filter ("ssh" or "proxmox").

## Commits

| Hash | Type | Description |
|------|------|-------------|
| ef93009 | test | RED tests for CredentialNotFoundError |
| 2dc3cfc | feat | raise CredentialNotFoundError on credential miss |
| 1ed8314 | test | RED tests for list_keyring_credentials tool |
| f45640f | feat | add list_keyring_credentials MCP tool |
| 2a57f98 | fix | add read-only annotation for list_keyring_credentials |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Annotation] list_keyring_credentials required ToolAnnotations for MCP spec compliance**
- **Found during:** Post-Task 2 full test suite run
- **Issue:** `tests/test_server.py::test_all_tools_have_annotations` failed — every tool in the registry must have a `ToolAnnotations` entry in `tool_annotations.py`
- **Fix:** Added `"list_keyring_credentials"` to `_READ_ONLY_TOOLS` list in `tool_annotations.py`
- **Files modified:** `src/homelab_mcp/tool_annotations.py`
- **Commit:** 2a57f98

## Self-Check: PASSED

- SUMMARY.md created at .planning/phases/22-agent-guidance/22-01-SUMMARY.md
- CredentialNotFoundError present in src/homelab_mcp/ssh_tools.py
- handle_list_keyring_credentials present in credential_handlers.py
- list_keyring_credentials wired in tool_handlers/__init__.py
- All task commits verified: ef93009, 2dc3cfc, 1ed8314, f45640f, 2a57f98
- Full non-integration test suite: 654 passed, 0 failed
