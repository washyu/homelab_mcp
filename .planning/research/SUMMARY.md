# Project Research Summary

**Project:** Homelab MCP Server — v1.4 Real-World Reliability
**Domain:** Python MCP server bug-fix milestone — interactive shell, SSH credential flow, TOFU host-key trust
**Researched:** 2026-03-13
**Confidence:** HIGH

## Executive Summary

v1.4 is a tightly scoped bug-fix milestone addressing three issues found during real Mac testing: a silent interactive shell failure, an SSH credential flow that leaves the AI agent with no recovery path, and SSH timeouts after device registration. Research confirms all three bugs are pure code-level defects in the existing stack — no new runtime dependencies are needed. The fixes are confined to six source files and collectively affect fewer than 100 lines of code.

The recommended approach is to fix the bugs in two dependency-ordered phases and accompany each code fix with schema description improvements so the agent has proactive guidance before errors occur. The interactive shell bug has two root causes: a PTY `term_size` argument is inverted (24 cols x 80 rows instead of 80 cols x 24 rows) causing display corruption, and the WebSocket output loop silently exits on EOF without notifying the browser. The credential flow bug is an opaque `PermissionDenied` that gives the agent no recovery steps. The TOFU timeout is most likely caused by a corrupted `known_hosts` entry — `export_public_key()` may include a comment field, producing a four-field line where asyncssh expects exactly three — combined with a credential hostname/IP label mismatch where `credentials add` stores a label that does not match the label used during discovery.

The primary risk in this milestone is regression: 635 tests are currently passing and several rely on the silent `mcp_admin` fallthrough behavior in `resolve_ssh_credentials()`. Any change to that fallthrough must be preceded by a test audit. A secondary risk is the dead `asyncio.Lock` in `TOFUSSHClient` — if touched without recognizing it must become a `threading.Lock`, it will deadlock the server on first SSH connection to a new host.

## Key Findings

### Recommended Stack

No stack changes for v1.4. All three bugs are call-site or error-handling issues within the existing dependencies. asyncssh 2.21.0, mcp 1.9.4, starlette 0.47.1, and websockets 16.0 are all confirmed correct at their locked versions. The bugs are in how the code calls these libraries, not in the libraries themselves.

**Core technologies (unchanged):**
- asyncssh 2.21.0: SSH connections, PTY sessions, TOFU host-key storage — `term_size` order and `validate_host_public_key` behavior verified by direct source inspection at `.venv/lib/python3.12/site-packages/asyncssh/`
- starlette + websockets: WebSocket I/O relay for browser-based shell — correct approach; bug is in the `stdout.read()` call inside the relay loop which blocks until EOF rather than returning available bytes
- keyring + `credential_registry.json`: Two-tier credential storage (OS keyring for passwords, SQLite for key-auth) — architecture is sound; bug is missing actionable errors when all tiers miss

### Expected Features

**Must fix (table stakes — blocks real-world use):**
- Interactive shell returns actionable output — today `start_interactive_shell` returns a URL that is unreachable in stdio mode and displays nothing even when reachable due to the blocking `read()` call
- SSH credential error tells the agent the exact recovery workflow — "Permission denied" without naming `credentials add` or `register_server` leaves the agent looping with no path forward
- `list_keyring_credentials` tool (new) — the agent has no way to inspect keyring state; analogous to `list_registered_servers` for the DB path; wraps the existing `credential_store.list_credentials("ssh")`
- TOFU works on first SSH connection for keyring-registered hosts — the core timeout bug for the `credentials add` then `ssh_discover` sequence

**Should add (high value, low cost):**
- SSH tool schema descriptions: one sentence naming the credential recovery path in each `ssh_discover` and `ssh_execute_command` description
- `register_server` description: mention that it stores the SSH host key (TOFU awareness)
- `start_interactive_shell` description: explicit "browser-only" language so the agent does not report false success

**Defer to v1.x:**
- `trust_host_key` dedicated tool — only needed if transparent TOFU fix proves insufficient
- `ssh_credential_setup` prompt — full workflow walkthrough; valuable but not blocking
- `credentials verify <host>` CLI command — diagnostic tool; nice-to-have

### Architecture Approach

