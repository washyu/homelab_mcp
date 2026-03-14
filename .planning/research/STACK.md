# Stack Research

**Domain:** Homelab MCP Server — v1.3 Credentials & Release Automation
**Researched:** 2026-03-14
**Confidence:** HIGH (keyring API), HIGH (PyPI OIDC workflow), HIGH (argparse subparsers)

**Scope:** New dependencies and integration patterns for v1.3 only.
Validated v1.2 stack (Python 3.12+, uv, mcp[cli], asyncssh, hatchling, SQLite, PyPI distribution) is NOT re-researched.

---

## Summary: What Changes for v1.3

| Feature | Stack Change | Verdict |
|---------|-------------|---------|
| OS keyring credential store | Promote `keyring>=25.0.0` from optional → core dependency | `keyring` is already in `[project.optional-dependencies] security`; move to `[project.dependencies]` |
| Keyring fallback (headless/CI) | No new dep — handle `keyring.errors.NoKeyringError` in code | Catch `NoKeyringError` and degrade gracefully to env-var-only mode |
| PyPI trusted publishing | Workflow-only change — no new dependencies | Add `publish` job to existing `main.yml` using `pypa/gh-action-pypi-publish@release/v1` |
| `--version` CLI flag | No new dep | `argparse` `--version` action built-in |
| `credentials add/list/remove` CLI subcommands | No new dep | `argparse.add_subparsers()` in existing `main()` function |

**Net new runtime dependencies for v1.3: one — `keyring>=25.0.0` promoted to core.**

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| keyring | >=25.6.0 | OS keyring abstraction (GNOME Secret Service, macOS Keychain, Windows Credential Manager) | Already in project optional deps; v25.6.0 removed spurious warning logs when no backend configured, making fallback detection clean; provides `keyring.errors.NoKeyringError` for graceful degradation |
| argparse (stdlib) | Python 3.12 built-in | `credentials add/list/remove` subcommands, `--version` flag | No new dep; `add_subparsers()` + `set_defaults(func=...)` pattern is idiomatic Python; already used in `main()` |
| pypa/gh-action-pypi-publish | release/v1 (pinned v1.13.0) | PyPI publish step in GitHub Actions | Official PyPA action; supports trusted publishing OIDC natively; no API tokens needed |

### Supporting Libraries — No Changes

All existing runtime deps (asyncssh, aiohttp, starlette, uvicorn, rich, pydantic, websockets) remain unchanged for v1.3.

---

## Feature 1: OS Keyring Integration

**Confidence: HIGH** — verified against keyring 25.7.0 docs and source.

### Dependency Change

Move `keyring` from optional to core:

```toml
# pyproject.toml — BEFORE (v1.2)
[project.optional-dependencies]
security = [
    "keyring>=25.0.0",
    "cryptography>=42.0.0",
]

# AFTER (v1.3)
[project.dependencies]
# ... existing deps ...
"keyring>=25.6.0",
```

The `security` optional group can keep `cryptography>=42.0.0` if it is used elsewhere, but `keyring` must move to core because `homelab-mcp credentials add` will fail without it.

### API — What to Use

```python
import keyring
import keyring.errors

# Store credential (service = "homelab-mcp", username = hostname)
keyring.set_password("homelab-mcp", hostname, password)

# Retrieve credential
password = keyring.get_password("homelab-mcp", hostname)  # returns None if not found

# Get credential object (includes username)
cred = keyring.get_credential("homelab-mcp", hostname)
# cred.username, cred.password — or None if not found

# Delete credential
keyring.delete_password("homelab-mcp", hostname)
# Raises keyring.errors.PasswordDeleteError if not found
```

`get_credential()` was added in keyring 21.4 and is present in all v25.x versions. It is preferred over `get_password()` when the stored username may differ from the lookup key.

`AnonymousCredential` was introduced in v25.4.0 to model secrets without usernames — not needed here since hostname is the natural username key.

