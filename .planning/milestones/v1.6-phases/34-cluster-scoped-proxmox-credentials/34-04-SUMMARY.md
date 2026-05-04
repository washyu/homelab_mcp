---
phase: 34-cluster-scoped-proxmox-credentials
plan: "04"
subsystem: cli-surface
tags: [credentials, cli, proxmox, cluster-scope, argparse, mcp-handler]
dependency_graph:
  requires:
    - credential_store.store_credential(scope, cluster_name)
    - credential_store.register_credential(scope, cluster_name)
    - credential_store.delete_credential(scope, cluster_name)
    - credential_store.list_credentials() returning scope/cluster_name fields
  provides:
    - server._parse_scope_arg(scope_arg) -> tuple[str, str]
    - server._cmd_credentials_add cluster branch (D-06)
    - server._cmd_credentials_list grouped output (D-08)
    - server._cmd_credentials_remove cluster branch (D-07)
    - credential_store.unregister_cluster_credential(cluster_name, credential_type)
    - credential_handlers.handle_list_keyring_credentials cluster display (D-17a)
  affects:
    - src/homelab_mcp/server.py
    - src/homelab_mcp/credential_store.py
    - src/homelab_mcp/tool_handlers/credential_handlers.py
tech_stack:
  added: []
  patterns:
    - nargs="?" positional + post-parse validation for conditional-positional argparse shape
    - _parse_scope_arg() helper centralises cluster:<name> string parsing
    - scope/cluster_name kwargs thread from CLI args to credential_store helpers
    - .get("scope", "node") backward-compat default on list entries
    - Cluster removal via unregister_cluster_credential (cluster-keyed, not hostname-keyed)
key_files:
  created:
    - tests/test_credential_handlers.py
  modified:
    - src/homelab_mcp/server.py
    - src/homelab_mcp/credential_store.py
    - src/homelab_mcp/tool_handlers/credential_handlers.py
    - tests/test_credentials_cli.py
decisions:
  - "post-parse validation chosen over subparsers for conditional-positional: matches --key-path precedent; one pair of subparsers kept, hostname made nargs='?' on add and remove"
  - "_parse_scope_arg placed as module-level private def above _cmd_credentials_add; raises ValueError for caller to translate to stderr + exit(1)"
  - "unregister_cluster_credential added to credential_store.py (not inline in server.py) to keep registry logic encapsulated in the store module"
  - "Existing per-node paths in all three handlers byte-for-byte equivalent to pre-Plan-04 behavior (SC-5)"
  - "tools.py / tool_schemas/ not touched — D-17 schema-unchanged proof: git diff 42151c5..HEAD shows empty for both files"
  - "test_credential_handlers.py created fresh (did not exist before Plan 04)"
  - "Pre-existing integration test ruff errors in tests/integration/ out of scope per scope-boundary rule (confirmed pre-exist on baseline)"
metrics:
  duration: "~30 minutes"
  completed: "2026-04-23"
  tasks_completed: 2
  files_modified: 4
requirements: [CRED-08]
---

# Phase 34 Plan 04: CLI Surface for Cluster-Scoped Proxmox Credentials

Add the user-visible CLI surface (`credentials add/remove/list --scope cluster:<name>`) and the one-line MCP handler display tweak so cluster entries render as `cluster:<name>` instead of blank hostname. Satisfies SC-1 (add command shape), SC-4 (list output distinguishes scopes), and SC-5 (per-node CLI unchanged). D-17 schema-non-change confirmed.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 RED | Failing tests for cluster CLI commands | f89125a | tests/test_credentials_cli.py |
| 1 GREEN | _parse_scope_arg + cluster branches in add/remove/list + argparse + epilog | 1d1176f | src/homelab_mcp/server.py, src/homelab_mcp/credential_store.py |
| 2 RED | Failing test for cluster display in handle_list_keyring_credentials | 628c1ae | tests/test_credential_handlers.py |
| 2 GREEN | D-17a one-line conditional in handle_list_keyring_credentials | 8ddf087 | src/homelab_mcp/tool_handlers/credential_handlers.py |

## Signatures Added

### _parse_scope_arg (new, server.py)

```python
def _parse_scope_arg(scope_arg: str | None) -> tuple[str, str]:
    """Return (scope, cluster_name). scope_arg of None or empty -> ("node", "").

    scope_arg of "cluster:<name>" -> ("cluster", "<name>"). "<name>" must be non-empty.
    Any other value raises ValueError for the caller to translate into stderr + exit.
    """
```

### unregister_cluster_credential (new, credential_store.py)

```python
def unregister_cluster_credential(cluster_name: str, credential_type: str = "proxmox") -> None:
    """Remove the cluster-scoped registry entry for (cluster_name, credential_type).

    No-op when no matching row exists.
    """
```

## Argparse Help Text (verbatim from `python -m homelab_mcp credentials add --help`)

