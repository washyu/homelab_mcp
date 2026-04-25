---
phase: 34-cluster-scoped-proxmox-credentials
plan: "03"
subsystem: proxmox-client-wiring
tags: [proxmox, credentials, async, resolver, wiring, INJECT-03-deleted]
dependency_graph:
  requires:
    - proxmox_api.resolve_proxmox_credentials (Plan 02)
    - proxmox_api._HOST_CLUSTER_CACHE (Plan 02)
    - credential_store.scope/cluster_name fields (Plan 01)
  provides:
    - proxmox_api.get_proxmox_client (now async def)
    - all 9 internal proxmox_api.py call sites await get_proxmox_client
  affects:
    - src/homelab_mcp/proxmox_api.py
    - tests/test_proxmox_api.py
tech_stack:
  added: []
  patterns:
    - async def factory function delegating to resolver on host-only path (D-10)
    - explicit auth (api_token or username+password) bypasses resolver (SC-5)
    - ValueError naming env var as migration pointer on no-host path (D-12)
    - AsyncMock new_callable for patching async factory in consumer tests
key_files:
  created: []
  modified:
    - src/homelab_mcp/proxmox_api.py
    - tests/test_proxmox_api.py
decisions:
  - "INJECT-03 shortcut block deleted entirely (D-12) — no placeholder comment left; resolver call replaces its intent"
  - "Resolver patch target in new TestGetProxmoxClientAsync is src.homelab_mcp.proxmox_api.resolve_proxmox_credentials (matches test file import style)"
  - "All @patch('src.homelab_mcp.proxmox_api.get_proxmox_client') decorators in consumer tests updated to new_callable=AsyncMock — MagicMock cannot be awaited"
  - "test_client_missing_credentials updated: now patches resolver to raise CredentialNotFoundError instead of expecting ValueError('Must provide...'); behavior change is correct since host+no-auth now routes to resolver"
  - "test_get_proxmox_client_keyring_fallback (INJECT-03 test) deleted — replaced with a comment per D-16a (no AST meta-test for shortcut removal)"
  - "CredentialNotFoundError imported via src.homelab_mcp.ssh_tools in test_client_missing_credentials to avoid home-dir RuntimeError from lazy import at module level in headless env"
metrics:
  duration: "~12 minutes"
  completed: "2026-04-23"
  tasks_completed: 1
  files_modified: 2
requirements: [CRED-08]
---

# Phase 34 Plan 03: Async get_proxmox_client Wiring Summary

Wire the Plan 02 resolver (`resolve_proxmox_credentials`) into `get_proxmox_client`, delete the INJECT-03 single-entry shortcut (D-12), convert `get_proxmox_client` to `async def`, and propagate `await` to all 9 internal callers in `proxmox_api.py`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 RED | Failing tests for async get_proxmox_client wiring | fd218e4 | tests/test_proxmox_api.py |
| 1 GREEN | async get_proxmox_client + INJECT-03 deletion + 9 await call sites | 708e5fb | src/homelab_mcp/proxmox_api.py, tests/test_proxmox_api.py |

## Implementation Notes

### get_proxmox_client line count diff (GREEN commit, proxmox_api.py)

- **Deleted:** 29 lines (the 19-line INJECT-03 shortcut block + sync `def` keyword + minor cleanup)
- **Added:** 23 lines (resolver call block with `async def`, debug log, comments)
- **Net:** -6 lines (function is shorter after the shortcut removal)

### INJECT-03 shortcut block deleted

The entire `# Keyring fallback (INJECT-03)` block (lines 366-384 in the pre-change file) is gone. The replacement is:

```python
# D-10: resolver fires only when host is known AND no explicit auth was provided.
if host and not api_token and not (username and password):
    resolved_token, scope, cluster_name = await resolve_proxmox_credentials(host, session=session)
    api_token = resolved_token
    logger.debug("Proxmox credential resolved for host=%s via source=%s cluster=%s", ...)
```

### 9 internal call sites awaited

All 9 `client = get_proxmox_client(host=host, session=session)` occurrences in `proxmox_api.py` were updated to `client = await get_proxmox_client(host=host, session=session)` via a single `replace_all` edit. Lines: 415, 454, 493, 537, 580, 659, 745, 817, 869.

### Existing test retrofitting (async/await)

The following existing tests in `tests/test_proxmox_api.py` were updated to `async def` + `await`:

| Test name | Change |
|-----------|--------|
| `TestGetProxmoxClient.test_client_from_env_vars` | Added `@pytest.mark.asyncio`, `async def`, `await get_proxmox_client()` |
| `TestGetProxmoxClient.test_client_missing_credentials` | Added `@pytest.mark.asyncio`, `async def`, `await get_proxmox_client()`, patched resolver to raise `CredentialNotFoundError` |
| `TestGetProxmoxClient.test_client_missing_host` | Added `@pytest.mark.asyncio`, `async def`, `await get_proxmox_client()` |
| `TestGetProxmoxClient.test_client_with_api_token_from_env` | Added `@pytest.mark.asyncio`, `async def`, `await get_proxmox_client()` |
| `TestGetProxmoxClient.test_client_with_explicit_params_override_env` | Added `@pytest.mark.asyncio`, `async def`, `await get_proxmox_client()` |
| `TestProxmoxSharedSession.test_get_proxmox_client_with_session` | Added `@pytest.mark.asyncio`, `async def`, `await get_proxmox_client()` |
| `TestProxmoxSSLVerification.test_ssl_verify_false_override_via_env` | Added `@pytest.mark.asyncio`, `async def`, `await get_proxmox_client()` |
| `TestProxmoxSSLVerification.test_get_proxmox_client_default_verify_ssl_true` | Added `@pytest.mark.asyncio`, `async def`, `await get_proxmox_client()` |

