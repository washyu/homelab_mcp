---
phase: 34-cluster-scoped-proxmox-credentials
plan: "02"
subsystem: proxmox-resolver
tags: [proxmox, credentials, resolver, cluster-scope, async]
dependency_graph:
  requires:
    - credential_store.list_credentials(scope, cluster_name)
    - credential_store.get_credential(scope, cluster_name)
    - CredentialNotFoundError (ssh_tools.py line 24)
    - ProxmoxAPIClient.get (proxmox_api.py)
  provides:
    - proxmox_api.resolve_proxmox_credentials(host, session)
    - proxmox_api._HOST_CLUSTER_CACHE
    - proxmox_api.CredentialNotFoundError (re-export)
  affects:
    - src/homelab_mcp/proxmox_api.py
    - tests/test_proxmox_resolver.py
tech_stack:
  added: []
  patterns:
    - two-tier per-node short-circuit then cluster walk (mirrors ssh_tools.resolve_ssh_credentials)
    - module-level plain dict cache for host→cluster_name (D-05a)
    - throwaway ProxmoxAPIClient per candidate cluster entry for /cluster/status probe
    - top-level CredentialNotFoundError import from ssh_tools (no circular import)
    - DEBUG log per tier attempt + terminal source=node|cluster record (D-11/SC-2)
    - desync WARNING with credentials add --type proxmox --scope cluster: pointer
key_files:
  created:
    - tests/test_proxmox_resolver.py
  modified:
    - src/homelab_mcp/proxmox_api.py
decisions:
  - "Top-level import of CredentialNotFoundError from .ssh_tools used (no circular import — ssh_tools does not import proxmox_api)"
  - "ProxmoxAPIClient.get() strips the 'data' wrapper (returns list directly) — defensive rows=status if isinstance(status,list) else [] branch is sufficient; dict fallback not needed"
  - "Throwaway ProxmoxAPIClient per candidate cluster entry for /cluster/status probe (reuses all auth header/session logic, zero new HTTP plumbing)"
  - "Plain dict for _HOST_CLUSTER_CACHE (Claude's Discretion per CONTEXT.md); functools.lru_cache not used to allow cache.clear() in tests"
  - "resolve_proxmox_credentials placed immediately above get_proxmox_client at line 194 (locality with consumer)"
metrics:
  duration: "~4 minutes"
  completed: "2026-04-23"
  tasks_completed: 1
  files_modified: 2
requirements: [CRED-08]
---

# Phase 34 Plan 02: Cluster-Aware Credential Resolver (Pure Addition)

Add `async def resolve_proxmox_credentials(host, session=None)` to `proxmox_api.py` as a standalone function alongside `get_proxmox_client`. Pure addition — `get_proxmox_client` is not modified. The resolver implements two-tier per-node short-circuit then cluster walk per D-09/D-10.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 RED | Failing tests for resolve_proxmox_credentials | 674843e | tests/test_proxmox_resolver.py |
| 1 GREEN | resolve_proxmox_credentials + _HOST_CLUSTER_CACHE | f16f113 | src/homelab_mcp/proxmox_api.py |

## Implementation Notes

### Insertion Location

`resolve_proxmox_credentials` was inserted at **line 194** of `src/homelab_mcp/proxmox_api.py`, immediately above `def get_proxmox_client(`. `_HOST_CLUSTER_CACHE` is at **line 21** (module scope, after imports).

### Import Strategy: Top-Level (not lazy)

Top-level import was used:
```python
from .ssh_tools import CredentialNotFoundError  # noqa: F401 — re-exported for consumers
```

Reason: `ssh_tools.py` has no import of `proxmox_api.py` (confirmed by grep), so there is no circular import risk. The `# noqa: F401` suppresses the "imported but unused" lint warning because the re-export pattern makes it intentionally importable by downstream consumers even though `proxmox_api.py` itself doesn't raise it directly (the raise sites use the local name after the import).

### ProxmoxAPIClient.get() Return Shape

