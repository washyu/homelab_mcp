# Project Research Summary

**Project:** Homelab MCP Server — v1.3 Credentials & Release Automation
**Domain:** Python CLI tool — OS keyring credential management + CI/CD release automation
**Researched:** 2026-03-14
**Confidence:** HIGH

## Executive Summary

v1.3 is a tightly scoped, low-risk milestone with one net-new runtime dependency and no architectural changes. The work breaks cleanly into three independent tracks: (1) credential store — a new `credential_store.py` module wrapping `keyring>=25.6.0` with full headless fallback, wired into the existing SSH and Proxmox credential priority chains; (2) CLI extension — adding `--version` and `credentials add/list/remove` subcommands to the existing `server.py` `main()` argparse entrypoint without breaking bare invocation; (3) CI/CD automation — a `publish` job added to `main.yml` using OIDC trusted publishing. All integration points have been verified by direct codebase inspection; all patterns are well-established. The only genuinely novel element is the OIDC trusted publisher setup, which requires a one-time manual step in the PyPI project settings before any tag is pushed.

The primary deployment target — headless Proxmox hosts — has no OS keyring backend available. This is the dominant risk in the milestone: every keyring call path must catch `keyring.errors.NoKeyringError` (and the older `RuntimeError` for pre-v24 compatibility) and fall back gracefully. The keyring feature is a convenience for desktop users; env vars remain the fully supported credential path for headless servers. The existing SQLite `ssh_credentials` table handles key-based SSH auth and is unchanged — keyring slots in at priority 2 for password-based auth, keeping all existing behaviour intact.

The bug fix for PRMT-02 (`_build_decommission_result()` generating `hostname=` instead of `device_id=` in tool call instructions) is independent of all other work and can be delivered in any phase. All seven work items in this milestone are P1 — there is no filler — but the build order is dictated by a single dependency: `credential_store.py` must exist before the CLI subcommands, SSH auto-inject, or Proxmox config fallback can be wired up.

---

## Key Findings

### Recommended Stack

v1.3 introduces one net-new runtime dependency: `keyring>=25.6.0` promoted from `[project.optional-dependencies] security` to `[project.dependencies]`. Version 25.6.0 specifically is required because it removes spurious no-backend warning logs, making the `NoKeyringError` fallback detection clean. All other runtime dependencies (asyncssh, aiohttp, starlette, uvicorn, rich, pydantic) are unchanged. The PyPI publish automation requires no new dependencies — `uv build` and `pypa/gh-action-pypi-publish@release/v1` are workflow-only additions. See `.planning/research/STACK.md` for full rationale and code patterns.

**Core technologies:**
- `keyring>=25.6.0`: OS keyring abstraction (GNOME Secret Service, macOS Keychain, Windows Credential Manager) — already in project optional deps; promotes to core because `credentials add` must work unconditionally for all install paths
- `argparse` (stdlib, Python 3.12): credentials subcommands and `--version` flag — no new dependency; two-level subparser pattern is idiomatic; verified against existing `main()` structure
- `pypa/gh-action-pypi-publish@release/v1`: PyPI OIDC trusted publishing in GitHub Actions — official PyPA action, keyless auth, `release/v1` rolling branch tracks security fixes automatically

### Expected Features

All v1.3 features are P1. Research confirms this is a complete and correctly scoped feature set with no ambiguity about what ships. See `.planning/research/FEATURES.md` for full prioritization matrix and dependency graph.

**Must have (table stakes):**
- `credentials add/list/remove` CLI subcommands — fundamental CRUD; every credential-managing tool ships this
- Auto-inject SSH credentials via keyring at priority 2 in `resolve_ssh_credentials()` — the core payoff of storing credentials; all 56 SSH tools benefit automatically through the single call site
- `homelab-mcp --version` flag — every CLI tool has this; users verify what's running
- Automated PyPI publish on `git tag v*` — `uvx homelab-mcp` users expect new versions without manual CI steps
- Graceful `NoKeyringError` handling in all code paths — headless homelab servers lack GUI keyring; must not crash or silently fail
- PRMT-02 bug fix in `_build_decommission_result()` — AI following the decommission workflow prompt hits a schema validation error on every invocation (`hostname=` vs `device_id=` mismatch)

**Should have (differentiators):**
- Proxmox credentials storable via `credentials add --type proxmox` — alternative to `.env` file; useful for multi-host setups
- Per-type service namespace (`homelab-mcp-ssh` vs `homelab-mcp-proxmox`) — isolated in OS keyring UI; no cross-type contamination
- Password never visible in `credentials list` output — matches `gh auth status` / `git credential` UX convention

