# Pitfalls Research

**Domain:** Python CLI tool — adding OS keyring credential storage and GitHub Actions PyPI release automation to an existing project
**Researched:** 2026-03-14
**Project context:** homelab-mcp v1.3, existing SQLite credential store, existing `server.py:main()` flat argparse, existing `log_filter.py` redaction, existing `main.yml` CI workflow

> **Note:** This file covers v1.3 Credentials & Release Automation pitfalls.
> v1.2 Protocol Completeness pitfalls (service_templates wheel bundling, version unification, MCP Prompts, dry-run split, drift Resource) are appended at the bottom of this file.

---

## Critical Pitfalls

---

### Pitfall 1: Keyring `NoKeyringError` Crashes the Server on Headless Linux

**What goes wrong:**
When `keyring.get_password()` or `keyring.set_password()` is called on a headless Linux machine — no D-Bus session, no GNOME Keyring, no KWallet — keyring raises `keyring.errors.NoKeyringError: No recommended backend was available`. This is an unguarded exception that propagates to the caller. The primary deployment target for this project is a headless Proxmox host accessed via `uvx homelab-mcp`. Docker containers are equally affected: libsecret/GNOME Keyring requires `--privileged` and an explicit daemon setup that no homelab user will configure.

The project already ships `keyring` as an optional extra (`[security]`). The risk is not a missing import — it is that `keyring` is installed (because the user ran `pip install homelab-mcp[security]`) but no OS backend exists. `ImportError` and `NoKeyringError` are separate failure modes and must both be handled. Older keyring versions (pre-24) raise `RuntimeError` instead of `NoKeyringError`, so catching only `NoKeyringError` is insufficient.

**Why it happens:**
Developers test on macOS (Keychain) or a graphical Linux desktop (SecretService). GitHub-hosted Ubuntu runners lack a D-Bus session. The disconnect between dev environment and target environment is total: every dev machine has a backend; no Proxmox host has one.

**How to avoid:**
1. Wrap every keyring call in `try/except (keyring.errors.NoKeyringError, RuntimeError, Exception)`. The broad `Exception` guard handles older keyring versions and unexpected `InitError` variants.
2. On exception, fall back silently to the existing SQLite credential store (`database.py`) — this backend is already proven and handles the headless case correctly.
3. Never call keyring at module import time, at server startup, or in `resolve_ssh_credentials()` where a crash prevents all SSH tool calls. Only call keyring inside explicit CLI subcommand handlers (`credentials add`/`credentials remove`).
4. Log at `DEBUG` level (not `WARNING`) when falling back — this is expected behaviour on headless deployments, not a problem.
5. Keep `keyring` as an optional extra. Do not promote it to a required dependency.

Minimal guard pattern:
```python
def _keyring_get(service: str, key: str) -> str | None:
    try:
        import keyring
        return keyring.get_password(service, key)
    except ImportError:
        return None  # keyring[security] not installed
    except Exception:  # NoKeyringError, RuntimeError, InitError
        return None  # no OS backend available; caller falls back to SQLite
```

**Warning signs:**
- `homelab-mcp credentials add hostname=192.168.1.10` raises an unhandled exception on the Proxmox host after install.
- Unit tests pass locally (macOS) but CI fails because the GitHub runner has no D-Bus session.
- Any call path that hits keyring causes `homelab-mcp` to crash before the MCP server loop starts.

**Phase to address:**
The phase that introduces keyring calls. Must be addressed before any keyring call is added to `ssh_tools.py`, `config.py`, or any module invoked during server startup.

---

### Pitfall 2: Argparse Subparsers Break the Existing Bare Invocation

**What goes wrong:**
`server.py:main()` uses a flat `ArgumentParser` with no subcommands. Adding `credentials` as a subparser via `add_subparsers()` changes how argparse handles invocation. The critical failure: `homelab-mcp` (bare, no args) may start printing a usage error instead of launching the MCP server in stdio mode, breaking every Claude Desktop / MCP client connection that starts the server without arguments.

