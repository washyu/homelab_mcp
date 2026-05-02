---
phase: 43-phase-38-documentation-cleanup
fixed_at: 2026-05-02T00:00:00Z
review_path: .planning/phases/43-phase-38-documentation-cleanup/43-REVIEW.md
iteration: 2
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 43: Code Review Fix Report

**Fixed at:** 2026-05-02
**Source review:** `.planning/phases/43-phase-38-documentation-cleanup/43-REVIEW.md`
**Iteration:** 2 (cumulative — supersedes iteration 1)

**Summary:**

- Findings in scope (all severities — `fix_scope=all`): 4
- Fixed: 4 (1 carried over from iteration 1, 3 new this iteration)
- Skipped: 0

Iteration 2 widens scope from `critical_warning` to `all`, picking up the
three Info findings (IN-01, IN-02, IN-03) that iteration 1 deferred. WR-01
remains fixed from iteration 1 (commit `139e082`) and is reported as
`already_fixed` rather than re-applied. After all 3 IN fixes, the unit test
suite was re-run: **936 passed, 15 skipped** — matches the expected baseline,
no regressions.

## Fixed Issues

### WR-01: Broken anchor link to `decommission_device_preview`

**Files modified:** `docs/tool-reference.md`
**Commit:** `139e082` (iteration 1 — already_fixed, not re-applied)
**Applied fix:** Added a new `### decommission_device_preview` subsection to
the **Infrastructure Tools** area of `docs/tool-reference.md`, inserted after
the existing `### decommission_device` section. The new section follows the
same template as `### update_device_fingerprint_preview` and
`### decommission_device`:

- **Description** mirrors the MCP tool description string from
  `tool_schemas/infrastructure_tools_schema.py`.
- **Annotations:** `[Read-Only]` `[Idempotent]`.
- **Arguments table** copies the four properties (`device_id`,
  `migration_plan`, `force_removal`, `validate_only`).
- **Example** JSON validated as parseable.
- **Returns** describes the dry-run report shape.

GitHub anchor generation lowercases the heading and replaces whitespace with
`-`, so `### decommission_device_preview` resolves to
`#decommission_device_preview` — the exact anchor referenced by the
`decommission_device_workflow` "Related tools" line.

**Iteration 2 verification (already_fixed re-check):**
- Confirmed `### decommission_device_preview` heading present at
  `docs/tool-reference.md:525` via Grep.
- Confirmed `[`decommission_device_preview`](#decommission_device_preview)`
  link present at `docs/tool-reference.md:1708` (relocated from L1675 by the
  +33-line insertion, as documented in iteration 1).
- Anchor target lives at L525, link source at L1708 — both resolve.
- No re-edit required; no new commit for WR-01.

---

### IN-01: `connect_to_device` step 4 propagates a pre-existing factual error

**Files modified:** `src/homelab_mcp/prompt_registry.py`,
`docs/tool-reference.md`
**Commit:** `7842f1d`
**Applied fix:** Corrected the misleading "into the database" wording in BOTH
the prompt body (source of truth) and the docs mirror.

In `src/homelab_mcp/prompt_registry.py:155-156` (function
`_build_connect_to_device_result`):

> Before: `Call ssh_discover with hostname="{hostname}" to collect hardware
> and system info and record it in the database.`
> After:  `Call ssh_discover with hostname="{hostname}" to collect hardware
> and system info (read-only — returns JSON; does not write to the database).`

Step 5 (`discover_and_map`) was extended to make explicit that it is the
DB-persisting step:

> Before: `Call discover_and_map with hostname="{hostname}" to add the device
> to the network sitemap.`
> After:  `Call discover_and_map with hostname="{hostname}" to add the device
> to the network sitemap (this is the step that persists discovery data to
> the database).`

In `docs/tool-reference.md:1676-1677` (the `### connect_to_device` prompt
section added by Phase 43, mirror of the prompt body), the same two-step
correction was applied to keep doc-vs-code wording parity.

This corrects a long-standing factual error: `ssh_discover` →
`ssh_discover_system` in `ssh_tools.py` returns JSON; the database write
happens via `discover_and_map` → `discover_and_store` in `sitemap.py`. The
review correctly identified that the bug predates Phase 43 (the prompt body
itself carried the incorrect claim), but Phase 43's tool-doc parity scope
made this a natural place to fix it at the source.

**Verification:**
- Tier 1 (re-read): Confirmed both files reflect the new wording at
  `prompt_registry.py:155-159` and `tool-reference.md:1676-1677`. F-string
  brace escapes in the prompt body remain intact (`{{...}}` for literal
  braces); no formatting damage.
- Tier 2 (syntax): `python -c "import ast; ast.parse(...)"` on
  `prompt_registry.py` → OK.
- Tier 3 (runtime): Pre-commit hooks ran ruff lint, ruff format, mypy, and
  python AST check — all passed.

---

### IN-02: Inconsistent removal-trigger for `_resolve_ssh_credentials_with_binding`

**Files modified:** `src/homelab_mcp/ssh_tools.py`
**Commit:** `02f21b0`
**Applied fix:** Aligned the one-line comment and the docstring on a single
removal criterion that combines both signals (v1.8 milestone + grep audit
update).

At `src/homelab_mcp/ssh_tools.py:307` (the deprecation banner above
`_resolve_ssh_credentials_with_binding`):

