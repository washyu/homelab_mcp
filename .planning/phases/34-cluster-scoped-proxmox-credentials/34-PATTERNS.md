# Phase 34: Cluster-Scoped Proxmox Credentials - Pattern Map

**Mapped:** 2026-04-23
**Files analyzed:** 6 (5 modified + 1 new test file)
**Analogs found:** 6 / 6
**Source of file list:** `34-CONTEXT.md` `<canonical_refs>` / `<code_context>` (no RESEARCH.md — user skipped per decision)

---

## File Classification

| File (new/modified) | Role | Data Flow | Closest Analog | Match Quality |
|---------------------|------|-----------|----------------|---------------|
| `src/homelab_mcp/credential_store.py` (~116-171) | utility / registry | CRUD on JSON + keyring | same file, Phase 33 D-09 `auth_type` field precedent | exact (self-analog) |
| `src/homelab_mcp/proxmox_api.py` — new `resolve_proxmox_credentials()` | service / resolver | async request-response (probe external API) | `src/homelab_mcp/ssh_tools.py::resolve_ssh_credentials` + `_resolve_username_from_registry` | exact (explicit analog in D-09) |
| `src/homelab_mcp/proxmox_api.py::get_proxmox_client` (~190-260) | service factory | sync→async conversion + tier-2 resolver call | same function today + `ssh_tools.py::resolve_ssh_credentials` return-contract | role-match (self-refactor) |
| `src/homelab_mcp/server.py` CLI handlers + argparse (~491-579, ~696-731) | controller / CLI | request-response | same file, existing `_cmd_credentials_add` / argparse with `--key-path` flag (Phase 33 D-09) | exact (self-analog) |
| `src/homelab_mcp/tool_handlers/credential_handlers.py::handle_list_keyring_credentials` | controller / MCP handler | request-response | same function today (D-17a is a one-line display tweak) | exact (self-analog) |
| `tests/test_proxmox_resolver.py` (new) or extension to `tests/test_proxmox_api.py` | test | async unit + caplog | `tests/test_ssh_credentials.py::TestResolveSSHCredentials` | exact (explicit analog in D-13..D-16) |
| Extension to `tests/test_credentials_cli.py` | test | unit | same file, existing `test_credentials_add_proxmox` | exact (self-analog) |

---

## Pattern Assignments

### 1. `src/homelab_mcp/credential_store.py` — extend `register_credential()` / `list_credentials()` for D-01 (`scope` + `cluster_name` fields)

**Analog:** `src/homelab_mcp/credential_store.py` lines 116-171 (itself — Phase 33 D-09 added the `auth_type` field using the same pattern Phase 34 needs to repeat).

**Precedent to copy — backward-readable `.get()` default** (lines 160-171):

```python
def list_credentials(credential_type: str = "ssh") -> list[dict[str, str]]:
    """Return all registry entries for the given credential type.

    Returns:
        List of dicts with keys: ``hostname``, ``username``, ``credential_type``,
        and optionally ``auth_type`` (``"password"`` | ``"key"``) — entries
        written before v1.6 lack this field and should be treated as
        ``"password"`` (use ``.get("auth_type", "password")``).
    """
    return [e for e in _load_registry() if e["credential_type"] == credential_type]
```

Readers use `entry.get("auth_type", "password")` — **Phase 34 readers use `entry.get("scope", "node")` and `entry.get("cluster_name", "")` identically** (D-01).

**Precedent to copy — upsert + `ValueError` validation on new field** (lines 116-150):

```python
def register_credential(
    hostname: str,
    username: str,
    credential_type: str = "ssh",
    auth_type: str = "password",
) -> None:
    """..."""
    if auth_type not in ("password", "key"):
        raise ValueError(f"auth_type must be 'password' or 'key', got {auth_type!r}")
    entries = _load_registry()
    entries = [
        e
        for e in entries
        if not (e["hostname"] == hostname and e["username"] == username and e["credential_type"] == credential_type)
    ]
    entries.append(
        {
            "hostname": hostname,
            "username": username,
            "credential_type": credential_type,
            "auth_type": auth_type,
        }
    )
    _save_registry(entries)
```