The underlying issue is argparse's `required` behaviour for subparsers: it changed between Python versions (required in 3.3–3.8, not required in 3.9+). Python 3.12 (the project minimum) defaults `required=False` for subparsers, but the behaviour of `parse_args([])` when subparsers are defined without `set_defaults(func=...)` is to produce an `args` namespace where `args.func` does not exist — which causes an `AttributeError` in any handler that calls `args.func(args)` unconditionally.

Additionally, `homelab-mcp --http --port 8080` (the documented HTTP mode invocation) must continue to work. Adding subparsers does not break `--http` positionally, but if the dispatch logic changes to `args.func(args)` without checking for the no-subcommand case, HTTP mode is unreachable.

**Why it happens:**
The developer adds subparsers, tests `homelab-mcp credentials add`, and it works. They do not re-test bare `homelab-mcp` or `homelab-mcp --http` — the MCP client integration test is not in the unit suite. The regression is invisible until a user upgrades.

**How to avoid:**
1. Call `parser.set_defaults(func=_run_server)` on the root parser so bare invocation dispatches to the existing server startup function.
2. Set `subparsers.required = False` explicitly — do not rely on version-specific defaults.
3. In dispatch: `getattr(args, 'func', _run_server)(args)` — fall back to server startup if no subcommand was given.
4. Add a regression test: `parser.parse_args([])` must not raise; `args` must route to server startup. `parser.parse_args(['--http'])` must set `args.http = True`.
5. The `credentials` subcommand handler must not call `get_resource_manager()` or require the MCP server lifespan to be running.

**Warning signs:**
- `homelab-mcp` (no args) prints usage and exits instead of "MCP Server starting in stdio mode..."
- Claude Desktop or any MCP client shows a connection error immediately after upgrade.
- `homelab-mcp --version` works but bare `homelab-mcp` does not.

**Phase to address:**
The CLI subcommand phase (adding `credentials add/list/remove`). The regression test for bare invocation must be a quality gate before the phase is complete.

---

### Pitfall 3: PyPI OIDC Trusted Publishing Fails with `invalid-publisher` Due to Configuration Mismatch

**What goes wrong:**
Trusted publishing requires that the PyPI-side publisher configuration (registered at pypi.org/manage/account/publishing) exactly matches the GitHub Actions workflow. Common mismatches — all confirmed by the official PyPI troubleshooting docs:

- **Workflow filename mismatch**: PyPI expects the bare filename (`publish.yml`), not the path (`.github/workflows/publish.yml`).
- **Environment name mismatch**: The `environment:` key in the workflow job must exactly match the environment name registered on PyPI. Omitting it when PyPI expects a named environment (or vice versa) causes `invalid-publisher`.
- **Hyphen/underscore confusion**: This project's package is `homelab-mcp` (hyphen). Registering the trusted publisher under `homelab_mcp` (underscore) produces `invalid-publisher`. PyPI normalises hyphens and underscores for package lookup but not for trusted publisher matching.
- **Missing `id-token: write` permission**: Without this, GitHub Actions cannot issue an OIDC token. The job silently receives an empty token and PyPI rejects it.
- **Workflow-level `read-all` overrides job-level `id-token: write`**: If the workflow has `permissions: read-all` at the top level, job-level permission grants do not expand beyond that.

**Why it happens:**
The PyPI trusted publisher UI cannot be tested without triggering the full workflow. The developer sets up the PyPI side once, pushes a tag, and only then discovers the mismatch. Fixing requires either updating the PyPI registration or the workflow, then pushing another tag — consuming another version number on TestPyPI or requiring a `post1` release on production PyPI.

**How to avoid:**
1. Before adding the publish workflow: ensure the `homelab-mcp` PyPI project exists (it was published manually in v1.2) and the trusted publisher is registered there, not via a pending publisher for a new project.
2. Use `pypa/gh-action-pypi-publish` (the official action) — it handles the OIDC token exchange and provides cleaner error messages than manual `twine` with OIDC tokens.
3. Set `permissions: id-token: write` at the **job level** in the publish job. Do not set `permissions: read-all` at the workflow level.
4. Publish job must be separate from the build job. Trusted publishing requires elevated permissions that the build job should not have.
5. Validate with a TestPyPI dry run before the first production tag: set `repository-url: https://test.pypi.org/legacy/` and verify the OIDC handshake succeeds.

