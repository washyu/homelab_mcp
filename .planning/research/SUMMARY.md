# Project Research Summary

**Project:** Homelab MCP Server v1.1 — Safety & Observability
**Domain:** MCP server safety features — dry-run mode, infrastructure drift detection, MCP Resources protocol
**Researched:** 2026-03-11
**Confidence:** HIGH

## Executive Summary

The v1.1 milestone adds three distinct safety and observability capabilities to an existing, production-quality Python MCP server: dry-run preview for destructive operations, on-demand infrastructure drift detection, and MCP Resources with subscriptions. All four research files converge on the same conclusion: the existing codebase is well-positioned for these additions. The stack requires only one new runtime dependency (`deepdiff` 8.6.1 for structural comparison), all MCP protocol hooks exist in the installed `mcp[cli] 1.9.4` SDK, and the codebase already has partial implementations of several v1.1 patterns (`validate_only` on infrastructure handlers, `destructiveHint` annotations, SQLite discovery history). The core engineering challenge is disciplined architecture, not new technology.

The recommended approach is to build in dependency order: fix tech debt first (proxmox_session wiring, API key auth), then implement MCP Resources plumbing (registry, fetcher, subscription tracker), then dry-run mode on the six destructive tools, then wire live data into Resources, then add notification dispatch, and finally build the drift detector. This sequencing ensures each phase builds on a stable foundation and avoids the most dangerous integration trap — adding features that silently depend on broken session management. Dry-run can proceed in parallel with Resources plumbing since these two features share no touchpoints.

The critical risks are implementation discipline problems rather than technology unknowns. Dry-run diverging from the real execution path over time is the highest-severity risk; the mitigation is a single shared code path where only the final write step is gated on the `dry_run` flag. Drift detection producing false positives from transient VM states and drift baselines not being updated after MCP mutations are the second and third most dangerous pitfalls — both require the right data model from the start and cannot be easily retrofitted. MCP Resources carrying stale data without signals is a real but low-recovery-cost risk, addressed by including `scanned_at` timestamps and wiring `send_resource_updated` notifications after mutations.

## Key Findings

### Recommended Stack

The existing stack (Python 3.12+, uv, mcp[cli] 1.9.4, asyncssh, aiohttp, SQLite, lowlevel.Server) is unchanged. A single dependency is added: `deepdiff>=8.0.0` (current: 8.6.1, released September 2025, Python 3.9+ compatible) for structural comparison of infrastructure state dictionaries. All alternatives (`jsondiff`, `dictdiffer`) are unmaintained. No dry-run library is appropriate — custom per-handler logic is required to return rich previews. No asyncio pub/sub library is needed for subscriptions since this is a single-client server. See `.planning/research/STACK.md` for detailed rationale.

**Core technologies:**
- `deepdiff 8.6.1`: Infrastructure state comparison — the only maintained library for deeply nested dict diffing with transient field exclusion; `ignore_order=True` and `exclude_paths` handle infrastructure state idioms
- `mcp[cli] 1.9.4` (already installed): MCP Resources API — `list_resources`, `read_resource`, `subscribe_resource`, `unsubscribe_resource` decorators confirmed present; capability auto-detection confirmed
- `stdlib dataclasses`: Drift report data structures — sufficient for internal models; Pydantic is over-engineering for this use case
- `stdlib asyncio + set[str]`: Subscription registry — single-client server needs no fan-out; a plain set of subscribed URIs is correct

**What NOT to add:**
- `drypy` / `dryable` — returns None on dry-run; cannot return rich preview; rejected
- `asyncio-multisubscriber-queue` — multi-subscriber broadcast for a single-client server is over-engineering
- `apscheduler` / `aiocron` — periodic background drift checks are explicitly out of scope for v1.1
- Pydantic as a direct dependency — already transitive; overkill for internal drift models

**Critical version note:** The `subscribe_resource` decorator and `send_resource_updated` session method need verification in the installed `mcp 1.9.4` before implementation begins (see Research Flags).

### Expected Features

Research cross-referenced against MCP spec (2025-11-25), IaC community patterns (Terraform plan, CloudFormation Change Sets, Puppet noop), and direct codebase analysis. See `.planning/research/FEATURES.md` for the full prioritization matrix.

