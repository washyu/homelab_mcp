# Phase 30: Security Fixes - Research

**Researched:** 2026-04-01
**Domain:** Python SSH security — shell injection prevention, TOFU lock serialization
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**SEC-01: Key Delivery Method**
- D-01: Use tmpfile + SFTP to deliver the public key to the remote host. Key content never touches a shell string. Upload to remote `/tmp` via `asyncssh.scp`, then use `_sudo_run` to move/append it.
- D-02: Use `mktemp /tmp/mcp_key_XXXXXX.pub` (randomized name) on the remote to avoid collisions from concurrent setup calls against the same host.
- D-03: For the "is key already installed?" check (currently `grep -F "{public_key}" ...`), use `grep -Ff /tmp/mcp_key_XXXXXX.pub authorized_keys` — file-based grep avoids shell interpolation. Reuses the same SFTP upload.
- D-04: Cleanup (rm temp file) happens in a `finally` block to guarantee removal even on error.

**SEC-02: TOFU Lock Scope**
- D-05: Acquire `_tofu_lock` at the top of `validate_host_public_key()` so the existence check (`_host_has_stored_key`) and the store (`_store_host_key`) are both inside the critical section. Simple `with _tofu_lock:` wrapping the entire method body.
- D-06: Remove the lock acquisition from `_store_host_key` since all callers now go through `validate_host_public_key` which holds the lock. Add a docstring note: "Caller must hold `_tofu_lock`."

### Claude's Discretion
- Exact temp file management details (local vs remote mktemp invocation order)
- Error message wording for SFTP failures
- Whether to extract a helper function for the SFTP upload+check+append sequence

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEC-01 | `setup_mcp_admin` and `add_to_sudoers` never interpolate public key content directly into remote shell strings — keys are transferred via a safe transport (tmpfile or heredoc) | SFTP upload via `conn.start_sftp_client()` + `sftp.put()` from local bytes; `grep -Ff <file>` for injection-safe existence check; `_sudo_run` for all sudo steps |
| SEC-02 | The TOFU existence check and append both execute under `_tofu_lock` — concurrent first-connections cannot write conflicting keys for the same host | Move `with _tofu_lock:` from `_store_host_key` to wrap the entire `validate_host_public_key` body; `_store_host_key` becomes lock-free with a docstring contract |
</phase_requirements>

---

## Summary

Phase 30 closes two targeted security holes in the SSH setup path. Neither fix requires new dependencies or architectural changes — only narrowly scoped changes to `ssh_tools.py` and `ssh_connection.py`.

**SEC-01** eliminates shell injection in `setup_remote_mcp_admin`. The current code at lines 315 and 358 of `ssh_tools.py` places `public_key` directly into f-strings that become remote shell commands. A public key containing backticks, `$()`, or double-quotes would execute arbitrary commands on the remote host. The fix uploads the key content to a remote tmpfile via SFTP (`conn.start_sftp_client()` + `sftp.put()`), then references that file path in all subsequent shell commands, so key content never reaches a shell argument.

**SEC-02** closes a TOCTOU race in `TOFUSSHClient.validate_host_public_key`. Currently `_tofu_lock` is only held during the file write inside `_store_host_key`, not during the preceding existence check in `_host_has_stored_key`. Two goroutines racing on a first-connection to the same host can both pass the existence check before either writes, resulting in duplicate or conflicting entries. The fix widens the lock to cover the entire `validate_host_public_key` body.