**Warning signs:**
- Workflow shows "Minting OIDC token..." then fails with HTTP 403 and `invalid-publisher`.
- PyPI shows the project does not exist (pending publisher but no project yet).
- Build artifact is in workflow artifacts but publish step failed.

**Phase to address:**
The CI/CD release automation phase. TestPyPI validation is a required quality gate before `v1.3.0` is tagged on production PyPI.

---

### Pitfall 4: CI Double-Publish — Workflow Triggers on Both Tag Push and Branch Push

**What goes wrong:**
The existing `main.yml` triggers on `push: branches: [main, develop]` AND `push: tags: ['v*']`. The current `release` job already guards with `if: startsWith(github.ref, 'refs/tags/')`. If the new publish job is added to the same workflow file, it is subject to the same trigger matrix. The danger:

- If the publish condition is accidentally written as `if: github.event_name == 'push'` (without the tag check), every merge to `main` triggers a publish attempt.
- Even with correct tag filtering, a single tag push triggers both the branch push handler (which runs tests) and the tag push handler (which publishes). This is correct, but if the workflow is split incorrectly, one run may attempt to publish before tests complete.
- `skip_existing: true` on production PyPI masks errors — a silently skipped publish looks like a successful one.

**Why it happens:**
Publish conditions are cargo-culted from build conditions. The `on: push: tags` trigger is less common than branch triggers. The existing `main.yml` has a working pattern for the GitHub Release job — the publish job must follow the same `if:` guard, or better, live in a separate workflow file.

**How to avoid:**
1. Put the publish job in a **separate workflow file** (`publish.yml`) triggered only by `on: push: tags: ['v*']`. This is the recommended approach from the Python Packaging User Guide.
2. Add `needs: [build]` so publish only runs after tests pass.
3. Never use `skip_existing: true` on production PyPI. Use it only on TestPyPI.
4. Add a redundant `if: startsWith(github.ref, 'refs/tags/v')` guard even in the tag-only workflow, as an explicit safety net.

**Warning signs:**
- The publish job appears in the workflow run list for a non-tag push (a `main` branch merge).
- PyPI shows "File already exists" after a successful first upload — means a second publish attempt was made.
- `dist/` artifact contains a version that does not match the git tag (version/tag mismatch; see below).

**Phase to address:**
The CI/CD release automation phase. The separate workflow file structure must be established before pushing the first `v1.3.0` tag.

---

### Pitfall 5: Credential Leak Through Exception Messages in New Logging Paths

**What goes wrong:**
`log_filter.py` provides `CredentialFilter` and `sanitize_error()`. These cover patterns like `password=`, `token=`, `PVEAPIToken=`, and `Authorization:` headers. The new credential store and auto-inject path introduces new failure modes that the existing patterns may not cover:

- `asyncssh` connection errors with auto-injected credentials sometimes include the username and hostname in the error message, but not the password. However, if the caller logs `f"SSH error for {creds.hostname}: {e}"` and `creds.password` is somehow embedded in `e` (e.g., via a repr), the existing filters do not catch a bare password string without a recognizable prefix.
- Proxmox token values stored in the credential store are UUID-format strings (e.g., `abc123...`). If logged without the `PVEAPIToken=` prefix, they pass through `_SENSITIVE_PATTERNS` unredacted.
- `keyring.errors.PasswordDeleteError` and `keyring.errors.PasswordSetError` include the service name and key in their messages — not the secret value — but careful review is needed to confirm this in all keyring versions.

**Why it happens:**
The existing `_SENSITIVE_PATTERNS` are prefix-anchored. A secret value appearing without a keyword prefix in an exception chain bypasses all patterns. New code paths that store and retrieve credentials create new places where secrets could appear in exceptions.

**How to avoid:**
1. Never log credential values — not the password string, not the Proxmox token value. Log only `hostname`, `username`, and `credential_id` (the SQLite integer).
2. Every `except` block in `ssh_tools.py`, `proxmox_api.py`, and the new credential module must use `sanitize_error(e)` (already in `log_filter.py`), never `str(e)`.
3. When auto-injected credentials fail SSH connection, the error logged must include only `hostname` and a note that stored credentials were tried — never the credential value.
4. Write a unit test: mock an SSH connection failure where `SSHCredentials.password = "secret123"`; assert that `caplog.text` does not contain `"secret123"` after the failure is logged.