All three bugs are isolated to narrow slices of the existing architecture. The build order has one hard dependency: the TOFU fix should precede credential error handling work because integration tests that verify `CredentialNotFoundError` behavior require a working SSH connection path. The shell streaming fix is fully independent and can be developed in parallel. Schema description updates are string-only changes with no code dependencies.

**Files changed:**

1. `shell_session.py` — fix `term_size=(24, 80)` to `term_size=(80, 24)` (cols x rows, verified at asyncssh `channel.py:1176`)
2. `http_app.py` — `read_output()` inner coroutine: replace blocking `stdout.read(4096)` with `asyncio.wait_for(..., timeout=0.05)` to enable streaming; add EOF notification to browser
3. `ssh_connection.py` — `TOFUSSHClient._store_host_key()`: strip comment field from `export_public_key()` output so `known_hosts` entries have exactly three fields; replace dead `asyncio.Lock` with `threading.Lock`
4. `ssh_tools.py` — `resolve_ssh_credentials()`: raise `CredentialNotFoundError` at bare-miss fallthrough instead of returning a no-auth `SSHCredentials`
5. `tool_schemas/ssh_tools_schema.py` — add credential workflow hints to `ssh_discover` and `ssh_execute_command` descriptions
6. `prompt_registry.py` — add `connect_to_device` prompt (~25 lines, purely additive)

**No-change modules:** `server.py`, `database.py`, `sitemap.py`, `credential_store.py`, `vm_operations.py`, `proxmox_api.py`, `service_installer.py`, `infrastructure_crud.py`

### Critical Pitfalls

1. **Dead `asyncio.Lock` in `TOFUSSHClient` will deadlock if naively activated** — `_tofu_lock = asyncio.Lock()` is declared but never acquired. `validate_host_public_key` is a synchronous callback; `await lock.acquire()` is unreachable from sync context. Any attempt to add locking via `asyncio.run()` or `loop.run_until_complete()` deadlocks the server (Python 3.10+: `RuntimeError: This event loop is already running`). Fix: replace with `threading.Lock` and use `with _tofu_lock:` inside `_store_host_key`.

2. **Changing `resolve_ssh_credentials` will break tests relying on `mcp_admin` fallthrough** — 635 currently-passing tests include some that depend on the silent fallthrough to the `mcp_admin` key. Making this path raise `CredentialNotFoundError` is correct new behavior but will appear as regressions. Must audit with `git grep "resolve_ssh_credentials\|get_credential_by_hostname\|mcp_admin" tests/` before implementation.

3. **Module-level singleton in `shell_session.py` breaks test isolation if async tasks are added** — `session_manager = ShellSessionManager()` is created at import time. Any `asyncio.create_task()` call in `__init__` or at module level will leak tasks into test event loops, causing `RuntimeWarning: Task was destroyed` across all 635 tests. The existing `start_cleanup_task()` pattern (explicit lifespan call only) is correct — do not change it.

4. **`start_interactive_shell` in stdio mode returns a dead URL** — The tool succeeds and returns a URL even when the HTTP server is not running (default Claude Desktop mode is stdio). Fix: detect HTTP mode (`MCP_HTTP_PORT` env var or a server-level flag) and return an actionable error, not a URL.

5. **`known_hosts` key export may include comment field, causing TOFU to re-trigger and then reject the connection** — `key.export_public_key().decode()` may return `"ssh-rsa AAAA...== user@host"` (four fields). asyncssh `known_hosts` expects exactly `"hostname algorithm base64"` (three fields). A four-field entry causes asyncssh to treat the key as not found, re-triggering TOFU on the same host, which then hits the MITM rejection path and refuses the connection. Fix: `" ".join(key_export.split()[:2])` to keep only algorithm and base64.

## Implications for Roadmap

Based on the dependency chain established in ARCHITECTURE.md, a three-phase structure is recommended:

### Phase 1: Core SSH Reliability (TOFU + Shell Streaming)

**Rationale:** TOFU fix unblocks integration tests for all subsequent work. Shell streaming fix is independent and has no downstream dependencies. These two fixes are the "make it work at all" layer.

**Delivers:**
- `ssh_connect()` TOFU correctly populates `known_hosts` for all registration paths including keyring-only (`credentials add`) hosts
- Interactive shell streams PTY output to the browser in real time (non-blocking `asyncio.wait_for` read loop)
- Browser receives explicit EOF/error notifications instead of hanging silently on a blank terminal
- Correct terminal dimensions (80x24) so shell prompts render correctly

