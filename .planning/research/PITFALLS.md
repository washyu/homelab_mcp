# Domain Pitfalls

**Domain:** Infrastructure management MCP server (SSH/Proxmox homelab automation)
**Researched:** 2026-03-08
**Confidence:** HIGH (based on codebase analysis + established infrastructure security patterns)

## Critical Pitfalls

Mistakes that cause security incidents, data loss, or require rewrites.

### Pitfall 1: Shipping Disabled Host Key Verification as "Fixable Later"

**What goes wrong:** The 19 instances of `known_hosts=None` across `ssh_tools.py`, `vm_operations.py`, `infrastructure_crud.py`, and `shell_session.py` mean every SSH connection is vulnerable to man-in-the-middle attacks. Teams often plan to "fix it after launch" but the fix requires a known_hosts management strategy that touches every SSH callsite. If users adopt with verification disabled, enabling it later is a breaking change (their connections start failing because host keys were never collected).

**Why it happens:** During development, `known_hosts=None` removes friction. asyncssh's default behavior is to reject unknown hosts, which blocks iteration. The pattern spreads because developers copy working connection code.

**Consequences:**
- MITM attacks on the homelab network (attacker can intercept SSH sessions the AI uses to manage infrastructure)
- Users trust tool output that may have been tampered with
- Enabling verification post-1.0 breaks every existing installation
- CVE-worthy if the project gains visibility

**Prevention:**
1. Implement a known_hosts file manager as the FIRST hardening task (before other fixes)
2. On first connection to a host, record the host key (trust-on-first-use / TOFU model)
3. On subsequent connections, verify against stored key and REJECT on mismatch
4. Provide a `--trust-new-hosts` flag for initial setup, not as a permanent default
5. Create a single `get_ssh_connection(hostname, ...)` function that ALL modules use -- eliminate the 19 independent connection sites

**Detection:** `grep -r "known_hosts=None" src/` should return zero results before 1.0 ships.

**Phase:** Must be Phase 1 (Security Hardening). This is the single highest-risk item in the codebase.

---

### Pitfall 2: Silent Exception Swallowing Masks Infrastructure Failures

**What goes wrong:** The 9 instances of bare `except: pass` or `except SomeError: pass` across `migration.py`, `http_transport.py`, `database.py`, `ssh_tools.py`, `sitemap.py`, and `service_installer.py` mean infrastructure operations can fail silently. When an AI assistant calls a tool and gets no error, it reports success to the user. The user believes their infrastructure was configured correctly when it was not.

**Why it happens:** During prototyping, silent catches prevent crashes. Some are intentional fallbacks (JSON parse errors in hardware detection where you try one format then fall back). The problem is distinguishing "acceptable fallback" from "swallowed infrastructure failure."

**Consequences:**
- AI reports "deployment succeeded" when it partially failed
- Sitemap data becomes stale/wrong (devices not updated after config changes due to stub `_update_sitemap_after_deployment`)
- Users make decisions based on stale device information
- Debugging becomes nearly impossible ("it just stopped working")

**Prevention:**
1. Audit each of the 9 silent handlers and categorize: intentional fallback vs. swallowed error
2. Intentional fallbacks: add `logger.debug()` with context
3. Swallowed errors: convert to `logger.error()` and propagate to tool response
4. Establish a rule: infrastructure-mutating operations must NEVER silently swallow exceptions

**Detection:** `grep -rn "except.*:\s*$" src/ | grep -A1 "pass"` should show only JSON parse fallbacks, never infrastructure operations.

**Phase:** Phase 1 (Security Hardening) -- silent failures in infrastructure tools are a safety issue.

---

### Pitfall 3: Stub Functions Called in Production Paths

**What goes wrong:** Three functions are called in real execution paths but do nothing:
- `_update_sitemap_after_deployment()` -- called after every deployment, body is `pass`
- `_rediscover_device_after_config()` -- called after config changes, body is `pass`
- `_install_with_script()` -- returns error string instead of functioning

The first two are worse than missing features: they create the illusion of functionality. The deployment succeeds, the stub is called, no error is raised, but the sitemap is now wrong.