**Warning signs:**
- Any `logger.debug(f"... {e}")` in `ssh_tools.py` or `proxmox_api.py` where `e` is an asyncssh or aiohttp exception that could contain connection details.
- New logging calls in the credential module that log the full `arguments` dict from a tool handler (which may contain `password=` as a tool input).

**Phase to address:**
Credential auto-inject implementation phase. Every new logging call in modules that touch credentials must be reviewed.

---

### Pitfall 6: Auto-Inject Silently Overrides Explicitly Passed Credentials

**What goes wrong:**
`resolve_ssh_credentials()` already implements a priority order: explicit credentials win over stored credentials. However, the implementation checks `if password or key_path` — if neither is passed but `username="root"` is explicit, the function falls through to the database lookup and may inject a stored credential for a different user on the same hostname. The tool caller specified `username="root"` but got a different user's SSH key.

The v1.3 milestone also adds Proxmox API credentials to the store. The spec says "env vars take precedence." If the implementation checks env vars only at startup and stores the resolved value, a user who rotates their env var without restarting the server gets the stale stored value injected silently.

**Why it happens:**
Priority order is documented but not enforced by tests. The MCP tool response says "connected successfully" — the caller cannot tell whether env vars, stored credentials, or the default key was used.

**How to avoid:**
1. When stored credentials are auto-injected, include `"credential_source": "stored (id=N, hostname=...)"` in the tool response (as an informational field, not the primary text).
2. Env vars for Proxmox must be checked at call time, not at startup. If `PROXMOX_TOKEN` is set, never consult the credential store for that host, regardless of what is stored.
3. `resolve_ssh_credentials()` must check explicit `username` separately from `password`/`key_path`: an explicit username with no explicit credential should still win over a stored credential for a different username on the same host.
4. TDD: write tests specifying the priority order as assertions before implementing.

**Warning signs:**
- A tool call with `username="root"` connects as a different user (stored credential has `username="mcp_admin"`).
- A Proxmox tool call works without env vars set, and the user has no memory of storing credentials.
- After rotating `PROXMOX_TOKEN` env var, tools continue to use the old token (stale stored credential injected).

**Phase to address:**
Credential auto-inject implementation phase. Priority rules must be specified as test cases (TDD wave-0) before implementation.

---

### Pitfall 7: Version in `pyproject.toml` Does Not Match Git Tag at Publish Time

**What goes wrong:**
The publish workflow builds a wheel from the current commit and uploads it to PyPI. If `pyproject.toml` still says `version = "1.2.0"` when the `v1.3.0` tag is pushed (because the developer forgot to bump the version before tagging), PyPI receives a `1.2.0` wheel from a `v1.3.0` tag push. PyPI will reject the upload if `1.2.0` already exists. If somehow it does not reject (e.g., on TestPyPI with a post-release suffix), users `pip install homelab-mcp==1.3.0` but the package metadata says `1.3.0` while the installed code reports `1.2.0` via `importlib.metadata`.

**Why it happens:**
The project uses a static version in `pyproject.toml` (confirmed by codebase inspection). Tag and version bump are separate manual steps. The developer pushes the tag before bumping the version, or bumps the version on `main` after tagging.

**How to avoid:**
1. Add a CI check in the publish workflow that verifies the `pyproject.toml` version matches the tag before building: `python -c "from importlib.metadata import version; v = version('homelab-mcp'); tag = '${{ github.ref_name }}'.lstrip('v'); assert v == tag, f'Version {v} != tag {tag}'"`.
2. Document the release process: bump version in `pyproject.toml`, commit, tag, push — in that order.
3. Consider using `hatch-vcs` or `setuptools-scm` to derive version from the git tag automatically, eliminating the manual step entirely. This project already uses hatchling, so `hatch-vcs` is a natural fit.

**Warning signs:**
- Publish workflow completes but the uploaded version on PyPI differs from the tag name.
- `importlib.metadata.version("homelab-mcp")` returns a different value than `git describe --tags`.