**Addresses features:** TOFU fix for keyring path (P1), interactive shell streaming fix (P1)

**Files:** `ssh_connection.py` (`_store_host_key` format + `threading.Lock`), `http_app.py` (`read_output` loop + EOF notification), `shell_session.py` (`term_size` inversion fix)

**Must avoid:** Deadlock from `asyncio.Lock` (must become `threading.Lock`); any `asyncio.create_task()` at module level in `shell_session.py`; `asyncio.run()` inside a synchronous callback

### Phase 2: Agent Guidance (Credential Errors + Schema Hints)

**Rationale:** Depends on Phase 1 TOFU being stable so integration tests pass. These changes make the system recoverable — the agent can diagnose and guide the user through setup failures rather than looping on opaque errors.

**Delivers:**
- `CredentialNotFoundError` with actionable message naming the exact CLI command and tool sequence for both auth paths
- Differentiated errors: "no credentials configured" vs "credentials configured but rejected"
- `list_keyring_credentials` tool (new) for agent-side credential state inspection
- `start_interactive_shell` returns HTTP-mode detection error in stdio mode instead of a dead URL
- Schema descriptions updated for `ssh_discover`, `ssh_execute_command`, `register_server`, and `start_interactive_shell`

**Addresses features:** SSH credential actionable error (P1), `list_keyring_credentials` tool (P1), schema credential guidance sentence (P1), browser-only shell description (differentiator)

**Files:** `ssh_tools.py` (`resolve_ssh_credentials` raise path + new exception class), `tool_handlers/ssh_handlers.py` (catch `CredentialNotFoundError`, HTTP-mode check), `tool_schemas/ssh_tools_schema.py` (description strings), `tool_schemas/credential_tools_schema.py` (new `list_keyring_credentials` entry), `tool_handlers/credential_handlers.py` (new handler)

**Must avoid:** Changing `resolve_ssh_credentials` before auditing tests that rely on `mcp_admin` fallthrough; breaking the DB Tier-3 fallback used by pre-v1.3 devices

### Phase 3: Workflow Completeness (Prompt + Polish)

**Rationale:** Purely additive. No existing code is modified. The `connect_to_device` prompt gives the agent a pre-built recipe for device onboarding, preventing the most common confusion where the agent calls `ssh_discover` with no credentials, gets an error, and has no path forward.

**Delivers:**
- `connect_to_device` prompt in `prompt_registry.py` sequencing the full setup flow: `setup_mcp_admin` -> `register_server` -> `credentials add` -> `ssh_discover` -> verify
- Warning log in `resolve_ssh_credentials` Tier-2 path when registry entry exists but keyring returns `None` (registry/keyring desync)
- Optional: `trust_host_key` tool if Phase 1 TOFU transparent fix proves insufficient for any edge cases

**Addresses features:** `ssh_credential_setup` prompt (deferred in FEATURES.md but low cost), keyring desync warning (PITFALLS minor pitfall 11)

**Files:** `prompt_registry.py` only (plus optionally `tool_schemas/` and `tool_handlers/` for `trust_host_key` if needed)

### Phase Ordering Rationale

- Phase 1 TOFU fix must precede Phase 2 credential error work because integration tests that exercise `CredentialNotFoundError` require a working SSH connection to validate the full path
- Phase 1 shell streaming fix is independent of both TOFU and credential work and can be developed as a parallel sub-task
- Phase 2 schema description updates are string-only changes with no code dependencies — they can be written at any time but are grouped with the error-handling work they document
- Phase 3 is purely additive and has zero blocking dependencies; it benefits from being written after Phase 2 has confirmed the correct credential workflow sequence

### Research Flags

Phases that warrant investigation before or during implementation:

- **Phase 1 (TOFU key format):** The `export_public_key()` comment-stripping hypothesis is MEDIUM confidence. Needs a test that creates a real `SSHKey`, calls `export_public_key()`, and inspects the output format to confirm the comment is actually present before committing to the fix approach. Plan: write the verification test first; the fix (`" ".join(parts[:2])`) is safe regardless.
- **Phase 1 (TOFU timeout root cause):** Two root causes are identified — key format corruption and credential hostname/IP label mismatch. The actual timeout on Mac may be either or both. The fix addresses both; verify which manifests via integration test before marking done.