### Consumer function patches updated

All `@patch("src.homelab_mcp.proxmox_api.get_proxmox_client")` decorators in consumer-function test classes (`TestListProxmoxResources`, `TestGetProxmoxNodeStatus`, `TestGetProxmoxVMStatus`, `TestGetProxmoxVMConfig`, `TestManageProxmoxVM`, `TestCreateProxmoxLXC`, `TestCreateProxmoxVM`, `TestCloneProxmoxVM`, `TestDeleteProxmoxVM`, and handler session tests) were changed to `new_callable=AsyncMock`. The `mock_get_client.return_value = mock_client` pattern continues to work unchanged because `AsyncMock` returns `return_value` when awaited.

### list_credentials / get_credential import status

Both imports remain in `proxmox_api.py` at line 14 — they are used by `resolve_proxmox_credentials` (Plan 02 function). No import changes were needed.

### registry_entries[0] source tree scan

```
grep -r "registry_entries\[0\]" src/
# → (no output — zero matches)
```

Confirmed absent from entire source tree post-change.

## Deviations from Plan

### Auto-fixed test issues (Rule 1)

**1. [Rule 1 - Bug] Patch path for new TestGetProxmoxClientAsync tests**
- **Found during:** Initial RED test run (all 4 tests used `"homelab_mcp.proxmox_api..."` path)
- **Issue:** `test_get_proxmox_client_async_delegates_to_resolver_when_host_only` patched `homelab_mcp.proxmox_api.resolve_proxmox_credentials` but the test file imports from `src.homelab_mcp.*` — the patch wasn't intercepting the call
- **Fix:** Changed all 4 new-test patch targets to `"src.homelab_mcp.proxmox_api.resolve_proxmox_credentials"` to match the module path used at import time
- **Files modified:** `tests/test_proxmox_api.py`

**2. [Rule 1 - Bug] test_client_missing_credentials inline import failure**
- **Found during:** GREEN test run
- **Issue:** `from homelab_mcp.ssh_tools import CredentialNotFoundError` inside test body raised `RuntimeError: Could not determine home directory` in headless env (credential_store.py module-level path expansion)
- **Fix:** Changed to `from src.homelab_mcp.ssh_tools import CredentialNotFoundError` (matching test file import convention)
- **Files modified:** `tests/test_proxmox_api.py`

**3. [Rule 1 - Behavior change] test_client_missing_credentials behavior**
- **Found during:** Plan analysis
- **Issue:** Old test expected `ValueError("Must provide either PROXMOX_API_TOKEN...")` but new code routes host+no-auth through the resolver, which raises `CredentialNotFoundError` on miss
- **Fix:** Updated test to patch the resolver with `side_effect=CredentialNotFoundError(...)` and assert `pytest.raises(CredentialNotFoundError)`
- **Files modified:** `tests/test_proxmox_api.py`

## Known Stubs

None. `get_proxmox_client` is fully wired — the resolver call is live, the INJECT-03 shortcut is gone, and all call sites propagate `await`.

## Threat Flags

None. This plan makes no new network endpoints visible. The resolver call inside `get_proxmox_client` uses the same Proxmox hosts and credentials that were previously accessible via the INJECT-03 shortcut; the only behavioral change is the resolution path (structured resolver vs. first-entry assumption).

## Self-Check

### Files exist
- `src/homelab_mcp/proxmox_api.py` — FOUND (modified)
- `tests/test_proxmox_api.py` — FOUND (modified)

### Commits exist
- `fd218e4` — RED: failing tests
- `708e5fb` — GREEN: implementation + test retrofitting

### Acceptance criteria verification

| Criterion | Result |
|-----------|--------|
| `grep -n "async def get_proxmox_client"` → line 332 | PASS |
| `grep -c "def get_proxmox_client"` → 1 | PASS |
| `grep -c "registry_entries\[0\]" src/homelab_mcp/proxmox_api.py` → 0 | PASS |
| `grep -c "INJECT-03" src/homelab_mcp/proxmox_api.py` → 0 | PASS |
| `grep -c "await get_proxmox_client(" src/homelab_mcp/proxmox_api.py` → 9 | PASS |
| `grep -n "await resolve_proxmox_credentials(host, session=session)"` → line 371 | PASS |
| `grep -n "PROXMOX_HOST env var"` → lines 345, 382 (docstring + error) | PASS |
| `uv run pytest tests/test_proxmox_api.py tests/test_proxmox_resolver.py` → 90 passed | PASS |
| `uv run ruff check src/homelab_mcp/proxmox_api.py tests/test_proxmox_api.py` → 0 | PASS |
| `uv run mypy src/homelab_mcp/proxmox_api.py` → 0 issues | PASS |
| `uv run pytest tests/ -m "not integration" -q` → 709 passed, 1 pre-existing failure | PASS |
| Sanity import: `inspect.iscoroutinefunction(get_proxmox_client)` → True | PASS |
| `grep -r "registry_entries\[0\]" src/` → (no output) | PASS |

## Self-Check: PASSED