**Primary recommendation:** Implement both fixes as two separate, self-contained changes in `ssh_connection.py` and `ssh_tools.py`. Tests for each must be part of the same commit as the production code.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncssh | Already installed (project dependency) | SFTP file upload to remote | Provides `conn.start_sftp_client()` and `SFTPClient.put()` |
| threading | stdlib | `_tofu_lock` (already exists) | asyncssh callbacks are called in the asyncio event loop thread; threading.Lock is already used and is the correct choice |
| tempfile | stdlib | Local temp file for SFTP source | Used to write key bytes locally before uploading |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest + pytest-asyncio | Already installed | Unit tests for both fixes | All tests in this phase |
| unittest.mock | stdlib | Mock `conn.start_sftp_client`, mock lock | Avoid real SSH connections in unit tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SFTP put (D-01) | heredoc via stdin | Heredoc is also injection-safe but requires careful quoting of the `cat <<'EOF'` delimiter; SFTP is simpler and already decided |
| Widen lock in `validate_host_public_key` | Use asyncio.Lock | asyncssh calls `validate_host_public_key` synchronously from the event loop; asyncio.Lock cannot be acquired synchronously; threading.Lock is correct and already present |

**Installation:** No new packages needed. All dependencies exist.

---

## Architecture Patterns

### SEC-01: SFTP Tmpfile Upload Pattern

The full flow for safe key delivery in `setup_remote_mcp_admin`:

```
1. Write public_key bytes to a local tempfile (tempfile.NamedTemporaryFile)
2. SFTP upload local tempfile → remote mktemp path
3. grep -Ff <remote_tmpfile> authorized_keys  (existence check, injection-safe)
4. cat <remote_tmpfile> >> authorized_keys     (append, no shell interpolation)
5. rm -f <remote_tmpfile>  (in finally block)
```

**Key detail:** The remote tmpfile path is obtained by running `mktemp /tmp/mcp_key_XXXXXX.pub` via `conn.run()` before the SFTP upload. The SFTP destination is the string returned by `mktemp`.

```python
# Source: asyncssh docs + CONTEXT.md D-01 through D-04

# Step 1: get a randomized remote temp path
mktemp_result = await conn.run("mktemp /tmp/mcp_key_XXXXXX.pub", check=False)
remote_tmp = mktemp_result.stdout.strip()  # e.g. "/tmp/mcp_key_aB3x9K.pub"

# Step 2: upload via SFTP using existing connection
import tempfile, os
with tempfile.NamedTemporaryFile(delete=False, suffix=".pub") as local_tmp:
    local_tmp.write(public_key.encode())
    local_tmp_path = local_tmp.name

try:
    async with conn.start_sftp_client() as sftp:
        await sftp.put(local_tmp_path, remote_tmp)

    # Step 3: injection-safe existence check
    key_check = await _sudo_run(
        conn,
        f"grep -Ff {remote_tmp} /home/mcp_admin/.ssh/authorized_keys 2>/dev/null",
        password=creds.password,
        check=False,
    )
    key_exists = key_check.exit_status == 0

    if not key_exists or force_update_key:
        # Step 4: append (no public_key in shell string)
        add_key = await _sudo_run(
            conn,
            f"bash -c 'cat {remote_tmp} >> /home/mcp_admin/.ssh/authorized_keys && "
            "chmod 600 /home/mcp_admin/.ssh/authorized_keys && "
            "chown mcp_admin:mcp_admin /home/mcp_admin/.ssh/authorized_keys'",
            password=creds.password,
            check=False,
        )
finally:
    # Step 5: cleanup both local and remote tmp
    os.unlink(local_tmp_path)
    await _sudo_run(conn, f"rm -f {remote_tmp}", password=creds.password, check=False)
```

### SEC-02: Widened Lock Pattern