Phases with well-established patterns (skip deeper research):

- **Phase 1 (shell streaming):** `asyncio.wait_for()` with `TimeoutError` catch is a standard non-blocking StreamReader pattern. Verified against asyncssh `stream.py` `read()` EOF behavior.
- **Phase 2 (`CredentialNotFoundError`):** Standard Python exception pattern; handler catch pattern already established in codebase. No research needed.
- **Phase 2 (`list_keyring_credentials` tool):** `credential_store.list_credentials("ssh")` already exists; needs only schema entry + handler wiring following the same pattern as `list_registered_servers`.
- **Phase 3 (prompt):** `prompt_registry.py` builder pattern is established by existing prompts. No research needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All three bugs verified by direct asyncssh source inspection; no new deps confirmed by reading `uv.lock` |
| Features | HIGH | Root causes confirmed by codebase inspection; feature set is purely reactive to confirmed bugs with clear fix strategies |
| Architecture | HIGH | All integration points verified by direct source read; build order derived from actual import dependencies; touch-point line counts verified |
| Pitfalls | HIGH | Critical pitfalls verified against Python stdlib behavior (`asyncio.Lock` / `threading.Lock`) and direct codebase patterns; TOFU format hypothesis is MEDIUM pending live verification |

**Overall confidence:** HIGH

### Gaps to Address

- **TOFU key export format (MEDIUM):** The `export_public_key()` comment-stripping hypothesis needs a live verification test before Phase 1 implementation is finalized. The fix strategy is safe regardless, but confirming the comment field is actually present avoids over-engineering.
- **Credential hostname/IP mismatch as TOFU timeout cause:** Identified as the most likely cause of reported timeouts by STACK.md analysis, but cannot be reproduced without a physical test device. The fix (improve error messages + document that `credentials add --hostname` must use the same label as used during discovery) is safe to ship without physical reproduction.
- **`mcp_admin` test fallthrough audit (pre-implementation checklist):** Must run `git grep "mcp_admin" tests/` before Phase 2 implementation. Not a research gap — a required pre-work step.

## Sources

### Primary (HIGH confidence)

- asyncssh 2.21.0 source, `.venv/lib/python3.12/site-packages/asyncssh/` — `connection.py` lines 1334-1344, 3473-3491, 4355-4388, 8128 (host key validation flow, `known_hosts` behavior, `create_session` defaults); `channel.py` lines 1170-1184 (`term_size` argument order); `process.py` lines 1456-1480 (`change_terminal_size` order); `client.py` lines 124-162 (`validate_host_public_key` contract); `stream.py` line 575 (SSHReader `read()` EOF behavior)
- `src/homelab_mcp/ssh_connection.py` — TOFUSSHClient full implementation, `_tofu_lock` dead code, `_store_host_key` key export and write path
- `src/homelab_mcp/ssh_tools.py` — `resolve_ssh_credentials()` four-tier priority chain, bare-miss fallthrough path (lines 36-131)
- `src/homelab_mcp/shell_session.py` — `create_process` call with inverted `term_size=(24, 80)` at line 109
- `src/homelab_mcp/http_app.py` — WebSocket `read_output` blocking loop, lines 189-202
- `src/homelab_mcp/credential_store.py` — `store_credential`, `register_credential`; confirms no `ssh_connect` call in the `credentials add` path
- `src/homelab_mcp/tool_schemas/ssh_tools_schema.py` — current description strings for `start_interactive_shell`, `ssh_discover`, `ssh_execute_command`
- `src/homelab_mcp/tool_handlers/ssh_handlers.py` — `handle_ssh_discover`, `handle_start_interactive_shell` response construction
- `uv.lock` — asyncssh 2.21.0, mcp 1.9.4, starlette 0.47.1, websockets 16.0 confirmed at locked versions

### Secondary (MEDIUM confidence)

- asyncssh documentation patterns — `known_hosts` + `client_factory` dual-validation behavior; `validate_host_public_key` synchronous-only constraint (corroborated by source inspection)
- Python `threading.Lock` documentation — safe to acquire from synchronous callbacks called within asyncio coroutines (standard library, HIGH confidence on the pattern itself)

---
*Research completed: 2026-03-13*
*Ready for roadmap: yes*
