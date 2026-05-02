---
phase: 43-phase-38-documentation-cleanup
plan: 02
subsystem: documentation
tags: [tool-reference, mcp-prompts, schema-wording-parity, phase-38-followup]

requires:
  - phase: 43-phase-38-documentation-cleanup
    plan: 01
    provides: |
      Plan 01 rewrote the source-side wording for merge_fingerprint /
      update_device_fingerprint(_preview) schema descriptions and prompt
      body — Plan 02 mirrors that wording into docs/tool-reference.md.
provides:
  - 4 new MCP prompt entries in docs/tool-reference.md (connect_to_device,
    decommission_device_workflow, deploy_service_workflow, homelab_health_check)
    matching the registered HOMELAB_PROMPTS dict
  - update_device_fingerprint tool entry now uses Plan 01's "one level deep ...
    REPLACE" wording (IN-03 docs surface)
  - update_device_fingerprint tool entry carries WR-03 persist-side note
    ("bumps `updated_at`; `last_seen` is preserved")
  - update_device_fingerprint_preview tool entry contrasts read-only/no-mutation
    behavior with the persist tool (WR-03 docs surface)
affects: [Phase 43 close — IN-03/WR-03/IN-04 all closed across source + docs surfaces]

tech-stack:
  added: []
  patterns:
    - "Wording-parity rule across docstring + MCP tool description + MCP prompt body
       + docs/tool-reference.md prose (the same canonical 'one level deep' phrase
       now lives on all 5 surfaces — Plan 01 covered 4, Plan 02 closes the 5th)"
    - "MCP Prompts docs section structure: heading, description prose with numbered
       step list, argument table, related-tools cross-link, --- separator"

key-files:
  created: []
  modified:
    - docs/tool-reference.md

key-decisions:
  - "Use --- horizontal rules at column 0 (NOT space-prefixed) between prompt entries —
    PLAN.md required the leading-space hack to escape its own YAML frontmatter parser,
    but the actual docs file uses standard markdown horizontal rules"
  - "Insert all 4 new prompt entries ABOVE the existing configure_host_fingerprint heading
    so configure_host_fingerprint stays as the 5th and final entry — preserves the
    Phase 38 entry's location as the chronological-newest, even though alphabetically
    it would land mid-section"

patterns-established:
  - "Docs-only plans skip pytest as a behavior gate (only sanity-confirms green) —
    the verifier in Plan 02 ran pytest as a sanity check (936 passed, matches Plan 01
    baseline) but did not assert any new behavior"

requirements-completed: [IN-04]

duration: ~2.5 min
completed: 2026-05-02
---

# Phase 43 Plan 02: Phase 38 Tool-Reference Documentation Cleanup Summary

**Adds 4 missing MCP prompt entries to `docs/tool-reference.md` (closes IN-04) and mirrors Plan 01's source-side wording rewrite (one-level-overwrite + WR-03 persist-side note) into the `update_device_fingerprint(_preview)` tool entries — pure docs prose changes, zero source diff.**

## Performance

- **Duration:** ~2.5 min
- **Started:** 2026-05-02T15:36:23Z
- **Completed:** 2026-05-02T15:38:52Z
- **Tasks:** 3 (2 work + 1 verification gate)
- **Files modified:** 1

## Accomplishments

