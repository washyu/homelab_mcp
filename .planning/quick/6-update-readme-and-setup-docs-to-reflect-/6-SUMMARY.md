---
phase: quick-6
plan: 6
subsystem: documentation
tags: [docs, readme, setup, credentials, pypi, uvx, v1.3]
dependency_graph:
  requires: []
  provides: [updated-readme, updated-configuration-docs, updated-setup-guide]
  affects: [user-onboarding, credential-management-discoverability]
tech_stack:
  added: []
  patterns: []
key_files:
  created: []
  modified:
    - README.md
    - docs/configuration.md
    - docs/setup-guide.md
decisions:
  - Placed uvx/PyPI install as the recommended option ahead of git clone in both README and setup guide
  - Added credentials CLI section to README with link to full reference in configuration.md
  - Added separate config JSON blocks labeled by install method (uvx vs source clone)
metrics:
  duration_minutes: 5
  completed_date: "2026-03-15"
  tasks_completed: 2
  files_modified: 3
---

# Quick Task 6: Update README and Docs for v1.3 Summary

**One-liner:** Updated README, configuration.md, and setup-guide.md to reflect v1.3 state: Python 3.12+, PyPI/uvx install path, credentials CLI reference, and accurate project structure.

## What Was Done

### Task 1: README.md

- Changed Python badge from `3.10+` to `3.12+`
- Replaced git-clone-only Quick Start with uvx one-liner as recommended option followed by clone as alternative
- Added **Credential Management** section with `credentials add/list/remove` examples and OS keyring explanation
- Added uvx MCP client config block ("From PyPI (uvx) — recommended") alongside existing source-clone block
- Added four missing modules to Project Structure listing: `credential_store.py`, `log_filter.py`, `prompt_registry.py`, `resource_readers.py`
- Updated tool_schemas count from 7 to 8

**Commit:** `8b34c06`

### Task 2: docs/configuration.md and docs/setup-guide.md

**configuration.md:**
- Appended new top-level `## Credentials CLI` section with:
  - Subcommand reference table (add/list/remove with arguments and descriptions)
  - `--type` flag table (ssh vs proxmox)
  - Full examples block covering all six common operations
  - Headless server fallback note

**setup-guide.md:**
- Restructured section 2 "Clone and Install" into "2. Install" with Option A (uvx/PyPI) and Option B (source clone)
- Section 5 Claude Desktop: added uvx config block labeled "Using PyPI (uvx) — recommended" before existing "Using source clone" block
- Section 5 Claude Code: same uvx-first pattern for the `.mcp.json` block

**Commit:** `1357903`

## Deviations from Plan

None — plan executed exactly as written.

## Verification Results

- `grep -c "uvx homelab-mcp" README.md` → 1
- `grep -c "uvx homelab-mcp" docs/setup-guide.md` → 1
- `grep -c "credentials add" README.md` → 2
- `grep -c "credentials add" docs/configuration.md` → 3
- `grep "3.12" README.md` → badge line confirmed

## Self-Check: PASSED

Files modified:
- /home/shaun/projects/mcp_python_server/README.md — FOUND
- /home/shaun/projects/mcp_python_server/docs/configuration.md — FOUND
- /home/shaun/projects/mcp_python_server/docs/setup-guide.md — FOUND

Commits:
- 8b34c06 — FOUND (README.md update)
- 1357903 — FOUND (configuration.md + setup-guide.md update)