**Defer to v1.x or v2+:**
- `credentials verify <host>` — test SSH connectivity with stored creds
- `credentials list --type proxmox` — separate listing by credential type
- `credentials export --format env` — dump stored creds as `.env` for migration/backup
- Credential import from existing `.env` files

### Architecture Approach

The architecture is additive: one new module (`credential_store.py`), four modified modules (`server.py`, `ssh_tools.py`, `config.py`, `prompt_registry.py`), and one modified CI file (`main.yml`). The new `credential_store.py` is intentionally isolated — it imports only `keyring` (optional, guarded) with no homelab_mcp imports, eliminating circular import risk. All keyring access is centralised there; other modules call `credential_store.get_credential(key)` without knowledge of keyring internals. The CLI extension uses the existing `homelab-mcp` console script entrypoint — `credentials` is a subparser that dispatches and exits before any server startup logic runs. See `.planning/research/ARCHITECTURE.md` for component map and data flow diagrams.

**Major components:**
1. `credential_store.py` (NEW) — keyring get/set/delete; `KEYRING_AVAILABLE` guard at module level; service name constants `homelab-mcp-ssh` / `homelab-mcp-proxmox`; all keyring exceptions caught and handled
2. `server.py main()` (MODIFY) — add `--version` action and `credentials` subparser; local import of `credential_store` inside the credentials branch; `sys.exit(0)` before server starts
3. `ssh_tools.resolve_ssh_credentials()` (MODIFY) — insert keyring lookup as priority 2 (after explicit args, before SQLite DB, before default mcp_admin key)
4. `config.py MCPConfig` (MODIFY) — add keyring fallback for Proxmox password after env var check; env vars always win
5. `prompt_registry.py _build_decommission_result()` (MODIFY) — PRMT-02 fix: replace `hostname=` tool call instruction with `list_devices` → `device_id` lookup step
6. `main.yml publish job` (NEW) — OIDC trusted publishing via `pypa/gh-action-pypi-publish@release/v1`; gated on `v*` tags and `test-and-quality` passing; runs in parallel with existing `release` job

### Critical Pitfalls

Full analysis in `.planning/research/PITFALLS.md`. Top five by severity and probability for v1.3:

1. **Keyring `NoKeyringError` crashes the server on headless Linux** — The primary deployment target (Proxmox host) has no D-Bus session; `keyring.get_password()` raises `NoKeyringError`. Wrap every keyring call in `try/except (keyring.errors.NoKeyringError, RuntimeError, Exception)`. Never call keyring at module import time or during server startup. Log at `DEBUG` level — this is expected behaviour, not an error.

2. **Argparse subparsers break the existing bare `homelab-mcp` invocation** — Adding `add_subparsers()` changes how argparse handles no-arg invocations. Use `parser.set_defaults(func=_run_server)` and `getattr(args, 'func', _run_server)(args)` for dispatch. Add an explicit regression test: `parse_args([])` must route to server startup; `parse_args(['--http'])` must set `args.http = True`.

3. **PyPI OIDC trusted publishing fails with `invalid-publisher`** — Configuration mismatches (workflow filename, environment name, hyphen vs underscore in package name, missing `id-token: write` at job level) cause silent 403 failures. Validate with a TestPyPI dry run before the first production tag push. The PyPI trusted publisher must be registered manually at `pypi.org/manage/project/homelab-mcp/settings/publishing/` before pushing `v1.3.0`.

4. **Version/tag mismatch at publish time** — `pyproject.toml version = "1.2.0"` when pushing `git tag v1.3.0` causes PyPI to reject the upload or publish a permanently mismatched release. Add a CI step asserting the `pyproject.toml` version equals the tag name before the build runs.

5. **Credential leak through exception messages in new logging paths** — `log_filter.py`'s `_SENSITIVE_PATTERNS` are prefix-anchored; bare secret values in exception messages bypass all filters. Every `except` block in new credential-touching code must use `sanitize_error(e)` from `log_filter.py`, never `str(e)`. Require a test that asserts `caplog.text` contains no credential value after a failed SSH connection with auto-injected creds.

---

## Implications for Roadmap

The build order is dictated by one hard dependency: `credential_store.py` must exist before CLI subcommands, SSH auto-inject, or Proxmox config fallback. Everything else is parallelisable once that module is in place. PRMT-02 and CI/CD automation are fully independent of the credential work.

### Phase 1: Credential Store Foundation

