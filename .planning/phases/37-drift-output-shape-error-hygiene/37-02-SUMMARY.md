---
phase: 37-drift-output-shape-error-hygiene
plan: "02"
subsystem: drift-surface-text
tags: [drift, schema, docs, text-scrub, drft-15]
requirements: [DRFT-15]

dependency_graph:
  requires: []
  provides:
    - drift_tools_schema.py: Phase 37 stable 4-bucket description, hostname-filter node description, Phase 39-reserved vm_type description
    - server.py: homelab://drift/latest resource description reflecting Phase 37 stable 4-bucket shape
    - openapi_app.py: Drift Detection INFRA_REQUIREMENTS entry pointing to discover_and_map + credentials CLI; PROXMOX_HOST removed
    - drift_handlers.py: handle_scan_infrastructure_drift docstring updated for Phase 37 4-bucket shape
    - docs/tool-reference.md: scan_infrastructure_drift entry rewritten for Phase 37 4-bucket envelope, hostname filter semantics, counts sub-dict, conditional guidance
  affects:
    - MCP client schema introspection (description visible to LLM clients)
    - OpenAPI/REST metadata endpoint consumers
    - Users reading docs/tool-reference.md

tech_stack:
  added: []
  patterns:
    - Description-only text scrub (no behavioral changes)
    - PROXMOX_HOST removal from drift surface (D-08)
    - Phase 39 reservation notes in schema descriptions (D-02)

key_files:
  created: []
  modified:
    - src/homelab_mcp/tool_schemas/drift_tools_schema.py
    - src/homelab_mcp/server.py
    - src/homelab_mcp/openapi_app.py
    - src/homelab_mcp/tool_handlers/drift_handlers.py
    - docs/tool-reference.md

decisions:
  - "openapi_app.py Proxmox entry (line 59) intentionally untouched — Phase 40 POL-03 territory (D-08)"
  - "PROXMOX_HOST references in other Proxmox tool docs entries untouched — out of scope per D-08"
  - "drift_handlers.py body unchanged; only docstring updated"

metrics:
  duration_seconds: 212
  completed_date: "2026-04-25"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 5
---

# Phase 37 Plan 02: Drift Surface Text Scrub Summary

**One-liner:** Removed all PROXMOX_HOST/2-bucket/stored-baselines text from drift surface (schema, server resource, openapi entry, handler docstring, docs) and replaced with Phase 37 stable 4-bucket framing and sitemap CRUD tool recovery pointers.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rewrite drift schema description + node/vm_type property descriptions | 14f5157 | src/homelab_mcp/tool_schemas/drift_tools_schema.py |
| 2 | Update drift surface descriptions in server.py + openapi_app.py + drift_handlers.py docstring | 43cdfc6 | src/homelab_mcp/server.py, src/homelab_mcp/openapi_app.py, src/homelab_mcp/tool_handlers/drift_handlers.py |
| 3 | Rewrite scan_infrastructure_drift entry in docs/tool-reference.md | d32d6a0 | docs/tool-reference.md |

## What Was Done

**Task 1 — drift_tools_schema.py:**
- Top-level `description` fully rewritten: names all four buckets (probed_ok, unreachable, unknown, changed), references counts sub-dict, conditional guidance field, discover_and_map + credentials CLI recovery pointer
- `node` property description: exact-match semantics, no wildcards/case folding, no-match returns success with empty buckets + guidance
- `vm_type` property description: explicit Phase 39 reservation note ("Reserved for Phase 39 per-VM detection; currently no-op")
- `enum` ["qemu", "lxc", "all"] and `default` "all" preserved unchanged (D-03)
- Zero PROXMOX_HOST, "2-bucket", "Phase 37 redesign", "stored baselines", "drift_type" in file

**Task 2 — server.py / openapi_app.py / drift_handlers.py:**
- `server.py` HOMELAB_RESOURCES["homelab://drift/latest"]["description"]: removed "2-bucket interim — shape stabilizes in Phase 37"; replaced with four-bucket description referencing discover_and_map recovery tools
- `openapi_app.py` INFRA_REQUIREMENTS["Drift Detection"] (line 60): removed "stored baselines" + "Set PROXMOX_HOST"; replaced with sitemap populate pointer + credentials CLI
- `openapi_app.py` INFRA_REQUIREMENTS["Proxmox"] (line 59): intentionally untouched — Phase 40 POL-03 territory; verified exactly 1 PROXMOX_HOST remains in file
- `drift_handlers.py` docstring: removed "2-bucket"; added Phase 37 four-bucket envelope description, DRFT-13/DRFT-09 cross-references; body unchanged

**Task 3 — docs/tool-reference.md:**
- `scan_infrastructure_drift` entry fully rewritten (lines 576-633 → expanded)
- Prose description: four-bucket coverage, exact-match hostname filter, conditional guidance, counts sub-dict, Phase 39 reservations
- Arguments table: node with exact-match semantics; vm_type with Phase 39 reservation note
- Two Returns examples: populated scan (probed_ok + unreachable + empty unknown/changed) and empty scan (all buckets empty + guidance field)
- Recovery section: `homelab-mcp credentials add --type proxmox` CLI pointer
- Annotations badge `[Read-Only]` `[Idempotent]` preserved
- Zero PROXMOX_HOST or "stored baselines" in the scan_infrastructure_drift entry

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — this plan is description-only text changes. No data flow, no stubs.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced. All changes are static description text only (T-37-02-01 through T-37-02-07 addressed as specified in plan threat model).

The remaining PROXMOX_HOST references in docs/tool-reference.md (lines 1314, 1322, 1348) are in Proxmox VM lifecycle tool entries, not the drift entry — these are explicitly out of scope per D-08 (Phase 40 / future docs phase).

## Self-Check: PASSED

**Files exist:**
- `src/homelab_mcp/tool_schemas/drift_tools_schema.py` — FOUND
- `src/homelab_mcp/server.py` — FOUND
- `src/homelab_mcp/openapi_app.py` — FOUND
- `src/homelab_mcp/tool_handlers/drift_handlers.py` — FOUND
- `docs/tool-reference.md` — FOUND

**Commits exist:**
- 14f5157 — FOUND (drift schema description rewrite)
- 43cdfc6 — FOUND (server.py + openapi_app.py + drift_handlers.py)
- d32d6a0 — FOUND (docs/tool-reference.md)

**Verification results:**
- `uv run ruff check` on all 4 source files: PASSED
- `uv run mypy` on drift_tools_schema.py: PASSED (no issues)
- Python introspection checks (schema desc, server desc, openapi entries, Proxmox entry untouched): PASSED
- `uv run pytest tests/test_drift_wiring.py -v --no-cov`: 10/10 PASSED
- `grep -c "PROXMOX_HOST" src/homelab_mcp/openapi_app.py`: exactly 1 (Proxmox entry preserved)
- `grep -c "PROXMOX_HOST" src/homelab_mcp/tool_schemas/drift_tools_schema.py src/homelab_mcp/tool_handlers/drift_handlers.py src/homelab_mcp/server.py`: 0/0/0
- Python regex check on docs entry: PASSED