**Must have (v1.1 table stakes):**
- `dry_run: bool` parameter on all six `_DESTRUCTIVE_TOOLS` (`decommission_device`, `remove_vm`, `remove_server`, `delete_proxmox_vm`, `destroy_terraform_service`, `rollback_infrastructure_changes`) — users must see what would happen before approving irreversible operations
- Structured dry-run report with `mode`, `would_affect`, `risk_level`, `reversible` fields — actionable output, not "would execute"
- State drift detection — binary running/stopped check via Proxmox API + SSH probe vs. SQLite last-known state; simpler and higher value than config drift
- Config drift detection — CPU/memory/network compare via Proxmox VM config API vs. stored baseline; requires `deepdiff` and baseline config storage
- `scan_infrastructure_drift` tool — composes both detection types into one on-demand report; on-demand only, not polled
- MCP Resources: `resources/list` and `resources/read` for `homelab://infra/vms`, `homelab://infra/devices`, `homelab://infra/services`, `homelab://infra/proxmox/resources`, `homelab://drift/report`
- Tech debt prerequisites: proxmox_session wiring (load-bearing), API key auth wiring, vm_providers error handling

**Should have (P2, add after v1.1 is validated):**
- Resource subscriptions (`resources/subscribe`) — protocol plumbing ships separately; notifications triggered by explicit scan results and tool mutations, not polling
- `homelab://drift/report` as a fast-read resource returning cached last scan without re-scanning
- Risk classification (`risk_level: high/medium/low`, `reversible: true/false`) derived from existing `destructiveHint` annotations

**Defer (v2+):**
- Background drift polling — explicitly deferred; needs false-positive suppression strategy first
- Full workflow simulation — mock state plus counterfactual execution; high complexity for marginal homelab gain
- `dry_run` on non-destructive tools — adds no value for read-only operations
- Resource versioning and history — unbounded resource list growth; `get_device_changes` tool covers this

### Architecture Approach

The v1.1 architecture adds three new modules (`drift.py`, `resources.py`, optionally `dry_run.py` if preview logic grows complex) alongside targeted modifications to seven existing modules. The existing layered structure (server.py → tool_handlers → domain modules → database/API) is preserved without new abstraction layers. All new components follow existing patterns: `DriftDetector` uses `get_resource_manager()` like existing handlers, `ResourceFetcher` calls existing read-only domain functions, and `SubscriptionTracker` lives on `ResourceManager` for server-lifetime durability. The four MCP Resource SDK hooks are wired directly in `server.py` alongside existing tool handlers.

**Major components:**
1. `resources.py` (NEW) — RESOURCE_REGISTRY (static URI catalog of five resources), ResourceFetcher (maps URI to live query), SubscriptionTracker (which URIs client has subscribed to)
2. `drift.py` (NEW) — DriftDetector class (orchestrates parallel config + state checks via asyncio.gather), ConfigDrift/StateDrift/DriftReport dataclasses
3. `server.py` (MODIFIED) — four Resource handler decorators; `_notify_resource_change()` helper called after successful non-dry-run mutations
4. `resource_manager.py` (MODIFIED) — add `subscription_tracker` property; fix proxmox_session wiring to all Proxmox call sites
5. Domain modules: `vm_operations.py`, `infrastructure_crud.py`, `proxmox_api.py` (MODIFIED) — add `dry_run: bool = False` to six destructive functions; add `dry_run` property to six tool schemas

**Key design decisions from architecture research:**
- Dry-run at domain function level, not as server.py interceptor — previews are domain-specific and must return rich detail
- Resources read from SQLite or fast API responses — slow SSH discovery is a tool call, not a resource read
- Drift scan stores result in module-level cache — `homelab://drift/report` resource returns cached result without re-scanning
- SubscriptionTracker uses `set[str]` not `dict[str, set[str]]` — single-client server; no per-client mapping needed

### Critical Pitfalls

Full analysis in `.planning/research/PITFALLS.md`. Top five by severity and probability:

1. **Dry-run diverging from real execution path** — Instinct is to write a separate `_preview_*` function. Over time it drifts from the real handler. Mitigation: `dry_run` is a parameter to the existing handler, not a separate function. Shared code path up to the mutation step; gate only the final write. Test: run dry-run then real execution, assert they describe the same operations.

2. **Drift baseline not updated after MCP mutations** — After MCP stops a VM intentionally, drift scanner flags it as "VM stopped unexpectedly." Mitigation: update stored baseline after every successful mutation. Add `mcp_last_changed_at` and `mcp_last_changed_by_tool` columns. This schema must be designed before the scanner is written.

