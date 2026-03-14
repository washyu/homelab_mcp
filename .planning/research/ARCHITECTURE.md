# Architecture Research

**Domain:** Python MCP server — credential store + CI/CD release automation (v1.3)
**Researched:** 2026-03-14
**Confidence:** HIGH (all integration points verified by direct source inspection)

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│               CLI entrypoint  server.py main()                   │
│                                                                  │
│  ┌──────────────────────┐  ┌─────────────────────────────────┐  │
│  │  --version  (NEW)    │  │  credentials subparser  (NEW)   │  │
│  │  argparse VERSION    │  │  add / list / remove subcommands│  │
│  │  exits immediately   │  └────────────┬────────────────────┘  │
│  └──────────────────────┘               │ direct call           │
│                                         ▼                        │
│                          ┌──────────────────────────────────┐   │
│                          │  credential_store.py  (NEW)      │   │
│                          │  get / set / delete              │   │
│                          │  keyring wrapper + dep guard     │   │
│                          └──────────────┬───────────────────┘   │
│                                         │ optional import        │
│                          ┌──────────────▼───────────────────┐   │
│                          │  keyring>=25.0.0                 │   │
│                          │  [project.optional-dependencies] │   │
│                          │  security extra (already listed) │   │
│                          └──────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│           MCP Tool Call Chain — SSH credential resolution        │
│                                                                  │
│  MCP client → server.py @call_tool handler                       │
│    → tool_handlers/ssh_handlers.py                              │
│        → ssh_tools.resolve_ssh_credentials()  ← EXISTING HOOK  │
│            priority chain (extended in v1.3):                   │
│            1. explicit args (password / key_path)  [unchanged]  │
│            2. db.get_credential_by_hostname()      [unchanged]  │
│            3. credential_store.get_credential()    [NEW step]   │
│            4. default mcp_admin key fallback       [unchanged]  │
│        → ssh_connection.ssh_connect()                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│           Proxmox credential resolution                          │
│                                                                  │
│  config.py MCPConfig.__init__()                                  │
│    1. os.getenv("PROXMOX_PASSWORD")      [env var, takes prec.] │
│    2. credential_store.get_credential()  [NEW keyring fallback] │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│           GitHub Actions CI/CD — .github/workflows/main.yml      │
│                                                                  │
│  on: push / tags: v*  (already configured)                       │
│                                                                  │
│  test-and-quality  ─────────────────────────────┐               │
│       (always)                                  │               │
│                              needs ─────────────┼──────┐        │
│                                                 ▼      ▼        │
│                                  publish (NEW)    release        │
│                                  PyPI OIDC        GitHub Release │
│                                  tags only        tags only      │
│                                  (NEW job,        (existing job) │
│                                  same file)                      │
└─────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | Status for v1.3 |
|-----------|----------------|-----------------|
| `server.py main()` | argparse entrypoint (`homelab-mcp` console script) | MODIFY — add `--version`, add `credentials` subparser |
| `credential_store.py` | keyring get/set/delete, service name convention, dep guard | NEW module |
| `ssh_tools.resolve_ssh_credentials()` | SSH credential priority chain for all SSH handlers | MODIFY — insert keyring lookup as step 3 |
| `config.py MCPConfig` | Proxmox session config construction | MODIFY — add keyring fallback after env var check |
| `database.py SQLiteAdapter` | SSH credential metadata CRUD (ssh_credentials table) | UNCHANGED — already stores hostname/username/key_path |
| `prompt_registry.py` | Static prompt text templates including decommission workflow | MODIFY — PRMT-02 fix in `_build_decommission_result()` |
| `main.yml` publish job | PyPI OIDC publish on `v*` tag | NEW job in existing file |

## Recommended Project Structure

```
src/homelab_mcp/
├── credential_store.py      # NEW — keyring wrapper, optional dep guard
├── server.py                # MODIFY — --version flag, credentials subparser
├── ssh_tools.py             # MODIFY — step 3 in resolve_ssh_credentials()
├── config.py                # MODIFY — Proxmox password keyring fallback
├── prompt_registry.py       # MODIFY — PRMT-02 fix in _build_decommission_result()
└── ... (all other modules unchanged)

.github/workflows/
└── main.yml                 # MODIFY — add publish job (peer to existing release job)
```

### Structure Rationale