`ProxmoxAPIClient.get()` strips the `"data"` wrapper automatically (line 175: `return result["data"]`). When aioresponses returns `{"data": [...]}`, the client's `.get("/cluster/status")` returns the list directly. Therefore the defensive unwrap in the resolver is:

```python
rows = status if isinstance(status, list) else []
```

The `dict` fallback branch (`status.get("data", [])`) was not needed and was omitted for clarity. Tests confirmed the `isinstance(status, list)` branch is the live path.

### Cache Implementation

Plain `dict[str, str]` chosen over `functools.lru_cache` because:
- Tests need `_HOST_CLUSTER_CACHE.clear()` in the autouse fixture — `lru_cache.cache_clear()` would work but the plan says "plain dict is fine (Claude's Discretion)"
- The module-level name is importable for test cleanup: `from homelab_mcp.proxmox_api import _HOST_CLUSTER_CACHE`

## Test Names Added

All 7 in `tests/test_proxmox_resolver.py`:

| # | Name | Mocks | Decision |
|---|------|-------|----------|
| 1 | `test_resolver_cluster_only_match` | list_credentials, get_credential, aioresponses | D-13 |
| 2 | `test_resolver_per_node_overrides_cluster_no_probe` | list_credentials, get_credential, aioresponses (zero calls asserted) | D-14 |
| 3 | `test_resolver_standalone_node_raises_with_actionable_message` | list_credentials, get_credential, aioresponses | D-15 |
| 4 | `test_resolver_multi_cluster_first_match_wins` | list_credentials, get_credential (side_effect), aioresponses (401 then 200), caplog | D-05b |
| 5 | `test_resolver_cache_hit_skips_probe` | list_credentials, get_credential, aioresponses (one mock, two calls) | D-05a |
| 6 | `test_resolver_debug_log_tier_trace` | list_credentials, get_credential, aioresponses, caplog | D-11/SC-2 |
| 7 | `test_resolver_desync_warning_on_missing_keyring_secret` | list_credentials, get_credential (returns None), caplog | D-07 |

All tests use `@pytest.mark.asyncio` per CLAUDE.md. All tests have an autouse `_clear_cache` fixture that calls `_HOST_CLUSTER_CACHE.clear()` before and after each test.

## Deviations from Plan

None — plan executed exactly as written. The ruff formatter reformatted minor whitespace in the implementation (blank line after list comprehension) on both commits, which is expected pre-commit hook behavior.

## Known Stubs

None. The resolver is a fully functional standalone function. It is not yet wired into `get_proxmox_client` — that is Plan 03's job and is intentional (not a stub).

## Threat Flags

None. The resolver reads from the credential store and makes outbound HTTPS calls to Proxmox hosts already known to the user. No new network endpoints are opened; no new auth paths are introduced at the MCP boundary (D-17 explicitly excludes new MCP tool surface for Phase 34).

## Self-Check

### Files exist
- `src/homelab_mcp/proxmox_api.py` — FOUND (modified)
- `tests/test_proxmox_resolver.py` — FOUND (created)

### Commits exist
- 674843e — RED: failing tests
- f16f113 — GREEN: implementation

### Acceptance criteria
- `grep -n "async def resolve_proxmox_credentials"` → line 194: FOUND
- `grep -n "_HOST_CLUSTER_CACHE: dict"` → line 21: FOUND
- `grep -c "tier=node"` → 2 (need ≥2): PASS
- `grep -c "tier=cluster"` → 3 (need ≥2): PASS
- `grep -c "source=node\|source=cluster"` → 3 (need ≥3): PASS
- `grep -n "credentials add --type proxmox"` → 4 lines (need ≥2): PASS
- `grep -c "registry_entries\[0\]"` → 1 (INJECT-03 shortcut still present): PASS
- All 7 new tests pass: PASS
- `uv run ruff check` → exit 0: PASS
- `uv run mypy src/homelab_mcp/proxmox_api.py` → exit 0: PASS
- `uv run pytest tests/test_proxmox_api.py` → 79 passed, 1 pre-existing failure: PASS
- `grep -c "await resolve_proxmox_credentials"` → 0 (not wired yet): PASS

## Self-Check: PASSED
