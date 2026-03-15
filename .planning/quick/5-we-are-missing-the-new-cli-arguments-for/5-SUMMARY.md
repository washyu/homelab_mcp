---
phase: quick
plan: 5
subsystem: cli
tags: [cli, credentials, argparse, help, discoverability]
dependency_graph:
  requires: []
  provides: [credentials-help-discoverability]
  affects: [src/homelab_mcp/server.py, tests/test_credentials_cli.py]
tech_stack:
  added: []
  patterns: [argparse-epilog, local-import-in-test]
key_files:
  created: []
  modified:
    - src/homelab_mcp/server.py
    - tests/test_credentials_cli.py
decisions:
  - Appended credential examples to existing epilog string rather than replacing it — preserves all existing usage examples
  - Used combined stdout+stderr capture in test to handle argparse printing to either stream
metrics:
  duration: 8
  completed_date: "2026-03-15"
  tasks_completed: 2
  files_modified: 2
---

# Quick Task 5: Add Credentials CLI Arguments to --help Epilog Summary

**One-liner:** Added credential subcommand examples (add/list/remove for ssh and proxmox) to the argparse epilog in main() with a test asserting discoverability.

## What Was Built

The `homelab-mcp` credentials subcommand (add/list/remove) was implemented in Phase 18 but had no presence in the `--help` output, making it invisible to users. This task adds 6 usage examples to the argparse epilog and adds a regression test to ensure they stay visible.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add credentials examples to --help epilog | 0dcddf4 | src/homelab_mcp/server.py |
| 2 | Add test asserting credentials appears in --help output | 97288fe | tests/test_credentials_cli.py |

## Verification

- `uv run pytest tests/test_credentials_cli.py -q` — 13 tests, all PASSED
- `uv run pytest tests/test_packaging.py -q` — 4 tests, all PASSED
- `uv run ruff check src/homelab_mcp/server.py tests/test_credentials_cli.py` — no errors

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- src/homelab_mcp/server.py: epilog updated with credential examples
- tests/test_credentials_cli.py: test_help_output_includes_credentials added
- Commits 0dcddf4 and 97288fe verified in git log
