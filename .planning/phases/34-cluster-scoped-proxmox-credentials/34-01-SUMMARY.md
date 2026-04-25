---
phase: 34-cluster-scoped-proxmox-credentials
plan: "01"
subsystem: credential-store
tags: [credentials, keyring, proxmox, cluster-scope, registry]
dependency_graph:
  requires: []
  provides:
    - credential_store.register_credential(scope, cluster_name)
    - credential_store.store_credential(scope, cluster_name)
    - credential_store.get_credential(scope, cluster_name)
    - credential_store.delete_credential(scope, cluster_name)
    - credential_store._keyring_key()
  affects:
    - src/homelab_mcp/credential_store.py
tech_stack:
  added: []
  patterns:
    - keyword-only scope/cluster_name kwargs following Phase 33 auth_type precedent
    - _keyring_key() centralises key-form logic for cluster/node branching
    - .get("scope","node") / .get("cluster_name","") backward-compat defaults on registry reads
key_files:
  created: []
  modified:
    - src/homelab_mcp/credential_store.py
    - tests/test_credential_store.py
decisions:
  - "scope/cluster_name added as keyword-only params (after *) to preserve positional call sites unchanged"
  - "Cluster upsert dedup uses (cluster_name, username, credential_type) per D-08a — hostname not compared"
  - "_keyring_key() is a plain module-level def (not a method) inserted just before store_credential"
  - "identity variable used in fallback log messages so cluster calls log cluster:name, not empty string"
  - "test_list_filters_by_type updated to include new scope/cluster_name fields in expected dict (existing test broke on exact equality after register_credential started emitting them)"
  - "2 pre-existing test failures (test_database.py::test_ssh_credentials_table_dropped_postgres, test_proxmox_api.py::TestGetProxmoxClient::test_client_missing_host) confirmed pre-exist on baseline; out of scope for Plan 01"
metrics:
  duration: "~30 minutes"
  completed: "2026-04-23"
  tasks_completed: 2
  files_modified: 2
requirements: [CRED-08]
---

# Phase 34 Plan 01: Credential Store Foundation — scope/cluster_name Extension

Extend `credential_store.py` so registry entries can carry `scope` ("node"|"cluster") and `cluster_name` fields, and so the keyring helpers use the `{username}@cluster:{cluster_name}` key form for cluster-scoped Proxmox credentials. Legacy registry rows remain loadable via `.get()` defaults. No downstream callers changed.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 RED | Failing tests for register_credential scope/cluster_name | 1b0c291 | tests/test_credential_store.py |
| 1 GREEN | register_credential + list_credentials scope/cluster_name | b12e483 | src/homelab_mcp/credential_store.py, tests/test_credential_store.py |
| 2 RED | Failing tests for store/get/delete cluster key form | 8fad307 | tests/test_credential_store.py |
| 2 GREEN | _keyring_key + scope/cluster_name on keyring helpers | fc5dcae | src/homelab_mcp/credential_store.py |

## Signatures Added

### register_credential (extended)

```python
def register_credential(
    hostname: str,
    username: str,
    credential_type: str = "ssh",
    auth_type: str = "password",
    *,
    scope: str = "node",
    cluster_name: str = "",
) -> None: ...
```

Validation: `scope not in ("node","cluster")` → `ValueError`; `scope=="cluster" and not cluster_name` → `ValueError`.

Dedup: cluster entries use `(cluster_name, username, credential_type)`; node entries use `(hostname, username, credential_type)`.

Registry entry shape emitted (all new entries):
```json
{
  "hostname": "...",
  "username": "...",
  "credential_type": "...",
  "auth_type": "...",
  "scope": "node|cluster",
  "cluster_name": ""
}
```

### store_credential / get_credential / delete_credential (extended)

