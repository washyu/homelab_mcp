# Phase 39: Drift Detection Cases — Pattern Map

**Mapped:** 2026-04-27
**Files analyzed:** 5 (3 modified, 1 new fixture file, 1 modified test file)
**Analogs found:** 5 / 5 (all in-tree from Phases 35/36/37/38/38.1)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/homelab_mcp/drift_detection.py` (modified) | service | request-response + batch SSH/API | `src/homelab_mcp/drift_detection.py:124-372` (existing `scan_drift`) + `src/homelab_mcp/sitemap.py:466-542` (`bulk_discover_and_store`) | exact (in-place extension) |
| `src/homelab_mcp/ssh_tools.py` (modified — extract `_probe_universal_core`) | utility | request-response | `src/homelab_mcp/ssh_tools.py:614-691` (the four-probe block inside `ssh_discover_system`) | exact (lift verbatim) |
| `tests/test_drift_detection.py` (modified — add 5 test classes) | test | request-response | `tests/test_drift_detection.py:12-110` (`TestScanDrift4Bucket`) + `tests/test_drift_detection.py:821-1026` (`TestScanDriftNotEligible`) | exact |
| `tests/test_ast_regression.py` (modified — add `TestPhase39DriftCases`) | test (regression) | n/a — static AST walk | `tests/test_ast_regression.py:747-833` (`TestPhase381CredBinding`) | exact (carry-forward) |
| `tests/conftest.py` (NEW) | test fixture | n/a — pytest fixture providers | None in-tree (no tests/conftest.py exists today); closest cousin is per-file fixtures inside `tests/test_drift_detection.py` test methods | partial (new file, no shared-fixture analog) |

## Pattern Assignments

### `src/homelab_mcp/drift_detection.py` (service, request-response + batch)

**Analog:** `src/homelab_mcp/drift_detection.py` itself (Phase 38.1 baseline) + `src/homelab_mcp/sitemap.py:466-542` for the SSH bulk pre-pass shape.

**Imports pattern** (drift_detection.py:27-40 — existing; extend with new imports):
```python
import logging
from datetime import UTC, datetime
from typing import Any

import aiohttp

from .database import DatabaseAdapter
from .log_filter import sanitize_error
from .proxmox_api import (
    CredentialNotFoundError,
    _HOST_CLUSTER_CACHE,                # Phase 39 D-05: cluster de-dupe
    get_proxmox_client,
    get_resolution_telemetry,
    resolve_proxmox_credentials,
)
# Phase 39 ADDS:
from .ssh_connection import ssh_connect
from .ssh_tools import _probe_universal_core, resolve_ssh_credentials
```

**Per-row classification + reason-enum + human message pattern** (drift_detection.py:58-121 — verbatim template for new helpers):
```python
def _classify_credential_failure(exc: CredentialNotFoundError, binding: str | None) -> str:
    """Map (CredentialNotFoundError, binding-context) → reason enum (D-08)."""
    if binding is None:
        return "unbound"
    hint = getattr(exc, "reason_hint", None)
    if hint == "binding_stale":
        return "binding_stale"
    if hint == "keyring_desync":
        return "keyring_desync"
    logger.warning(...)
    return "binding_stale"


def _reason_message(reason: str, hostname: str, credential_type: str) -> str:
    """Human-readable message for the not_eligible bucket (D-08)."""
    if reason == "unbound":
        return (
            f"No {credential_type} credential bound; run "
            f"`homelab-mcp credentials add --type {credential_type} {hostname} <username>` "
            f"to bind."
        )
    # ... per-reason branches with command pointers ...