**Phase 34 changes to apply:**
- Add keyword-only parameters `scope: str = "node"` and `cluster_name: str = ""`.
- Validate `scope in ("node", "cluster")`. If `scope == "cluster"`, require `cluster_name` non-empty.
- **Upsert key changes for cluster entries:** when `scope == "cluster"`, dedup by `(cluster_name, username, credential_type)` — not `(hostname, username, credential_type)` — per D-08a. Per-node path (`scope == "node"`) keeps existing dedup key.
- Emit the two new fields on every new entry (writers); readers use `.get("scope", "node")` + `.get("cluster_name", "")` for back-compat with legacy v1.3/v1.4 rows (D-01).

---

### 2. `src/homelab_mcp/proxmox_api.py` — new `resolve_proxmox_credentials()` function (D-09, D-10, D-11)

**Analog:** `src/homelab_mcp/ssh_tools.py::_resolve_username_from_registry` (lines 40-74) + `resolve_ssh_credentials` (lines 77-189). Explicit analog called out in CONTEXT.md D-09.

**Imports pattern to mirror** (ssh_tools.py lines 1-15):

```python
import logging
from dataclasses import dataclass  # optional — Proxmox may not need a dataclass return
from typing import Any

from .credential_store import get_credential, list_credentials
from .log_filter import sanitize_error

logger = logging.getLogger(__name__)
```