- **credential_store.py:** Isolated module with no homelab_mcp imports avoids circular import risk. All keyring calls centralised here; other modules call `credential_store.get_credential(key)` with no knowledge of keyring internals. Consistent with the existing pattern of module-per-concern (`database.py`, `error_handling.py`, etc.).
- **main.yml (modify, not new file):** The `release` job in `main.yml` already fires on `v*` tags and already `needs: test-and-quality`. Adding `publish` as a peer job keeps all tag-triggered automation co-located and avoids duplicating the trigger definition in a second file.

## Architectural Patterns

### Pattern 1: Optional Dependency Guard in credential_store.py

**What:** Import `keyring` inside a `try/except ImportError` block at module level. Expose a module-level `KEYRING_AVAILABLE: bool` constant. All public functions check this constant and return `None` (get) or raise `RuntimeError` with a user-facing install hint (set/delete) when keyring is absent.

**When to use:** `keyring` is already listed in `[project.optional-dependencies] security` in `pyproject.toml`. Users who install `homelab-mcp` without `pip install homelab-mcp[security]` must not receive a hard import error on server startup.

**Trade-offs:** Tests must cover both the `KEYRING_AVAILABLE = True` and `KEYRING_AVAILABLE = False` branches. Silent `None` return on get is safe — `resolve_ssh_credentials()` falls through to the mcp_admin key anyway.

**Example:**
```python
# src/homelab_mcp/credential_store.py
try:
    import keyring as _keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

SERVICE_NAME = "homelab-mcp"

def get_credential(key: str) -> str | None:
    """Return stored secret for key, or None if keyring unavailable or key absent."""
    if not KEYRING_AVAILABLE:
        return None
    return _keyring.get_password(SERVICE_NAME, key)

def set_credential(key: str, secret: str) -> None:
    """Store secret for key. Raises RuntimeError if keyring is not installed."""
    if not KEYRING_AVAILABLE:
        raise RuntimeError(
            "keyring package is not installed. "
            "Install with: pip install homelab-mcp[security]"
        )
    _keyring.set_password(SERVICE_NAME, key, secret)

def delete_credential(key: str) -> bool:
    """Delete credential for key. Returns True if deleted, False if absent."""
    if not KEYRING_AVAILABLE:
        return False
    try:
        _keyring.delete_password(SERVICE_NAME, key)
        return True
    except Exception:
        return False
```

### Pattern 2: Extend resolve_ssh_credentials() Priority Chain

**What:** `ssh_tools.resolve_ssh_credentials()` already implements a three-step priority chain (explicit args → SQLite lookup → mcp_admin key fallback). Insert `credential_store.get_credential(f"{hostname}:{username}")` as step 3 — between the SQLite lookup and the mcp_admin fallback.

**When to use:** This is the single call site that supplies credentials to every SSH handler. All 56 tools automatically benefit from keyring-stored passwords without any handler changes.

**Key convention:** Keyring keys use `hostname:username` format (e.g., `192.168.1.10:admin`). This mirrors the `(hostname, username)` primary lookup in the SQLite `ssh_credentials` table.

**The updated priority order:**
1. Explicit `password` or `key_path` argument — backward compatible, unchanged
2. `db.get_credential_by_hostname(hostname, username)` — SQLite metadata record — unchanged
3. `credential_store.get_credential(f"{hostname}:{username or 'mcp_admin'}")` — keyring password — NEW
4. Default `mcp_admin` key path — unchanged fallback

**Trade-offs:** The keyring lookup adds one function call per SSH connection establishment. Since `credential_store.get_credential()` is synchronous and `resolve_ssh_credentials()` is already synchronous, no async complexity is introduced.

### Pattern 3: argparse subparser for credentials subcommand

**What:** Add `--version` as a top-level flag and `credentials` as a subparser in the existing `main()` function in `server.py`. The `credentials` subparser has three sub-subcommands: `add`, `list`, `remove`.

**When to use:** The `homelab-mcp` console script points at `homelab_mcp.server:main`. Extending this function is the correct approach — adding a second console script would require users to remember two different commands.

**Execution path:** When `sys.argv` includes `credentials`, `main()` dispatches to `credential_store` functions and calls `sys.exit(0)` before any server startup logic runs. `--version` uses `argparse`'s built-in `action="version"` and also exits without starting the server.

**Key implementation note:** Import `credential_store` inside the credentials branch (local import), not at module top. This keeps `server.py`'s startup cost unchanged for the common case (starting the MCP server). Consistent with the established local import pattern used for circular import avoidance throughout the codebase (e.g., `tool_handlers/credential_handlers.py` line 34).

