# Phase 18: Credentials CLI + --version - Research

**Researched:** 2026-03-14
**Domain:** Python argparse subcommands, getpass, keyring enumeration gap, credential registry, importlib.metadata
**Confidence:** HIGH

## Summary

Phase 18 adds two things to `main()` in `server.py`: (1) a `credentials` subcommand group with `add`, `list`, and `remove` actions, and (2) a `--version` flag. Both are pure argparse additions. The credential operations delegate to the existing `credential_store.py` (Phase 17) for keyring reads/writes, and to a new lightweight **credential registry** for list support.

The critical design discovery for this phase: `keyring` has no enumeration API. `keyring.get_keyring()` exposes no `list_all_items()` or similar method, and the keyring maintainer explicitly confirmed this is by design (jaraco/keyring#151). This means `credentials list` cannot be backed by keyring alone. The solution is a small JSON registry file (`~/.homelab_mcp/credential_registry.json`) that records `(hostname, username, credential_type)` tuples. `credential_store.py` gains three new functions: `register_credential`, `unregister_credential`, and `list_credentials`. The keyring continues to hold passwords; the registry only holds metadata safe to store in plaintext.

The `--version` flag is a one-liner using `argparse`'s built-in `action='version'` with the version string pulled from the already-present `_get_version()` helper in `server.py`. The `--version` requirement is the simplest item in this phase.

**Primary recommendation:** Extend `credential_store.py` with a JSON registry for list support; extend `main()` in `server.py` with argparse subparsers using `set_defaults(func=...)` dispatch; keep server startup unchanged for bare `homelab-mcp` invocation.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CRED-01 | User can store SSH credentials for a host with `homelab-mcp credentials add <host> <user>` (password prompted securely, never via CLI arg) | argparse subparser `credentials add <host> <user>`; `getpass.getpass()` for secure password input; `credential_store.store_credential()` for keyring write; `register_credential()` for registry write |
| CRED-02 | User can list stored SSH credential hostnames with `homelab-mcp credentials list` | `credential_store.list_credentials(credential_type='ssh')` returns `[(hostname, username)]` from JSON registry file |
| CRED-03 | User can remove stored SSH credentials with `homelab-mcp credentials remove <host>` | argparse subparser `credentials remove <host>`; `credential_store.delete_credential()` for keyring delete; `unregister_credential()` for registry cleanup |
| CRED-04 | User can store Proxmox credentials with `homelab-mcp credentials add --type proxmox <host> <user>` (token/password prompted securely) | Same `add` subparser with `--type proxmox`; keyring service name `"homelab-mcp-proxmox"` to namespace Proxmox separately from SSH |
| CRED-05 | User can list stored Proxmox credential hosts with `homelab-mcp credentials list --type proxmox` | `list_credentials(credential_type='proxmox')` against same JSON registry, filtered by type |
| CRED-06 | User can remove stored Proxmox credentials with `homelab-mcp credentials remove --type proxmox <host>` | `delete_credential()` with proxmox service name; `unregister_credential()` with `credential_type='proxmox'` |
| CLI-01 | `homelab-mcp --version` prints the installed package version | `parser.add_argument('--version', action='version', version=f'%(prog)s {_get_version()}')` — one-liner using existing `_get_version()` helper |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| argparse | stdlib | Subcommand dispatch + `--version` flag | Already used in `server.py main()`; stdlib, no extra deps |
| getpass | stdlib | Secure password prompting (no echo) | Python standard; reads from `/dev/tty` not stdin — survives piped input |
| json | stdlib | Credential registry persistence | Simplest serialization; credentials metadata is small flat list |
| pathlib | stdlib | Registry file path construction | Already used throughout project |
| keyring | >=25.6.0 | Actual password storage (Phase 17) | Already promoted to core deps in Phase 17 |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| importlib.metadata | stdlib | Version string for `--version` | `_get_version()` already exists in `server.py` — reuse it |
| logging | stdlib | Warnings in credential_store registry functions | Already established pattern in credential_store |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| JSON registry file | Existing `ssh_credentials` SQLite table | SQLite table is for network discovery, has complex schema, no `credential_type` column, requires `DatabaseAdapter` instantiation; JSON file is simpler and self-contained for CLI use |
| JSON registry file | New SQLite table | Adds migration complexity (Phase 17 already added `credential_store.py`); JSON is sufficient and readable |
| Separate Proxmox service name | Same service name with type prefix in username | Separate service names (`"homelab-mcp"` vs `"homelab-mcp-proxmox"`) are cleaner in keyring UIs and prevent key collisions |

**Installation:** No new packages. All stdlib. `credential_store.py` extended in-place.

---

## Architecture Patterns

### Recommended Project Structure

```
src/homelab_mcp/
├── credential_store.py    # Extended: add register_credential, unregister_credential, list_credentials
├── server.py              # Extended: main() gets --version + credentials subcommand
tests/
├── test_credential_store.py  # Extended: cover new registry functions
└── test_credentials_cli.py   # New: CLI integration tests via monkeypatch + capsys
```

### Pattern 1: argparse set_defaults Dispatch (avoids bare `homelab-mcp` regression)

**What:** Top-level parser has `set_defaults(func=_run_stdio_wrapper)`. Subparsers each set their own `func`. Dispatch is `getattr(args, 'func', _run_stdio_wrapper)(args)`.

**When to use:** Adding any subcommand to an existing entry-point CLI.

**Example:**
```python
# Source: STATE.md locked decision + argparse official docs
# Inside main() — runs as local imports per project pattern (PLC0415)
parser = argparse.ArgumentParser(...)

# Existing flags unchanged
parser.add_argument("--http", ...)
parser.add_argument("--port", ...)
# ... other existing flags ...

# NEW: --version
parser.add_argument(
    "--version",
    action="version",
    version=f"%(prog)s {_get_version()}",  # _get_version() already defined at module level
)

# NEW: set_defaults so bare `homelab-mcp` still runs the server
parser.set_defaults(func=_run_stdio_wrapper)

# NEW: credentials subcommand
sub = parser.add_subparsers(dest="command")
cred_p = sub.add_parser("credentials", help="Manage stored credentials")
cred_p.set_defaults(func=_run_stdio_wrapper)  # bare `homelab-mcp credentials` shows help

cred_sub = cred_p.add_subparsers(dest="cred_action")

# credentials add <host> <user> [--type ssh|proxmox]
add_p = cred_sub.add_parser("add", help="Store a credential")
add_p.add_argument("host")
add_p.add_argument("user")
add_p.add_argument("--type", choices=["ssh", "proxmox"], default="ssh")
add_p.set_defaults(func=_cmd_credentials_add)

# credentials list [--type ssh|proxmox]
list_p = cred_sub.add_parser("list", help="List stored credential hostnames")
list_p.add_argument("--type", choices=["ssh", "proxmox"], default="ssh")
list_p.set_defaults(func=_cmd_credentials_list)

# credentials remove <host> [--type ssh|proxmox]
remove_p = cred_sub.add_parser("remove", help="Remove a stored credential")
remove_p.add_argument("host")
remove_p.add_argument("--type", choices=["ssh", "proxmox"], default="ssh")
remove_p.set_defaults(func=_cmd_credentials_remove)

args = parser.parse_args()

# Dispatch — existing if/else server logic moved into _run_stdio_wrapper
getattr(args, "func", _run_stdio_wrapper)(args)
```

**Key:** `_run_stdio_wrapper` encapsulates the existing `if args.http: ... else: asyncio.run(_run_stdio())` logic. `parser.set_defaults(func=_run_stdio_wrapper)` ensures bare `homelab-mcp` is identical to today.

### Pattern 2: Credential Registry — JSON File in ~/.homelab_mcp/

**What:** A simple JSON file at `~/.homelab_mcp/credential_registry.json` records credential metadata. No passwords stored. New functions added to `credential_store.py`.

**When to use:** Any operation requiring enumeration of stored credentials.

**Example:**
```python
# Source: project design constraint — keyring has no list API (jaraco/keyring#151)
# Inside credential_store.py — same constraints apply: only stdlib imports at module level

_REGISTRY_PATH_DEFAULT = pathlib.Path.home() / ".homelab_mcp" / "credential_registry.json"
# NOTE: pathlib is stdlib — acceptable module-level import (not keyring)

def _load_registry() -> list[dict[str, str]]:
    """Load credential registry from JSON file. Returns empty list if missing."""
    path = _REGISTRY_PATH_DEFAULT
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return []

def _save_registry(entries: list[dict[str, str]]) -> None:
    """Persist credential registry to JSON file."""
    path = _REGISTRY_PATH_DEFAULT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2))

def register_credential(hostname: str, username: str, credential_type: str = "ssh") -> None:
    """Record credential metadata in the registry (no password stored here)."""
    entries = _load_registry()
    # Upsert: replace existing entry for same (hostname, username, type)
    entries = [
        e for e in entries
        if not (e["hostname"] == hostname and e["username"] == username
                and e["credential_type"] == credential_type)
    ]
    entries.append({"hostname": hostname, "username": username, "credential_type": credential_type})
    _save_registry(entries)

def unregister_credential(hostname: str, credential_type: str = "ssh") -> None:
    """Remove all entries for hostname+type from the registry."""
    entries = _load_registry()
    entries = [e for e in entries if not (e["hostname"] == hostname
                                          and e["credential_type"] == credential_type)]
    _save_registry(entries)

def list_credentials(credential_type: str = "ssh") -> list[dict[str, str]]:
    """Return all registry entries for the given credential type."""
    return [e for e in _load_registry() if e["credential_type"] == credential_type]
```

### Pattern 3: getpass for Secure Password Prompting

**What:** `getpass.getpass()` prompts on the controlling terminal (`/dev/tty`) with echo disabled. Unlike reading `sys.stdin`, it works even when stdin is redirected.

**When to use:** All `credentials add` operations — SSH and Proxmox. Never use `--password` CLI arg (shell history risk; listed in REQUIREMENTS.md Out of Scope).

**Example:**
```python
# Source: Python stdlib getpass module
def _cmd_credentials_add(args: argparse.Namespace) -> None:
    import getpass  # noqa: PLC0415
    from homelab_mcp.credential_store import (  # noqa: PLC0415
        register_credential, store_credential,
    )
    credential_type: str = args.type  # 'ssh' or 'proxmox'
    prompt = "Token/Password: " if credential_type == "proxmox" else "Password: "
    password = getpass.getpass(prompt)

    ok = store_credential(args.host, args.user, password, credential_type=credential_type)
    if ok:
        register_credential(args.host, args.user, credential_type=credential_type)
        print(f"Stored {credential_type} credential for {args.user}@{args.host}")
    else:
        print(f"Warning: OS keyring unavailable — credential not stored for {args.host}", file=sys.stderr)
        sys.exit(1)
```

### Pattern 4: Proxmox Credential Namespacing in Keyring

**What:** Use `"homelab-mcp-proxmox"` as the `service_name` for Proxmox credentials in keyring, versus `"homelab-mcp"` for SSH. This keeps them distinct in keyring UIs and prevents key collisions between SSH and Proxmox hostnames.

**Implementation:** `credential_store.py` must accept a `credential_type` parameter in `store_credential`, `get_credential`, and `delete_credential` (or use separate functions). The cleanest approach is to add an optional `credential_type: str = "ssh"` parameter to the existing three functions — Phase 17 used a fixed `_SERVICE_NAME = "homelab-mcp"`. Phase 18 changes this to derive the service name from the type:

```python
_SERVICE_NAMES = {
    "ssh": "homelab-mcp",
    "proxmox": "homelab-mcp-proxmox",
}
```

This is a backward-compatible change to `credential_store.py` — existing calls without `credential_type` continue to use `"homelab-mcp"`.

### Anti-Patterns to Avoid

- **`args.func(args)` without `set_defaults`:** If no `set_defaults` is called on the top-level parser, bare `homelab-mcp` results in `AttributeError: Namespace has no attribute 'func'`. Always call `parser.set_defaults(func=_run_stdio_wrapper)`.
- **`--password` CLI argument:** Shell history exposure. Out of scope per REQUIREMENTS.md. Use `getpass.getpass()` only.
- **Enumerating keyring directly:** `keyring` has no list API. Do not attempt `keyring.get_keyring().get_all_items()` — this is SecretService-specific, breaks on macOS/Windows/headless.
- **Module-level `import getpass` in credential_store.py:** Acceptable (getpass is stdlib, no D-Bus risk), but CLI imports belong in `server.py`, not `credential_store.py`. Keep `credential_store.py` free of all non-stdlib imports.
- **`print()` for server stderr messages:** Existing server code uses `print(..., file=sys.stderr)`. CLI success messages use `print()` to stdout. Keep these consistent.
- **`credentials` subparser with `set_defaults(func=_run_stdio_wrapper)`:** This makes `homelab-mcp credentials` (no action) start the server silently — misleading. Better: `cred_p.set_defaults(func=lambda args: cred_p.print_help())` so bare `homelab-mcp credentials` shows credentials help. But this requires a closure. Simpler: don't set `func` on `cred_p`, and handle missing `func` attr with `cred_p.print_help()` fallback in dispatch.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Secure password input | Read from stdin | `getpass.getpass()` | stdin may be piped; getpass opens `/dev/tty` directly; built-in echo suppression |
| Password storage | Custom encrypted file | `keyring` (Phase 17) | Already built in Phase 17 |
| Credential enumeration | Keyring-backend-specific code | JSON registry file | keyring has no list API by design; JSON file is portable, simple, no extra deps |
| Version string | Hardcode version | `_get_version()` + `action='version'` | `_get_version()` already exists; `action='version'` handles SystemExit and output format |
| CLI entry point registration | New script | Existing `[project.scripts]` entry | `homelab-mcp = "homelab_mcp.server:main"` already registered; just extend `main()` |

**Key insight:** The entire credentials CLI is ~80 lines of argparse + getpass code. The hard parts (keyring, registry, error handling) are in `credential_store.py`.

---

## Common Pitfalls

### Pitfall 1: Breaking Bare `homelab-mcp` Invocation

**What goes wrong:** Adding `parser.add_subparsers()` without `parser.set_defaults(func=...)` causes bare `homelab-mcp` to exit with an error in Python 3.11+ (subparsers are required by default when using `argparse`'s internal logic), or does nothing when `args.func` is not set.

**Why it happens:** `add_subparsers()` returns a group where subcommand is optional unless `required=True` is set; without `set_defaults`, there's no `func` attribute on the namespace.

**How to avoid:** Call `parser.set_defaults(func=_run_stdio_wrapper)` on the top-level parser immediately after creating it. The STATE.md locked decision documents this pattern explicitly.

**Warning signs:** `homelab-mcp` without arguments prints an error or does nothing instead of starting the server.

### Pitfall 2: `getpass.getpass()` in Non-TTY Test Environments

**What goes wrong:** Unit tests calling `_cmd_credentials_add` will fail with `GetPassWarning: Can not control echo on the terminal.` when there's no controlling terminal (CI/CD runner, pytest without a TTY).

**Why it happens:** `getpass.getpass()` tries to open `/dev/tty`; if unavailable, it falls back to stdin with a warning.

**How to avoid:** Mock `getpass.getpass` in all `credentials add` tests: `mocker.patch("homelab_mcp.server.getpass.getpass", return_value="test_password")`. The prompt string arg should be verified separately if needed.

**Warning signs:** `GetPassWarning` in test output; tests hang waiting for TTY input.

### Pitfall 3: PLC0415 on `from homelab_mcp.credential_store import ...` Inside main()

**What goes wrong:** The CLI handler functions inside `main()` need to import `credential_store`. Since `main()` uses local imports throughout, these imports need `# noqa: PLC0415`.

**Why it happens:** ruff's PLC0415 rule flags imports not at module top level. All imports inside `main()` already have this annotation (`import argparse  # noqa: PLC0415`).

**How to avoid:** Add `# noqa: PLC0415` to every import inside function bodies. This is the established project pattern.

**Warning signs:** ruff errors on `from homelab_mcp.credential_store import store_credential  # needs noqa`.

### Pitfall 4: Registry File Missing on First Run

**What goes wrong:** `credentials list` fails with `FileNotFoundError` on a fresh install before any credentials have been added.

**Why it happens:** `~/.homelab_mcp/credential_registry.json` doesn't exist until the first `credentials add`.

**How to avoid:** `_load_registry()` must return `[]` when the file doesn't exist (check `path.exists()` before reading). `list_credentials()` therefore always returns an empty list on fresh install — which is correct behavior.

**Warning signs:** `FileNotFoundError` when `credentials list` is run on a fresh install.

### Pitfall 5: Proxmox Credential Stored Under Wrong Service Name

**What goes wrong:** If `store_credential()` is called for Proxmox with the default `"homelab-mcp"` service name, `delete_credential(..., credential_type="proxmox")` will look in `"homelab-mcp-proxmox"` and find nothing.

**Why it happens:** Phase 17 hardcoded `_SERVICE_NAME = "homelab-mcp"`. Phase 18 must extend `store_credential`/`get_credential`/`delete_credential` to accept `credential_type` and derive the service name from `_SERVICE_NAMES[credential_type]`.

**How to avoid:** Add `credential_type: str = "ssh"` parameter to all three Phase 17 functions. Default to `"ssh"` to remain backward compatible.

**Warning signs:** Proxmox `credentials remove` reports credential not found after successful `credentials add --type proxmox`.

### Pitfall 6: `_run_stdio_wrapper` Must Replicate Existing HTTP/Stdio Branch Logic

**What goes wrong:** Moving the existing `if args.http:` logic into `_run_stdio_wrapper` incorrectly loses the `args.http`, `args.port`, etc. attributes if the wrapper is called without those args set.

**Why it happens:** Subcommand namespaces only contain their own arguments. `args.http` will be `None` or missing when dispatching from `_cmd_credentials_add`.

**How to avoid:** `_run_stdio_wrapper` is only called when `func` is set to it (bare invocation or `--http` path). The credentials handler functions (`_cmd_credentials_add`, etc.) never call the server logic. The argparse dispatch is mutually exclusive: either server args are parsed (no subcommand) or credentials args are parsed (with subcommand) — never both. The `func=_run_stdio_wrapper` default is only hit on bare invocations.

---

## Code Examples

Verified patterns from official sources and existing codebase:

### Existing: `_get_version()` in server.py (already present)
```python
# Source: src/homelab_mcp/server.py lines 109-113
from importlib.metadata import PackageNotFoundError, version

def _get_version() -> str:
    """Return package version from installed dist-info."""
    try:
        return version("homelab-mcp")
    except PackageNotFoundError:
        return "unknown"
```
`--version` uses this: `parser.add_argument("--version", action="version", version=f"%(prog)s {_get_version()}")`.

### Existing: Lazy Local Import Pattern in main() (established in server.py)
```python
# Source: src/homelab_mcp/server.py main() function
def main() -> None:
    import argparse  # noqa: PLC0415
    import asyncio   # noqa: PLC0415
    import os        # noqa: PLC0415
    import sys       # noqa: PLC0415
```
All new imports inside `main()` and handler functions follow this same pattern.

### New: --version One-Liner
```python
# Source: Python argparse official docs — action='version'
parser.add_argument(
    "--version",
    action="version",
    version=f"%(prog)s {_get_version()}",
)
# Produces output like: "homelab-mcp 1.2.0"
# Exits with code 0 immediately after printing
```

### New: credentials add Handler
```python
# Source: project pattern + Python stdlib getpass
def _cmd_credentials_add(args: argparse.Namespace) -> None:
    """Handle `homelab-mcp credentials add <host> <user> [--type ssh|proxmox]`."""
    import getpass  # noqa: PLC0415
    import sys  # noqa: PLC0415
    from homelab_mcp.credential_store import (  # noqa: PLC0415
        register_credential,
        store_credential,
    )

    credential_type: str = args.type
    prompt = "Token/Password: " if credential_type == "proxmox" else "Password: "
    password = getpass.getpass(prompt)

    ok = store_credential(args.host, args.user, password, credential_type=credential_type)
    if ok:
        register_credential(args.host, args.user, credential_type=credential_type)
        print(f"Stored {credential_type} credential for {args.user}@{args.host}")
    else:
        print(
            f"Warning: OS keyring unavailable — credential not persisted for {args.host}",
            file=sys.stderr,
        )
        sys.exit(1)
```

### New: credentials list Handler
```python
# Source: project pattern
def _cmd_credentials_list(args: argparse.Namespace) -> None:
    """Handle `homelab-mcp credentials list [--type ssh|proxmox]`."""
    from homelab_mcp.credential_store import list_credentials  # noqa: PLC0415

    credential_type: str = args.type
    entries = list_credentials(credential_type=credential_type)
    if not entries:
        print(f"No stored {credential_type} credentials.")
        return
    print(f"Stored {credential_type} credentials:")
    for entry in entries:
        print(f"  {entry['username']}@{entry['hostname']}")
```

### New: credentials remove Handler
```python
# Source: project pattern
def _cmd_credentials_remove(args: argparse.Namespace) -> None:
    """Handle `homelab-mcp credentials remove <host> [--type ssh|proxmox]`."""
    import sys  # noqa: PLC0415
    from homelab_mcp.credential_store import (  # noqa: PLC0415
        delete_credential,
        unregister_credential,
    )

    credential_type: str = args.type
    # Look up username from registry to pass to delete_credential
    from homelab_mcp.credential_store import list_credentials  # noqa: PLC0415
    entries = [e for e in list_credentials(credential_type=credential_type)
               if e["hostname"] == args.host]
    if not entries:
        print(f"No {credential_type} credential found for {args.host}", file=sys.stderr)
        sys.exit(1)

    for entry in entries:
        delete_credential(entry["hostname"], entry["username"], credential_type=credential_type)
    unregister_credential(args.host, credential_type=credential_type)
    print(f"Removed {credential_type} credential for {args.host}")
```

### New: credential_store.py Extensions
```python
# Source: project design (Phase 18 extends Phase 17)
# Add to credential_store.py module level (stdlib only — no homelab_mcp imports):
import json
import pathlib

_SERVICE_NAMES: dict[str, str] = {
    "ssh": "homelab-mcp",
    "proxmox": "homelab-mcp-proxmox",
}
_REGISTRY_PATH = pathlib.Path.home() / ".homelab_mcp" / "credential_registry.json"

# Updated signature for Phase 17 functions (backward-compatible default):
def store_credential(
    hostname: str, username: str, password: str, credential_type: str = "ssh"
) -> bool:
    service = _SERVICE_NAMES.get(credential_type, _SERVICE_NAME)
    ...  # rest unchanged except use `service` instead of `_SERVICE_NAME`
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No credential CLI | `homelab-mcp credentials add/list/remove` | Phase 18 | Users can manage credentials without editing env vars |
| No version flag | `homelab-mcp --version` | Phase 18 | Standard CLI behavior; enables scripted version checks |
| `_SERVICE_NAME` constant | `_SERVICE_NAMES` dict keyed by credential type | Phase 18 | Proxmox and SSH credentials namespaced separately in keyring |

**Deprecated/outdated:**
- `if args.http: ... else: asyncio.run(_run_stdio())` as flat dispatch: Phase 18 wraps this in `_run_stdio_wrapper(args)` called via `set_defaults`. The logic is identical; only the call site changes.

---

## Open Questions

1. **Should `credentials remove` require the username, or remove all credentials for a hostname?**
   - What we know: REQUIREMENTS.md shows `credentials remove <host>` (no user arg); multiple users per host are supported by the keyring key format.
   - What's unclear: If `root@192.168.1.1` and `admin@192.168.1.1` both exist, which is removed?
   - Recommendation: Remove all credentials for the hostname (all matching registry entries + keyring entries). This matches the success criterion wording "deletes the stored credential and confirms removal" without mentioning username.

2. **Should `_run_stdio_wrapper` check `hasattr(args, 'http')` to handle being called from the credentials dispatch path?**
   - What we know: `set_defaults(func=_run_stdio_wrapper)` only fires on bare invocations (no subcommand). The credentials handlers have their own `func`. So `_run_stdio_wrapper` is never called from a credentials dispatch.
   - What's unclear: Nothing — the dispatch is mutually exclusive by argparse design.
   - Recommendation: No guard needed. The wrapper can access `args.http` safely because it's only ever called when the top-level flags are present.

---

## Validation Architecture

> `workflow.nyquist_validation` is `true` in `.planning/config.json` — section included.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_credential_store.py tests/test_credentials_cli.py -x -q` |
| Full suite command | `uv run pytest tests/ -m "not integration" -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CRED-01 | `credentials add <host> <user>` calls `store_credential` + `register_credential` + prints confirmation | unit | `uv run pytest tests/test_credentials_cli.py::test_credentials_add_ssh -x` | Wave 0 |
| CRED-01 | Password is obtained via `getpass.getpass`, never from CLI arg | unit | `uv run pytest tests/test_credentials_cli.py::test_credentials_add_uses_getpass -x` | Wave 0 |
| CRED-02 | `credentials list` prints SSH hostnames, no passwords | unit | `uv run pytest tests/test_credentials_cli.py::test_credentials_list_ssh -x` | Wave 0 |
| CRED-02 | `credentials list` on empty registry prints "No stored ssh credentials." | unit | `uv run pytest tests/test_credentials_cli.py::test_credentials_list_empty -x` | Wave 0 |
| CRED-03 | `credentials remove <host>` calls `delete_credential` + `unregister_credential` + prints confirmation | unit | `uv run pytest tests/test_credentials_cli.py::test_credentials_remove_ssh -x` | Wave 0 |
| CRED-04 | `credentials add --type proxmox <host> <user>` stores under proxmox service name | unit | `uv run pytest tests/test_credentials_cli.py::test_credentials_add_proxmox -x` | Wave 0 |
| CRED-05 | `credentials list --type proxmox` shows only Proxmox hosts | unit | `uv run pytest tests/test_credentials_cli.py::test_credentials_list_proxmox -x` | Wave 0 |
| CRED-06 | `credentials remove --type proxmox <host>` deletes from proxmox service name | unit | `uv run pytest tests/test_credentials_cli.py::test_credentials_remove_proxmox -x` | Wave 0 |
| CLI-01 | `homelab-mcp --version` prints version string and exits 0 | unit | `uv run pytest tests/test_credentials_cli.py::test_version_flag -x` | Wave 0 |
| CLI-01 | bare `homelab-mcp` still starts server (does not exit, does not print version) | unit | `uv run pytest tests/test_credentials_cli.py::test_bare_invocation_starts_server -x` | Wave 0 |
| CRED-01..06 | `register_credential` upserts entry in registry; `list_credentials` returns it | unit | `uv run pytest tests/test_credential_store.py::test_register_and_list -x` | Wave 0 |
| CRED-01..06 | `unregister_credential` removes entry; `list_credentials` returns empty | unit | `uv run pytest tests/test_credential_store.py::test_unregister_removes_entry -x` | Wave 0 |
| CRED-01..06 | `list_credentials` returns `[]` when registry file does not exist | unit | `uv run pytest tests/test_credential_store.py::test_list_credentials_no_file -x` | Wave 0 |
| CRED-04 | `store_credential(..., credential_type='proxmox')` uses `'homelab-mcp-proxmox'` service name | unit | `uv run pytest tests/test_credential_store.py::test_store_proxmox_uses_proxmox_service_name -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_credential_store.py tests/test_credentials_cli.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -m "not integration" -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_credentials_cli.py` — new file, covers all CRED-01..06 + CLI-01 CLI-facing behaviors
- [ ] Additional test cases in `tests/test_credential_store.py` — covers registry functions + `credential_type` parameter on existing functions

*(All test infrastructure already exists — pytest, pytest-mock, pyproject.toml config. `test_credential_store.py` exists from Phase 17 and will be extended.)*

---

## Sources

### Primary (HIGH confidence)
- Python 3.12 argparse official docs (https://docs.python.org/3/library/argparse.html#sub-commands) — `set_defaults(func=...)` dispatch pattern, `action='version'` behavior
- Python 3.12 getpass official docs (stdlib) — `getpass.getpass()` signature, `/dev/tty` behavior
- Project codebase `src/homelab_mcp/server.py` — existing `main()`, `_get_version()`, local import pattern
- Project codebase `src/homelab_mcp/credential_store.py` (Phase 17) — `_SERVICE_NAME`, lazy import pattern, function signatures to extend
- Project STATE.md — locked pattern: `parser.set_defaults(func=_run_server)` + `getattr(args, 'func', _run_server)(args)`

### Secondary (MEDIUM confidence)
- GitHub jaraco/keyring#151 — maintainer confirmed no enumeration API exists; registry pattern is the standard workaround
- Python stdlib `json` + `pathlib` — JSON registry approach confirmed as standard for small credential metadata stores

### Tertiary (LOW confidence)
- None — all findings have PRIMARY or SECONDARY verification.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all stdlib; credential_store.py already in codebase
- Architecture: HIGH — argparse dispatch verified via live Python test; registry design follows established project patterns; keyring enumeration gap confirmed from official source
- Pitfalls: HIGH for pitfalls 1, 2, 4, 5; MEDIUM for pitfall 3 (ruff PLC0415 — follows established project pattern), pitfall 6 (argparse namespace behavior — verified via live test)

**Research date:** 2026-03-14
**Valid until:** 2026-09-14 (stable stdlib; keyring API changes are tracked)
