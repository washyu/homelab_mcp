---
phase: 32-regression-tests
plan: 04
subsystem: testing
tags:
  - testing
  - regression
  - schema
  - credentials
dependency-graph:
  requires:
    - src/homelab_mcp/tools.get_available_tools
    - src/homelab_mcp/tool_schemas/credential_tools_schema.py (list_keyring_credentials)
  provides:
    - tests/test_tools.py::test_sch01_credential_type_rejects_non_enum_values
    - "# --- Regression guards (v1.5 / PR #39) ---" section header
  affects:
    - tests/test_tools.py
tech-stack:
  added: []
  patterns:
    - Plain `def` (synchronous) regression test reading schema dict directly — matches test_sitemap_tool_schemas analog at test_tools.py:285
    - Section header comment `# --- Regression guards (v1.5 / PR #39) ---` marks the regression-guard group at end of file
key-files:
  created: []
  modified:
    - tests/test_tools.py
decisions:
  - "Regression test is synchronous: schema validation happens at JSON Schema level (sync dict inspection); no asyncio needed — same pattern as test_sitemap_tool_schemas"
  - "Exact-equality list assertion `prop[\"enum\"] == [\"ssh\", \"proxmox\"]` (not membership or set-equality) — production schema literal is a list, order is stable and meaningful for MCP clients"
  - "Revert-proof recorded in commit body, not a separate file — keeps SUMMARY lean and pairs the proof with the change that introduced it"
  - "Test name exactly matches plan spec: test_sch01_credential_type_rejects_non_enum_values (CONTEXT.md D-02)"
metrics:
  duration-minutes: 4
  completed: "2026-04-21"
  tasks-completed: 1
  files-modified: 1
requirements:
  - REG-01
---

# Phase 32 Plan 04: SCH-01 Regression Test Summary

One-liner: Added a synchronous `test_sch01_credential_type_rejects_non_enum_values` regression test to `tests/test_tools.py` that asserts `list_keyring_credentials.inputSchema.properties.credential_type` has `type="string"`, `enum=["ssh","proxmox"]`, and `default="ssh"` — guarding commit `bdb76bb` (SCH-01 fix from plan 31-01).

## What Was Built

- **File**: `tests/test_tools.py`
- **New section**: `# --- Regression guards (v1.5 / PR #39) ---` header appended after `test_all_tool_schema_properties_are_valid_dicts`
- **New test**: `test_sch01_credential_type_rejects_non_enum_values` — a plain `def` (no `@pytest.mark.asyncio`) test that:
  1. Calls `get_available_tools()` (already imported at `test_tools.py:8`)
  2. Navigates `tools["list_keyring_credentials"]["inputSchema"]["properties"]["credential_type"]`
  3. Asserts `prop["type"] == "string"`
  4. Asserts `prop["enum"] == ["ssh", "proxmox"]` (exact list equality, order preserved)
  5. Asserts `prop.get("default") == "ssh"`

## Test name + location

- **Name**: `test_sch01_credential_type_rejects_non_enum_values`
- **Location**: `tests/test_tools.py:878` (function definition)

## Revert-Proof Output

Performed locally by deleting the `"enum": ["ssh", "proxmox"],` line from `src/homelab_mcp/tool_schemas/credential_tools_schema.py:130` and re-running the test. Failure output captured:

```
FAILED tests/test_tools.py::test_sch01_credential_type_rejects_non_enum_values - KeyError: 'enum'
============================== 1 failed in 2.16s ==============================
```

The `KeyError: 'enum'` is raised at the assertion `assert prop["enum"] == ["ssh", "proxmox"]` because the schema no longer carries the `enum` key. If the enum key were kept but set to a different value (e.g., `["ssh"]` only), the assertion would instead produce the explicit diagnostic message "credential_type must restrict values to enum ['ssh', 'proxmox']; got enum=['ssh'] — SCH-01 regression would allow arbitrary strings".

Schema file was restored via `git checkout -- src/homelab_mcp/tool_schemas/credential_tools_schema.py`. Test re-run on the restored tree passed (37/37 in `tests/test_tools.py`).

## Acceptance Criteria (from 32-04-PLAN.md)

- [x] `grep -q "def test_sch01_credential_type_rejects_non_enum_values" tests/test_tools.py` exits 0 (1 match)
- [x] `grep -q "list_keyring_credentials" tests/test_tools.py` exits 0
- [x] `grep -q '\["ssh", "proxmox"\]' tests/test_tools.py` exits 0 (4 matches)
- [x] `grep -q "# --- Regression guards (v1.5 / PR #39) ---" tests/test_tools.py` exits 0 (1 match)
- [x] `uv run pytest tests/test_tools.py::test_sch01_credential_type_rejects_non_enum_values -v` exits 0 (1 passed)
- [x] `uv run pytest tests/test_tools.py -v` exits 0 (37 passed)
- [x] `uv run ruff check tests/test_tools.py` exits 0 (All checks passed!)
- [x] `uv run ruff format --check tests/test_tools.py` exits 0 (1 file already formatted)
- [x] Commit body contains revert-proof line (KeyError: 'enum')

## Success Criteria (from 32-04-PLAN.md)

- [x] `test_sch01_credential_type_rejects_non_enum_values` exists in `tests/test_tools.py` with the exact name
- [x] Passes on current HEAD
- [x] Revert-proof documented (commit body + this SUMMARY)
- [x] `# --- Regression guards (v1.5 / PR #39) ---` header present before the new test

## Deviations from Plan

**Ruff format adjustment (auto-applied)**: ruff's formatter collapsed the multi-line
short-form assertion messages on the `list_keyring_credentials must be registered`,
`list_keyring_credentials must expose credential_type`, and `credential_type default
must be 'ssh'` assertions into single lines. The assertion logic, values, and messages
are unchanged — only the source-line wrapping. This is a cosmetic format-driven change,
not a behavior change, and was applied before commit so `ruff format --check` passes.
No content was removed.

Otherwise: plan executed exactly as written.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add SCH-01 regression test (credential_type enum constraint) | `f03e585` | `tests/test_tools.py` |

## Commands Used (Reproducibility)

```bash
# After writing the test
uv run pytest tests/test_tools.py::test_sch01_credential_type_rejects_non_enum_values -v   # PASS
uv run pytest tests/test_tools.py -v                                                       # 37 passed
uv run ruff check tests/test_tools.py                                                      # All checks passed!
uv run ruff format tests/test_tools.py                                                     # 1 file reformatted (collapsed multi-line assertion messages)
uv run ruff format --check tests/test_tools.py                                             # 1 file already formatted

# Revert-proof sequence (manually performed)
# 1. Remove "enum": ["ssh", "proxmox"], from credential_tools_schema.py:130
uv run pytest tests/test_tools.py::test_sch01_credential_type_rejects_non_enum_values -v
# -> FAILED ... - KeyError: 'enum'
# 2. Restore
git checkout -- src/homelab_mcp/tool_schemas/credential_tools_schema.py
uv run pytest tests/test_tools.py::test_sch01_credential_type_rejects_non_enum_values -v   # PASS
```

## Self-Check: PASSED

- Commit `f03e585` exists in git log of this worktree branch (verified via `git rev-parse --short HEAD`).
- File `tests/test_tools.py` contains `def test_sch01_credential_type_rejects_non_enum_values` (1 match) and `# --- Regression guards (v1.5 / PR #39) ---` header (1 match) and `["ssh", "proxmox"]` (4 matches across diff+test).
- Full `tests/test_tools.py` suite passes (37 passed in 2.15s).
- Production schema file unchanged from pre-task state (restored after revert-proof).