```

**Phase 39 mirror:** `_classify_unreachable(row, exc, threshold_days, now) -> tuple[Literal["unreachable", "missing"], str]` follows the same shape — pure compute, returns `(status_substate, message)`. `_drift_message(case, hostname, fields)` mirrors `_reason_message`. Both helpers contain NO loops over rows/VMs (D-11(b)).

**Existing single row-loop body** (drift_detection.py:225-339) — extend in-place, no new for-loops over `rows`:
```python
for row in rows:
    hostname = row.get("hostname")
    binding = row.get("proxmox_credential_id")  # Phase 38.1 R6

    # D-17: degenerate rows route to not_eligible (no continue — D-15 invariant).
    if hostname is None or hostname in ("", "unknown") or row.get("status") == "error":
        not_eligible.append({...})
    else:
        try:
            client = await get_proxmox_client(host=hostname, session=session, credential_id=binding)
        except CredentialNotFoundError as exc:
            reason = _classify_credential_failure(exc, binding)
            not_eligible.append({...})
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            unreachable.append({..., "status": "unreachable", "error": sanitize_error(exc)})
        else:
            telemetry = get_resolution_telemetry(hostname, binding)
            # ... resolve scope/cluster_name ...
            try:
                status = await client.get("/cluster/status")
                # PHASE 39 INSERT POINT: consult ssh_probe_results[hostname] →
                # call _diff_fingerprints(stored, current) → if non-empty:
                #     changed.append({...})
                # else:
                #     probed_ok.append({...})
            except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
                # PHASE 39: route to unreachable/missing per _classify_unreachable
                substatus, message = _classify_unreachable(row, exc, threshold, now)
                unreachable.append({..., "status": substatus, "last_seen": ..., "message": message})
```

**Bucket-shape pattern (existing — gain `status: "missing"` and `last_seen` per D-01)** (drift_detection.py:266-276 + 329-339):
```python
unreachable.append(
    {
        "hostname": hostname,
        "connection_ip": row.get("connection_ip", ""),
        "scope": scope,
        "cluster_name": cluster_name,
        "status": "unreachable",          # PHASE 39: also "missing" per D-01
        "error": sanitize_error(exc),
        "scan_timestamp": scan_timestamp,
        # PHASE 39 ADDS when status == "missing":
        # "last_seen": row.get("last_seen"),
        # "message": "...recovery pointer to decommission_device / purge_failed_discoveries...",
    }
)
```

**Counts + envelope locked-key-order pattern** (drift_detection.py:341-372 — preserve verbatim):
```python
counts: dict[str, int] = {
    "probed_ok": len(probed_ok),
    "unreachable": len(unreachable),
    "not_eligible": len(not_eligible),
    "unknown": len(unknown),     # Phase 39: NOW populated
    "changed": len(changed),     # Phase 39: NOW populated
}
scanned = sum(counts.values())

response: dict[str, Any] = {
    "status": "success",
    "scan_timestamp": scan_timestamp,
    "scanned": scanned,
    "counts": counts,
}
if scanned == 0:
    response["guidance"] = _EMPTY_SCAN_GUIDANCE
response["probed_ok"] = probed_ok
response["unreachable"] = unreachable
response["not_eligible"] = not_eligible
response["unknown"] = unknown
response["changed"] = changed
return response
```

**Bulk SSH pre-pass pattern (Semaphore + gather)** — analog: `src/homelab_mcp/sitemap.py:466-542` (`bulk_discover_and_store`):
```python
# Source: sitemap.py:466-542 — Phase 35 D-07 template
async def bulk_discover_and_store(sitemap, targets):
    semaphore = asyncio.Semaphore(10)   # bounded fanout

    async def _discover_one(target):
        async with semaphore:
            try:
                result = await discover_and_store(...)
                return json.loads(result)
            except Exception as e:
                return {"status": "error", "error": sanitize_error(e)}

    raw_results = await asyncio.gather(
        *[_discover_one(t) for t in targets],
        return_exceptions=True,
    )
```

**Phase 39 mirror** (`_bulk_universal_core_probes(rows) -> dict[hostname, probe_result]`):
- Per-scan `Semaphore(10)` instance (NOT module-level — see `Claude's Discretion` lock).
- Inner `_probe_one(row)` returns `(hostname, probe_dict_or_error_dict)`.
- Outer `asyncio.gather(*[_probe_one(r) for r in rows if r.get("ssh_credential_id")])`.
- Each per-host probe wrapped in `asyncio.wait_for(_probe_universal_core(conn, []), timeout=45.0)` (Pitfall 3 outer-bound).
- Catches `(asyncssh.Error, OSError, TimeoutError, ValueError)`; sanitizes via `sanitize_error()`.

**Cluster `/cluster/resources` enumeration pattern** — analog: `src/homelab_mcp/proxmox_api.py:540-574`:
```python
client = await get_proxmox_client(host=host, session=session)
try:
    resources = await client.get("/cluster/resources")
    if resource_type:
        resources = [r for r in resources if r.get("type") == resource_type]
    return {"status": "success", "total": len(resources), "resources": resources}
except (aiohttp.ClientError, ValueError) as e:
    logger.error("Error listing Proxmox resources: %s", str(e))
    return {"status": "error", "message": f"Failed to list resources: {sanitize_error(e)}"}
```

