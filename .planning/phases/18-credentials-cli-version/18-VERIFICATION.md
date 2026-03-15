---
phase: 18-credentials-cli-version
verified: 2026-03-14T00:00:00Z
status: passed
score: 7/7 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Run homelab-mcp --version in a terminal"
    expected: "Prints 'homelab-mcp <version-string>' and exits 0"
    why_human: "importlib.metadata.version() requires the package to be installed; cannot confirm version string format in a headless pytest context without installed dist-info"
  - test: "Run homelab-mcp credentials add myhost myuser and enter a password at the prompt"
    expected: "getpass prompt appears, password is not echoed, 'Stored ssh credential for myuser@myhost' is printed"
    why_human: "getpass prompts require a real TTY; tests mock getpass so interactive UX cannot be verified programmatically"
---

# Phase 18: Credentials CLI + --version Verification Report

**Phase Goal:** Provide a CLI interface for managing SSH/Proxmox credentials and add --version flag to the server entry point.
**Verified:** 2026-03-14
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | homelab-mcp --version prints the installed version and exits 0 | VERIFIED | `--version` argparse action added at server.py line 588-592; test_version_flag passes (green) |
| 2 | homelab-mcp (bare) starts the stdio server unchanged | VERIFIED | `set_defaults(func=_run_stdio_wrapper)` at line 637; `getattr(args, "func", _run_stdio_wrapper)(args)` dispatch at line 663; test_bare_invocation_starts_server passes |
| 3 | credentials add prompts for password via getpass and stores credential | VERIFIED | `_cmd_credentials_add` (line 491) calls `getpass.getpass`, then `store_credential` + `register_credential`; test_credentials_add_ssh and test_credentials_add_uses_getpass both green |
| 4 | credentials add --type proxmox stores under proxmox service name | VERIFIED | `_SERVICE_NAMES = {"ssh": "homelab-mcp", "proxmox": "homelab-mcp-proxmox"}` in credential_store.py line 18-21; `store_credential` uses `_SERVICE_NAMES.get(credential_type, _SERVICE_NAME)`; test_store_proxmox_uses_proxmox_service_name and test_credentials_add_proxmox green |
| 5 | credentials list prints hostnames with no passwords visible | VERIFIED | `_cmd_credentials_list` (line 512) prints `username@hostname` from registry entries only, never keyring values; test_credentials_list_ssh passes including assertion that "password" not in output |
| 6 | credentials remove deletes credential and confirms removal | VERIFIED | `_cmd_credentials_remove` (line 524) calls `delete_credential` + `unregister_credential`; test_credentials_remove_ssh green |
| 7 | All Phase 18 credential_store extensions present and tested | VERIFIED | `register_credential`, `unregister_credential`, `list_credentials`, `_REGISTRY_PATH`, `_SERVICE_NAMES` all in credential_store.py; all 15 test_credential_store.py tests green |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/test_credentials_cli.py` | 12 CLI test cases covering CRED-01..06 + CLI-01 | VERIFIED | 264 lines; 12 tests collected and all passing |
| `tests/test_credential_store.py` | Extended with 6 registry + credential_type tests | VERIFIED | 199 lines; 6 new Phase 18 tests plus 9 Phase 17 tests all green (15 total) |
| `src/homelab_mcp/credential_store.py` | _SERVICE_NAMES, _REGISTRY_PATH, register/unregister/list_credentials, credential_type param | VERIFIED | 144 lines; all symbols present and substantive; ruff + mypy clean |
| `src/homelab_mcp/server.py` | _cmd_credentials_add/list/remove, _run_stdio_wrapper, --version flag, subparsers, set_defaults | VERIFIED | All 4 functions present at lines 491-570; subparsers and set_defaults at lines 637-663; --version at lines 588-592 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `parser.set_defaults(func=_run_stdio_wrapper)` | `asyncio.run(_run_stdio())` | `getattr(args, 'func', _run_stdio_wrapper)(args)` | WIRED | Lines 637 and 663 in server.py; test_bare_invocation_starts_server verifies asyncio.run is called |
| `_cmd_credentials_add` | `credential_store.store_credential` | module-level import at server.py line 25-29 | WIRED | `from .credential_store import ... store_credential ...` at module level; monkeypatched via `homelab_mcp.server.store_credential` in tests |
| `_cmd_credentials_list` | `credential_store.list_credentials` | module-level import at server.py line 27 | WIRED | `list_credentials` in module-level import block; called directly in `_cmd_credentials_list` line 515 |
| `store_credential` | `keyring.set_password` | `_SERVICE_NAMES[credential_type]` | WIRED | `service_name = _SERVICE_NAMES.get(credential_type, _SERVICE_NAME)` at credential_store.py line 30; `keyring.set_password(service_name, ...)` at line 35 |
| `register_credential` | `_REGISTRY_PATH` | `_save_registry(entries)` | WIRED | `_save_registry` called at credential_store.py line 128; `_save_registry` writes to `_REGISTRY_PATH` at line 113 |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CRED-01 | 18-01, 18-02, 18-03 | User can store SSH credentials via `credentials add <host> <user>` with getpass | SATISFIED | `_cmd_credentials_add` uses getpass, calls store_credential + register_credential; test_credentials_add_ssh green |
| CRED-02 | 18-01, 18-02, 18-03 | User can list SSH credential hostnames via `credentials list` | SATISFIED | `_cmd_credentials_list` prints `username@hostname` from list_credentials(); test_credentials_list_ssh green |
| CRED-03 | 18-01, 18-02, 18-03 | User can remove SSH credentials via `credentials remove <host>` | SATISFIED | `_cmd_credentials_remove` calls delete_credential + unregister_credential; test_credentials_remove_ssh green |
| CRED-04 | 18-01, 18-02, 18-03 | User can store Proxmox credentials via `credentials add --type proxmox <host> <user>` | SATISFIED | `--type` argparse arg with `dest="credential_type"` and `choices=["ssh","proxmox"]`; `_SERVICE_NAMES["proxmox"]="homelab-mcp-proxmox"`; test_credentials_add_proxmox green |
| CRED-05 | 18-01, 18-02, 18-03 | User can list Proxmox hosts via `credentials list --type proxmox` | SATISFIED | list_credentials filters by credential_type; test_credentials_list_proxmox green |
| CRED-06 | 18-01, 18-02, 18-03 | User can remove Proxmox credentials via `credentials remove --type proxmox <host>` | SATISFIED | delete_credential + unregister_credential called with credential_type; test_credentials_remove_proxmox green |
| CLI-01 | 18-01, 18-03 | `homelab-mcp --version` prints installed package version and exits 0; bare invocation starts server | SATISFIED | argparse `action="version"` with `_get_version()`; set_defaults + getattr dispatch preserves bare invocation; both CLI-01 tests green |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | - | - | - | - |

No TODO, FIXME, placeholder, empty return, or stub patterns found in any Phase 18 modified files. Ruff reports clean on all four files.

### Human Verification Required

#### 1. Interactive --version behavior

**Test:** Run `homelab-mcp --version` from a terminal where the package is installed.
**Expected:** Output contains `homelab-mcp <semver-string>` and process exits 0 immediately.
**Why human:** `importlib.metadata.version("homelab-mcp")` returns `"unknown"` in test environments where the package dist-info is absent; automated tests patch `sys.argv` and confirm SystemExit(0) but cannot assert the actual version string format without an installed package.

#### 2. Interactive getpass prompt behavior

**Test:** Run `homelab-mcp credentials add testhost testuser` in a real terminal.
**Expected:** A `Password:` prompt appears, typed characters are not echoed, and after pressing Enter `Stored ssh credential for testuser@testhost` is printed.
**Why human:** getpass falls back to plain input when stdin is not a TTY; tests mock getpass.getpass entirely, so the TTY echo-suppression behavior cannot be confirmed programmatically.

### Gaps Summary

No gaps. All automated checks pass:

- 630 unit tests green (0 failures, 7 skipped — pre-existing, 29 deselected as integration)
- All 12 test_credentials_cli.py tests green
- All 15 test_credential_store.py tests green (9 Phase 17 + 6 Phase 18)
- ruff check: all checks passed
- mypy: no issues found in 2 source files
- All 4 commits documented in SUMMARYs confirmed present in git log (e358eed, a3bfebd, b9b4230, 999678d)
- No anti-patterns found in any Phase 18 modified file

---

_Verified: 2026-03-14_
_Verifier: Claude (gsd-verifier)_
