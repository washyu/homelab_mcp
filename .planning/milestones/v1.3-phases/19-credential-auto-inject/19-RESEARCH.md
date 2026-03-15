# Phase 19: Credential Auto-Inject - Research

**Researched:** 2026-03-14
**Domain:** Python credential injection, SSH tool wiring, Proxmox API fallback
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INJECT-01 | SSH tools automatically fill username/password from keyring when hostname matches a stored credential | `resolve_ssh_credentials()` already has the right shape; needs keyring lookup added as priority 2 |
| INJECT-02 | Explicitly passed tool arguments take precedence over stored credentials (explicit > keyring > default key) | Current explicit-arg check at top of `resolve_ssh_credentials()` is already correct gating point |
| INJECT-03 | Proxmox connection falls back to keyring when PROXMOX_HOST/PROXMOX_TOKEN env vars are absent | `get_proxmox_client()` has a clear env-var section; keyring lookup inserts cleanly before the final `raise ValueError` |
</phase_requirements>

---

## Summary

Phase 19 wires the keyring credential store (built in Phase 17) into the two remaining callsites: the SSH credential resolution path and the Proxmox client factory. Both callsites already have the structural scaffolding needed — the work is adding one new priority tier to each.

The SSH path runs through `resolve_ssh_credentials()` in `ssh_tools.py`. That function already has a three-tier waterfall (explicit args → SQLite DB credentials → mcp_admin key fallback). Phase 19 inserts a new tier between explicit args and the DB lookup: if no explicit `password` or `key_path` was provided, look up the hostname in the keyring registry, resolve the username from the registry entry, and call `get_credential(hostname, username)`. If the keyring returns a password, inject it. The DB-lookup tier remains as-is for backward compatibility.

The Proxmox path runs through `get_proxmox_client()` in `proxmox_api.py`. That function reads four env vars (`PROXMOX_HOST`, `PROXMOX_API_TOKEN`, `PROXMOX_USER`, `PROXMOX_PASSWORD`) and raises `ValueError` if host or auth is missing. Phase 19 extends this function to attempt a keyring lookup when env vars are absent. The REQUIREMENTS.md uses "PROXMOX_TOKEN" as the env-var name but the codebase uses `PROXMOX_API_TOKEN` — both are the same variable.

Log safety is already provided by the `CredentialFilter` attached to the root logger in `server.py`. Any `password=...` string in a log message is automatically redacted to `[REDACTED]`. The additional guard is to never pass the raw credential value as a log argument — use `logger.debug("injected keyring credential for %s", hostname)` not `logger.debug("injected %s for %s", password, hostname)`.

**Primary recommendation:** Add keyring inject as a thin new tier in `resolve_ssh_credentials()`, extend `get_proxmox_client()` with a keyring fallback block, and write tests using `mocker.patch` on `homelab_mcp.ssh_tools.get_credential` and `homelab_mcp.proxmox_api.get_credential`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `credential_store.get_credential` | project | Retrieve password from OS keyring by hostname+username | Already implemented in Phase 17; headless-safe; used for all keyring reads |
| `credential_store.list_credentials` | project | Resolve username for a hostname via the registry | Registry is the source of truth for (hostname, username) mapping |
| `log_filter.sanitize_error` | project | Redact credentials from exception messages | Established pattern; every except block uses this |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `log_filter.CredentialFilter` | project | Auto-redact `password=...` from all log output | Already attached to root logger in `server.py`; no additional wiring needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `list_credentials()` for username lookup | Pass username explicitly from callers | Callers don't have the username — it was stored at credential-add time and must come from the registry |
| Injecting into handlers (`ssh_handlers.py`) | Injecting into `resolve_ssh_credentials()` | Handler injection requires changes in every handler; `resolve_ssh_credentials()` is the single resolution point for all SSH tools |

---

## Architecture Patterns

### Recommended Project Structure

No new files needed. All changes are modifications to:

```
src/homelab_mcp/
├── ssh_tools.py          # Add keyring tier to resolve_ssh_credentials()
├── proxmox_api.py        # Add keyring fallback to get_proxmox_client()
tests/
├── test_ssh_tools.py     # New tests for INJECT-01 and INJECT-02
├── test_proxmox_api.py   # New tests for INJECT-03
```

### Pattern 1: Keyring Inject Tier in resolve_ssh_credentials()

**What:** After the explicit-args check and before the DB lookup, query the registry for the hostname and call `get_credential()`.
**When to use:** When `password` and `key_path` are both None (i.e., no explicit credentials were passed).
**Example:**