**Example structure:**
```python
# In main(), after existing parser.add_argument() calls:
parser.add_argument(
    "--version",
    action="version",
    version=f"homelab-mcp {_get_version()}",
)
subparsers = parser.add_subparsers(dest="subcommand")
cred_parser = subparsers.add_parser("credentials", help="Manage stored credentials")
cred_sub = cred_parser.add_subparsers(dest="cred_action")

add_p = cred_sub.add_parser("add")
add_p.add_argument("--hostname", required=True)
add_p.add_argument("--username", default="mcp_admin")
add_p.add_argument("--password", required=True)

cred_sub.add_parser("list")

remove_p = cred_sub.add_parser("remove")
remove_p.add_argument("--hostname", required=True)
remove_p.add_argument("--username", default="mcp_admin")

args = parser.parse_args()

if args.subcommand == "credentials":
    from homelab_mcp.credential_store import (  # noqa: PLC0415
        delete_credential, get_all_credentials, set_credential,
    )
    # dispatch to cred_action; sys.exit(0) when done
    return
# ... existing server startup ...
```

### Pattern 4: PyPI OIDC Trusted Publisher in main.yml

**What:** Add a `publish` job to the existing `main.yml` that uses `pypa/gh-action-pypi-publish@release/v1` with `attestations: true`. Job runs only on `v*` tags, `needs: [test-and-quality]`, and declares `permissions: id-token: write`.

**When to use:** The existing `release` job already fires on `v*` tags. Add `publish` as a peer (not dependent) job — both need tests to pass, neither needs the other to finish first.

**Why new job in main.yml, not a new file:** The tag trigger (`startsWith(github.ref, 'refs/tags/')`) is already in `main.yml`. A separate `publish.yml` would require duplicating this trigger and reasoning about two independent pipelines. Peer job in the same file is the standard pattern for projects that have both GitHub Release creation and PyPI publish.

**OIDC setup prerequisite:** The PyPI project settings must have a Trusted Publisher configured (GitHub Actions / owner / repo / workflow name / environment). This is a one-time manual step done in the PyPI web UI before the workflow runs — it is not encoded in the workflow YAML.

**Example job:**
```yaml
publish:
  name: Publish to PyPI
  runs-on: ubuntu-latest
  needs: [test-and-quality]
  if: startsWith(github.ref, 'refs/tags/')
  permissions:
    id-token: write

  steps:
  - uses: actions/checkout@v6

  - name: Install uv
    uses: astral-sh/setup-uv@v4
    with:
      enable-cache: true
      cache-dependency-glob: "pyproject.toml"

  - name: Set up Python
    run: uv python install 3.12

  - name: Build distribution
    run: uv build

  - name: Publish to PyPI
    uses: pypa/gh-action-pypi-publish@release/v1
    with:
      attestations: true
```

## Data Flow

### SSH Credential Resolution (v1.3 updated flow)

```
ssh_handler receives {hostname, username?, password?, key_path?}
    ↓
resolve_ssh_credentials(hostname, username, password, key_path)
    │
    ├── password or key_path present?
    │       YES → SSHCredentials(explicit)          [backward compat, UNCHANGED]
    │
    ├── db.get_credential_by_hostname(hostname, username)
    │       FOUND → SSHCredentials(from SQLite)     [UNCHANGED]
    │
    ├── credential_store.get_credential(f"{hostname}:{username or 'mcp_admin'}")
    │       FOUND → SSHCredentials(password=keyring_secret)    [NEW]
    │
    └── username == "mcp_admin" and ~/.ssh/mcp/mcp_admin_key exists?
            YES → SSHCredentials(mcp_admin key)     [UNCHANGED fallback]
            NO  → SSHCredentials(bare)              [UNCHANGED]
```

### Proxmox Credential Resolution (v1.3 extended)

```
MCPConfig.__init__()
    │
    ├── os.getenv("PROXMOX_PASSWORD") → use directly   [env var, takes precedence]
    │
    └── credential_store.get_credential("proxmox:password") → use if present  [NEW]
```

This path is only reached when `PROXMOX_PASSWORD` env var is absent.

### CLI credentials subcommand flow

