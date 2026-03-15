---
phase: quick-7
plan: "01"
subsystem: ssh-tools
tags: [schema, mcp, credentials, ux]
dependency_graph:
  requires: []
  provides: [ssh-tool-keyring-aware-schemas]
  affects: [ssh_tools_schema.py, ssh_tools.py]
tech_stack:
  added: []
  patterns: [optional-credential-fields, keyring-aware-descriptions]
key_files:
  created: []
  modified:
    - src/homelab_mcp/tool_schemas/ssh_tools_schema.py
    - src/homelab_mcp/ssh_tools.py
decisions:
  - "username removed from required arrays for ssh_discover and ssh_execute_command — credential auto-inject makes it optional"
  - "Error messages now reference `credentials add` instead of register_server to match current credential management flow"
metrics:
  duration: 5
  completed_date: "2026-03-15"
---

# Quick Task 7: Fix SSH Tool Schemas So the Model Knows About Keyring Auto-Inject

**One-liner:** Made username optional and added keyring-aware descriptions in ssh_discover/ssh_execute_command schemas; replaced register_server fallback error messages with credentials add guidance.

## What Was Done

The MCP server already supported auto-injecting SSH credentials from the system keyring (stored via `credentials add`), but the tool schemas still listed `username` as required and described it with mcp_admin setup language. This caused LLM clients to prompt users for credentials even when they were already stored.

Two files were updated with minimal, targeted edits:

1. **ssh_tools_schema.py** — `ssh_discover` and `ssh_execute_command` schemas updated:
   - Top-level descriptions mention keyring auto-inject and tell the model to omit credentials
   - `username` and `password` field descriptions say "Omit if credentials were stored with `credentials add`"
   - `required` arrays: `["hostname", "username"]` -> `["hostname"]` for ssh_discover; `["hostname", "username", "command"]` -> `["hostname", "command"]` for ssh_execute_command

2. **ssh_tools.py** — Two fallback ValueError strings updated:
   - "Register the server first with register_server or provide password/key_path." -> "Store them with `credentials add` or pass password/key_path explicitly."
   - "Register the server first with register_server or provide password." -> "Store them with `credentials add` or pass password explicitly."

## Deviations from Plan

None - plan executed exactly as written. (Ruff auto-collapsed multi-line string in ssh_tools.py on first commit attempt — re-staged and committed cleanly on second attempt.)

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Make username optional + keyring descriptions | 585996a | src/homelab_mcp/tool_schemas/ssh_tools_schema.py |
| 2 | Fix misleading fallback error messages | d261600 | src/homelab_mcp/ssh_tools.py |
| 3 | Verify quality gates pass | (no commit) | ruff + mypy clean |

## Self-Check: PASSED

- FOUND: src/homelab_mcp/tool_schemas/ssh_tools_schema.py
- FOUND: src/homelab_mcp/ssh_tools.py
- FOUND: commit 585996a (task 1)
- FOUND: commit d261600 (task 2)