**Why it happens:** Stubs are scaffolded during architecture phase with the intent to implement later. They get forgotten because they do not cause test failures (there is nothing to test) and do not cause runtime errors (they just silently do nothing).

**Consequences:**
- Sitemap diverges from reality after every deployment
- AI assistant gives incorrect information about infrastructure state
- Users cannot trust device inventory data
- Script-based installation silently fails, users must use Terraform/Ansible even when inappropriate

**Prevention:**
1. Implement the two sitemap stubs before shipping -- they are not optional features, they are data integrity requirements
2. Either implement `_install_with_script()` or remove the code path entirely and document that only Terraform and Ansible are supported
3. Add a pre-release check: `grep -rn "^\s*pass$" src/ --include="*.py"` and verify every hit is either an abstract method or an exception class body

**Detection:** Any function whose body is just `pass` that is NOT an abstract method or exception class is a bug.

**Phase:** Phase 2 (Stub Implementation). Depends on Phase 1 SSH fixes since stubs need working SSH connections.

---

### Pitfall 4: Command Injection Through Unvalidated Tool Arguments

**What goes wrong:** Tool arguments come from an AI model, which in turn gets them from user natural language. The `service_installer.py` uses `subprocess.run()` with arguments that include user-provided values (playbook paths, variable names). SSH commands are constructed from tool arguments and executed on remote hosts. If any of these paths pass unsanitized user input to shell commands, it is a command injection vulnerability.

**Why it happens:** MCP servers have an unusual trust model -- the input comes from an AI, so developers assume it is "safe." But the AI is reflecting user intent, and prompt injection or malicious user input can produce hostile tool arguments. The JSON schema validation checks types but not semantic content (no validation of hostnames, IP addresses, or path traversals).

**Consequences:**
- Arbitrary command execution on managed infrastructure
- Data exfiltration from homelab devices
- Lateral movement across the network
- Particularly dangerous because this tool runs with SSH access to infrastructure

**Prevention:**
1. Validate all hostnames against a regex: `^[a-zA-Z0-9][a-zA-Z0-9.-]*$`
2. Validate IP addresses with `ipaddress.ip_address()` from stdlib
3. Validate port ranges: 1-65535
4. Path arguments: resolve and check they stay within expected directories (no `../` traversal)
5. Never pass tool arguments directly into shell commands -- use parameterized approaches
6. The `subprocess.run()` in `service_installer.py` already uses list form (good), but verify `extra_vars` JSON cannot inject Ansible flags

**Detection:** Search for string formatting in subprocess calls and SSH command construction. Any f-string or `.format()` that includes tool arguments adjacent to shell metacharacters is suspect.

**Phase:** Phase 1 (Security Hardening). Input validation is a prerequisite for safe operation.

---

### Pitfall 5: HTTP Transport Binding to 0.0.0.0 With Weak Auth Defaults

**What goes wrong:** `config.py` defaults `MCP_HTTP_HOST` to `"0.0.0.0"` and while auth is enabled by default, the API key comes from an environment variable that may not be set in development. The `validate_api_key_strength()` function exists but is not called by default (`auth.py:141-155`). This means the HTTP transport can be exposed to the network with a weak or missing API key.

**Why it happens:** Binding to `0.0.0.0` is convenient for development and necessary for containerized deployments. The auth validation exists but was not wired into the startup path.

**Consequences:**
- Anyone on the network can call MCP tools (SSH into your infrastructure, deploy services, modify configs)
- Homelab networks often have IoT devices, guests, or other less-trusted hosts
- A single compromised device on the LAN gets full infrastructure management capability

**Prevention:**
1. Default `MCP_HTTP_HOST` to `127.0.0.1` (localhost only)
2. Call `validate_api_key_strength()` during startup, refuse to start HTTP transport with weak keys
3. Log a clear warning when binding to non-localhost addresses
4. Document the security implications of network-accessible HTTP transport

**Detection:** Check that startup validates auth configuration before accepting connections.

**Phase:** Phase 1 (Security Hardening).

## Moderate Pitfalls