```
homelab-mcp credentials add --hostname 192.168.1.10 --username admin --password s3cr3t
    ↓
main() detects args.subcommand == "credentials", args.cred_action == "add"
    ↓
credential_store.set_credential("192.168.1.10:admin", "s3cr3t")
    ↓
print("Credential stored for 192.168.1.10:admin")
sys.exit(0)    [MCP server never starts]
```

### Tag-push PyPI publish flow

```
git tag v1.3.0 && git push origin v1.3.0
    ↓
main.yml triggers on push/tags/v*
    ↓
test-and-quality job (ruff, mypy, pytest -m "not integration")
    ↓ needs: [test-and-quality]                        ↓ needs: [test-and-quality]
publish job                                       release job
  uv build → dist/                                 softprops/action-gh-release
  pypa/gh-action-pypi-publish (OIDC)               generates release notes
  uploads to PyPI                                  creates GitHub Release
```

The `publish` and `release` jobs run in parallel — neither depends on the other.

### PRMT-02 Fix Data Flow

```
MCP client → prompts/get { name: "decommission_device_workflow",
                           arguments: { hostname: "192.168.1.10" } }
    ↓
prompt_registry.get_prompt_result("decommission_device_workflow", args)
    ↓
_build_decommission_result(args)
    ↓
Returns PromptMessage text instructing AI to:
  1. Call list_network_devices or get_device_info to resolve hostname → device_id
  2. Call decommission_device_preview with device_id=<resolved_id>
  3. Get confirmation
  4. Call decommission_device with device_id=<resolved_id>
```

The fix is purely in the rendered text of `_build_decommission_result()`. The `HOMELAB_PROMPTS` metadata entry (`hostname` argument) is correct — the prompt accepts hostname as human input. Only the tool call instructions in the rendered text need updating (two occurrences of `hostname=` → `device_id=`, plus a resolver step).

## Integration Points

### New Module Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `credential_store.py` → `ssh_tools.py` | `resolve_ssh_credentials()` calls `credential_store.get_credential()` directly | No circular risk: `credential_store` imports only `keyring` (optional) |
| `credential_store.py` → `server.py main()` | Local import inside the `credentials` subcommand branch | Consistent with local import pattern established throughout tool_handlers |
| `credential_store.py` → `config.py` | Called in `MCPConfig` constructor for Proxmox password fallback | After env var check; only imported if env var absent |

### Modified Module Touch Points

| Module | What Changes | Lines / Scope |
|--------|--------------|---------------|
| `server.py main()` | Add `--version` action, add `credentials` subparser and dispatch | ~40 lines new; existing server startup logic unchanged |
| `ssh_tools.resolve_ssh_credentials()` | Insert step 3: keyring lookup via credential_store | ~8 lines inserted in existing function body |
| `config.py MCPConfig` | Add keyring fallback for Proxmox password after env var check | ~5 lines; conditional on `PROXMOX_PASSWORD` env var absent |
| `prompt_registry.py _build_decommission_result()` | Update tool call instructions: add resolver step, change `hostname=` to `device_id=` | ~5 lines changed in prompt text string |
| `.github/workflows/main.yml` | Add `publish` job after existing `release` job | ~25 lines new YAML |

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| OS keyring (libsecret / macOS Keychain / Windows Credential Manager) | `keyring` library abstraction | Optional dep; absent = silent no-op in get, RuntimeError with install hint in set/delete |
| PyPI | OIDC trusted publisher via `pypa/gh-action-pypi-publish@release/v1` | One-time manual PyPI project settings setup required before first publish |
| GitHub Releases | `softprops/action-gh-release@v2` | Already present; `publish` job is a peer, not dependent |

## Anti-Patterns

### Anti-Pattern 1: Second console script entry point for credentials

**What people do:** Add `homelab-mcp-credentials = "homelab_mcp.cli:credentials_main"` to `[project.scripts]` in `pyproject.toml`.

**Why it's wrong:** Users must remember two different commands. The existing `homelab-mcp` console script already uses argparse and is the right extension point. A second script doubles distribution surface for no gain.

**Do this instead:** Add `credentials` as a subparser in the existing `main()` function in `server.py`. When `args.subcommand is None`, existing server startup runs unchanged.

### Anti-Pattern 2: Separate publish.yml workflow file

**What people do:** Create `.github/workflows/publish.yml` with its own `on: push: tags:` trigger.

**Why it's wrong:** Duplicates trigger logic already in `main.yml`. The existing `release` job in `main.yml` fires on `v*` tags; a second file creates two independent pipelines that are hard to reason about together.

