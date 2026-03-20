---
phase: 26-sync-tool-schema-file-to-match-current-tool-parameters
plan: "01"
subsystem: tool-schemas
tags: [schema, service-tools, bug-fix]
dependency_graph:
  requires: []
  provides: [service-tool-schemas-without-port]
  affects: [service_tools_schema.py]
tech_stack:
  added: []
  patterns: []
key_files:
  created: []
  modified:
    - src/homelab_mcp/tool_schemas/service_tools_schema.py
decisions:
  - "Remove port from service tool schemas entirely — ServiceInstaller has no port parameter and handlers pass **arguments directly"
metrics:
  duration_minutes: 3
  completed_date: "2026-03-17"
  tasks_completed: 2
  files_modified: 1
---

# Phase 26 Plan 01: Sync Tool Schema File to Match Current Tool Parameters Summary

**One-liner:** Removed phantom `port` property from 9 service tool schemas that caused `TypeError: got an unexpected keyword argument 'port'` at runtime.

## What Was Built

Deleted the `port` property block from the `inputSchema.properties` of all 9 service tools that declared it despite the underlying `ServiceInstaller` methods having no `port` parameter. The `**arguments` pass-through in service handlers made this a live TypeError for any MCP client that sent `port`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Remove phantom port property from 9 service tool schemas | dc63e7f | src/homelab_mcp/tool_schemas/service_tools_schema.py |
| 2 | Verify full schema-to-function alignment and run tests | — | (verification only, no file changes) |

## Decisions Made

- **Remove port from service tool schemas entirely:** ServiceInstaller methods (`check_service_requirements`, `install_service`, `get_service_status`, `plan_terraform_service`, `destroy_terraform_service`, `refresh_terraform_service`, `check_ansible_service`, `run_ansible_playbook`) have no `port` parameter. Service handlers use `**arguments` to pass schema properties directly, so any `port` value triggers `TypeError`. Removing from schema is the correct fix — it was never wired up to anything.

## Verification Results

- `grep -c '"port"' src/homelab_mcp/tool_schemas/service_tools_schema.py` returns `0`
- `uv run ruff check src/homelab_mcp/tool_schemas/` exits 0
- `uv run ruff format --check src/homelab_mcp/tool_schemas/` exits 0
- `uv run pytest tests/ -m "not integration" -x -q` — 668 passed, 7 skipped

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- File modified: src/homelab_mcp/tool_schemas/service_tools_schema.py — FOUND
- Commit dc63e7f — FOUND