```python
# Source: CONTEXT.md D-05 and D-06

# BEFORE (race window between check and store):
def validate_host_public_key(self, host, addr, port, key):
    if self._host_has_stored_key(host, port):   # no lock here
        return False
    self._store_host_key(host, port, key)        # lock only inside _store_host_key
    return True

# AFTER (entire check+store under one lock):
def validate_host_public_key(self, host, addr, port, key):
    with _tofu_lock:
        if self._host_has_stored_key(host, port):
            logger.warning("Host key mismatch ...")
            return False
        self._store_host_key(host, port, key)
        logger.info("TOFU: Accepted and stored ...")
        return True

# _store_host_key loses its internal `with _tofu_lock:` block:
def _store_host_key(self, host, port, key):
    """Store a host key in the known_hosts file.
    Caller must hold `_tofu_lock`.
    """
    host_label = self._format_host_label(host, port)
    key_export = key.export_public_key().decode("utf-8").strip()
    parts = key_export.split()
    key_data = " ".join(parts[:2])
    entry = f"{host_label} {key_data}\n"
    try:
        with open(self._known_hosts_path, "a") as f:
            f.write(entry)
    except OSError:
        logger.error("Failed to write to known_hosts file: %s", self._known_hosts_path)
```

### Anti-Patterns to Avoid

- **f-string key interpolation:** `f'echo "{public_key}" >> authorized_keys'` — any key with `"`, `$`, or backticks breaks the shell command or executes code.
- **grep -F with shell argument:** `grep -F "{public_key}" file` — still passes key content as a shell argument; use `grep -Ff <file>` instead.
- **Lock only on write:** Holding `_tofu_lock` only inside `_store_host_key` still allows two threads to both pass `_host_has_stored_key` before either writes — that is the exact TOCTOU window this fix closes.
- **asyncio.Lock for TOFU:** asyncssh calls `validate_host_public_key` as a synchronous callback; `asyncio.Lock` cannot be acquired with `with` in a sync context.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Writing key to remote without shell expansion | Custom base64 encode/decode pipeline | `sftp.put()` on existing connection | SFTP is binary-safe, no shell involved at all |
| Thread-safe file append | Custom file locking | `threading.Lock` (already present) | OS-level file write is not atomic; Lock ensures check+write are one operation |
| Injection-safe grep | Escape the key string | `grep -Ff <tmpfile>` | Shell escaping is error-prone for arbitrary key content; file-based grep has no expansion |

---

## Runtime State Inventory

Step 2.5: SKIPPED — this is not a rename/refactor/migration phase. It is a targeted security fix to two specific code paths.

---

## Environment Availability

Step 2.6: SKIPPED — no external dependencies beyond the project's existing asyncssh and pytest stack. No new tools, services, CLIs, or runtimes are introduced.

---

## Common Pitfalls

### Pitfall 1: Remote mktemp path not stripped
**What goes wrong:** `mktemp` stdout includes a trailing newline. If not stripped, the path embedded in subsequent shell commands gets a literal `\n`, breaking all commands silently.
**Why it happens:** `conn.run()` returns stdout as a string with the shell's trailing newline.
**How to avoid:** Always call `.strip()` on `mktemp_result.stdout` before using it as a path.
**Warning signs:** `_sudo_run` exits non-zero on the grep step with "No such file or directory".

### Pitfall 2: SFTP put called before mktemp
**What goes wrong:** If SFTP upload targets a hardcoded path (e.g. `/tmp/mcp_key.pub`) without `mktemp`, two concurrent `setup_remote_mcp_admin` calls to the same host can overwrite each other's tmpfile.
**Why it happens:** D-02 exists for this reason — always `mktemp` first, then upload to the returned path.
**How to avoid:** Run `mktemp` on the remote first; use the returned path as the SFTP destination.

### Pitfall 3: Local tempfile not cleaned up on SFTP error
**What goes wrong:** SFTP can raise `SFTPError` if the remote path is wrong or permissions deny. If the `try/finally` only cleans the remote tmpfile, the local tempfile leaks.
**Why it happens:** Two cleanup targets (local tempfile from `tempfile.NamedTemporaryFile`, remote tmpfile from `mktemp`) require two cleanup steps.
**How to avoid:** Use a single outer `try/finally` that calls `os.unlink(local_tmp_path)` AND `await _sudo_run(...rm -f remote_tmp...)` in the `finally` block.