### Pitfall 6: New aiohttp Session Per Proxmox API Request

**What goes wrong:** `proxmox_api.py` creates a new `aiohttp.ClientSession` with a new `TCPConnector` for every API call. This means no connection reuse, no TCP keepalive, and a new TLS handshake for every request. Under load (e.g., polling VM status, listing nodes), this creates excessive overhead and can exhaust file descriptors.

**Prevention:**
1. Create the `ClientSession` once in `__init__` or on first use
2. Store as instance variable, reuse across requests
3. Implement proper cleanup with `async with` or explicit `close()` in a shutdown hook
4. Add connection pool size limits appropriate for homelab (5-10 connections is plenty)

**Detection:** Search for `ClientSession(` -- it should appear once (initialization), not in every method.

**Phase:** Phase 3 (Performance/Polish). Not a correctness issue but causes reliability problems under sustained use.

---

### Pitfall 7: Database Connection Churn in SSH Credential Lookups

**What goes wrong:** `ssh_tools.py` opens, queries, and closes a database connection for every credential lookup. Since credential resolution happens for every SSH operation, and SSH operations are the core of this tool, this means constant database churn. With SQLite this is tolerable but creates lock contention if multiple async operations run concurrently.

**Prevention:**
1. Use a connection pool or persistent connection for the database adapter
2. For SQLite specifically, use WAL mode to allow concurrent reads
3. Cache frequently-accessed credentials in memory with a TTL

**Detection:** Profile database open/close operations during a multi-device discovery scan.

**Phase:** Phase 3 (Performance/Polish).

---

### Pitfall 8: Hardcoded `mcp_admin` Username Assumption

**What goes wrong:** `infrastructure_crud.py:27` hardcodes `"username": "mcp_admin"` when resolving SSH connections for devices. While the credential resolution system supports multiple usernames, the infrastructure manager bypasses it. Users who set up SSH access with a different username will find infrastructure operations fail while direct SSH tools work.

**Prevention:**
1. Always use the credential resolution system (`resolve_ssh_credentials`) instead of hardcoding usernames
2. If `mcp_admin` is the recommended default, document it clearly but do not require it
3. Test with non-default usernames in integration tests

**Detection:** `grep -r "mcp_admin" src/` -- should only appear in credential defaults and documentation, not hardcoded in connection logic.

**Phase:** Phase 2 (Stub Implementation / Functional Completeness).

---

### Pitfall 9: 45-Second Global Timeout for All Tool Operations

**What goes wrong:** `tools.py` wraps all tool execution with `@timeout_wrapper(timeout_seconds=45.0)`. This is a single timeout for wildly different operations: listing credentials (milliseconds), discovering a device via SSH (5-30 seconds), deploying infrastructure (potentially minutes). Long-running operations will be killed, returning a timeout error to the AI, which may interpret this as a failure and retry -- potentially creating duplicate deployments.

**Prevention:**
1. Define per-tool-category timeouts: fast queries (10s), SSH operations (60s), deployments (300s)
2. For long-running operations, implement a job/task pattern: start operation, return job ID, poll for completion
3. Make timeouts configurable per tool in the schema

**Detection:** Test deployment operations against real infrastructure and verify they complete within timeout.

**Phase:** Phase 2 or 3. Not a security issue but causes functional failures for legitimate operations.

---

### Pitfall 10: No Graceful Shutdown / Resource Cleanup

**What goes wrong:** Shell sessions are in-memory (`ShellSession` objects in `ShellSessionManager.sessions` dict). SSH connections held by active sessions are not cleaned up on server shutdown. The cleanup loop only handles expired sessions, not server termination. aiohttp sessions (when pooled) need explicit cleanup. SQLite connections need closing.

**Prevention:**
1. Implement signal handlers (SIGTERM, SIGINT) that trigger graceful shutdown
2. Close all active SSH connections in sessions
3. Close database connections
4. Close aiohttp client sessions
5. Log shutdown activity so users know cleanup happened

**Detection:** Kill the server process and check for leaked SSH connections on target hosts (`ss -tnp | grep ssh`).