**Phase 39 mirror** (`_enumerate_proxmox_vms(probed_ok_hosts, session) -> dict[cluster_key, list[vm]]`):
- Filter `resources` by `type in ("qemu", "lxc")` (drop nodes/storage/etc.).
- De-dupe by `cluster_name` from `_HOST_CLUSTER_CACHE` BEFORE issuing calls (single comprehension; no `continue`):
  ```python
  targets = list({(c or h): (h, c) for h, c in probed_ok_hosts}.values())
  ```
- Enumeration failure → log debug + return empty list for that hypervisor (host stays in `probed_ok` per Open Question 4).

**Diff helper pattern** (RESEARCH.md Pattern 2 — recursive walk):
```python
def _diff_fingerprints(stored: dict, current: dict) -> dict[str, dict]:
    """D-08: per-leaf diffs with dotted-path keys; D-09a: only leaves present in BOTH."""
    diffs: dict[str, dict] = {}

    def _walk(s: Any, c: Any, path: list[str]) -> None:
        if isinstance(s, dict) and isinstance(c, dict):
            for k in s.keys() & c.keys():     # leaf-level "present in both"
                _walk(s[k], c[k], path + [k])
        else:
            if s != c:
                diffs[".".join(path)] = {"stored": s, "current": c}

    _walk(stored, current, [])
    return diffs
```

**Env-var clamp pattern** (RESEARCH.md Code Examples — `_missing_threshold_days`):
```python
_DEFAULT_THRESHOLD_DAYS = 7

def _missing_threshold_days() -> int:
    raw = os.getenv("HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS", str(_DEFAULT_THRESHOLD_DAYS))
    try:
        v = int(raw)
        return v if v > 0 else _DEFAULT_THRESHOLD_DAYS
    except ValueError:
        return _DEFAULT_THRESHOLD_DAYS
```

**Last-seen parse + UTC-normalize pattern** (RESEARCH.md Pitfall 4):
```python
def _parse_last_seen(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
```

---

### `src/homelab_mcp/ssh_tools.py` (utility, request-response — extract helper)

**Analog:** `src/homelab_mcp/ssh_tools.py:614-691` — the in-line four-probe block inside `ssh_discover_system`. Lift VERBATIM into a standalone helper; replace the original site with a call to the helper.

**Existing four-probe block** (ssh_tools.py:614-691 — extract into `_probe_universal_core`):
```python
fingerprint_info: dict[str, Any] = {}

uname_s_result = await _run_with_timeout(conn, "uname -s", cmd_name="uname-s", timed_out=timed_out_commands)
if uname_s_result and uname_s_result.exit_status == 0 and uname_s_result.stdout:
    fingerprint_info["kernel_name"] = cast(str, uname_s_result.stdout).strip()
elif uname_s_result is not None and uname_s_result.exit_status != 0:
    if "uname-s" not in timed_out_commands:
        timed_out_commands.append("uname-s")

uname_r_result = await _run_with_timeout(conn, "uname -r", cmd_name="uname-r", timed_out=timed_out_commands)
if uname_r_result and uname_r_result.exit_status == 0 and uname_r_result.stdout:
    fingerprint_info["kernel_version"] = cast(str, uname_r_result.stdout).strip()
elif uname_r_result is not None and uname_r_result.exit_status != 0:
    if "uname-r" not in timed_out_commands:
        timed_out_commands.append("uname-r")

os_release_result = await _run_with_timeout(
    conn,
    "cat /etc/os-release 2>/dev/null",
    cmd_name="os-release-full",
    timed_out=timed_out_commands,
)
if os_release_result and os_release_result.exit_status == 0 and os_release_result.stdout:
    parsed: dict[str, str] = {}
    for line in cast(str, os_release_result.stdout).splitlines():
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    if parsed.get("PRETTY_NAME"):
        fingerprint_info["os_name"] = parsed["PRETTY_NAME"]
    elif parsed.get("NAME"):
        fingerprint_info["os_name"] = parsed["NAME"]
    if parsed.get("VERSION_ID"):
        fingerprint_info["os_version"] = parsed["VERSION_ID"]
elif os_release_result is not None and os_release_result.exit_status != 0:
    if "os-release-full" not in timed_out_commands:
        timed_out_commands.append("os-release-full")

dpkg_result = await _run_with_timeout(
    conn,
    "LC_ALL=C dpkg -l 2>/dev/null | sort | sha256sum",
    cmd_name="dpkg-fingerprint",
    timed_out=timed_out_commands,
)
if dpkg_result is not None and dpkg_result.exit_status == 0 and dpkg_result.stdout:
    digest_field = cast(str, dpkg_result.stdout).strip().split()[0]
    if digest_field and digest_field != "d41d8cd98f00b204e9800998ecf8427e":
        fingerprint_info["package_fingerprint"] = f"sha256:{digest_field}"
elif dpkg_result is not None and dpkg_result.exit_status != 0:
    if "dpkg-fingerprint" not in timed_out_commands:
        timed_out_commands.append("dpkg-fingerprint")

if fingerprint_info:
    system_info["fingerprint"] = fingerprint_info
```

