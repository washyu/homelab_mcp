---
phase: 34-cluster-scoped-proxmox-credentials
verified: 2026-04-23T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
gaps: []
deferred: []
human_verification: []
---

# Phase 34: Cluster-Scoped Proxmox Credentials — Verification Report

**Phase Goal:** Introduce cluster-scoped Proxmox credentials — credentials are keyed to a cluster name instead of a single node, and any node in the cluster can authenticate against the same shared credential. CRED-08 requirement.
**Verified:** 2026-04-23
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (Success Criteria)

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| SC-1 | Users can register a cluster-scoped credential via `credentials add --scope cluster:<name>` | VERIFIED | `_parse_scope_arg` helper at server.py:492; argparse `--scope` flag on `add_p` (line 892) and `remove_p` (line 922); `_cmd_credentials_add` cluster branch calls `store_credential(..., scope="cluster", cluster_name=...)` and `register_credential(..., scope="cluster", ...)` |
| SC-2 | Any node discovered via `discover_and_map` against that cluster uses the shared credential | VERIFIED | `resolve_proxmox_credentials` at proxmox_api.py:194 implements cluster walk tier; `get_proxmox_client` (line 332, async) calls `await resolve_proxmox_credentials(host, session=session)` (line 371) when host known and no explicit auth; DEBUG logs include `tier=cluster` and terminal `source=cluster` records |
| SC-3 | `get_proxmox_client` resolves the right credential by walking: explicit args → registry scope match → error | VERIFIED | proxmox_api.py:366-386 — explicit `api_token` or `username+password` bypasses resolver; when host-only path taken, `resolve_proxmox_credentials` walks node tier then cluster tier; `CredentialNotFoundError` raised on miss naming all tried clusters + `credentials add --type proxmox` CLI pointer |
| SC-4 | `credentials list` groups output into Per-node: and Cluster-scoped: sections | VERIFIED | `_cmd_credentials_list` at server.py:645 partitions entries by `e.get("scope", "node")`; prints `"  Per-node:"` and `"  Cluster-scoped:"` headings only when entries exist in each group; `handle_list_keyring_credentials` in credential_handlers.py:35 renders cluster entries as `cluster:<name>` instead of blank hostname (D-17a) |
| SC-5 | Per-node credential behavior remains 100% backward-compatible (no regressions) | VERIFIED | Resolver tier-1 short-circuits on per-node registry match without calling `/cluster/status` (proxmox_api.py:223-241); per-node CLI paths in `_cmd_credentials_add` and `_cmd_credentials_remove` are byte-for-byte equivalent to pre-Phase-34 behavior; `register_credential` / `store_credential` / `get_credential` / `delete_credential` accept `scope` and `cluster_name` as keyword-only params with defaults `"node"` and `""` — existing callers without those kwargs get legacy behavior unchanged |

**Score: 5/5 truths verified**

---

### Deferred Items

