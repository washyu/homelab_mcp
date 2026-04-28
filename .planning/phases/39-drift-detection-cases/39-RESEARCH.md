# Phase 39: Drift Detection Cases — Research

**Researched:** 2026-04-27
**Domain:** Async Python (3.12+) drift detection — extends `scan_drift` to populate `unknown[]` (DRFT-17), `unreachable[]` with `status: "missing"` (DRFT-18), and `changed[]` (DRFT-19) buckets via Proxmox `/cluster/resources` enumeration + bulk SSH universal-core probes.
**Confidence:** HIGH (all patterns/libraries already in-tree from Phases 35/36/37/38/38.1; no new dependencies; Proxmox API + asyncssh + asyncio.Semaphore stack reused verbatim)

## Summary

Phase 39 fills the three placeholder bucket paths in `scan_drift` that Phase 38.1 left at `[]`. All foundation work is in place: the 5-bucket envelope + `not_eligible` routing (38.1), the universal-core fingerprint schema in `devices.fingerprint` JSON column (38), `_HOST_CLUSTER_CACHE` and resolution telemetry (proxmox_api.py:22, 33), `_run_with_timeout(10s)` wrapping (ssh_tools.py:863), `Semaphore(10) + asyncio.gather` bulk pattern (sitemap.py:466), and the per-row classification + reason-enum helper template in drift_detection.py:58-121. Phase 39 layers on three concerns: (a) one `/cluster/resources` enumeration pre-pass per cluster_name; (b) one bulk SSH universal-core probe pre-pass across all rows with `ssh_credential_id`; (c) a `_diff_fingerprints` helper that walks stored vs current emitting dict-of-dicts diffs with dotted-path keys.

The CONTEXT.md decisions D-01..D-12 are tight; almost every "Claude's Discretion" recommendation in CONTEXT lines up with established codebase patterns. The two genuine planning choices are: (1) extract `_probe_universal_core(conn, timed_out_commands) -> dict` from `ssh_discover_system` (lines 614-691) and call it from both sites; (2) implement helpers as pure functions returning per-row decisions so `scan_drift` appends inside its existing single-loop body (D-11(b)) — preserves the AST guard without an allowlist extension.

**Primary recommendation:** Add a single SSH probe pre-pass and a single VM enumeration pre-pass before the existing `for row in rows:` loop in `scan_drift`. Keep the helpers loop-free (D-11(b)). Use `Semaphore(10)` per scan instance. The `changed`/`probed_ok` decision is a per-row diff applied inside the existing loop; `unknown[]` is populated entirely from the enumeration pre-pass, independent of the row loop.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DRFT-17 | `scan_infrastructure_drift` detects **unknown infrastructure** — VMs/LXC present on a Proxmox hypervisor but absent from sitemap (manually-created VM case) | `/cluster/resources` enumeration via existing `proxmox_api.py:557`; per-cluster de-dupe via `_HOST_CLUSTER_CACHE` (proxmox_api.py:22); per-VM rows in `unknown[]` per D-07 with case-insensitive `vm.name == sitemap.hostname` match (D-06) |
| DRFT-18 | `scan_infrastructure_drift` detects **missing infrastructure** — sitemap rows reachable previously but no longer responding past threshold | Read `last_seen` from `get_all_devices()` (already top-level per Phase 38 D-10); env `HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS` default 7; promote `unreachable` → `status: "missing"` in same bucket per D-01 |
| DRFT-19 | `scan_infrastructure_drift` detects **changed infrastructure** — live universal-core fingerprint differs from stored | Reuse Phase 38 probes (uname -s/-r, /etc/os-release, dpkg-fingerprint at ssh_tools.py:614-691); extract `_probe_universal_core` helper; compare to stored `row["fingerprint"]` via dotted-path diff per D-08 + D-09a |
</phase_requirements>

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Missing-bucket placement (DRFT-18)**
- **D-01:** `missing` is **NOT a 6th bucket**. Promoted rows stay in `unreachable[]` with `status: "missing"` (instead of `"unreachable"`). Phase 38.1's 5-bucket envelope (`probed_ok` / `unreachable` / `not_eligible` / `unknown` / `changed`) stays intact. Per-row record gains `last_seen` + a recovery pointer (`decommission_device` or `purge_failed_discoveries`) when `status == "missing"`.
- **D-02:** Threshold for unreachable→missing promotion is configurable via env var `HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS`, default `7`. Sourced from the existing `devices.last_seen` column — no new persistence, no consecutive-failure tracking. Logic: `if (now - last_seen).days > threshold and probe failed: status = "missing"`. Otherwise `status = "unreachable"`.

**Probe strategy for missing/changed (DRFT-18 + DRFT-19)**
- **D-03:** Drift probes the **universal-core fingerprint only** inline — three SSH commands per host: `uname -s`, `uname -r`, `cat /etc/os-release`, `dpkg -l 2>/dev/null | sort | sha256sum`. Same probes as Phase 38 D-04 (re-used, not duplicated). Each wrapped with `_run_with_timeout(conn, ..., timed_out=timed_out_commands)`. Capability re-probing is **NOT** in drift's scope.
- **D-04:** Drift SSH-probes **all sitemap rows with `ssh_credential_id` bound** — not just Proxmox hosts. Rows without `ssh_credential_id` route to `not_eligible` with `reason="unbound"`. A Proxmox host bound by BOTH `ssh_credential_id` AND `proxmox_credential_id` runs both probes.
- **D-04a:** Bulk SSH probes use `Semaphore(10) + asyncio.gather` per Phase 35 D-02. Outer scan timeout follows Phase 35's 120s ceiling.
- **D-04b:** Drift does NOT update the stored fingerprint after probing. Locked at REQUIREMENTS.md §Out of Scope.

**Unknown VM enumeration (DRFT-17)**
- **D-05:** VM enumeration uses **`/cluster/resources` once per probed_ok Proxmox host**. Per-node `/nodes/{node}/qemu` + `/nodes/{node}/lxc` fallback only when `/cluster/resources` returns an error indicating standalone (non-cluster) Proxmox setup. Cluster-scope rows that share a single Proxmox cluster get one enumeration call total per scan (de-dupe by cluster_name from `_HOST_CLUSTER_CACHE`).
- **D-06:** VM-in-sitemap match key is **case-insensitive `VM.name == sitemap.hostname`**. Mismatched-name VMs surface as `unknown` until adopted via `discover_and_map`.
- **D-07:** **Per-VM row** in `unknown[]` (NOT per-host with nested vm list). Shape: `hypervisor_hostname`, `node`, `vmid`, `vm_type` (`qemu` | `lxc`), `vm_name`, `vm_status`, `scan_timestamp`, `message`. `unknown[]` is a parallel per-VM surface, NOT a host bucket.

**Changed-diff payload (DRFT-19)**
- **D-08:** **Per-field diff pre-computed by drift** as `{field: {stored, current}}` dict-of-dicts. Empty `changed_fields` → no entry; the host stays in `probed_ok`. Dotted-path keys for nested capability sub-keys (`capabilities.vulkan.available`).
- **D-09:** **Diff scope = universal-core always; capabilities only when present in BOTH stored and current.** Drift never re-probes capabilities.
- **D-09a:** "Present in both" check is per leaf, not per `capabilities.*` sub-tree.
- **D-09b:** Agent's `update_device_fingerprint` deep-merge is the implicit acceptance for capability changes.

**Bucket exclusivity (host-level)**
- **D-10:** **Hosts land in exactly one host-level bucket per scan.** Priority order: `not_eligible` > `unreachable` (status sub-states) > `changed` > `probed_ok`. `unknown[]` is a per-VM surface independent of host buckets. `scanned == sum(counts.values())` invariant holds.

**AST guard extension (Phase 38.1 D-15 / D-16 carry-forward)**
- **D-11:** Phase 38.1 D-15's "no `continue` inside `scan_infrastructure_drift` body" AST guard is extended to cover Phase 39's new helpers. Either (a) add to `_FORBIDDEN_CONTINUE_FUNCTIONS` allowlist OR (b) refactor helpers to be loop-free. **(b) is recommended.**
- **D-12:** AST guard scope stays targeted (named-function list).

