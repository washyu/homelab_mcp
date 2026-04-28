# Phase 39: Drift Detection Cases — Context

**Gathered:** 2026-04-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Fill the `unknown` and `changed` placeholder buckets in `scan_infrastructure_drift` (currently `[]` from Phase 38.1) and add a `missing` sub-status to `unreachable[]`. After this phase, a user running `scan_infrastructure_drift` after a real-world change — manually-created VM, offline NAS, kernel update that regressed Vulkan — sees that change reported in the right bucket with an actionable recovery pointer.

Three drift cases delivered (one requirement each):

- **DRFT-17 unknown:** VMs/LXC present on a Proxmox hypervisor but absent from sitemap → per-VM rows in `unknown[]`.
- **DRFT-18 missing:** Sitemap rows that were reachable but have stopped responding for longer than a configurable threshold → routed to `unreachable[]` with `status: "missing"` and `last_seen` + decommission/purge pointer.
- **DRFT-19 changed:** Live universal-core fingerprint (kernel / OS / package digest) differs from stored sitemap fingerprint → per-field diff in `changed[]`.

Out of this phase:

- Auto-update sitemap when drift detected — locked at REQUIREMENTS.md §Out of Scope (drift reports differences; user accepts via re-running `discover_and_map`).
- Capability sub-key re-probing inline during drift — D-09 below; capability changes surface only when agent re-runs `configure_host_fingerprint`.
- Per-VM fingerprint diffing for the `changed` bucket — host-level only this phase. Per-VM lifecycle is v1.7.1 LIFE-* territory.
- Lifecycle hooks that update sitemap on VM create/destroy — v1.7.1 LIFE-01..04, LIFE-09, LIFE-10.
- Role-aware drift profiles (gateway routing, NAS expected-services) — v1.7.2 TAGS-* + ROLE-*.
- POL-01..03 Proxmox VM lifecycle polish — Phase 40, independent of drift work.

</domain>

<decisions>
## Implementation Decisions

### Missing-bucket placement (DRFT-18)

- **D-01:** `missing` is **NOT a 6th bucket**. Promoted rows stay in `unreachable[]` with `status: "missing"` (instead of `"unreachable"`). Phase 38.1's 5-bucket envelope (`probed_ok` / `unreachable` / `not_eligible` / `unknown` / `changed`) stays intact — DRFT-18's "missing infrastructure bucket" wording is satisfied by the sub-state, not by adding a key. Per-row record gains `last_seen` + a recovery pointer (`decommission_device` or `purge_failed_discoveries`) when `status == "missing"`.
- **D-02:** Threshold for unreachable→missing promotion is configurable via env var `HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS`, default `7`. Sourced from the existing `devices.last_seen` column — no new persistence, no consecutive-failure tracking. Logic: `if (now - last_seen).days > threshold and probe failed: status = "missing"`. Otherwise `status = "unreachable"`.

### Probe strategy for missing/changed (DRFT-18 + DRFT-19)

- **D-03:** Drift probes the **universal-core fingerprint only** inline — three SSH commands per host: `uname -s` (kernel_name), `uname -r` (kernel_version), `cat /etc/os-release` (os_name, os_version), `dpkg -l 2>/dev/null | sort | sha256sum` (package_fingerprint). Same probes as Phase 38 D-04 (re-used, not duplicated). Each wrapped with `_run_with_timeout(conn, ..., timed_out=timed_out_commands)` per Phase 35 D-05. Capability re-probing is **NOT** in drift's scope — capability commands are per-host and probe code can't know what to check (D-09 reconciles).
- **D-04:** Drift SSH-probes **all sitemap rows with `ssh_credential_id` bound** — not just Proxmox hosts. Covers TrueNAS, gateway, Pi-hole, Ollama servers, etc. Rows without `ssh_credential_id` route to `not_eligible` with the existing Phase 38.1 `reason="unbound"` enum. A Proxmox host bound by BOTH `ssh_credential_id` AND `proxmox_credential_id` runs both probes: SSH for fingerprint, Proxmox API for reachability + VM enumeration. Bucket placement priority handles the multi-signal case (D-10).
- **D-04a:** Bulk SSH probes use `Semaphore(10) + asyncio.gather` per Phase 35 D-02 — bounded fanout, identical pattern to bulk discovery. Outer scan timeout follows Phase 35's 120s ceiling.
- **D-04b:** Drift does NOT update the stored fingerprint after probing. The stored fingerprint is only updated by `discover_and_map` (full discovery) or `update_device_fingerprint` (agent-driven). Locked at REQUIREMENTS.md §Out of Scope ("Auto-update sitemap when drift detected"). Changed rows persist across scans until the user accepts via re-discovery — preserves the "kernel update broke Vulkan" alert use case.