### Pitfall 4: Existing test for `_store_host_key` lock breaks
**What goes wrong:** `tests/test_ssh_connection.py::TestTOFULock::test_store_host_key_uses_lock` (line 247) patches `_tofu_lock` and asserts it is acquired inside `_store_host_key`. After D-06, `_store_host_key` no longer holds the lock — this test will fail.
**Why it happens:** The test was written to match the old locking location.
**How to avoid:** Update this test to instead verify the lock is acquired inside `validate_host_public_key`. The new test should call `validate_host_public_key` (not `_store_host_key` directly) and assert `mock_lock.__enter__` was called once.

### Pitfall 5: `validate_host_public_key` is a synchronous callback
**What goes wrong:** asyncssh calls `validate_host_public_key` synchronously (it is not `async def`). Any `await` inside it will cause a runtime error.
**Why it happens:** asyncssh's host key validation protocol is synchronous.
**How to avoid:** The lock widening (`with _tofu_lock:`) is synchronous and correct. Do not add any `await` calls inside `validate_host_public_key`. All async operations (SFTP, sudo) belong in `setup_remote_mcp_admin`, not in the TOFU callback.

---

## Code Examples

### SFTP upload via existing connection (verified pattern)
```python
# Source: asyncssh documentation — conn.start_sftp_client() async context manager
async with conn.start_sftp_client() as sftp:
    await sftp.put(local_path_str, remote_path_str)
```

### Remote mktemp + stripped path
```python
# Source: standard Unix + asyncssh conn.run()
result = await conn.run("mktemp /tmp/mcp_key_XXXXXX.pub", check=False)
remote_tmp = result.stdout.strip()
```

### grep -Ff file-based existence check (injection-safe)
```python
# Source: CONTEXT.md D-03
# No public_key content in the shell string — only the tmpfile path
key_check = await _sudo_run(
    conn,
    f"grep -Ff {remote_tmp} /home/mcp_admin/.ssh/authorized_keys 2>/dev/null",
    password=creds.password,
    check=False,
)
```

### Widened TOFU lock (from CONTEXT.md D-05/D-06)
```python
def validate_host_public_key(self, host, addr, port, key):
    with _tofu_lock:
        if self._host_has_stored_key(host, port):
            return False
        self._store_host_key(host, port, key)
        return True
```

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (installed) |
| Config file | `pytest.ini` (project root) |
| Quick run command | `uv run pytest tests/test_ssh_connection.py tests/test_ssh_tools.py -v --tb=short` |
| Full suite command | `uv run pytest tests/ -m "not integration" -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEC-01 | Shell metacharacters in public key do not execute on remote — SFTP path used, not f-string | unit | `uv run pytest tests/test_ssh_tools.py -k "injection" -v` | Wave 0 (new test) |
| SEC-01 | SFTP tmpfile is removed in `finally` even when append fails | unit | `uv run pytest tests/test_ssh_tools.py -k "cleanup" -v` | Wave 0 (new test) |
| SEC-02 | Second concurrent call to `validate_host_public_key` blocks until first completes | unit | `uv run pytest tests/test_ssh_connection.py -k "concurrent or race" -v` | Wave 0 (new test) |
| SEC-02 | After concurrent first-connections, known_hosts has exactly one entry for the host | unit | `uv run pytest tests/test_ssh_connection.py -k "single_entry" -v` | Wave 0 (new test) |
| SEC-02 (compat) | Existing lock test updated: lock acquired in `validate_host_public_key`, not `_store_host_key` | unit | `uv run pytest tests/test_ssh_connection.py::TestTOFULock -v` | Exists — needs update |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_ssh_connection.py tests/test_ssh_tools.py -v --tb=short`
- **Per wave merge:** `uv run pytest tests/ -m "not integration" -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_ssh_tools.py` — new test: `test_setup_mcp_admin_key_injection_safe` — covers SEC-01 (metacharacters in key content; asserts no f-string interpolation path reached)
- [ ] `tests/test_ssh_tools.py` — new test: `test_setup_mcp_admin_tmpfile_cleanup_on_error` — covers SEC-01 D-04 (finally block removes tmpfile even when append fails)
- [ ] `tests/test_ssh_connection.py` — new test: `test_tofu_concurrent_first_connection_single_entry` — covers SEC-02 (two threads racing; known_hosts ends with one entry)
- [ ] `tests/test_ssh_connection.py` — update test: `TestTOFULock::test_store_host_key_uses_lock` → assert lock acquired in `validate_host_public_key` instead of `_store_host_key`

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `f'echo "{public_key}" >> authorized_keys'` | SFTP put + `cat tmpfile >>` | Phase 30 | Eliminates shell injection via key content |
| Lock only inside `_store_host_key` | Lock wraps entire check+store in `validate_host_public_key` | Phase 30 | Closes TOCTOU race window |