**Phase to address:**
CI/CD release automation phase. The version-tag check must be a CI step that gates the publish job.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Store Proxmox token in SQLite in plaintext (no keyring encryption) | Works on headless, simpler implementation | Token readable by any process with `~/.mcp/sitemap.db` access | Acceptable as v1.3 baseline; document the risk; add keyring encryption in v1.4 |
| Single `main.yml` for tests + publish | One fewer file to maintain | Accidental publish on non-tag push; harder to audit permissions | Never — separate workflow files for publish |
| Skip TestPyPI validation and publish directly to production | Faster first publish | Cannot retract bad release; version consumed on failure | Never for first use of a new workflow |
| Bare `except Exception` on all keyring calls | Ensures headless fallback | Swallows unexpected errors (disk full, permission denied) | Acceptable; log at `WARNING` level so unexpected failures are visible |
| Interactive password prompt in `credentials add` | Matches user expectation | Hangs in non-interactive shells (CI, scripts, MCP client subprocess) | Never as default; always offer `--password` flag as alternative |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| keyring on headless Linux | Calling `keyring.set_password()` without catching `NoKeyringError` | Wrap all keyring calls; fall back to SQLite on any exception |
| PyPI OIDC trusted publishing | `id-token: write` at workflow level when `read-all` is also set | Set `id-token: write` per-job only; never use `read-all` on the publish workflow |
| PyPI project name | Registering trusted publisher as `homelab_mcp` (underscore) | Use `homelab-mcp` (hyphen) — must match `pyproject.toml` name exactly |
| `pypa/gh-action-pypi-publish` | Build and publish in the same job | Separate jobs: `build` (no elevated permissions) → `publish` (`id-token: write`) |
| asyncssh exception messages | `logger.debug(f"error: {e}")` in new credential paths | Always use `sanitize_error(e)` from `log_filter.py` |
| Proxmox credential precedence | Storing token via `credentials add` then forgetting env var takes precedence | Check env var at call time; document and test precedence order explicitly |
| argparse `add_subparsers()` | Not testing bare `homelab-mcp` invocation after adding subparsers | Regression test: `parse_args([])` routes to server startup without error |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Synchronous keyring call inside async SSH handler | Event loop blocked during OS keychain unlock (100–500ms) | Run `keyring.get_password()` via `asyncio.to_thread()` if called from async context | Every SSH tool call that resolves credentials via keyring |
| SQLite credential lookup on every SSH connection attempt | Database open/close overhead per call | Cache resolved credentials in `ResourceManager` for the server lifespan | Noticeable at >10 concurrent SSH tool calls |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Proxmox token stored in SQLite without encryption | Token readable by any local process | Use keyring for token value when backend available; warn at `WARNING` level when falling back to plaintext SQLite |
| SSH private key passphrase stored alongside key path | Passphrase on disk defeats key protection | Store only the key path; never accept or store passphrases |
| Credential value appearing in MCP tool error response | AI client logs MCP responses; credential leaks to conversation history | All error responses in `ssh_tools.py` and `proxmox_api.py` must use `sanitize_error(e)` |
| `credentials add` accepting password as positional CLI arg | Password appears in shell history and `ps aux` | Always use `--password` flag (not positional); or prompt interactively with `getpass` |
| Publish job has `contents: write` AND `id-token: write` | Overly broad permissions increase workflow blast radius | Publish job needs only `id-token: write`; GitHub Release creation uses a separate job with `contents: write` |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| `NoKeyringError` shown as a user-visible error message | User thinks installation is broken; server is actually functional | Log at `DEBUG`; on success return `"credential stored in SQLite (keyring not available on this system)"` |
| `credentials list` shows `key_path` values without checking whether the file still exists | User trusts listed credentials are usable; stale paths cause confusing SSH failures | Show `[key file not found]` warning when `key_path` is set but the file is missing |
| `--version` flag added as subparser argument instead of root parser argument | `homelab-mcp --version` works; `homelab-mcp credentials --version` behaves differently | Add `--version` to the root parser before `add_subparsers()` is called |
| Auto-inject provides no feedback to the tool caller | User cannot tell which credential source was used; debugging stale credentials is hard | Include `"credential_source"` in tool response metadata when auto-inject fires |

---

## "Looks Done But Isn't" Checklist

