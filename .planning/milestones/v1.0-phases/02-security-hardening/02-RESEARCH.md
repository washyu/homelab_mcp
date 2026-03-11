# Phase 2: Security Hardening - Research

**Researched:** 2026-03-09
**Domain:** SSH host key verification, SSL/TLS certificate validation, input validation, credential sanitization
**Confidence:** HIGH

## Summary

Phase 2 addresses four security gaps in the current codebase. The most critical finding is that **every SSH connection in the codebase sets `known_hosts=None`**, completely disabling host key verification across 20+ call sites in `ssh_tools.py`, `vm_operations.py`, `infrastructure_crud.py`, and `shell_session.py`. Similarly, the Proxmox API client defaults `verify_ssl=False` and the `get_proxmox_client()` factory reads `PROXMOX_VERIFY_SSL` with a default of `"false"`. Neither of these issues requires new libraries -- asyncssh 2.21.0 (already installed) has full known_hosts and TOFU support, and aiohttp's `ssl` parameter already supports both `True` (default cert verification) and custom `ssl.SSLContext` for self-signed certs.

Input validation is currently absent at the application level -- tool schemas define JSON Schema types but hostnames, IPs, and ports are not validated before being passed to SSH/HTTP operations. Python's `ipaddress` module and simple regex validation cover these needs without third-party libraries. For credential sanitization, the codebase is mostly clean (only one log line mentions auth, and it does not log the key value), but `str(e)` exception stringification in error handlers could leak credentials embedded in URLs or connection strings.

**Primary recommendation:** Create a centralized `ssh_connect()` helper with TOFU known_hosts management, flip the Proxmox SSL default to `True`, add an input validation module, and add a logging filter to redact sensitive patterns.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SEC-01 | SSH connections use host key verification with trust-on-first-use (TOFU) model | asyncssh 2.21.0 supports `known_hosts` file path, `SSHKnownHosts` objects, and `validate_host_public_key` callback on `SSHClient` -- all needed for TOFU. See Architecture Patterns section. |
| SEC-02 | Proxmox API connections verify SSL certificates by default with configurable override | `aiohttp.TCPConnector(ssl=...)` accepts `bool` or `ssl.SSLContext`. Change default from `False` to `True`, add `PROXMOX_CA_CERT` env var for self-signed cert paths. |
| SEC-03 | All tool inputs validated for hostnames, IP addresses, and port ranges | Python stdlib `ipaddress` module + hostname regex covers validation. Create `validation.py` module called before SSH/HTTP operations. |
| SEC-04 | Sensitive credentials never appear in log output or error responses | Add `logging.Filter` subclass that redacts patterns matching passwords/tokens/keys. Wrap `str(e)` calls in error handlers with a sanitization function. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| asyncssh | 2.21.0 | SSH connections with host key verification | Already installed. Native known_hosts parsing, SSHClient callback for TOFU, `export_public_key()` for key storage. |
| aiohttp | 3.9.0+ | Proxmox API HTTPS with SSL verification | Already installed. `TCPConnector(ssl=True/SSLContext)` for certificate verification. |
| ipaddress | stdlib | IP address validation | Standard library. `ipaddress.ip_address()` and `ipaddress.ip_network()` with proper error handling. |
| re | stdlib | Hostname validation | RFC 952/1123 hostname pattern matching. |
| ssl | stdlib | SSL context for self-signed certs | `ssl.create_default_context(cafile=...)` for custom CA bundles. |
| logging | stdlib | Log filtering for credential redaction | `logging.Filter` subclass for pattern-based redaction. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pathlib | stdlib | Known hosts file management | Managing `~/.homelab_mcp/known_hosts` file |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom hostname regex | validators (PyPI) | Adds dependency for one function; stdlib regex is sufficient for hostname/IP validation |
| Manual known_hosts file | asyncssh SSHKnownHosts | SSHKnownHosts only parses; we need a writable TOFU store, so we manage the file ourselves and pass path to asyncssh |
| logging.Filter | structlog | Structlog is more powerful but adds a dependency; stdlib Filter is sufficient for redaction |

