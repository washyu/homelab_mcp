---
phase: 43-phase-38-documentation-cleanup
plan: 01
subsystem: documentation
tags: [docstrings, schema-descriptions, dead-code-annotation, phase-38-followup]

requires:
  - phase: 38-sitemap-fingerprint-schema
    provides: merge_fingerprint, update_device_fingerprint(_preview), configure_host_fingerprint prompt
  - phase: 38.1-sitemap-keystore-binding
    provides: _resolve_ssh_credentials_with_binding (dead code with audit banner)
provides:
  - Corrected merge_fingerprint docstring with explicit one-level-overwrite semantics + replacement example
  - Corrected abstract method docstring on database adapter base class
  - Schema descriptions for update_device_fingerprint(_preview) carry one-level-overwrite wording + persist-side updated_at note (WR-03)
  - Prompt body for configure_host_fingerprint warns callers that capability entries are REPLACED entirely
  - Preview handler docstring contrasts read-only preview vs persist-side updated_at mutation (WR-03)
  - Sentinel comment on dead _resolve_ssh_credentials_with_binding for v1.8 grep cleanup
  - WR-02 invariant verified: exactly one list_keyring_credentials in _READ_ONLY_TOOLS
affects: [43-02-PLAN.md (docs/tool-reference.md surface text), v1.8 cleanup pass]

tech-stack:
  added: []
  patterns:
    - "Sentinel comment pattern '# Deprecated: kept for grep audit; remove in vX.Y' for grep-driven dead-code cleanup"
    - "Wording-parity rule across docstring + MCP tool description + MCP prompt body for the same merge contract"

key-files:
  created: []
  modified:
    - src/homelab_mcp/database.py
    - src/homelab_mcp/tool_schemas/network_tools_schema.py
    - src/homelab_mcp/prompt_registry.py
    - src/homelab_mcp/tool_handlers/network_handlers.py
    - src/homelab_mcp/ssh_tools.py

key-decisions:
  - "Annotate dead _resolve_ssh_credentials_with_binding with v1.8 sentinel rather than delete — preserves Phase 38.1-08 plan-acceptance grep audit trail; deletion deferred to v1.8 grep-allowlist sweep where it can be done cleanly"
  - "Do not edit tool_annotations.py — WR-02 invariant already held from REVIEW-FIX commit f42ed0e; runtime + grep gates assert the invariant in this plan"
  - "Use the literal phrase 'one-level overwrite' across all four wording surfaces (Python docstring, abstract method docstring, MCP tool description, prompt body) so grep-based audits find a single canonical phrase"

patterns-established:
  - "Sentinel-comment-for-future-removal: a one-line, grep-stable comment immediately above the def of a function targeted for deletion in a named future milestone, separate from any pre-existing audit banner"
  - "WR-02-style invariant assertion as a verification gate: instead of editing a known-clean file, the plan asserts the invariant holds via grep + runtime import; regression would surface as gate failure in a future re-run"

requirements-completed: [IN-03, WR-03, WR-02, dead-code-cleanup]

duration: ~12min
completed: 2026-05-02
---

# Phase 43 Plan 01: Phase 38 Source-Side Documentation Cleanup Summary

**Corrects misleading "deep-merge" wording for `merge_fingerprint` capabilities semantics across 4 surfaces, documents persist-side `updated_at` mutation in the preview handler, and adds a v1.8 sentinel comment to dead `_resolve_ssh_credentials_with_binding` — all docstring/comment/string edits, zero behavior change.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-02T15:20Z (approx)
- **Completed:** 2026-05-02T15:32:29Z
- **Tasks:** 5 (4 work + 1 verification gate)
- **Files modified:** 5

## Accomplishments

- IN-03 source-side wording corrected: `merge_fingerprint` and abstract method docstrings now explicitly state "one-level overwrite" semantics, with an explicit `capabilities.vulkan` REPLACEMENT example so future readers cannot mistake the contract for recursive deep-merge.
- IN-03 surface-text wording corrected: both fingerprint tool descriptions in `network_tools_schema.py` and step 5 of the `configure_host_fingerprint` prompt body carry the same canonical wording — wording-parity holds across docstring/schema/prompt.
- WR-03 closed at the source: preview handler docstring carries an explicit "Side-effect contract" section contrasting read-only preview (no DB write, no `last_seen`/`updated_at` mutation) vs persist (bumps `updated_at`, preserves `last_seen` per Phase 38 REVIEW-FIX commit f53365c).
- Dead-code annotation: `_resolve_ssh_credentials_with_binding` carries the canonical sentinel `# Deprecated: kept for grep audit; remove in v1.8` directly above the existing 8-line DEAD CODE banner. The function and banner are unchanged — v1.8 cleanup pass can grep-find the deletion target while Phase 38.1-08 plan-acceptance grep still finds the symbol.
- WR-02 invariant verified: exactly one `list_keyring_credentials` entry in `_READ_ONLY_TOOLS` (already clean from REVIEW-FIX commit f42ed0e); no edit to `tool_annotations.py` was needed.

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite merge_fingerprint + abstract method docstrings (IN-03 source side)** - `86c8f51` (docs)
2. **Task 2: Update schema descriptions + prompt body for capabilities semantics (IN-03 surface text)** - `09f8aea` (docs)
3. **Task 3: Document persist-side updated_at mutation in preview handler docstring (WR-03)** - `49fa625` (docs)
4. **Task 4: Add v1.8 sentinel comment to dead _resolve_ssh_credentials_with_binding + assert WR-02 invariant** - `e66e758` (docs)
5. **Task 5: Verification-only gate (no work files modified)** - no commit (gate only)

