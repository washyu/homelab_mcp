# Phase 40: Proxmox VM Lifecycle Polish — Pattern Map

**Mapped:** 2026-04-28
**Files analyzed:** 6 (4 source, 2 test)
**Analogs found:** 6 / 6

All target files are **modifications** of existing files (polish-only phase per CONTEXT.md `<domain>` boundary). No new modules. The closest "analog" for each modified file is most often a sibling helper or assertion already inside the same file — change-by-extension, not change-by-creation.

## File Classification

| Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------|------|-----------|----------------|---------------|
| `src/homelab_mcp/proxmox_api.py` (lines 612-650, `get_proxmox_vm_status` except branch + new `_classify_vm_status_error` helper) | service (HTTP client wrapper) | request-response | `src/homelab_mcp/drift_detection.py:64-127` (`_classify_credential_failure` + `_reason_message`) and `:196-229` (`_classify_unreachable`) | exact (per-row classify-and-return-or-None pattern) |
| `src/homelab_mcp/proxmox_api.py` (lines 443-528, `get_proxmox_client` env-var removal + ValueError rewrite) | service (credential resolver glue) | request-response | `src/homelab_mcp/proxmox_api.py:431-440` (sibling `resolve_proxmox_credentials` raise — verbatim wording template) | exact (same file, same module, identical pattern by design) |
| `src/homelab_mcp/tool_schemas/proxmox_tools_schema.py` (lines 222-294 `create_proxmox_vm` + lines 48, 54, 76 description sweep) | config (JSON-schema dict) | declarative | `src/homelab_mcp/tool_schemas/proxmox_tools_schema.py` itself (other entries — schema shape is uniform across the file) | exact (same file, mechanical edit) |
| `src/homelab_mcp/openapi_app.py` (line 59 `INFRA_REQUIREMENTS["Proxmox"]`) | config (dict literal) | declarative | `openapi_app.py:60` (`"Drift Detection"` entry — already rewritten in Phase 37 D-08) | exact (sibling dict value, just-shipped rewrite to copy phrasing from) |
| `tests/test_ast_regression.py` (extend `_DRIFT_SURFACE_FILES` list + class) | test | declarative + AST scan | `tests/test_ast_regression.py:630-688` (`TestPhase37DriftHygiene.test_no_proxmox_host_in_drift_files`) | exact (Phase 37 D-11 assertion — D-06 extends the file list) |
| `tests/test_proxmox_api.py` (new `vm_not_found` shape tests + schema-required test + no-host ValueError test) | test | request-response (mocked) | `tests/test_proxmox_api.py:416-499` (`TestGetProxmoxVMStatus.test_get_vm_status_*`) | exact (same test class, same mocking idiom) |

## Pattern Assignments

### `proxmox_api.py` — `_classify_vm_status_error` helper + `get_proxmox_vm_status` rewrite (POL-01 D-01/D-02)

**Primary analog:** `src/homelab_mcp/drift_detection.py:64-127` (helper) + `:196-229` (`_classify_unreachable`)

