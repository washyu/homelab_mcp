---
plan: 36-06
phase: 36-drift-sitemap-foundation
status: complete
completed: 2026-04-25
---

# Plan 36-06 Summary — Update tool-reference docs for scan_infrastructure_drift

## What was built

Added a new `### scan_infrastructure_drift` entry to `docs/tool-reference.md`, inserted at the end of the "Infrastructure Tools" section (just before "## VM Tools"). The entry:

- Describes scan_drift as iterating the sitemap as the source of truth (sitemap-as-baseline architecture, DRFT-11).
- Shows the full 2-bucket return shape (`probed_ok` / `unreachable`) with the D-02 per-host record (hostname, connection_ip, scope, cluster_name, status, error, scan_timestamp).
- Notes that `node` and `vm_type` filter args are accepted for back-compat but currently inert; Phase 37 (DRFT-13) will activate them.
- Points users to `discover_and_map` for adding hosts to drift coverage (sitemap CRUD = baseline lifecycle per CONTEXT D-17).
- Does NOT mention `PROXMOX_HOST` (the wider docs sweep is Phase 37 / DRFT-15).
- Does NOT reference any speculative `*_drift_baseline` MCP tools (Bug C — none found in any `docs/` file).

## key-files.modified

- `docs/tool-reference.md` (one new section added; no other doc files touched)

## key-files.created

(none)

## Quality gates

- `grep -n "### scan_infrastructure_drift" docs/tool-reference.md` — 1 match (heading exists exactly once).
- `grep -A 30 "### scan_infrastructure_drift" docs/tool-reference.md | grep -i "iterates registered devices in the network sitemap"` — 1 match (sitemap-iteration phrasing present).
- `grep -A 50 "### scan_infrastructure_drift" docs/tool-reference.md | grep -cE "probed_ok|unreachable"` — 4 matches (return shape documented).
- `grep -A 50 "### scan_infrastructure_drift" docs/tool-reference.md | grep -ic "PROXMOX_HOST"` — 0 matches.
- `grep -rn "register_drift_baseline\|list_drift_baselines\|delete_drift_baseline" docs/` — 0 matches.

## Self-Check: PASSED

All acceptance criteria verified by grep. Markdown structure is preserved (table format, code fences closed, separator `---` after the entry).

## Notes / deviations

- The entry was added under Infrastructure Tools (matching the `scan_infrastructure_*` naming convention) rather than under Service Tools where `refresh_terraform_service` lives. Both sections discuss drift detection in different scopes; the choice keeps the tool grouped with sibling discovery/sitemap commands.
- No pre-existing `scan_infrastructure_drift` mentions were found in any other doc file (Bug C was a non-finding across docs/), so no removal sweep was needed beyond the verification greps.
- This plan was executed inline in the orchestrator (sequential fallback) rather than via a subagent — the original Wave 2 subagent dispatch for this plan failed up-front because `EnterWorktree` created the worktree on the wrong base (`b580d30` from a divergent branch) and the sandbox denied `git reset --hard` to correct it. The inline path is the workflow-documented fallback under `<runtime_compatibility>`.