- [ ] **Keyring headless fallback:** `homelab-mcp credentials add hostname=192.168.1.10` completes without error on a machine where `DBUS_SESSION_BUS_ADDRESS` is unset — verify by running `env -u DBUS_SESSION_BUS_ADDRESS homelab-mcp credentials add ...`.
- [ ] **Bare invocation not broken:** `echo '{"jsonrpc":"2.0","method":"initialize","params":{},"id":1}' | homelab-mcp` responds without a usage error — regression test for stdio MCP mode.
- [ ] **Trusted publisher registered before first tag:** PyPI project `homelab-mcp` has the GitHub Actions publisher configured at pypi.org before pushing `v1.3.0` — this cannot be done retroactively without a fallback token.
- [ ] **Tag-only publish:** `git push origin main` does NOT trigger the publish workflow job — verify by checking Actions run list after a non-tag push.
- [ ] **Credential not in logs:** After a failed SSH connection with auto-injected stored credentials, `grep -i "password\|secret\|token" <log>` finds no credential values.
- [ ] **Env var precedence:** With `PROXMOX_TOKEN` set and a stored credential for the same host, the env var wins — verified by a unit test with both present.
- [ ] **Version matches tag:** `pyproject.toml version = "1.3.0"` before the `v1.3.0` tag is pushed — CI verifies this before the publish job runs.
- [ ] **TestPyPI dry run passes:** The publish workflow succeeds against `https://test.pypi.org/legacy/` before any production publish attempt.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Server crashes on headless due to `NoKeyringError` | HIGH — requires hotfix release | Add `except Exception` guard to all keyring calls; release `v1.3.1` |
| Bare invocation broken by subparsers | HIGH — all MCP clients stop working | Revert subparser dispatch change; release patch; add regression test |
| PyPI `invalid-publisher` on first tag push | LOW — no artifact leaked | Fix publisher config on PyPI or fix workflow filename/environment; push new tag |
| Double publish (version already exists on PyPI) | LOW — second upload fails, first was correct | No action needed if first upload was correct |
| Credential value leaked in logs | HIGH — security advisory required | Scrub logs; add `sanitize_error()` call in the affected path; release patch |
| Wrong version published (pyproject.toml / tag mismatch) | HIGH — version is permanently on PyPI | Yank the release on PyPI (`pip index versions homelab-mcp`, then `twine` yank); publish corrected version as patch |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Keyring `NoKeyringError` crashes server | Credential store implementation | Test: `credentials add` with no D-Bus session raises no exception |
| Argparse subparsers break bare invocation | CLI subcommand phase | Regression test: `parse_args([])` routes to server startup |
| PyPI OIDC `invalid-publisher` | CI/CD automation phase | TestPyPI dry run before tagging `v1.3.0` |
| Double publish on non-tag push | CI/CD automation phase | Verify: push to `main` does not trigger publish job |
| Credential leak in exception messages | Credential auto-inject phase | Unit test: `caplog.text` contains no credential value on SSH failure |
| Auto-inject silent override | Credential auto-inject phase | TDD: priority order tests before implementation |
| Proxmox env var precedence violated | Credential auto-inject phase | Unit test: env var set + stored credential present → env var wins |
| Version / tag mismatch at publish time | CI/CD automation phase | CI step: assert `pyproject.toml` version equals tag name before build |

---

## Sources