Proxmox-side: `resolve_proxmox_credentials` lives alongside `get_proxmox_client` in `proxmox_api.py` (planner-preferred per Claude's Discretion bullet in CONTEXT.md), so the imports above are already present (see proxmox_api.py lines 8-17). Only add whatever `Literal` / `TYPE_CHECKING` helpers the new signature needs.

**CredentialNotFoundError reuse:**

`CredentialNotFoundError` is defined in `ssh_tools.py` line 24:

```python
class CredentialNotFoundError(RuntimeError):
    """Raised when no credentials are found for a hostname in any tier."""
```

CONTEXT.md `<code_context>` → **Reusable Assets** says Phase 34 uses the same class (or adds a Proxmox-specific subclass if planner prefers). Easiest path: import from `.ssh_tools` inside `proxmox_api.py`, or lift the class to a shared module. Either works — planner picks.

**Two-tier resolver contract to mirror** (ssh_tools.py lines 77-189, the D-04 registry-scan structure):

```python
def resolve_ssh_credentials(
    hostname: str,
    username: str | None = None,
    password: str | None = None,
    key_path: str | None = None,
    port: int = 22,
) -> SSHCredentials:
    """Resolve SSH credentials for a hostname.

    Two-tier resolution (v1.6, Phase 33 / Phase 33.1):
      1. **Explicit args** (``password`` or ``key_path`` supplied): returned directly...
      2. **Keyring registry**: look up by hostname; when ``username`` is ``None``...
    """
    # Tier 1: explicit args
    if password or key_path:
        ...
        return SSHCredentials(...)

    # Tier 2: Keyring — sole remaining fallback.
    if username is None:
        resolved_username, matched = _resolve_username_from_registry(hostname)
    else:
        registry_entries = list_credentials(credential_type="ssh")
        matched = [e for e in registry_entries if e["hostname"] == hostname and e["username"] == username]
        resolved_username = username

    if matched:
        stored_username = matched[0]["username"]
        auth_type = matched[0].get("auth_type", "password")  # D-09 backward compat
        ...
        keyring_password = get_credential(hostname, stored_username, credential_type="ssh")
        if keyring_password:
            logger.debug(
                "Auto-injected keyring password credential for %s (user: %s)",
                hostname,
                stored_username,
            )
            return SSHCredentials(...)

    # Terminal: no credential anywhere. Actionable error (D-05).
    raise CredentialNotFoundError(
        f"No credentials found for {hostname}. "
        f"Run `homelab-mcp credentials add {hostname} {username or '<username>'}` "
        "in your terminal."
    )
```

**Registry-scan-on-miss pattern — THE load-bearing analog for Phase 34 D-04 cluster walk** (ssh_tools.py lines 40-74):

```python
def _resolve_username_from_registry(hostname: str) -> tuple[str, list[dict[str, str]]]:
    """Scan the keyring registry for ``hostname``; return (resolved_username, matched_entries).

    Behaviour:
      * **Single match** → returns the one registered ``username`` plus the
        matched entry list (for downstream ``auth_type`` branching).
      * **Zero match** → raises :class:`CredentialNotFoundError` with the
        standard ``homelab-mcp credentials add`` pointer.
      * **Multiple matches** → raises :class:`CredentialNotFoundError` whose
        message names every registered username and points the agent at
        ``list_keyring_credentials`` / ``list_registered_servers`` so it can
        self-disambiguate (D-04a).
    """
    registry_entries = list_credentials(credential_type="ssh")
    matched = [e for e in registry_entries if e["hostname"] == hostname]
    if len(matched) == 0:
        raise CredentialNotFoundError(
            f"No credentials found for {hostname}. "
            f"Run `homelab-mcp credentials add {hostname} <username>` "
            "in your terminal."
        )
    if len(matched) >= 2:
        registered = ", ".join(sorted(e["username"] for e in matched))
        raise CredentialNotFoundError(
            f"Multiple credentials registered for {hostname}: {registered}. "
            "Specify username explicitly, or call list_keyring_credentials "
            "to inspect registered entries."
        )
    return matched[0]["username"], matched
```

**Phase 34 cluster-walk translation of this pattern (D-04 / D-10):**

- **Tier 1 (per-node short-circuit):** `matched = [e for e in list_credentials("proxmox") if e.get("scope", "node") == "node" and e["hostname"] == host]`. If a match exists, return `(api_token, "node", None)` **without calling `/cluster/status`** (D-10 bullet 1 short-circuit; Success Criterion 5 requires this).
- **Tier 2 (cluster walk):** iterate `cluster_entries = [e for e in list_credentials("proxmox") if e.get("scope", "node") == "cluster"]`; for each, retrieve its token via `get_credential(cluster_name, username, credential_type="proxmox")` under the `f"{username}@cluster:{cluster_name}"` keyring key (D-03), issue a `GET /cluster/status` probe against `host`, and match when response has a `type=cluster` row whose `name` equals the entry's `cluster_name`. Log at DEBUG per D-11 per-tier (see log format below). First match wins (D-04).
- **Cache:** a module-level `_HOST_CLUSTER_CACHE: dict[str, str] = {}` populated on successful match, checked first in Tier 2 (D-05a). Plain dict is fine (Claude's Discretion in CONTEXT.md).
- **Standalone error:** if Tier 2 walk produces no match, raise `CredentialNotFoundError` that (a) names the cluster entries tried, (b) includes `credentials add --type proxmox` (D-05, D-15). Follow ssh_tools line 185-189 message shape.

**Debug log pattern** (ssh_tools.py lines 145-149, 159-163):

```python
logger.debug(
    "Auto-injected keyring key-path credential for %s (user: %s)",
    hostname,
    stored_username,
)
```

D-11 extends this to one record per tier attempt plus a terminal record naming `source=node|cluster`. Exact wording is Claude's Discretion per CONTEXT.md.

**Desync warning pattern** (ssh_tools.py lines 171-179) — reuse verbatim when a registry cluster entry exists but `get_credential` returns `None`:

```python
logger.warning(
    "Credential desync for %s (user: %s): registry entry exists but keyring "
    "returned None — re-run 'homelab-mcp credentials add %s %s' to restore",
    hostname,
    stored_username,
    hostname,
    stored_username,
)
```

For cluster entries, substitute `hostname` with `f"cluster:{cluster_name}"` in the log fields and the `credentials add` pointer becomes `credentials add --type proxmox --scope cluster:<name> <token_id>`.

---

### 3. `src/homelab_mcp/proxmox_api.py::get_proxmox_client` — sync→async conversion + INJECT-03 shortcut deletion (D-12)

**Analog:** the function as it stands today (lines 190-260) — D-12 deletes lines 224-242 and wraps the rest in `async def`.

**Current shortcut block to DELETE (D-12)** (lines 224-242 verbatim):

```python
    # Keyring fallback (INJECT-03): only when env vars are insufficient
    # Single-homelab assumption: if PROXMOX_HOST is absent, take first registry entry.
    # If PROXMOX_HOST is set but auth is missing, match by host (or skip if no match).
    if not host or (not api_token and not (username and password)):
        registry_entries = list_credentials(credential_type="proxmox")
        if registry_entries:
            entry = registry_entries[0]
            keyring_host = entry["hostname"]
            keyring_username = entry["username"]
            # Only use this entry if: no host set, OR the env host matches the entry host
            if not host or host == keyring_host:
                keyring_secret = get_credential(keyring_host, keyring_username, credential_type="proxmox")
                if keyring_secret:
                    host = host or keyring_host
                    # Proxmox API tokens use "user@realm!tokenid=secret" format.
                    # The registry username holds the token ID (e.g. root@pam!mcp_test),
                    # the keyring holds the secret UUID.
                    api_token = api_token or f"{keyring_username}={keyring_secret}"
                    logger.debug("Auto-injected Proxmox keyring credential for %s", host)
```

**Replacement structure to write:**

```python
async def get_proxmox_client(
    host: str | None = None,
    port: int = 8006,
    verify_ssl: bool | None = None,
    username: str | None = None,
    password: str | None = None,
    api_token: str | None = None,
    session: aiohttp.ClientSession | None = None,
) -> ProxmoxAPIClient:
    # env-var pickup stays unchanged (lines 215-222).
    host = host or os.getenv("PROXMOX_HOST")
    if verify_ssl is None:
        verify_ssl = os.getenv("PROXMOX_VERIFY_SSL", "true").lower() != "false"
    username = username or os.getenv("PROXMOX_USER")
    password = password or os.getenv("PROXMOX_PASSWORD")
    api_token = api_token or os.getenv("PROXMOX_API_TOKEN")

    # NEW: resolver call when host known but auth missing (D-10).
    if host and not api_token and not (username and password):
        api_token, scope, cluster_name = await resolve_proxmox_credentials(host, session=session)
        logger.debug("Proxmox resolver source=%s cluster=%s", scope, cluster_name)

    # Validation gates (unchanged — D-12 error message names PROXMOX_HOST).
    if not host:
        raise ValueError("Proxmox host must be provided or set in PROXMOX_HOST env var")
    if not api_token and not (username and password):
        raise ValueError("Must provide either PROXMOX_API_TOKEN or PROXMOX_USER+PROXMOX_PASSWORD")

    return ProxmoxAPIClient(...)
```

**Async call-site propagation** — all callers already `async def`, so converting to `await get_proxmox_client(...)` is mechanical. Existing callers (lines 279, 318, 357, 401, ~422+): every `client = get_proxmox_client(host=host, session=session)` becomes `client = await get_proxmox_client(host=host, session=session)`. No sync→async boundary crossing new — noted in CONTEXT.md `<code_context>` → Established Patterns.

**Session reuse pattern** — the new resolver's `/cluster/status` probe reuses the shared `session=` parameter already threaded through `get_proxmox_client` (CONTEXT.md `<code_context>` → Reusable Assets #3). Pattern from proxmox_api.py lines 121-128:

```python
if self._shared_session is not None:
    return await self._do_request(self._shared_session, method, url, data, params)
else:
    connector = aiohttp.TCPConnector(ssl=self.verify_ssl)
    async with aiohttp.ClientSession(connector=connector) as session:
        return await self._do_request(session, method, url, data, params)
```

Resolver does the same branching when probing `/cluster/status`. Simpler: construct a **throwaway** `ProxmoxAPIClient(host=host, api_token=candidate_token, session=session)` per candidate cluster entry and call `await client.get("/cluster/status")` — all the auth header / session logic is already on `ProxmoxAPIClient`. This reuses existing code with zero new HTTP plumbing.

---

### 4. `src/homelab_mcp/server.py` CLI — `--scope cluster:<name>` argparse + handler branches (D-06, D-07, D-08)

**Analog:** same file, existing `_cmd_credentials_add` (lines 491-548) and argparse setup (lines 696-721). Phase 33 D-09's `--key-path` flag shows the exact pattern for "conditional flag that changes handler branch".

**Existing argparse pattern for `add` subparser** (lines 696-721):

```python
# credentials add <hostname> <username> [--type ssh|proxmox] [--key-path PATH]
add_p = cred_sub.add_parser(
    "add",
    help="Store a credential (upsert — re-run to replace an existing entry)",
    description=(
        "Store a credential in the OS keyring. This is upsert behavior: re-running "
        "`add` for the same (hostname, username, type) replaces the existing secret "
        "and its auth_type. There is no separate `update` subcommand — `add` is it."
    ),
)
add_p.add_argument("hostname")
add_p.add_argument("username")
add_p.add_argument("--type", choices=["ssh", "proxmox"], default="ssh", dest="credential_type")
add_p.add_argument(
    "--key-path",
    dest="key_path",
    default=None,
    metavar="PATH",
    help=(...),
)
add_p.set_defaults(func=_cmd_credentials_add)
```

**Existing handler branch pattern for `--key-path`** (lines 503-529) — **copy this branching shape for `--scope cluster:*`**:

```python
credential_type: str = args.credential_type
key_path: str | None = getattr(args, "key_path", None)

if key_path is not None:
    # Key-path auth branch (D-09). Strict validation.
    if credential_type != "ssh":
        print(
            f"Error: --key-path is only valid with --type ssh (got {credential_type!r})",
            file=sys.stderr,
        )
        sys.exit(1)
    ...
    auth_type = "key"
else:
    prompt = "Token/Password: " if credential_type == "proxmox" else "Password: "
    secret = getpass.getpass(prompt)
    if not secret:
        print("Error: empty password rejected", file=sys.stderr)
        sys.exit(1)
    auth_type = "password"
```

**Phase 34 translation — the conditional-positional pattern:**

For D-06 (add) / D-07 (remove), when `--scope cluster:<cluster_name>` is present the positional `<hostname>` is dropped. CONTEXT.md says "subparsers vs post-parse validation both acceptable" (Claude's Discretion). The **simplest** option that matches the key-path precedent: keep `hostname` as `nargs="?"` positional and **post-parse validate**:

- If `--scope cluster:*` present: require `hostname is None`, parse `cluster_name` out of the scope string, set registry `hostname=""` (D-02), call `register_credential(..., scope="cluster", cluster_name=cluster_name)`, store keyring secret at key `f"{username}@cluster:{cluster_name}"` (D-03).
- If `--scope cluster:*` absent (or `--scope node`): require `hostname` non-None, existing per-node path unchanged.
- Validation errors follow the existing stderr/exit-1 shape:

```python
print(
    f"Error: --key-path is only valid with --type ssh (got {credential_type!r})",
    file=sys.stderr,
)
sys.exit(1)
```

**Existing `_cmd_credentials_list` pattern to extend for D-08 grouped output** (lines 551-560):

```python
def _cmd_credentials_list(args: argparse.Namespace) -> None:
    """Handle `homelab-mcp credentials list [--type ssh|proxmox]`."""
    credential_type: str = args.credential_type
    entries = list_credentials(credential_type=credential_type)
    if not entries:
        print(f"No stored {credential_type} credentials.")
        return
    print(f"Stored {credential_type} credentials:")
    for entry in entries:
        print(f"  {entry['username']}@{entry['hostname']}")
```

**Phase 34 D-08 grouped-output translation:**

```python
node_entries = [e for e in entries if e.get("scope", "node") == "node"]
cluster_entries = [e for e in entries if e.get("scope") == "cluster"]
print(f"Stored {credential_type} credentials:")
if node_entries:
    print("  Per-node:")
    for e in node_entries:
        print(f"    {e['username']}@{e['hostname']}")
if cluster_entries:
    print("  Cluster-scoped:")
    for e in cluster_entries:
        print(f"    {e['username']}@cluster:{e['cluster_name']}")
```

D-08 says "when only one scope has entries, only that section renders" — the `if node_entries:` / `if cluster_entries:` guards above satisfy this.

**Epilog help text update** (lines 621-638): existing `Examples:` block gets three new lines following the same 2-column padded format:

```
  uvx homelab-mcp credentials add --type proxmox --scope cluster:<name> <token_id>  # store cluster-scoped Proxmox token
  uvx homelab-mcp credentials remove --type proxmox --scope cluster:<name>          # remove cluster-scoped Proxmox credential
```

---

### 5. `src/homelab_mcp/tool_handlers/credential_handlers.py::handle_list_keyring_credentials` — D-17a display tweak

**Analog:** the function as it exists today (lines 25-35):

```python
async def handle_list_keyring_credentials(arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle list_keyring_credentials tool."""
    credential_type = arguments.get("credential_type", "ssh")
    entries = list_credentials(credential_type=credential_type)
    result = {
        "status": "success",
        "credential_type": credential_type,
        "count": len(entries),
        "credentials": [{"hostname": e["hostname"], "username": e["username"]} for e in entries],
    }
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
```

**Phase 34 D-17a translation — one-line branch in the list comprehension** (no schema change, handler-internal string format only):

```python
"credentials": [
    {
        "hostname": (
            f"cluster:{e['cluster_name']}"
            if e.get("scope") == "cluster"
            else e["hostname"]
        ),
        "username": e["username"],
    }
    for e in entries
],
```

CONTEXT.md D-17a explicitly says: "a one-line branch in the handler covers it" and this is NOT a schema/annotation/openapi lock-step change. Planner should confirm during implementation whether the current shape already distinguishes them via `hostname == ""` — if so, the cluster entry's `hostname=""` (per D-02) would render as empty string, which is ambiguous, so the branch above is the safer option.

---

### 6. Tests — `resolve_proxmox_credentials` unit tests (D-13, D-14, D-15, D-16)

**Analog:** `tests/test_ssh_credentials.py::TestResolveSSHCredentials` (lines 27-194). The class structure, `@patch("src.homelab_mcp.ssh_tools.list_credentials")` + `@patch("src.homelab_mcp.ssh_tools.get_credential")` decorator pattern, and `caplog` usage are directly reusable. Swap the import path to `src.homelab_mcp.proxmox_api` and the test skeletons transfer 1:1.

**Imports pattern to copy** (tests/test_ssh_credentials.py lines 12-24):

```python
import json
import logging
from unittest.mock import AsyncMock, patch

import pytest

from src.homelab_mcp.ssh_tools import (
    CredentialNotFoundError,
    SSHCredentials,
    list_registered_servers,
    register_server,
    resolve_ssh_credentials,
)
```

**D-13 analog — single keyring-backed match** (test_ssh_credentials.py lines 55-69):

```python
@patch("src.homelab_mcp.ssh_tools.list_credentials")
@patch("src.homelab_mcp.ssh_tools.get_credential")
def test_resolve_keyring_password_auth(self, mock_get_cred, mock_list_creds):
    """D-16: resolve_ssh_credentials returns keyring-backed password credential."""
    mock_list_creds.return_value = [
        {"hostname": "192.168.1.100", "username": "admin", "credential_type": "ssh", "auth_type": "password"}
    ]
    mock_get_cred.return_value = "secret_password"

    creds = resolve_ssh_credentials(hostname="192.168.1.100", username="admin")

    assert isinstance(creds, SSHCredentials)
    assert creds.password == "secret_password"
    assert creds.key_path is None
    assert creds.username == "admin"
```

**D-13 Phase 34 translation** — add a `/cluster/status` mock via `aioresponses()` (already established by test_proxmox_api.py line 12 import + lines 129-140 example) when a cluster registry entry exists but no per-node entry matches. Assert `(token, "cluster", "homelab-prod")` returned.

**aioresponses pattern to copy** (tests/test_proxmox_api.py lines 129-140):

```python
with aioresponses() as mocked:
    mocked.post(
        "https://192.168.1.100:8006/api2/json/access/ticket",
        payload={"data": {"ticket": "...", "CSRFPreventionToken": "..."}},
        status=200,
    )
    # ... test code
```

Phase 34 uses `mocked.get("https://pve1.home:8006/api2/json/cluster/status", payload={"data": [{"type": "cluster", "name": "homelab-prod"}]}, status=200)`.

**D-14 analog — precedence / short-circuit spy** (no direct 1:1 analog in current tests, but the pattern is: mock `aioresponses` so the cluster endpoint is **set up** but, when the test passes, it must NEVER be requested; assert via `aioresponses`' recorded calls list or a separate `AsyncMock` spy on `ProxmoxAPIClient.get` that the short-circuit skipped it).

Closest shape is the existing `get_credential`-not-called assertion pattern — translate to an `aioresponses` "registered-but-never-called" assertion: `assert not mocked.requests` or use `mocked._responses` count.

**D-15 analog — standalone error** (test_ssh_credentials.py lines 86-91):

```python
@patch("src.homelab_mcp.ssh_tools.list_credentials")
def test_mcp_admin_no_fallback(self, mock_list_creds):
    """D-17: resolve_ssh_credentials raises CredentialNotFoundError for mcp_admin with empty keyring."""
    mock_list_creds.return_value = []
    with pytest.raises(CredentialNotFoundError) as exc_info:
        resolve_ssh_credentials(hostname="any-host", username="mcp_admin")
    assert "credentials add" in str(exc_info.value)
```

**D-15 Phase 34 translation** — mock `list_credentials("proxmox")` to return one cluster entry; mock `/cluster/status` to return a payload **without** a `type=cluster` row; assert `CredentialNotFoundError` raised; message contains `credentials add --type proxmox` AND names the cluster entry tried (per D-05).

**D-16 analog — caplog DEBUG assertion** (test_ssh_credentials.py lines 117-129):

```python
@patch("src.homelab_mcp.ssh_tools.list_credentials")
@patch("src.homelab_mcp.ssh_tools.get_credential")
def test_desync_warning_logged(self, mock_get_cred, mock_list_creds, caplog):
    """When registry has entry but keyring returns None, a WARNING containing 'desync' is logged."""
    mock_list_creds.return_value = [{"hostname": "desync-host", "username": "alice", "credential_type": "ssh"}]
    mock_get_cred.return_value = None

    with caplog.at_level(logging.WARNING, logger="homelab_mcp.ssh_tools"):
        with pytest.raises(CredentialNotFoundError):
            resolve_ssh_credentials("desync-host")

    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING and "desync" in r.message.lower()]
    assert len(warning_records) >= 1, "Expected a WARNING log containing 'desync'"
    assert "desync-host" in warning_records[0].message
```

**D-16 Phase 34 translation** — `caplog.at_level(logging.DEBUG, logger="homelab_mcp.proxmox_api")`; run the D-13 scenario; assert the record stream contains both a `tier=node MISS` line AND a `tier=cluster MATCH` line AND a terminal `source=cluster` line. For the D-14 scenario (precedence), assert exactly one terminal `source=node` line AND no `tier=cluster` records.

---

### 7. Tests — cluster add/list/remove CLI flow (extension to `tests/test_credentials_cli.py`)

**Analog:** same file, `test_credentials_add_proxmox` (lines 201-222), `test_credentials_list_proxmox` (lines 225-239), `test_credentials_remove_proxmox` (lines 242-264) — all three transfer 1:1 with the added `args.scope = "cluster:homelab-prod"` attribute and the assertion that output/behavior follows D-06/D-07/D-08.

**Test scaffolding pattern to copy** (lines 201-222):

```python
def test_credentials_add_proxmox(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """credentials add --type proxmox stores proxmox credential and prints success."""
    import getpass  # noqa: PLC0415

    from homelab_mcp.server import _cmd_credentials_add  # noqa: PLC0415

    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "pw")
    monkeypatch.setattr(
        "homelab_mcp.server.store_credential",
        lambda hostname, username, password, credential_type="ssh": True,
    )
    monkeypatch.setattr(
        "homelab_mcp.server.register_credential",
        lambda hostname, username, credential_type="ssh", auth_type="password": None,
    )
    args = argparse.Namespace(hostname="pxhost", username="pxuser", credential_type="proxmox")
    _cmd_credentials_add(args)
    captured = capsys.readouterr()
    assert "Stored proxmox credential for pxuser@pxhost" in captured.out
```

**Phase 34 translation:** new test `test_credentials_add_cluster_scope`. The `register_credential` monkeypatch signature must accept the new `scope` / `cluster_name` kwargs. `args = argparse.Namespace(hostname=None, username="root@pam!tok", credential_type="proxmox", scope="cluster:homelab-prod")`. Assert success message references `cluster:homelab-prod`.

For D-08 list grouping: separate test where `list_credentials` mock returns both a per-node entry and a cluster entry; assert both `Per-node:` and `Cluster-scoped:` section headers appear AND the cluster entry renders as `<user>@cluster:homelab-prod`.

---

## Shared Patterns

### Lazy keyring import (CRITICAL — D-03 new keyring key form)

**Source:** `src/homelab_mcp/credential_store.py` lines 25-45

**Apply to:** any new code path that touches the keyring — including the new cluster-key-form read inside `resolve_proxmox_credentials`.

```python
def store_credential(hostname: str, username: str, password: str, credential_type: str = "ssh") -> bool:
    service_name = _SERVICE_NAMES.get(credential_type, _SERVICE_NAME)
    try:
        import keyring  # noqa: PLC0415
        import keyring.errors  # noqa: PLC0415

        keyring.set_password(service_name, f"{username}@{hostname}", password)
        return True
    except keyring.errors.NoKeyringError:
        logger.warning("OS keyring unavailable (headless host) — credential not stored for %s", hostname)
        return False
    ...
```

Phase 34 cluster-scoped read becomes `get_credential(cluster_name, username, credential_type="proxmox")` with an **internal branch** inside `credential_store.py` that emits the `f"{username}@cluster:{cluster_name}"` keyring key form when the caller flags the entry as cluster-scoped. Alternative: add a new kwarg `scope="cluster"` to `get_credential/store_credential/delete_credential` that flips the key format. Planner picks — either preserves the lazy-import pattern.

**CONTEXT.md `<code_context>` → Established Patterns #1** calls this out explicitly as **must-preserve** for headless-Linux D-Bus safety.

### Backward-readable `.get()` default on new registry fields

**Source:** `src/homelab_mcp/credential_store.py` docstring lines 160-171 + existing reader in `ssh_tools.py` line 140:

```python
auth_type = matched[0].get("auth_type", "password")  # D-09 backward compat
```

**Apply to:** every reader of the registry that touches the new `scope` / `cluster_name` fields in Phase 34:

- `scope = e.get("scope", "node")` — legacy v1.3/v1.4 per-node Proxmox entries AND every SSH entry.
- `cluster_name = e.get("cluster_name", "")` — same back-compat reason.

### Actionable `CredentialNotFoundError` message shape

**Source:** `src/homelab_mcp/ssh_tools.py` lines 62-66, 69-73, 185-189.

**Apply to:** every raise site in the new Proxmox resolver.

Message must:
1. Name the concrete problem (no credential for host X / cluster entries Y, Z tried and missed).
2. Name the exact CLI fix — `homelab-mcp credentials add --type proxmox ...`.
3. For multi-match / walk-missed cases, point the agent at `list_keyring_credentials` so it can self-disambiguate (the D-04a pattern).

### Debug log format

**Source:** `src/homelab_mcp/ssh_tools.py` lines 145-163.

Single DEBUG record per tier outcome using `logger.debug("...%s...", fields)` (lazy format — never f-strings for log args). Phase 34 D-11 follows this shape; exact wording is Claude's Discretion per CONTEXT.md.

### `aioresponses` for Proxmox HTTP mocking

**Source:** `tests/test_proxmox_api.py` line 12 import, lines 129-140 mock setup.

**Apply to:** every Phase 34 resolver test that needs to stub `/cluster/status`. This is the established test-side pattern in the codebase and works with the existing `ProxmoxAPIClient` session logic.

### `caplog.at_level(logging.X, logger="homelab_mcp.Y")` scoped assertion

**Source:** `tests/test_ssh_credentials.py` lines 117-129.

**Apply to:** D-16 debug-log assertions. Use `logger="homelab_mcp.proxmox_api"` to scope the log capture to the resolver's logger.

---

## No Analog Found

None. Every file in the Phase 34 change set has a direct analog either in itself (self-refactor with additive field/branch) or in the Phase 33 / 33.1 surface (`ssh_tools.resolve_ssh_credentials`, `_resolve_username_from_registry`).

---

## Metadata

**Analog search scope:**
- `src/homelab_mcp/credential_store.py` (full)
- `src/homelab_mcp/ssh_tools.py` (lines 1-200 — resolver + `_resolve_username_from_registry`)
- `src/homelab_mcp/proxmox_api.py` (lines 1-430 — client + `get_proxmox_client` + call sites)
- `src/homelab_mcp/server.py` (lines 480-740 — CLI handlers + argparse)
- `src/homelab_mcp/tool_handlers/credential_handlers.py` (full)
- `tests/test_ssh_credentials.py` (lines 1-200 — `TestResolveSSHCredentials`)
- `tests/test_credentials_cli.py` (full)
- `tests/test_credential_store.py` (lines 125-205 — registry tests)
- `tests/test_proxmox_api.py` (lines 1-220 — client tests + `aioresponses` usage)

**Pattern extraction date:** 2026-04-23
**Files scanned:** 9
**Strong matches found:** 6 / 6 (stopped search per critical-rule: enough strong matches)
