---
phase: 40-proxmox-vm-lifecycle-polish
plan: 02
subsystem: api
tags: [proxmox, schema, openapi, error-hygiene, credentials-cli]

# Dependency graph
requires:
  - phase: 36-drift-sitemap-foundation
    provides: keyring-only credential resolution surfaced via `homelab-mcp credentials add --type proxmox`
  - phase: 37-drift-output-shape
    provides: D-08 "Drift Detection" INFRA_REQUIREMENTS phrasing template (line 60)
provides:
  - "create_proxmox_vm schema requires `host` (POL-02 D-03)"
  - "Zero PROXMOX_HOST substrings remain in proxmox_tools_schema.py (D-05 sweep)"
  - "INFRA_REQUIREMENTS['Proxmox'] mirrors Drift Detection phrasing — credentials-CLI pointer, no env-var, no register_server pointer"
affects: [40-01-proxmox-host-removal, 40-03-ast-guard, v1.7.1-lifecycle-hooks]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Credentials-CLI pointer in schema descriptions (mirrors Phase 37 D-08 'Drift Detection' phrasing)"
    - "Sibling-entry phrasing template: per-node + cluster-scope hint embedded in error/help text"

key-files:
  created:
    - tests/test_proxmox_tools_schema.py
    - tests/test_openapi_infra_requirements.py
  modified:
    - src/homelab_mcp/tool_schemas/proxmox_tools_schema.py
    - src/homelab_mcp/openapi_app.py

key-decisions:
  - "Sweep scope held to D-05 boundary — only descriptions of the four host-bearing tools were rewritten; `required` lists for the six other tools (manage_proxmox_vm, clone_proxmox_vm, delete_proxmox_vm, get_proxmox_vm_config, create_proxmox_lxc, delete_proxmox_vm_preview) were intentionally NOT touched per CONTEXT D-05 (deferred to v1.7.1 LIFE-* / v1.8 mechanical sweep)."
  - "Schema description text uses backticked CLI fragments to match Phase 37 D-08 line 60 styling and to be copy-pasteable verbatim from agent UIs."
  - "openapi_app.py rewrite drops both PROXMOX_HOST and POST /api/tools/register_server in a single edit — register_server became deprecated in v1.3 with the credentials CLI; keeping it in error text would mislead users."

patterns-established:
  - "Test pattern: combine dict-literal access on the imported schema (PROXMOX_TOOLS, INFRA_REQUIREMENTS) with file-level Path().read_text() scans — catches both runtime mutation and source-text drift."
  - "TDD RED commit explicitly enumerates failing assertion count in commit body; GREEN commit reports passing-test sweep across related modules."

requirements-completed: [POL-02]

# Metrics
duration: 5m
completed: 2026-04-28
---

# Phase 40 Plan 02: Proxmox Schema POL-02 + D-05 Sweep Summary

**`create_proxmox_vm` now declares `host` required; every PROXMOX_HOST mention removed from `proxmox_tools_schema.py` and the OpenAPI Proxmox INFRA_REQUIREMENTS entry, with all rewrites pointing at `homelab-mcp credentials add --type proxmox` and the `--scope cluster:` form.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-28T17:33:11Z
- **Completed:** 2026-04-28T17:37:19Z
- **Tasks:** 2 (each TDD: RED + GREEN commits)
- **Files modified:** 2 source + 2 tests

## Accomplishments

- `PROXMOX_TOOLS["create_proxmox_vm"]["inputSchema"]["required"]` is now `["node", "vmid", "name", "host"]` — closes the POL-02 D-03 schema lie that the Plan-01 runtime ValueError exposed.
- Zero `PROXMOX_HOST` substrings remain in `tool_schemas/proxmox_tools_schema.py` (4 occurrences removed across `list_proxmox_resources` tool description + 3 host-property descriptions).
- 4 host-property descriptions across the file (`create_proxmox_vm`, `list_proxmox_resources`, `get_proxmox_node_status`, `get_proxmox_vm_status`) now reference `homelab-mcp credentials add --type proxmox` and the `--scope cluster:<name>` form.
- `INFRA_REQUIREMENTS["Proxmox"]` (openapi_app.py:59) rewritten to mirror the line-60 "Drift Detection" entry's structure; PROXMOX_HOST and `POST /api/tools/register_server` both gone.
- 14 new revert-proof regression tests (8 schema + 6 openapi) wired in to lock the changes against future regressions.

## Task Commits

Each task was executed TDD (RED → GREEN):

1. **Task 1 RED: failing schema tests** - `6db3188` (test)
2. **Task 1 GREEN: create_proxmox_vm host required + PROXMOX_HOST sweep** - `430d7a6` (feat)
3. **Task 2 RED: failing INFRA_REQUIREMENTS test** - `97768fa` (test)
4. **Task 2 GREEN: rewrite INFRA_REQUIREMENTS['Proxmox']** - `99fca67` (feat)

(Plan-metadata commit pending — captures this SUMMARY.md.)

## Files Created/Modified