**Phase 39 extraction shape:**
```python
async def _probe_universal_core(
    conn: asyncssh.SSHClientConnection,
    timed_out_commands: list[str],
) -> dict[str, Any]:
    """Phase 38 D-04 universal-core fingerprint probes (kernel/OS/package).

    Reused by Phase 39 drift detection. All four probes wrapped in
    ``_run_with_timeout(10s)`` per Phase 35 D-05; non-zero exits enroll
    cmd_name into ``timed_out_commands`` so callers can flag ``partial: True``.

    Returns the four-key fingerprint dict (kernel_name, kernel_version,
    os_name, os_version, package_fingerprint) — possibly partial when commands
    fail or time out. Empty dict if no probe yielded a value.
    """
    fingerprint_info: dict[str, Any] = {}
    # ... lift lines 614-691 verbatim, replacing `system_info["fingerprint"]`
    # assignment with `return fingerprint_info` ...
    return fingerprint_info
```

**`_run_with_timeout` wrapper pattern** (ssh_tools.py:863-889 — UNCHANGED, used by extracted helper):
```python
async def _run_with_timeout(
    conn: asyncssh.SSHClientConnection,
    command: str,
    *,
    cmd_name: str,
    timed_out: list[str],
    timeout: float = 10.0,
) -> "asyncssh.SSHCompletedProcess | None":
    try:
        return await asyncio.wait_for(conn.run(command, check=False), timeout=timeout)
    except TimeoutError:
        logger.debug(...)
        timed_out.append(cmd_name)
        return None
```

**AST guard scope (Pitfall 7):** The Phase 35 AST guard at `tests/test_ast_regression.py:447-502` (`test_ssh_discover_system_wraps_every_conn_run_phase35`) targets **only** `ssh_discover_system` (line 466: `n.name == "ssh_discover_system"`). The new sibling `_probe_universal_core` is OUT of that guard's scope, but its body MUST still wrap every `conn.run(...)` in `_run_with_timeout` — which it does, because we lift the wrapped calls verbatim. The guard does NOT need to be extended.

---

### `tests/test_drift_detection.py` (test, request-response)

**Analog:** `tests/test_drift_detection.py:12-110` (`TestScanDrift4Bucket`) for happy-path mock structure; `tests/test_drift_detection.py:821-1026` (`TestScanDriftNotEligible`) for routing-regression test class shape.

**Test class header pattern** (test_drift_detection.py:12-22):
```python
class TestScanDrift4Bucket:
    """Phase 37 D-01/D-02/D-04/D-05/D-07/D-09/D-10: scan_drift 4-bucket envelope.

    Combines Phase 36's 2-bucket sanity tests (preserved verbatim) with Phase 37's
    envelope/filter/guidance regression tests. ...
    """
```

**Phase 39 mirrors** — five new test classes, each with the same docstring shape (decision IDs + 1-line summary):
- `TestPhase39Helpers` — unit tests for `_diff_fingerprints`, `_enumerate_unknown_vms`, `_classify_unreachable`, `_parse_last_seen`, `_missing_threshold_days`.
- `TestPhase39Unknown` — DRFT-17 functional tests.
- `TestPhase39Missing` — DRFT-18 functional tests.
- `TestPhase39Changed` — DRFT-19 functional tests.
- `TestPhase39Bucket` — D-10 invariants (`scanned == sum(counts.values())`, mutual exclusivity).

