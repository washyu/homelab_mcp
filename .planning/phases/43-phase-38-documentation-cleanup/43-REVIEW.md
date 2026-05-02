---
phase: 43-phase-38-documentation-cleanup
reviewed: 2026-05-02T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - src/homelab_mcp/database.py
  - src/homelab_mcp/prompt_registry.py
  - src/homelab_mcp/ssh_tools.py
  - src/homelab_mcp/tool_handlers/network_handlers.py
  - src/homelab_mcp/tool_schemas/network_tools_schema.py
  - docs/tool-reference.md
findings:
  critical: 0
  warning: 1
  info: 3
  total: 4
status: issues_found
---

# Phase 43: Code Review Report

**Reviewed:** 2026-05-02
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Phase 43 is a docs-only cleanup that updates docstrings, comments, MCP tool
description strings, an MCP prompt body, and `docs/tool-reference.md`.

**Docs-only invariant: CONFIRMED.** AST comparison against base
`8fb85d151a480d0d217483a63ed182a3cfcb6cdb` shows:

- `database.py`, `ssh_tools.py`, `network_handlers.py` — AST identical modulo
  docstring nodes (verified by AST walk that drops `ast.Constant`-string
  docstrings and re-dumps).
- `prompt_registry.py`, `network_tools_schema.py` — AST not bit-identical, but
  every diff is a string-literal value change inside an f-string body or a
  schema description string (non-string node-shape lists are equal by length
  and order — 526 nodes for prompt_registry, 114 for the schema). These are
  exactly the documentation surface Phase 43 was scoped to update; the
  surrounding code structure is unchanged.
- `docs/tool-reference.md` — pure markdown.

No statement-level behavior change anywhere in the six files.

The substantive wording updates (capabilities-merge semantics + last_seen
preservation) are accurate against the underlying implementation
(`merge_fingerprint` uses `dict.update()` on the `capabilities` sub-dict, which
DOES replace each incoming top-level capability entry; the SQLite + Postgres
`update_device_fingerprint` paths both omit `last_seen` from the UPDATE).

One real defect: a broken anchor link introduced in the new
`decommission_device_workflow` doc section. Three minor wording / consistency
notes follow.

## Warnings

### WR-01: Broken anchor link to `decommission_device_preview`

**File:** `docs/tool-reference.md:1675`
**Issue:** The newly added `### decommission_device_workflow` section
(introduced by Phase 43 commit `ff272d6`) has a "Related tools" line:

> [`decommission_device_preview`](#decommission_device_preview)

But there is no `### decommission_device_preview` heading anywhere in
`docs/tool-reference.md` (only `### decommission_device` at L493). The tool
exists in code (`src/homelab_mcp/tool_handlers/infrastructure_handlers.py`,
`tool_schemas/infrastructure_tools_schema.py`), and the prompt body itself
references it correctly — but this Markdown anchor will 404 on GitHub /
docsite render. The decommission prompt page tells users to read about
`decommission_device_preview`, then sends them to a missing anchor.

**Fix:** Either (a) add a `### decommission_device_preview` section to the
"Infrastructure Tools" subsection of `tool-reference.md` (preferred — the tool
is undocumented and Phase 43's scope was tool-doc parity), or (b) downgrade the
link to plain code-style (`` `decommission_device_preview` ``) so no anchor
resolution is attempted. Option (a) is consistent with Phase 43's stated goal
of completing the tool-reference; option (b) is the minimum-change fix.

## Info

### IN-01: `connect_to_device` doc step 4 propagates a pre-existing factual error

**File:** `docs/tool-reference.md:1643` (and
`src/homelab_mcp/prompt_registry.py:155-156`)
**Issue:** The new prompt-doc section says step 4 is:

> Call `ssh_discover` to collect hardware and system info into the database.

`ssh_discover` (→ `ssh_discover_system` in `ssh_tools.py`) does NOT write to
the database — it returns JSON. The actual database write happens in step 5
via `discover_and_map` (`discover_and_store` in `sitemap.py`). The prompt body
in `prompt_registry.py` makes the same incorrect claim ("collect hardware and
system info and record it in the database"), so Phase 43 is faithfully
documenting the prompt — but it's also Phase 43's chance to flag the bug.

**Fix:** This is an underlying prompt-body wording issue (NOT a Phase 43
regression — wording predates the base commit). Recommend filing a follow-up to
edit the prompt body itself: change "collect hardware and system info and
record it in the database" → "collect hardware and system info" (and let step
5 own the "add to network sitemap" wording, which it already does). Phase 43
review need not block on this; just don't carry the inaccuracy forward in
future prompt-tweak work.

### IN-02: Inconsistent removal-trigger for the deprecated
`_resolve_ssh_credentials_with_binding`

**File:** `src/homelab_mcp/ssh_tools.py:307` (vs docstring at L325-334)
**Issue:** The new one-line comment says:

```python
# Deprecated: kept for grep audit; remove in v1.8
```

But the function's existing Sphinx-style docstring says:

> "...it will be removed once the plan acceptance grep is updated."

These are two different removal criteria (a milestone version vs an audit-tool
update). A future maintainer reading the docstring will not know whether to
honor the v1.8 deadline or wait for the grep update. Pick one — either align
the docstring to "remove in v1.8 once the grep is updated", or drop the v1.8
date and keep "remove once the grep is updated".

**Fix:** Single-line edit either way. Suggested:

```python
# Deprecated: kept solely for plan-acceptance grep audit. Safe to remove in
# v1.8 once Plan 38.1-08 acceptance grep no longer references this symbol.
```

### IN-03: Slight ambiguity in "REPLACES each top-level capability entry"

**File:** `src/homelab_mcp/prompt_registry.py:210` (also schema description at
`src/homelab_mcp/tool_schemas/network_tools_schema.py:108-110`)
**Issue:** The new sentence reads:

> "the persist call REPLACES each top-level capability entry entirely (not a
> recursive merge)"

A careful reader could parse "each top-level capability entry" as "every
existing capability entry" (i.e., the whole `capabilities` dict is wiped each
call), which is NOT what the merge does — only INCOMING capability keys
replace stored entries; un-mentioned existing keys are preserved (verified at
`database.py:1278` via `existing_caps.update(value)`).

The follow-up sentence ("always pass the full per-capability dict") and the
canonical `merge_fingerprint` docstring both clarify this, so this is a minor
wording sharpening, not a correctness issue.

**Fix:** Optional — tighten to "REPLACES each *incoming* top-level capability
entry entirely". Mirrors the wording used in the `merge_fingerprint` docstring
itself (`database.py:1265-1272`), which is unambiguous.

---

_Reviewed: 2026-05-02_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