These are the in-tree precedents for "module-private classifier that returns either a structured tuple/dict or `None`, called from a try/except, with a sibling `_*_message` builder for the human sentence." Phase 39's `_classify_unreachable` is the closest by call shape — it takes the raw exception plus the inputs needed to construct the response, and returns a `(reason, message)` tuple. Phase 40's helper returns `dict | None` instead (per CONTEXT D-02 + Claude's Discretion line 72), but everything else copies cleanly.

**Imports pattern** (from `proxmox_api.py:1-19` — already in file, no new imports for the helper):
```python
import logging
import os
import uuid
from typing import Any, Literal

import aiohttp

from .credential_store import find_credential_by_id, get_credential, list_credentials
from .log_filter import sanitize_error
from .ssh_tools import CredentialNotFoundError  # noqa: F401 — re-exported for consumers

logger = logging.getLogger(__name__)
```
Helper does NOT need to import anything new — `aiohttp.ClientResponseError` is already reachable via the bound `aiohttp`. **Critical:** the helper does NOT call `sanitize_error` and does NOT read `e.request_info` — see CONTEXT line 165 ("echo the inputs back; don't pass through the exception"). The URL leak is closed precisely by ignoring the exception's URL fields.

**Per-row classification helper pattern** (from `drift_detection.py:64-99`):
```python
def _classify_credential_failure(exc: CredentialNotFoundError, binding: str | None) -> str:
    """Map (CredentialNotFoundError, binding-context) → reason enum (D-08).

    Reads the ``.reason_hint`` attribute set by the resolver Tier-0 path...
    """
    # If the row had no binding, the failure is definitionally "unbound"
    if binding is None:
        return "unbound"
    hint = getattr(exc, "reason_hint", None)
    if hint == "binding_stale":
        return "binding_stale"
    ...
    logger.warning(
        "Resolver raised CredentialNotFoundError without reason_hint for "
        "bound row (binding=%s). Defaulting to binding_stale; this indicates "
        "a code path that should set reason_hint explicitly.",
        binding,
    )
    return "binding_stale"
```
**Apply:** signature, docstring style with "D-XX" markers, defensive `getattr` for soft attribute reads, `logger.warning` on the "wording didn't match" fallback so format drift surfaces in logs.

**Classify-or-fallback (returns Optional[dict]) pattern** (from `drift_detection.py:196-229` — `_classify_unreachable`):
```python
def _classify_unreachable(
    row: dict[str, Any],
    exc: Exception,
    threshold_days: int,
    now: datetime,
) -> tuple[Literal["unreachable", "missing"], str]:
    """D-01: classify a probe failure into ``unreachable`` (transient) or
    ``missing`` (host gone — last_seen older than threshold)..."""
    parsed = _parse_last_seen(row.get("last_seen"))
    if parsed is not None and (now - parsed) > timedelta(days=threshold_days):
        hostname = row.get("hostname", "")
        message = (
            f"Host last seen {parsed.isoformat()} (>{threshold_days}d ago). "
            f"If decommissioned, run `decommission_device {hostname}` or "
            f"`purge_failed_discoveries` to clean up."
        )
        return ("missing", message)
    return ("unreachable", sanitize_error(exc))
```
**Apply with adjustments for POL-01:**
- Signature: `_classify_vm_status_error(exc: Exception, *, node: str, vmid: int, vm_type: str, host: str) -> dict | None`
- Inspect `isinstance(exc, aiohttp.ClientResponseError)` then `exc.status in (500, 404)`
- Substring-match the body for `"does not exist"` or `str(vmid)` (per D-01)
- On match → return the `vm_not_found` dict per D-02
- On no-match → return `None` (caller falls through to existing generic-error path; **no `sanitize_error` call inside this branch** — that's the existing path's job)
- Use `Literal["qemu", "lxc"]` for `vm_type` per CONTEXT line 142
- Construct `message` from inputs only — never from `exc.request_info.url` or `exc.message`

**Recovery-pointer message style** (from `drift_detection.py:102-127` — `_reason_message`):
```python
def _reason_message(reason: str, hostname: str, credential_type: str) -> str:
    """Human-readable message for the not_eligible bucket (D-08)."""
    if reason == "unbound":
        return (
            f"No {credential_type} credential bound; run "
            f"`homelab-mcp credentials add --type {credential_type} {hostname} <username>` "
            f"to bind."
        )
    ...
```
**Apply:** Phase 40 D-02 message follows this style — declarative input echo + recovery sentence pointing at the next tool to run. Template per CONTEXT D-02:
```python
message = (
    f"VM {vmid} ({vm_type}) not found on node {node!r} at host {host!r}. "
    f"Run list_proxmox_resources to see available VMs."
)
```
Planner polishes wording per Phase 37 D-08 / Phase 39 D-07 conventions (Claude's Discretion line 73).

**Existing except branch to rewrite** (`proxmox_api.py:645-650`):
```python
except (aiohttp.ClientError, ValueError) as e:
    logger.error("Error getting VM status: %s", str(e))
    return {
        "status": "error",
        "message": f"Failed to get VM status: {sanitize_error(e)}",
    }
```
**Rewrite shape:** call `_classify_vm_status_error(...)` first, return its dict if non-None, else fall back to the existing `{status: "error", message: ...}` shape. The fallback retains `sanitize_error(e)` per CONTEXT D-01 ("graceful degradation if Proxmox changes its error format"). The signature already exposes `node`, `vmid`, `host`, `vm_type` — the helper has everything it needs from the function-local scope.

**Reading the response body** (CONTEXT line 141 — "planner confirms which idiom is used elsewhere"): in this codebase `aiohttp.ClientResponseError.message` is the populated string set by aiohttp's `_raise_for_status`. The body is not always re-readable after the exception. The substring-check therefore runs against `str(exc)` and `getattr(exc, "message", "")` — both return the rendered error message including any embedded body excerpt aiohttp captured.

---

### `proxmox_api.py:474, :521` — env-var hard-removal + ValueError rewrite (POL-03 D-04)

**Primary analog:** `proxmox_api.py:431-440` — sibling raise in `resolve_proxmox_credentials`. Verbatim wording template per CONTEXT line 127 ("Reuse `resolve_proxmox_credentials` wording verbatim").

**Canonical wording to copy** (`proxmox_api.py:431-440`):
```python
# Terminal: no credential anywhere (D-05, D-15).
tried = ", ".join(c for c in cluster_names_tried if c) or "<none>"
raise CredentialNotFoundError(
    f"No Proxmox credentials found for {host}. "
    f"Cluster entries tried: {tried}. "
    f"Run `homelab-mcp credentials add --type proxmox {host} <username>` "
    "in your terminal to register this node explicitly, "
    "or run `homelab-mcp credentials add --type proxmox --scope cluster:<name> <token_id>` "
    "in your terminal to register this node explicitly, "
    "if this host belongs to a Proxmox cluster."
)
```
**Apply to line 521 ValueError rewrite:** keep the `homelab-mcp credentials add --type proxmox` and `--scope cluster:<name>` exact phrasing; this is the canonical sentence. Per CONTEXT D-04 template:
```python
raise ValueError(
    "Proxmox host required. "
    "Run `homelab-mcp credentials add --type proxmox <host> <username>` "
    "to register a node, or "
    "`homelab-mcp credentials add --type proxmox --scope cluster:<name> <token_id>` "
    "for cluster tokens."
)
```
Planner polishes wording (Claude's Discretion line 74) but the `homelab-mcp credentials add --type proxmox` literal stays exact for grep-ability and consistency.

**Line to delete** (`proxmox_api.py:474`):
```python
host = host or os.getenv("PROXMOX_HOST")
```
Just the one line. Lines 479-481 (`PROXMOX_USER`/`PROXMOX_PASSWORD`/`PROXMOX_API_TOKEN` reads) are explicitly out of scope per CONTEXT D-04 final paragraph. The resolver-firing condition at `:495` (`if host:`) still works because callers will now always supply `host` (POL-02 schema or other-tool surface raises the rewritten ValueError below).

**Critical preservation per CONTEXT line 96:** the tier-0 UUID short-circuit at `:497-510` is unchanged. The `credential_id` keyword path must keep working — verify by reading the existing tests for `resolve_proxmox_credentials` Tier-0 (`tests/test_proxmox_resolver.py`) before and after the line-474 deletion.

---

### `tool_schemas/proxmox_tools_schema.py:292` — `create_proxmox_vm` schema (POL-02 D-03) + sweep (D-05)

**Primary analog:** other entries in the same file — schema shape is uniform.

**`required` array shape** (existing in `create_proxmox_vm` at line 292):
```python
"required": ["node", "vmid", "name"],
```
**Rewrite to:** `"required": ["node", "vmid", "name", "host"]` (single mechanical edit).

**Description-text rewrite for `host`** (line 287-290 currently):
```python
"host": {
    "type": "string",
    "description": "Proxmox host (optional)",
},
```
**Rewrite per CONTEXT D-03 template:**
```python
"host": {
    "type": "string",
    "description": (
        "Proxmox host. Any node hostname covered by your registered "
        "credential (per-node) or cluster-scope token. Register with "
        "`homelab-mcp credentials add --type proxmox <host> <username>`, "
        "or `... --scope cluster:<name> <token_id>` for cluster tokens."
    ),
},
```
Planner polishes wording within the Phase 37 D-08 convention (point at sitemap CRUD / credentials CLI, never deprecated env vars).

**D-05 sweep targets** (lines 48, 54, 76 — current text):
```python
# Line 47-48 (list_proxmox_resources description):
"description": "List all Proxmox cluster resources (VMs, containers, nodes, storage). Uses PROXMOX_HOST from environment if host not provided.",

# Line 53-54 (list_proxmox_resources host param):
"description": "Proxmox host (optional, uses PROXMOX_HOST env var if not provided)",

# Line 75-76 (get_proxmox_node_status host param):
"description": "Proxmox host (optional, uses PROXMOX_HOST env var)",
```
**Apply:** delete the "uses PROXMOX_HOST env var" clause everywhere; either omit (most common) or replace with the credentials-add pointer where context warrants. Planner runs `Grep("PROXMOX_HOST", path: "src/homelab_mcp/tool_schemas/proxmox_tools_schema.py")` to confirm zero matches post-edit (matches the AST guard's expectation per D-06).

---

### `openapi_app.py:59` — `INFRA_REQUIREMENTS["Proxmox"]` rewrite (D-05 ripple, Claude's Discretion line 76)

**Primary analog:** `openapi_app.py:60` — the just-shipped `"Drift Detection"` entry (Phase 37 D-08).

**Sibling-entry phrasing already in tree** (`openapi_app.py:60`):
```python
"Drift Detection": "a Proxmox VE host registered in the sitemap. Populate via 'discover_and_map' and configure credentials with 'homelab-mcp credentials add --type proxmox' (per-node) or '--scope cluster:<name>' (cluster-wide)",
```
**Current `"Proxmox"` line to rewrite** (`openapi_app.py:59`):
```python
"Proxmox": "a Proxmox VE host. Set PROXMOX_HOST and credentials via environment or POST /api/tools/register_server",
```
**Apply:** rewrite in the same shape as the `"Drift Detection"` entry — point at `homelab-mcp credentials add --type proxmox` (per-node) and `--scope cluster:<name>` (cluster). Drop the `PROXMOX_HOST` reference. The exact phrasing is planner discretion but the structure (cite the CLI, cite the cluster scope) mirrors line 60 verbatim.

**Schema duplication audit** (CONTEXT line 112, Claude's Discretion line 76): planner uses `Grep("create_proxmox_vm|host.*required", path: "src/homelab_mcp/openapi_app.py")` to confirm whether `openapi_app.py` reads `PROXMOX_TOOLS` directly (inheriting the schema change for free) or duplicates schema text. If duplicated, the host-required + description rewrite applies here too.

---

### `tests/test_ast_regression.py` — D-06 AST guard extension

**Primary analog:** `tests/test_ast_regression.py:623-688` (`TestPhase37DriftHygiene.test_no_proxmox_host_in_drift_files`).

**Existing assertion shape** (`tests/test_ast_regression.py:630-668`):
```python
_DRIFT_SURFACE_FILES: tuple[str, ...] = (
    "drift_detection.py",
    "tool_handlers/drift_handlers.py",
    "tool_schemas/drift_tools_schema.py",
)

def test_no_proxmox_host_in_drift_files(self) -> None:
    """Phase 37 D-11: drift surface files contain no PROXMOX_HOST references.
    ...
    """
    src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
    violations: list[str] = []

    # File scan: each drift-surface file must have zero PROXMOX_HOST.
    for relative_path in self._DRIFT_SURFACE_FILES:
        file_path = src_root / relative_path
        assert file_path.exists(), (
            f"Phase 37 D-11 setup error: {file_path} does not exist. "
            f"_DRIFT_SURFACE_FILES is out of sync with the source tree."
        )
        source = file_path.read_text(encoding="utf-8")
        if "PROXMOX_HOST" in source:
            violations.append(
                f"{relative_path}: contains PROXMOX_HOST (Phase 37 D-11 / DRFT-15 — "
                f"drift surface must reference sitemap CRUD tools + credentials CLI, "
                f"not the deprecated env var)"
            )
    ...
```
**Apply per CONTEXT D-06 + Claude's Discretion line 75 ("reuse the existing assertion list — minimal change"):** add two file paths to `_DRIFT_SURFACE_FILES` (or add a new sibling tuple if the planner judges the class name "Phase37DriftHygiene" too narrow):
```python
_DRIFT_SURFACE_FILES: tuple[str, ...] = (
    "drift_detection.py",
    "tool_handlers/drift_handlers.py",
    "tool_schemas/drift_tools_schema.py",
    "proxmox_api.py",                          # Phase 40 D-06
    "tool_schemas/proxmox_tools_schema.py",    # Phase 40 D-06
)
```
Planner picks: extend the existing tuple (minimal — recommended per Discretion) **or** add a new `TestPhase40ProxmoxHostHygiene` class with its own tuple (cleaner phase attribution, slightly more code). Either way, the violation message string updates to cite Phase 40 D-06 alongside Phase 37 D-11.

**Important:** the existing line-672 `INFRA_REQUIREMENTS["Drift Detection"]` dict-value scan is per Phase 37; for Phase 40 the **sibling key `"Proxmox"`** must also lack `PROXMOX_HOST` after the openapi_app.py rewrite above. Planner adds an analogous dict-value scan for `INFRA_REQUIREMENTS["Proxmox"]` if not already covered by the file-level scan over `openapi_app.py` (it isn't — openapi_app.py is intentionally NOT in the surface-files list per the line 627 comment).

---

### `tests/test_proxmox_api.py` — new functional tests for D-01/D-02/D-03/D-04

**Primary analog:** `tests/test_proxmox_api.py:416-499` (`TestGetProxmoxVMStatus` class).

**Existing test shape — happy path** (`tests/test_proxmox_api.py:418-443`):
```python
@pytest.mark.asyncio
@patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)
async def test_get_vm_status_qemu_success(self, mock_get_client):
    """Test getting status of a QEMU VM."""
    # GIVEN: Mock client with VM status
    mock_client = AsyncMock()
    mock_get_client.return_value = mock_client
    mock_client.get.return_value = {
        "status": "running",
        ...
    }

    # WHEN: Getting VM status
    result = await get_proxmox_vm_status(node="pve", vmid=100, vm_type="qemu")

    # THEN: Should return success with VM details
    assert result["status"] == "success"
    assert result["node"] == "pve"
    assert result["vmid"] == 100
    ...
```
**Apply patterns:** GIVEN/WHEN/THEN comment block, `@patch("src.homelab_mcp.proxmox_api.get_proxmox_client", new_callable=AsyncMock)` to bypass the credential resolver, `mock_client.get.side_effect = ...` to inject the failure mode, assert on the result dict shape.

**Existing not-found test (current — to be augmented, not deleted)** (`tests/test_proxmox_api.py:469-483`):
```python
async def test_get_vm_status_vm_not_found(self, mock_get_client):
    """Test getting status of non-existent VM."""
    mock_client = AsyncMock()
    mock_get_client.return_value = mock_client
    mock_client.get.side_effect = ClientError("VM 999 does not exist")

    result = await get_proxmox_vm_status(node="pve", vmid=999)

    assert result["status"] == "error"
    assert "does not exist" in result["message"]
```
**Apply:** the existing test currently asserts only the legacy fallback shape. Phase 40 adds **new sibling tests** that inject `aiohttp.ClientResponseError(status=500, message="VM 9999 does not exist")` (or similar) and assert the **new** structured shape:
```python
async def test_get_vm_status_returns_vm_not_found_shape(self, mock_get_client):
    """POL-01 D-02: HTTP 500 with 'does not exist' body returns vm_not_found shape."""
    mock_client = AsyncMock()
    mock_get_client.return_value = mock_client
    # Simulate Proxmox 500 + body containing 'does not exist'
    fake_request_info = MagicMock()
    err = aiohttp.ClientResponseError(
        request_info=fake_request_info,
        history=(),
        status=500,
        message="VM 9999 does not exist",
    )
    mock_client.get.side_effect = err

    result = await get_proxmox_vm_status(
        node="pve1", vmid=9999, vm_type="qemu", host="homelab-pve1"
    )

    assert result["status"] == "error"
    assert result["error_kind"] == "vm_not_found"
    assert result["node"] == "pve1"
    assert result["vmid"] == 9999
    assert result["vm_type"] == "qemu"
    assert result["host"] == "homelab-pve1"
    assert "list_proxmox_resources" in result["message"]
    # URL leak check: message constructed from inputs, not from exception
    assert "/api2/" not in result["message"]
```
Repeat for: LXC variant; vmid-as-substring-only-match (no "does not exist" wording); `status=404` defensive case; body-unreadable graceful-degradation case (asserts the legacy shape, not the new one — covers D-01 fallback).

**Schema-required test pattern** (CONTEXT line 116):
```python
def test_create_proxmox_vm_schema_requires_host():
    """POL-02 D-03: 'host' is in the create_proxmox_vm required list."""
    from src.homelab_mcp.tool_schemas.proxmox_tools_schema import PROXMOX_TOOLS

    schema = PROXMOX_TOOLS["create_proxmox_vm"]["inputSchema"]
    assert "host" in schema["required"]
    assert schema["properties"]["host"]["type"] == "string"
```

**No-host ValueError test pattern** (CONTEXT line 117):
```python
async def test_get_proxmox_client_no_host_raises_actionable_error():
    """POL-03 D-04: missing host → ValueError with credentials-add CLI hint, no PROXMOX_HOST."""
    # Bypass schema; call get_proxmox_client directly with no host & no env var.
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError) as exc_info:
            await get_proxmox_client(host=None)

    msg = str(exc_info.value)
    assert "homelab-mcp credentials add --type proxmox" in msg
    assert "PROXMOX_HOST" not in msg  # critical: env-var name must NOT appear
    assert "scope cluster:" in msg or "--scope cluster" in msg  # cluster pointer
```

## Shared Patterns

### Structured-error contract (POL-01 message construction)
**Source:** Phase 36/37 — every proxmox / drift tool returns `{status: "success", ...}` or `{status: "error", message: ...}`.
**Apply to:** `_classify_vm_status_error` return dict.
**Excerpt to extend** (existing fallback in `proxmox_api.py:646-650`):
```python
return {
    "status": "error",
    "message": f"Failed to get VM status: {sanitize_error(e)}",
}
```
**Phase 40 extension shape** (per CONTEXT D-02):
```python
return {
    "status": "error",
    "error_kind": "vm_not_found",
    "node": node,
    "vmid": vmid,
    "vm_type": vm_type,
    "host": host,
    "message": (
        f"VM {vmid} ({vm_type}) not found on node {node!r} "
        f"at host {host!r}. "
        f"Run list_proxmox_resources to see available VMs."
    ),
}
```
`status: "error"` is preserved (binary contract). `error_kind` is the new programmatic discriminator. `message` is constructed from inputs only — **never wraps `sanitize_error(e)`**, which is what closes the URL leak for this code path.

### Hard-error-with-actionable-pointer (POL-03 ValueError)
**Source:** `proxmox_api.py:431-440` (`resolve_proxmox_credentials` raise) + `drift_detection.py:104-127` (`_reason_message`).
**Apply to:** `get_proxmox_client` line 521 ValueError rewrite.
**Excerpt** (verbatim canonical phrasing from `proxmox_api.py:434-439`):
```python
f"Run `homelab-mcp credentials add --type proxmox {host} <username>` "
"in your terminal to register this node explicitly, "
"or run `homelab-mcp credentials add --type proxmox --scope cluster:<name> <token_id>` "
"if this host belongs to a Proxmox cluster."
```
The literal `homelab-mcp credentials add --type proxmox` and `--scope cluster:<name>` strings are canonical — Phase 40's ValueError text uses the same form for cross-error grep-ability.

### Test mocking idiom (functional tests for POL-01)
**Source:** `tests/test_proxmox_api.py:418-499` — `TestGetProxmoxVMStatus` class.
**Apply to:** every new test for the `vm_not_found` shape.
**Standard imports** (`tests/test_proxmox_api.py:7-26`):
```python
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientError
from aioresponses import aioresponses

from src.homelab_mcp.proxmox_api import (
    get_proxmox_vm_status,
    create_proxmox_vm,
    get_proxmox_client,
    ...
)
```
Add `import aiohttp` (for `aiohttp.ClientResponseError`) — already in test file context per the `aioresponses` import.

### AST guard extension (D-06)
**Source:** `tests/test_ast_regression.py:630` (`_DRIFT_SURFACE_FILES` tuple) + line 636-688 scan loop.
**Apply to:** add `proxmox_api.py` and `tool_schemas/proxmox_tools_schema.py` to the file list, plus an `INFRA_REQUIREMENTS["Proxmox"]` dict-value scan analogous to the existing `"Drift Detection"` scan at line 673-680.

## No Analog Found

None. Every Phase 40 change extends an existing pattern in the codebase:
- The classifier helper has two precedents in `drift_detection.py` (Phase 38.1, Phase 39).
- The ValueError wording has a verbatim sibling in the same file (`proxmox_api.py:431-440`).
- The schema-required edit is mechanical against existing schema entries.
- The AST guard is an existing assertion that gains two file-list entries.
- The functional tests extend an existing test class with the same mocking idiom.

This is precisely why Phase 40 is "polish-only" — no greenfield patterns are introduced.

## Metadata

**Analog search scope:**
- `src/homelab_mcp/proxmox_api.py` (target + analog)
- `src/homelab_mcp/drift_detection.py` (Phase 38.1 / Phase 39 classifier analogs)
- `src/homelab_mcp/tool_schemas/proxmox_tools_schema.py` (target + sibling-entry analog)
- `src/homelab_mcp/tool_handlers/proxmox_handlers.py` (call-site verification only)
- `src/homelab_mcp/openapi_app.py` (target + sibling-entry analog at line 60)
- `tests/test_ast_regression.py` (Phase 37 D-11 analog at line 623-688)
- `tests/test_proxmox_api.py` (target + sibling-test analog at line 416-499)

**Files scanned:** 7 source files (4 analogs + 3 reference files for call-site / import-style verification).
**Pattern extraction date:** 2026-04-28.