3. **Drift detection flagging transient states as confirmed drift** — A VM rebooting during a scan is classified as "DRIFTED: stopped." Mitigation: state drift must be reported as "possibly drifted" with a `scan_timestamp` and point-in-time disclaimer. Config drift (CPU/memory changed) can be classified with high confidence since it persists. Never classify a single point-in-time state failure as "confirmed drift."

4. **MCP Resources returning stale data without signaling it** — Client caches resource content; VM crashes; client never re-reads because server sent no notification. Mitigation: include `scanned_at` timestamp in every resource JSON; wire `send_resource_updated` in tool handlers after successful mutations; do not advertise `subscribe: true` unless notifications are actually implemented.

5. **proxmox_session not wired before Resources are implemented** — Known tech debt bug: ResourceManager creates a shared aiohttp session that ProxmoxAPIClient never uses. Every Proxmox call creates its own session. Mitigation: fix this before MCP Resource handlers are written. If Resources bypass the fix and open their own sessions, unclosed sessions accumulate. Verify fix with `grep -r "ClientSession()" src/homelab_mcp/proxmox_api.py` — zero hits in non-init code after fix.

## Implications for Roadmap

Based on research, the architecture's dependency graph (confirmed in ARCHITECTURE.md) suggests six phases. The ordering is driven by two hard constraints: tech debt fixes are prerequisites for Proxmox-backed features, and the subscription tracker must exist before any notification calls can be made.

### Phase 1: Tech Debt Cleanup
**Rationale:** Three known bugs are prerequisites for features in every subsequent phase. proxmox_session wiring is required for any Proxmox API call in drift detection and Resources. API key auth fix ensures HTTP transport security. vm_providers error handling improves dry-run and drift output quality. These are isolated bug fixes with no dependencies on new features — safest to do first and unblock everything downstream.
**Delivers:** Correct Proxmox session management across all handlers; authenticated HTTP transport; structured error responses from VM providers
**Addresses:** PITFALLS Pitfall 5 (proxmox_session wiring), integration gotcha (API key auth mid-refactor window)
**Avoids:** Session leak accumulation in future Resource handlers; incorrect Proxmox API behavior in drift scanner

### Phase 2: MCP Resources Plumbing
**Rationale:** The SubscriptionTracker must exist on ResourceManager before any notification calls can be made. Implementing with stub ResourceFetcher data lets clients exercise the protocol path immediately and validates SDK integration before real data is connected. Has no dependencies on drift detection or dry-run.
**Delivers:** `resources/list` returning URI catalog; `resources/read` returning placeholder JSON; `subscribe/unsubscribe` working without error; `subscription_tracker` on ResourceManager
**Uses:** `mcp[cli] 1.9.4` — `list_resources`, `read_resource`, `subscribe_resource`, `unsubscribe_resource` SDK decorators
**Implements:** `resources.py` (RESOURCE_REGISTRY, ResourceFetcher stubs, SubscriptionTracker); server.py handler wiring
**Research Flag:** Verify `@server.subscribe_resource()` decorator and `send_resource_updated` method availability in installed mcp 1.9.4 before starting this phase

### Phase 3: Dry-Run Mode
**Rationale:** Lowest coupling of all three feature areas — each domain function change is independent with no shared touchpoints with Phase 2. Can be developed in parallel with Phase 2. Immediately delivers user-visible safety value. Requires no new modules. The `validate_only` precedent in infrastructure_crud.py provides the exact pattern to follow; align naming to `dry_run` and deprecate `validate_only` in this phase to eliminate the parameter collision pitfall.
**Delivers:** All six `_DESTRUCTIVE_TOOLS` accept `dry_run: true` and return structured previews with `mode`, `would_affect`, `risk_level`, `reversible` fields; `validate_only` usage consolidated to `dry_run` throughout
**Addresses:** FEATURES table stakes — dry_run on destructive tools, structured report format
**Avoids:** PITFALLS Pitfall 1 (diverging paths), Pitfall 2 (dry-run performing real side effects), parameter collision (`validate_only` vs `dry_run`)

### Phase 4: MCP Resources — Live Data
**Rationale:** ResourceFetcher calls existing read-only query functions — no new persistence layer. Depends on Phase 2 (registry exists) but adds real data. After this phase, resources return live state and the tool-to-URI mutation mapping becomes concrete knowledge, which Phase 5 requires to know which tool should notify which URI.
**Delivers:** `resources/read` returns real live data for all five URIs: devices (SQLite), VMs (Proxmox API + docker/LXD), services (SSH), proxmox resources (API), drift report (cached placeholder)
**Uses:** Existing `db_adapter.get_all_devices()`, `list_proxmox_resources()`, `list_vms_on_device()` — all read-only functions
**Avoids:** PITFALLS Pitfall 4 (stale data) — include `scanned_at` timestamp in every resource JSON; resource reads query fast paths only (SQLite + Proxmox API), never SSH discovery

