---
phase: 26-sync-tool-schema-file-to-match-current-tool-parameters
plan: "03"
subsystem: infra
tags: [proxmox, schema, mcp-tools, vm, lxc]

requires:
  - phase: 26-01
    provides: Removed phantom port property from service tool schemas

provides:
  - create_proxmox_vm schema exposes sockets, cdrom, net0, ostype (all function params now visible to MCP callers)
  - create_proxmox_lxc schema exposes swap, ssh_public_keys, unprivileged (all function params now visible to MCP callers)
  - Proxmox handlers wire all new schema properties to their function calls with matching defaults

affects: [27-update-tests-to-make-sure-we-are-testing-all-parameters-of-the-tools]

tech-stack:
  added: []
  patterns:
    - "Schema-handler parity: every non-session parameter in proxmox_api.py functions must appear in both the schema and the handler call"

key-files:
  created: []
  modified:
    - src/homelab_mcp/tool_schemas/proxmox_tools_schema.py
    - src/homelab_mcp/tool_handlers/proxmox_handlers.py

key-decisions:
  - "Defaults in arguments.get() match proxmox_api.py function signature defaults exactly: sockets=1, net0='virtio,bridge=vmbr0', ostype='l26', swap=512, unprivileged=True"
  - "cdrom and ssh_public_keys use arguments.get() with no default (returns None) matching function signature defaults of None"
  - "required arrays in schemas left unchanged — all new properties have defaults or are optional"

patterns-established:
  - "Schema-handler parity check: when a function gains a new parameter, both the schema and handler must be updated together"

requirements-completed: []

duration: 10min
completed: 2026-03-17
---

# Phase 26 Plan 03: Proxmox Schema Gap Closure Summary

**Exposed 7 hidden create_proxmox_vm/create_proxmox_lxc parameters in their MCP schemas and wired them through the handlers so callers can now configure sockets, cdrom, net0, ostype, swap, ssh_public_keys, and unprivileged**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-03-17T07:30:00Z
- **Completed:** 2026-03-17T07:40:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `create_proxmox_vm` schema now exposes `sockets` (CPU socket count), `cdrom` (alternative ISO attachment), `net0` (network device config), and `ostype` (OS type hint for BIOS optimization)
- `create_proxmox_lxc` schema now exposes `swap` (swap size in MB), `ssh_public_keys` (SSH key injection), and `unprivileged` (security isolation flag)
- Both handlers updated to extract and pass all new properties to their underlying API functions with matching defaults

## Task Commits

Each task was committed atomically:

1. **Task 1: Add missing properties to create_proxmox_vm and create_proxmox_lxc schemas** - `e9d70b9` (feat)
2. **Task 2: Wire new schema properties through Proxmox handlers and run tests** - `014df8e` (feat)

## Files Created/Modified
- `src/homelab_mcp/tool_schemas/proxmox_tools_schema.py` - Added 4 properties to create_proxmox_vm schema, 3 properties to create_proxmox_lxc schema
- `src/homelab_mcp/tool_handlers/proxmox_handlers.py` - Updated handle_create_proxmox_vm and handle_create_proxmox_lxc to pass all new arguments

## Decisions Made
- Defaults in `arguments.get()` in the handlers match the `proxmox_api.py` function signature defaults exactly to preserve backward compatibility
- `required` arrays left unchanged — new properties are optional with sensible defaults

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `uv run` returned exit code 120 in this environment (command-not-found signal from uv); verified using the venv Python directly instead. Tests and lint were run via the venv interpreter and passed.

## Next Phase Readiness
- All 7 previously hidden parameters are now accessible to MCP callers
- Phase 27 (update tests to cover all tool parameters) can now add coverage for the newly exposed properties

---
*Phase: 26-sync-tool-schema-file-to-match-current-tool-parameters*
*Completed: 2026-03-17*
