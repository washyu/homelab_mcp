# Phase 39: Drift Detection Cases - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-27
**Phase:** 39-drift-detection-cases
**Areas discussed:** Missing-bucket placement, Probe strategy, Unknown VM enumeration, Changed-diff payload shape, Bucket exclusivity

---

## Missing-bucket placement (DRFT-18)

### Where does the promoted row live in the response?

| Option | Description | Selected |
|--------|-------------|----------|
| New `missing[]` 6th bucket | Adds `missing` to envelope alongside `unreachable`. Matches DRFT-18 wording verbatim. Cost: reopens locked 5-bucket envelope. | |
| Same bucket, status flag | Stays in `unreachable[]` with `status: "missing"` instead of `"unreachable"`. Envelope shape unchanged. | ✓ |
| Both — promote to new bucket AND status flag | Most explicit, also most surface area to maintain. | |

**User's choice:** Same bucket, status flag.
**Notes:** Envelope stability beats requirement-text fidelity. Per-row record gains `last_seen` + decommission/purge pointer when `status == "missing"`.

### Threshold and source

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed 7-day default from `last_seen` | No new persistence, no config knob. | |
| Fixed 24-hour default from `last_seen` | Aggressive; catches outages fast but noisy. | |
| Configurable via env var (default 7d) | `HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS=7`; user can tune. | ✓ |
| Consecutive-failure count, not time | Promote after N consecutive failed probes. Requires new persistence. | |

**User's choice:** Configurable env var with 7d default.
**Notes:** "just a check if it has been unreachable for a set amount of time" — sourced from existing `devices.last_seen` column. No new persistence.

---

## Probe strategy for missing/changed

### How deep does drift probe?

| Option | Description | Selected |
|--------|-------------|----------|
| Universal-core only inline (Recommended) | Three Phase 38 probes (uname, /etc/os-release, dpkg fingerprint) wrapped with `_run_with_timeout(10s)`. Capability re-probing left to the agent. | ✓ |
| Full re-discovery per host | Entire `ssh_discover_system` payload. Most thorough; ~30s per host. | |
| Liveness only (uname -r) | Single SSH command. Misses package + capability changes. | |
| Two-mode — quick default + --deep flag | Default liveness; deep flag for fingerprint. Doubles code paths. | |

**User's choice:** Universal-core only inline.

### Which sitemap rows get the SSH probe?

| Option | Description | Selected |
|--------|-------------|----------|
| All sitemap rows (Recommended) | Every row with `ssh_credential_id` binding. Covers Proxmox + NAS + gateway + Pi-hole + etc. Unbound rows route to `not_eligible`. | ✓ |
| Proxmox-bound rows only | Same scope as today; misses NAS/Pi/gateway changes. | |
| All rows; skip if both ssh + proxmox bindings missing | Probe via whichever credential the row is bound to. | |

**User's choice:** All sitemap rows with `ssh_credential_id`.

---

## Unknown VM enumeration (DRFT-17)

### How does drift enumerate VMs/LXC?

| Option | Description | Selected |
|--------|-------------|----------|
| `/cluster/resources` once per cluster (Recommended) | Single API call per cluster returns all VMs + LXC. Per-node fallback for standalone hosts. | ✓ |
| Per-node `/nodes/{node}/qemu` + `/lxc` | Two calls per host. Uniform but more requests. | |
| Both — cluster preferred, per-node fallback | Most robust; most code paths to test. | |

**User's choice:** `/cluster/resources` once per cluster.

### Match key for "in sitemap"

| Option | Description | Selected |
|--------|-------------|----------|
| VM name == sitemap hostname (Recommended) | Cheapest. Hostname-as-natural-key match. Mismatched-name VMs surface as unknown until adopted via `discover_and_map`. | ✓ |
| VMID + node tuple stored on sitemap row | Most precise; requires new schema columns + lifecycle hook (v1.7.1 territory). | |
| Loose match — name OR connection_ip | Catches name mismatches but risks cross-matching on shared IPs. | |

**User's choice:** VM name == sitemap hostname (case-insensitive).

### Per-row shape for unknown[]

| Option | Description | Selected |
|--------|-------------|----------|
| Per-VM row (Recommended) | One unknown[] entry per unmatched VM. Each independently actionable. | ✓ |
| Per-host row with nested vms list | Fewer top-level entries; harder to iterate. | |

**User's choice:** Per-VM row.

---

## Changed-diff payload shape (DRFT-19)

### Diff shape per entry