**Deprecated after this phase:**
- Direct interpolation of `public_key` into any remote shell command string — forbidden, replaced by tmpfile references.
- `with _tofu_lock:` inside `_store_host_key` — removed, lock ownership moves to caller.

---

## Open Questions

1. **`force_update_key` path and sed command**
   - What we know: The `sed -i '/mcp_admin@/d'` removal step (line 348) does not interpolate `public_key` and is not an injection site — it is fine as-is.
   - What's unclear: Should the removal step also use a tmpfile approach for consistency, or is it out of scope?
   - Recommendation: Leave `sed -i '/mcp_admin@/d'` unchanged — it does not use key content and is out of scope per CONTEXT.md.

2. **`add_to_sudoers` injection site**
   - What we know: CONTEXT.md and the phase description mention `add_to_sudoers` as a target, but the CONTEXT.md canonical refs point only to `setup_remote_mcp_admin` (lines 315 and 358). Grepping `src/` shows no separate `add_to_sudoers` function — the sudoers step is inside `setup_remote_mcp_admin` at line 377 and does not interpolate `public_key`.
   - What's unclear: Whether `add_to_sudoers` refers to a separate function or the sudoers step inside `setup_remote_mcp_admin`.
   - Recommendation: Treat the two injection sites at lines 315 and 358 as the canonical targets. The sudoers echo at line 378 is a hardcoded string and is not an injection site.

---

## Sources

### Primary (HIGH confidence)
- asyncssh GitHub + docs: `conn.start_sftp_client()` returns an `SFTPClient`; `sftp.put(local, remote)` uploads a local file to a remote path over the existing connection. No new connection required. Verified via WebFetch of asyncssh GitHub docs.
- `src/homelab_mcp/ssh_connection.py` (full read): Confirms `_tofu_lock` is `threading.Lock`, `validate_host_public_key` is synchronous, lock currently inside `_store_host_key` only.
- `src/homelab_mcp/ssh_tools.py` lines 199-235, 280-447: Confirms injection sites at lines 315 and 358; confirms `_sudo_run` pattern.
- `tests/test_ssh_connection.py` (full read): Confirms existing `TestTOFULock::test_store_host_key_uses_lock` will need updating.
- `.planning/phases/30-security-fixes/30-CONTEXT.md` (full read): All implementation decisions are locked (D-01 through D-06).

### Secondary (MEDIUM confidence)
- asyncssh WebSearch result confirming `conn.start_sftp_client()` is the standard SFTP interface on an existing connection. Consistent with existing usage patterns in the codebase.

### Tertiary (LOW confidence)
- None.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; asyncssh SFTP API confirmed, threading.Lock already in use
- Architecture: HIGH — implementation decisions fully locked in CONTEXT.md; code read directly
- Pitfalls: HIGH — derived from direct code inspection of injection sites and lock scope; one pitfall (Pitfall 4) confirmed by reading the existing test

**Research date:** 2026-04-01
**Valid until:** 2026-05-01 (stable domain — asyncssh API, threading primitives, shell behavior do not change rapidly)