### Claude's Discretion

- Exact env var name format: `HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS` recommended. **Recommendation:** Stay with this — no `HOMELAB_MCP_` prefix observed in `config.py` (env vars use `MCP_*` for transport but `HOMELAB_*`-style is novel; minimum-friction).
- Whether `_probe_universal_core(conn) -> dict` is extracted as a shared helper. **Strongly recommended.**
- Whether `_diff_fingerprints` returns dict-of-dicts or list of records. **Dict-of-dicts recommended** — matches D-08 verbatim; flat structure, easy to iterate.
- Whether `/cluster/resources` enumeration is interleaved with the row loop or hoisted to a single pre-pass. **Single pre-pass recommended.**
- Exact `message` wording for unknown / missing / changed entries. Templates in D-07 / D-01 / D-08 are starting points; planner polishes for actionability.
- Whether parallelism uses a per-scan `Semaphore` instance or module-level. **Per-scan recommended** (no shared state across scans).
- Whether `last_seen` updates as a side effect of universal-core probe succeeding. **Locked NO by D-04b.** The threshold (D-02) measures "time since last `discover_and_map`" — correct semantic.
- Whether universal-core fields use a fixed dotted-path key set or dynamic walk. **Dynamic walk recommended** — same code path that diffs `capabilities.*` sub-keys handles top-level keys.

### Deferred Ideas (OUT OF SCOPE)

- Per-VM fingerprint diffing in the changed bucket → **v1.7.1 LIFE-***
- Storing `proxmox_vmid` + `proxmox_node` columns on sitemap rows → **v1.7.1**
- Drift re-probing capabilities via stored per-host probe commands → **v1.8 candidate**
- Consecutive-failure tracking for missing promotion → **v1.8 candidate**
- Two-mode drift scan (`--quick` + `--deep`) → **v1.8 candidate**
- Per-VM unknown-bucket flag for which discovery method to use → **v1.7.1 / v1.8**
- Extracting universal-core probe block as public helper for v1.7.1 LIFE-* hooks → **v1.7.1**
- Per-cluster `/cluster/resources` cache TTL across scans → **v1.8 candidate**
- Auto-promote unknown VM to sitemap with degraded-trust marker → **v1.7.2 / role-aware drift**
- `homelab://drift/latest` MCP Resource refresh: planner verifies — already auto-fires on `set_latest_drift_report` (server.py:456). [VERIFIED: server.py:456 sends `notifications/resources/updated` after every drift run; new bucket fields surface automatically since `read_drift_resource` returns the cached payload verbatim.]
</user_constraints>

## Project Constraints (from CLAUDE.md)

| Constraint | Implication for Phase 39 |
|------------|--------------------------|
| Python 3.12+, strict mypy | All new helpers (`_probe_universal_core`, `_diff_fingerprints`, `_enumerate_unknown_vms`, `_classify_unreachable`) must have full type annotations including return types. `dict[str, Any]` for fingerprint blobs; `Literal["missing", "unreachable"]` for the status sub-state. |
| `uv` package manager | All commands prefixed `uv run` (pytest, ruff, mypy). No new dependencies needed for this phase. |
| `mcp[cli]`, `asyncssh`, SQLite | All in tree. No new install. |
| Async-first for I/O | `_probe_universal_core` is `async`; SSH pre-pass uses `asyncio.gather`; `/cluster/resources` calls are already async on `ProxmoxAPIClient`. |
| `error_handling.py` patterns | Reuse `sanitize_error()` (log_filter.py) for unreachable/missing error fields per Phase 36 D-02 precedent. |
| Tools registered in `tools.py` (or `tool_schemas/drift_tools_schema.py`) | **No new tool surface.** `scan_infrastructure_drift` already exists; Phase 39 only enriches its output. Update the schema description if the bucket semantics change. |
| Type hints required, async/await for I/O | Enforced in mypy CI. |
| AST meta-tests guard known footguns (`feedback_regression_test_scope.md`) | Phase 38.1 D-15 invariant carries forward via D-11. |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| VM enumeration (DRFT-17) | API / Backend (Proxmox HTTP via aiohttp) | — | `/cluster/resources` is a remote read against Proxmox; no local persistence needed. |
| Universal-core probe (DRFT-19) | API / Backend (asyncssh subprocess) | — | SSH commands run on remote hosts. `_run_with_timeout` wraps each subprocess. |
| Threshold comparison (DRFT-18) | API / Backend (pure compute) | Database (sitemap read) | `last_seen` comes from `devices` row; comparison is in-process datetime arithmetic. |
| Diff computation (DRFT-19) | API / Backend (pure function) | — | `_diff_fingerprints(stored, current)` is a pure dict walk. |
| Bucket assembly | API / Backend (drift_detection.py module) | — | Read-only against the DB adapter; no writes (D-04b locks no fingerprint update). |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `asyncssh` | 2.x (in-tree) | Universal-core SSH probes | Already used by `ssh_discover_system` and `_run_with_timeout` (ssh_tools.py:863). [VERIFIED: pyproject.toml lists asyncssh; ssh_tools.py imports it at line 11.] |
| `aiohttp` | in-tree | Proxmox `/cluster/resources` HTTP calls | `ProxmoxAPIClient` (proxmox_api.py:49) already speaks `aiohttp`; Phase 38.1 hardened `ClientError + TimeoutError + ValueError` triple. |
| `asyncio` (stdlib) | 3.12 | `Semaphore(10) + gather`, outer 120s timeout | Phase 35 D-02 precedent at `bulk_discover_and_store` (sitemap.py:466-542). |
| `datetime` (stdlib) | 3.12 | `last_seen` parsing + threshold compare | Existing pattern: `datetime.now(UTC).isoformat()` already used at drift_detection.py:210 for `scan_timestamp`. |
| `os.getenv` (stdlib) | 3.12 | `HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS` env var | Matches `MCP_HTTP_*` / `DATABASE_TYPE` convention in config.py:1-80. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `ast` (stdlib) | 3.12 | AST guard extension | `tests/test_ast_regression.py` — D-11 carry-forward. |
| `json` (stdlib) | 3.12 | Fingerprint dict serialization | Already round-tripped by `get_all_devices()` (database.py:530-535). |
| `pytest` + `pytest-asyncio` | in-tree | Functional drift tests | Existing pattern in `tests/test_drift_detection.py`. |
| `unittest.mock` (stdlib) | 3.12 | `MagicMock` + `AsyncMock` for `db_adapter`, `get_proxmox_client`, SSH probe | Existing precedent in `tests/test_drift_detection.py:36-54`. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `Semaphore(10) + asyncio.gather` | `asyncio.TaskGroup` (3.11+) | TaskGroup gives structured concurrency / better cancellation. **Rejected** because Phase 35 D-02 locked Semaphore + gather and `bulk_discover_and_store` (sitemap.py:466) is the cited template. Consistency wins. |
| `_diff_fingerprints` as recursive walk | Hand-coded iterative stack | Recursion is ~6-10 lines; the fingerprint shape is shallow (~3 levels: top → `capabilities` → per-key dict). **Recursion recommended.** |
| `/cluster/resources` per-scan caching | Module-level TTL cache | Premature; cluster_name dedup within a scan is enough. **Per-scan local dict.** |
| Re-implementing the four probes inline in `scan_drift` | Extract `_probe_universal_core` helper | Duplication = drift between `ssh_discover_system` and `scan_drift` if Phase 40+ adds a fifth probe. **Extract.** |

**Installation:** No new packages. All libraries already in `pyproject.toml`.

**Version verification:** `uv pip list | grep -E '(asyncssh|aiohttp|mcp)'` confirms in-tree versions; no upgrade needed for this phase.

## Architecture Patterns

### System Architecture Diagram