**Do this instead:** Add `publish` as a peer job to `release` inside `main.yml`. Both need `test-and-quality`, both fire on `v*` tags, clearly co-located.

### Anti-Pattern 3: Scattering keyring calls across modules

**What people do:** Call `keyring.get_password("homelab-mcp", key)` directly in `ssh_tools.py` and `config.py`.

**Why it's wrong:** The service name `"homelab-mcp"` becomes an implicit coupling across files. The optional import guard must be duplicated. Bandit may flag direct keyring calls outside a purpose-built module.

**Do this instead:** All keyring access through `credential_store.py`. The service name is a single module-level constant there. Other modules call `credential_store.get_credential(key)`.

### Anti-Pattern 4: Storing passwords in both keyring and SQLite

**What people do:** When `credentials add --password` is invoked, write the password to both `credential_store.set_credential()` and the SQLite `ssh_credentials` table.

**Why it's wrong:** The SQLite DB (`~/.mcp/sitemap.db`) is a plaintext file. Duplicating secrets there defeats the security purpose of OS keyring. The existing `ssh_credentials` table correctly stores only `hostname`, `username`, `port`, and `key_path` — no passwords.

**Do this instead:** SQLite stores non-secret metadata only. Keyring stores passwords only. `resolve_ssh_credentials()` checks SQLite for key-based auth records, then keyring for password-based auth, in that order.

## Build Order

Ordered by implementation dependencies — each item can be Wave-0 RED-test scaffolded before implementation:

```
1. credential_store.py
   No homelab_mcp dependencies. Standalone module.
   Tests mock keyring; cover KEYRING_AVAILABLE=True and False branches.

2. --version flag in server.py main()
   Trivial: one argparse.add_argument call, one test.
   No dependencies on step 1.

3. credentials subparser in server.py main()
   Depends on credential_store.py being importable (step 1).
   Wave-0 test stubs credential_store; full test imports it.

4. resolve_ssh_credentials() extension in ssh_tools.py
   Depends on credential_store.py (step 1).
   Extend existing unit tests with keyring-hit and keyring-miss cases.

5. Proxmox password fallback in config.py
   Depends on credential_store.py (step 1).
   Can be done in parallel with step 4.

6. PRMT-02 fix in prompt_registry.py
   No new dependencies. Self-contained text change.
   Can be done at any point in the sequence.

7. publish job in main.yml
   No code dependencies. YAML-only change.
   Requires one-time PyPI trusted publisher setup before first tag push.
```

Steps 4, 5, 6, and 7 have no ordering dependency between them once step 1 is done.

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| credential_store.py pattern | HIGH | `keyring` optional dep guard is a standard Python pattern; keyring>=25.0.0 already in pyproject.toml |
| resolve_ssh_credentials() hook point | HIGH | Function body inspected directly; three-step chain verified |
| argparse subparser extension | HIGH | Existing `main()` in server.py inspected; no conflicts with existing args |
| PRMT-02 root cause | HIGH | Tool schema (`device_id` required) and prompt text (`hostname=`) both inspected directly |
| PyPI OIDC publish job | MEDIUM | Pattern is standard `pypa/gh-action-pypi-publish` usage; PyPI UI setup step is external and manual |
| Proxmox config.py fallback | MEDIUM | config.py not deeply inspected in this session; env var precedence pattern is standard |

## Sources

- `src/homelab_mcp/server.py` — `main()` argparse setup (lines 483–580), `_get_version()` (lines 109–114)
- `src/homelab_mcp/ssh_tools.py` — `resolve_ssh_credentials()` full body (lines 35–114)
- `src/homelab_mcp/database.py` — `DatabaseAdapter` credential CRUD methods (lines 67–109), no password field in `add_credential()` signature
- `src/homelab_mcp/prompt_registry.py` — `_build_decommission_result()` (lines 73–87), tool calls using `hostname=`
- `src/homelab_mcp/tool_schemas/infrastructure_tools_schema.py` — `decommission_device` schema: `required: ["device_id"]`
- `.github/workflows/main.yml` — existing jobs, tag triggers, `release` job structure (lines 192–211)
- `pyproject.toml` — `[project.optional-dependencies] security` includes `keyring>=25.0.0`; console script `homelab_mcp.server:main`

---
*Architecture research for: homelab-mcp v1.3 — credential store + release automation*
*Researched: 2026-03-14*
