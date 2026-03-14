# Feature Research

**Domain:** CLI credential management + CI/CD release automation for Python MCP server
**Researched:** 2026-03-14
**Confidence:** HIGH (keyring API verified via official docs; argparse --version pattern verified against Python stdlib docs and existing codebase; PyPI OIDC workflow verified via PyPI docs and Python Packaging User Guide)

---

## Context: What Already Exists (v1.2 baseline)

Relevant to v1.3 scope only:

- **`resolve_ssh_credentials()`** in `ssh_tools.py` — three-step fallback chain: explicit args → DB `ssh_credentials` table → default mcp_admin SSH key. Keyring is not yet in the chain.
- **`ssh_credentials` DB table** — DatabaseAdapter has full CRUD (`add_credential`, `get_credential_by_hostname`, `list_credentials`, `delete_credential`). Password is NOT stored — only hostname, username, key_path, port.
- **`keyring` in optional-dependencies** — `pyproject.toml` has `keyring>=25.0.0` under `[project.optional-dependencies] security`. Not a core dependency. Must be promoted to core for CLI subcommand to work unconditionally.
- **`main()` in `server.py`** — argparse-based entry point exists with `--http`, `--host`, `--port`, `--no-auth`, `--api-key`, `--ssl-cert`, `--ssl-key`. No `--version` flag. No subcommands yet.
- **`importlib.metadata` version unification** — already done in v1.2. `version("homelab-mcp")` works. No new work needed for `--version`.
- **CI `main.yml`** — has `test-and-quality`, `integration-tests`, `cross-platform`, `security`, and `release` (GitHub Release) jobs. No PyPI publish job. The `release` job already gates on `startsWith(github.ref, 'refs/tags/')`.
- **`prompt_registry.py` PRMT-02** — `_build_decommission_result()` generates `hostname=` args for `decommission_device` calls. Tool schema requires `device_id` (integer). The mismatch causes AI to generate invalid tool calls.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist in a credential-managing CLI tool. Missing these = product feels broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `credentials add <host> <user> <pass>` | Standard CRUD entry point for any credential store | LOW | Positional args; `keyring.set_password("homelab-mcp-ssh", "<host>:<user>", password)` call |
| `credentials list` | Enumerate what's stored — user can't manage blind | LOW | List from keyring; show host + user, never echo password |
| `credentials remove <host> <user>` | Cleanup without manual OS keyring UI | LOW | `keyring.delete_password`; silent success if not found |
| Auto-inject on hostname match | Core payoff of storing creds — silent resolution during SSH tool calls | MEDIUM | Insert keyring lookup in `resolve_ssh_credentials()` at priority 2 (after explicit args, before DB) |
| `homelab-mcp --version` | Every CLI tool has this; users verify what's running | LOW | argparse `action="version"` + `importlib.metadata.version("homelab-mcp")` |
| Automated PyPI publish on `git tag v*` | `uvx homelab-mcp` users expect new versions without manual CI steps | MEDIUM | OIDC trusted publishing via `pypa/gh-action-pypi-publish@release/v1` |
| Graceful failure on missing OS keyring | Headless homelab servers lack GUI keyring; must not silently fail | LOW | Catch `keyring.errors.NoKeyringError`; emit actionable message with `PYTHON_KEYRING_BACKEND` hint |
| PRMT-02 bug fix | AI following prompt hits validation error — `hostname=` vs `device_id=` mismatch | LOW | Surgical change to `_build_decommission_result()` in `prompt_registry.py` |

### Differentiators (Competitive Advantage)