```python
# In resolve_ssh_credentials(), after the existing explicit-args block:

# Tier 2: Keyring lookup (new)
# Only attempt if no explicit password or key_path was given.
# This preserves INJECT-02: explicit > keyring > default key.
from .credential_store import get_credential, list_credentials  # lazy import inside function

registry_entries = list_credentials(credential_type="ssh")
matched = [e for e in registry_entries if e["hostname"] == hostname]
if matched:
    stored_username = matched[0]["username"]
    resolved_username = username or stored_username
    keyring_password = get_credential(hostname, stored_username, credential_type="ssh")
    if keyring_password:
        logger.debug("Auto-injected keyring credential for %s", hostname)
        return SSHCredentials(
            hostname=hostname,
            username=resolved_username,
            port=port,
            password=keyring_password,
        )

# Tier 3: DB lookup (existing, unchanged)
# ...
```

### Pattern 2: Keyring Fallback in get_proxmox_client()

**What:** After reading env vars, if `host` or auth is still missing, attempt keyring lookup before raising.
**When to use:** PROXMOX_HOST and PROXMOX_API_TOKEN env vars are absent.
**Example:**

```python
# In get_proxmox_client(), after the env-var reads:

# Keyring fallback (new): attempt when env vars insufficient
if not host or (not api_token and not (username and password)):
    from .credential_store import get_credential, list_credentials  # lazy import

    registry_entries = list_credentials(credential_type="proxmox")
    if registry_entries:
        entry = registry_entries[0]  # first stored Proxmox host
        keyring_host = entry["hostname"]
        keyring_username = entry["username"]
        keyring_secret = get_credential(keyring_host, keyring_username, credential_type="proxmox")
        if keyring_secret:
            host = host or keyring_host
            # The stored secret is the API token (format: user@realm!tokenid=secret)
            # or a password — both are stored as the keyring password field.
            api_token = api_token or keyring_secret
            logger.debug("Auto-injected Proxmox keyring credential for %s", host)

# Existing raise remains as the final gate:
if not host:
    raise ValueError("Proxmox host must be provided or set in PROXMOX_HOST env var")
if not api_token and not (username and password):
    raise ValueError("Must provide either PROXMOX_API_TOKEN or PROXMOX_USER+PROXMOX_PASSWORD")
```

### Pattern 3: Lazy Imports of credential_store Inside Function Bodies

**What:** Import `get_credential` and `list_credentials` inside the function body, not at module level.
**When to use:** Always in `ssh_tools.py` and `proxmox_api.py` — these modules are not `credential_store.py` and neither should have module-level keyring dependencies.
**Why:** Consistent with the established pattern for all keyring usage in the project. Prevents circular imports; consistent with `server.py` local imports of `get_resource_manager`.

### Anti-Patterns to Avoid

- **Module-level `from .credential_store import ...` in ssh_tools.py or proxmox_api.py:** Creates an import-time dependency that could interfere with test isolation. Use function-body imports.
- **Logging the injected credential value:** `logger.debug("password=%s", password)` will leak even through `CredentialFilter` if the format string doesn't match the redaction patterns. Use `logger.debug("auto-injected keyring credential for %s", hostname)` instead.
- **Raising on keyring miss:** `get_credential()` returning `None` is normal (headless host, not stored). The existing fallback tiers handle this — do not treat `None` as an error.
- **Relying on explicit-username precedence when matching registry:** If the caller passes `username="root"` but the registry has `username="admin"`, use the caller-provided username with the registry password only if hostnames match. Current design: `resolved_username = username or stored_username`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Secure password retrieval | Custom keyring wrapper | `credential_store.get_credential()` | Already headless-safe; all error paths handled; consistent with Phase 17 |
| Credential log redaction | Custom `re.sub` patterns | `CredentialFilter` (already on root logger) + `sanitize_error()` | Already wired in `server.py`; patterns cover `password=...`, `token=...`, PVEAPIToken |
| Username-for-hostname resolution | Another DB query or dict lookup | `credential_store.list_credentials()` + filter by hostname | Registry is the authoritative source of (hostname, username) pairs |

---

## Common Pitfalls

### Pitfall 1: INJECT-02 Regression — Explicit Args Overridden by Keyring

