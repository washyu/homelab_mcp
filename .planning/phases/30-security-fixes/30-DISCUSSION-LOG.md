# Phase 30: Security Fixes - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-01
**Phase:** 30-security-fixes
**Areas discussed:** Key delivery method, TOFU lock scope, Test strategy

---

## Key Delivery Method

### Q1: How should the public key be delivered to the remote host?

| Option | Description | Selected |
|--------|-------------|----------|
| Tmpfile + sftp | Write key to temp file, SFTP to remote, sudo move into place. Key never touches shell string. | :heavy_check_mark: |
| Heredoc via stdin | Pipe key through stdin. Simpler but mixes stdin with sudo password piping. | |
| SFTP direct write | Use asyncssh SFTP to write directly to authorized_keys. No shell, but needs sudo-level SFTP access. | |

**User's choice:** Tmpfile + sftp
**Notes:** Clean separation -- key content only flows through SFTP, never interpolated into any command string.

### Q2: How should the 'is key already installed?' check avoid interpolation?

| Option | Description | Selected |
|--------|-------------|----------|
| SFTP + grep -Ff | Upload key to temp file, use `grep -Ff` for file-based matching. Reuses same SFTP upload. | :heavy_check_mark: |
| SFTP read + Python compare | Read authorized_keys back to Python, string compare locally. Zero shell risk but more data transfer. | |

**User's choice:** SFTP + grep -Ff
**Notes:** Single SFTP upload serves both the check and the append.

### Q3: Should the temp file use a predictable or randomized name?

| Option | Description | Selected |
|--------|-------------|----------|
| Randomized mktemp | `mktemp /tmp/mcp_key_XXXXXX.pub` avoids collisions on concurrent calls. | :heavy_check_mark: |
| Fixed /tmp/mcp_key.pub | Simpler, deterministic cleanup. Concurrent same-host setup is unlikely. | |

**User's choice:** Randomized mktemp

### Q4: Should the SFTP upload go to /tmp or connecting user's home?

| Option | Description | Selected |
|--------|-------------|----------|
| Remote /tmp | Standard temp location, world-writable, sudo can read it. | :heavy_check_mark: |
| Connecting user's home | More restricted but requires writable home dir. | |

**User's choice:** Remote /tmp

### Q5: Should cleanup happen in a finally block?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, finally block | Guarantees temp file removal even on error. | :heavy_check_mark: |
| Best-effort cleanup | Just rm at the end; temp file may linger on failure. | |

**User's choice:** Yes, finally block

---

## TOFU Lock Scope

### Q1: How should the TOFU lock be restructured for atomicity?

| Option | Description | Selected |
|--------|-------------|----------|
| Lock entire validate method | `with _tofu_lock:` at top of validate_host_public_key. Simple, correct. | :heavy_check_mark: |
| Extract check-and-store helper | New `_tofu_accept()` method holds lock around both operations. More modular. | |

**User's choice:** Lock entire validate method

### Q2: How to handle deadlock with _store_host_key's internal lock?

| Option | Description | Selected |
|--------|-------------|----------|
| Remove lock from _store_host_key | All callers go through validate which holds the lock. Simpler. | :heavy_check_mark: |
| Use RLock (reentrant) | Switch to threading.RLock() so same thread can acquire twice. | |

**User's choice:** Remove lock from _store_host_key

---

## Test Strategy

### Q1: How to test shell metacharacter injection is blocked?

| Option | Description | Selected |
|--------|-------------|----------|
| Mock _sudo_run, assert no interpolation | Patch _sudo_run and scp. Call with malicious key. Assert key only in SCP args, never in command strings. | :heavy_check_mark: |
| Regex guard in _sudo_run | Runtime check rejecting commands containing public key content. Belt-and-suspenders. | |
| You decide | Claude picks best approach. | |

**User's choice:** Mock _sudo_run, assert no interpolation

### Q2: How to test TOFU lock serialization?

| Option | Description | Selected |
|--------|-------------|----------|
| Threading + shared known_hosts | Spawn N threads calling validate_host_public_key for same host. Assert exactly one entry. | :heavy_check_mark: |
| Sequential with lock assertion | Call validate twice in sequence, assert second returns False. Simpler but no race stress. | |
| You decide | Claude picks best concurrency test approach. | |

**User's choice:** Threading + shared known_hosts

---

## Claude's Discretion

- Exact temp file management details (local vs remote mktemp invocation order)
- Error message wording for SFTP failures
- Whether to extract a helper function for the SFTP upload+check+append sequence

## Deferred Ideas

None -- discussion stayed within phase scope