```
                     ┌─────────────────────────────────────────────┐
                     │     scan_infrastructure_drift (MCP tool)    │
                     │     drift_handlers.handle_*  (handler)      │
                     └───────────────────┬─────────────────────────┘
                                         │
                                         ▼
                     ┌─────────────────────────────────────────────┐
                     │      drift_detection.scan_drift (entry)     │
                     │           (single for-row loop)             │
                     └───┬─────────────────┬──────────────────┬────┘
                         │                 │                  │
            ┌────────────▼──────┐  ┌───────▼──────────┐  ┌────▼────────────────┐
            │ DB read pre-pass  │  │ SSH probe pre-   │  │ VM enumeration      │
            │ get_all_devices() │  │ pass (universal- │  │ pre-pass per        │
            │ (sitemap rows)    │  │ core, all SSH-   │  │ cluster_name        │
            │                   │  │ bound rows)      │  │ (probed_ok hosts    │
            │ → rows[]          │  │ → {host: probe   │  │  only)              │
            │                   │  │     result}      │  │ → {cluster: vms[]}  │
            └────────┬──────────┘  └────────┬─────────┘  └────────┬────────────┘
                     │                      │                     │
                     └──────────────────────┼─────────────────────┘
                                            │
                                            ▼
                     ┌─────────────────────────────────────────────┐
                     │  for row in rows:  (single loop, D-15)      │
                     │   ├─ degenerate? → not_eligible (existing)  │
                     │   ├─ unbound (no proxmox_credential_id      │
                     │   │   AND no ssh_credential_id)? →          │
                     │   │   not_eligible/unbound (existing path)  │
                     │   ├─ Proxmox probe (existing /cluster/      │
                     │   │   status) →                             │
                     │   │     fail + last_seen old → unreachable/ │
                     │   │       missing                           │
                     │   │     fail + last_seen recent → unreach./ │
                     │   │       unreachable                       │
                     │   │     ok → consult SSH probe pre-pass     │
                     │   │       result → diff against stored      │
                     │   │       fingerprint                       │
                     │   │         diff non-empty → changed[]      │
                     │   │         diff empty → probed_ok[]        │
                     │   └─ append to chosen bucket                │
                     │                                             │
                     │  for cluster, vms in cluster_vm_map.items():│
                     │   for vm in vms:                            │
                     │     if vm.name.lower() not in               │
                     │         {row.hostname.lower() for row...}:  │
                     │       unknown.append({...per-VM record...}) │
                     └────────────────┬────────────────────────────┘
                                      │
                                      ▼
                     ┌─────────────────────────────────────────────┐
                     │  Build response envelope (locked key order):│
                     │  status, scan_timestamp, scanned, counts,   │
                     │  [guidance,] probed_ok, unreachable,        │
                     │  not_eligible, unknown, changed             │
                     └─────────────────────────────────────────────┘
                                      │
                                      ▼
                     ┌─────────────────────────────────────────────┐
                     │ set_latest_drift_report (server.py:85)      │
                     │  → notifications/resources/updated for      │
                     │    homelab://drift/latest (server.py:456)   │
                     └─────────────────────────────────────────────┘
```

### Recommended Project Structure

No new files. All work in:

```
src/homelab_mcp/
├── drift_detection.py           # extend scan_drift; add _diff_fingerprints,
│                                #   _enumerate_unknown_vms, _classify_unreachable
├── ssh_tools.py                 # extract _probe_universal_core helper
│                                #   (lines 614-691 → standalone fn)
└── proxmox_api.py               # NO CHANGES (reuse existing /cluster/resources)

tests/
├── test_drift_detection.py      # extend with TestPhase39Unknown,
│                                #   TestPhase39Missing, TestPhase39Changed
└── test_ast_regression.py       # extend D-11 (recommended: helpers loop-free,
                                 #   so no list grows)
```

### Pattern 1: Pre-pass + main loop (Phase 35 D-07 template)

**What:** Run bulk fan-out work (SSH probes, VM enumeration) BEFORE the row-classification loop; the loop reads from the pre-pass result dicts. Keeps the loop deterministic and AST-guardable.

**When to use:** Whenever bulk work is independent of per-row classification logic.

**Example:**
```python
# Source: sitemap.py:466-542 — Phase 35 D-07 template
semaphore = asyncio.Semaphore(10)

async def _probe_one(row: dict) -> tuple[str, dict | Exception]:
    hostname = row["hostname"]
    binding = row.get("ssh_credential_id")
    if binding is None:
        return (hostname, {"status": "unbound"})
    async with semaphore:
        try:
            creds = resolve_ssh_credentials(hostname, credential_id=binding)
            async with await ssh_connect(...) as conn:
                return (hostname, await _probe_universal_core(conn, []))
        except Exception as exc:  # noqa: BLE001 — caller classifies
            return (hostname, exc)

probe_results: dict[str, dict | Exception] = dict(
    await asyncio.gather(*[_probe_one(r) for r in rows], return_exceptions=False)
)

for row in rows:  # single loop; AST guard scope unchanged
    probe = probe_results.get(row["hostname"])
    # classify into bucket using `probe`
```

### Pattern 2: Pure-function classification helpers (D-11(b) recommendation)

**What:** Helpers return per-row decisions; appends happen inside `scan_drift`'s single loop. Helpers contain NO loops over `rows` / `vms` (the iteration is in `scan_drift`).

**When to use:** When the AST guard expects no `continue` inside the row-iter scope — which is exactly D-15's invariant.

**Example:**
```python
# RECOMMENDED — keeps helpers loop-free
def _classify_unreachable(
    row: dict, exc: BaseException, threshold_days: int, now: datetime
) -> tuple[Literal["unreachable", "missing"], str]:
    """Return (status_sub_state, message). No loops; pure compute."""
    last_seen = _parse_last_seen(row.get("last_seen"))
    if last_seen is not None and (now - last_seen).days > threshold_days:
        msg = (
            f"Host last seen {last_seen.isoformat()} (>{threshold_days}d ago). "
            f"If decommissioned, run `decommission_device {row['hostname']}` "
            f"or `purge_failed_discoveries` to clean up."
        )
        return ("missing", msg)
    return ("unreachable", sanitize_error(exc))


def _diff_fingerprints(stored: dict, current: dict) -> dict[str, dict]:
    """Walk both dicts, emit per-leaf diffs with dotted-path keys.

    D-09a: only diff leaves present in BOTH sides. D-09: capabilities follow
    the same rule — capabilities sub-keys absent from `current` (drift never
    re-probes) silently skip.
    """
    diffs: dict[str, dict] = {}

    def _walk(s: Any, c: Any, path: list[str]) -> None:
        if isinstance(s, dict) and isinstance(c, dict):
            for k in s.keys() & c.keys():  # leaf-level "present in both"
                _walk(s[k], c[k], path + [k])
        else:
            if s != c:
                diffs[".".join(path)] = {"stored": s, "current": c}

    _walk(stored, current, [])
    return diffs


def _enumerate_unknown_vms(
    cluster_vm_map: dict[str, list[dict]],
    sitemap_hostnames: set[str],  # already lower-cased
    scan_timestamp: str,
) -> list[dict]:
    """Build the unknown[] list. NO loop over sitemap rows here — caller
    pre-computes ``sitemap_hostnames``."""
    unknown: list[dict] = []

    def _make_row(vm: dict, hypervisor: str) -> dict | None:
        name = (vm.get("name") or "").strip()
        if not name or name.lower() in sitemap_hostnames:
            return None
        return {
            "hypervisor_hostname": hypervisor,
            "node": vm.get("node", ""),
            "vmid": int(vm.get("vmid", 0)),
            "vm_type": vm.get("type", "qemu"),  # qemu | lxc
            "vm_name": name,
            "vm_status": vm.get("status", "unknown"),
            "scan_timestamp": scan_timestamp,
            "message": (
                f"VM '{name}' (vmid={vm.get('vmid')}) on node '{vm.get('node')}' "
                f"not in sitemap; run `discover_and_map <ip-or-hostname>` to adopt."
            ),
        }

    # Caller-driven iteration; helper only flattens (no `continue` inside
    # iteration over the live data structures the row loop also consumes).
    for hypervisor, vms in cluster_vm_map.items():
        unknown.extend(filter(None, (_make_row(vm, hypervisor) for vm in vms)))

    return unknown
```