| Option | Description | Selected |
|--------|-------------|----------|
| Per-field diff, drift pre-computes (Recommended) | `changed_fields: {field: {stored, current}}`. Empty changed_fields → host stays in probed_ok. | ✓ |
| Full stored + current blobs, agent diffs | Larger payload; pushes diff logic to every caller. | |
| Per-field diff plus full blobs as sibling | Both — most flexible, largest payload. | |

**User's choice:** Per-field diff, drift pre-computes.

### Which fields get diffed

| Option | Description | Selected |
|--------|-------------|----------|
| Universal-core + all capabilities sub-keys (initial pick — superseded) | Diff everything. Catches "kernel update breaks Vulkan" verbatim. | |
| Universal-core only | Tighter; capabilities require agent re-investigation. | |
| Universal-core + capabilities only when stored AND current both present | Avoids false positives when probe transiently fails. | |

**User's initial choice:** Universal-core + all capabilities sub-keys.

### Reconcile with D-03 (drift only probes universal-core)

D-09 conflict: if drift never probes capabilities but diffs them, every scan flags every stored capability as "removed."

| Option | Description | Selected |
|--------|-------------|----------|
| Diff only what was probed; capabilities only when present in both stored AND current (Recommended) | Drift catches kernel/package change; agent re-runs `configure_host_fingerprint` to catch capability regression. | ✓ |
| Drift re-probes capabilities via stored per-host probe commands | Catches Vulkan break directly. Cost: persistence of arbitrary shell commands per host. | |
| Universal-core only — drop capability diff entirely | Tightest scope; loses "capability disappeared" signal. | |

**User's choice:** Diff only what was probed.
**Notes:** Pivotal mental model — drift catches the kernel change that motivates re-investigation; the agent catches the capability regression via `configure_host_fingerprint`. Avoids the false-positive trap of "every scan reports capabilities removed."

---

## Bucket exclusivity

### How is a host with multiple drift signals represented?

| Option | Description | Selected |
|--------|-------------|----------|
| Buckets stay exclusive for hosts; unknown VMs are independent per-VM rows (Recommended) | One host-level bucket per row. Priority: `not_eligible` > `unreachable(missing)` > `changed` > `probed_ok`. Unknown[] is parallel per-VM surface. | ✓ |
| Hosts can appear in multiple buckets | Doubles per-host record count; counts dict no longer sums to `scanned`. | |
| Single host bucket + per-row drift_signals list | Avoids duplicate rows but loses iteration simplicity. | |

**User's choice:** Buckets exclusive for hosts; unknown VMs independent per-VM rows.

---

## Claude's Discretion

- Exact env var name format (`HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS` recommended).
- Whether to extract a shared `_probe_universal_core(conn) -> dict` helper between `ssh_discover_system` and `scan_drift` (strongly recommended for source-of-truth probe set).
- `_diff_fingerprints` return shape (dict-of-dicts vs list-of-records — dict-of-dicts recommended).
- Whether `/cluster/resources` enumeration is interleaved with the row loop or hoisted to a single pre-pass (single pre-pass recommended).
- Exact `message` wording for unknown / missing / changed entries — templates in CONTEXT.md are starting points.
- Per-scan `Semaphore(10)` instance vs module-level (per-scan recommended).
- `last_seen` only updates via `discover_and_map`, not via drift's universal-core probe success — locked NO by D-04b but flag for planner risk-list confirmation.
- Whether universal-core fields use a fixed dotted-path key list when emitted in `changed_fields` or whether the diff helper walks them dynamically (dynamic walk recommended — same code path that diffs `capabilities.*`).

## Deferred Ideas

- Per-VM fingerprint diffing in the changed bucket — v1.7.1 follow-up.
- Storing `proxmox_vmid` + `proxmox_node` columns on sitemap rows — v1.7.1 lifecycle territory.
- Drift re-probing capabilities via stored per-host probe commands — v1.8 candidate only if agent-driven recovery proves too noisy.
- Consecutive-failure tracking for missing promotion — v1.8 candidate if time-based threshold mis-classifies.
- Two-mode drift scan (`--quick` default + `--deep` re-discovery flag) — v1.8 candidate.
- Per-VM unknown bucket reachability hint — v1.7.1 / v1.8.
- Extracting universal-core probe helper for v1.7.1 LIFE-* hooks — v1.7.1.
- Per-cluster `/cluster/resources` cache TTL across scans — v1.8 candidate.
- Auto-promote unknown VM to sitemap with degraded-trust marker — conflicts with milestone-locked "alert, not silent acceptance" stance; deferred indefinitely.
- `homelab://drift/latest` MCP Resource serializer surfaces new bucket fields — planner verifies during research.