**Rationale:** `credential_store.py` is the blocking dependency for three other work items. Building it first with full test coverage (both `KEYRING_AVAILABLE=True` and `KEYRING_AVAILABLE=False` branches) de-risks the entire milestone. The headless fallback pattern established here must be correct before any consuming code is written.
**Delivers:** `credential_store.py` with `get_credential`, `set_credential`, `delete_credential`; `KEYRING_AVAILABLE` guard; `homelab-mcp-ssh` / `homelab-mcp-proxmox` service name constants; `NoKeyringError` / `RuntimeError` / `ImportError` all handled; `keyring>=25.6.0` promoted to core in `pyproject.toml`
**Addresses:** Prerequisite for `credentials` CLI subcommands, SSH auto-inject, and Proxmox config fallback
**Avoids:** Pitfall 1 (keyring crashes on headless); Pitfall 5 (credential leak in exception messages)

### Phase 2: CLI Extension

**Rationale:** With `credential_store.py` available, the `credentials` subparser and `--version` flag can be added to `server.py main()`. This is the primary user-visible surface of the credential feature and must not break the existing bare invocation.
**Delivers:** `homelab-mcp credentials add/list/remove` subcommands; `homelab-mcp --version` flag; `getpass.getpass()` for interactive password prompts; `sys.exit(0)` before server starts in credentials path
**Uses:** `argparse` stdlib subparsers; `credential_store.py`; `importlib.metadata.version()` (already imported in `server.py`)
**Avoids:** Pitfall 2 (bare invocation regression) — regression test for `parse_args([])` is a required quality gate

### Phase 3: Credential Auto-Inject

**Rationale:** Wires the stored credentials into live tool call paths (`resolve_ssh_credentials()` and `MCPConfig`). This phase modifies existing production code and must be TDD-first — priority order tests before implementation. The `sanitize_error()` discipline must be enforced in every new logging path.
**Delivers:** Keyring at priority 2 in `resolve_ssh_credentials()` (after explicit args, before SQLite DB); Proxmox password keyring fallback after env var check in `MCPConfig`; `credential_source` informational field in tool responses when auto-inject fires; env var precedence verified by test
**Avoids:** Pitfall 5 (credential leak in logs); Pitfall 6 (silent override of explicit credentials); stale Proxmox token from env var rotation

### Phase 4: PRMT-02 Bug Fix

**Rationale:** Fully independent of all other work. Pure text change in `_build_decommission_result()` — no schema changes, no new imports. Can be pulled into any earlier phase slot if needed, but placing it here keeps phases clean.
**Delivers:** Decommission workflow prompt generates `list_devices` lookup step before `decommission_device` call; `device_id=<found_id>` replaces `hostname=` in generated tool call instructions; eliminates AI schema validation error on every decommission workflow
**Avoids:** AI generating invalid tool calls on every invocation of the decommission workflow

### Phase 5: CI/CD Release Automation

**Rationale:** Independent of all code changes. Placing it last allows TestPyPI validation to use the fully assembled v1.3 codebase. The one-time PyPI trusted publisher registration must be completed manually before this phase's quality gate.
**Delivers:** `publish` job in `main.yml` using `pypa/gh-action-pypi-publish@release/v1`; OIDC trusted publishing with `id-token: write` at job level; version/tag assertion CI step; `publish` and `release` jobs run in parallel on `v*` tags
**Uses:** `uv build`; `pypa/gh-action-pypi-publish@release/v1`; `pypi` GitHub environment for protection rules
**Avoids:** Pitfall 3 (OIDC `invalid-publisher`); Pitfall 4 (double publish on non-tag push); Pitfall 7 (version/tag mismatch at publish time)

### Phase Ordering Rationale

- Phase 1 must precede Phases 2 and 3 — both consume `credential_store.py` and cannot be built without it
- Phases 2 and 3 can be developed in parallel once Phase 1 is merged
- Phase 4 has zero dependencies and can be pulled into any slot if there is a scheduling reason to do so
- Phase 5 has zero code dependencies but benefits from being last so the TestPyPI dry run uses the complete v1.3 build

### Research Flags

All phases use standard, well-documented patterns. No phase requires `/gsd:research-phase`.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Credential Store):** `keyring` API is stable, documented, and already in the project; optional dep guard is a standard Python pattern; HIGH confidence throughout
- **Phase 2 (CLI Extension):** argparse stdlib, two-level subparsers, `--version` action — all verified against existing `main()` structure; zero new patterns
- **Phase 4 (PRMT-02 Fix):** Root cause confirmed by direct schema + prompt inspection; fix is text-only in a single function

