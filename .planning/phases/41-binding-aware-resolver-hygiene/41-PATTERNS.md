# Phase 41: Binding-Aware Resolver Hygiene — Pattern Map

**Mapped:** 2026-04-29
**Files analyzed:** 6 (1 new test file + 1 new symbol + 4 modifications)
**Analogs found:** 6 / 6

This phase is a **wiring phase, not a building phase** (RESEARCH "Don't Hand-Roll" §). Every primitive needed already exists in the codebase. PATTERNS.md routes each new/modified file to the closest existing analog so the planner can specify "copy from `<file>:<lines>`" rather than re-derive.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| NEW symbol `resolve_ssh_for_sitemap_row` in `src/homelab_mcp/ssh_tools.py` | utility (resolver helper) | request-response (sync DB lookup + sync resolver call) | `_probe_one` body in `src/homelab_mcp/drift_detection.py:488-524` (lines 488-497 are the verbatim row→binding→resolver pattern to crystallize) + `_scan_registry_for_binding` in `src/homelab_mcp/ssh_tools.py:812-835` (zero-raise scan helper structure) | exact (drift's working impl is the spec) |
| MODIFY `src/homelab_mcp/sitemap.py` `discover_and_store` (lines 410-463) + `parse_discovery_output` (lines 76-151) | service (orchestrator) | request-response | self (existing function); pre-fix uses `ssh_discover_system_with_binding` — the modification swaps the resolver call to the new helper and threads `requested_identifier` through `parse_discovery_output` | self (in-place edit) |
| MODIFY `src/homelab_mcp/error_handling.py` `ssh_connection_wrapper` (lines 229-321) | middleware (decorator/error wrapper) | request-response | self; the four error-envelope `json.dumps({...})` blocks at lines 248-263, 269-278, 280-289, 296-305, 307-316 each gain a `"hostname"` field (`kwargs.get("hostname", args[0] if args else "unknown")` — the same expression already used for `connection_ip` extraction at line 247/266/292) | self (in-place edit) |
| MODIFY `src/homelab_mcp/drift_detection.py` `_probe_one` (lines 488-541) + Proxmox row-loop call site (lines 759-763) | service (drift scanner) | request-response | self; the row-loop already has the right shape — the change is `host=hostname` → `host=row.get("connection_ip") or hostname` and the `_probe_one` `creds = resolve_ssh_credentials(...)` call becomes `creds, _ = resolve_ssh_for_sitemap_row(...)` (or, after refactor, the helper returns the row so dial-target selection happens inside the helper) | self (in-place edit) |
| NEW `tests/test_phase41_binding_aware.py` (functional regression for Bugs AA, BB, V) | test | request-response | `tests/test_drift_detection.py` lines 21-80 (TestScanDrift4Bucket — `MagicMock` db_adapter + `AsyncMock` proxmox client + `patch` context-manager + `pytest.mark.asyncio` shape) | role-match (test framework parity) |
| MODIFY `tests/test_ast_regression.py` add `TestPhase41BindingAwareResolver` class | test (AST guard) | static analysis | `TestPhase41_1KeyringHygiene` at `tests/test_ast_regression.py:1072-1196` (allowlist + ast.walk pattern, this phase's predecessor — added 2026-04-29 in commit d1c398a) + `TestPhase39_1NoSkipInDriftEnum` at `tests/test_ast_regression.py:853-983` (function-scoped AST + canonical-name pin + call-site floor) | exact (sibling phase, identical mechanic) |

## Pattern Assignments

### NEW symbol `resolve_ssh_for_sitemap_row` in `src/homelab_mcp/ssh_tools.py`

**Analog (primary):** `src/homelab_mcp/drift_detection.py:488-497` — the working row→binding→resolver sequence.
**Analog (secondary):** `src/homelab_mcp/ssh_tools.py:812-835` — `_scan_registry_for_binding` shows the "best-effort, never-raise" scan-helper convention this codebase prefers, plus the existing import location and docstring header style.

**Imports pattern** (mirror `ssh_tools.py:1-30` style; helper goes near `_scan_registry_for_binding` in the same file, so no new module imports — `database.get_database_adapter` and `find_credential_by_id` are already in scope):

```python
# At call sites of the new helper (top of function in ssh_tools.py):
from .database import get_database_adapter
# resolve_ssh_credentials, CredentialNotFoundError, list_credentials already imported in ssh_tools.py
```

**Core pattern — row→binding→resolver** (verbatim from `drift_detection.py:488-497`, lift this 10-line block):

```python
async def _probe_one(row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    hostname = row.get("hostname", "")
    binding = row.get("ssh_credential_id")
    # Caller filters by ssh_credential_id, but be defensive against
    # external callers that don't.
    if binding is None:
        return (hostname, {"_error": "no_ssh_credential_id"})
    async with semaphore:
        try:
            creds = resolve_ssh_credentials(hostname, credential_id=binding)
```

→ The new helper inverts this: it takes the **identifier** (not the row), does the row lookup, then runs the same `resolve_ssh_credentials(..., credential_id=binding)` call. RESEARCH Pattern 1 (lines 175-240) is the proposed signature — copy that body verbatim into the planner action.

**Multi-match disambiguation pattern** (mirror `ssh_tools.py:80-92` `_resolve_username_from_registry`):

```python
# Source: src/homelab_mcp/ssh_tools.py:85-91 — existing CredentialNotFoundError shape
if len(matched) >= 2:
    registered = ", ".join(sorted(e["username"] for e in matched))
    raise CredentialNotFoundError(
        f"Multiple credentials registered for {hostname}: {registered}. "
        "Specify username explicitly, or call list_keyring_credentials "
        "to inspect registered entries."
    )
```

→ New helper raises with the same `CredentialNotFoundError` constructor shape, substituting "Multiple sitemap rows matched" + a pointer to `get_network_sitemap` (per RESEARCH Open Question 1 / Pitfall 6).

**Sitemap row lookup primitive** (use as-is, no new code):

```python
# Source: src/homelab_mcp/database.py:440-452
def find_devices_by_hostname_or_ip(self, hostname: str) -> list[dict[str, Any]]:
    """SQLite implementation. See DatabaseAdapter.find_devices_by_hostname_or_ip."""
    cursor.execute(
        "SELECT id, hostname, connection_ip, "
        "ssh_credential_id, proxmox_credential_id "
        "FROM devices WHERE hostname = ? OR connection_ip = ?",
        (hostname, hostname),
    )
    return [dict(row) for row in cursor.fetchall()]
```

→ Helper calls `db.find_devices_by_hostname_or_ip(identifier)`. Returns `list[dict]` with the exact keys the helper needs (`hostname`, `connection_ip`, `ssh_credential_id`).

**Resolver delegation** (Tier-0 short-circuit) — call as-is, do NOT duplicate the auth_type branching (RESEARCH Anti-pattern 2):

```python
# Source: src/homelab_mcp/ssh_tools.py:95-103 — Tier-0 keyword-only param
def resolve_ssh_credentials(
    hostname: str,
    username: str | None = None,
    password: str | None = None,
    key_path: str | None = None,
    port: int = 22,
    *,
    credential_id: str | None = None,
) -> SSHCredentials:
```

→ New helper passes `credential_id=row["ssh_credential_id"]` when row matched + binding non-null; passes nothing on the bare-fallback path.

---

### MODIFY `src/homelab_mcp/sitemap.py`

**Analog:** self. Two surgical edits.

**Edit 1 — `discover_and_store` (lines 410-463):** swap the `ssh_discover_system_with_binding` call for the new helper + dial-target selection. Existing pattern at lines 430-436:

```python
# Source: src/homelab_mcp/sitemap.py:430-436 (current)
from .ssh_tools import ssh_discover_system_with_binding

# Phase 38.1 R3: resolver+discovery wrapper captures the matched
# registry entry's credential_id (None when no registry entry matches).
discovery_result, used_credential_id = await ssh_discover_system_with_binding(
    hostname, username, password, key_path, port,
)
```

→ Becomes (per RESEARCH Pattern 3, lines 264-280): call `resolve_ssh_for_sitemap_row(hostname)` first, derive `dial_target = row.get("connection_ip") or hostname` (Pitfall 4 guard), then call `ssh_discover_system` with that dial target. On error, look up the existing row first and merge `device.hostname` / `device.connection_ip` from it (Pattern 3).

**Edit 2 — `parse_discovery_output` (lines 76-151):** add `requested_identifier` parameter, use it on the JSON-decode-error path AND the `status=="error"` branch. Current degenerate-shape lines 143-151:

```python
# Source: src/homelab_mcp/sitemap.py:143-151 (current — Bug BB site)
except json.JSONDecodeError as e:
    # Create error device for invalid JSON
    return NetworkDevice(
        hostname="unknown",
        connection_ip="unknown",
        last_seen=datetime.now().isoformat(),
        status="error",
        error_message=f"JSON parse error: {sanitize_error(e)}",
    )
```

→ Both `"unknown"` literals become `requested_identifier or "unknown"` (RESEARCH Pitfall 3). The `data.get("hostname", "")` on line 82 becomes `data.get("hostname") or requested_identifier or ""` (RESEARCH Pattern 2, lines 244-260).

**Error handling pattern** (mirror existing `sitemap.py:138-141` — assignment-style error message wiring; do NOT introduce new error classes):

```python
# Source: src/homelab_mcp/sitemap.py:138-141
elif data.get("status") == "error":
    device.error_message = data.get("error", "Unknown error")
```

→ Extend with the `device.hostname = device.hostname or requested_identifier` assignment per RESEARCH Pattern 2.

---

### MODIFY `src/homelab_mcp/error_handling.py` `ssh_connection_wrapper` (lines 229-321)

**Analog:** self. The wrapper already extracts `hostname` from `kwargs`/`args` for the `connection_ip` field. The change is to **also emit it as a top-level `hostname` field** in every error envelope.

**Existing extraction pattern** (use the same expression — appears 3× in current source at lines 247, 266, 292):

```python
# Source: src/homelab_mcp/error_handling.py:247
hostname = kwargs.get("hostname", args[0] if args else "unknown")
```

**Existing envelope shape** (lines 248-263 — the timeout branch is the canonical shape; replicate on 4 other branches):

```python
# Source: src/homelab_mcp/error_handling.py:248-263 (current shape — Bug BB site)
error_response = json.dumps(
    {
        "status": "error",
        "connection_ip": hostname,  # ← already wired
        "error": f"SSH connection timeout after {effective_timeout} seconds",
        "error_type": "ssh_timeout",
        "suggestions": [...],
        "timestamp": datetime.now(UTC).isoformat(),
    },
    indent=2,
)
```

→ Add `"hostname": hostname,` as a sibling key. Apply uniformly to all five `json.dumps({...})` sites: lines 248-263 (TimeoutError), 269-278 (ConnectionError/timeout sub-branch), 280-289 (ConnectionError/general sub-branch), 296-305 (auth_error), 307-316 (general_error). One-line additions; no behavior change.

**Defensive note** for line 292: the existing extraction is `kwargs.get("hostname", "unknown")` (no `args[0]` fallback) — when fixing this site, normalize to the lines 247/266 form so all five envelopes carry the same fallback chain.

---

### MODIFY `src/homelab_mcp/drift_detection.py` (`_probe_one` body + scan_drift Proxmox row loop)

**Analog:** self. Two edits.

**Edit 1 — `_probe_one` SSH dial target** (lines 498-503 — Bug V on drift's side):

```python
# Source: src/homelab_mcp/drift_detection.py:497-503 (current — Bug V site)
creds = resolve_ssh_credentials(hostname, credential_id=binding)
async with await ssh_connect(
    hostname=creds.hostname,  # ← Bug V: dials creds.hostname, should be row.connection_ip
    username=creds.username,
    port=creds.port,
    password=creds.password,
    key_path=creds.key_path,
) as conn:
```

→ Either (a) compute `dial_target = row.get("connection_ip") or hostname` and pass it as `hostname=dial_target` to `ssh_connect`, or (b) refactor to use the new `resolve_ssh_for_sitemap_row` helper which returns the row alongside creds and apply the same dial-target derivation. Pitfall 4 guard: skip when `connection_ip` is empty / None / equal to input identifier.

**Edit 2 — scan_drift Proxmox row loop** (lines 758-763 — Bug V on Proxmox side):

```python
# Source: src/homelab_mcp/drift_detection.py:758-763 (current — Bug V site)
client = await get_proxmox_client(
    host=hostname,                 # ← passes row.hostname; should prefer row.connection_ip when truthy
    session=session,
    credential_id=binding,
)
```

→ Becomes `host=row.get("connection_ip") or hostname` (same Pitfall 4 guard). The `credential_id=binding` keyword is preserved per Phase 39.1 D-16 / `TestPhase39_1NoSkipInDriftEnum` (`tests/test_ast_regression.py:884-949`) — guard already locks it in.

**Per-iteration reset pattern** (already in place at lines 730-738 — preserve, do NOT regress):

```python
# Source: src/homelab_mcp/drift_detection.py:730-738 (Phase 39 WR-06)
# WR-06 (Phase 39 review): reset scope / cluster_name explicitly
# at the top of each iteration. Python doesn't scope variables
# to ``for`` blocks ...
scope: str = "unknown"
cluster_name: str | None = None
```

→ RESEARCH Anti-pattern 3 ("Caching the matched row across iteration") cites this. New code in the same loop body must not introduce variables that survive across iterations.

---

### NEW `tests/test_phase41_binding_aware.py`

**Analog:** `tests/test_drift_detection.py:21-80` (TestScanDrift4Bucket).

**Imports pattern** (mirror `tests/test_drift_detection.py:1-19`):

```python
# Source: tests/test_drift_detection.py:1-19
"""Tests for drift detection — Phase 36/37 ..."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homelab_mcp.drift_detection import (...)
from homelab_mcp.proxmox_api import CredentialNotFoundError
from homelab_mcp.ssh_tools import _probe_universal_core
```

**Core pattern — async test with MagicMock db_adapter + patch context manager** (`tests/test_drift_detection.py:37-77`):

```python
# Source: tests/test_drift_detection.py:37-77
@pytest.mark.asyncio
async def test_three_row_classification(self):
    db_adapter = MagicMock()
    db_adapter.get_all_devices.return_value = [
        {"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"},
        ...
    ]

    async def fake_get_client(host, *, session=None, credential_id=None):
        if host == "pve1":
            client = MagicMock()
            client.get = AsyncMock(return_value=[...])
            return client
        ...

    with (
        patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
        patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
    ):
        result = await scan_drift(session=None, db_adapter=db_adapter)

    assert result["status"] == "success"
    assert result["scanned"] == 3
```

**SSH-mock pattern** (mirror `tests/test_ssh_tools.py:24-55` for the helper unit tests):

```python
# Source: tests/test_ssh_tools.py:34-55
async def _fake_ssh_connect(**kwargs):
    class _Ctx:
        async def __aenter__(self_inner):
            return fake_conn
        async def __aexit__(self_inner, exc_type, exc, tb):
            return None
    return _Ctx()

monkeypatch.setattr(
    ssh_tools,
    "resolve_ssh_credentials",
    lambda hostname, username, password, key_path, port: SimpleNamespace(...),
)
monkeypatch.setattr(ssh_tools, "ssh_connect", _fake_ssh_connect)
```

**In-memory sqlite fixture** (mirror `tests/test_sitemap.py:16-25`):

```python
# Source: tests/test_sitemap.py:16-25
@pytest.fixture
def temp_db():
    yield ":memory:"

@pytest.fixture
def sitemap(temp_db):
    return NetworkSiteMap(db_path=temp_db, db_type="sqlite")
```

**Test cases to write** (per RESEARCH Phase Requirements → Test Map, lines 503-514):

| Test name | Asserts |
|-----------|---------|
| `test_discover_and_map_uses_row_binding_when_row_exists` | Row with `ssh_credential_id` set → resolver receives `credential_id=` keyword (Bug AA). |
| `test_helper_falls_back_when_no_row_matches` | Zero-row case: helper returns `(creds, None)`; resolver called without `credential_id`. |
| `test_helper_raises_on_ambiguous_match` | Two rows, neither status='success' → `CredentialNotFoundError`. |
| `test_helper_handles_unbound_row` | One row, `ssh_credential_id` is `None` → falls back to keyring scan, returns `(creds, row)`. |
| `test_helper_handles_empty_connection_ip` | One row, `connection_ip=""` → caller falls back to identifier (Pitfall 4). |
| `test_dial_target_uses_row_connection_ip` | Row with `connection_ip=192.168.10.20` + identifier `"pve"` → `ssh_connect` called with `hostname="192.168.10.20"` (Bug V). |
| `test_drift_dials_connection_ip_not_hostname` | scan_drift Proxmox path: `get_proxmox_client(host=..., credential_id=...)` called with `connection_ip` (Bug V on drift side). |
| `test_failed_discover_writes_to_requested_identifier_row` | Failed discovery + row exists for `"pve"` → upsert lands on the existing row, `device.hostname == "pve"` (Bug BB). |
| `test_failed_discover_does_not_collapse_to_empty_hostname` | Failed JSON decode + `requested_identifier="fakehost.local"` → no zombie `(hostname="", connection_ip="unknown")` row created. |
| `test_error_envelope_carries_hostname` | `ssh_connection_wrapper` error envelope includes `"hostname"` field (Bug BB at envelope layer). |

---

### MODIFY `tests/test_ast_regression.py` — add `TestPhase41BindingAwareResolver`

**Analog (primary):** `tests/test_ast_regression.py:1072-1196` — `TestPhase41_1KeyringHygiene` (the sibling phase, added 2026-04-29 in commit d1c398a). Mirror its allowlist + ast.walk shape.
**Analog (secondary):** `tests/test_ast_regression.py:853-983` — `TestPhase39_1NoSkipInDriftEnum`. Provides the **function-scoped** AST guard pattern + canonical-name pin against import aliasing + call-site floor sanity check.
**Analog (tertiary):** `tests/test_ast_regression.py:758-845` — `TestPhase381CredBinding`. Provides the `_probe_one`-style nested-function discovery (`ast.walk` + `FunctionDef | AsyncFunctionDef` filter).

**Class docstring shape** (mirror `TestPhase41_1KeyringHygiene` at lines 1072-1110):

```python
# Source: tests/test_ast_regression.py:1072-1110
class TestPhase41_1KeyringHygiene:
    """Phase 41.1 SC-2: any test that calls ``store_credential`` ...

    Scope (per threat model T-41.1-02 — precise carve-out):
      * Covers ONLY direct ``store_credential(...)`` ...
      * ``getattr(...)``-indirected calls ... are BLOCKED by the
        canonical-name pin in ``test_guarded_symbols_not_aliased_in_tests``.
      ...

    Threat model T-41.1-02 mitigation: deny-by-default. Allowlist
    entries must cite a fixture path or CONTEXT decision.
    """
```

**Allowlist + ast.walk pattern** (lines 1115-1195 — copy verbatim, swap symbols and target files):

```python
# Source: tests/test_ast_regression.py:1115-1195
_GUARDED_SYMBOLS = ("store_credential", "register_credential")
_ALLOWLIST: frozenset[str] = frozenset({
    "tests/conftest.py",
    "tests/test_credential_store.py",
    ...
})

def test_no_unprotected_credential_writes_in_tests(self) -> None:
    tests_root = Path(__file__).parent
    repo_root = tests_root.parent
    violations: list[str] = []
    for py_file in sorted(tests_root.rglob("*.py")):
        rel = py_file.relative_to(repo_root).as_posix()
        if rel in self._ALLOWLIST:
            continue
        ...
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in self._GUARDED_SYMBOLS
            ):
                violations.append(f"{rel}:{node.lineno} — {node.func.id}(...) in non-allowlisted file")
    assert not violations, ("Phase 41.1 SC-2: ..." + "\n  ".join(violations))
```

→ For Phase 41: `_GUARDED_SYMBOLS = ("resolve_ssh_credentials",)`; scan **`src/homelab_mcp/sitemap.py`** + **`src/homelab_mcp/drift_detection.py`** (not `tests/`). Allowlist holds the intentional bypass call sites (`ssh_tools.py` itself; `_probe_one` if it retains a direct call after refactor).

**Function-scoped AST + canonical-name pin** (mirror `tests/test_ast_regression.py:884-949` for the helper-existence + binding-thread checks):

```python
# Source: tests/test_ast_regression.py:884-949 — TestPhase39_1NoSkipInDriftEnum
def test_get_proxmox_client_calls_thread_credential_id_phase39_1(self) -> None:
    src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
    source = (src_root / "drift_detection.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="drift_detection.py")

    # Canonical-name pin (WR-03 mitigation — defeats import aliasing)
    imports = [
        a
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and (n.module or "").endswith("proxmox_api")
        for a in n.names
        if a.name == "get_proxmox_client"
    ]
    assert imports and all(a.asname is None for a in imports), "..."

    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "get_proxmox_client"
    ]
    violations = [c.lineno for c in calls if "credential_id" not in {kw.arg for kw in c.keywords}]
    assert not violations, "..."
```

→ For Phase 41: scan `sitemap.py` and `drift_detection.py` for direct `resolve_ssh_credentials(...)` calls outside the allowlist; pin `resolve_ssh_for_sitemap_row` as canonical (no aliasing); assert at least one call site uses the new helper (call-site floor — see below).

**Function-scoped target discovery** (mirror `tests/test_ast_regression.py:784-807` for the `discover_and_store` and `_probe_one` named-function lookup):

```python
# Source: tests/test_ast_regression.py:784-807
target = next(
    (
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == "scan_drift"
    ),
    None,
)
assert target is not None, "Phase 38.1 D-15: scan_drift not found ..."
```

→ For Phase 41: target names are `discover_and_store` (in `sitemap.py`) and `_probe_one` (nested inside `_bulk_universal_core_probes` in `drift_detection.py`). RESEARCH Pitfall 5 explicitly warns against the MCP-tool-name confusion (`discover_and_map` vs `discover_and_store`) — use the implementation name.

**Call-site floor pattern** (mirror `tests/test_ast_regression.py:951-983`):

```python
# Source: tests/test_ast_regression.py:951-983
def test_phase39_1_guard_call_site_floor(self) -> None:
    """Defensive sanity check: the guard ENUMERATES at least 2 call sites ..."""
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "get_proxmox_client"
    ]
    assert len(calls) >= 2, "..."
```

→ For Phase 41: assert `>= 2` direct callers of `resolve_ssh_for_sitemap_row` (one in `sitemap.py`, one in `drift_detection.py`) so a regression that drops one call site fails the floor instead of silently weakening the guard.

---

## Shared Patterns

### Sitemap row lookup
**Source:** `src/homelab_mcp/database.py:440-452` — `find_devices_by_hostname_or_ip`
**Apply to:** the new helper `resolve_ssh_for_sitemap_row`; the failure-path row reuse in `discover_and_store` (RESEARCH Pattern 3).
**Why this pattern:** Already exists, SQLite + Postgres parity, returns `list[dict]` with the right columns. Anti-pattern (RESEARCH §): **do NOT** add a new adapter method.

```python
# Already in tree — just call it:
db = get_database_adapter()
matched = db.find_devices_by_hostname_or_ip(identifier)  # OR-match across hostname AND connection_ip
```

### UUID-keyed credential resolution (Tier-0 short-circuit)
**Source:** `src/homelab_mcp/ssh_tools.py:95-303` — `resolve_ssh_credentials(..., credential_id=)`
**Apply to:** the new helper's binding-row branch (when `row["ssh_credential_id"]` is non-null).
**Why this pattern:** Phase 38.1 D-11/D-12/D-13/D-14 reason-hint logic lives here. RESEARCH Anti-pattern 2: **do NOT** duplicate the auth_type branching in the new helper — delegate.

```python
# Source: src/homelab_mcp/ssh_tools.py:95-103
def resolve_ssh_credentials(hostname, username=None, password=None, key_path=None, port=22, *, credential_id=None) -> SSHCredentials:
```

### CredentialNotFoundError shape with disambiguation pointer
**Source:** `src/homelab_mcp/ssh_tools.py:85-91` — multi-match raise inside `_resolve_username_from_registry`
**Apply to:** the new helper's multi-row case (RESEARCH Pattern 1, Pitfall 6).
**Why this pattern:** Existing tests already assert this error-class + message-shape contract.

```python
# Source: src/homelab_mcp/ssh_tools.py:85-91
raise CredentialNotFoundError(
    f"Multiple credentials registered for {hostname}: {registered}. "
    "Specify username explicitly, or call list_keyring_credentials "
    "to inspect registered entries."
)
```

### Per-iteration variable reset (drift row loop)
**Source:** `src/homelab_mcp/drift_detection.py:730-738` — Phase 39 WR-06 reset of `scope` / `cluster_name`.
**Apply to:** any new code in `_probe_one` or the scan_drift row loop that introduces row-scoped state.
**Why this pattern:** Python `for`-loop variable scoping leaks across iterations; explicit reset prevents previous-row attribution bugs (RESEARCH Anti-pattern 3).

### Async test with MagicMock + patch
**Source:** `tests/test_drift_detection.py:37-77` — TestScanDrift4Bucket
**Apply to:** all functional tests in `tests/test_phase41_binding_aware.py` that exercise `discover_and_store` or `scan_drift`.
**Why this pattern:** Project standard — `MagicMock` for db_adapter, `AsyncMock` for `client.get`, `patch(...)` context-manager grouping, `@pytest.mark.asyncio` decorator.

### AST guard with allowlist + canonical-name pin + call-site floor
**Source:** `tests/test_ast_regression.py:1072-1196` (allowlist scan) + `tests/test_ast_regression.py:884-983` (function-scoped + canonical-name pin + floor)
**Apply to:** `TestPhase41BindingAwareResolver` in `tests/test_ast_regression.py`.
**Why this pattern:** Five prior phases shipped this pattern (33.1, 35, 36, 38.1, 39.1, 41.1). Universally known mechanic. RESEARCH explicitly cites "mirror Phase 41.1's pattern."

---

## No Analog Found

**None.** Every file in this phase has a strong analog. RESEARCH says it directly: "Every primitive needed for the fix already exists. This is a wiring phase, not a building phase." (line 301).

---

## Metadata

**Analog search scope:** `src/homelab_mcp/{ssh_tools,sitemap,drift_detection,error_handling,database}.py` and `tests/{test_ast_regression,test_drift_detection,test_sitemap,test_ssh_tools,conftest}.py`.
**Files scanned:** 10 source/test files.
**Pattern extraction date:** 2026-04-29.
**Cross-references locked:** RESEARCH §"Architecture Patterns" / §"Code Examples" / §"Common Pitfalls" / §"Don't Hand-Roll" / §"Sources".