> Before: `# Deprecated: kept for grep audit; remove in v1.8`
> After:  `# Deprecated: kept solely for plan-acceptance grep audit. Safe to
>          remove in v1.8 once the Phase 38.1-08 acceptance grep no longer
>          references this symbol.`

At `src/homelab_mcp/ssh_tools.py:333-335` (the corresponding clause in the
function docstring):

> Before: `New code MUST NOT call this; it will be removed once the plan
>          acceptance grep is updated.`
> After:  `New code MUST NOT call this; safe to remove in v1.8 once the
>          Phase 38.1-08 acceptance grep no longer references this symbol.`

Both surfaces now state the same removal criterion: a future maintainer
reading either the inline comment or the rendered Sphinx docstring gets the
same answer. The v1.8 sentinel matches the v1.7→v1.8 cleanup intent
(consistent with the milestone branch naming convention in CLAUDE.md), and
the grep-audit gating remains the operational trigger. Documentation-only;
no behavior change to the (unreachable) function body.

**Verification:**
- Tier 1 (re-read): Confirmed both edits at `ssh_tools.py:307-308` (one-line
  comment) and `ssh_tools.py:334-335` (docstring clause). The surrounding
  DEAD CODE banner (L309-316) is untouched.
- Tier 2 (syntax): `python -c "import ast; ast.parse(...)"` on
  `ssh_tools.py` → OK.
- Tier 3 (runtime): Pre-commit hooks ran ruff lint, ruff format, mypy, and
  python AST check — all passed.

---

### IN-03: Sharpen "REPLACES each top-level capability entry" wording

**Files modified:** `src/homelab_mcp/prompt_registry.py`,
`src/homelab_mcp/tool_schemas/network_tools_schema.py`,
`docs/tool-reference.md`
**Commit:** `ab1a879`
**Applied fix:** Tightened the ambiguous wording in three documentation
surfaces simultaneously, to match the unambiguous canonical phrasing in the
`merge_fingerprint` docstring at `database.py:1265-1272`.

Original ambiguity: "REPLACES each top-level capability entry entirely" can
be misread as "wipes every existing capability entry on each call". The
actual semantic (verified at `database.py:1278` via
`existing_caps.update(value)`): only INCOMING capability keys overwrite their
stored counterparts; existing keys not present in the call are preserved.

Wording-parity update (functionally identical across all three surfaces):

1. **`src/homelab_mcp/prompt_registry.py:210-212`** (the
   `configure_host_fingerprint` prompt body, step 5):
   > New: `Note: the persist call REPLACES each *incoming* top-level
   > capability entry entirely (not a recursive merge); existing capability
   > keys not present in the call are preserved, but every key you DO send
   > overwrites its stored entry, so always pass the full per-capability
   > dict.`

2. **`src/homelab_mcp/tool_schemas/network_tools_schema.py:109-112`** (the
   MCP tool description string for `update_device_fingerprint`):
   > New: `each *incoming* top-level capability key REPLACES its stored
   > entry entirely (NOT a recursive merge); stored capability keys not
   > present in the call are preserved.`

3. **`docs/tool-reference.md:360`** (the mirror of the same MCP tool
   description in the user-facing reference):
   > New: identical wording to (2) above, preserving doc-vs-schema parity.

All three surfaces now unambiguously express the per-key replacement
semantic. Documentation-only; no behavior change.

**Verification:**
- Tier 1 (re-read): Confirmed all three edits at the cited locations.
  F-string brace escapes in the prompt body (`{{"capabilities": {{...}}}}`)
  remain intact; markdown emphasis (`*incoming*`) renders correctly.
- Tier 2 (syntax): `python -c "import ast; ast.parse(...)"` on both
  Python files → OK.
- Tier 3 (runtime): Pre-commit hooks ran ruff lint, ruff format, mypy, and
  python AST check — all passed.
- Tier 4 (full unit suite): `uv run pytest -m "not integration" -q` →
  **936 passed, 15 skipped, 25 deselected, 1 warning in 12.95s**. Matches
  the expected baseline; no regressions.
- Stale-grep check: `grep -rn "REPLACES each top-level capability entry"
  src/ docs/` → only a stale `.pyc` cache hit remains; all live source
  surfaces use the new wording.

**Plan 43-01 acceptance grep note:** The original Phase 43 plan
(`.planning/phases/43-phase-38-documentation-cleanup/43-01-PLAN.md:320`)
included an acceptance grep `grep "REPLACES each top-level capability entry"
src/homelab_mcp/prompt_registry.py` that expected the OLD wording. Since
Phase 43 is already closed (state advanced in commit `c4e1cd6`), this grep
is historical-plan documentation rather than live CI; the new wording still
contains the substring "REPLACES each" and the broader phrase if one were to
re-grep with a relaxed pattern. Flagged here for transparency.

## Skipped Issues

None — all 4 in-scope findings (1 Warning carried over + 3 Info) are
resolved.

---

**Worktree note (iteration 2):** As in iteration 1, `git worktree add`
failed because the target branch `gsd/v1.7-drift-architectural-fix` is
already checked out in the foreground session's main worktree (the only
worktree for that branch). Falling back to operating in the main working
tree was safe for this run because (a) the working tree was clean at start,
(b) all three IN fixes are documentation-only edits, (c) each fix was
committed atomically before the next began, and (d) the foreground session
was idle during the run. This deviation is logged for transparency and is
NOT a regression in the fixes themselves.

---

_Fixed: 2026-05-02_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2 (cumulative)_