**Installation:**
```bash
# No new dependencies needed -- all stdlib or already installed
```

## Architecture Patterns

### Recommended Project Structure
```
src/homelab_mcp/
├── ssh_connection.py      # NEW: Centralized SSH connect helper with TOFU
├── validation.py          # NEW: Input validation for hostnames, IPs, ports
├── log_filter.py          # NEW: Credential redaction logging filter
├── config.py              # MODIFIED: Add SSH known_hosts path, Proxmox SSL defaults
├── proxmox_api.py         # MODIFIED: Default verify_ssl=True, CA cert support
├── ssh_tools.py           # MODIFIED: Use ssh_connect() helper
├── vm_operations.py       # MODIFIED: Use ssh_connect() helper
├── infrastructure_crud.py # MODIFIED: Use ssh_connect() helper
├── shell_session.py       # MODIFIED: Use ssh_connect() helper
├── resource_manager.py    # MODIFIED: SSL context in session creation
└── error_handling.py      # MODIFIED: Sanitize str(e) in error responses
```

### Pattern 1: Centralized SSH Connection with TOFU

**What:** A single `ssh_connect()` async context manager that replaces all 20+ `asyncssh.connect(..., known_hosts=None)` calls. It manages a per-project known_hosts file and implements trust-on-first-use.

**When to use:** Every SSH connection in the codebase.

**How asyncssh TOFU works:**
1. asyncssh's `known_hosts` parameter accepts: `None` (disable verification), a file path string (load and verify), `bytes` (inline known_hosts data), or an `SSHKnownHosts` object.
2. When `known_hosts` points to a file that does NOT contain the server's key, asyncssh raises `HostKeyNotVerifiable`.
3. For TOFU: on first connection (empty/missing file), catch `HostKeyNotVerifiable`, store the key, then reconnect. On subsequent connections, the file contains the trusted key and mismatches are rejected automatically.
4. Alternatively, subclass `SSHClient` and override `validate_host_public_key(host, addr, port, key) -> bool` to implement TOFU logic in-memory. This callback is invoked when the key is NOT in the known_hosts file.

**Example:**
```python
# Source: asyncssh 2.21.0 installed source code analysis
import asyncssh
from pathlib import Path

KNOWN_HOSTS_PATH = Path.home() / ".homelab_mcp" / "known_hosts"

class TOFUSSHClient(asyncssh.SSHClient):
    """SSH client that implements trust-on-first-use for host keys."""

    def __init__(self, known_hosts_path: Path) -> None:
        super().__init__()
        self._known_hosts_path = known_hosts_path
        self._new_host_key: asyncssh.SSHKey | None = None

    def validate_host_public_key(
        self, host: str, addr: str, port: int, key: asyncssh.SSHKey
    ) -> bool:
        """Accept and store unknown host keys (TOFU).

        Called only when key is NOT in the known_hosts file.
        Returns True to accept the key, then stores it.
        """
        # Check if ANY key for this host exists in our file
        if self._host_has_stored_key(host, port):
            # Key mismatch -- host has a different stored key
            return False  # Reject -- possible MITM

        # First connection -- trust and store
        self._store_host_key(host, port, key)
        return True

    def _host_has_stored_key(self, host: str, port: int) -> bool:
        """Check if we already have a key for this host."""
        if not self._known_hosts_path.exists():
            return False
        content = self._known_hosts_path.read_text()
        host_pattern = f"[{host}]:{port}" if port != 22 else host
        return host_pattern in content

    def _store_host_key(self, host: str, port: int, key: asyncssh.SSHKey) -> None:
        """Append host key to known_hosts file."""
        self._known_hosts_path.parent.mkdir(parents=True, exist_ok=True)
        host_pattern = f"[{host}]:{port}" if port != 22 else host
        key_data = key.export_public_key().decode("utf-8").strip()
        with open(self._known_hosts_path, "a") as f:
            f.write(f"{host_pattern} {key_data}\n")


async def ssh_connect(
    hostname: str,
    username: str = "mcp_admin",
    port: int = 22,
    password: str | None = None,
    key_path: str | None = None,
) -> asyncssh.SSHClientConnection:
    """Create SSH connection with TOFU host key verification."""
    connect_kwargs: dict = {
        "host": hostname,
        "username": username,
        "port": port,
        "known_hosts": str(KNOWN_HOSTS_PATH),
        "client_factory": lambda: TOFUSSHClient(KNOWN_HOSTS_PATH),
    }
    if password:
        connect_kwargs["password"] = password
    if key_path:
        connect_kwargs["client_keys"] = [key_path]

    return await asyncssh.connect(**connect_kwargs)
```