- **IN-04 closed:** All 5 registered MCP prompts now documented in `docs/tool-reference.md` MCP Prompts section in the planned order: `connect_to_device` → `decommission_device_workflow` → `deploy_service_workflow` → `homelab_health_check` → `configure_host_fingerprint`. Each entry carries the verbatim `HOMELAB_PROMPTS[name].description` text, an argument table matching the `PromptArgument` schema, a numbered workflow step list paraphrased from the matching `_build_*_result` builder, and a related-tools cross-link.
- **IN-03 docs surface closed:** `update_device_fingerprint` tool entry replaced its old `capabilities sub-dict deep-merges (incoming sub-keys overwrite, missing sub-keys preserve)` wording with the canonical Plan-01 phrasing: `capabilities sub-dict updates one level deep — incoming top-level capability keys REPLACE the stored entry entirely (NOT a recursive merge), so callers updating any field within a capability must pass the full capability dict`. Wording-parity now holds across all 5 surfaces (Python docstring, abstract method docstring, both schema descriptions, and the docs prose).
- **WR-03 docs surface closed:** `update_device_fingerprint` tool entry now ends with `Persists to DB and bumps updated_at; last_seen is preserved (Phase 38 REVIEW-FIX WR-03)`. `update_device_fingerprint_preview` tool entry rewritten to explicitly contrast: `Read-only — no DB write, no last_seen or updated_at mutation`. The preview-vs-persist contract is now explicit on both surfaces.
- **`update_device_fingerprint_preview` entry FOUND and updated.** Plan PLAN.md instructed to check whether the heading exists; it was found at line 394. Description rewritten per Task 2 Edit 2.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add 4 missing MCP prompt entries (IN-04)** — `ff272d6` (docs)
2. **Task 2: Sync update_device_fingerprint(_preview) wording with Plan 01 schema (IN-03 + WR-03 docs surface)** — `b0118f9` (docs)
3. **Task 3: Verification-only phase gate (no work files modified)** — no commit (gate only)

## Files Created/Modified

- `docs/tool-reference.md` — `+81 −2` lines: 4 new MCP prompt sub-sections inserted above existing `### configure_host_fingerprint` heading; `update_device_fingerprint` description prose replaced (1 line); `update_device_fingerprint_preview` description prose replaced (1 line).

## Decisions Made

- **Insert above `configure_host_fingerprint`, not alphabetically.** Plan PLAN.md specified order: `connect_to_device → decommission_device_workflow → deploy_service_workflow → homelab_health_check → configure_host_fingerprint`. Followed verbatim — preserves chronological position of the Phase 38 entry as the newest.
- **`---` horizontal rules at column 0.** PLAN.md noted that ` ---` (leading space) was a YAML-escape hack inside the plan file itself; the actual docs file uses standard column-0 horizontal rules. Confirmed the section renders cleanly with all 5 entries separator-divided.
- **No new content for `connect_to_device`/etc. beyond plan spec.** All 4 step-list paragraphs paraphrased from the matching `_build_*_result` builder narratives in `prompt_registry.py:99-236`. No invented workflow steps.

## Deviations from Plan

None — plan executed exactly as written. All 3 tasks ran in order; all acceptance criteria + verify gates passed; no Rule 1-4 deviations triggered.

**Note on Task 1 acceptance gate quirk:** The plan's `grep -A1 "^### <prompt>$" ... | grep -c "<verbatim phrase>"` pre-flight check returned 0 for `connect_to_device` because `-A1` only captures the heading + 1 line (which is the blank line, not the description). Re-ran with `-A2` (heading + blank + description) — all 4 wording probes returned `1` as expected. The actual docs file is correct; only the plan's verification snippet was off-by-one. Not classified as a deviation since no edit was needed.

**Note on Task 2 acceptance gate quirk:** The combined `set -e` bash one-liner exited non-zero because `grep -c` on the deleted `'capabilities sub-dict deep-merges'` phrase returns exit-code `1` when count is `0` — which is exactly the desired outcome (the wording was successfully removed). Re-ran the three sub-checks with explicit `if/then` and all 3 passed (`deep=0`, `new=1`, `persist=1`). Not classified as a deviation since the docs are correct; only the verify shell snippet had the `set -e` × `grep -c 0` interaction.

## Issues Encountered

None.

## No-behavior-change Gate Results

