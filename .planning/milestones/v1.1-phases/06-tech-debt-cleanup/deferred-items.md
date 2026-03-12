---
phase: 06-tech-debt-cleanup
updated: "2026-03-11"
---

# Deferred Items - Phase 06 Tech Debt Cleanup

Pre-existing mypy errors found in files outside the scope of plan 06-03.
These errors existed before any 06-03 changes (confirmed by `git stash` + mypy run).
They are not caused by the current task and should be addressed as separate work items.

## Pre-existing mypy failures (out of scope for 06-03)

Found during 06-03 execution via pre-commit hook:

| File | Line | Error |
|------|------|-------|
| src/homelab_mcp/ssh_tools.py | 788 | Statement is unreachable [unreachable] |
| src/homelab_mcp/proxmox_scripts.py | 41 | Returning Any from function declared to return "str" [no-any-return] |
| src/homelab_mcp/vm_operations.py | 31, 63, 95, 127, 196, 228 | Unused "type: ignore" comment [unused-ignore] |
| src/homelab_mcp/infrastructure_crud.py | 643 | Unused "type: ignore" comment [unused-ignore] |
| src/homelab_mcp/http_app.py | 31 | Unused "type: ignore[attr-defined, no-redef]" comment [unused-ignore] |

Recommendation: Fix these in a dedicated mypy cleanup plan (06-04 or separate debt item).