### Pattern 2: Proxmox SSL Verification with Self-Signed Cert Override

**What:** Change `verify_ssl` default to `True` and add support for a custom CA certificate file path via `PROXMOX_CA_CERT` environment variable.

**When to use:** All Proxmox API connections.

**Example:**
```python
# Source: aiohttp docs + ssl stdlib
import ssl
import aiohttp

def create_ssl_context(
    verify: bool = True,
    ca_cert_path: str | None = None,
) -> ssl.SSLContext | bool:
    """Create SSL context for Proxmox API connections.

    Returns:
        True for default verification, False to disable,
        or SSLContext for custom CA cert.
    """
    if not verify:
        return False

    if ca_cert_path:
        ctx = ssl.create_default_context(cafile=ca_cert_path)
        return ctx

    return True  # Use system CA bundle
```

### Pattern 3: Input Validation Module

**What:** Centralized validation functions for hostnames, IP addresses, and port ranges that reject malformed or hostile inputs before they reach SSH/HTTP operations.

**When to use:** Called in tool handlers before passing user inputs to SSH connect or HTTP requests.

**Example:**
```python
# Source: Python stdlib ipaddress module + RFC 1123
import ipaddress
import re

# RFC 1123 hostname: labels of 1-63 chars, total max 253
_HOSTNAME_RE = re.compile(
    r'^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})*$'
)

def validate_hostname(value: str) -> str:
    """Validate and return a hostname or IP address string.

    Raises ValueError with clear message on invalid input.
    """
    if not value or len(value) > 253:
        raise ValueError(f"Invalid hostname: empty or too long ({len(value)} chars)")

    # Try as IP address first
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        pass

    # Try as hostname
    if not _HOSTNAME_RE.match(value):
        raise ValueError(
            f"Invalid hostname '{value}': must be a valid hostname or IP address"
        )
    return value


def validate_port(value: int) -> int:
    """Validate a port number (1-65535)."""
    if not isinstance(value, int) or value < 1 or value > 65535:
        raise ValueError(f"Invalid port: {value} (must be 1-65535)")
    return value
```

### Pattern 4: Credential Redaction in Logging

**What:** A `logging.Filter` that scans log messages for patterns that look like passwords, API tokens, or SSH key content and replaces them with `[REDACTED]`.

**When to use:** Attached to the root logger during server initialization.

**Example:**
```python
import logging
import re

_SENSITIVE_PATTERNS = [
    (re.compile(r'(password["\s:=]+)\S+', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(token["\s:=]+)\S+', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(PVEAPIToken=)\S+'), r'\1[REDACTED]'),
    (re.compile(r'(Authorization:\s*)\S+'), r'\1[REDACTED]'),
    (re.compile(r'(-----BEGIN[A-Z ]+KEY-----).*?(-----END[A-Z ]+KEY-----)',
                re.DOTALL), r'\1[REDACTED]\2'),
]

class CredentialFilter(logging.Filter):
    """Redact sensitive values from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, replacement in _SENSITIVE_PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        if record.args:
            sanitized = []
            for arg in (record.args if isinstance(record.args, tuple) else (record.args,)):
                if isinstance(arg, str):
                    for pattern, replacement in _SENSITIVE_PATTERNS:
                        arg = pattern.sub(replacement, arg)
                sanitized.append(arg)
            record.args = tuple(sanitized)
        return True


def sanitize_error(error: Exception) -> str:
    """Sanitize an exception message to remove credentials."""
    msg = str(error)
    for pattern, replacement in _SENSITIVE_PATTERNS:
        msg = pattern.sub(replacement, msg)
    return msg
```