### Fallback Strategy — Headless / No Keyring

The target audience (Proxmox homelabbers) runs the MCP server on headless Linux servers or in containers where GNOME Secret Service / KWallet are unavailable. `keyring` raises `keyring.errors.NoKeyringError` in this case (on v25.x; earlier versions raised `RuntimeError`).

**Required fallback pattern:**

```python
import keyring
import keyring.errors

def get_credential_from_keyring(service: str, hostname: str) -> str | None:
    """Retrieve credential, returning None if keyring unavailable."""
    try:
        return keyring.get_password(service, hostname)
    except keyring.errors.NoKeyringError:
        return None  # degrade gracefully — caller falls back to env vars
    except Exception:
        return None  # corrupt backend — same degradation

def store_credential_in_keyring(service: str, hostname: str, password: str) -> bool:
    """Store credential. Returns False if keyring unavailable."""
    try:
        keyring.set_password(service, hostname, password)
        return True
    except keyring.errors.NoKeyringError:
        return False  # caller must warn the user
```

**User-facing behaviour when no keyring:**

- `homelab-mcp credentials add` — print a clear warning: "No OS keyring available on this system. Credentials cannot be stored securely. Use environment variables instead." and exit with non-zero status.
- Auto-inject on SSH tool calls — silently skip keyring lookup, use env vars if set.
- Do NOT fall back to `keyrings.alt` (plaintext file on disk) — homelab-mcp does not want silent credential storage in a world-readable file.

**Detection without attempting an operation:**

```python
backend = keyring.get_keyring()
# backend.__class__.__name__ == "NullKeyring" → no usable backend
# or check: hasattr(backend, 'priority') and backend.priority < 0
```

Alternatively, set `PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring` in the environment to force null backend (useful for CI to prevent keyring prompts during tests).

### Backend Availability by Platform

| Platform | Backend | Available Headless? |
|----------|---------|-------------------|
| GNOME desktop Linux | SecretService (libsecret) | No — requires D-Bus session |
| KDE Linux | KWallet | No — requires D-Bus session |
| macOS | Keychain | Yes (with TTY) |
| Windows | Credential Manager | Yes |
| Headless Linux server | None (NullKeyring) | No — `NoKeyringError` |
| WSL2 | None by default | No — same as headless Linux |

For the primary homelab use case (headless Proxmox host), the keyring will be unavailable. The implementation must treat env vars as the fully supported path and keyring as a convenience feature on desktop systems.

### Proxmox Credentials Storage

Proxmox API credentials (`PROXMOX_HOST`, `PROXMOX_TOKEN_ID`, `PROXMOX_TOKEN_SECRET`) should use the same keyring service with a `proxmox:` prefix in the username key:

```python
keyring.set_password("homelab-mcp", "proxmox:host", proxmox_host)
keyring.set_password("homelab-mcp", "proxmox:token_id", token_id)
keyring.set_password("homelab-mcp", "proxmox:token_secret", token_secret)
```

Env vars always take precedence — check `os.getenv("PROXMOX_HOST")` first, fall back to `keyring.get_password("homelab-mcp", "proxmox:host")`.

### What NOT to Add for Keyring

| Avoid | Why |
|-------|-----|
| `keyrings.alt` (PlaintextKeyring) | Stores credentials base64-encoded on disk with no encryption; false security; explicitly warn and refuse instead |
| `cryptography` for DIY encryption | Reinvents keyring's purpose; not needed if using OS keyring correctly |
| SQLite as credential store | Database is already used for device tracking; mixing credentials into device DB creates privilege-confusion; OS keyring is the correct abstraction |
| Secret scanning in code | `log_filter.py` already handles credential redaction; no change needed |

---

## Feature 2: GitHub Actions PyPI Trusted Publishing

**Confidence: HIGH** — verified against official PyPI docs and pypa/gh-action-pypi-publish README.