**Imports pattern** (test_drift_detection.py:1-9):
```python
"""Tests for drift detection — Phase 36/37/38.1/39."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homelab_mcp.drift_detection import scan_drift
from homelab_mcp.proxmox_api import CredentialNotFoundError
```

**Phase 39 ADDS:**
```python
from homelab_mcp.drift_detection import (
    _classify_unreachable,
    _diff_fingerprints,
    _enumerate_unknown_vms,
    _missing_threshold_days,
    _parse_last_seen,
)
```

**Test method pattern — async + mocked db_adapter + patched resolver chain** (test_drift_detection.py:28-87):
```python
@pytest.mark.asyncio
async def test_three_row_classification(self):
    """3-row sitemap: pve1 -> probed_ok, truenas1 -> not_eligible/unbound, pi-lab -> unreachable."""
    db_adapter = MagicMock()
    db_adapter.get_all_devices.return_value = [
        {"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"},
        {"hostname": "truenas1", "connection_ip": "10.0.0.11", "status": "success"},
        {"hostname": "pi-lab", "connection_ip": "10.0.0.12", "status": "success"},
    ]

    async def fake_get_client(host, *, session=None, credential_id=None):
        if host == "pve1":
            client = MagicMock()
            client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
            return client
        if host == "truenas1":
            raise CredentialNotFoundError(f"no creds for {host}")
        if host == "pi-lab":
            client = MagicMock()
            client.get = AsyncMock(side_effect=aiohttp.ClientError("connection refused"))
            return client
        raise AssertionError(f"unexpected host: {host}")

    async def fake_resolve(host, session=None, *, credential_id=None):
        if host == "pve1":
            return ("token@node", "node", None)
        if host == "pi-lab":
            return ("token@cluster", "cluster", "homelab-prod")
        raise AssertionError(f"unexpected host: {host}")

    with (
        patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
        patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
    ):
        result = await scan_drift(session=None, db_adapter=db_adapter)

    assert result["status"] == "success"
    assert result["scanned"] == 3
    assert len(result["probed_ok"]) == 1
    # ... per-bucket assertions ...
```

**Phase 39 mirrors:** Each test method patches the relevant call sites:
- For DRFT-17 (`unknown[]`): also patch `client.get("/cluster/resources")` to return mocked VM list.
- For DRFT-18 (`missing`): seed `last_seen` in the row dict; patch `client.get("/cluster/status")` with `aiohttp.ClientError`.
- For DRFT-19 (`changed`): seed `fingerprint` in the row dict; patch `homelab_mcp.drift_detection.ssh_connect` and `homelab_mcp.drift_detection.resolve_ssh_credentials` to return mock probe results.

**Routing-regression test class pattern** (test_drift_detection.py:821-859):
```python
class TestScanDriftNotEligible:
    """Phase 38.1 D-18: routing-semantics regression.

    Companion to the AST guard (D-15): the AST guard catches structural
    regressions (a stray ``continue``); this class catches semantic regressions
    (rows landing in the wrong bucket).
    """

    @pytest.mark.asyncio
    async def test_unbound_row_routes_to_not_eligible(self) -> None:
        """Row with NULL proxmox_credential_id + no cluster cred → not_eligible/unbound."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {
                "hostname": "pve1",
                "connection_ip": "10.0.0.10",
                "status": "success",
                "proxmox_credential_id": None,
                "ssh_credential_id": None,
            },
        ]

        async def fake_get_client(host, *, session=None, credential_id=None):
            raise CredentialNotFoundError(f"No Proxmox credentials found for {host}.")

        with patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["status"] == "success"
        assert len(result["probed_ok"]) == 0
        assert result["counts"]["not_eligible"] == 1
        assert result["not_eligible"][0]["hostname"] == "pve1"
```

---

### `tests/test_ast_regression.py` (test, regression — add `TestPhase39DriftCases`)

**Analog:** `tests/test_ast_regression.py:747-833` (`TestPhase381CredBinding`) — exact carry-forward template.

