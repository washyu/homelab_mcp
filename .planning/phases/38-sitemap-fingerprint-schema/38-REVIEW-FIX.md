---
phase: 38-sitemap-fingerprint-schema
fix_applied: 2026-04-26T00:00:00Z
fix_scope: critical_warning
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 38: Code Review Fix Report

## Summary

All four in-scope warnings (WR-01..WR-04) from `38-REVIEW.md` were fixed and
committed atomically. The six Info findings (IN-01..IN-06) were out of scope
for this iteration (`fix_scope = critical_warning`) and were not addressed.
Targeted test suites (`test_database.py`, `test_ssh_tools.py`, `test_tools.py`,
`test_sitemap.py`) pass: 116 passed, 10 skipped (Postgres driver unavailable).
Ruff and mypy were clean on every touched file.

## Fixes Applied

### WR-01: Per-probe non-zero exit-status branches do not enroll in `timed_out_commands`

- **File:** `src/homelab_mcp/ssh_tools.py` (lines 404-450)
- **Commit:** `dd696a9`
- **Applied fix:** Added explicit `elif <result> is not None and <result>.exit_status != 0:`
  branches for the three new fingerprint probes (`uname -s`, `uname -r`,
  `cat /etc/os-release`) that enroll the cmd_name in `timed_out_commands` (de-duped),
  mirroring the pre-existing `dpkg-fingerprint` pattern. Hosts where any of these
  probes fail now correctly carry the `partial: True` marker in the response,
  fixing the Phase 39 drift-detector false-negative window.

### WR-02: `list_keyring_credentials` listed twice in `_READ_ONLY_TOOLS`

- **File:** `src/homelab_mcp/tool_annotations.py` (line 46 removed)
- **Commit:** `f42ed0e`
- **Applied fix:** Deleted the duplicate `"list_keyring_credentials"` entry at
  line 46 (kept the line-37 occurrence in the alphabetical neighborhood of
  `list_registered_servers`). The line-46 entry sat between
  `validate_infrastructure_changes` and the new Phase 38 preview tools and was
  the rebase remnant. No behavior change today; closes a future-divergence
  hazard.

### WR-03: `update_device_fingerprint` mutates `last_seen` on every call

- **File:** `src/homelab_mcp/database.py` (SQLite line 348-351, Postgres line 766-769)
- **Commit:** `f53365c`
- **Applied fix:** Dropped the `last_seen` clause from both the SQLite and
  Postgres UPDATE statements in `update_device_fingerprint`. `updated_at` still
  tracks row mutations; the existing `last_seen` value (set by `store_device`
  on actual discovery contact) is preserved. The tool's `idempotentHint=True`
  annotation is now also strictly true: identical inputs produce deterministic
  state. No tests asserted the old `last_seen` mutation behavior, so no test
  updates were needed.

### WR-04: Postgres `update_device_fingerprint` lost-write race vs. concurrent `store_device`

- **File:** `src/homelab_mcp/database.py` (lines 728-794)
- **Commit:** `9489bfa`
- **Applied fix:** Wrapped the Postgres SELECT + Python merge + UPDATE in an
  explicit transaction with `SELECT ... FOR UPDATE` to row-lock the device
  during the merge window. Added a try/except that rolls back on any error
  (including the missing-hostname `ValueError` path) so we never leave an open
  row lock. The `cursor.execute("BEGIN")` is redundant under
  `autocommit = False` but documents intent. Pitfall 4 SQLite/Postgres parity
  is preserved (merge still happens in Python, not via `jsonb_set`).

## Skipped

None. All in-scope findings were applied successfully on the first attempt.

## Out of Scope

The following Info findings (IN-01..IN-06) were not addressed because
`fix_scope = critical_warning` excludes Info severity:

- **IN-01:** `_run_with_timeout` accesses private `conn._host` attribute
  (`src/homelab_mcp/ssh_tools.py:592`)
- **IN-02:** `_maybe_json_load` silently swallows JSON decode errors
  (`src/homelab_mcp/database.py:942-960`)
- **IN-03:** `merge_fingerprint` is "deep-merge" only one level deep
  (`src/homelab_mcp/database.py:963-983`)
- **IN-04:** `connect_to_device` MCP prompt is undocumented in
  `tool-reference.md` (`docs/tool-reference.md:1632-1652`)
- **IN-05:** `configure_host_fingerprint` prompt body has stylistic
  inconsistency (`src/homelab_mcp/prompt_registry.py:180-215`)
- **IN-06:** Test mocks hardcode `_run_with_timeout` keyword args
  (`tests/test_ssh_tools.py:98,199-204,303,762,836`)

---

_Fixed: 2026-04-26T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