### Anti-Patterns to Avoid
- **`known_hosts=None` everywhere:** This is the current state -- it disables ALL host key verification, making every SSH connection vulnerable to MITM. Must be replaced.
- **Wrapping each call site individually:** Do NOT add known_hosts logic to each of the 20+ `asyncssh.connect()` calls. Centralize in one helper function.
- **Storing host keys in the database:** Tempting but wrong -- asyncssh already has a well-tested OpenSSH known_hosts file format parser. Use the file.
- **Blanket `except Exception` that logs `str(e)`:** Exception messages from `aiohttp` and `asyncssh` can contain URLs with embedded credentials. Always sanitize.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSH known_hosts parsing | Custom parser | asyncssh `SSHKnownHosts` / known_hosts file | OpenSSH format is complex (hashed entries, patterns, revoked markers). asyncssh handles it all. |
| IP address validation | Custom regex for IPv4/IPv6 | `ipaddress.ip_address()` | IPv6 has many representation forms; the stdlib handles them all. |
| SSL certificate verification | Custom certificate checking | `ssl.create_default_context()` | System CA bundle management, certificate chain validation, hostname verification -- all handled. |
| Host key format | Custom key serialization | `key.export_public_key()` / `asyncssh.import_public_key()` | Key format handling (RSA, Ed25519, ECDSA) is complex. asyncssh handles all formats. |

**Key insight:** Every security primitive in this phase is already available in the Python stdlib or asyncssh/aiohttp. The work is wiring them correctly and replacing the insecure defaults.

## Common Pitfalls

### Pitfall 1: asyncssh `known_hosts` Empty String vs None
**What goes wrong:** Passing `known_hosts=""` (empty string) makes asyncssh look for `~/.ssh/known_hosts` (the system-wide file). Passing `known_hosts=None` disables verification entirely. Passing `known_hosts=b""` (empty bytes) means "no trusted keys" and will reject ALL connections.
**Why it happens:** The three falsy values have completely different semantics.
**How to avoid:** Always pass an explicit file path string to `known_hosts`. If the file does not exist, create it empty first. Then use the `SSHClient.validate_host_public_key` callback for TOFU.
**Warning signs:** Tests pass but host key verification is silently disabled.

### Pitfall 2: Race Condition on Known Hosts File
**What goes wrong:** Two concurrent SSH connections to the same new host could both trigger TOFU, writing duplicate entries.
**Why it happens:** File append is not atomic with the TOFU decision.
**How to avoid:** Use a per-host asyncio.Lock or a file-level lock. Since this is a single-user homelab server, a module-level `asyncio.Lock` is sufficient.
**Warning signs:** Duplicate entries in known_hosts file (harmless but messy).

### Pitfall 3: Self-Signed Cert Rejection Breaks Existing Setups
**What goes wrong:** Changing `verify_ssl` default from `False` to `True` will break every existing installation using Proxmox's default self-signed certificate.
**Why it happens:** Proxmox ships with a self-signed cert by default. Most homelab setups do not have proper TLS.
**How to avoid:** Default to `True` but provide clear error messages that explain `PROXMOX_VERIFY_SSL=false` or `PROXMOX_CA_CERT=/path/to/cert.pem` as options. Add a migration note.
**Warning signs:** "SSL certificate verify failed" errors after upgrade.

### Pitfall 4: Hostname Validation Rejects Valid Internal Names
**What goes wrong:** Overly strict hostname validation rejects common homelab patterns like `pve.local`, `node-1`, or `.internal` TLDs.
**Why it happens:** RFC 1123 is strict about labels; internal networks use non-standard names.
**How to avoid:** Validate syntax (no spaces, no shell metacharacters, reasonable length) but do NOT enforce valid TLDs. Accept anything that matches the hostname regex pattern plus valid IP addresses.
**Warning signs:** Users report "invalid hostname" for names that work with SSH.

