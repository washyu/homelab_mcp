---
phase: quick
plan: 3
subsystem: ci
tags: [ci, windows, pytest, cross-platform]
dependency_graph:
  requires: []
  provides: [windows-cross-platform-ci-passing]
  affects: [.github/workflows/main.yml, pyproject.toml]
tech_stack:
  added: []
  patterns: [norecursedirs-exclusion]
key_files:
  created: []
  modified:
    - .github/workflows/main.yml
    - pyproject.toml
decisions:
  - Use inline `run:` form (no block scalar) in workflow to be shell-agnostic across PowerShell and bash
  - Add belt-and-suspenders norecursedirs alongside existing testpaths to guard against cache traversal
metrics:
  duration: "48s"
  completed: "2026-03-12T20:36:00Z"
  tasks_completed: 2
  files_modified: 2
---

# Quick Task 3: Fix Windows Cross-Platform CI Failures Summary

**One-liner:** Fixed two Windows CI bugs — collapsed PowerShell-incompatible backslash line continuation to a single `run:` line and added `norecursedirs` excluding `setup-uv-cache`/`_temp` to prevent fatal pytest collection errors in the uv cache.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Collapse cross-platform pytest command to single line | 251a7d6 | .github/workflows/main.yml |
| 2 | Add norecursedirs to prevent pytest traversing uv cache | abc79e8 | pyproject.toml |

## Changes Made

### Task 1: .github/workflows/main.yml

The `cross-platform` job's "Run core tests" step used a `run: |` block scalar with a bash backslash `\` continuation. PowerShell treats `\` as a path separator, not a line continuation — this caused `-v` to be interpreted as a separate command producing "The term '-v' is not recognized".

**Fix:** Replaced the multi-line block scalar with a single-line inline `run:` form. No `|` block scalar needed for one command — the inline form is unambiguous across all shells.

### Task 2: pyproject.toml

pytest on Windows runners traversed the uv cache at `D:\a\_temp\setup-uv-cache\...` and tried to collect `win32comext\taskscheduler\test\test_addtask.py`, causing a Windows fatal access violation.

**Fix:** Added `norecursedirs` under `[tool.pytest.ini_options]` with entries for `setup-uv-cache` and `_temp` (matching the Windows runner cache path components), plus conventional exclusions (`.git`, `.venv`, `build`, `dist`, etc.).

## Verification

- `grep -n "run: uv run pytest" .github/workflows/main.yml` confirms single-line form at line 150
- `grep -A5 "norecursedirs" pyproject.toml` confirms `setup-uv-cache` and `_temp` in list
- Local smoke test: `uv run pytest tests/test_config.py tests/test_error_handling.py tests/test_database.py -v --tb=short` → 71 passed, 3 skipped

## Deviations from Plan

None — plan executed exactly as written.