### Phase 5: Resource Subscriptions and Notification Wiring
**Rationale:** Requires Phase 4 (live data) to be meaningful. The tool-to-URI mutation mapping (which tool affects which resource URI) is confirmed during Phase 4 implementation. Phase 5 adds `_notify_resource_change()` to server.py and wires it into each mutating handler after successful non-dry-run execution.
**Delivers:** Subscribed clients receive `ResourceUpdated` notifications after any successful mutating tool call; `listChanged` emitted after `ssh_discover` discovers new devices; capability flag correctly declared only once notifications are wired
**Implements:** `_notify_resource_change()` in server.py; post-success wiring in vm_handlers.py, proxmox_handlers.py, infrastructure_handlers.py, network_handlers.py
**Avoids:** PITFALLS — no notifications sent for dry-run executions; no `subscribe: true` capability declared before this phase ships

### Phase 6: Drift Detection
**Rationale:** Most complex feature. Requires SSH connectivity patterns and Proxmox API integration (both confirmed working in Phases 2-5). Building last means notification infrastructure already exists for `homelab://drift/report` and session wiring is correct. The drift baseline schema (what SQLite columns to add, which migration to write) must be designed before any scanner code is written.
**Delivers:** `scan_infrastructure_drift` tool runs full config + state drift scan; returns DriftReport with classified drift items, `scan_timestamp`, and point-in-time disclaimer for state findings; subscribed clients receive `ResourceUpdated` on `homelab://drift/report` after each scan
**Uses:** `deepdiff 8.6.1` for structural comparison with transient field exclusion; `stdlib dataclasses` for DriftReport models; `asyncio.gather()` for parallel device scanning (required to avoid 30-120 second serial scan timeouts)
**Implements:** `drift.py` (DriftDetector, ConfigDrift, StateDrift, DriftReport); `tool_schemas/drift_tools_schema.py`; drift handler; SQLite schema extension for `expected_state`, `last_mcp_update` columns; baseline update in every successful mutating tool handler
**Avoids:** PITFALLS Pitfall 3 (transient state false positives), Pitfall 6 (baseline not updated on mutation) — both require correct data model from the start; Performance Trap (serial scan timeout) — use asyncio.gather

### Phase Ordering Rationale

- Phase 1 before everything: proxmox_session wiring is a load-bearing prerequisite for Phases 4 and 6; fixing it first means Resource handlers and the drift scanner inherit correct session management automatically
- Phase 2 (Resources Plumbing) before Phase 4 (Live Data): registry and SubscriptionTracker must exist before fetcher calls and notification dispatch are added
- Phase 3 (Dry-Run) is independent and can proceed in parallel with Phase 2; the only ordering constraint is that Phase 1 must complete first to avoid compounding the session bug
- Phase 5 (Notifications) after Phase 4 (Live Data): which tools mutate which URIs is only fully clear after ResourceFetcher is implemented
- Phase 6 (Drift) last: most complex, builds on everything, needs a stable platform; Session wiring from Phase 1 and notification infrastructure from Phase 5 are prerequisites

### Research Flags

Phases likely needing deeper research during planning:

- **Phase 2 (MCP Resources Plumbing):** Verify `@server.subscribe_resource()` decorator and `server.request_context.session.send_resource_updated(uri)` availability in installed mcp 1.9.4 before implementation. Run `grep -r "subscribe_resource" .venv/lib/python3.12/site-packages/mcp/` to confirm. If absent, upgrade `mcp[cli]` to a version that includes it before this phase starts.
- **Phase 6 (Drift Detection):** SQLite schema extension for drift baselines needs explicit design before coding — which tables to alter, which columns to add (`expected_state`, `last_mcp_update`, full config JSON blob), and the migration script. Read `src/homelab_mcp/database.py` and `src/homelab_mcp/migration.py` before the phase starts.

Phases with standard patterns (skip research-phase):