**What goes wrong:** Keyring lookup runs even when the caller passed an explicit `username`/`password`, causing explicit credentials to be silently replaced.
**Why it happens:** The keyring tier is placed before the explicit-args check instead of after it.
**How to avoid:** The explicit-args check is already at the top of `resolve_ssh_credentials()`. The keyring tier must come AFTER that block. The existing condition `if password or key_path: return SSHCredentials(...)` is the gate.
**Warning signs:** Test that passes explicit `username="root", password="explicit"` and verifies the `SSHCredentials.password` is `"explicit"` not the keyring value.

### Pitfall 2: PROXMOX_TOKEN vs PROXMOX_API_TOKEN Naming Mismatch

**What goes wrong:** INJECT-03 requirement text says "PROXMOX_TOKEN" but the actual env var in the codebase is `PROXMOX_API_TOKEN`. Tests fail or the wrong env var is unset in test setup.
**Why it happens:** The requirement was written with a shorter name; the implementation pre-dates it.
**How to avoid:** Always use `PROXMOX_API_TOKEN` in code and tests. The requirement description is informal shorthand.
**Warning signs:** `os.getenv("PROXMOX_TOKEN")` returning None even when the token is set.

### Pitfall 3: Keyring Import at Module Level in ssh_tools.py or proxmox_api.py

**What goes wrong:** `from .credential_store import get_credential` at module top causes D-Bus probe on headless hosts at server startup, before any tool call is made.
**Why it happens:** Forgetting the lazy-import constraint established in Phase 17.
**How to avoid:** All credential_store imports in ssh_tools.py and proxmox_api.py must live inside function bodies.
**Warning signs:** The existing test `test_no_module_level_keyring_import` in `test_credential_store.py` does not cover `ssh_tools.py`; write a parallel test for the new import points if desired.

### Pitfall 4: Log Leakage via f-string

**What goes wrong:** `logger.debug(f"injected password {password} for {hostname}")` writes the credential to logs even though `CredentialFilter` is attached — because the filter operates on `record.msg` and `record.args`, not pre-formatted strings.
**Why it happens:** Using f-strings in log calls bypasses the filter.
**How to avoid:** Always use `%`-style formatting: `logger.debug("auto-injected keyring credential for %s", hostname)`. Never include the password value in any log argument.
**Warning signs:** Any log call in the injection code path that includes the credential variable.

### Pitfall 5: Multi-Entry Proxmox Registry — Which Host to Use

**What goes wrong:** A user has stored credentials for `proxmox1` and `proxmox2` in the keyring. `get_proxmox_client()` picks the wrong one.
**Why it happens:** `list_credentials(credential_type="proxmox")` returns a list; selecting `[0]` is arbitrary.
**How to avoid:** The keyring fallback only fires when `host` env var is also absent. If host is absent, we can't match by hostname — we take the first entry. This is acceptable for single-homelab use (per the project's out-of-scope constraint: "Multi-user credential namespacing: out of scope"). Document this assumption clearly in the code comment.
**Warning signs:** User reports wrong Proxmox host being connected to.

---

## Code Examples

### Resolved SSH Credential Flow (Tier Waterfall)

```python
# Source: src/homelab_mcp/ssh_tools.py — resolve_ssh_credentials() (current + proposed)

def resolve_ssh_credentials(
    hostname: str,
    username: str | None = None,
    password: str | None = None,
    key_path: str | None = None,
    port: int = 22,
) -> SSHCredentials:
    # Tier 1: Explicit args (INJECT-02 gating)
    if password or key_path:
        return SSHCredentials(
            hostname=hostname,
            username=username or "mcp_admin",
            port=port,
            key_path=key_path,
            password=password,
        )

    # Tier 2: Keyring lookup (NEW — INJECT-01)
    # Lazy import: must not be at module level (headless-safe constraint)
    from .credential_store import get_credential, list_credentials  # noqa: PLC0415
    registry_entries = list_credentials(credential_type="ssh")
    matched = [e for e in registry_entries if e["hostname"] == hostname]
    if matched:
        stored_username = matched[0]["username"]
        resolved_username = username or stored_username
        keyring_password = get_credential(hostname, stored_username, credential_type="ssh")
        if keyring_password:
            logger.debug("Auto-injected keyring credential for %s", hostname)
            return SSHCredentials(
                hostname=hostname,
                username=resolved_username,
                port=port,
                password=keyring_password,
            )

    # Tier 3: DB lookup (existing, unchanged)
    # ...
```

### get_proxmox_client Keyring Fallback (INJECT-03)

