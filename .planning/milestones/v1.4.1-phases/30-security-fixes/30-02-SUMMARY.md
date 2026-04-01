---
phase: 30-security-fixes
plan: "02"
subsystem: ssh-tools
tags: [security, ssh, injection, sftp, tdd]
dependency_graph:
  requires: []
  provides: [SEC-01-closed]
  affects: [src/homelab_mcp/ssh_tools.py, tests/test_ssh_tools.py]
tech_stack:
  added: [tempfile, os]
  patterns: [SFTP tmpfile delivery, file-based grep, finally cleanup]
key_files:
  created: []
  modified:
    - src/homelab_mcp/ssh_tools.py
    - tests/test_ssh_tools.py
decisions:
  - "SFTP-based key delivery: key content written to local tmpfile, uploaded via conn.start_sftp_client(), never touches a shell string"
  - "grep -Ff with remote tmpfile path replaces grep -F with key as shell argument"
  - "cat {remote_tmp} >> authorized_keys replaces echo \"{public_key}\" interpolation"
  - "sed -i '/mcp_admin@/d' retained for force-update removal (does not interpolate key content)"
  - "Updated existing test sequences to add mktemp/SFTP/rm-f calls in correct order"
metrics:
  duration_seconds: 732
  completed_date: "2026-04-01"
  tasks_completed: 2
  files_changed: 2
---

# Phase 30 Plan 02: SEC-01 Shell Injection Fix Summary

SFTP-based public key delivery in setup_remote_mcp_admin replaces f-string shell interpolation — a public key containing shell metacharacters can no longer execute arbitrary commands on the remote host.

## What Was Done

Closed SEC-01: Eliminated two shell command injection sites in `setup_remote_mcp_admin`:

1. **Old injection site 1 (key check):** `f'sudo grep -F "{public_key}" /home/mcp_admin/.ssh/authorized_keys'`
   - **Fixed:** `sudo grep -Ff {remote_tmp} /home/mcp_admin/.ssh/authorized_keys` — grep reads pattern from a file, not a shell argument

2. **Old injection site 2 (key append):** `f'echo "{public_key}" | sudo -u mcp_admin tee -a /home/mcp_admin/.ssh/authorized_keys'`
   - **Fixed:** `sudo bash -c 'cat {remote_tmp} >> /home/mcp_admin/.ssh/authorized_keys ...'` — cat reads from tmpfile, key content never in shell string

**New flow:**
1. `mktemp /tmp/mcp_key_XXXXXX.pub` on remote (randomized name, avoids concurrent collision)
2. Write key to local tmpfile, SFTP upload via `conn.start_sftp_client()` + `sftp.put()`
3. `grep -Ff {remote_tmp}` for existence check (file-based, no key in args)
4. `cat {remote_tmp} >> authorized_keys` for append (file-based, no key in args)
5. `finally:` block — `os.unlink(local_tmp_path)` + `conn.run(f"rm -f {remote_tmp}")` — always cleans up

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Write failing RED tests for SFTP injection safety | 33e235b |
| 2 | Replace f-string interpolation with SFTP tmpfile delivery | 89e767f |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Adapted tests to worktree's older ssh_tools.py API**
- **Found during:** Task 1
- **Issue:** The worktree's `setup_remote_mcp_admin` uses `conn.run` directly (not `_sudo_run` helper) and requires `username: str, password: str` as positional args. Plan was written for the main branch's newer API.
- **Fix:** Tests written against the worktree's actual `conn.run` call pattern. Assertions check `conn.run` calls instead of `_sudo_run` calls.
- **Files modified:** tests/test_ssh_tools.py
- **Commit:** 33e235b

**2. [Rule 1 - Bug] Updated existing test conn.run sequences for new SFTP flow**
- **Found during:** Task 2
- **Issue:** Existing tests (`test_setup_remote_mcp_admin_success`, `_user_exists`, `_force_update_key`, `_no_force_update`) used `conn.run.side_effect` lists tuned to the old sequence. New code inserts `mktemp` and `rm -f` calls.
- **Fix:** Updated all four affected test sequences to add `mktemp_result` and `cleanup_tmp` at the correct positions, and added `mock_conn.start_sftp_client` mock to each test.
- **Files modified:** tests/test_ssh_tools.py
- **Commit:** 89e767f

## Acceptance Criteria Verification

- `ssh_tools.py` contains `import tempfile` — YES (line 6)
- `ssh_tools.py` contains `import os` — YES (line 5)
- `ssh_tools.py` contains `start_sftp_client` inside `setup_remote_mcp_admin` — YES (line 250)
- `ssh_tools.py` contains `mktemp /tmp/mcp_key_XXXXXX.pub` — YES (line 231)
- `ssh_tools.py` contains `grep -Ff` (file-based grep) — YES (line 255)
- `ssh_tools.py` does NOT contain `grep -F "{public_key}"` — CONFIRMED (grep returns empty)
- `ssh_tools.py` does NOT contain `echo "{public_key}"` — CONFIRMED (grep returns empty)
- `ssh_tools.py` contains `os.unlink(local_tmp_path)` in a finally block — YES (line 313)
- `ssh_tools.py` contains `rm -f {remote_tmp}` in a finally block — YES (line 314)
- All `{public_key}` f-string interpolations in shell commands removed — CONFIRMED

## Known Stubs

None. The SFTP-based key delivery is fully wired.

## Self-Check: PASSED

- `src/homelab_mcp/ssh_tools.py` modified — file exists
- `tests/test_ssh_tools.py` modified — file exists
- Commit 33e235b exists: `git log --oneline | grep 33e235b` — confirms test(30-02) commit
- Commit 89e767f exists: `git log --oneline | grep 89e767f` — confirms feat(30-02) commit
- No `{public_key}` f-string in any shell command in ssh_tools.py — confirmed via grep
