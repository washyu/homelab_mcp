# Phase 44: Sitemap CRUD Completion — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 44-sitemap-crud-completion
**Areas discussed:** Filter API shape, Filter syntax, remove_device identity

---

## Filter API shape

| Option | Description | Selected |
|--------|-------------|----------|
| Single filter | One filter per call: {filter_type, value}. Simpler schema, simpler SQL, easier dry_run. Combining needs two calls or pre-filtering by the agent. Matches existing `purge_failed_discoveries` shape. | ✓ |
| Composite filter object | One call can combine: {hostname_like, last_seen_older_than_days, status} — all keys ANDed. Single round-trip for compound queries. More schema surface, more SQL-builder logic. | |
| Single filter, but require at least one | Hybrid: schema accepts ALL filter keys at top level, handler validates exactly-one-of. Cheap to extend later. | |

**User's choice:** Single filter with enum-typed `filter_type` and matching `value` per filter type.
**Notes:** Compound queries cost two calls or agent-side pre-filtering — accepted trade because homelab single-user use cases are dominated by single-filter calls. Composite remains additive (non-breaking) to add later if needed.

---

## Filter syntax — hostname

| Option | Description | Selected |
|--------|-------------|----------|
| SQL LIKE wildcards | Pass-through to SQL LIKE. `%` and `_`. Exact match is bare hostname. | |
| Glob-style with translation | Accept shell-style globs and translate to SQL LIKE server-side. | |
| Exact match only | No patterns. value is the literal hostname. Forces one call per hostname; loses the `test-*` use case. | ✓ |

**User's choice:** Exact match only.
**Notes:** Simplest possible semantics. `test-*` use case served by `ip_range` (test rig on its own subnet), `last_seen_older_than_days`, or agent walking `get_network_sitemap` + per-row `remove_device`.

---

## Filter syntax — IP-range

| Option | Description | Selected |
|--------|-------------|----------|
| CIDR notation | value is `192.168.1.0/24`-style. Use `ipaddress.ip_network(value, strict=False)` and per-row `ip in net` check. IPv6 + single-IP `/32` for free. | ✓ |
| Explicit start-end range | value is `{start, end}`. More flexible (arbitrary ranges) but loses single-IP convenience and forces dict-shape validation. | |
| Prefix glob | value is `192.168.1.*`. Friendly for /24 boundaries but breaks down on non-byte-aligned subnets and IPv6. | |

**User's choice:** CIDR notation with `ipaddress.ip_network(strict=False)` and Python-side membership filter (NOT SQL string-match).
**Notes:** Rows whose `connection_ip` doesn't parse as an IP (zombie rows) are silently skipped — consistent with the "purge_devices is a precise-match tool" philosophy. IPv6 supported for free.

---

## remove_device identity

| Option | Description | Selected |
|--------|-------------|----------|
| device_id only | `remove_device(device_id, dry_run)`. Matches `decommission_device` exactly. Zero ambiguity (id is surrogate PK; hostnames can drift). | ✓ |
| device_id OR hostname (xor) | Schema accepts EITHER (handler validates exactly-one-of). Saves the lookup round-trip when hostname is known. | |
| device_id required, hostname optional disambiguator | Hostname as extra safety check; handler verifies row's hostname matches before deleting. | |

**User's choice:** `device_id` only.
**Notes:** Symmetry with `decommission_device` over symmetry with `update_device_fingerprint`. Hostname can drift after `discover_and_map` rebinding; `id` is the stable surrogate PK. Small extra round-trip via `get_network_sitemap` eliminates the hostname-collision class of bugs entirely.

---

## Claude's Discretion

The fourth gray area (AST guard scope + preview-tool variants) was not selected for discussion. Defaults proposed and accepted:

- **AST guard scope (D-10):** Body-level check on `handle_remove_device` and the new adapter method `delete_device_by_id`, matching the Phase 37 D-11 / Phase 38.1 D-15 / Phase 40 D-06 idiom. Forbidden-symbol set: `ssh_connect`, `asyncssh` (any name), `subprocess.*` calls (most defensive scope), `keyring.delete_password` / `keyring.set_password` / `delete_credential` / `delete_proxmox_credential`, `decommission_network_device` / `_stop_all_device_services` / `_remove_from_clusters` / `_execute_migration_plan`. New test class `TestPhase44RemoveDeviceCallPath` in `tests/test_ast_regression.py`, one `test_*` per forbidden symbol.
- **Preview siblings (D-11):** Ship both `remove_device_preview` and `purge_devices_preview` as thin `dry_run=True` delegates. `readOnlyHint=True` annotation on each, matching existing `decommission_device_preview` and `update_device_fingerprint_preview` precedent.

Other Claude's-discretion items captured inline in CONTEXT.md `<decisions>` Claude's Discretion section: adapter-method naming, shared filter-helper module placement, AST-guard implementation strategy (visitor walk vs substring match), exact contrast-block wording, `last_seen_older_than_days` value=0 semantics, SQL builder unification, JSON Schema enum constraint on `filter_type`, credential-preservation test mocking strategy, test class naming.

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` section. Highlights:

- Composite/ANDed `purge_devices` filters (additive, non-breaking — defer until use case emerges).
- Hostname pattern matching as a separate `hostname_pattern` filter type.
- Hostname kwarg on `remove_device` (additive xor with device_id).
- Drift report bucket-level "purge candidates" surface that pipes directly into `purge_devices`.
- Auto-purge mode (scheduled sweep for stale `status='error'` rows).
- FK CASCADE on `discovery_history.device_id` (eliminates manual two-step DELETE).
- Tool-description contrast block extracted as a shared module-level constant.
- Bulk `remove_device` (plural, list of device_ids in one call).
- Confirm-token / two-call confirmation flow if MCP clients add the convention.
- Per-VM `remove_device` semantics when v1.7.1 lifecycle hooks add per-VM rows.