Features beyond table stakes that add compounding value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Proxmox creds storable via CLI | Alternative to `.env` file for Proxmox host credentials; especially useful for multi-host setups | MEDIUM | Separate keyring service "homelab-mcp-proxmox"; env vars still override |
| Per-credential-type service namespace | SSH and Proxmox creds isolated in keyring — no cross-type contamination; visible as distinct groups in OS keyring UI | LOW | Convention: `"homelab-mcp-ssh"` vs `"homelab-mcp-proxmox"` |
| Password never visible in list output | Passwords masked in `credentials list` output; matches `git credential` and `gh auth status` UX | LOW | `CredentialFilter` already exists in `log_filter.py`; same principle applied to CLI output |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Encrypted file-based credential store | "I don't want OS keyring dependency" | Reinvents keyring with worse security; file permission management is fragile cross-platform | Instruct users to set `PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring` for headless scenarios |
| `credentials update <host>` | Natural CRUD verb | keyring has no update primitive — `set_password` silently overwrites. A separate `update` subcommand creates false expectation of different behavior. | `credentials add` with same host/user silently overwrites; document this in help text |
| Credential rotation / expiry | "Security best practice" | Out of scope for single-operator homelab; adds persistent state (expiry timestamps) with no homelab benefit | Document `credentials remove` + `credentials add` as manual rotation procedure |
| SSH key generation via credentials CLI | "One credential management surface" | SSH key management already lives in `ssh_tools.ensure_mcp_ssh_key()`; conflates two distinct concerns | Keep key generation separate; `credentials` CLI handles username/password only |
| Credential groups / tags | "Organize by network segment" | Scope creep; homelab is single-operator with handful of hosts; hostname is sufficient discriminator | Use hostname as the natural grouping key |
| Publish on every merge to main | "Always latest on PyPI" | Risks bad/incomplete releases; PyPI versions are permanent; requires version bump discipline on every PR | Tag-gated publish: `git tag v1.3.0 && git push --tags` is the one release path |

---

## Credential Lookup Precedence Chain

This is the authoritative precedence order. All implementations must follow this chain exactly.

### SSH Credentials (in `resolve_ssh_credentials()`)

```
Priority 1 — Explicit args in tool call (password=, key_path= present)
    → Use as-is; return immediately. Backward compatible.

Priority 2 — OS keyring lookup [NEW in v1.3]
    → keyring.get_credential("homelab-mcp-ssh", "<hostname>:<username>")
    → If found: use stored username + password
    → If NoKeyringError or not found: continue to next priority

Priority 3 — DB ssh_credentials table (existing)
    → db.get_credential_by_hostname(hostname, username)
    → If found: use stored username + key_path (no password stored in DB)

Priority 4 — Default mcp_admin SSH key
    → If username is "mcp_admin" and ~/.ssh/mcp/mcp_admin_key exists: use it

Priority 5 — No credentials
    → Return minimal SSHCredentials; SSH tool will report auth failure
```

### Proxmox Credentials (in config.py MCPConfig)

```
Priority 1 — Environment variables
    → PROXMOX_HOST, PROXMOX_USER, PROXMOX_PASSWORD (or PROXMOX_TOKEN_ID + PROXMOX_TOKEN_SECRET)
    → If any relevant env var is set: use env vars; stop. (12-factor compatibility)

Priority 2 — OS keyring lookup [NEW in v1.3]
    → keyring.get_credential("homelab-mcp-proxmox", proxmox_host)
    → If found: use stored user + password

Priority 3 — No credentials
    → Raise configuration error with actionable message
```

**Why env vars beat keyring for Proxmox:** Proxmox is often run in Docker or CI where env vars are the standard injection mechanism. Keyring is an enhancement for interactive use, not a replacement.

---

## Keyring Service Naming Conventions

The Python keyring API: `keyring.set_password(service, username, password)` — stores exactly one password per `(service, username)` tuple.

| Credential Type | Service Name | Username Field | Password Field |
|----------------|--------------|----------------|----------------|
| SSH host credential | `homelab-mcp-ssh` | `<hostname>:<user>` | SSH password |
| Proxmox API credential | `homelab-mcp-proxmox` | `<proxmox_host>` | password or API token value |

**Service name rationale:**
- `homelab-mcp-ssh` groups all SSH entries as one visible namespace in OS keyring UI (Keychain, GNOME Keyring, Windows Credential Manager)
- The `:` separator in username field (`hostname:user`) encodes multi-user-per-host in the single username field, since keyring has no secondary key
- Service names are lowercase kebab-case matching the PyPI package name pattern

**Multi-user-per-host encoding:**
```python
keyring.set_password("homelab-mcp-ssh", "192.168.1.10:root", "root_pass")
keyring.set_password("homelab-mcp-ssh", "192.168.1.10:deploy", "deploy_pass")
# Lookup: keyring.get_credential("homelab-mcp-ssh", "192.168.1.10:root")
```

**CLI commands store username in the key:**
```
homelab-mcp credentials add 192.168.1.10 root hunter2
  → keyring.set_password("homelab-mcp-ssh", "192.168.1.10:root", "hunter2")

homelab-mcp credentials list
  → enumerate all entries under "homelab-mcp-ssh"

homelab-mcp credentials remove 192.168.1.10 root
  → keyring.delete_password("homelab-mcp-ssh", "192.168.1.10:root")
```