**Existing AST guard pattern** (test_ast_regression.py:763-806):
```python
def test_scan_drift_no_continue_in_row_loop_phase38_1(self) -> None:
    """Phase 38.1 D-15: no ``continue`` in scan_drift row loop.

    The for-loop body must route EVERY row into one of the five buckets.
    A bare ``continue`` is the original Bug O shape (silent skip).
    """
    src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
    source = (src_root / "drift_detection.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="drift_detection.py")

    target = next(
        (
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
            and n.name == "scan_drift"
        ),
        None,
    )
    assert target is not None, (
        "Phase 38.1 D-15: scan_drift not found in drift_detection.py "
        "(if you renamed the function, update this guard)"
    )

    # Find the row-iter for-loop ("for row in rows:")
    row_loops = [
        n for n in ast.walk(target)
        if isinstance(n, ast.For)
        and isinstance(n.target, ast.Name)
        and n.target.id == "row"
    ]
    assert len(row_loops) == 1, (
        f"Phase 38.1 D-15: expected one `for row in rows:` loop in scan_drift, "
        f"found {len(row_loops)}. If you intentionally split the loop, update "
        f"this guard's row-loop discovery shape."
    )

    violations = [
        n.lineno for n in ast.walk(row_loops[0]) if isinstance(n, ast.Continue)
    ]
    assert not violations, (
        f"Phase 38.1 D-15 regression — `continue` reappeared in scan_drift row "
        f"loop at line(s): {violations}. ..."
    )
```

**Phase 39 mirror** — `TestPhase39DriftCases`:
```python
class TestPhase39DriftCases:
    """Phase 39 D-11/D-12: helpers added in Phase 39 stay loop-free.

    Recommended path D-11(b): rather than extending an allowlist, the new
    helpers (`_diff_fingerprints`, `_enumerate_unknown_vms`,
    `_classify_unreachable`) are written without `continue` inside any loop
    body that appends to a bucket-shaped list. This keeps the AST guard
    scope unchanged from Phase 38.1.
    """

    PHASE_39_NEW_HELPERS = (
        "_diff_fingerprints",
        "_enumerate_unknown_vms",
        "_classify_unreachable",
    )

    def test_phase39_helpers_no_continue(self) -> None:
        """Each new helper has zero `ast.Continue` nodes (D-11(b))."""
        src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
        source = (src_root / "drift_detection.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename="drift_detection.py")

        for helper_name in self.PHASE_39_NEW_HELPERS:
            target = next(
                (n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
                 and n.name == helper_name),
                None,
            )
            assert target is not None, (
                f"Phase 39 D-11: helper {helper_name!r} not found in drift_detection.py"
            )
            violations = [n.lineno for n in ast.walk(target) if isinstance(n, ast.Continue)]
            assert not violations, (
                f"Phase 39 D-11 regression — `continue` in {helper_name} at line(s): "
                f"{violations}. Recommended: refactor to comprehension or early-return."
            )
```

**Critical:** the existing `test_scan_drift_no_continue_in_row_loop_phase38_1` test must STILL PASS after Phase 39 changes — Phase 39 must not introduce a `continue` into `scan_drift`'s row loop. Wave 0 keeps this guard green.

---

### `tests/conftest.py` (NEW — pytest fixtures)

**Analog:** None in-tree. Per-method local fixtures inside `tests/test_drift_detection.py:36-54` are the closest cousin; promote those into shared fixtures.

**Imports pattern** (lift from test_drift_detection.py:1-10):
```python
"""Shared pytest fixtures for the homelab MCP test suite.

Phase 39 introduces this conftest as drift tests gain enough shared mock
machinery (universal-core probe responses, /cluster/resources fixtures,
freeze_now) to justify pulling them out of per-method definitions.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
```

**Fixture shapes** (synthesized from the existing per-method patterns + RESEARCH.md fixture table at lines 696-708):