- `uv run pytest -m "not integration" -q`: **936 passed, 15 skipped, 25 deselected, 1 warning in 17.32s** — exactly matches Plan 01's baseline (936); well above the ≥907 threshold from Phase 42 close. Pure docs change; expected zero behavior delta.
- `git diff --stat` between Plan 01 merge point (`71ba632`) and Plan 02 HEAD (`b0118f9`): `docs/tool-reference.md | 83 ++++++++++++++++++++++++++++++++++++++++++++++++--` — 1 file, +81/-2 lines. Exclusively docs prose. Source dir untouched in Plan 02 (Plan 01 already covered the 5 source files).
- `grep -c "^### " docs/tool-reference.md`: **57** (was 53 pre-Plan-02; +4 new prompt sub-sections). Matches plan invariant.
- Visual scan of `docs/tool-reference.md` lines 1632-1731: 5 prompt entries render cleanly, ordered as planned, separator-divided, no orphaned `---` rules, no missing blank lines.

## Cross-link to Plan 01

Plan 01 (`43-01-SUMMARY.md`) closed the source-side half of IN-03 + WR-03 across 5 files (`database.py`, `network_tools_schema.py`, `prompt_registry.py`, `network_handlers.py`, `ssh_tools.py`) plus the v1.8 sentinel comment + WR-02 invariant assertion. Plan 02 closes the docs surface (IN-04 + the IN-03/WR-03 mirror in `docs/tool-reference.md`).

Combined Plan 01 + Plan 02 commit chain (newest → oldest):
- `b0118f9` Plan 02 Task 2 — IN-03/WR-03 docs surface sync
- `ff272d6` Plan 02 Task 1 — IN-04 4 new MCP prompt entries
- `45d448b` (Plan 01 wave-merge state update — no source files)
- `71ba632` (worktree merge from Plan 01 executor)
- `4e8c294` Plan 01 wave-close metadata commit
- `e66e758` Plan 01 Task 4 — v1.8 sentinel + WR-02 assertion
- `49fa625` Plan 01 Task 3 — preview handler docstring (WR-03 source side)
- (`09f8aea`, `86c8f51` — Plan 01 Tasks 2 + 1 in original chain)

## Phase 43 Close Note

Phase 43 has shipped all 5 success criteria from ROADMAP:
- **IN-03**: `merge_fingerprint` docstring + abstract method docstring + 2 schema descriptions + prompt body + docs/tool-reference.md update_device_fingerprint entry — all carry the canonical "one level deep" / "REPLACE" wording.
- **WR-03**: preview handler docstring (`Side-effect contract` section) + tool description note (`bumps updated_at; last_seen is preserved`) + docs/tool-reference.md preview entry (`Read-only — no DB write, no last_seen or updated_at mutation`) — preview-vs-persist contract is explicit across all 3 surfaces.
- **IN-04**: All 5 registered MCP prompts documented in `docs/tool-reference.md`.
- **WR-02**: Invariant asserted clean by Plan 01 Task 4 gate (no source change needed).
- **Dead-code**: `_resolve_ssh_credentials_with_binding` annotated with v1.8 sentinel comment.

Plus the no-behavior-change gate: pytest green (936 passed, matches Plan 01); ruff clean; mypy clean; combined Plan 01 + Plan 02 diff is exclusively docstrings, comments, schema-description strings, the v1.8 sentinel comment, and docs prose — zero functional code change.

**Ready for `/gsd-verify-work 43`.**

## Self-Check: PASSED

**Files (modified):**
- docs/tool-reference.md — FOUND

**Commits:**
- ff272d6 (Task 1: 4 new MCP prompt entries — IN-04) — FOUND
- b0118f9 (Task 2: IN-03/WR-03 docs surface sync) — FOUND

**Acceptance criteria gates:**
- All 5 prompt headings exist exactly once — PASS
- "## MCP Prompts" heading exists exactly once (not duplicated) — PASS
- Old "capabilities sub-dict deep-merges" wording purged — PASS (count=0)
- New "one level deep" wording present — PASS (count=1)
- WR-03 persist-side note "bumps `updated_at`; `last_seen` is preserved" present — PASS (count=1)
- pytest -m "not integration" exit 0 — PASS (936 passed)
- git diff scope: only docs/tool-reference.md modified in Plan 02 — PASS

---
*Phase: 43-phase-38-documentation-cleanup*
*Plan: 02*
*Completed: 2026-05-02*