None.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/homelab_mcp/credential_store.py` | `register_credential(scope, cluster_name)` + cluster keyring key form | VERIFIED | `register_credential` at line 175 accepts `scope: str = "node"` and `cluster_name: str = ""` keyword-only params. `_keyring_key` helper at line 25 returns `f"{username}@cluster:{cluster_name}"` for cluster scope. `store_credential`, `get_credential`, `delete_credential` all updated. `unregister_cluster_credential` added at line 259. |
| `src/homelab_mcp/proxmox_api.py` | `async resolve_proxmox_credentials` + module-level `_HOST_CLUSTER_CACHE` + `async get_proxmox_client` + INJECT-03 deleted | VERIFIED | `resolve_proxmox_credentials` at line 194. `_HOST_CLUSTER_CACHE: dict[str, str] = {}` at line 21. `get_proxmox_client` is `async def` at line 332. INJECT-03 shortcut block absent (`grep -c "INJECT-03"` → 0; `grep -c "registry_entries[0]"` → 0). |
| `src/homelab_mcp/server.py` | `--scope cluster:<name>` argparse flag + `_parse_scope_arg` + cluster branches in add/remove/list | VERIFIED | `_parse_scope_arg` at line 492. `--scope` flag on both `add_p` and `remove_p` subparsers (lines 892, 922). Cluster branches in `_cmd_credentials_add` (line 541), `_cmd_credentials_remove` (line 682), and `_cmd_credentials_list` (line 645). Epilog updated with three new cluster examples. |
| `src/homelab_mcp/tool_handlers/credential_handlers.py` | D-17a display tweak for cluster entries | VERIFIED | Line 35: `f"cluster:{e.get('cluster_name', '')}"` conditional expression for cluster-scoped entries. Legacy entries without `scope` field use `e["hostname"]` via `.get("scope")` default None. |

---

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `credential_store.register_credential` | `credential_registry.json` | `_save_registry` with `scope` + `cluster_name` fields | WIRED | Entry dict at line 239-248 always emits `"scope"` and `"cluster_name"` fields. |
| `credential_store.store_credential` | OS keyring `homelab-mcp-proxmox` service | `_keyring_key(username, hostname, scope, cluster_name)` → `f"{username}@cluster:{cluster_name}"` | WIRED | `_keyring_key` at line 25; called in `store_credential` at line 60, `get_credential` at line 101, `delete_credential` at line 143. |
| `proxmox_api.resolve_proxmox_credentials` | `credential_store.list_credentials / get_credential` | Tier-1 per-node lookup + Tier-2 cluster-entry walk | WIRED | `list_credentials(credential_type="proxmox")` at proxmox_api.py:220; `get_credential(..., scope="cluster", cluster_name=...)` at lines 250-255 and 278-284. |
| `proxmox_api.resolve_proxmox_credentials` | Proxmox `GET /cluster/status` | Throwaway `ProxmoxAPIClient` per candidate + `await client.get("/cluster/status")` | WIRED | proxmox_api.py:297-307; response parsed at line 309-318 to match `type=="cluster"` row. |
| `proxmox_api.get_proxmox_client` | `resolve_proxmox_credentials` | `await resolve_proxmox_credentials(host, session=session)` when host set and no explicit auth | WIRED | proxmox_api.py:370-371; resolver token assigned to `api_token` at line 372. |
| Nine async consumer functions in `proxmox_api.py` | `get_proxmox_client` | `client = await get_proxmox_client(host=host, session=session)` | WIRED | `grep -c "await get_proxmox_client("` → 9. Lines: 415, 454, 493, 537, 580, 659, 745, 817, 869 (from summary). |
| `server._cmd_credentials_add` (cluster branch) | `credential_store.store_credential + register_credential` | `scope="cluster"`, `cluster_name=` kwargs | WIRED | server.py lines 261-271; both calls include explicit `scope="cluster"` and `cluster_name=cluster_name` kwargs. |
| `server._cmd_credentials_list` | stdout grouped output | Partition entries by `e.get("scope", "node")` | WIRED | server.py:651-662; `Per-node:` and `Cluster-scoped:` headings confirmed (grep count = 1 each). |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `credential_handlers.handle_list_keyring_credentials` | `entries` | `list_credentials(credential_type=...)` reads `_REGISTRY_PATH` JSON | Yes — reads actual registry file | FLOWING |
| `proxmox_api.resolve_proxmox_credentials` | `entries` | `list_credentials("proxmox")` + `get_credential(..., scope="cluster", ...)` reads OS keyring | Yes — reads real registry + real keyring | FLOWING |
| `proxmox_api.get_proxmox_client` | `api_token` | `await resolve_proxmox_credentials(host, session=session)` returns real token | Yes — flows from resolver | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| `get_proxmox_client` is a coroutine function | `python -c "from homelab_mcp.proxmox_api import get_proxmox_client; import inspect; print(inspect.iscoroutinefunction(get_proxmox_client))"` | `True` | PASS |
| INJECT-03 shortcut deleted | `grep -c "INJECT-03" src/homelab_mcp/proxmox_api.py` | `0` | PASS |
| All 9 internal call sites await get_proxmox_client | `grep -c "await get_proxmox_client(" src/homelab_mcp/proxmox_api.py` | `9` | PASS |
| `--scope` flag appears in credentials add help | `uv run homelab-mcp credentials add --help \| grep -c "\-\-scope"` (inferred from argparse at line 892) | At least 1 (confirmed by grep on source) | PASS |
| Full unit test suite | `uv run pytest tests/ -m "not integration" -q` | `1 failed (pre-existing), 709 passed, 9 skipped` | PASS |
| Phase-34-specific tests | `uv run pytest tests/test_credential_store.py tests/test_proxmox_resolver.py tests/test_credentials_cli.py tests/test_credential_handlers.py -q` | `60 passed` | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| CRED-08 | Plans 01, 02, 03, 04 | Proxmox API tokens can be stored at cluster scope — one cluster credential automatically serves all N nodes in the same Proxmox datacenter; per-node tokens remain supported and take precedence when both exist | SATISFIED | Plan 01: `register_credential` / `store_credential` / `get_credential` extended with `scope` + `cluster_name`. Plan 02: `resolve_proxmox_credentials` implements two-tier per-node → cluster walk. Plan 03: `get_proxmox_client` async, wired to resolver, INJECT-03 deleted. Plan 04: CLI surface `--scope cluster:<name>` on `credentials add/remove/list` + MCP handler display. |

---

### Anti-Patterns Found

| File | Pattern | Severity | Assessment |
| ---- | ------- | -------- | ---------- |
| None | — | — | No stub patterns, empty returns, or TODO/FIXME/PLACEHOLDER comments found in the four modified source files. |

No TODO/FIXME markers found in `credential_store.py`, `proxmox_api.py`, `server.py`, or `credential_handlers.py`. No `return null` / `return {}` / `return []` empty stubs in the new code paths. All new functions are fully implemented.

---

### Human Verification Required

None. All success criteria are verifiable programmatically and have been confirmed by code inspection plus test execution.

---

### Gaps Summary

No gaps. All five success criteria are verified by implementation evidence and confirmed passing tests (60 new phase-34-specific tests, plus 709 passing unit tests with only the pre-existing PostgreSQL import error failing).

---

## Pre-Existing Failures (Out of Scope)

One pre-existing test failure exists that predates Phase 34 and is unrelated to this phase:

- `tests/test_database.py::test_ssh_credentials_table_dropped_postgres` — `ImportError: No module named 'psycopg2'`. PostgreSQL driver not installed in test environment. Documented as pre-existing in all four Plan SUMMARYs.

The previously mentioned `tests/test_proxmox_api.py::TestGetProxmoxClient::test_client_missing_host` pre-existing failure was actually **fixed** during Plan 03 when `get_proxmox_client` was converted to async — this test now passes.

---

_Verified: 2026-04-23T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
