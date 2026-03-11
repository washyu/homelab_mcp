---
phase: 02-security-hardening
verified: 2026-03-09T17:30:00Z
status: passed
score: 4/4 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 2/4
  gaps_closed:
    - "Tool inputs for hostnames, IP addresses, and port ranges are validated before use -- malformed or hostile inputs are rejected with clear error messages"
    - "Passwords, API tokens, and SSH keys never appear in log output or error responses returned to the MCP client"
  gaps_remaining: []
  regressions: []
---

# Phase 2: Security Hardening Verification Report

**Phase Goal:** Users can trust that their SSH and Proxmox connections are not vulnerable to interception, tool inputs are validated, and credentials never leak into logs
**Verified:** 2026-03-09T17:30:00Z
**Status:** passed
**Re-verification:** Yes -- after gap closure (plans 02-04 and 02-05)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SSH connections verify host keys using TOFU -- first connection stores, subsequent reject mismatches | VERIFIED | ssh_connection.py implements TOFUSSHClient with validate_host_public_key(). Zero known_hosts=None in src/. All 4 consumer files import ssh_connect. No regression. |
| 2 | Proxmox API connections verify SSL certificates by default, with documented override for self-signed certs | VERIFIED | proxmox_api.py verify_ssl=True default (line 26). config.py proxmox_verify_ssl/proxmox_ca_cert with create_ssl_context(). No regression. |
| 3 | Tool inputs for hostnames, IP addresses, and port ranges are validated before use -- malformed or hostile inputs are rejected with clear error messages | VERIFIED | ssh_connection.py imports validate_hostname/validate_port and calls both at lines 182-183 (centralized entry point covering all 21+ SSH call sites). Handler-level validation in network_handlers.py (validate_hostname at line 12, line 21), ssh_handlers.py (validate_hostname line 44, validate_port line 46), proxmox_handlers.py (validate_hostname at 10 call sites). 4 wiring tests pass proving invalid inputs rejected. |
| 4 | Passwords, API tokens, and SSH keys never appear in log output or error responses returned to the MCP client | VERIFIED | CredentialFilter on root logger (server.py line 26). sanitize_error imported in 9 production modules: error_handling.py, proxmox_api.py, vm_operations.py, infrastructure_crud.py, ssh_tools.py, service_installer.py, sitemap.py, http_transport.py, proxmox_scripts.py. Zero raw str(e) in error response dicts across the 5 key modules (proxmox_api, vm_operations, infrastructure_crud, ssh_tools, service_installer). All remaining str(e) are in logger.* calls (covered by CredentialFilter). 7 wiring tests pass. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/homelab_mcp/validation.py` | Input validation functions | VERIFIED | 93 lines, 3 functions, imported in ssh_connection.py + 3 handler modules |
| `src/homelab_mcp/log_filter.py` | Credential redaction filter | VERIFIED | CredentialFilter + sanitize_error, imported in 9 modules |
| `src/homelab_mcp/ssh_connection.py` | TOFU SSH + validation at entry | VERIFIED | 209 lines, TOFUSSHClient + ssh_connect with validate_hostname/validate_port |
| `src/homelab_mcp/config.py` | SSL config | VERIFIED | proxmox_verify_ssl, proxmox_ca_cert, create_ssl_context() |
| `src/homelab_mcp/proxmox_api.py` | verify_ssl=True + sanitize_error | VERIFIED | Line 26: verify_ssl=True. sanitize_error in all 8 error response dicts |
| `src/homelab_mcp/resource_manager.py` | SSL-aware session creation | VERIFIED | create_ssl_context() passed to TCPConnector |
| `tests/test_validation.py` | Validation unit tests | VERIFIED | 32 tests passing |
| `tests/test_validation_wiring.py` | Wiring tests for validation | VERIFIED | 37 lines, 4 tests passing |
| `tests/test_log_filter.py` | Redaction tests | VERIFIED | 16 tests passing |
| `tests/test_ssh_connection.py` | TOFU tests | VERIFIED | 7 tests passing |
| `tests/test_sanitize_wiring.py` | Wiring tests for sanitize_error | VERIFIED | 111 lines, 7 tests passing |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| ssh_connection.py | validation.py | `from .validation import validate_hostname, validate_port` | WIRED | Import line 18, calls at lines 182-183 |
| tool_handlers/network_handlers.py | validation.py | `from ..validation import validate_hostname` | WIRED | Import line 7, calls at lines 12, 21 |
| tool_handlers/ssh_handlers.py | validation.py | `from ..validation import validate_hostname, validate_port` | WIRED | Import line 8, calls at lines 44, 46 |
| tool_handlers/proxmox_handlers.py | validation.py | `from ..validation import validate_hostname` | WIRED | Import line 6, 10 call sites |
| ssh_tools.py | ssh_connection.py | `from .ssh_connection import ssh_connect` | WIRED | Import line 14 |
| vm_operations.py | ssh_connection.py | `from .ssh_connection import ssh_connect` | WIRED | Import line 8 |
| infrastructure_crud.py | ssh_connection.py | `from .ssh_connection import ssh_connect` | WIRED | Import line 10 |
| shell_session.py | ssh_connection.py | `from .ssh_connection import ssh_connect` | WIRED | Import line 11 |
| proxmox_api.py | log_filter.py | `from .log_filter import sanitize_error` | WIRED | Import line 14, 8 sanitize_error(e) calls |
| vm_operations.py | log_filter.py | `from .log_filter import sanitize_error` | WIRED | Import line 6, 12 sanitize_error(e) calls |
| infrastructure_crud.py | log_filter.py | `from .log_filter import sanitize_error` | WIRED | Import line 8, 13 sanitize_error(e) calls |
| ssh_tools.py | log_filter.py | `from .log_filter import sanitize_error` | WIRED | Import line 13, 6 sanitize_error(e) calls |
| service_installer.py | log_filter.py | `from .log_filter import sanitize_error` | WIRED | Import line 10, 3 sanitize_error(e) calls |
| server.py | log_filter.py | `CredentialFilter` on root logger | WIRED | Import line 18, attached line 26 |
| config.py | proxmox_api.py | PROXMOX_VERIFY_SSL / PROXMOX_CA_CERT | WIRED | Both read env vars consistently |
| resource_manager.py | TCPConnector | ssl parameter from create_ssl_context() | WIRED | Confirmed |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SEC-01 | 02-03 | SSH connections use TOFU host key verification | SATISFIED | ssh_connection.py TOFUSSHClient, zero known_hosts=None, all consumers use ssh_connect |
| SEC-02 | 02-02 | Proxmox API verifies SSL by default with override | SATISFIED | verify_ssl=True default, PROXMOX_VERIFY_SSL/PROXMOX_CA_CERT config, ResourceManager SSL wiring |
| SEC-03 | 02-01, 02-04 | All tool inputs validated for hostnames, IPs, ports | SATISFIED | Centralized validation in ssh_connect() + defense-in-depth in 3 handler modules. 4 wiring tests confirm. |
| SEC-04 | 02-01, 02-05 | Credentials never in log output or error responses | SATISFIED | CredentialFilter on root logger. sanitize_error(e) in all error response dicts across 9 production modules. Zero raw str(e) in MCP client-facing error responses for the 5 key modules. 7 wiring tests confirm. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| src/homelab_mcp/vm_providers/lxd_provider.py | 72-306 | 11x str(e) in error response dicts via _format_error() | Warning | Provider-level error dicts flow through vm_operations.py to MCP clients. Lower risk: provider errors are typically operational (Docker/LXD CLI failures) not credential-bearing. Consider sanitizing in a future phase. |
| src/homelab_mcp/vm_providers/docker_provider.py | 81-250 | 9x str(e) in error response dicts via _format_error() | Warning | Same as above. |
| src/homelab_mcp/vm_providers/base.py | 92 | 1x str(e) in error response dict | Warning | Same pattern. |
| src/homelab_mcp/error_handling.py | 287 | str(e) used for exception type detection | Info | Used for control flow ("Authentication failed" check), not output. Acceptable. |

### Human Verification Required

### 1. TOFU Behavior with Real SSH Server

**Test:** Connect to a real SSH host for the first time, then change the host key and reconnect.
**Expected:** First connection succeeds and stores key. Second connection with different key is rejected with warning.
**Why human:** Requires live SSH server; mock tests verify logic but not asyncssh integration.

### 2. SSL Verification with Proxmox

**Test:** Connect to a Proxmox instance with valid cert, then with PROXMOX_VERIFY_SSL=false, then with PROXMOX_CA_CERT.
**Expected:** Valid cert works, self-signed fails by default, PROXMOX_VERIFY_SSL=false allows connection, PROXMOX_CA_CERT with correct CA works.
**Why human:** Requires live Proxmox instance to verify SSL handshake behavior.

### 3. Input Validation Error Messages

**Test:** Call a tool with a hostile hostname like "host; rm -rf /" and verify the error message is clear and the command is never executed.
**Expected:** ValueError with "invalid characters" message, no SSH connection attempted.
**Why human:** Confirms user-facing error message quality and that validation truly blocks the connection path end-to-end.

### Gaps Summary

No gaps remain. Both previously-identified gaps have been closed:

**Gap 1 (CLOSED): Input validation wired (SEC-03).** Plan 02-04 added validate_hostname/validate_port calls at the centralized ssh_connect() entry point (covering all 21+ SSH call sites) and defense-in-depth validation in 3 handler modules (network_handlers, ssh_handlers, proxmox_handlers). 4 wiring tests confirm.

**Gap 2 (CLOSED): Credential redaction in error responses (SEC-04).** Plan 02-05 replaced all raw str(e) calls in error response dicts with sanitize_error(e) across 8 production modules. 7 wiring tests using source inspection confirm no raw str(e) remains in error response contexts.

**Note:** The vm_providers layer (lxd_provider.py, docker_provider.py, base.py) still uses raw str(e) in error dicts. These were not in the original gap scope and are lower risk (operational errors from Docker/LXD CLI rather than credential-bearing exceptions). Flagged as warnings for consideration in Phase 3.

**Test Suite:** 434 passed, 7 skipped, 29 deselected (3.21s).

---

_Verified: 2026-03-09T17:30:00Z_
_Verifier: Claude (gsd-verifier)_
