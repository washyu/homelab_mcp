# Feature Research

**Domain:** Bug fixes for interactive shell, SSH credential flow, and TOFU known_hosts — homelab MCP server real-world reliability
**Researched:** 2026-03-13
**Confidence:** HIGH (all three bugs diagnosed from direct codebase inspection — shell_session.py, ssh_tools.py, ssh_connection.py, credential_store.py, tool_schemas/ssh_tools_schema.py)

---

## Context: What Already Exists (v1.3 baseline)

Relevant to v1.4 scope only:

- **`start_interactive_shell` tool** in `ssh_handlers.py` — creates a `ShellSession` (asyncssh PTY), stores it in `ShellSessionManager`, returns a JSON blob containing a `shell_url` like `http://localhost:8080/shell/{session_id}`. The URL is browser-only. An MCP agent receives the URL but cannot open a browser; it reports success but the user gets nothing actionable in their chat context.
- **`register_server` tool** — writes hostname + username + key_path to the DB `ssh_credentials` table. Does NOT accept a password. Calls `ssh_connect` with the key path during `verify_connection=True`, which triggers TOFU host key storage in `~/.homelab_mcp/known_hosts`.
- **`credentials add` CLI** — writes username + password to OS keyring. Also calls `register_credential()` to add hostname to the JSON registry (`credential_registry.json`). Does NOT call `ssh_connect`; does NOT trigger TOFU.
- **`resolve_ssh_credentials()`** in `ssh_tools.py` — three-tier chain: (1) explicit args, (2) OS keyring via `list_credentials` + `get_credential`, (3) DB `ssh_credentials` table. Priority 2 and 3 are mutually exclusive per lookup but can coexist in storage.
- **`ssh_connect()`** in `ssh_connection.py` — always uses `known_hosts=str(kh_path)` where `kh_path` defaults to `~/.homelab_mcp/known_hosts`. Uses `TOFUSSHClient` as `client_factory`, which stores new host keys on first connection.
- **TOFU path**: `TOFUSSHClient.validate_host_public_key()` is called by asyncssh only when the connecting host is NOT already in the `known_hosts` file. If the host IS in `known_hosts`, asyncssh validates directly — `TOFUSSHClient` is bypassed.
- **Tool schema descriptions** — `ssh_discover` and `ssh_execute_command` say "Omit [credentials] if credentials were stored with `credentials add` — they are auto-injected." `start_interactive_shell` says "SSH username (optional, uses registered credentials if available)." No description explains what to do when credentials are missing.

---

## The Three Bugs — Root Cause Analysis

### Bug 1: Interactive Shell Returns Nothing Actionable

**What the agent does today:**
1. Agent calls `start_interactive_shell(hostname="192.168.1.10")`
2. Tool creates an asyncssh PTY session and returns: `{"status": "success", "shell_url": "http://localhost:8080/shell/abc123", ...}`
3. Agent reads this response and reports "Interactive shell started at http://localhost:8080/shell/abc123"
4. User sees a URL. In most MCP clients (Claude Desktop, etc.), there is no browser to open it. Nothing happened.

**Why it's silent failure:** The tool returns `status: success` — from the agent's perspective the operation succeeded. There is no error. The agent has no way to know the user can't interact with the URL.

**What should happen instead:** The tool should either (a) make the shell useful within the MCP protocol context — executing a command and returning its output — or (b) return an explicit explanation that this requires a browser with a WebSocket connection, and surface the limitation clearly in the tool schema and response so the agent guides the user correctly.

---

### Bug 2: SSH Credential Flow Is Invisible to the Agent

**What the agent does today:**
1. Agent calls `ssh_discover(hostname="192.168.1.10")` with no credentials.
2. `resolve_ssh_credentials()` checks keyring (empty), checks DB (empty), falls back to mcp_admin key.
3. If `~/.ssh/mcp/mcp_admin_key` doesn't exist, returns `SSHCredentials` with no auth.
4. `ssh_discover_system()` raises `ValueError("No credentials found for 192.168.1.10. Store them with credentials add...")`.
5. Agent sees an error, but doesn't know the right recovery workflow: which tool to use first, whether to use `register_server` or `credentials add`, and in what order.

**The credential path confusion:** There are two distinct storage mechanisms that coexist:
- **Keyring path** (`credentials add`): Stores password in OS keyring + hostname in JSON registry. No DB write. Best for password-auth SSH.
- **DB path** (`register_server`): Stores hostname + username + key_path in SQLite. No keyring write. Best for key-auth SSH (especially `mcp_admin` after `setup_mcp_admin`).