- [keyring 25.7.0 documentation](https://keyring.readthedocs.io/) — backend unavailability, exception types (HIGH confidence)
- [WSL2+Debian NoKeyringError — jaraco/keyring issue #566](https://github.com/jaraco/keyring/issues/566) — confirmed `NoKeyringError` in headless Linux (HIGH confidence)
- [NoKeyringError in pypa/hatch — issue #671](https://github.com/pypa/hatch/issues/671) — real project hit by same issue (HIGH confidence)
- [PyPI Trusted Publishers: Troubleshooting](https://docs.pypi.org/trusted-publishers/troubleshooting/) — `invalid-publisher`, permission errors (HIGH confidence, official docs)
- [PyPI Trusted Publisher Management and Pitfalls — dreamnetworking.nl, 2025](https://dreamnetworking.nl/blog/2025/01/07/pypi-trusted-publisher-management-and-pitfalls/) — hyphen/underscore mismatch, environment name mismatch (MEDIUM confidence)
- [pypa/gh-action-pypi-publish](https://github.com/pypa/gh-action-pypi-publish) — build/publish job separation (HIGH confidence, official action)
- [Publishing with GitHub Actions — Python Packaging User Guide](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/) — tag-only trigger, separate workflow file (HIGH confidence)
- [GitHub Actions: avoid double runs — Adam Johnson, 2025](https://adamj.eu/tech/2025/05/14/github-actions-avoid-simple-on/) — double-trigger prevention (MEDIUM confidence)
- [argparse documentation — Python 3.12](https://docs.python.org/3/library/argparse.html) — `add_subparsers()` required behaviour (HIGH confidence)
- [argparse required subparsers change — CPython issue #77290](https://github.com/python/cpython/issues/77290) — version-specific default history (HIGH confidence)
- Project codebase: `src/homelab_mcp/log_filter.py`, `src/homelab_mcp/ssh_tools.py`, `src/homelab_mcp/server.py`, `src/homelab_mcp/config.py`, `pyproject.toml`, `.github/workflows/main.yml` (HIGH confidence, first-party)

---

---

## Appendix: v1.2 Protocol Completeness Pitfalls

> Preserved from prior milestone research. These pitfalls are addressed in v1.2 and should be verified complete before v1.3 phases begin.

**Domain:** Python MCP server — PyPI packaging, MCP Prompts, dry-run tool split, drift MCP Resource
**Researched:** 2026-03-12

### Critical: `service_templates` YAML files excluded from wheel

`service_templates/*.yaml` must be bundled via `importlib.resources`, not `__file__`-relative paths. Explicitly declare YAML inclusion in pyproject.toml. Add a wheel smoke test before publish.

**Phase:** PyPI packaging — completed in v1.2.

---

### Critical: Version mismatch between `pyproject.toml` and `__init__.py`

Remove `__version__` from `__init__.py`; use `importlib.metadata.version("homelab-mcp")` as the single source of truth.

**Phase:** PyPI packaging — completed in v1.2.

---

### Critical: `*_preview` dry-run tools missing from `tool_annotations.py`

Annotation coverage test: assert every key in `get_all_tool_schemas()` has a corresponding entry in `TOOL_ANNOTATIONS`. Prevents silent annotation gaps.

**Phase:** Dry-run tool split — completed in v1.2.

---

### Critical: Renaming existing destructive tools breaks MCP clients

Keep all existing destructive tool names unchanged. Add `*_preview` variants as additive new tools only.

**Phase:** Dry-run tool split — completed in v1.2.

---

### Critical: `homelab://drift/latest` URI omitted from `HOMELAB_RESOURCES` dict

Resource is readable by URI but not discoverable via `resources/list`. Add to registry atomically with the reader function.

**Phase:** Drift MCP Resource — completed in v1.2.

---

### Moderate: Drift Resource serving stale data without staleness indicator

Always include `scanned_at` ISO 8601 UTC in payload; add `staleness_warning` when data age exceeds threshold.

**Phase:** Drift MCP Resource — completed in v1.2.

---

### Moderate: Drift Resource crashes when no scan has ever run

Return structured empty-state response: `{"drift_report": null, "status": "no_scan_run"}`. Never raise on first access.

**Phase:** Drift MCP Resource — completed in v1.2.

---

*v1.2 pitfalls section condensed. Full detail in git history of this file.*

---

---

## Appendix: v1.1 Safety & Observability Pitfalls

> Preserved from prior milestone research. These pitfalls are addressed in v1.1.

**Researched:** 2026-03-11

Addressed: dry-run handler that cannot execute the real path; dry-run performing real side effects; drift detection flagging transient state as drift; MCP Resources returning stale data without `scanned_at`; `ResourceManager.proxmox_session` not wired into handlers; drift baseline not updated after mutation tool calls.

*v1.1 pitfalls section condensed. Full detail in git history of this file.*

---

*Pitfalls research for: homelab-mcp v1.3 — keyring credential store + GitHub Actions PyPI release automation*
*Researched: 2026-03-14*
