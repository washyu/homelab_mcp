# Phase 36: Drift ↔ Sitemap Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 36-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 36-drift-sitemap-foundation
**Areas discussed:** scan_drift interim behavior

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| scan_drift interim behavior | What does scan_infrastructure_drift return between Phase 36 (foundation) and Phase 39 (detection)? | ✓ |
| Proxmox-host identification in sitemap | How does scan_drift pick Proxmox rows to scan? | (Claude's Discretion in CONTEXT.md — see D-10) |
| update_baseline_after_mutation cleanup | Remove the 3 callsites + function entirely, or stub? | (Claude's Discretion in CONTEXT.md — see D-11) |
| Migration banner & AST meta-test scope | Banner format, AST meta-test forbidden patterns | (Claude's Discretion in CONTEXT.md — see D-08, D-12, D-13) |

**User's choice:** scan_drift interim behavior only. Other three areas deferred to Claude with recommended defaults.

---

## scan_drift Interim Behavior

### Q1: What does scan_infrastructure_drift return after Phase 36 lands but before Phase 37 (shape) and Phase 39 (detection)?

| Option | Description | Selected |
|--------|-------------|----------|
| Stub: empty result | `{status: success, scanned: N, drift: []}`. Iterate sitemap rows, no probe, no cred resolution per-row. Doesn't satisfy SC-2. | |
| Cred-resolution only | Per Proxmox-row in sitemap, call resolve_proxmox_credentials and report which resolved (node/cluster) vs. miss. No probe. Cleanly satisfies SC-2 with smallest possible surface. | |
| 2-bucket interim probe (Recommended) | Per Proxmox-row, resolve creds AND probe /cluster/status. Bucket = probed-OK or unreachable. Two buckets only — no unknown/changed yet. Gives users immediate value the day Phase 36 ships. | ✓ |
| Full 4-bucket envelope | Phase 36 emits the canonical 4-bucket shape (probed-OK, unreachable, unknown=[], changed=[]) with last two empty. Locks shape early but bleeds Phase 37 work. | |

**User's choice:** 2-bucket interim probe (Recommended)
**Notes:** Captured as D-01 in CONTEXT.md. Drives the entire scan_drift rewrite shape.

---

### Q2: What's the per-row record shape inside the 2-bucket probe response?

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal | `{hostname, status: 'probed-ok'\|'unreachable', error: str\|None}`. Smallest surface to lock now. | |
| Mid (Recommended) | `{hostname, connection_ip, scope: 'node'\|'cluster', cluster_name: str\|None, status, error, scan_timestamp}`. Includes resolver telemetry from Phase 34 D-09 — direct SC-2 verification signal. | ✓ |
| Rich envelope | Mid shape + raw /cluster/status payload on probed-OK rows. Larger payload, more shape to refactor in Phase 37. | |

**User's choice:** Mid (Recommended)
**Notes:** Captured as D-02. Resolver telemetry (`scope`, `cluster_name`) makes SC-2 directly verifiable from tool output, not just logs.

---

### Q3: The existing 'no baseline available — register a drift baseline before scanning, or set PROXMOX_HOST...' precondition error in handle_scan_infrastructure_drift — what replaces it?

| Option | Description | Selected |
|--------|-------------|----------|
| Remove the precondition (Recommended) | Empty sitemap returns a successful empty 2-bucket result. Aligns with DRFT-13 (officially Phase 37). Necessary leak to satisfy SC-2 with no env vars. | ✓ |
| Replace text, keep precondition | Keep early-return error but rewrite to 'No Proxmox hosts in sitemap — run discover_and_map'. Satisfies DRFT-15 but DRFT-13 will undo in Phase 37. | |
| Keep but reframe to '0 sitemap rows' | Same as B but error fires only when sitemap is totally empty. Slightly more permissive. | |

**User's choice:** Remove the precondition (Recommended)
**Notes:** Captured as D-03. Documented as a necessary "Phase 37 work leaking into Phase 36" because DRFT-12 SC-2 conflicts with the current precondition.

---

### Q4: scan_infrastructure_drift's tool schema today has `node` and `vm_type` filter params. After Phase 36, what happens to them?

| Option | Description | Selected |
|--------|-------------|----------|
| Leave as inert passthrough (Recommended) | Keep params in schema; document filter semantics stabilize in Phase 37 (DRFT-13). scan_drift accepts but ignores them in Phase 36. No breaking change. | ✓ |
| Remove from schema | Drop both params in Phase 36; Phase 37 reintroduces. Schema-shape regression for any wired client. | |
| Reinterpret as sitemap filters now | `node` becomes 'sitemap hostname filter'; `vm_type` becomes a no-op. Awkward middle ground. | |

**User's choice:** Leave as inert passthrough (Recommended)
**Notes:** Captured as D-04. Schema description gets a one-line note about the inertness; tool surface is otherwise unchanged.

---

## Claude's Discretion (deferred areas with recommended defaults)

| Area | Default chosen | Captured at |
|------|----------------|-------------|
| Proxmox-host identification in sitemap | Per-row `resolve_proxmox_credentials(hostname)` with `CredentialNotFoundError` skip; degenerate rows (status=error, hostname='', 'unknown', None) excluded upfront. Asymmetric registry walk rejected because cluster entries have `hostname=""` (Phase 34 D-02). | D-10, D-10a, D-10b |
| `update_baseline_after_mutation` callsite cleanup | Remove function + 3 callsites entirely. No stubs. v1.7.1 LIFE-01..04 owns lifecycle hooks cleanly. | D-11, D-11a, D-11b |
| Migration banner & AST meta-test scope | Banner mirrors Phase 33 ssh_credentials drop format; no row count. AST meta-test scans `src/homelab_mcp/*.py` for forbidden strings, allows only `migration.py` to retain references. | D-08, D-12, D-13 |
| Test rewrite scope | `tests/test_drift_detection.py` rewrite for 2-bucket; `tests/test_database.py` `TestDriftBaselines` deleted; `tests/test_drift_wiring.py` rewrite/delete; `tests/test_drift_resource.py` shape verify. | D-16 |
| Documentation sweep | Narrow: only `scan_infrastructure_drift` entry in `docs/tool-reference.md` updated. Wider PROXMOX_HOST sweep deferred to Phase 37 / docs phase. | D-19 |

---

## Deferred Ideas

(See `36-CONTEXT.md` `<deferred>` section for the full list.)

Notable items: Phase 37 four-bucket shape, Phase 39 unknown/missing/changed detection, Phase 38 fingerprint schema, v1.7.1 lifecycle hooks, v1.7.2 sitemap tags / role-aware drift, broader PROXMOX_HOST docs sweep.