### Unknown VM enumeration (DRFT-17)

- **D-05:** VM enumeration uses **`/cluster/resources` once per probed_ok Proxmox host** (cheapest — single API call returns all VMs + LXC across all nodes with vmid, node, name, type, status). Existing pattern at `proxmox_api.py:557`. Per-node `/nodes/{node}/qemu` + `/nodes/{node}/lxc` fallback only when `/cluster/resources` returns an error indicating standalone (non-cluster) Proxmox setup. Cluster-scope rows that share a single Proxmox cluster get one enumeration call total per scan (de-dupe by cluster_name from the existing `get_resolution_telemetry` cache).
- **D-06:** VM-in-sitemap match key is **case-insensitive `VM.name == sitemap.hostname`**. Matches the hostname-as-natural-key convention (Phase 35 D-01). Mismatched-name VMs (e.g., Proxmox name `ubuntu-test`, OS hostname `test.lan`) surface as `unknown` until adopted via `discover_and_map`. The unknown row's `message` field points the user at `discover_and_map <ip>` — adoption resolves the mismatch by writing a sitemap row keyed on the OS hostname. Storing `vmid` on sitemap rows is v1.7.1 LIFE-* territory (lifecycle hooks own VMID-tracking).
- **D-07:** **Per-VM row** in `unknown[]` (NOT per-host with nested vm list). Shape:
  ```
  {
    "hypervisor_hostname": str,        # the Proxmox host that reported this VM
    "node": str,                       # Proxmox node name (cluster member)
    "vmid": int,
    "vm_type": "qemu" | "lxc",
    "vm_name": str,                    # what Proxmox reports as `name`
    "vm_status": str,                  # "running" | "stopped" | etc., from /cluster/resources
    "scan_timestamp": str,             # same value across all records this scan
    "message": str,                    # e.g., "VM 'ubuntu-test' (vmid=110) on node 'pve1' not in sitemap; run discover_and_map <ip-or-hostname> to adopt."
  }
  ```
  Each unknown VM is independently actionable. Unknown[] is a parallel per-VM surface, NOT a host bucket — its rows are independent of where their hypervisor host landed (D-10).

### Changed-diff payload (DRFT-19)

- **D-08:** **Per-field diff pre-computed by drift** (NOT full stored+current blobs). Empty `changed_fields` → no entry; the host stays in `probed_ok`. Per-row record shape:
  ```
  {
    "hostname": str,
    "connection_ip": str,
    "scope": str,                      # carried from probed_ok shape if applicable
    "status": "changed",
    "changed_fields": {
      "kernel_version": {"stored": "6.5.13-1-pve", "current": "6.8.4-2-pve"},
      "package_fingerprint": {"stored": "sha256:abc...", "current": "sha256:def..."},
      "capabilities.vulkan.available": {"stored": true, "current": false},
    },
    "scan_timestamp": str,
    "message": str,                    # e.g., "Kernel + package fingerprint changed; re-run configure_host_fingerprint to refresh capability tracking, then discover_and_map to accept."
  }
  ```
  The `changed_fields` dict uses dotted-path keys for nested capability sub-keys (`capabilities.vulkan.available`) — flat structure, easy to iterate. Planner picks a small helper that walks two dicts and emits dotted-key diffs.
