# Phase 30: Security Fixes - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Close two known attack surfaces in the SSH setup path: (1) shell command injection via public key interpolation in `setup_mcp_admin`/`add_to_sudoers`, and (2) TOFU race condition allowing concurrent writes of conflicting host keys. No new features, no refactoring beyond what's needed for the fix.

</domain>

<decisions>
## Implementation Decisions

### SEC-01: Key Delivery Method
- **D-01:** Use tmpfile + SFTP to deliver the public key to the remote host. Key content never touches a shell string. Upload to remote `/tmp` via `asyncssh.scp`, then use `_sudo_run` to move/append it.
- **D-02:** Use `mktemp /tmp/mcp_key_XXXXXX.pub` (randomized name) on the remote to avoid collisions from concurrent setup calls against the same host.
- **D-03:** For the "is key already installed?" check (currently `grep -F "{public_key}" ...`), use `grep -Ff /tmp/mcp_key_XXXXXX.pub authorized_keys` — file-based grep avoids shell interpolation. Reuses the same SFTP upload.
- **D-04:** Cleanup (rm temp file) happens in a `finally` block to guarantee removal even on error.

### SEC-02: TOFU Lock Scope
- **D-05:** Acquire `_tofu_lock` at the top of `validate_host_public_key()` so the existence check (`_host_has_stored_key`) and the store (`_store_host_key`) are both inside the critical section. Simple `with _tofu_lock:` wrapping the entire method body.
- **D-06:** Remove the lock acquisition from `_store_host_key` since all callers now go through `validate_host_public_key` which holds the lock. Add a docstring note: "Caller must hold `_tofu_lock`."

### Claude's Discretion
- Exact temp file management details (local vs remote mktemp invocation order)
- Error message wording for SFTP failures
- Whether to extract a helper function for the SFTP upload+check+append sequence

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Security Fix Targets
- `src/homelab_mcp/ssh_tools.py` -- Lines 315 and 358: current injection sites where `public_key` is interpolated into shell strings via f-strings
- `src/homelab_mcp/ssh_connection.py` -- Lines 46-81: `validate_host_public_key()` with race condition; lines 112-135: `_store_host_key()` with existing lock

### Supporting Code
- `src/homelab_mcp/ssh_tools.py` -- `_sudo_run` helper (line 199): already handles sudo -S stdin piping; fixes will use this
- `src/homelab_mcp/tool_handlers/ssh_handlers.py` -- `handle_setup_mcp_admin` dispatcher (line 24)

### Requirements
- `.planning/REQUIREMENTS.md` -- SEC-01 and SEC-02 definitions with acceptance criteria

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_sudo_run()` helper in `ssh_tools.py:199`: Handles sudo password piping via stdin. All sudo commands in the fix should use this.
- `_tofu_lock` (`threading.Lock`) in `ssh_connection.py:26`: Already exists, just needs wider scope.
- `asyncssh.scp` available via the existing `asyncssh` dependency.

### Established Patterns
- `@ssh_connection_wrapper` decorator handles connection setup and error wrapping for SSH tools
- `@retry_on_failure` decorator on `setup_remote_mcp_admin` handles transient failures
- `_sudo_run` uses `check=False` pattern with manual exit status inspection

### Integration Points
- `setup_remote_mcp_admin()` in `ssh_tools.py` is the main function to modify for SEC-01
- `TOFUSSHClient.validate_host_public_key()` in `ssh_connection.py` is the method to modify for SEC-02
- `TOFUSSHClient._store_host_key()` needs lock removal (moved to caller)

</code_context>

<specifics>
## Specific Ideas

- Flow for SEC-01: SFTP upload key to remote `/tmp` (mktemp name) -> `grep -Ff` to check existence -> `cat >>` to append -> `rm -f` in finally block
- Flow for SEC-02: `with _tofu_lock:` wrapping entire `validate_host_public_key` body; `_store_host_key` loses its internal lock

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 30-security-fixes*
*Context gathered: 2026-04-01*