The agent has no tool or schema text that describes this distinction or the correct workflow. The tool descriptions for `ssh_discover` and `ssh_execute_command` say "omit credentials if stored with `credentials add`" — but they don't say what to do when credentials aren't stored, or that `register_server` is the alternative.

**What should happen instead:** When an SSH tool fails due to missing credentials, the error response should tell the agent the exact recovery steps. Tool schema descriptions should document the two paths and guide the agent to call `list_registered_servers` or `list_credentials` (a new tool) to diagnose the state before attempting SSH.

---

### Bug 3: TOFU Known_Hosts Not Populated for Keyring-Only Hosts

**What happens today:**
1. User runs `homelab-mcp credentials add 192.168.1.10 root hunter2` → writes to keyring + JSON registry. No SSH connection made. `known_hosts` unchanged.
2. Agent calls `ssh_discover(hostname="192.168.1.10")` → `resolve_ssh_credentials()` finds keyring entry → calls `ssh_connect(hostname="192.168.1.10", password="hunter2")`.
3. `ssh_connect` reads `known_hosts` → host not found → asyncssh calls `TOFUSSHClient.validate_host_public_key()`.
4. **Expected behavior:** TOFU accepts and stores key. First connection succeeds.
5. **Actual behavior during Mac testing:** SSH times out or fails. The known_hosts file isn't populated.