- **D-09:** **Diff scope = universal-core always; capabilities only when present in BOTH stored and current.** Drift never re-probes capabilities (D-03), so the canonical flow is:
  1. Drift probes universal-core → emits `changed_fields` with kernel/os/package diffs.
  2. Agent sees the kernel change → re-runs `configure_host_fingerprint` → re-probes Vulkan via `ssh_execute_command` → writes new `capabilities.vulkan.available: false` to stored.
  3. Next drift scan: stored now has the OLD capability values overwritten — diff against current only fires if the agent's NEW values differ from what the user expected (in practice, the agent's update IS the acceptance, so the next scan shows no capability diff).
  Drift catches the **kernel/package change that motivates re-investigation**; the agent catches the capability regression. This avoids the false-positive trap where every drift scan reports "capabilities removed" because drift didn't probe them.
- **D-09a:** "Present in both" check is per leaf, not per `capabilities.*` sub-tree. If `stored.capabilities.vulkan.available` exists but `current.capabilities` is `{}` (drift didn't re-probe), the leaf is NOT diffed. If a future phase adds capability re-probing, the same leaf-level check still works — keys appearing on both sides get diffed; one-sided keys don't.
- **D-09b:** When the agent updates capabilities via `configure_host_fingerprint` and `update_device_fingerprint`, the deep-merge from Phase 38 D-05 means stored now has BOTH the agent's new capability values AND the universal-core fields from the LAST `discover_and_map`. Subsequent drift scans probe fresh universal-core and diff against that stored snapshot. The capability-acceptance flow is implicit: the agent's write to stored is the acceptance.

### Bucket exclusivity (host-level)

- **D-10:** **Hosts land in exactly one host-level bucket per scan.** Priority order (highest to lowest):
  1. `not_eligible` — credential resolution failed structurally (Phase 38.1 D-08 reasons).
  2. `unreachable` (with `status: "unreachable"` or `status: "missing"` per D-01) — credential resolved, probe raised network/timeout error.
  3. `changed` — probe succeeded AND `changed_fields` is non-empty.
  4. `probed_ok` — probe succeeded AND `changed_fields` is empty.
  Counts dict mirrors bucket sizes; `scanned == sum(counts.values())` invariant holds. `unknown[]` is a per-VM surface independent of host buckets — a host with kernel change AND unknown VMs underneath appears in `changed[]` for the host record AND in `unknown[]` once per unmatched VM.

### AST guard extension (Phase 38.1 D-15 / D-16 carry-forward)

- **D-11:** Phase 38.1 D-15's "no `continue` inside `scan_infrastructure_drift` body" AST guard is extended to cover Phase 39's new helpers. New helpers introduced this phase (e.g., `_probe_universal_core`, `_diff_fingerprints`, `_enumerate_unknown_vms`, `_classify_unreachable`) MUST also be free of `continue` inside their row/VM iteration loops if those loops feed bucket appends. Planner enumerates the new helpers and either: (a) adds each to the existing `_FORBIDDEN_CONTINUE_FUNCTIONS` allowlist in `tests/test_ast_regression.py` (existing pattern) OR (b) refactors helpers to return per-row decisions that `scan_drift` appends, avoiding loops in the helpers entirely. (b) is the cleaner shape; (a) is the fallback.
- **D-12:** AST guard scope stays targeted (named-function list, not whole-file). Matches Phase 35 D-15 / Phase 38.1 D-16 precedent. New guard functions added in this phase get explicit names in the test class.

### Claude's Discretion

- Exact env var name format: `HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS` recommended; planner may pick `HOMELAB_MCP_DRIFT_MISSING_THRESHOLD_DAYS` for namespacing if the existing env-var convention prefers the prefix.
- Whether the universal-core probe code is extracted into a helper (`_probe_universal_core(conn) -> dict`) shared between `ssh_discover_system` (Phase 38 D-04) and `scan_drift` (Phase 39 D-03), or whether `scan_drift` re-implements the four probes inline. **Strongly recommended:** extract a helper to avoid drift between the two probe sites — Phase 38 already defines the canonical command set and `_run_with_timeout` wrapping.
- Whether `_diff_fingerprints` returns a dict-of-dicts (`{field: {stored, current}}`) or a list of records (`[{field, stored, current}, ...]`). Dict-of-dicts recommended for D-08 — matches the "iterate keys, each is a leaf diff" pattern; flatter to consume.
- Whether the per-cluster `/cluster/resources` enumeration is interleaved with the per-row probe loop or hoisted to a single pre-pass. Single pre-pass recommended (one cluster_name → one enumeration; build a `{vm_name_lower: vm_record}` lookup; loop sitemap rows after).
- Exact `message` wording for unknown / missing / changed entries. Templates in D-07 / D-01 / D-08 are starting points — planner polishes for actionability matching Phase 37 D-08 conventions.
- Whether the SSH probe pre-pass parallelism is wired through a new `Semaphore` instance per scan or via a module-level sem. Per-scan instance recommended (no shared state across scans; matches Phase 35 D-02 pattern in `bulk_discover_and_store`).
- Whether `last_seen` updates as a side effect of the universal-core probe succeeding. **Locked NO by D-04b** — but flag in planner risk list for explicit confirmation; if `last_seen` only updates via `discover_and_map`, the missing-promotion threshold (D-02) measures "time since last `discover_and_map`," which is the correct semantic ("when did we last fully verify this host").
- Whether the four universal-core fields use a fixed set of dotted-path keys when emitted in `changed_fields` (`kernel_name`, `kernel_version`, `os_name`, `os_version`, `package_fingerprint`) or whether the diff helper walks them dynamically. Dynamic walk recommended — same code path that diffs `capabilities.*` sub-keys handles top-level keys.

</decisions>

<specifics>
## Specific Ideas

- **Drift catches the kernel change; the agent catches the capability regression.** Pivotal mental model from D-09 discussion. Drift's role is "did the universal-core fingerprint shift?"; the agent's role is "given the shift, did anything I was tracking break?". Capability diffs only fire when the agent re-runs `configure_host_fingerprint` and writes new values that differ from the prior agent-curated snapshot. This avoids the false-positive trap of "every scan reports capabilities removed" that would happen if drift naively diffed full fingerprint blobs without re-probing capabilities.
- **`missing` is a sub-status, not a sixth bucket.** User chose envelope stability over requirement-text fidelity. The 5-bucket shape Phase 38.1 just locked stays unchanged; DRFT-18's "missing infrastructure bucket" satisfied by `status: "missing"` inside `unreachable[]`. Per-row record gains `last_seen` + recovery pointer when promoted.
- **Universal-core probes are reused, not duplicated.** Phase 38 already defined the four canonical probes (uname -s/-r, /etc/os-release, dpkg fingerprint) inside `ssh_discover_system`. Phase 39 extracts the probe block into a shared helper (Claude's discretion above) so drift and discovery share the source-of-truth probe set. If a future phase adds a fifth universal-core probe, both sites get it.
- **`/cluster/resources` over per-node enumeration.** Existing Proxmox API pattern at `proxmox_api.py:557` returns all VMs + LXC across a cluster in one call. Cluster-served rows (Phase 38.1 D-07: cluster-scope credentials, no per-row binding) get one enumeration per cluster_name, not per row.
- **Hostname-natural-key match for unknown VMs.** Mismatched VM-name vs OS-hostname surfaces as `unknown` until adopted via `discover_and_map`. Adoption rewrites the sitemap row keyed on the OS hostname. v1.7.1's lifecycle hooks (LIFE-01..04) will close the loop by populating sitemap rows on VM create — eliminating the `unknown` bucket for VMs the MCP server creates itself.
- **Bucket priority puts changed below unreachable.** A host that's both unreachable AND had its stored fingerprint change is `unreachable` (with `status: "missing"` if past threshold). Reachability diagnosis takes precedence over fingerprint diagnosis — you can't trust a fingerprint diff against a host you can't currently probe.
- **Drift never updates the stored fingerprint.** Locked at REQUIREMENTS.md §Out of Scope. Changed rows persist across scans until `discover_and_map` re-runs and the user accepts the new state. Preserves the "alert, not silent acceptance" UX intent.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 39 lock-ins

- `.planning/ROADMAP.md` §Phase 39 — Phase goal + 4 Success Criteria; the scope anchor.
- `.planning/REQUIREMENTS.md` §Active Requirements (DRFT-17, DRFT-18, DRFT-19) + §Coverage Map ("Manually-created VM not in sitemap" → DRFT-17; "Server offline / unresponsive" → DRFT-18; "Kernel update breaks Vulkan / llama.cpp" → DRFT-19 + DRFT-20) + §Out of Scope ("Auto-update sitemap when drift detected" — locks D-04b; "Per-device drift resources" — locks single-report shape).

### Prior phase decisions (locked, inherited)

- `.planning/phases/36-drift-sitemap-foundation/36-CONTEXT.md` §Decisions — sitemap-as-source-of-truth, per-row credential resolution, scan-path drift architecture.
- `.planning/phases/37-drift-output-shape-error-hygiene/37-CONTEXT.md` §Decisions — 4-bucket envelope (Phase 38.1 added 5th `not_eligible`), counts sub-dict shape, conditional `guidance` field, locked envelope key order, error-message style referencing sitemap CRUD tools.
- `.planning/phases/38-sitemap-fingerprint-schema/38-CONTEXT.md` §Decisions — D-01 single fingerprint JSON column; D-02 top-level structure (kernel_*, os_*, package_fingerprint, capabilities); D-04 universal-core probes inside `ssh_discover_system`; D-04a `_run_with_timeout` wrapping; D-05 `update_device_fingerprint` deep-merge semantics; D-07 `os_info` back-compat; D-09/D-10 adapter round-trip + flatten-on-read.
- `.planning/phases/38.1-sitemap-keystore-credential-binding/38.1-CONTEXT.md` §Decisions — D-08 `not_eligible` reason enum (`unbound`/`binding_stale`/`keyring_desync`/`degenerate`); D-15 AST guard ("no `continue` inside `scan_infrastructure_drift` body"); D-16 targeted-guard scope (extends to Phase 39 helpers per D-11 here); R6 `credential_id` keyword param on resolvers; R7 5-bucket envelope; D-17 degenerate-row routing pattern.
- `.planning/milestones/v1.6-phases/35-sitemap-discovery-reliability-fix-discover-and-map-field-los/35-CONTEXT.md` §Decisions — D-01 hostname-as-natural-key; D-02 `Semaphore(10) + asyncio.gather` for bulk; D-05 `_run_with_timeout(10s)` per-probe wrapping; D-09a `partial: True` payload tag on probe timeout.

### Memory / user feedback

- `~/.claude/projects/C--Users-washy-projects-mcp-python-server/memory/feedback_regression_test_scope.md` — AST meta-tests guard known footguns (D-15/D-16 from Phase 38.1 still apply — Phase 39 extends them per D-11). New-feature paths (unknown enumeration, changed diff helpers) get functional + unit tests; the AST guard rides on the existing `scan_infrastructure_drift` invariant.
- `~/.claude/projects/C--Users-washy-projects-mcp-python-server/memory/project_credential_architecture.md` — keyring-only credential pattern; SSH probes in D-03 / D-04 resolve via `resolve_ssh_credentials` with `credential_id` from the binding (Phase 38.1 R6). No env-var fallback, no `mcp_admin` default.

### Source files (read before changing)

- `src/homelab_mcp/drift_detection.py` — current 5-bucket implementation. The `for row in rows:` loop at line 225 is the surface to extend with: SSH probe pre-pass (D-04 + D-04a), VM enumeration pre-pass (D-05), per-row diff classification (D-08 + D-10). The `not_eligible` shape is already in place; add `unknown[]` and `changed[]` population. The status-string field on `unreachable` records (`"unreachable"` today at lines 272/335) gains `"missing"` per D-01.
- `src/homelab_mcp/proxmox_api.py:557` — existing `/cluster/resources` call (`get_proxmox_cluster_resources` or similar — planner verifies exact function name). Direct template for D-05.
- `src/homelab_mcp/proxmox_api.py:194-240` — `resolve_proxmox_credentials` with `credential_id` keyword (Phase 38.1 D-14). Drift's existing per-row resolution pattern unchanged.
- `src/homelab_mcp/ssh_tools.py` — `ssh_discover_system` universal-core probes (Phase 38 D-04). D-03's helper extraction (Claude's discretion) refactors the four-command probe block into `_probe_universal_core(conn, timed_out_commands) -> dict` that both `ssh_discover_system` and `scan_drift` call. `_run_with_timeout(10s)` wrapping carried into the helper.
- `src/homelab_mcp/ssh_tools.py` — `resolve_ssh_credentials` with `credential_id` keyword (Phase 38.1 D-14). Drift's SSH pre-pass calls this with `row.get("ssh_credential_id")`.
- `src/homelab_mcp/database.py` — `get_all_devices()` returns rows with `ssh_credential_id`, `proxmox_credential_id`, `last_seen`, `fingerprint` (top-level dict) per Phase 38 D-10 + Phase 38.1 R2. No new adapter methods needed for Phase 39 (drift is read-only against the sitemap per D-04b).
- `src/homelab_mcp/sitemap.py` — no changes for Phase 39. `parse_discovery_output` writes the fingerprint Phase 39 reads.
- `tests/test_ast_regression.py` — Phase 38.1 D-15 guard (`TestPhase381CredBinding::test_scan_drift_no_continue_in_row_loop` or similar — planner verifies). Phase 39 D-11 either extends the function-name list or restructures helpers to be loop-free per D-11(b).
- `tests/test_drift_detection.py` (extend, or create if absent — planner verifies) — functional tests for all three drift cases: unknown via fixture mocking `/cluster/resources` to return a VM not in sitemap; missing via fixture with `last_seen` older than `HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS`; changed via fixture with stored fingerprint differing from a mocked SSH probe response.

### External / Proxmox API reference

- `GET /cluster/resources` — returns all VMs + LXC across a cluster with vmid, node, name, type, status, vmstatus. Documented at https://pve.proxmox.com/pve-docs/api-viewer/index.html#/cluster/resources. Already used at `proxmox_api.py:557`.
- `GET /nodes/{node}/qemu` + `GET /nodes/{node}/lxc` — fallback per-node enumeration for standalone (non-cluster) Proxmox hosts. Documented at the same API reference.

### Pattern / architecture reference

- `_run_with_timeout()` (`ssh_tools.py:490-516`) — Phase 35 D-05 per-probe timeout wrapper. Phase 39 D-03 reuses for the universal-core probe extraction.
- `Semaphore(10) + asyncio.gather` bulk-discovery pattern (`bulk_discover_and_store` — planner verifies exact function). Phase 39 D-04a uses the same pattern for the SSH probe pre-pass.
- `sanitize_error()` (`log_filter.py`) — error-message redaction; Phase 39's missing/unreachable error fields use it identically to Phase 36 D-02.
- 5-bucket envelope key order from Phase 38.1 D-08: `status, scan_timestamp, scanned, counts, [guidance,] probed_ok, unreachable, not_eligible, unknown, changed`. Order locked; Phase 39 populates the empty buckets, doesn't re-order.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable assets

- **`scan_drift` in `drift_detection.py`** — 5-bucket envelope already in place; Phase 39 extends the loop body with SSH probe pre-pass + VM enumeration pre-pass + diff classification. The `not_eligible` routing pattern (D-17 from Phase 38.1) is the template for new bucket appends.
- **`_classify_credential_failure` + `_reason_message`** in `drift_detection.py:58-121` — per-bucket-reason enum + human-message helpers. Phase 39 follows the same pattern: a `_classify_probe_outcome(stored, current, last_seen) -> ("probed_ok"|"unreachable"|"missing"|"changed", details)` helper and a `_drift_message(case, hostname, fields) -> str` helper for the per-row `message` field.
- **`/cluster/resources` API call** at `proxmox_api.py:557` — single-call cluster enumeration. Direct reuse for D-05.
- **`_HOST_CLUSTER_CACHE`** at `proxmox_api.py:243-279` — process-lifetime cache that maps hostname → (scope, cluster_name). Phase 39 reuses to de-dupe `/cluster/resources` calls per cluster_name (same cluster_name → one enumeration call total).
- **`resolve_proxmox_credentials` with `credential_id`** (Phase 38.1 D-14) — already plumbed; drift uses identical signature for the SSH pre-pass via `resolve_ssh_credentials`.
- **`update_device_fingerprint` MCP tool** (Phase 38 D-05) — NOT called by drift (D-04b locks "drift never updates stored fingerprint"); but it IS the agent-side path that closes the changed-bucket loop after the agent re-runs `configure_host_fingerprint`.
- **Phase 38.1 D-15 AST guard** — Phase 39's new helpers either get added to the guard's allowlist (D-11(a)) or stay loop-free (D-11(b) recommended).

### Established patterns

- **Per-row classification with reason enum + human message** (Phase 38.1 D-08 + this phase D-08) — both `not_eligible` and `changed` rows carry a structured reason/diff PLUS a sentence the agent can surface.
- **Pre-pass + main loop** for bulk operations (Phase 35 `bulk_discover_and_store`). Phase 39 uses the same shape: SSH probe pre-pass (returns `{hostname: probe_result}` dict), VM enumeration pre-pass (returns `{cluster_name: [vm_records]}` dict), then the existing row loop reads from those pre-pass dicts.
- **AST-guarded "no silent skip"** invariant (Phase 38.1 D-15 / D-16). Phase 39 maintains the invariant by either extending the guard scope or refactoring to keep new helpers loop-free.
- **Hostname-as-natural-key** for sitemap reads/writes (Phase 35 D-01). Unknown-VM matching (D-06) follows.
- **Env-var-driven configuration** (Phase 38.1 D-19's version-stamp file format precedent for migration_state; Phase 36's existing config.py patterns). D-02's `HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS` follows the existing env-var convention.

### Integration points

- **`scan_drift` row loop** (`drift_detection.py:225`) — the surface that grows: SSH probe pre-pass call before the loop, VM enumeration pre-pass call before the loop, per-row classification + bucket routing inside the loop. The `not_eligible` and `unreachable` shape additions (D-01 status field) extend existing append shapes.
- **`get_all_devices()`** is the single sitemap read funnel (Phase 36 D-09). Phase 39 reads `last_seen` and `fingerprint` from the row dicts; both already top-level keys per Phase 38 D-10.
- **`update_device_fingerprint`** is the agent-side write path that closes the changed-bucket loop. Drift never calls it (D-04b); but the changed[] entry's `message` should hint at it via `configure_host_fingerprint` — the agent's natural recovery flow.
- **`resolve_ssh_credentials`** (`ssh_tools.py:80-160`) called in the SSH probe pre-pass with `credential_id=row.get("ssh_credential_id")`. Failures route to `not_eligible` per existing Phase 38.1 D-15/D-17 invariants.
- **`_HOST_CLUSTER_CACHE`** read during VM enumeration pre-pass to group sitemap rows by cluster_name, so each cluster gets one `/cluster/resources` call.

</code_context>

<deferred>
## Deferred Ideas

Captured during 39 discussion — preserved so v1.7.1 / v1.7.2 / v1.8 / future phases pick them up.

- **Per-VM fingerprint diffing in the changed bucket.** Phase 39 ships host-level changed only. Per-VM fingerprints (each VM gets its own kernel/package/capability tracking) belong with v1.7.1's lifecycle-hook scope (LIFE-01..04 ship the create/destroy hooks; per-VM drift would extend Phase 39's pattern to nested VM rows). → **v1.7.1 follow-up.**
- **Storing `proxmox_vmid` + `proxmox_node` columns on sitemap rows.** Would eliminate D-06's name-mismatch unknown-bucket false-positive. Requires schema migration + populate path through `discover_and_map` + lifecycle hook to track VMID changes — the latter is v1.7.1 LIFE-* territory. → **v1.7.1.**
- **Drift re-probing capabilities via stored per-host probe commands.** Would let drift catch capability regressions directly without agent re-investigation. Cost: persisting arbitrary shell commands per host (security review surface) + longer scan time + command-rot maintenance. Considered and rejected this phase in favor of the agent-driven recovery flow (D-09). → **v1.8 candidate, only if agent-driven recovery proves too noisy in practice.**
- **Consecutive-failure tracking for missing promotion.** Phase 39 uses `last_seen`-based threshold (D-02). A more accurate "missing" classifier would track per-host consecutive failed probes (e.g., 3 consecutive failures regardless of time). Requires new persistence (probe history column or table). → **v1.8 candidate if the time-based threshold mis-classifies hosts.**
- **Two-mode drift scan (`--quick` default + `--deep` re-discovery flag).** Phase 39 commits to universal-core-only probing (D-03). A `--deep` mode that re-runs full `discover_and_map` would catch hardware/disk/network changes too. Considered; rejected for scope discipline. Could be added without breaking the envelope. → **v1.8 candidate.**
- **Per-VM unknown bucket flag for which discovery method to use.** D-07's `message` field hints at `discover_and_map <ip-or-hostname>` — but the actual recovery command depends on whether the unknown VM is reachable (network-wise) by the MCP server's discovery layer. A future enrichment could probe the VM's reported IP and pre-populate a "reachable: true|false" hint. → **v1.7.1 / v1.8.**
- **Extracting the universal-core probe block into a public helper for v1.7.1's LIFE-* hooks.** D-03 extracts a private `_probe_universal_core(conn) -> dict` helper. v1.7.1 lifecycle hooks (create_proxmox_vm → populate sitemap row with fingerprint) will likely re-use the same helper. Already noted in Phase 38 deferred ideas; reaffirmed here. → **v1.7.1.**
- **Per-cluster `/cluster/resources` cache TTL across scans.** Phase 39 D-05 calls `/cluster/resources` once per scan per cluster. A future enrichment could cache the result with a short TTL (e.g., 30s) to avoid redundant calls if drift is invoked back-to-back. Premature; observe call patterns first. → **v1.8 candidate.**
- **Auto-promote unknown VM to sitemap with degraded-trust marker.** Instead of leaving unknown VMs as alerts requiring manual `discover_and_map`, an opt-in mode could auto-add them to sitemap with `status: "auto-discovered"` and skip them in subsequent unknown checks. Conflicts with the milestone-locked "alert, not silent acceptance" stance. → **v1.7.2 / role-aware drift.**
- **Drift output `homelab://drift/latest` MCP Resource refresh notification when bucket counts change.** v1.2 Phase 13 shipped the resource; Phase 39's bucket-population changes the counts. The notification fires already on `update`; verify the resource serializer surfaces the new bucket fields. Not a deferral — just a planner check. → **planner verifies during research.**

</deferred>

---

*Phase: 39-drift-detection-cases*
*Context gathered: 2026-04-27*