- `src/homelab_mcp/tool_schemas/proxmox_tools_schema.py` — `create_proxmox_vm` host required + 4 host-bearing descriptions rewritten + tool-level `list_proxmox_resources` description trimmed
- `src/homelab_mcp/openapi_app.py` — line 59 `INFRA_REQUIREMENTS["Proxmox"]` rewritten to mirror line-60 "Drift Detection" phrasing
- `tests/test_proxmox_tools_schema.py` (new) — 8 assertions covering POL-02 D-03 (`host` required, description content) and D-05 (PROXMOX_HOST-free, credentials-CLI literal count ≥ 4, swept tools' descriptions all reference the CLI)
- `tests/test_openapi_infra_requirements.py` (new) — 6 assertions covering INFRA_REQUIREMENTS Proxmox content + sibling Drift Detection guard + file-level PROXMOX_HOST sweep

## Decisions Made

- **Backticked CLI fragments inside the description triple-quoted Python literal** — chose `\`homelab-mcp credentials add --type proxmox <host> <username>\`` form (markdown backticks inside the description string). This matches how MCP agent UIs render the description in tool-pickers and keeps the literal grep-able for future AST guards (Plan 03 D-06).
- **Did NOT touch the other 6 tools' `required` lists.** CONTEXT D-05 explicitly scopes this plan to `create_proxmox_vm` only — `manage_proxmox_vm`, `clone_proxmox_vm`, `delete_proxmox_vm`, `get_proxmox_vm_config`, `create_proxmox_lxc`, `delete_proxmox_vm_preview` still declare host optional. The runtime ValueError from Plan 01 still fires if these calls omit host (tracked T-40-10 in threat register; deferred to v1.7.1 LIFE-* / v1.8 mechanical sweep).
- **Single backtick-style for `--scope cluster:<name>`** — chose to embed the partial CLI fragment (`... --scope cluster:<name> <token_id>`) so users see exactly what to paste. Not the full repeated CLI invocation, since the per-node form was already shown in the same description.

## Deviations from Plan

None - plan executed exactly as written.

The only adjustment was that the audit grep found PROXMOX_HOST mentions only in the three sites already enumerated by the plan (lines 48, 54, 76) plus the implicit `get_proxmox_vm_status` "(optional)" wording the plan had already called out in Task 1 step 6. No additional sweep targets surfaced. The other 6 tools listed in Task 1 step 7 (manage_proxmox_vm, clone_proxmox_vm, delete_proxmox_vm, get_proxmox_vm_config, create_proxmox_lxc) were checked: their `host` descriptions are already simple `"Proxmox host (optional)"` strings without PROXMOX_HOST mentions, so per the plan's "if it already lacks PROXMOX_HOST and is succinct, leave it" guidance, they were left untouched. The grep gate confirmed zero PROXMOX_HOST matches post-edit.

## Issues Encountered

- **Pre-existing mypy stub gap (jsonschema):** `uv run mypy src/homelab_mcp/openapi_app.py` reports `Library stubs not installed for "jsonschema"` on line 18. Verified pre-existing by stashing my changes and re-running mypy — the error is independent of this plan's edits. Logged as out-of-scope (deferred); not a deviation.

## TDD Gate Compliance

Both tasks followed RED → GREEN strictly:

- **Task 1 RED commit (`6db3188`):** 8 failing assertions pre-implementation; pytest output verified the failures point at the correct unrewritten descriptions before any source edits.
- **Task 1 GREEN commit (`430d7a6`):** 8/8 schema tests pass; broader sweep of `test_tools.py`, `test_proxmox_api.py`, `test_proxmox_resolver.py`, `test_ast_regression.py` is 155/155 green.
- **Task 2 RED commit (`97768fa`):** 5 failing assertions pre-implementation (the 6th — Drift Detection sibling guard — passed because that entry was already correct from Phase 37).
- **Task 2 GREEN commit (`99fca67`):** 6/6 INFRA_REQUIREMENTS tests pass; broader sweep of `test_openapi_app.py`, `test_http_app.py`, `test_ast_regression.py`, `test_drift_detection.py` is 96/96 green.

## Verification Gates Passed

- `uv run python -c "...assert 'host' in PROXMOX_TOOLS['create_proxmox_vm']['inputSchema']['required']"` exits 0.
- `uv run python -c "...assert 'PROXMOX_HOST' not in INFRA_REQUIREMENTS['Proxmox']"` exits 0.
- `grep -c PROXMOX_HOST` on both target files returns 0.
- `grep -c "homelab-mcp credentials add --type proxmox"` on `proxmox_tools_schema.py` returns 4.
- `uv run ruff check` on both files: clean.
- All new + related tests: 169 total passing (8 + 6 new + 155 broader sweep, with 96 overlapping in the openapi/drift sweep).

## Next Phase Readiness

- POL-02 fully closed; ready for Plan 03 (D-06 AST guard locking the PROXMOX_HOST-free invariant in).
- Plan 01's POL-03 runtime hard-removal pairs cleanly: the schema now declares `host` required, the runtime now raises `ValueError` if `host` is None, and Plan 03 will add the AST guard that prevents future PROXMOX_HOST reintroduction in either source file.
- T-40-10 in the threat register is deliberately accepted: the other 6 host-bearing tools still have schema-runtime divergence (their `required` lists omit host; runtime accepts None and Plan 01's ValueError fires). Out of v1.7 scope by design — captured for v1.7.1 LIFE-* or v1.8.

## Self-Check: PASSED

- Created files exist:
  - `src/homelab_mcp/tool_schemas/proxmox_tools_schema.py` (modified) — FOUND
  - `src/homelab_mcp/openapi_app.py` (modified) — FOUND
  - `tests/test_proxmox_tools_schema.py` (new) — FOUND
  - `tests/test_openapi_infra_requirements.py` (new) — FOUND
- Commits exist:
  - `6db3188` (Task 1 RED) — FOUND
  - `430d7a6` (Task 1 GREEN) — FOUND
  - `97768fa` (Task 2 RED) — FOUND
  - `99fca67` (Task 2 GREEN) — FOUND

---
*Phase: 40-proxmox-vm-lifecycle-polish*
*Completed: 2026-04-28*