### Pattern 3: Reuse `_probe_universal_core` (Claude's Discretion → strongly recommended)

**What:** Lift lines 614-691 of ssh_tools.py (the four-command probe block + `partial: True` accumulator) into a standalone async helper.

**When to use:** Both `ssh_discover_system` (existing) and `scan_drift`'s SSH pre-pass (new) call it. Single source of truth.

**Example:**
```python
# Source: extracted from ssh_tools.py:614-691
async def _probe_universal_core(
    conn: asyncssh.SSHClientConnection,
    timed_out_commands: list[str],
) -> dict[str, Any]:
    """Phase 38 D-04 universal-core fingerprint probes (kernel/OS/package).

    Reused by Phase 39 drift detection. All four probes wrapped in
    ``_run_with_timeout(10s)`` per Phase 35 D-05; non-zero exits enroll
    cmd_name into ``timed_out_commands`` so callers can flag ``partial: True``.
    """
    fingerprint: dict[str, Any] = {}

    uname_s = await _run_with_timeout(conn, "uname -s", cmd_name="uname-s",
                                       timed_out=timed_out_commands)
    if uname_s and uname_s.exit_status == 0 and uname_s.stdout:
        fingerprint["kernel_name"] = uname_s.stdout.strip()
    elif uname_s is not None and uname_s.exit_status != 0:
        if "uname-s" not in timed_out_commands:
            timed_out_commands.append("uname-s")

    # ... (uname -r, /etc/os-release, dpkg-fingerprint — same pattern as
    # ssh_tools.py lines 626-688; lift verbatim) ...

    return fingerprint
```

### Anti-Patterns to Avoid

- **`continue` inside `scan_drift`'s row loop or any new helper that contains a loop appending to a bucket.** Phase 38.1 D-15 invariant; D-11 extends. Use early-return + per-row classification helpers instead.
- **Re-implementing the universal-core probes inline in `scan_drift`.** Drift between `ssh_discover_system` and the drift probe site if a fifth probe is added later.
- **Updating `last_seen` after a successful drift probe.** D-04b locks no — and Phase 38 WR-03 (database.py:412-416) explicitly comments the same invariant on `update_device_fingerprint`.
- **Calling `/cluster/resources` once per Proxmox row.** D-05 requires de-dupe by `cluster_name`. A 5-node cluster with 5 sitemap rows → 1 enumeration call, not 5.
- **Diffing capability sub-keys absent from `current`.** D-09a: per-leaf "present in both" check. Otherwise every drift scan reports "capabilities removed" because drift didn't probe them.
- **Adding a 6th `missing[]` bucket.** D-01 explicitly rejects this; envelope stability is locked.
- **Creating a new MCP tool surface.** Phase 39 ONLY enriches `scan_infrastructure_drift` output; no new tool registration in `tool_schemas/drift_tools_schema.py`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-host SSH command timeout | Custom `asyncio.wait_for` blocks | `_run_with_timeout(conn, cmd, cmd_name=..., timed_out=...)` (ssh_tools.py:863) | Phase 35 D-05 + AST guard at tests/test_ast_regression.py:447 enforce this. |
| Bulk fan-out concurrency | Custom queue / worker pool | `asyncio.Semaphore(10) + asyncio.gather` (sitemap.py:466) | Phase 35 D-02 locked. |
| Proxmox `/cluster/resources` call | Re-implement HTTP/auth | `client.get("/cluster/resources")` via existing `get_proxmox_client` | proxmox_api.py:557 already does it. |
| Cluster_name → host de-dupe | Walk rows, hash by hostname | `_HOST_CLUSTER_CACHE` lookup (proxmox_api.py:22) + `get_resolution_telemetry` (proxmox_api.py:36) | Process-lifetime cache populated by every successful resolution. |
| Error sanitization for missing/unreachable | Hand-strip secrets | `sanitize_error(exc)` (log_filter.py) | Phase 36 D-02 already routes drift error fields through this. |
| Credential resolution | Bypass with env vars | `resolve_ssh_credentials(hostname, credential_id=...)` and `resolve_proxmox_credentials(hostname, credential_id=...)` | Phase 38.1 R6 — `credential_id` keyword param. |
| Datetime parsing for `last_seen` | Custom regex | `datetime.fromisoformat(row["last_seen"])` | Sitemap stores `datetime.now().isoformat()` per sitemap.py:84 — round-trips cleanly with `fromisoformat`. |
| Fingerprint storage / merge | Re-write merge | Already locked: `update_device_fingerprint` (Phase 38 D-05) — but **drift never calls it** per D-04b. Read-only via `get_all_devices()`. | |

**Key insight:** Every primitive Phase 39 needs is already in tree. The phase is a composition exercise: glue `_probe_universal_core` + `Semaphore(10) + gather` + `_diff_fingerprints` + `/cluster/resources` enumeration into the existing single-loop body of `scan_drift`. No new abstractions.

## Runtime State Inventory

> **N/A — Phase 39 is purely a feature extension; no rename / refactor / migration.**

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Phase 39 is read-only against `devices` table; D-04b locks no fingerprint update | None |
| Live service config | None | None |
| OS-registered state | None | None |
| Secrets/env vars | New env var `HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS` (default 7) — code-only addition; no existing env var to migrate | Document in README + tool schema description |
| Build artifacts | None | None |

## Common Pitfalls

### Pitfall 1: Function name `scan_drift` ≠ MCP tool name `scan_infrastructure_drift`
**What goes wrong:** AST guard tests target `scan_drift` (the Python function in `drift_detection.py`), but the MCP tool name (`scan_infrastructure_drift` in `tool_schemas/drift_tools_schema.py`) is what the user invokes. Confusing them in test fixtures or AST guard names breaks the guard silently.
**Why it happens:** Phase 38.1 D-15 explicitly notes this in the test class docstring at `tests/test_ast_regression.py:758-760`. The MCP tool calls into the Python function via `tool_handlers/drift_handlers.py:24`.
**How to avoid:** AST guards use `scan_drift`; user-facing schema messages use `scan_infrastructure_drift`. Test class names follow precedent (`TestPhase39DriftCases` etc.).
**Warning signs:** AST guard test asserts `target is not None` — flips `False` if `scan_drift` is renamed without the guard's `n.name == "scan_drift"` updated.

### Pitfall 2: Cluster-served Proxmox rows have `eligibility.proxmox = False` even though the resolver Tier-2 walk resolves them
**What goes wrong:** Phase 38.1 D-09 noted that `device_dict["eligibility"]` is "pure binding-state" (binding column non-null), NOT cluster-walk-aware. A cluster-scope Proxmox host has `proxmox_credential_id = None` on its sitemap row but the Tier-2 walk in `resolve_proxmox_credentials` finds it. If Phase 39 routes by `eligibility.proxmox` instead of attempting resolution, every cluster-served host wrongly lands in `not_eligible/unbound`.
**Why it happens:** Reading `eligibility` (database.py:542-545) is cheaper than calling the resolver, but `eligibility` is a partial signal.
**How to avoid:** Continue the Phase 38.1 routing pattern — call `get_proxmox_client(host=hostname, credential_id=binding)` and let the resolver chain decide. Drop into `not_eligible` only on `CredentialNotFoundError`, never on `eligibility.proxmox == False` alone.
**Warning signs:** Cluster-served hosts disappear from `probed_ok[]` in functional tests with `_HOST_CLUSTER_CACHE` populated.