### What Trusted Publishing Is

PyPI Trusted Publishing uses GitHub's OIDC token to authenticate publish requests. No long-lived API token is stored in GitHub Secrets. The OIDC token is short-lived and scoped to a specific workflow run. Sigstore attestations are generated automatically for each distribution.

This is the current PyPI-recommended approach as of 2023 and is now the de facto standard.

### Pre-Requisite: One-Time PyPI Configuration

Before the workflow can publish, a Trusted Publisher must be configured at:
`https://pypi.org/manage/project/homelab-mcp/settings/publishing/`

Required fields:
- **Owner:** GitHub organisation or username (e.g. `shaunpalmer` or org name)
- **Repository name:** `mcp_python_server`
- **Workflow filename:** `publish.yml` (or `main.yml` if publishing from the existing workflow)
- **Environment name:** `pypi` (must match the `environment:` in the workflow)
- **Tag (optional):** Can restrict to `v*` tags for extra safety

This is a manual one-time step — it cannot be automated.

### Workflow Addition

Add a `publish` job to the existing `.github/workflows/main.yml`. The job should:

1. Depend on `test-and-quality` passing
2. Trigger only on `v*` tags
3. Build the wheel and sdist using `uv build`
4. Publish using `pypa/gh-action-pypi-publish@release/v1` with OIDC permissions

```yaml
publish:
  name: Publish to PyPI
  runs-on: ubuntu-latest
  needs: [test-and-quality]
  if: startsWith(github.ref, 'refs/tags/v')
  environment:
    name: pypi
    url: https://pypi.org/p/homelab-mcp
  permissions:
    id-token: write  # mandatory for trusted publishing

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
```

**Why `uv build` instead of `python -m build`:** The project already uses uv throughout CI; `uv build` respects the same lockfile and produces identical output. No extra dependency install step needed.

**Why `release/v1` not a pinned SHA:** The `release/v1` branch is maintained by PyPA as a rolling stable pointer — it receives security fixes (e.g. GHSA-vxmw-7h4f-hqxh fixed in v1.13.0) without changing the user-facing interface. Pinning to a SHA would require manual updates for security patches. The PyPA project explicitly recommends `release/v1` for this reason.

### GitHub Environment Protection

Create a `pypi` environment in GitHub repository settings (`Settings > Environments > New environment`):
- Name: `pypi`
- Optional: add protection rule requiring a manual approval for tag-triggered deploys (adds a human gate before every PyPI release)

### Version Bump Workflow

Tag-triggered publishing means the release workflow is:

```bash
# 1. Update version in pyproject.toml
# 2. Commit: "chore: bump version to v1.3.0"
# 3. Tag: git tag v1.3.0
# 4. Push tag: git push origin v1.3.0
# → CI runs tests → publish job triggers → PyPI updated
```

No manual `uv publish` command needed after the first release. The `release` job (GitHub Release creation) already exists in `main.yml` and will continue to run in parallel.

### What NOT to Do for PyPI Publishing

| Avoid | Why |
|-------|-----|
| `UV_PUBLISH_TOKEN` secret in GitHub | Token-based auth requires manual rotation; trusted publishing is keyless |
| Publishing from the existing `release` job | Separation of concerns — GitHub Release creation and PyPI publish are independent; if PyPI is down, GitHub Release should still succeed |
| `uv publish` in CI without trusted publishing configured | Would fail with auth error; trusted publishing must be configured at pypi.org first |

---

## Feature 3: argparse Subcommands for Credentials CLI

**Confidence: HIGH** — stdlib, documented pattern, verified against existing `main()` in `server.py`.

### Current CLI Structure

The existing `main()` in `server.py` (lines 483–563) uses `argparse.ArgumentParser` with flat flags:

```
homelab-mcp [--http] [--host HOST] [--port PORT] [--no-auth] [--api-key KEY] [--ssl-cert CERT] [--ssl-key KEY]
```