```python
@pytest.fixture
def freeze_now(monkeypatch):
    """Freeze datetime.now(UTC) inside drift_detection to a fixed instant.

    Returns the frozen datetime so tests can compute relative last_seen values.
    """
    frozen = datetime(2026, 4, 27, 12, 0, 0, tzinfo=UTC)

    class _FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return frozen if tz is not None else frozen.replace(tzinfo=None)

    monkeypatch.setattr("homelab_mcp.drift_detection.datetime", _FakeDatetime)
    return frozen


@pytest.fixture
def mock_universal_core_probe_response():
    """Stable baseline universal-core fingerprint (matches sitemap_row_with_stored_fingerprint)."""
    return {
        "kernel_name": "Linux",
        "kernel_version": "6.5.13-1-pve",
        "os_name": "Proxmox VE",
        "os_version": "8.2.4",
        "package_fingerprint": "sha256:abc123",
    }


@pytest.fixture
def mock_universal_core_probe_drifted():
    """Probe response with kernel_version differing from baseline (DRFT-19 fixture)."""
    return {
        "kernel_name": "Linux",
        "kernel_version": "6.8.4-2-pve",   # CHANGED
        "os_name": "Proxmox VE",
        "os_version": "8.2.4",
        "package_fingerprint": "sha256:def456",   # CHANGED
    }


@pytest.fixture
def mock_cluster_resources_response():
    """Mock /cluster/resources payload with two VMs; one matches a sitemap row."""
    return [
        {"type": "qemu", "vmid": 100, "node": "pve1", "name": "ubuntu-prod", "status": "running"},
        {"type": "qemu", "vmid": 110, "node": "pve1", "name": "ubuntu-test", "status": "running"},
        {"type": "lxc", "vmid": 200, "node": "pve1", "name": "pi-hole", "status": "running"},
        {"type": "node", "node": "pve1", "name": "pve1"},      # filtered out (not a VM/LXC)
    ]


@pytest.fixture
def sitemap_row_old_last_seen(freeze_now):
    """Sitemap row with last_seen 12 days before frozen now (>7d threshold default)."""
    return {
        "hostname": "pi-lab",
        "connection_ip": "10.0.0.12",
        "status": "success",
        "ssh_credential_id": "11111111-1111-1111-1111-111111111111",
        "proxmox_credential_id": None,
        "last_seen": (freeze_now.replace(tzinfo=None) - timedelta(days=12)).isoformat(),
        "fingerprint": {},
    }


@pytest.fixture
def sitemap_row_recent_last_seen(freeze_now):
    """Sitemap row with last_seen 1 day before frozen now (within threshold)."""
    return {
        "hostname": "pi-lab",
        "connection_ip": "10.0.0.12",
        "status": "success",
        "ssh_credential_id": "11111111-1111-1111-1111-111111111111",
        "proxmox_credential_id": None,
        "last_seen": (freeze_now.replace(tzinfo=None) - timedelta(days=1)).isoformat(),
        "fingerprint": {},
    }


@pytest.fixture
def sitemap_row_with_stored_fingerprint(mock_universal_core_probe_response):
    """Sitemap row with full Phase 38 fingerprint blob including capabilities."""
    return {
        "hostname": "pve1",
        "connection_ip": "10.0.0.10",
        "status": "success",
        "ssh_credential_id": "22222222-2222-2222-2222-222222222222",
        "proxmox_credential_id": "33333333-3333-3333-3333-333333333333",
        "last_seen": "2026-04-26T10:00:00",
        "fingerprint": {
            **mock_universal_core_probe_response,
            "capabilities": {"vulkan": {"available": True}},
        },
    }


@pytest.fixture
def mock_resolve_ssh_credentials():
    """Patch helper for homelab_mcp.drift_detection.resolve_ssh_credentials."""
    creds = MagicMock()
    creds.hostname = "10.0.0.12"
    creds.username = "mcp_admin"
    creds.port = 22
    creds.password = None
    creds.key_path = "/tmp/fake-key"
    return creds


@pytest.fixture
def mock_ssh_connect():
    """Async context manager mock for homelab_mcp.drift_detection.ssh_connect."""
    conn = MagicMock()
    conn.run = AsyncMock(return_value=MagicMock(exit_status=0, stdout="Linux"))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm
```

---

## Shared Patterns

### Authentication / Credential Resolution
**Source:** `src/homelab_mcp/proxmox_api.py:219-262` + `src/homelab_mcp/ssh_tools.py:95-163`
**Apply to:** All drift-side credential calls (Proxmox + SSH)

```python
# Phase 38.1 R6: keyword-only credential_id parameter
client = await get_proxmox_client(
    host=hostname,
    session=session,
    credential_id=row.get("proxmox_credential_id"),
)

creds = resolve_ssh_credentials(
    hostname,
    credential_id=row.get("ssh_credential_id"),
)
```