**Why it times out (hypothesis based on asyncssh behavior):** When `known_hosts=str(kh_path)` is passed and the file is empty (or the host isn't present), asyncssh may not call `validate_host_public_key()` at all for hosts in non-standard formats. Alternatively, the `TOFUSSHClient` factory may not be invoked correctly when asyncssh finds a `known_hosts` file path (as opposed to no `known_hosts`). The TOFU path was tested with `register_server` (which uses `verify_connection=True`), not with the keyring-first path. The keyring path was added in v1.3 but was not exercised against a real host.

**The real root cause:** `register_server(verify_connection=True)` calls `ssh_connect()` which triggers TOFU. The DB credential path inherently exercises TOFU. The keyring path (`credentials add`) skips `ssh_connect` entirely. If a user only uses `credentials add` and never calls `register_server`, no TOFU occurs, and the first real `ssh_discover` call either triggers TOFU (and works) or fails with a timeout depending on asyncssh's exact behavior when `known_hosts` is present but empty vs missing.

**What should happen instead:** Either (a) `credentials add` should trigger a connection probe to populate known_hosts, or (b) the first SSH connection attempt should handle a failed TOFU gracefully with a clear error telling the agent to call a dedicated "trust this host" tool, or (c) `ssh_connect` should be verified to correctly trigger TOFU when `known_hosts` is present but doesn't contain the host.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features required to make the three bugs non-issues. Missing these = bugs persist or errors are cryptic.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Interactive shell tool returns actionable output | An MCP tool that returns "open this URL" is not useful inside a chat interface. Either the tool executes a command and returns output, or it clearly tells the agent and user what action is needed. | MEDIUM | The fix is a schema description change + response content change. The WebSocket server can stay; the tool should acknowledge its browser-only limitation and explain next steps. |
| SSH credential error tells agent the recovery workflow | Every SSH tool should return a structured, actionable error when credentials are missing. "No credentials found" is not enough — the error must name the correct tool and the correct parameter order. | LOW | Change the `ValueError` message in `ssh_discover_system()` and `ssh_execute_command()` (and the general `resolve_ssh_credentials()` fallback path) to include: "1. Call `register_server(hostname=...)` to register a key-auth device. 2. Or run `homelab-mcp credentials add <host> <user> <pass>` to store a password." |
| Agent-facing credential workflow in tool schema descriptions | `ssh_discover` and `ssh_execute_command` schema descriptions say "omit credentials if stored" but don't tell the agent what to do when credentials are missing. | LOW | Add one sentence: "If credentials are missing, call `list_registered_servers` to check registered key-auth servers, or use `credentials add` CLI for password auth." |
| TOFU works on first SSH connection for keyring-registered hosts | A host added via `credentials add` must successfully connect on the first `ssh_discover` call. Today there is a timeout bug in this path. | MEDIUM | Root cause must be verified (empty `known_hosts` + asyncssh behavior). Fix is either: ensure `known_hosts` file doesn't exist (so asyncssh uses TOFU correctly) OR remove `known_hosts=` param to let asyncssh handle new hosts OR add a dedicated "trust host" step. |
| `list_keyring_credentials` tool (or equivalent) | The agent needs a tool to inspect what credentials are in the keyring registry — analogous to `list_registered_servers` for the DB path. Today there is no MCP tool that calls `list_credentials()` from `credential_store.py`. The agent has no way to diagnose credential state. | LOW | New tool `list_keyring_credentials` that calls `credential_store.list_credentials("ssh")` and returns the result. No passwords returned. One handler function, one schema entry. |

### Differentiators (Competitive Advantage)

Features beyond bug fixes that improve reliability and agent guidance.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| SSH credential flow prompt template | A `MCP Prompt` named `ssh_credential_setup` that walks the agent through the correct setup sequence: check existing credentials → decide keyring vs register_server path → confirm TOFU on first connect. Analogous to `decommission_device_workflow`. | MEDIUM | Adds a 4th prompt to `prompt_registry.py`. The template should branch on whether the user is doing password auth vs key auth. |
| Interactive shell tool description explains browser requirement | Schema description for `start_interactive_shell` should say: "Returns a browser URL — this tool is intended for human use in a browser, not for AI-initiated commands. For AI-driven command execution use `ssh_execute_command` instead." | LOW | Pure description change — prevents agent from calling the wrong tool. |
| `trust_host_key` tool for explicit TOFU | A dedicated tool that connects to a host and forces TOFU acceptance, independent of any credential lookup. Allows the agent to say "establish trust with this host first" before the first SSH command. | MEDIUM | Thin wrapper around `ssh_connect` that accepts and stores the key then closes. Handles the chicken-and-egg problem where TOFU must happen before `ssh_discover` can run. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Remove `start_interactive_shell` entirely | "It doesn't work in the chat interface" | The browser-based shell is genuinely useful for humans — just not from within an AI tool call. It should stay but its description must be honest about requiring a browser. | Update schema description to say it's browser-only; tool stays for human-initiated browser use. |
| Merge `register_server` and `credentials add` into one tool | "Two credential paths is confusing" | They serve different auth mechanisms: DB path = key auth (no password), keyring path = password auth. Merging would require storing passwords in DB (security regression) or keys in keyring (wrong abstraction). | Keep both; fix agent guidance to explain when to use each. |
| Auto-discover and store all hosts on network scan | "Pre-populate known_hosts" | Network scan hits devices that may not be SSH targets. Storing host keys speculatively creates false trust. | TOFU on first actual connection attempt is the correct model. |
| Disable TOFU / use `known_hosts=None` globally | "Simpler, avoids the bug" | Disabling host key verification opens MITM attacks on all SSH operations. This is a homelab but the SSH sessions run privileged commands. | Fix TOFU for the keyring path specifically; keep verification enforced. |

---

## Credential + TOFU Workflow — Correct Sequences

This is the authoritative workflow the agent should follow. All fixes must guide toward this.

### Sequence A: Password-auth SSH (user has username + password)

```
1. User: "I want to SSH into 192.168.1.10 as root with password hunter2"
2. Agent: Run `homelab-mcp credentials add 192.168.1.10 root hunter2` (CLI — cannot be done from MCP tool)
   → Writes to OS keyring + JSON registry. No SSH connection yet.
3. Agent: Call `ssh_discover(hostname="192.168.1.10")`
   → resolve_ssh_credentials() finds keyring entry → calls ssh_connect()
   → TOFU fires on first connect (host key stored) → discovery proceeds
   → [BUG: today this may timeout if TOFU doesn't fire correctly]
4. Agent: Subsequent calls to ssh_execute_command / ssh_discover work without credentials.
```

**Agent guidance needed:** The agent should know that `credentials add` is a CLI command, not an MCP tool. It cannot call it directly. It should instruct the user to run it, then retry.

### Sequence B: Key-auth SSH (mcp_admin workflow)

```
1. User: "Set up mcp_admin on 192.168.1.10"
2. Agent: Call `setup_mcp_admin(hostname="192.168.1.10", username="root", password="hunter2")`
   → Connects with root credentials → creates mcp_admin → installs public key
   → TOFU fires during this connection
3. Agent: Call `register_server(hostname="192.168.1.10", username="mcp_admin")`
   → verify_connection=True by default → calls ssh_connect with mcp_admin key
   → If TOFU already fired in step 2, this validates against stored key (no re-TOFU)
   → Saves to DB
4. Agent: All future ssh_discover/ssh_execute_command calls use DB mcp_admin entry.
```

**Current problem:** The agent doesn't know to call `register_server` after `setup_mcp_admin`. It's not in any prompt or schema description.

### Sequence C: First SSH call fails with no credentials (most common agent confusion)

```
Today:
1. Agent: Call ssh_discover(hostname="192.168.1.10")
2. Error: "No credentials found for 192.168.1.10. Store them with `credentials add`..."
3. Agent: ??? (doesn't know if keyring or DB or what to ask the user)

After fix:
1. Agent: Call ssh_discover(hostname="192.168.1.10")
2. Error: "No credentials found for 192.168.1.10.
   For key-auth (mcp_admin): call setup_mcp_admin then register_server.
   For password-auth: ask user to run: homelab-mcp credentials add 192.168.1.10 <user> <password>
   Then call list_registered_servers or list_keyring_credentials to verify before retrying."
3. Agent: Can decide path based on available information and ask user the right question.
```

---

## Feature Dependencies

```
[Fix interactive shell — schema + response]
    └──modifies──> [tool_schemas/ssh_tools_schema.py start_interactive_shell description]
    └──modifies──> [tool_handlers/ssh_handlers.py handle_start_interactive_shell response text]
    └──independent-of──> [credential fixes] (different code path)

[Fix SSH credential error messages]
    └──modifies──> [ssh_tools.py ssh_discover_system() ValueError text]
    └──modifies──> [ssh_tools.py ssh_execute_command() error path]
    └──requires──> [list_keyring_credentials tool] (error message references it)

[list_keyring_credentials tool]
    └──requires──> [credential_store.list_credentials("ssh")] (already exists — just needs MCP exposure)
    └──adds──> [tool_schemas/credential_tools_schema.py new entry]
    └──adds──> [tool_handlers/credential_handlers.py new handler]
    └──adds──> [tool_handlers/__init__.py registration]
    └──independent-of──> [TOFU fix]

[Fix TOFU for keyring path]
    └──modifies──> [ssh_connection.py ssh_connect()] (verify TOFU fires correctly with non-empty empty known_hosts)
    └──requires-investigation──> [asyncssh behavior with known_hosts file present but host absent]
    └──may-require──> [trust_host_key tool] if TOFU can't be fixed transparently

[trust_host_key tool] (differentiator, only if TOFU transparent fix is insufficient)
    └──adds──> [tool_schemas/ssh_tools_schema.py new entry]
    └──adds──> [tool_handlers/ssh_handlers.py new handler]
    └──uses──> [ssh_connection.ssh_connect()] (existing)

[SSH credential flow prompt]
    └──adds──> [prompt_registry.py new prompt entry]
    └──independent-of──> [code fixes] (purely additive)
    └──benefits-from──> [list_keyring_credentials tool being available]
```

---

## MVP Definition

### Must Fix (v1.4 — blocking real-world use)

- [ ] **Interactive shell — honest schema description**: Change `start_interactive_shell` description to state it opens a browser-based terminal. Add explicit note: "Use `ssh_execute_command` for AI-driven command execution." Add to response: "Open this URL in a browser to access the interactive shell."
- [ ] **Interactive shell — no silent success**: Response should include a field `requires_browser: true` and a `note` explaining the agent cannot interact with this session. The agent must not report "task complete" when it can't verify interaction.
- [ ] **SSH credential error — actionable recovery**: `ssh_discover_system()` and `ssh_execute_command()` must return errors that name the exact recovery steps (both paths: CLI `credentials add` for passwords; `register_server` for mcp_admin key auth).
- [ ] **`list_keyring_credentials` tool**: New MCP tool that calls `credential_store.list_credentials("ssh")` and returns hostname + username list (no passwords). Enables agent to inspect keyring state without going blind.
- [ ] **TOFU fix for keyring path**: Investigate and fix why `ssh_connect()` with an existing (but host-absent) `known_hosts` file fails to trigger TOFU correctly on Mac. This is the core timeout bug. Fix must be verified with a real SSH connection test.

### Should Add (v1.4 — high value, low cost)

- [ ] **SSH tools schema: credential guidance sentence**: Each SSH tool description that says "omit if stored" should add: "If no credentials are stored, check state with `list_registered_servers` (key auth) or `list_keyring_credentials` (password auth)."
- [ ] **`register_server` description mentions TOFU**: Schema description should say "Registers the server and stores its SSH host key for future connections."

### Add After Validation (v1.x)

- [ ] `trust_host_key` tool — only needed if TOFU transparent fix is insufficient or users want explicit "verify this host" step
- [ ] `ssh_credential_setup` prompt — walkthrough template for the credential setup sequence
- [ ] `credentials verify <host>` CLI command — test connectivity with stored credentials

### Out of Scope (v1.4)

- [ ] Merge `register_server` and `credentials add` into a single flow — requires design work, not a bug fix
- [ ] Persistent browser UI for interactive shell — out of scope per PROJECT.md
- [ ] Auto-TOFU for all hosts on network scan

---

## Feature Prioritization Matrix

| Feature | User/Agent Value | Implementation Cost | Priority |
|---------|-----------------|---------------------|----------|
| Interactive shell — honest description + response | HIGH (stops false "success" reports) | LOW | P1 |
| SSH credential error — actionable recovery text | HIGH (agent can recover without confusion) | LOW | P1 |
| `list_keyring_credentials` tool | HIGH (closes the diagnostic gap) | LOW | P1 |
| TOFU fix for keyring path | HIGH (eliminates real SSH timeout bug) | MEDIUM (requires asyncssh investigation) | P1 |
| SSH tool schema: credential guidance sentence | MEDIUM (improves proactive guidance) | LOW | P1 |
| `register_server` description mentions TOFU | LOW (informational) | LOW | P2 |
| `trust_host_key` tool | MEDIUM (belt-and-suspenders for TOFU) | MEDIUM | P2 (defer if TOFU fix works) |
| `ssh_credential_setup` prompt | MEDIUM (end-to-end workflow guidance) | MEDIUM | P2 |

---

## Competitor / Analogous Tool Reference

| Dimension | OpenSSH `ssh` CLI | Ansible | Our Approach (post-fix) |
|-----------|-------------------|---------|------------------------|
| First connection to unknown host | Interactive prompt: "Are you sure you want to continue connecting?" | `host_key_checking=False` default or TOFU via `StrictHostKeyChecking=accept-new` | TOFU transparent — first connect stores key, agent not interrupted |
| Missing credentials | `Permission denied (publickey,password)` — tells you what was tried | Task fails with `Failed to connect to the host via ssh` — shows what auth methods failed | Error message names exact recovery tools and CLI commands |
| Credential inventory | `~/.ssh/config` is human-readable; `ssh-add -l` lists loaded keys | `ansible-vault` for secrets, inventory files for hosts | Two-path: `list_registered_servers` (DB/key) + `list_keyring_credentials` (keyring/password) |
| Browser shell | N/A | N/A | `start_interactive_shell` with explicit browser-required language |

---

## Sources

- Codebase inspection (HIGH confidence):
  - `src/homelab_mcp/shell_session.py` — `ShellSessionManager.create_session()` return type; `handle_start_interactive_shell` builds `shell_url` string
  - `src/homelab_mcp/ssh_tools.py` — `resolve_ssh_credentials()` tier logic; `ssh_discover_system()` ValueError raise; `register_server()` `verify_connection=True` path calls `ssh_connect()`
  - `src/homelab_mcp/ssh_connection.py` — `ssh_connect()` passes `known_hosts=str(kh_path)`; `TOFUSSHClient` as `client_factory`; `validate_host_public_key()` called only when host NOT in file
  - `src/homelab_mcp/credential_store.py` — `store_credential()` writes to keyring only; `register_credential()` writes to JSON registry; no `ssh_connect()` call
  - `src/homelab_mcp/tool_schemas/ssh_tools_schema.py` — current descriptions for `start_interactive_shell`, `ssh_discover`, `ssh_execute_command`
  - `src/homelab_mcp/tool_schemas/credential_tools_schema.py` — `register_server` has no description about TOFU
  - `src/homelab_mcp/tool_handlers/credential_handlers.py` — no `list_keyring_credentials` handler exists
  - `src/homelab_mcp/prompt_registry.py` — no SSH setup prompt exists
- asyncssh docs: `known_hosts` parameter behavior — when file is present, asyncssh validates against it; `validate_host_public_key` is called ONLY for hosts not found in the file; an empty file should trigger TOFU on all connections (LOW confidence — needs verification in TOFU bug investigation)
- PROJECT.md milestone context — v1.4 goal: fix interactive shell, SSH credential flow, TOFU known_hosts

---

*Feature research for: homelab-mcp v1.4 — real-world reliability bug fixes*
*Researched: 2026-03-13*