The entry point `homelab_mcp.server:main` is wired in `pyproject.toml`.

### Adding Subcommands Without Breaking Existing Behaviour

The challenge: adding `credentials add/list/remove` as subcommands while keeping `homelab-mcp` (no subcommand) as the MCP server start command.

**Pattern: subparsers with default behaviour when no subcommand given**

```python
def main() -> None:
    parser = argparse.ArgumentParser(...)

    # -- existing flags (--http, --host, --port, etc.) stay on the root parser --
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {_get_version()}")

    subparsers = parser.add_subparsers(dest="subcommand")

    # credentials subcommand
    creds_parser = subparsers.add_parser(
        "credentials",
        help="Manage stored credentials",
    )
    creds_sub = creds_parser.add_subparsers(dest="creds_action")

    # credentials add
    add_parser = creds_sub.add_parser("add", help="Store a credential")
    add_parser.add_argument("--hostname", required=True)
    add_parser.add_argument("--username", required=True)
    add_parser.add_argument("--password", required=False,
                            help="If omitted, prompted securely")
    add_parser.add_argument("--type", choices=["ssh", "proxmox"], default="ssh")

    # credentials list
    creds_sub.add_parser("list", help="List stored credentials")

    # credentials remove
    remove_parser = creds_sub.add_parser("remove", help="Remove a credential")
    remove_parser.add_argument("--hostname", required=True)

    args = parser.parse_args()

    # Dispatch
    if args.subcommand == "credentials":
        _run_credentials_cli(args)
    else:
        # Default: start MCP server (existing behaviour)
        _run_mcp_server(args)
```

**Why this is the correct pattern:**

- `args.subcommand` is `None` when no subcommand is given — existing `homelab-mcp` invocations continue to start the MCP server unchanged.
- The root-level flags (`--http`, `--port`, etc.) remain on the root parser and apply to the server-start path only.
- `credentials` dispatches to a synchronous CLI path that does not start the MCP server.
- No third-party CLI framework (Click, Typer) needed — argparse stdlib handles two levels of subcommands cleanly for this scope.

### Password Input Security

When adding a credential via CLI, never accept the password as a positional or flag argument (it would appear in shell history). Use `getpass.getpass()` for interactive prompts:

```python
import getpass

if not args.password:
    args.password = getpass.getpass(f"Password for {args.hostname}: ")
```

`getpass` is stdlib — no new dependency.

### `--version` Flag

```python
from importlib.metadata import version, PackageNotFoundError

def _get_version() -> str:
    try:
        return version("homelab-mcp")
    except PackageNotFoundError:
        return "unknown"

parser.add_argument("--version", action="version", version=f"%(prog)s {_get_version()}")
```

This follows the existing `importlib.metadata` pattern already used elsewhere in the project (server.py imports `version` from `importlib.metadata`).

### What NOT to Do for CLI Extension

| Avoid | Why |
|-------|-----|
| Click or Typer | New dependency for a two-level subcommand tree that argparse handles natively; breaks existing argparse-based invocation |
| `homelab-mcp-credentials` as a separate entry point | Confuses users; a single entrypoint with subcommands is more discoverable |
| Accepting password via `--password` flag | Appears in shell history and `ps aux` output; `getpass.getpass()` is the secure alternative |
| Starting MCP server when credentials subcommand is invoked | Credentials CLI is synchronous and must exit; starting the server would block |

---

## Installation