**Critical:** never bypass with env vars; never hardcode usernames; let resolver chain (Tier-0 UUID → Tier-1 explicit → Tier-2 keyring) decide. CredentialNotFoundError carries `.reason_hint` for `_classify_credential_failure` to map.

### Error Sanitization
**Source:** `src/homelab_mcp/log_filter.py:64-` (`sanitize_error`)
**Apply to:** Every `unreachable[].error`, `unreachable[].message` (when missing), every catch-and-log site
**Existing precedents in drift_detection.py:** lines 273, 336

```python
except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
    unreachable.append({
        ...,
        "error": sanitize_error(exc),     # Phase 36 D-02 invariant
    })
```

For SSH probe errors, also sanitize:
```python
except (asyncssh.Error, OSError, TimeoutError, ValueError) as exc:
    return (hostname, {"_error": sanitize_error(exc)})
```

### Per-Probe SSH Timeout Wrapping
**Source:** `src/homelab_mcp/ssh_tools.py:863-889` (`_run_with_timeout`)
**Apply to:** Every `conn.run(...)` call inside `_probe_universal_core`
**Existing AST guard:** `tests/test_ast_regression.py:447-502` — scoped to `ssh_discover_system` only; new helper inherits the pattern but is OUT of guard scope

```python
result = await _run_with_timeout(
    conn,
    "uname -r",
    cmd_name="uname-r",
    timed_out=timed_out_commands,
)
```

### Bucket-Append No-Continue Invariant
**Source:** `src/homelab_mcp/drift_detection.py:225-339` (existing single row-loop)
**Apply to:** `scan_drift` body + every Phase 39 helper
**Enforced by:** `tests/test_ast_regression.py:763-806` (existing) + new `TestPhase39DriftCases::test_phase39_helpers_no_continue`

Pattern: route every row into exactly one bucket via if/elif/else + try/except chain. NO `continue`. NO `return` mid-loop (function continues processing other rows).

### Cluster Cache De-Dupe
**Source:** `src/homelab_mcp/proxmox_api.py:22, 33, 36` (`_HOST_CLUSTER_CACHE`, `get_resolution_telemetry`)
**Apply to:** `_enumerate_proxmox_vms` pre-pass — group `probed_ok` Proxmox hosts by `cluster_name` so each cluster gets ONE `/cluster/resources` call

```python
# Loop-free de-dupe via dict comprehension (D-11(b) preserves AST guard cleanliness):
targets = list({(c or h): (h, c) for h, c in probed_ok_hosts}.values())
```

### Mocked Resolver + Mocked Client Test Pattern
**Source:** `tests/test_drift_detection.py:43-67` (`fake_get_client` + `fake_resolve` + `with patch(...)`)
**Apply to:** Every Phase 39 functional test

```python
async def fake_get_client(host, *, session=None, credential_id=None):
    if host == "pve1":
        client = MagicMock()
        client.get = AsyncMock(return_value=[...])
        return client
    raise CredentialNotFoundError(...)

with (
    patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
    patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
):
    result = await scan_drift(session=None, db_adapter=db_adapter)
```

For DRFT-19 (changed), also patch:
```python
with patch("homelab_mcp.drift_detection.ssh_connect", return_value=mock_ssh_connect), \
     patch("homelab_mcp.drift_detection.resolve_ssh_credentials", return_value=mock_resolve_ssh_credentials), \
     patch("homelab_mcp.drift_detection._probe_universal_core",
           AsyncMock(return_value=mock_universal_core_probe_drifted)):
    ...
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/conftest.py` | test fixture | n/a | No `tests/conftest.py` exists today; per-method MagicMock setup at `tests/test_drift_detection.py:36-54` is the only nearby precedent. Phase 39 introduces it; planner should not over-design — keep it scoped to drift fixtures, not a tree-wide harness rewrite. |

All other Phase 39 surfaces have exact in-tree analogs; the phase is a composition exercise.

## Metadata

**Analog search scope:** `src/homelab_mcp/`, `tests/`
**Files scanned:** ~14 source files + 2 test files (drift_detection.py, ssh_tools.py, sitemap.py, proxmox_api.py, ssh_connection.py, log_filter.py, error_handling.py, database.py, test_drift_detection.py, test_ast_regression.py)
**Pattern extraction date:** 2026-04-27
