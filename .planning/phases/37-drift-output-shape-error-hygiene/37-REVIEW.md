---
phase: 37-drift-output-shape-error-hygiene
reviewed: 2026-04-25T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - src/homelab_mcp/drift_detection.py
  - src/homelab_mcp/openapi_app.py
  - src/homelab_mcp/server.py
  - src/homelab_mcp/tool_handlers/drift_handlers.py
  - src/homelab_mcp/tool_schemas/drift_tools_schema.py
  - docs/tool-reference.md
  - tests/test_ast_regression.py
  - tests/test_drift_detection.py
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 37: Code Review Report

**Reviewed:** 2026-04-25T00:00:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Phase 37 delivers DRFT-13/14/15/16: a stable four-bucket envelope shape for `scan_infrastructure_drift`, `counts` sub-dict, conditional `guidance`, exact-hostname `node` filter, and an inert `vm_type` parameter. The core implementation in `drift_detection.py` is clean and correct. The handler, schema, and test suite are well-structured and the AST regression guards are comprehensive.

Two warnings are raised: one is a logic gap where the defensive `continue` after the second `resolve_proxmox_credentials` call silently drops a row from the `probed_ok` bucket without updating any bucket, making `scanned` inconsistent with the actual iteration outcome; the second is a stale docstring in a preserved Phase 36 test that claims the `node` filter is "inert in Phase 36" even though Phase 37 actively uses it. Three info items cover documentation staleness (deprecated tool entries in `docs/tool-reference.md`), a minor type annotation gap, and a `global` usage in `openapi_app.py`.

---

## Warnings

### WR-01: Defensive `CredentialNotFoundError` catch in resolve step silently drops rows from all buckets

**File:** `src/homelab_mcp/drift_detection.py:166-172`

**Issue:** After `get_proxmox_client` succeeds (line 146), `resolve_proxmox_credentials` is called a second time to capture `(scope, cluster_name)` telemetry. If that second call raises `CredentialNotFoundError`, the code hits a bare `continue` (line 172) and the row is dropped without being appended to any bucket. The comment says "should not happen after get_proxmox_client succeeded," but if it does happen — due to a race condition on the credential cache, or a future code change that breaks the cache invariant — `scanned` will be less than the number of rows iterated and no diagnostic information (not even an `unreachable` entry) surfaces.

The consequence is a silently-wrong `counts` / `scanned` total. From the caller's perspective the row vanished; there is no way to distinguish "credential resolved and probed" from "credential evaporated mid-scan." In a monitoring context this is a correctness issue, not merely a cosmetic one.

**Fix:** Append the row to `unreachable` before continuing, so the invariant `scanned == len(probed_ok) + len(unreachable) + len(unknown) + len(changed)` is preserved even in the defensive path:

```python
        except CredentialNotFoundError:
            # Defensive — should not happen after get_proxmox_client succeeded.
            # If it does, surface as unreachable so the row is counted and visible.
            unreachable.append({
                "hostname": hostname,
                "connection_ip": row.get("connection_ip", ""),
                "scope": "unknown",
                "cluster_name": None,
                "status": "unreachable",
                "error": "credential disappeared between client-resolve and telemetry-resolve",
                "scan_timestamp": scan_timestamp,
            })
            continue
```

---

### WR-02: `test_inert_filter_passthrough` docstring claims `node` is "inert in Phase 36" — misleading for Phase 37 regression coverage

**File:** `tests/test_drift_detection.py:165`

**Issue:** The docstring reads `"""D-04: node and vm_type kwargs are accepted but inert in Phase 36."""`. In Phase 37 the `node` parameter is active — it filters sitemap rows by exact hostname (implemented in `drift_detection.py:133-134`). The test itself uses an empty sitemap so both pass regardless, but the docstring gives false confidence that the test covers the "inert in Phase 37" case. A future reader diagnosing a node-filter regression may be misdirected by the stale claim.

This test was "preserved verbatim from Phase 36 per the class header." That is legitimate, but the docstring should at minimum be annotated to indicate the Phase 37 behavior supersedes the Phase 36 statement.

**Fix:** Update the docstring to reflect current semantics and distinguish the Phase 36 and Phase 37 behaviors:

```python
    @pytest.mark.asyncio
    async def test_inert_filter_passthrough(self):
        """D-04: node and vm_type kwargs are accepted without error.

        Preserved from Phase 36: in Phase 36 BOTH filters were inert; in Phase 37
        the node filter is active (exact-match), but this test exercises an empty
        sitemap where the filter result is identical (zero rows either way).
        The canonical Phase 37 active-filter tests are test_node_filter_exact_hostname_match
        and test_node_filter_no_match_returns_success_empty.
        """
```

---

## Info

### IN-01: `docs/tool-reference.md` documents removed tools (`setup_mcp_admin`, `update_mcp_admin_groups`, `update_server_credentials`, `remove_server`)

**File:** `docs/tool-reference.md:64`, `docs/tool-reference.md:181`, `docs/tool-reference.md:1197`, `docs/tool-reference.md:1229`

**Issue:** The tool-reference doc still documents four tool entries that were removed in Phase 33 (`setup_mcp_admin` at line 64, `update_mcp_admin_groups` at line 181, `update_server_credentials` at line 1197, `remove_server` at line 1229). These names are in the `FORBIDDEN_SOURCE_STRINGS` list in `test_ast_regression.py` (Phase 33 D-25), confirming they were intentionally deleted from the server surface. The doc entries now describe tools that do not exist and will return an error if an LLM client reads the reference and tries to call them.

This is a documentation staleness issue, not a source code defect. No source code is affected.

**Fix:** Remove (or mark as deprecated/removed) the four entries in `docs/tool-reference.md` for `setup_mcp_admin`, `update_mcp_admin_groups`, `update_server_credentials`, and `remove_server`.

---

### IN-02: `drift_tools_schema.py` uses unparameterized `dict` as value type annotation

**File:** `src/homelab_mcp/tool_schemas/drift_tools_schema.py:3`

**Issue:** The module-level type annotation is `dict[str, dict]` rather than `dict[str, dict[str, Any]]`. The inner `dict` is unparameterized, which mypy accepts but silently widens: any access to values in the inner dict returns `Any`, bypassing type checking. The project's CLAUDE.md requires strict typing with mypy.

**Fix:**

```python
from typing import Any

DRIFT_TOOLS: dict[str, dict[str, Any]] = {
```

---

### IN-03: `openapi_app.py` module-level mutable counters use `global` inside a closure

**File:** `src/homelab_mcp/openapi_app.py:567`

**Issue:** `_request_count` and `_error_count` are module-level integers mutated via `global` inside the `tool_endpoint` async closure (line 567: `global _request_count, _error_count`). This pattern works in single-process deployments but creates race conditions under async concurrency: a read-modify-write on `_request_count += 1` is not atomic in Python's asyncio event loop if awaits occur between the read and write. The counters are cosmetic (health endpoint only), so this is a low-severity issue, but it is a latent correctness gap.

**Fix:** Use `threading.Lock` or, preferably since this is async code, wrap the counters in an `asyncio.Lock` if precision matters. For a cosmetic counter, accepting the occasional skew and documenting it explicitly is also acceptable:

```python
# NOTE: _request_count / _error_count are approximate — non-atomic increment
# under concurrent async tasks. Suitable for monitoring dashboards; not for billing.
```

---

_Reviewed: 2026-04-25T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