```
usage: __main__.py credentials add [-h] [--type {ssh,proxmox}]
                                   [--key-path PATH] [--scope SCOPE]
                                   [hostname] username

Store a credential in the OS keyring. This is upsert behavior: re-running
`add` for the same (hostname, username, type) replaces the existing secret and
its auth_type. There is no separate `update` subcommand — `add` is it.

positional arguments:
  hostname              Target host DNS name (required for per-node
                        credentials; must be omitted when --scope
                        cluster:<name> is used)
  username              Username on the target host (proxmox: the Proxmox
                        token ID in `user@realm!tokenname` form)

options:
  -h, --help            show this help message and exit
  --type {ssh,proxmox}
  --key-path PATH       Path to SSH private key file for key-based auth. When
                        given, skips the password prompt and stores the path
                        as the credential instead (D-09). The key file itself
                        is not copied — only its filesystem path.
  --scope SCOPE         Credential scope. Omit for per-node (default). Use
                        --scope cluster:<cluster_name> to store a Proxmox
                        cluster-wide token (requires --type proxmox). When
                        --scope cluster:<name> is used, the positional
                        <hostname> is not allowed.
```

## New Test Names

### tests/test_credentials_cli.py (9 new tests added)

1. `test_credentials_add_cluster_scope` — D-06 add with cluster kwargs verification
2. `test_credentials_add_proxmox_per_node_unchanged` — SC-5 per-node back-compat
3. `test_credentials_add_rejects_hostname_with_cluster_scope` — D-06 rejection
4. `test_credentials_add_rejects_empty_cluster_name` — D-06 empty name rejection
5. `test_credentials_add_rejects_cluster_scope_with_ssh_type` — D-06 type rejection
6. `test_credentials_remove_cluster_scope` — D-07 remove with cluster kwargs
7. `test_credentials_remove_per_node_unchanged` — SC-5 per-node remove back-compat
8. `test_credentials_list_groups_per_node_and_cluster_sections` — D-08 grouped output
9. `test_credentials_list_single_section_when_only_one_scope_has_entries` — D-08 single-section

### tests/test_credential_handlers.py (4 new tests, file created fresh)

1. `test_handle_list_keyring_credentials_per_node_entry_renders_hostname`
2. `test_handle_list_keyring_credentials_cluster_entry_renders_cluster_form`
3. `test_handle_list_keyring_credentials_legacy_entry_uses_node_default`
4. `test_handle_list_keyring_credentials_payload_shape_unchanged`

**tests/test_credential_handlers.py existed before Plan 04:** NO — created fresh in this plan.

Total new tests: 13

## D-17 Schema-Unchanged Proof

`git diff 42151c5..HEAD -- src/homelab_mcp/tools.py src/homelab_mcp/tool_schemas/credential_tools_schema.py`
returns empty. No properties added, removed, or renamed in the `list_keyring_credentials` schema.

## Deviations from Plan

None — plan executed exactly as written. Ruff formatter reformatted whitespace on both implementation commits (expected pre-commit hook behavior).

### Pre-existing Failures (Out of Scope)

Two pre-existing failures confirmed on baseline (same as noted in Plan 01):
- `tests/test_database.py::test_ssh_credentials_table_dropped_postgres`
- `tests/test_proxmox_api.py::TestGetProxmoxClient::test_client_missing_host`

Neither is related to Plan 04 changes. Out of scope per scope-boundary rule.

Pre-existing ruff errors in `tests/integration/` (12 errors in `test_sitemap_integration.py` and `test_ssh_integration.py`) — not in Plan 04's `files_modified`, out of scope per scope-boundary rule.

## Known Stubs

None. All implemented functionality is fully wired — no placeholder values or TODO stubs.

## Threat Flags

None. Plan 04 adds only CLI argument parsing and display-level formatting changes. No new network endpoints, auth paths, or file access patterns introduced. All credential I/O flows through the existing `credential_store.py` helpers (unchanged trust boundary).

## Self-Check

### Files exist
- `src/homelab_mcp/server.py` — FOUND (modified)
- `src/homelab_mcp/credential_store.py` — FOUND (modified)
- `src/homelab_mcp/tool_handlers/credential_handlers.py` — FOUND (modified)
- `tests/test_credentials_cli.py` — FOUND (modified)
- `tests/test_credential_handlers.py` — FOUND (created)

### Commits exist
- f89125a — FOUND (RED: failing tests for cluster CLI)
- 1d1176f — FOUND (GREEN: cluster CLI surface implementation)
- 628c1ae — FOUND (RED: failing test for handler display)
- 8ddf087 — FOUND (GREEN: D-17a display tweak)

### Acceptance criteria
- `grep -n "def _parse_scope_arg" server.py` → line 492: PASS
- `grep -n '"--scope"' server.py` → lines 892, 922 (>=2): PASS
- `grep -c 'scope="cluster"' server.py` → 3 (>=2): PASS
- `grep -n "def unregister_cluster_credential" credential_store.py` → line 259: PASS
- `grep -c "Per-node:" server.py` → 1: PASS
- `grep -c "Cluster-scoped:" server.py` → 1: PASS
- `grep -c "credentials add --type proxmox --scope cluster" server.py` → 1: PASS
- 9 new CLI tests pass: PASS
- `uv run pytest tests/test_credentials_cli.py --no-header` → 22 passed: PASS
- `grep -n "f\"cluster:{e.get('cluster_name', '')}\"" credential_handlers.py` → line 35: PASS
- `grep -n 'e.get("scope") == "cluster"' credential_handlers.py` → line 35: PASS
- `grep -c '"hostname": e["hostname"]' credential_handlers.py` → 0 (gone): PASS
- 4 handler tests pass: PASS
- `uv run ruff check` (plan files) → exit 0: PASS
- `uv run mypy` (3 source files) → exit 0: PASS
- tools.py diff empty (D-17): PASS
- Full unit regression: 705 passed, 2 pre-existing failures: PASS

## Self-Check: PASSED