### Pitfall 5: Credential Leakage in Exception Chains
**What goes wrong:** `str(e)` on an `aiohttp.ClientResponseError` can include the request URL, which may contain credentials in query parameters. asyncssh errors can include the username.
**Why it happens:** Library exception messages are designed for debugging, not user-facing output.
**How to avoid:** Apply `sanitize_error()` to all `str(e)` calls in error responses returned to the MCP client. The logging filter handles log output separately.
**Warning signs:** Full URLs with `?token=...` appearing in MCP client error responses.

## Code Examples

Verified patterns from installed library source code:

### asyncssh Connection with Known Hosts File
```python
# Source: asyncssh 2.21.0 connection.py line 7530-7535
# known_hosts parameter accepts:
# - None: disable host key verification
# - str: path to known_hosts file
# - bytes: inline known_hosts data
# - SSHKnownHosts: parsed known_hosts object
# - callable(host, addr, port) -> [str]: dynamic lookup

conn = await asyncssh.connect(
    host="192.168.1.100",
    username="mcp_admin",
    known_hosts="/path/to/known_hosts",  # File path for verification
)
```

### asyncssh SSHClient Callback for TOFU
```python
# Source: asyncssh 2.21.0 client.py line 124-158
# validate_host_public_key is called ONLY when key is not in known_hosts
# Return True to accept, False to reject
# asyncssh then verifies server possesses the private key

class MyClient(asyncssh.SSHClient):
    def validate_host_public_key(self, host, addr, port, key):
        # TOFU: accept if no prior key, reject if different key
        return not self._has_existing_key(host, port)
```

### aiohttp SSL Context for Self-Signed Certs
```python
# Source: aiohttp + ssl stdlib
import ssl
ctx = ssl.create_default_context(cafile="/path/to/proxmox-ca.pem")
connector = aiohttp.TCPConnector(ssl=ctx)
# For disable: aiohttp.TCPConnector(ssl=False)
```

### asyncssh Host Key Export
```python
# Source: asyncssh 2.21.0 public_key module
# export_public_key() returns bytes in OpenSSH format
key_bytes = key.export_public_key()  # b"ssh-ed25519 AAAA... comment\n"
key_str = key_bytes.decode("utf-8").strip()
# Write to known_hosts: f"{host} {key_str}\n"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `known_hosts=None` (disable) | File-based known_hosts with TOFU callback | asyncssh has supported this since 2.0+ | All SSH connections become MITM-resistant |
| `verify_ssl=False` default | `verify_ssl=True` with CA cert override | Standard practice | Proxmox API connections verify certificates |
| No input validation | Validation module before SSH/HTTP | Always best practice | Prevents injection of malformed hostnames |
| Raw `str(e)` in responses | Sanitized error messages | Always best practice | Credentials never leak to MCP clients |

**Deprecated/outdated:**
- `known_hosts=None` was a development shortcut that must not ship in production.
- `verify_ssl=False` default was a development convenience.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio |
| Config file | pyproject.toml (pytest section) |
| Quick run command | `uv run pytest tests/ -m "not integration" -x -q` |
| Full suite command | `uv run pytest tests/ -m "not integration" -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEC-01 | TOFU accepts new host keys and stores them | unit | `uv run pytest tests/test_ssh_connection.py::test_tofu_first_connection -x` | No -- Wave 0 |
| SEC-01 | TOFU rejects changed host keys | unit | `uv run pytest tests/test_ssh_connection.py::test_tofu_rejects_mismatch -x` | No -- Wave 0 |
| SEC-01 | TOFU accepts known host keys | unit | `uv run pytest tests/test_ssh_connection.py::test_tofu_accepts_known_key -x` | No -- Wave 0 |
| SEC-02 | Proxmox SSL verification enabled by default | unit | `uv run pytest tests/test_proxmox_api.py::test_ssl_verify_default_true -x` | No -- Wave 0 |
| SEC-02 | Proxmox self-signed cert override works | unit | `uv run pytest tests/test_proxmox_api.py::test_ssl_custom_ca_cert -x` | No -- Wave 0 |
| SEC-03 | Valid hostnames/IPs accepted | unit | `uv run pytest tests/test_validation.py::test_valid_hostnames -x` | No -- Wave 0 |
| SEC-03 | Invalid/hostile inputs rejected | unit | `uv run pytest tests/test_validation.py::test_invalid_hostnames -x` | No -- Wave 0 |
| SEC-03 | Port range validation | unit | `uv run pytest tests/test_validation.py::test_port_validation -x` | No -- Wave 0 |
| SEC-04 | Logging filter redacts passwords | unit | `uv run pytest tests/test_log_filter.py::test_redacts_password -x` | No -- Wave 0 |
| SEC-04 | Error responses do not contain credentials | unit | `uv run pytest tests/test_log_filter.py::test_sanitize_error -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -m "not integration" -x -q`
- **Per wave merge:** `uv run pytest tests/ -m "not integration" -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_ssh_connection.py` -- covers SEC-01 (TOFU behavior with mocked asyncssh)
- [ ] `tests/test_validation.py` -- covers SEC-03 (hostname, IP, port validation)
- [ ] `tests/test_log_filter.py` -- covers SEC-04 (credential redaction)
- [ ] Update `tests/test_proxmox_api.py` -- add SEC-02 tests (SSL default, CA cert)