**Headless server fallback behavior:**
On servers without a GUI keyring, `keyring.set_password()` raises `keyring.errors.NoKeyringError`. The CLI must:
1. Catch `NoKeyringError` on `credentials add`
2. Print: `"No OS keyring available. Set PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring for file-based credential storage, or configure PROXMOX_* environment variables directly."`
3. Exit non-zero. Never silently succeed with no storage.

Auto-inject (in `resolve_ssh_credentials()`) must also catch `NoKeyringError` and continue to the next priority level rather than crashing.

---

## `--version` Flag Implementation Details

**Approach:** argparse `action="version"` built-in — prints and exits automatically.

```python
# In server.py main(), before parser.parse_args()
try:
    _pkg_version = version("homelab-mcp")
except PackageNotFoundError:
    _pkg_version = "dev"

parser.add_argument(
    "--version",
    action="version",
    version=f"homelab-mcp {_pkg_version}",
)
```

**Why:** `importlib.metadata.version()` and `PackageNotFoundError` are already imported in `server.py` (used for the existing version unification from v1.2). This is a 6-line change with zero new imports.

**Output format:** `homelab-mcp 1.3.0` — matches the convention of `git --version`, `python --version`, `uv --version`.

**What NOT to do:**
- Do not hardcode `"1.3.0"` — defeats v1.2's importlib.metadata unification
- Do not implement as a subcommand (`homelab-mcp version`) — `--version` is a standard global flag

---

## Automated PyPI Publishing Details

**Approach:** OIDC trusted publishing — no stored API tokens, no secrets in GitHub.

**One-time setup (PyPI project settings):**
1. Go to PyPI → Project `homelab-mcp` → Settings → Publishing
2. Add a new publisher:
   - Publisher: GitHub Actions
   - Owner: `<github_username_or_org>`
   - Repository: `mcp_python_server`
   - Workflow filename: `main.yml`
   - Environment name: `pypi` (optional; use if adding environment protection rules)

**GitHub Actions job to add to main.yml:**

```yaml
publish:
  name: Publish to PyPI
  runs-on: ubuntu-latest
  needs: [test-and-quality]
  if: startsWith(github.ref, 'refs/tags/v')
  environment: pypi
  permissions:
    id-token: write

  steps:
    - uses: actions/checkout@v6

    - name: Install uv
      uses: astral-sh/setup-uv@v4
      with:
        enable-cache: true
        cache-dependency-glob: "pyproject.toml"

    - name: Build distributions
      run: uv build

    - name: Publish to PyPI
      uses: pypa/gh-action-pypi-publish@release/v1
```

**Key constraints:**
- `id-token: write` at the job level is **mandatory** — OIDC exchange fails without it. Must be job-level, not workflow-level.
- `needs: [test-and-quality]` — tests must pass before publish. Never publish a broken release.
- `if: startsWith(github.ref, 'refs/tags/v')` — gates on `v*` prefix specifically. A bare `refs/tags/1.3.0` (no `v`) would not trigger.
- `uv build` produces both `.whl` and `.tar.gz` in `dist/` — pypa action uploads both.
- `environment: pypi` links to a GitHub environment — allows branch protection rules and required approvals.
- The existing `release` job (GitHub Release creation) remains unchanged; `publish` runs in parallel after `test-and-quality`.

**Version/tag alignment contract:**
- `pyproject.toml version = "1.3.0"` must match `git tag v1.3.0` (PyPI strips the `v`)
- PyPI rejects uploads where wheel version doesn't match the already-published version string
- The version bump commit must be merged to main and the `pyproject.toml` version must be correct before tagging
- Workflow: bump version in `pyproject.toml` → commit → merge to main → `git tag v1.3.0` → `git push --tags`

**Confidence:** HIGH — verified against PyPI official docs and Python Packaging User Guide.

---

## PRMT-02 Bug Analysis

**Location:** `src/homelab_mcp/prompt_registry.py`, function `_build_decommission_result()` (line 73-87)

**What's broken:**
- Prompt accepts argument `hostname` (string)
- Generated instructions tell AI: `Call decommission_device with hostname="{hostname}"`
- Tool schema (`infrastructure_tools_schema.py` line 105-110): `decommission_device` requires `device_id` (integer). There is no `hostname` parameter.
- Result: AI following the prompt generates an invalid tool call. Tool handler receives `hostname` instead of `device_id` and fails schema validation.

**Fix — Option A (recommended): Lookup workflow in prompt text**