```python
# Source: src/homelab_mcp/proxmox_api.py — get_proxmox_client() (current + proposed)

def get_proxmox_client(host=None, ...) -> ProxmoxAPIClient:
    host = host or os.getenv("PROXMOX_HOST")
    verify_ssl = ...
    username = username or os.getenv("PROXMOX_USER")
    password = password or os.getenv("PROXMOX_PASSWORD")
    api_token = api_token or os.getenv("PROXMOX_API_TOKEN")

    # NEW: Keyring fallback when env vars are absent (INJECT-03)
    if not host or (not api_token and not (username and password)):
        from .credential_store import get_credential, list_credentials  # noqa: PLC0415
        registry_entries = list_credentials(credential_type="proxmox")
        if registry_entries:
            entry = registry_entries[0]
            keyring_host = entry["hostname"]
            keyring_username = entry["username"]
            keyring_secret = get_credential(keyring_host, keyring_username, credential_type="proxmox")
            if keyring_secret:
                host = host or keyring_host
                api_token = api_token or keyring_secret
                logger.debug("Auto-injected Proxmox keyring credential for %s", host)

    # Existing validation gates (unchanged)
    if not host:
        raise ValueError("Proxmox host must be provided or set in PROXMOX_HOST env var")
    if not api_token and not (username and password):
        raise ValueError("Must provide either PROXMOX_API_TOKEN or PROXMOX_USER+PROXMOX_PASSWORD")

    return ProxmoxAPIClient(...)
```

### Test Pattern — SSH Keyring Inject (INJECT-01)

```python
# In tests/test_ssh_tools.py

def test_resolve_ssh_credentials_keyring_inject(mocker):
    """INJECT-01: keyring credential auto-injected when no explicit args."""
    from homelab_mcp.ssh_tools import resolve_ssh_credentials

    mocker.patch(
        "homelab_mcp.ssh_tools.list_credentials",
        return_value=[{"hostname": "192.168.1.10", "username": "root", "credential_type": "ssh"}],
    )
    mocker.patch("homelab_mcp.ssh_tools.get_credential", return_value="secret")

    creds = resolve_ssh_credentials("192.168.1.10")

    assert creds.password == "secret"
    assert creds.username == "root"


def test_resolve_ssh_credentials_explicit_overrides_keyring(mocker):
    """INJECT-02: explicit args take precedence over keyring."""
    from homelab_mcp.ssh_tools import resolve_ssh_credentials

    # Keyring would return something — should be ignored
    mocker.patch(
        "homelab_mcp.ssh_tools.list_credentials",
        return_value=[{"hostname": "192.168.1.10", "username": "root", "credential_type": "ssh"}],
    )
    mocker.patch("homelab_mcp.ssh_tools.get_credential", return_value="keyring-secret")

    creds = resolve_ssh_credentials("192.168.1.10", username="admin", password="explicit")

    assert creds.password == "explicit"
    assert creds.username == "admin"
```

### Test Pattern — Proxmox Keyring Fallback (INJECT-03)

```python
# In tests/test_proxmox_api.py

def test_get_proxmox_client_keyring_fallback(mocker, monkeypatch):
    """INJECT-03: keyring used when PROXMOX_HOST and PROXMOX_API_TOKEN env vars absent."""
    from homelab_mcp.proxmox_api import get_proxmox_client

    monkeypatch.delenv("PROXMOX_HOST", raising=False)
    monkeypatch.delenv("PROXMOX_API_TOKEN", raising=False)
    monkeypatch.delenv("PROXMOX_USER", raising=False)
    monkeypatch.delenv("PROXMOX_PASSWORD", raising=False)

    mocker.patch(
        "homelab_mcp.proxmox_api.list_credentials",
        return_value=[{"hostname": "proxmox.local", "username": "root@pam", "credential_type": "proxmox"}],
    )
    mocker.patch("homelab_mcp.proxmox_api.get_credential", return_value="root@pam!mytoken=abc123")

    client = get_proxmox_client()

    assert client.host == "proxmox.local"
    assert client.api_token == "root@pam!mytoken=abc123"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pass credentials in every tool call | Auto-inject from keyring | Phase 19 (this phase) | Users store once, MCP handles the rest |
| SQLite credential table for SSH creds | OS keyring via `credential_store.py` | Phase 17-18 | Headless-safe; passwords never in DB |

**Deprecated/outdated:**
- The SQLite `ssh_credentials` table (`database.py`) is a pre-existing credential store from early development. Phase 19 does NOT remove it — it keeps tier 3 (DB lookup) for backward compatibility. The two systems coexist: keyring is tier 2, DB is tier 3.

---

## Open Questions

1. **Should the keyring tier also check the DB tier username when no registry match exists?**
   - What we know: The keyring registry was populated by `homelab-mcp credentials add`. The DB was populated by the older `register_server` flow.
   - What's unclear: Are there deployments using the DB store that expect keyring injection to work?
   - Recommendation: No. Keyring is for Phase 18 credentials only. DB lookup remains tier 3 for backward compat. Don't conflate the two.

2. **Proxmox host overriding: what if `host` is already set from env but auth is missing?**
   - What we know: The keyring fallback example above preserves an explicitly-set `host` (`host = host or keyring_host`).
   - What's unclear: Should we allow using a keyring host credential for a different env-var host?
   - Recommendation: No. If `PROXMOX_HOST` is set, use it as-is and only fill in the missing auth. Match the keyring entry by `keyring_host == host` in that case, or fall through if no match.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_ssh_tools.py tests/test_proxmox_api.py -x -q` |