- **Phase 1 (Tech Debt):** All three fixes are pure wiring with fully specified correct approaches in STACK.md and PITFALLS.md
- **Phase 3 (Dry-Run):** Pattern is fully specified in ARCHITECTURE.md with code examples; `validate_only` precedent exists in the codebase
- **Phase 4 (Resources Live Data):** Calls existing read-only functions; no new patterns needed
- **Phase 5 (Notifications):** Session method confirmed in SDK source; wiring pattern specified in ARCHITECTURE.md

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Single new dependency (`deepdiff`) verified on PyPI; MCP SDK resource decorators confirmed via API reference and SDK source inspection; all other decisions use existing installed packages; alternatives evaluated and rejected with specific reasoning |
| Features | HIGH | MCP Resources spec verified against official 2025-11-25 docs; dry-run and drift patterns verified against Terraform, CloudFormation, Kubernetes KEP-576; prioritization matrix derived from direct codebase analysis and existing `validate_only`/`destructiveHint` patterns |
| Architecture | HIGH | Directly sourced from MCP SDK lowlevel.Server source inspection (mcp>=1.9.1); all v1.0 patterns confirmed by full source read; build order validated against concrete dependency graph; code examples in ARCHITECTURE.md are verified patterns, not training-data speculation |
| Pitfalls | HIGH | Codebase analysis confirms specific risky patterns (proxmox_session orphan confirmed by grep, `validate_only`/`dry_run` collision confirmed by source); MCP spec confirms stale data risk; IaC community patterns confirm transient drift false positives; recovery costs explicitly estimated |

**Overall confidence:** HIGH

### Gaps to Address

- **MCP subscribe_resource in mcp 1.9.4:** The `subscribe_resource` decorator and notification send method are confirmed in the protocol spec and API reference, but the exact Python SDK method signatures in the installed 1.9.4 version need source inspection before Phase 2 implementation. Mitigation: inspect `.venv` source at phase start; upgrade `mcp[cli]` if needed.
- **Drift baseline SQLite schema:** Research identified what data to store (`expected_state`, `last_mcp_update`, full config JSON blob) but the exact ALTER TABLE migrations and column types require reading the existing `database.py` and `migration.py` before Phase 6 implementation.
- **`remove_server` dry-run scope:** The `remove_server` tool is listed in `_DESTRUCTIVE_TOOLS` but its domain module was not fully analyzed in the research. Confirm which module implements it and whether a `validate_only` path already exists before Phase 3.
- **asyncio.gather timeout strategy for drift scan:** Drift scanner must use `asyncio.gather` with per-device SSH timeouts to avoid the 30-120 second serial scan problem. The exact `asyncio.wait_for` timeout value appropriate for homelab SSH is not specified in research; use the existing tool timeout pattern from `error_handling.py` as the baseline.

## Sources

### Primary (HIGH confidence)
- MCP Resources specification (2025-11-25) — `resources/list`, `resources/read`, `subscribe`, `listChanged` capability structure, notification flow, error code -32002 requirement
- MCP Python SDK API reference — `list_resources()`, `read_resource()` decorator signatures; `send_resource_updated`, `send_resource_list_changed` on ServerSession
- MCP SDK lowlevel.Server source (`mcp>=1.9.1` installed) — `subscribe_resource`, `unsubscribe_resource` decorators; capability auto-detection from SubscribeRequest handler registration
- Project source inspection (all modules read directly) — v1.0 patterns confirmed; existing `validate_only`, `destructiveHint`, `get_resource_manager()`, proxmox_session bug all verified
- PyPI `deepdiff` 8.6.1 — released September 3, 2025; Python 3.9+ requirement; no conflicts with existing deps confirmed
- Kubernetes dry-run design (KEP-576) — shared execution path with write interception; side-effects handling

### Secondary (MEDIUM confidence)
- Spacelift: Infrastructure Drift Detection — config vs. state drift taxonomy, false positive patterns
- Scalr: Understanding Detecting Infrastructure Drift Part 1 — desired vs. actual state framing
- MCP community discussion #301 — `send_resource_updated` patterns from community implementers
- MCP community discussion #391 — Claude Desktop does not support resource subscriptions as of 2025
- Hacker News: In praise of --dry-run — dry-run divergence pitfalls from practitioners
- Snyk: Infrastructure drift detection mitigation — transient state false positive causes
- BoltOps: CloudFormation Change Sets = Dry Run Mode — Change Set pattern and structured preview output

### Tertiary (LOW confidence)
- `drypy` / `dryable` PyPI packages — evaluated and rejected; confirmed unsuitable for rich preview return values

---
*Research completed: 2026-03-11*
*Ready for roadmap: yes*