## Open Questions

1. **Known hosts file location**
   - What we know: The project uses `~/.homelab_mcp/` for database storage. SSH keys are in `~/.ssh/mcp/`.
   - What's unclear: Whether to put known_hosts in `~/.homelab_mcp/known_hosts` or `~/.ssh/mcp/known_hosts`.
   - Recommendation: Use `~/.homelab_mcp/known_hosts` to keep project files together and avoid conflicts with the user's own `~/.ssh/known_hosts`.

2. **Handling existing `known_hosts=None` deployments**
   - What we know: Every current user has no stored host keys.
   - What's unclear: Whether first-run after upgrade should auto-trust all existing hosts.
   - Recommendation: TOFU handles this naturally -- first connection after upgrade will trust and store the key. No migration needed.

3. **Proxmox SSL default change -- breaking change?**
   - What we know: Most homelab Proxmox installations use self-signed certificates.
   - What's unclear: How many users have configured proper TLS.
   - Recommendation: Change default to `True` but provide clear error message with instructions for `PROXMOX_VERIFY_SSL=false` or `PROXMOX_CA_CERT` path. This is a security improvement worth the friction.

## Sources

### Primary (HIGH confidence)
- asyncssh 2.21.0 installed source -- `connection.py` (known_hosts handling, lines 3473-3489, 7530-7549), `client.py` (validate_host_public_key callback, lines 124-158), `known_hosts.py` (SSHKnownHosts parser, import_known_hosts, read_known_hosts)
- Python stdlib `ipaddress` module documentation
- Python stdlib `ssl` module -- `create_default_context()` API
- Python stdlib `logging` module -- `Filter` class
- aiohttp source -- `TCPConnector(ssl=...)` parameter

### Secondary (MEDIUM confidence)
- Codebase analysis: 20+ `known_hosts=None` sites identified across 4 source files
- Codebase analysis: `verify_ssl=False` default in `proxmox_api.py` line 24 and `get_proxmox_client()` line 217
- Codebase analysis: `str(e)` used in 15+ error handler locations

### Tertiary (LOW confidence)
- None -- all findings verified from installed source code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed, API verified from source
- Architecture: HIGH -- patterns derived from asyncssh source code analysis
- Pitfalls: HIGH -- identified from actual codebase state and library behavior
- Input validation: HIGH -- stdlib ipaddress module is well-documented
- Credential sanitization: MEDIUM -- regex patterns cover known cases but edge cases may exist

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable libraries, no fast-moving APIs)