Phases warranting attention during execution (not more research, but implementation care):
- **Phase 3 (Auto-Inject):** TDD-first is mandatory — the 5-priority SSH credential chain is complex, the silent-override pitfall is easy to miss, and `sanitize_error()` discipline must be enforced in every new exception handler
- **Phase 5 (CI/CD):** The PyPI one-time manual setup step is external; TestPyPI dry run is a required quality gate before any production tag is pushed; version/tag alignment must be verified

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | `keyring` 25.7.0 docs verified; `pypa/gh-action-pypi-publish` official action; argparse stdlib; `pyproject.toml` and `server.py` inspected directly; one net-new runtime dep with no uncertainty |
| Features | HIGH | All features verified against codebase; credential priority chain matches existing `resolve_ssh_credentials()` structure confirmed by source inspection; PRMT-02 root cause confirmed by schema + prompt text inspection |
| Architecture | HIGH | All integration points verified by direct source inspection; build order confirmed by dependency analysis; module boundary rationale consistent with existing codebase patterns |
| Pitfalls | HIGH | Headless keyring failure confirmed by official docs and multiple real-world issue reports; argparse subparser behaviour verified against Python 3.12 docs; OIDC mismatch patterns from official PyPI troubleshooting docs |

**Overall confidence:** HIGH

### Gaps to Address

- **Proxmox `config.py` fallback insertion point:** ARCHITECTURE.md notes `config.py` was not deeply inspected in this research session. The env var precedence pattern is standard, but the exact insertion point for the keyring fallback should be verified against the actual constructor before writing tests.
- **TestPyPI trusted publisher setup:** The first end-to-end OIDC publish cannot be validated before the PyPI trusted publisher is manually registered. Document the manual setup step explicitly in the Phase 5 plan; the TestPyPI dry run must be the first action taken in that phase.
- **`keyring` behaviour on WSL2:** Confirmed headless failure from issue reports but not from a WSL2-specific test run. The `except Exception` guard handles this case regardless, so risk is low.

---

## Sources

### Primary (HIGH confidence)
- [keyring 25.7.0 documentation](https://keyring.readthedocs.io/en/latest/) — API methods, `NoKeyringError`, `PYTHON_KEYRING_BACKEND`, backend list by platform
- [keyring changelog](https://keyring.readthedocs.io/en/latest/history.html) — v25.6.0 warning removal confirmed; `NoKeyringError` present since v23.x
- [PyPI Trusted Publishers documentation](https://docs.pypi.org/trusted-publishers/using-a-publisher/) — OIDC flow, required fields, one-time setup procedure
- [PyPI Trusted Publishers: Troubleshooting](https://docs.pypi.org/trusted-publishers/troubleshooting/) — `invalid-publisher` causes enumerated
- [pypa/gh-action-pypi-publish GitHub](https://github.com/pypa/gh-action-pypi-publish) — workflow YAML, `release/v1` recommendation, `id-token: write` requirement, PEP 740 attestations
- [Python Packaging User Guide — publishing with CI/CD](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/) — canonical reference workflow
- [Python stdlib argparse docs (3.12)](https://docs.python.org/3/library/argparse.html) — `add_subparsers`, `dest`, `set_defaults`, `action="version"`
- Project codebase (first-party, direct inspection): `src/homelab_mcp/server.py`, `src/homelab_mcp/ssh_tools.py`, `src/homelab_mcp/config.py`, `src/homelab_mcp/database.py`, `src/homelab_mcp/prompt_registry.py`, `src/homelab_mcp/tool_schemas/infrastructure_tools_schema.py`, `pyproject.toml`, `.github/workflows/main.yml`

### Secondary (MEDIUM confidence)
- [NoKeyringError in headless Linux — jaraco/keyring issue #566](https://github.com/jaraco/keyring/issues/566) — real-world confirmation of headless failure mode
- [NoKeyringError in pypa/hatch — issue #671](https://github.com/pypa/hatch/issues/671) — second real-world confirmation from a different Python project
- [PyPI Trusted Publisher pitfalls — dreamnetworking.nl, 2025](https://dreamnetworking.nl/blog/2025/01/07/pypi-trusted-publisher-management-and-pitfalls/) — hyphen/underscore mismatch, environment name mismatch cases
- [GitHub Actions avoid double runs — Adam Johnson, 2025](https://adamj.eu/tech/2025/05/14/github-actions-avoid-simple-on/) — double-trigger prevention patterns

---
*Research completed: 2026-03-14*
*Ready for roadmap: yes*