**Phase:** Phase 3 (Performance/Polish).

## Minor Pitfalls

### Pitfall 11: Service Template Path Hardcoding

**What goes wrong:** `service_installer.py` loads YAML service templates from a hardcoded directory path relative to the package. When installed via different methods (editable install, system install, container), the path may not resolve correctly.

**Prevention:** Use `importlib.resources` or `__file__`-relative paths with proper `Path` resolution. Test template loading from an installed (non-editable) package.

**Phase:** Phase 4 (Distribution/Packaging).

---

### Pitfall 12: Proxmox API Token Format Not Validated

**What goes wrong:** The `ProxmoxAPIClient` accepts `api_token` as a string but does not validate the expected format (`user@realm!tokenid=secret`). A malformed token results in cryptic auth failures rather than a clear error message.

**Prevention:** Validate token format on client initialization with a regex check. Provide a clear error message showing the expected format.

**Phase:** Phase 2 (Functional Completeness).

---

### Pitfall 13: Hardware Detection Parsing Fragility

**What goes wrong:** SSH-based hardware detection in `ssh_tools.py` parses command output (lsblk JSON, /proc/cpuinfo, etc.) from remote hosts. Different Linux distributions, kernel versions, and tool versions produce subtly different output formats. The JSON parse fallbacks (`except json.JSONDecodeError: pass`) silently lose data when the format is unexpected.

**Prevention:**
1. Test hardware detection against multiple distros (Ubuntu, Debian, Rocky, Alpine -- common in Proxmox LXC)
2. Log when fallback parsing is used so users know data may be incomplete
3. Return partial results with a "completeness" indicator rather than silently dropping fields

**Phase:** Phase 2 (Functional Completeness). Important for reliability but not a security issue.

---

### Pitfall 14: Missing Rate Limiting on SSH Operations

**What goes wrong:** An AI assistant that encounters an error may retry aggressively. With no rate limiting on SSH operations, rapid retries can trigger fail2ban or similar intrusion detection on target hosts, locking out the MCP admin account. This is particularly insidious because the tool that was supposed to manage the infrastructure causes it to become inaccessible.

**Prevention:**
1. Implement per-host rate limiting for SSH connections (max 3 concurrent, max 10/minute)
2. Add exponential backoff on connection failures
3. The retry decorator in `error_handling.py` already exists -- verify it has reasonable backoff

**Phase:** Phase 3 (Performance/Polish).

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Security Hardening | Breaking existing installations when enabling host key verification | Use TOFU model: auto-accept on first connect, reject on mismatch. Provide migration tool to populate known_hosts from current connections. |
| Security Hardening | Over-securing to the point of unusability | Keep defaults secure but provide clear escape hatches. Document how to disable verification for specific hosts if needed. |
| Stub Implementation | Implementing stubs that silently fail under edge cases | Write integration tests against real Proxmox before considering stubs "done." |
| Stub Implementation | Sitemap update logic creating inconsistencies if deployment partially succeeds | Implement idempotent sitemap updates -- running the update twice should produce the same result. |
| Performance | Connection pool exhaustion under concurrent tool calls | Set pool limits appropriate for homelab (5-10 connections), queue excess requests rather than failing. |
| Performance | Breaking existing timeout behavior when changing to per-tool timeouts | Keep 45s as the default, only override for specific tool categories. |
| Documentation | Assuming users will read docs before running | Make `uv sync && uv run python run_server.py` work with zero configuration. Fail loudly with actionable errors when config is needed. |
| Distribution | Different behavior between `uv run` and installed package | Test the actual distribution path (clone, sync, run) on a clean system before tagging 1.0. |

## Sources

- Direct codebase analysis of `/home/shaun/projects/mcp_python_server/src/`
- asyncssh documentation on known_hosts handling (training data, MEDIUM confidence)
- OWASP command injection prevention guidelines (training data, HIGH confidence -- established patterns)
- aiohttp ClientSession best practices (training data, HIGH confidence -- well-documented pattern)
- General infrastructure automation security patterns (Ansible, Terraform security hardening guides -- training data, MEDIUM confidence)