```bash
# Move keyring from optional to core deps in pyproject.toml, then:
uv sync

# Verify keyring is available
uv run python -c "import keyring; print(keyring.get_keyring())"

# Test credentials CLI (after implementation)
uv run homelab-mcp credentials add --hostname 192.168.1.10 --username admin --type ssh
uv run homelab-mcp credentials list
uv run homelab-mcp credentials remove --hostname 192.168.1.10

# Test --version
uv run homelab-mcp --version
```

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Credential storage | OS keyring (keyring lib) | SQLite device DB | Device DB is for topology data, not secrets; mixes concerns |
| Credential storage | OS keyring (keyring lib) | `keyrings.alt` PlaintextKeyring | Plaintext on disk is false security; no warning possible after the fact |
| Credential storage | OS keyring (keyring lib) | `cryptography` + custom file | Re-implements what keyring does; key management complexity |
| Headless fallback | `NoKeyringError` → env-var-only | `PYTHON_KEYRING_BACKEND=keyrings.alt...` | Forces plaintext fallback silently; homelab-mcp should be explicit |
| PyPI auth | Trusted Publishing (OIDC) | `UV_PUBLISH_TOKEN` GitHub secret | Token requires manual rotation; OIDC is keyless and scoped to the workflow run |
| CLI framework | argparse (stdlib) | Click / Typer | No new dependency justified for 3 subcommands; argparse already in use |

---

## Version Compatibility

| Package | Version Required | Notes |
|---------|-----------------|-------|
| keyring | >=25.6.0 | v25.6.0 removed spurious no-backend warning; `NoKeyringError` present since v23.x |
| pypa/gh-action-pypi-publish | release/v1 (v1.13.0+) | v1.13.0 fixed GHSA-vxmw-7h4f-hqxh; `release/v1` branch auto-tracks security fixes |
| Python | 3.12+ | No change — `getpass`, `argparse`, `importlib.metadata` all stdlib |

---

## Sources

- [keyring 25.7.0 documentation](https://keyring.readthedocs.io/en/latest/) — API methods, PYTHON_KEYRING_BACKEND, backend list (HIGH confidence)
- [keyring changelog / history](https://keyring.readthedocs.io/en/latest/history.html) — v25.6.0 warning removal, v25.4.0 AnonymousCredential, v25.7.0 KWallet 6 (HIGH confidence)
- [keyring PyPI page](https://pypi.org/project/keyring/) — latest version 25.7.0 confirmed (HIGH confidence)
- [PyPI Trusted Publishers documentation](https://docs.pypi.org/trusted-publishers/using-a-publisher/) — one-time setup, required fields, OIDC flow (HIGH confidence)
- [pypa/gh-action-pypi-publish GitHub](https://github.com/pypa/gh-action-pypi-publish) — workflow YAML, `release/v1` recommendation, permissions requirement (HIGH confidence)
- [Python Packaging User Guide — publishing with CI/CD](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/) — complete reference workflow (HIGH confidence)
- [Python stdlib argparse docs](https://docs.python.org/3/library/argparse.html) — `add_subparsers`, `set_defaults`, `dest` parameter (HIGH confidence)
- [keyring WSL2/headless issues #566, #569](https://github.com/jaraco/keyring/issues/566) — confirms NoKeyringError on headless Linux (MEDIUM confidence, issue tracker)
- `pyproject.toml` direct inspection — confirmed keyring already in optional security group, version constraint `>=25.0.0` (HIGH confidence)
- `server.py` direct inspection — confirmed existing argparse structure and `main()` entry point shape (HIGH confidence)

---

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| keyring API (set/get/delete/NoKeyringError) | HIGH | Official docs + pyproject.toml confirms lib already present |
| keyring fallback on headless Linux | HIGH | Official docs + multiple confirmed issue reports; NullKeyring path documented |
| Trusted publishing workflow YAML | HIGH | Official PyPI docs + Python Packaging User Guide + pypa action README |
| PyPI one-time setup requirement | HIGH | Official PyPI docs — no automation possible |
| argparse subparsers pattern | HIGH | Python stdlib docs; matches existing `main()` structure |
| `--version` implementation | HIGH | Existing `importlib.metadata` usage in codebase |

---

*Stack research for: Homelab MCP Server v1.3 Credentials & Release Automation*
*Researched: 2026-03-14*