### Pitfall 3: SSH probe timeout cascade exceeding 120s outer scan timeout
**What goes wrong:** With `Semaphore(10)`, 50 unreachable SSH-bound rows × 4 probes × 10s/probe = up to 200s if probes are serial within a host. Outer 120s scan timeout (Phase 35 D-02 ceiling) trips, scan returns partial results.
**Why it happens:** Each `_run_with_timeout(10s)` is per-probe; within one host, four probes run sequentially in `_probe_universal_core`. Per-host worst-case is 40s (4 × 10s). Across `Semaphore(10)`, 50 hosts in 5 batches = ~5 × 40s = 200s.
**How to avoid:** (a) the SSH connection itself uses asyncssh's default connect timeout — wrap the whole `_probe_universal_core` call (not just per-probe) in an outer `asyncio.wait_for(timeout=45)` to bound per-host worst case; (b) document the bound; (c) add unit test that verifies a single unreachable host doesn't take >45s.
**Warning signs:** `test_drift_scan_outer_timeout` test asserts `< 120s` for a fixture of 50 unreachable hosts.

### Pitfall 4: `last_seen` value parsing edge cases
**What goes wrong:** SQLite stores `last_seen TEXT NOT NULL` (database.py:201) populated by `datetime.now().isoformat()` (sitemap.py:84) — a NAIVE datetime, no timezone suffix. `datetime.fromisoformat(s)` returns a naive `datetime`. Comparing to `datetime.now(UTC)` raises `TypeError: can't subtract offset-naive and offset-aware datetimes`.
**Why it happens:** Sitemap discovery uses `datetime.now().isoformat()` (no tzinfo), while drift uses `datetime.now(UTC)` for `scan_timestamp`.
**How to avoid:** Normalize parse: `last_seen = datetime.fromisoformat(s).replace(tzinfo=UTC)` (or naive-vs-naive comparison). Add a `_parse_last_seen(s) -> datetime | None` helper that returns timezone-aware UTC; tolerates malformed values by returning `None` (then row classifies as `unreachable`, not `missing` — defensive default).
**Warning signs:** Functional test with mock `last_seen = "2026-04-20T10:00:00"` raises TypeError instead of comparing.

### Pitfall 5: Case-insensitive hostname match in `unknown[]` skipping legitimate VMs
**What goes wrong:** D-06 specifies case-insensitive `vm.name == sitemap.hostname` match. If sitemap stores `pve1.lan` and Proxmox reports VM name `pve1`, naive case-folded equality misses the suffix.
**Why it happens:** Hostname-as-natural-key (Phase 35 D-01) doesn't normalize the FQDN suffix. Sitemap can hold either `pve1` or `pve1.lan` depending on `discover_and_map` input.
**How to avoid:** Lower-case both sides before comparison: `vm.name.lower() in {row["hostname"].lower() for row in rows if row.get("hostname")}`. Document that suffix-mismatch surfaces as `unknown[]` until adopted via `discover_and_map` (D-06 explicit).
**Warning signs:** Functional test with VM name `Plex-Server` and sitemap row `plex-server` — must match.

### Pitfall 6: `unknown[]` cardinality from cluster-walk pollution
**What goes wrong:** A cluster with 50 LXC containers and only 5 in sitemap → 45 entries in `unknown[]`. Phase 39 D-07 makes each per-VM, so the response can become large.
**Why it happens:** Honest cardinality of the user's untracked infrastructure. Not a bug, but a UX surprise.
**How to avoid:** No code change — but the planner should add a phase-level note in `message` field templates that `discover_and_map` adopts a single host at a time (matches D-07 wording: "run `discover_and_map <ip>` to adopt"). Acceptable for v1.7; v1.7.1 LIFE-* hooks will populate sitemap on VM create, eliminating most of this load.

### Pitfall 7: AST guard accidentally extended to `_probe_universal_core` in `ssh_tools.py`
**What goes wrong:** D-11 extends AST guard to NEW helpers in `drift_detection.py`. If `_probe_universal_core` is extracted to `ssh_tools.py` (its true home, since `ssh_discover_system` calls it), the guard scope must NOT include it — it doesn't iterate sitemap rows.
**Why it happens:** Function-name globbing in the AST guard's allowlist could match the helper anywhere in the source tree.
**How to avoid:** D-12: keep AST guard scope targeted (named-function list, not whole-file). The guard's source-file lookup currently hits `drift_detection.py` ONLY (test_ast_regression.py:769). Maintain that.
**Warning signs:** AST guard test fails on the lifted helper because `ssh_tools.py` isn't in the scope.

## Code Examples

### Reading and parsing `last_seen`
```python
# Source: drift_detection.py:210 (existing pattern + database.py:201 schema)
import os
from datetime import UTC, datetime, timedelta

_DEFAULT_THRESHOLD_DAYS = 7

def _missing_threshold_days() -> int:
    raw = os.getenv("HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS", str(_DEFAULT_THRESHOLD_DAYS))
    try:
        v = int(raw)
        return v if v > 0 else _DEFAULT_THRESHOLD_DAYS
    except ValueError:
        return _DEFAULT_THRESHOLD_DAYS


def _parse_last_seen(raw: str | None) -> datetime | None:
    """Sitemap writes naive isoformat; normalize to UTC-aware for compare."""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
```

### Per-cluster `/cluster/resources` enumeration with de-dupe
```python
# Source: proxmox_api.py:557 (existing call) + proxmox_api.py:22 (cache)
from .proxmox_api import _HOST_CLUSTER_CACHE, get_resolution_telemetry

async def _enumerate_proxmox_vms(
    probed_ok_hosts: list[tuple[str, str | None]],   # (hostname, cluster_name)
    session: aiohttp.ClientSession | None,
) -> dict[str, list[dict]]:
    """Returns {representative_hostname: [vm_record, ...]}.
    De-duped by cluster_name; standalone hosts keyed by their own hostname.
    """
    seen_clusters: set[str] = set()
    cluster_vm_map: dict[str, list[dict]] = {}

    async def _enum_one(hostname: str, cluster_name: str | None) -> tuple[str, list[dict]]:
        client = await get_proxmox_client(host=hostname, session=session)
        try:
            resources = await client.get("/cluster/resources")
        except (aiohttp.ClientError, ValueError) as exc:
            logger.debug("VM enum failed for %s: %s", hostname, sanitize_error(exc))
            return (hostname, [])
        # /cluster/resources returns mixed types; filter to VMs/LXC.
        vms = [r for r in resources if r.get("type") in ("qemu", "lxc")]
        return (hostname, vms)

    targets: list[tuple[str, str | None]] = []
    for hostname, cluster_name in probed_ok_hosts:
        key = cluster_name or hostname
        if key in seen_clusters:
            continue  # NOTE: this `continue` is OUTSIDE scan_drift's row loop;
                     # it's in a DIFFERENT helper, allowed by D-11/D-12 scope.
        seen_clusters.add(key)
        targets.append((hostname, cluster_name))

    results = await asyncio.gather(*[_enum_one(h, c) for h, c in targets])
    for hostname, vms in results:
        cluster_vm_map[hostname] = vms

    return cluster_vm_map
```

> **AST guard note:** the `continue` above is in a NEW helper. Per D-11(b), helpers either get added to the allowlist OR avoid loops over the row/VM iteration that feeds bucket appends. This helper's loop builds `targets` (de-dupe), it does NOT iterate the per-bucket-append path. The bucket-feeding loop is in `_enumerate_unknown_vms` and `scan_drift` itself; those stay loop-free or non-`continue`. **Recommendation:** even here, refactor the de-dupe to use a comprehension so D-11/D-12 stays maximally clean:
>
> ```python
> # Loop-free de-dupe via dict comprehension preserving first occurrence:
> targets = list({(c or h): (h, c) for h, c in probed_ok_hosts}.values())
> ```

### Diff helper (recursive walk)
See Pattern 2 example above (`_diff_fingerprints`).