Update `_build_decommission_result()` to generate:

```
1. Call list_devices to find the device with hostname matching "{hostname}". Note its device_id.
2. Call decommission_device_preview with device_id=<found_id> to preview the operation.
3. Present the preview result and ask for explicit user confirmation.
4. Only if confirmed: call decommission_device with device_id=<found_id>.
5. Report the result.
```

This approach is correct: the tool schema is right (integer device_id for precision), and the prompt guides AI through the natural lookup step.

**Fix — Option B: Add hostname alias to tool schema**
Accept `hostname` as optional alias, resolve in handler. This changes the tool schema and adds handler complexity. Not recommended — the tool schema is correct.

**Complexity:** LOW — 4-6 line change in `_build_decommission_result()`. No schema changes, no handler changes, no new imports. This is a pure prompt text fix.

---

## Feature Dependencies

```
[credentials add/list/remove CLI subcommand]
    └──requires──> [keyring promoted to core dependency in pyproject.toml]
    └──requires──> [argparse subparsers in server.py main()]
    └──requires──> [NoKeyringError handling]

[auto-inject SSH credentials]
    └──requires──> [credentials add CLI] (to populate keyring store)
    └──requires──> [keyring promoted to core dependency]
    └──modifies──> [resolve_ssh_credentials() in ssh_tools.py] (insert keyring at priority 2)
    └──coexists-with──> [DB ssh_credentials table] (DB becomes priority 3; keyring is priority 2)

[Proxmox creds via CLI]
    └──requires──> [credentials add CLI] (same CLI surface, --type proxmox flag)
    └──requires──> [keyring promoted to core dependency]
    └──modifies──> [config.py MCPConfig] (add keyring fallback after env var check)
    └──preserves──> [env vars PROXMOX_* take precedence] (env vars always win)

[homelab-mcp --version]
    └──depends-on──> [importlib.metadata version unification from v1.2] (already done — zero new work)
    └──modifies──> [server.py main() argparse setup] (add --version argument)

[automated PyPI publish]
    └──requires──> [OIDC trusted publisher configured on PyPI project] (one-time manual setup)
    └──requires──> [main.yml publish job] (new job added to workflow)
    └──depends-on──> [test-and-quality job passing] (needs: [test-and-quality])
    └──independent-of──> [credential store features] (can be done in any order)

[PRMT-02 fix]
    └──modifies──> [prompt_registry.py _build_decommission_result()]
    └──independent-of──> [all other v1.3 features] (pure bug fix, no new deps)
```

### Dependency Notes

- **keyring must become a core dependency:** Currently in `[project.optional-dependencies] security`. If it stays optional, `credentials add` fails for users who installed `uvx homelab-mcp` without extras. Promoted to `[project.dependencies]` so every installation has it.
- **DB ssh_credentials and keyring coexist:** The DB table stores key_path; the keyring stores passwords. They are complementary. Priority 2 (keyring) provides password-based SSH auth; priority 3 (DB) provides key-based SSH auth. Do not remove the DB path.
- **Proxmox keyring modifies config.py MCPConfig:** The `proxmox_host` is needed to look up the keyring entry, but MCPConfig currently reads host from env var `PROXMOX_HOST`. If `PROXMOX_HOST` env var is absent and keyring is being used, the host must come from the keyring entry itself — stored as the `username` field in the `homelab-mcp-proxmox` service. This is the correct design: the CLI stores the host in the username field, so `credentials add --type proxmox 192.168.1.100 root password` stores `keyring.set_password("homelab-mcp-proxmox", "192.168.1.100", "password")` where host is the username field.

---

## MVP Definition

### Launch With (v1.3 — all in scope per PROJECT.md)

- [ ] `keyring` promoted to core `[project.dependencies]` — prerequisite for all credential features
- [ ] `homelab-mcp credentials add <host> <user> <pass>` — writes to OS keyring `"homelab-mcp-ssh"` service
- [ ] `homelab-mcp credentials add --type proxmox <host> <user> <pass>` — writes to `"homelab-mcp-proxmox"` service
- [ ] `homelab-mcp credentials list` — lists host + user (no password) for all SSH keyring entries
- [ ] `homelab-mcp credentials remove <host> <user>` — removes from keyring; no error if not found
- [ ] Graceful `NoKeyringError` handling in both CLI and auto-inject code paths
- [ ] Auto-inject: `resolve_ssh_credentials()` checks keyring at priority 2 before DB
- [ ] Proxmox keyring fallback in `MCPConfig` at priority 2 after env vars
- [ ] `homelab-mcp --version` flag — outputs `homelab-mcp 1.3.0` and exits
- [ ] Automated PyPI publish job in `main.yml` on `startsWith(github.ref, 'refs/tags/v')`
- [ ] PRMT-02 fix: `_build_decommission_result()` generates `list_devices` lookup step, not `hostname=`