| Full suite command | `uv run pytest tests/ -m "not integration" -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| INJECT-01 | SSH tool call with no credentials auto-injects from keyring | unit | `uv run pytest tests/test_ssh_tools.py -k "keyring_inject" -x` | ❌ Wave 0 |
| INJECT-02 | Explicit args override keyring credential | unit | `uv run pytest tests/test_ssh_tools.py -k "explicit_overrides_keyring" -x` | ❌ Wave 0 |
| INJECT-03 | Proxmox client uses keyring when env vars absent | unit | `uv run pytest tests/test_proxmox_api.py -k "keyring_fallback" -x` | ❌ Wave 0 |
| INJECT-03 | Log output after auto-inject does not contain password | unit | `uv run pytest tests/test_ssh_tools.py tests/test_proxmox_api.py -k "no_password_log" -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_ssh_tools.py tests/test_proxmox_api.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -m "not integration" -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_ssh_tools.py` — add `test_resolve_ssh_credentials_keyring_inject` (INJECT-01)
- [ ] `tests/test_ssh_tools.py` — add `test_resolve_ssh_credentials_explicit_overrides_keyring` (INJECT-02)
- [ ] `tests/test_proxmox_api.py` — add `test_get_proxmox_client_keyring_fallback` (INJECT-03)
- [ ] `tests/test_proxmox_api.py` or `tests/test_log_filter.py` — add `test_no_password_in_log_after_inject` (success criterion 4)

Note: test files already exist — new test functions append to existing files.

---

## Sources

### Primary (HIGH confidence)

- `/home/shaun/projects/mcp_python_server/src/homelab_mcp/credential_store.py` — `get_credential()`, `list_credentials()`, `_SERVICE_NAMES` dict, keyring lookup contract
- `/home/shaun/projects/mcp_python_server/src/homelab_mcp/ssh_tools.py` — `resolve_ssh_credentials()` full implementation (lines 35–136), all SSH function signatures
- `/home/shaun/projects/mcp_python_server/src/homelab_mcp/proxmox_api.py` — `get_proxmox_client()` full implementation (lines 189–237), env-var names, `PROXMOX_API_TOKEN` vs requirement text `PROXMOX_TOKEN`
- `/home/shaun/projects/mcp_python_server/src/homelab_mcp/log_filter.py` — `CredentialFilter` redaction patterns, `sanitize_error()` contract
- `/home/shaun/projects/mcp_python_server/src/homelab_mcp/server.py` — `CredentialFilter` attached to root logger at line 55, credential_store module-level imports for monkeypatching

### Secondary (MEDIUM confidence)

- `/home/shaun/projects/mcp_python_server/.planning/STATE.md` — accumulated constraints: lazy keyring import rule, sanitize_error pattern, module-level import rule for credential_store
- `/home/shaun/projects/mcp_python_server/tests/test_credential_store.py` — mock patterns for `keyring.get_password`, `keyring.set_password`, monkeypatch of `_REGISTRY_PATH`

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are in-project, implementations verified by reading source
- Architecture: HIGH — both callsites read in full; inject points are unambiguous
- Pitfalls: HIGH — INJECT-02 regression and PROXMOX_TOKEN naming verified by reading code and requirements
- Test patterns: HIGH — consistent with existing test_credential_store.py patterns, mocker.patch targets confirmed against actual import paths

**Research date:** 2026-03-14
**Valid until:** 2026-04-14 (stable project, no external dependencies added)