### Bulk SSH probe pre-pass with Semaphore(10)
```python
# Source: sitemap.py:466-542 — Phase 35 D-07 template
from .ssh_tools import _probe_universal_core, resolve_ssh_credentials
from .ssh_connection import ssh_connect

async def _bulk_universal_core_probes(
    rows: list[dict],
) -> dict[str, dict]:
    """Run universal-core probes against every row with ssh_credential_id.
    Returns {hostname: probe_result_or_error_dict}.
    """
    semaphore = asyncio.Semaphore(10)

    async def _probe_one(row: dict) -> tuple[str, dict]:
        hostname = row["hostname"]
        binding = row.get("ssh_credential_id")
        if binding is None:
            return (hostname, {"_error": "unbound"})
        async with semaphore:
            try:
                creds = resolve_ssh_credentials(hostname, credential_id=binding)
                async with await ssh_connect(
                    hostname=creds.hostname,
                    username=creds.username,
                    port=creds.port,
                    password=creds.password,
                    key_path=creds.key_path,
                ) as conn:
                    timed_out: list[str] = []
                    fp = await asyncio.wait_for(
                        _probe_universal_core(conn, timed_out),
                        timeout=45.0,  # Pitfall 3 bound
                    )
                    return (hostname, {
                        "fingerprint": fp,
                        "partial": bool(timed_out),
                        "timed_out_commands": timed_out,
                    })
            except (asyncssh.Error, OSError, TimeoutError, ValueError) as exc:
                return (hostname, {"_error": sanitize_error(exc)})

    pairs = await asyncio.gather(
        *[_probe_one(r) for r in rows if r.get("ssh_credential_id")],
        return_exceptions=False,
    )
    return dict(pairs)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Drift maintains parallel `drift_baselines` table | Sitemap is single source of truth | v1.7 Phase 36 | DRFT-21 dropped table; Phase 39's stored fingerprint reads come from `devices.fingerprint` only |
| Drift detection skipped rows on credential failure (Bug O) | All rows route to one of 5 buckets; `not_eligible` enum | v1.7 Phase 38.1 | Phase 39 maintains the invariant via D-15 AST guard |
| Universal-core fingerprint NOT on sitemap rows | `fingerprint` JSON column with kernel/OS/package + per-host capabilities | v1.7 Phase 38 | Phase 39 reads this for the `changed[]` diff |
| Per-row credential resolution by hostname inference | Stable `proxmox_credential_id` / `ssh_credential_id` UUID binding | v1.7 Phase 38.1 | Phase 39 binds via R6 `credential_id` keyword |

**Deprecated/outdated:**
- `mcp_admin` username default in resolvers — removed in Phase 33.1; drift NEVER hardcodes default usernames.
- `PROXMOX_HOST` env-var-based drift path — Phase 36 DRFT-12 removed; resolver path only.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `last_seen` written by sitemap is naive `datetime.now().isoformat()` | Pitfall 4, Code Examples | Threshold compare raises `TypeError`. **VERIFIED** by sitemap.py:84 grep. |
| A2 | `/cluster/resources` returns rows with `name`, `vmid`, `node`, `type` (`qemu`|`lxc`), `status` keys | Pattern 1, _enumerate_unknown_vms | Per-VM record shape D-07 misses fields. [CITED: pve.proxmox.com/pve-docs/api-viewer #/cluster/resources — keys verified: `vmid`, `node`, `name`, `type`, `status`; on standalone Proxmox the endpoint still exists and returns local resources.] |
| A3 | `_HOST_CLUSTER_CACHE` is populated whenever `resolve_proxmox_credentials` succeeds via Tier-2 cluster walk | Pattern 1, Pitfall 2 | Cluster de-dupe misses → N×duplicate `/cluster/resources` calls. **VERIFIED** at proxmox_api.py:424. |
| A4 | `eligibility.proxmox` is binding-only (NOT cluster-walk-aware) | Pitfall 2 | Cluster-served hosts wrongly route to `not_eligible`. **VERIFIED** at database.py:537-545 + comment. |
| A5 | The 120s outer scan timeout from Phase 35 D-02 is implicit (not currently set in `scan_drift`) | Pitfall 3 | If absent, no upper bound on scan duration. **CHECK during planning** — search `scan_drift` for outer `wait_for`. [ASSUMED — not yet verified.] |
| A6 | Adding `_probe_universal_core` to `ssh_tools.py` does NOT trigger the Phase 35 AST guard (`test_ssh_discover_system_wraps_every_conn_run_phase35`) | Pitfall 7 | False positive on guard. **VERIFIED**: guard scope is `n.name == "ssh_discover_system"` only (test_ast_regression.py:466). New helper is a sibling. |
| A7 | `set_latest_drift_report` (server.py:85, 456) automatically surfaces new bucket fields via `homelab://drift/latest` | CONTEXT Deferred Ideas | Resource readers might filter the payload. **VERIFIED**: resource_readers.py:138 returns `report` verbatim — no filtering. New buckets surface automatically. |
| A8 | `asyncssh.Error` covers connection-refused / auth-failure / timeout exceptions for SSH probes | Code Examples | If a different exception class escapes, drift returns 500 instead of `unreachable`. [CITED: asyncssh docs — `asyncssh.Error` is the base class; `ConnectionLost`, `PermissionDenied`, `ProcessError` all subclass it.] |

## Open Questions

1. **Outer scan timeout enforcement.** Does `scan_drift` currently wrap its body in `asyncio.wait_for(scan_drift_body, timeout=120)`? Phase 35 D-02 set the precedent for `bulk_discover_and_store` (sitemap.py:466) but a quick scan of drift_detection.py:124-372 shows no outer `wait_for`. The Phase 35 ceiling is documented but might not be enforced.
   - What we know: `_run_with_timeout(10s)` is per-probe; no outer scan timeout in current code.
   - What's unclear: whether to add it in Phase 39 (might be CONTEXT D-04a's literal intent: "Outer scan timeout follows Phase 35's 120s ceiling").
   - Recommendation: Plan adds `asyncio.wait_for(... , timeout=120)` around the SSH pre-pass + main loop block. Confirm in plan-check.

2. **Tool schema description update.** `tool_schemas/drift_tools_schema.py:4-20` mentions `(probed_ok, unreachable, unknown, changed)` — does it currently describe the `not_eligible` bucket or missing/changed semantics?
   - Recommendation: Plan reviews the schema description and updates to mention all 5 bucket semantics + the `status: "missing"` sub-state.