### Add After Validation (v1.x)

- [ ] `credentials verify <host> [<user>]` — test SSH connectivity with stored creds; report success/failure
- [ ] `credentials list --type proxmox` — list Proxmox keyring entries separately

### Future Consideration (v2+)

- [ ] `credentials export --format env` — dump stored creds as `.env` format for migration/backup
- [ ] Credential import from existing `.env` files

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| `credentials add/list/remove` CLI | HIGH | LOW | P1 |
| Auto-inject SSH on hostname match | HIGH | MEDIUM | P1 |
| `homelab-mcp --version` | MEDIUM | LOW | P1 |
| Automated PyPI publish (OIDC) | HIGH | MEDIUM | P1 |
| PRMT-02 fix | HIGH | LOW | P1 |
| Proxmox creds via CLI | MEDIUM | MEDIUM | P1 |
| Graceful NoKeyringError handling | HIGH | LOW | P1 |
| keyring promoted to core dependency | HIGH | LOW | P1 (prerequisite) |

All features are P1 — this is a focused milestone with no filler.

---

## Competitor Feature Analysis

| Dimension | AWS CLI credentials | GitHub CLI (`gh auth`) | Our Approach |
|-----------|---------------------|------------------------|--------------|
| Storage backend | `~/.aws/credentials` plaintext file | OS keyring (file fallback) | OS keyring via `keyring` library |
| Precedence | CLI flag > env var > profile file > default | flag > env var > stored | CLI arg > env var > keyring > DB > default key |
| List stored | `aws configure list-profiles` | `gh auth status` | `credentials list` (host + user, masked password) |
| Remove | Manual file edit | `gh auth logout` | `credentials remove <host> <user>` |
| Headless | File always works; no keyring needed | Graceful error with fallback hint | Actionable error + `PYTHON_KEYRING_BACKEND` env hint |
| Version flag | `aws --version` | `gh --version` | `homelab-mcp --version` |
| Release automation | Internal CI | GitHub Actions OIDC | GitHub Actions OIDC (`pypa/gh-action-pypi-publish`) |

---

## Sources

- [keyring 25.7.0 documentation](https://keyring.readthedocs.io/) — `set_password`/`get_password`/`get_credential` API, `NoKeyringError`, backend behavior
- [Publishing to PyPI with a Trusted Publisher](https://docs.pypi.org/trusted-publishers/) — OIDC trusted publishing overview
- [Using a Trusted Publisher — PyPI Docs](https://docs.pypi.org/trusted-publishers/using-a-publisher/) — `id-token: write` requirement, workflow structure
- [Python Packaging User Guide: Publishing with GitHub Actions](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/) — canonical workflow structure
- [pypa/gh-action-pypi-publish GitHub](https://github.com/pypa/gh-action-pypi-publish) — action reference; PEP 740 attestations default in v1.11+
- [Python argparse docs: action="version"](https://docs.python.org/3/library/argparse.html) — built-in version action
- [keyring NoKeyringError on headless Ubuntu — jaraco/keyring issue #477](https://github.com/jaraco/keyring/issues/477) — confirmed headless failure mode
- [Python keyring backends: SecretService, Windows Credential Manager 2025](https://johal.in/python-keyring-backends-secretservice-windows-credential-manager-support-2025/) — platform availability matrix
- Codebase inspection (HIGH confidence): `src/homelab_mcp/ssh_tools.py` (`resolve_ssh_credentials`, `SSHCredentials`), `src/homelab_mcp/config.py` (`MCPConfig`, env var reading), `src/homelab_mcp/server.py` (`main()`, `importlib.metadata` usage), `src/homelab_mcp/prompt_registry.py` (PRMT-02 location), `src/homelab_mcp/tool_schemas/infrastructure_tools_schema.py` (`decommission_device` schema), `pyproject.toml` (keyring in optional-dependencies, CI workflow shape), `.github/workflows/main.yml` (existing job structure)

---

*Feature research for: homelab-mcp v1.3 — credential management + release automation*
*Researched: 2026-03-14*