```python
def store_credential(
    hostname: str, username: str, password: str,
    credential_type: str = "ssh",
    *, scope: str = "node", cluster_name: str = "",
) -> bool: ...

def get_credential(
    hostname: str, username: str,
    credential_type: str = "ssh",
    *, scope: str = "node", cluster_name: str = "",
) -> str | None: ...

def delete_credential(
    hostname: str, username: str,
    credential_type: str = "ssh",
    *, scope: str = "node", cluster_name: str = "",
) -> bool: ...
```

Same validation as `register_credential` in each function body.

### _keyring_key helper

Location: `src/homelab_mcp/credential_store.py` line 25 (module-level, before `store_credential`).

```python
def _keyring_key(username: str, hostname: str, scope: str, cluster_name: str) -> str:
    """Return the keyring key. Cluster scope uses '@cluster:' form (D-03)."""
    if scope == "cluster":
        return f"{username}@cluster:{cluster_name}"
    return f"{username}@{hostname}"
```

Called in all three helpers: `_keyring_key(username, hostname, scope, cluster_name)` — exactly 3 call sites.

## Test Names Added

Task 1 (register_credential + list_credentials):
- `test_register_credential_cluster_scope`
- `test_register_credential_cluster_requires_cluster_name`
- `test_register_credential_invalid_scope`
- `test_register_credential_cluster_upsert_ignores_hostname`
- `test_register_credential_node_scope_legacy_dedup_unchanged`
- `test_list_credentials_backward_readable_scope_defaults`

Task 2 (store/get/delete keyring key form):
- `test_store_credential_cluster_scope_key_form`
- `test_get_credential_cluster_scope_key_form`
- `test_delete_credential_cluster_scope_key_form`
- `test_credential_helpers_legacy_key_form_unchanged`
- `test_credential_helpers_cluster_requires_cluster_name`
- `test_store_credential_cluster_scope_headless_fallback`

Total new tests: 12. Total tests in file after plan: 27 (all passing).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_register_and_list exact-equality assertion broke after Task 1**
- **Found during:** Task 1 GREEN verification
- **Issue:** `test_register_and_list` used exact dict equality `== [{"hostname":..., "auth_type":"password"}]`; after `register_credential` started emitting `scope`/`cluster_name`, the assertion failed.
- **Fix:** Updated expected dict to include `"scope": "node", "cluster_name": ""`.
- **Files modified:** `tests/test_credential_store.py`
- **Commit:** b12e483

**2. [Rule 1 - Bug] test_list_filters_by_type exact-equality dicts similarly broke**
- **Found during:** Task 1 test writing (pre-emptive, caught before running)
- **Issue:** Same exact-equality issue; the test was already updated during the RED phase write to include the new fields.
- **Fix:** Both `ssh_entries` and `proxmox_entries` expected dicts include `"scope": "node", "cluster_name": ""`.
- **Files modified:** `tests/test_credential_store.py`
- **Commit:** 1b0c291

### Pre-existing Failures (Out of Scope)

Two pre-existing failures confirmed present on baseline before Plan 01 changes began:
- `tests/test_database.py::test_ssh_credentials_table_dropped_postgres`
- `tests/test_proxmox_api.py::TestGetProxmoxClient::test_client_missing_host`

Neither is related to `credential_store.py`. Logged to deferred-items per scope-boundary rule.

## Known Stubs

None. All implemented functionality is fully wired — no placeholder values or TODO stubs.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced. `credential_store.py` is a local-only utility with no network surface.

## Self-Check

### Created files exist
- `src/homelab_mcp/credential_store.py` — FOUND (modified)
- `tests/test_credential_store.py` — FOUND (modified)

### Commits exist
- 1b0c291 — FOUND
- b12e483 — FOUND
- 8fad307 — FOUND
- fc5dcae — FOUND

### Tests pass
- `uv run pytest tests/test_credential_store.py --no-header -q` → 27 passed

### Quality gates
- `uv run ruff check src/homelab_mcp/credential_store.py tests/test_credential_store.py` → passed
- `uv run mypy src/homelab_mcp/credential_store.py` → no issues found

## Self-Check: PASSED