## Files Created/Modified

- `src/homelab_mcp/database.py` — `merge_fingerprint` docstring (lines ~1249-1271) + abstract `update_device_fingerprint` docstring (lines ~47-56) rewritten with one-level-overwrite semantics
- `src/homelab_mcp/tool_schemas/network_tools_schema.py` — `update_device_fingerprint` and `update_device_fingerprint_preview` description strings rewritten
- `src/homelab_mcp/prompt_registry.py` — `configure_host_fingerprint` prompt body step 5 paragraph rewritten with REPLACE warning + preview-is-read-only note
- `src/homelab_mcp/tool_handlers/network_handlers.py` — `handle_update_device_fingerprint_preview` docstring extended with WR-03 Side-effect contract section
- `src/homelab_mcp/ssh_tools.py` — single sentinel comment line added above existing DEAD CODE banner

LOC delta: 5 files changed, 44 insertions, 12 deletions — entirely docstring/comment/description-string. Zero statement-level diff (visual confirmation; the regex gate surfaced only multi-line docstring continuation lines, all inside `"""..."""` blocks or parenthesized string concatenations).

## Decisions Made

- **Annotate, don't delete `_resolve_ssh_credentials_with_binding`** — the existing Phase 38.1-08 plan-acceptance grep relies on the symbol being present. Adding the sentinel comment now lets v1.8 do the deletion alongside a grep-allowlist edit in a single coordinated change. Documented in PLAN.md objective as the explicit decision; carried forward verbatim.
- **No edit to `tool_annotations.py`** — REVIEW-FIX commit f42ed0e already deleted the duplicate `list_keyring_credentials` entry. This plan asserts the invariant holds via runtime + grep gates rather than touching the file. If a future regression reintroduces the duplicate, this plan's gate (the in-Python `assert _READ_ONLY_TOOLS.count('list_keyring_credentials') == 1`) would catch it on re-run.
- **Wording parity across 4 surfaces** — chose "one-level overwrite" as the single canonical phrase. Used verbatim in `merge_fingerprint` docstring, abstract method cross-reference, both schema descriptions, and the prompt body. Future grep audits for capability-merge wording have one phrase to search.

## Deviations from Plan

None — plan executed exactly as written. All 5 tasks ran in order; all acceptance criteria + verify gates passed on first run; no Rule 1-4 deviations triggered.

## Issues Encountered

None. The verify gate's strict regex (`grep -vE "^[+-]\s*(#|\"\"\"|\"|')"`) surfaced multi-line docstring continuation lines as expected — these are docstring prose inside `"""..."""` blocks (the regex only matches the opening line). Manually confirmed every surfaced line is inside a docstring or parenthesized string; no statement-level diff exists.

## No-behavior-change Gate Results

- `uv run pytest -m "not integration" -q`: **936 passed, 15 skipped, 25 deselected, 1 warning in 16.38s** — well above the ≥907 threshold from Phase 42 close.
- `uv run ruff check <6 touched files>`: **All checks passed!**
- `uv run mypy <6 touched files>`: **Success: no issues found in 6 source files**
- `git diff HEAD~4 HEAD --shortstat -- src/`: 5 files changed, 44 insertions(+), 12 deletions(-) — all docstring/comment/string

## Cross-link to Plan 02

Plan 02 closes IN-04 + the `docs/tool-reference.md` surface-text portion of IN-03/WR-03. The wording established in this plan (`merge_fingerprint` docstring) is the canonical reference Plan 02's docs edits should mirror.

## Next Phase Readiness

- Phase 43 source-side cleanup complete; ready for Plan 02 (docs/tool-reference.md surface text).
- v1.8 cleanup pass has a grep-stable sentinel (`# Deprecated: kept for grep audit; remove in v1.8`) for the dead helper deletion target.
- No blockers or open concerns.

## Self-Check: PASSED

**Files (modified):**
- src/homelab_mcp/database.py — FOUND
- src/homelab_mcp/tool_schemas/network_tools_schema.py — FOUND
- src/homelab_mcp/prompt_registry.py — FOUND
- src/homelab_mcp/tool_handlers/network_handlers.py — FOUND
- src/homelab_mcp/ssh_tools.py — FOUND

**Commits:**
- 86c8f51 (Task 1: database.py docstrings) — FOUND
- 09f8aea (Task 2: schema + prompt body) — FOUND
- 49fa625 (Task 3: preview handler docstring) — FOUND
- e66e758 (Task 4: v1.8 sentinel + WR-02 assertion) — FOUND

---
*Phase: 43-phase-38-documentation-cleanup*
*Plan: 01*
*Completed: 2026-05-02*