3. **Standalone-Proxmox `/cluster/resources` fallback.** D-05 says "Per-node fallback only when `/cluster/resources` returns an error indicating standalone (non-cluster) Proxmox setup." Standalone Proxmox supports `/cluster/resources` (returns local node's VMs) per Proxmox docs — the fallback to `/nodes/{node}/qemu` may be unreachable in practice.
   - What we know: A2 verifies the endpoint works on standalone.
   - Recommendation: Document the fallback as DEFENSIVE (rare; only if API returns 4xx with a recognized standalone error code). Don't hand-roll an exhaustive fallback path; raise on unexpected errors and surface as `unreachable[]` for the hypervisor row.

4. **VM enumeration error → which bucket?** If the host is in `probed_ok` (cluster status returned a list) but `/cluster/resources` raises, which bucket does the host land in? Probably stays in `probed_ok` with a note (the `/cluster/status` probe SUCCEEDED, this is a secondary fetch).
   - Recommendation: Plan defines the rule: enumeration failure DOES NOT change the host's bucket placement; it just means `unknown[]` doesn't get any VMs from that host. Log a debug message; don't degrade to `unreachable`.

5. **Wave 0 testing scope.** Phase 39 has 3 functional tests (one per requirement) + AST guard extension + per-helper unit tests for `_diff_fingerprints`, `_classify_unreachable`, `_enumerate_unknown_vms`. Existing `tests/test_drift_detection.py` is at line 821+ for `TestScanDriftNotEligible` (the prior phase's tests). New test classes `TestPhase39Unknown`, `TestPhase39Missing`, `TestPhase39Changed` follow the same pattern.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All | ✓ | 3.12.x | — |
| `uv` package manager | Test/lint commands | ✓ | (in dev env) | — |
| `asyncssh` | SSH probe pre-pass | ✓ | in `pyproject.toml` | — |
| `aiohttp` | Proxmox `/cluster/resources` | ✓ | in `pyproject.toml` | — |
| `pytest`, `pytest-asyncio` | Functional tests | ✓ | in dev deps | — |
| `mypy`, `ruff`, `bandit` | Quality gates | ✓ | in dev deps | — |
| Live Proxmox cluster | Manual UAT (DRFT-17 unknown VM case) | ✗ | — | CI uses mocks; manual verification on user's homelab Proxmox |
| Real SSH-bound host with kernel update | Manual UAT (DRFT-19 changed case) | ✗ | — | Functional test uses mock SSH probe response with differing fingerprint |

**Missing dependencies with no fallback:** None blocking — all three drift cases are mock-testable. Real hardware verification is part of milestone close UAT, not Phase 39 plan execution.

**Missing dependencies with fallback:** Live Proxmox / real-host probes deferred to UAT. STATE.md "Phase 38/39 live-test verifiability" notes this is expected.

## Validation Architecture

> Nyquist validation enabled (`workflow.nyquist_validation: true` in .planning/config.json).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (pytest-asyncio plugin) |
| Config file | `pyproject.toml` (pytest-asyncio mode, markers); pytest discovers `tests/` |
| Quick run command | `uv run pytest tests/test_drift_detection.py tests/test_ast_regression.py -x -v` |
| Full suite command | `uv run pytest -m "not integration" -x` (unit) + `uv run pytest tests/integration/ -m integration` (Docker integration — only if drift integration scope changes) |

### Test Layers

| Layer | Location | Coverage Target | Sampling Rate |
|-------|----------|----------------|----------------|
| **Unit (helpers)** | `tests/test_drift_detection.py::TestPhase39Helpers` | `_diff_fingerprints` (10+ leaf-level cases), `_probe_universal_core` extraction parity (3+ cases), `_enumerate_unknown_vms` (5+ cases), `_classify_unreachable` (4+ cases) | Per-task commit |
| **Functional (per-requirement)** | `tests/test_drift_detection.py::{TestPhase39Unknown,TestPhase39Missing,TestPhase39Changed}` | One happy-path + one edge per requirement = 3 happy + 3 edge ≥ 6 tests | Per-wave merge |
| **AST regression guard** | `tests/test_ast_regression.py::TestPhase39DriftCases` | D-11(b) — verify `scan_drift` row loop still has zero `continue`; verify new helpers (`_diff_fingerprints`, `_enumerate_unknown_vms`, `_classify_unreachable`) have no `continue` inside any loop body that appends to a bucket-shaped list | Per-task commit (cheap) |
| **Quality gates** | `ruff`, `mypy`, `bandit` | Strict mypy on new helpers (full type annotations); ruff format/lint clean | Per-task commit |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DRFT-17 | Manually-created VM appears in `unknown[]` with hypervisor + node + vmid + adoption pointer | functional | `pytest tests/test_drift_detection.py::TestPhase39Unknown::test_unmatched_vm_in_unknown_bucket -x` | ❌ Wave 0 (extend existing file) |
| DRFT-17 | Cluster with N nodes does ONE `/cluster/resources` call (de-dupe) | functional | `pytest tests/test_drift_detection.py::TestPhase39Unknown::test_cluster_dedup_single_enumeration -x` | ❌ Wave 0 |
| DRFT-17 | Case-insensitive VM-name match against sitemap hostname | unit | `pytest tests/test_drift_detection.py::TestPhase39Helpers::test_enumerate_unknown_case_insensitive -x` | ❌ Wave 0 |
| DRFT-18 | Sitemap row with `last_seen` > 7d AND probe failed → `unreachable[]` with `status: "missing"` | functional | `pytest tests/test_drift_detection.py::TestPhase39Missing::test_old_last_seen_promotes_to_missing -x` | ❌ Wave 0 |
| DRFT-18 | Threshold env var override respected | unit | `pytest tests/test_drift_detection.py::TestPhase39Missing::test_threshold_env_var_override -x` | ❌ Wave 0 |
| DRFT-18 | Recent unreachable host stays `status: "unreachable"` | functional | `pytest tests/test_drift_detection.py::TestPhase39Missing::test_recent_unreachable_not_promoted -x` | ❌ Wave 0 |
| DRFT-18 | `_classify_unreachable` returns correct sub-state for naive vs UTC last_seen | unit | `pytest tests/test_drift_detection.py::TestPhase39Helpers::test_classify_unreachable_timezone_normalization -x` | ❌ Wave 0 |
| DRFT-19 | Universal-core kernel diff appears in `changed[]` with `kernel_version: {stored, current}` | functional | `pytest tests/test_drift_detection.py::TestPhase39Changed::test_kernel_change_in_changed_bucket -x` | ❌ Wave 0 |
| DRFT-19 | Empty diff → host stays in `probed_ok[]` (not `changed[]`) | functional | `pytest tests/test_drift_detection.py::TestPhase39Changed::test_no_diff_stays_probed_ok -x` | ❌ Wave 0 |
| DRFT-19 | Capability diff only fires when leaf present in BOTH stored and current | unit | `pytest tests/test_drift_detection.py::TestPhase39Helpers::test_diff_fingerprints_per_leaf_present_in_both -x` | ❌ Wave 0 |
| DRFT-19 | Dotted-path keys for nested capabilities (`capabilities.vulkan.available`) | unit | `pytest tests/test_drift_detection.py::TestPhase39Helpers::test_diff_fingerprints_dotted_path -x` | ❌ Wave 0 |
| DRFT-19 | Drift never writes to `devices.fingerprint` (D-04b) | functional | `pytest tests/test_drift_detection.py::TestPhase39Changed::test_drift_does_not_update_fingerprint -x` (asserts `db_adapter.update_device_fingerprint` not called) | ❌ Wave 0 |
| D-10 | `scanned == sum(counts.values())` invariant holds across all 5 buckets | functional | `pytest tests/test_drift_detection.py::TestPhase39Bucket::test_scanned_equals_counts_sum -x` | ❌ Wave 0 |
| D-10 | Host with kernel change AND unknown VMs → `changed[]` for host record + N entries in `unknown[]` | functional | `pytest tests/test_drift_detection.py::TestPhase39Bucket::test_changed_host_with_unknown_vms -x` | ❌ Wave 0 |
| D-11 | AST guard: no `continue` in `scan_drift` row loop after Phase 39 changes | regression | `pytest tests/test_ast_regression.py::TestPhase381CredBinding::test_scan_drift_no_continue_in_row_loop_phase38_1 -x` | ✅ exists |
| D-11 | AST guard (NEW): no `continue` inside `_diff_fingerprints`, `_enumerate_unknown_vms`, `_classify_unreachable` loops that append to bucket lists | regression | `pytest tests/test_ast_regression.py::TestPhase39DriftCases -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_drift_detection.py::TestPhase39Helpers tests/test_ast_regression.py -x` (~3-5s, all unit + AST guards)
- **Per wave merge:** `uv run pytest tests/test_drift_detection.py tests/test_ast_regression.py -x -v` (full drift + regression test files; ~10-15s)
- **Phase gate:** Full suite green before `/gsd-verify-work` — `uv run pytest -m "not integration" -x` + `uv run ruff check src/ tests/` + `uv run mypy src/`

### Fixtures Needed

| Fixture | Purpose | Shape / Seed Data |
|---------|---------|-------------------|
| `mock_cluster_resources_response` | Mock Proxmox `/cluster/resources` JSON | List of dicts: `[{type: "qemu", vmid: 100, node: "pve1", name: "ubuntu-test", status: "running"}, {type: "lxc", vmid: 101, node: "pve1", name: "pi-hole", status: "running"}, ...]` |
| `mock_universal_core_probe_response` | Mock `_probe_universal_core` return | `{"kernel_name": "Linux", "kernel_version": "6.5.13-1-pve", "os_name": "Proxmox VE", "os_version": "8.2.4", "package_fingerprint": "sha256:abc..."}` (current snapshot for diff baseline) |
| `mock_universal_core_probe_drifted` | Mock probe with kernel change | Same as above but `kernel_version: "6.8.4-2-pve"` (the diff fixture) |
| `sitemap_row_old_last_seen` | Sitemap row past missing threshold | `{"hostname": "pi-lab", "ssh_credential_id": "uuid-...", "last_seen": "2026-04-15T10:00:00", "fingerprint": {...}}` (12 days before scan) |
| `sitemap_row_recent_last_seen` | Sitemap row within threshold | `{"hostname": "pi-lab", "last_seen": "2026-04-26T10:00:00", ...}` (1 day before scan) |
| `sitemap_row_with_stored_fingerprint` | Sitemap row with full Phase 38 fingerprint blob | top-level `fingerprint: {kernel_*, os_*, package_fingerprint, capabilities: {vulkan: {available: true}}}` |
| `mock_db_adapter` | `MagicMock` with `get_all_devices.return_value = [...]` and `update_device_fingerprint = MagicMock()` (asserted never called) | Existing pattern at `test_drift_detection.py:36-41` |
| `mock_get_proxmox_client` | `AsyncMock`-based fake (returns client whose `.get()` is `AsyncMock`) | Existing pattern at `test_drift_detection.py:43-54`; extend to also stub `client.get("/cluster/resources")` |
| `mock_resolve_ssh_credentials` | Patch `homelab_mcp.drift_detection.resolve_ssh_credentials` to return canned `SSHCredentials` | New for Phase 39 — drift now imports it |
| `mock_ssh_connect` | Patch `homelab_mcp.drift_detection.ssh_connect` to yield a mock async context manager whose `conn` returns mock probe results | New for Phase 39 |
| `freeze_now` | Patch `datetime.now(UTC)` to fixed instant for deterministic `scan_timestamp` and threshold compare | Use `freezegun` if already in dev deps, else `monkeypatch.setattr(drift_detection, "datetime", FakeDatetime)` |

### Wave 0 Gaps

- [ ] `tests/test_drift_detection.py::TestPhase39Helpers` — unit tests for `_diff_fingerprints`, `_classify_unreachable`, `_enumerate_unknown_vms` (covers DRFT-17/18/19 helper logic)
- [ ] `tests/test_drift_detection.py::TestPhase39Unknown` — DRFT-17 functional tests (3 tests minimum)
- [ ] `tests/test_drift_detection.py::TestPhase39Missing` — DRFT-18 functional tests (3 tests minimum)
- [ ] `tests/test_drift_detection.py::TestPhase39Changed` — DRFT-19 functional tests (4 tests minimum)
- [ ] `tests/test_drift_detection.py::TestPhase39Bucket` — D-10 invariants (2 tests minimum)
- [ ] `tests/test_ast_regression.py::TestPhase39DriftCases` — D-11(b) carry-forward (1-3 tests)
- [ ] Shared fixture file: existing `tests/conftest.py` — add `freeze_now`, `mock_universal_core_probe_response*`, `mock_cluster_resources_response`, sitemap-row factory helpers
- [ ] No new pytest plugins / framework install required.

## Security Domain

> `security_enforcement` not explicitly false in `.planning/config.json` — included.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Reuse `resolve_ssh_credentials` and `resolve_proxmox_credentials` Tier-0 UUID short-circuit (Phase 38.1 D-11/D-12/D-13). Drift never reads keyring directly. |
| V3 Session Management | no | Stateless drift scan; no user sessions. MCP transport handles session if HTTP. |
| V4 Access Control | no | Drift scan is read-only; user authorization enforced at MCP transport layer. |
| V5 Input Validation | yes | `HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS` env var: clamp to positive int; reject malformed via `try/except ValueError` falling back to default 7 (Code Examples above). VM enumeration response fields validated by `vm.get(key, default)` — no trust-the-shape. |
| V6 Cryptography | no | No crypto operations in this phase; SHA-256 fingerprint is a simple digest, not for security purposes. |
| V7 Error Handling and Logging | yes | All `unreachable`/`missing` error fields go through `sanitize_error()` (log_filter.py) per Phase 36 D-02. NEVER log the actual SSH command output (could leak hostnames/IPs). |
| V14 Configuration | yes | Env var documented; default safe (7 days is conservative); negative/zero values rejected. |

### Known Threat Patterns for {asyncio + asyncssh + aiohttp}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Slow-loris SSH probe (host hangs handshake) | Denial of Service | `_run_with_timeout(10s)` per probe + outer `asyncio.wait_for(45s)` per host + `Semaphore(10)` outer + 120s scan ceiling |
| Hostile Proxmox API response (oversized `/cluster/resources` payload) | DoS | aiohttp default response size cap; if needed, add explicit `max_field_size` on `ClientSession`. Currently relies on aiohttp defaults — acceptable for homelab scope. |
| Credential leakage in error messages | Information Disclosure | `sanitize_error()` strips known token patterns; existing pattern at drift_detection.py:336 |
| Malformed `last_seen` causing crash | DoS via crafted DB write | `_parse_last_seen` returns `None` on parse failure; row defaults to `unreachable` (not `missing`) |
| Malformed `fingerprint` JSON in DB | DoS via parse error | `get_all_devices()` already wraps in `try/except json.JSONDecodeError` (database.py:531-535) — sets `fingerprint = {}` on parse failure |
| Hostile VM name with shell metachars in `unknown[].message` | Cross-Site Scripting (if rendered in MCP client) | MCP clients render text content; clients are responsible for escaping. Our `message` field uses backtick-wrapped command; no further escaping at server. |

## Sources

### Primary (HIGH confidence)
- `src/homelab_mcp/drift_detection.py` — current 5-bucket scan_drift implementation, helpers `_classify_credential_failure`, `_reason_message`, single `for row in rows:` loop at line 225, locked envelope key order
- `src/homelab_mcp/proxmox_api.py:22, 33, 36, 557` — `_HOST_CLUSTER_CACHE`, `_RESOLUTION_TELEMETRY_CACHE`, `get_resolution_telemetry`, `/cluster/resources` call
- `src/homelab_mcp/ssh_tools.py:614-691, 863-889` — universal-core fingerprint probes, `_run_with_timeout` helper
- `src/homelab_mcp/sitemap.py:466-542` — `bulk_discover_and_store` Semaphore(10) + asyncio.gather template
- `src/homelab_mcp/database.py:201, 503-549, 537-545` — `last_seen TEXT NOT NULL`, `get_all_devices()` row shape, `eligibility` derivation
- `tests/test_ast_regression.py:447-502, 747-833` — Phase 35 D-15 + Phase 38.1 D-15 AST guard precedents
- `tests/test_drift_detection.py:1-100, 821+` — existing functional tests pattern (`MagicMock` + `AsyncMock` + `patch` of resolver)
- `.planning/phases/38-sitemap-fingerprint-schema/38-CONTEXT.md` — fingerprint schema D-01..D-09 (top-level `kernel_*` / `os_*` / `package_fingerprint` / `capabilities`)
- `.planning/phases/38.1-sitemap-keystore-credential-binding/38.1-CONTEXT.md` — D-08 reason enum, D-15/D-16 AST guard scope, R6 `credential_id` keyword
- `.planning/REQUIREMENTS.md` — DRFT-17/18/19 wording + §Out of Scope (D-04b lock)

### Secondary (MEDIUM confidence)
- Proxmox VE API docs — `https://pve.proxmox.com/pve-docs/api-viewer/index.html#/cluster/resources` (verified A2 keys; standalone vs cluster behavior)
- asyncssh exception hierarchy docs — `asyncssh.Error` base class (A8)

### Tertiary (LOW confidence)
- A5 (outer scan timeout enforcement in current `scan_drift`) — flagged in Open Questions for plan-time confirmation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every primitive is in-tree from prior phases; no new dependencies; no version-currency risk.
- Architecture: HIGH — pre-pass + main loop pattern is the Phase 35 D-07 template applied verbatim; D-11(b) (loop-free helpers) keeps AST guard scope unchanged.
- Pitfalls: HIGH — Pitfalls 1-7 are derived from explicit Phase 38.1 / Phase 38 / Phase 35 lessons-learned in the codebase; not speculation.

**Research date:** 2026-04-27
**Valid until:** 2026-05-27 (30 days; stable substrate, no major library churn expected). Re-validate if Phase 38 schema or Phase 38.1 binding semantics change.

## RESEARCH COMPLETE
