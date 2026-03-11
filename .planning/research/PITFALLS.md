# Pitfalls Research

**Domain:** Adding dry-run mode, drift detection, and MCP Resources to an existing Python MCP server
**Researched:** 2026-03-11
**Confidence:** HIGH (codebase analysis + verified against MCP spec + IaC/drift detection community patterns)

> **Note:** This file covers v1.1 Safety & Observability pitfalls. v1.0 pitfalls (SSH TOFU,
> command injection, silent exceptions, connection pooling) are in the git history of this file.

---

## Critical Pitfalls

### Pitfall 1: Dry-Run Preview That Cannot Execute the Real Path

**What goes wrong:** The dry-run implementation is written as a separate code path — a parallel
simulation that approximates what would happen — rather than running the actual execution logic
with writes intercepted. Over time, the simulation drifts from the real path. A user sees a
preview that says "will stop VM pve-101, then delete disk /dev/sdb" and approves. The actual
execution stops VM pve-201 and deletes a different disk. The preview was accurate at the time
it was written but fell behind after a refactor to the real handler.

**Why it happens:** The instinct when adding dry-run to `decommission_device`, `remove_vm`, and
`delete_proxmox_vm` is to write a separate inspection function: read state, describe what would
change, return. This feels clean. But it creates two representations of the same logic.

**How to avoid:** Structure dry-run as a parameter to the existing handler, not a separate
function. The handler checks `dry_run=True` and short-circuits before the mutation step. The
read/validate/plan portion is shared code. Only the final write/commit step is gated. Pattern:

```python
async def decommission_device(..., dry_run: bool = False) -> dict:
    # Shared path: read state, validate, compute impact
    device = await _fetch_device(device_id)
    impact = _compute_impact(device)  # what would be deleted

    if dry_run:
        return {"status": "dry_run", "would_affect": impact, "skipped": True}

    # Real path: only reachable when dry_run=False
    await _execute_decommission(device)
    return {"status": "success"}
```

**Warning signs:**
- Any function named `_preview_*` or `_simulate_*` that duplicates logic from `_execute_*`
- Dry-run tests pass but real execution diverges when you add a new step
- The dry-run result mentions resources by ID but the real execution resolves by name (or vice versa)

**Phase to address:** Dry-run implementation phase. The single-path design must be established
before any destructive operations get dry-run support. Retrofit is painful.

---

### Pitfall 2: Dry-Run Performs Real Side Effects

**What goes wrong:** The dry-run preview claims to be safe but silently performs real operations
as part of "checking" what would happen. Common examples in this codebase:

- Proxmox API authentication (`_authenticate()` in `proxmox_api.py`) is called to check current
  VM state for the preview. Authentication itself writes a session ticket on the Proxmox server.
- SSH connection is established to gather current device state. If `setup_mcp_admin` was part
  of a plan, dry-run would connect and check user existence — but the connection itself leaves
  traces in auth logs and potentially triggers `fail2ban`.
- `discover_and_map` as part of a deploy preview would update the SQLite sitemap.

The user is told "no changes will be made" but changes are made.

**Why it happens:** State-read operations feel side-effect-free but they are not. Proxmox API
calls consume rate limit budget. SSH connections consume file descriptors and appear in auth logs.
Database reads in `NetworkSiteMap` also run schema initialization (`_init_database()`) on every
instantiation — a write.

**How to avoid:**
1. Define precisely what "no changes made" means for this server: no mutations to Proxmox state,
   no mutations to remote host state, no mutations to the local SQLite database.
2. Read operations against Proxmox and SSH are acceptable in dry-run — they gather state to
   compute the preview. Document this explicitly.
3. Database writes are NOT acceptable in dry-run. Pass `read_only=True` to `NetworkSiteMap` when
   running dry-run, or skip sitemap updates entirely.
4. Annotate each destructive handler with what dry-run will and will not do.

**Warning signs:**
- Dry-run tests that check only return value but not SQLite state after execution
- `NetworkSiteMap()` instantiation inside a dry-run code path (it calls `_init_database()`)
- Any `await emit_progress(...)` in the dry-run path that logs "deploying X" (misleads)

**Phase to address:** Dry-run implementation phase. Add a test that runs dry-run and then asserts
the database is unchanged.

---

### Pitfall 3: Drift Detection That Mistakes Transient State for Drift

**What goes wrong:** The drift scanner queries Proxmox or SSH to get current state and compares
it against stored baseline. A VM that is rebooting, a service that is restarting, or a host
temporarily unreachable is flagged as "DRIFTED: VM stopped unexpectedly" or "DRIFTED: service
not running." The user sees an alarm, investigates, finds nothing wrong because the system had
recovered by the time they checked. After several false positives, they stop trusting drift
reports entirely — which defeats the purpose.

**Why it happens:** Infrastructure is not a static snapshot. Point-in-time queries during
transient operations produce states that look like drift but are expected. On-demand scans make
this worse than polling because the timing is unpredictable — a scan might hit exactly during
a service restart.

**How to avoid:**
1. For state drift (VM stopped, service not running): report "possibly drifted" with a
   `last_stable_at` timestamp. Require the anomalous state to persist for N minutes before
   classifying as confirmed drift. For v1.1 on-demand scans, include a `scan_age_warning` in
   the report: "This is a point-in-time scan. Transient states (rebooting, restarting) may
   appear as drift."
2. For config drift (CPU/memory/network changed): this is less transient — config changes
   persist. High confidence classification is appropriate.
3. Track `mcp_last_known_good` timestamps in the database. A drift item is only alarming if
   the last-known-good was more recent than a configurable threshold.

**Warning signs:**
- Drift reports that show the same VM as drifted one minute and healthy the next
- Tests that mock `get_proxmox_vm_status` returning "stopped" and assert the result is
   classified as confirmed drift (should be "suspected drift")
- No `scan_timestamp` in the drift report output

**Phase to address:** Drift detection implementation phase. The baseline storage schema and
drift classification logic must handle transient states from the start — retrofitting
"suspected vs confirmed" later requires schema changes.

---

### Pitfall 4: MCP Resources Returning Stale Data Without Signaling It

**What goes wrong:** `homelab://vms` is registered as an MCP Resource exposing live VM state.
The client reads it and gets a list of VMs with statuses. An hour later, a VM crashes. The
client still has the cached resource content. The client never re-reads it because the server
never sent a `notifications/resources/updated` notification. The AI assistant answers "yes, all
your VMs are running" based on the stale resource.

Since subscriptions are opt-in and many MCP clients (including Claude Desktop as of 2025) do
not support resource subscriptions, the server cannot rely on push notifications to keep clients
current. Resource content is fundamentally pull-based.

**Why it happens:** Adding `@server.list_resources()` and `@server.read_resource()` decorators
feels complete. But the protocol only guarantees freshness at the moment of read. Without either
a subscription push or a client that re-reads regularly, the data ages.

**How to avoid:**
1. Include a `scanned_at` timestamp in every resource's JSON content. Clients see how old the
   data is.
2. For resources that expose live state (VM list, service status), set `mimeType:
   "application/json"` and include `"warning": "Point-in-time snapshot. Re-read for current state."`
3. Implement `notifications/resources/updated` via
   `ctx.session.send_resource_updated(AnyUrl(uri))` when a tool mutation succeeds — at minimum
   after `manage_proxmox_vm`, `control_vm`, `remove_vm`, `deploy_vm`.
4. Do not advertise `subscribe: true` in server capabilities unless notifications are actually
   implemented. An empty capability declaration is worse than omitting it.

**Warning signs:**
- Resource handlers that fetch from Proxmox API without timestamps in the response
- No calls to `send_resource_updated` anywhere in tool handlers after mutations
- Tests that read a resource, mutate state, read again, and never assert the content changed

**Phase to address:** MCP Resources phase. Notification sending must be planned as part of the
resource implementation, not added afterward.

---

### Pitfall 5: ResourceManager.proxmox_session Not Wired Into Handlers (Known Tech Debt)

**What goes wrong:** This is a documented issue in PROJECT.md: the `proxmox_session`
(an `aiohttp.ClientSession` created in `ResourceManager.initialize()`) is never consumed by
`ProxmoxAPIClient`. Every Proxmox tool call creates its own session via `aiohttp.ClientSession()`
inside the handler, ignoring the shared one. The shared session exists but is orphaned.

When v1.1 adds MCP Resources that query Proxmox (e.g., `homelab://vms` reading
`list_proxmox_resources`), if the resource handler also creates its own session, the problem
multiplies. A single `resources/read` call could open a new session, authenticate, query, and
leave the session unclosed if the handler does not use `async with`.

**Why it happens:** The ResourceManager was designed before the ProxmoxAPIClient was written.
The client defaulted to creating its own session because the shared one was not accessible
from the call site. The module-level `get_resource_manager()` was the intended solution but
was never plumbed through to Proxmox handlers.

**How to avoid:** Fix the wiring in the tech debt phase (before MCP Resources are implemented).
`ProxmoxAPIClient.__init__` already accepts `session: aiohttp.ClientSession | None`. The fix
is to pass `get_resource_manager().proxmox_session` at the call site in each Proxmox handler.
This must be done before Resource handlers are written, otherwise Resources will also bypass
the shared session.

**Warning signs:**
- `grep -r "ClientSession()" src/homelab_mcp/proxmox_api.py` returns hits in non-init methods
- `ResourceManager.proxmox_session` is never accessed outside `resource_manager.py` itself
- Any new code in resource handlers that instantiates `aiohttp.ClientSession` directly

**Phase to address:** Tech debt cleanup phase — must precede MCP Resources phase. Resource
handlers will call into the same Proxmox API code and need the session wired correctly.

---

### Pitfall 6: Drift Baseline That Does Not Track "Expected" Changes

**What goes wrong:** User asks MCP to stop VM pve-101 for maintenance. MCP stops it
successfully. The drift scanner runs an hour later and reports: "DRIFT DETECTED: VM pve-101
expected state=running, actual state=stopped." The drift detection cannot distinguish between
"MCP stopped it intentionally" and "it crashed." The user now has a noisy drift report that
always flags everything MCP recently changed as drift.

**Why it happens:** Drift detection compares current state against a stored baseline without
knowing which changes MCP itself made. If the baseline was set before MCP ran the stop command,
the baseline is now intentionally stale.

**How to avoid:**
1. After every successful mutation (tool call that changes infrastructure state), update the
   stored baseline for the affected resource. The baseline should reflect "last known intended
   state," not "initial state."
2. Store `mcp_last_changed_at` and `mcp_last_changed_by_tool` alongside baseline values.
   Drift is only flagged when current state differs from the baseline AND the baseline was set
   after the last MCP mutation.
3. Schema: add `expected_state` and `last_mcp_update` columns to the device/VM tracking tables
   in SQLite.

**Warning signs:**
- Drift reports that flag VMs or services that were recently modified by MCP tools
- No database writes after successful `manage_proxmox_vm` or `control_vm` calls
- Drift schema that stores only a static snapshot with no mutation timestamps

**Phase to address:** Drift detection implementation phase. The baseline update-on-mutation
pattern must be designed before implementing the scanner — the scanner depends on it.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `dry_run` as a flag checked at the top of the function with early return | Quick to add | Preview drifts from real execution as code changes; two code paths to maintain | Never — use the shared-path pattern instead |
| Registering MCP Resources without `notifications/resources/updated` | Simple first implementation | Clients cache stale data with no indication it is stale | Only as an explicitly documented v1.1 limitation with `scanned_at` timestamps in every response |
| Drift baseline as a static table populated once | Simple schema | Every MCP mutation creates false drift alarms; users lose trust in reports | Never for a tool that mutates infrastructure |
| Fixing `proxmox_session` wiring only in ResourceManager without updating call sites | Minimal code change | Resource handlers will bypass the fix and open their own sessions | Never — fix must propagate to all Proxmox call sites |
| Storing drift config snapshot as JSON blob | Easy to extend | No queryability, hard to compare field-by-field, migrations require JSON parsing | Acceptable for v1.1; plan structured columns for v1.2 if drift comparison logic grows |

---

## Integration Gotchas

Common mistakes when connecting these new features to existing code.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Dry-run + `emit_progress()` | Emitting "Deploying X" progress messages during dry-run misleads the AI/user | Gate progress messages behind `if not dry_run:` or use different message prefix "Would deploy X" |
| MCP Resources + `get_resource_manager()` | Resource handlers calling `get_resource_manager()` before lifespan starts during tests | Mock the resource manager or ensure lifespan context is set in test fixtures |
| Drift scanner + `NetworkSiteMap()` | Constructing `NetworkSiteMap()` in drift scanner runs `_init_database()` (a write) | Pass the existing db_adapter from `ResourceManager` instead of constructing a new `NetworkSiteMap` |
| MCP Resources + lowlevel.Server | Declaring `resources` capability in server init but not registering `@server.list_resources()` handler causes protocol errors | Always pair capability declaration with handler registration |
| Dry-run + existing `validate_only=True` parameter | `infrastructure_crud.py` already has `validate_only=True` in several functions; adding a separate `dry_run=True` creates two similar but different modes | Align on one parameter name (`dry_run`) and deprecate `validate_only` in the same phase |
| Tech debt fix + existing 479 tests | Wiring `proxmox_session` into Proxmox handlers changes how tests must mock the session | Update test fixtures in the same PR as the wiring fix; do not split across phases |

---

## Performance Traps

Patterns that work for a homelab but fail under specific conditions.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Drift scan queries all VMs and devices in serial | Scan takes 30-120 seconds on larger homelabs, hits the 45-second `execute_tool` timeout | Use `asyncio.gather()` for parallel Proxmox + SSH queries; increase timeout for drift scan tool | Any homelab with 6+ VMs or 4+ devices |
| Resource `read_resource` that calls Proxmox API synchronously | MCP client UI hangs waiting for slow API; appears unresponsive | Add timeout to resource read; return cached last-scan data if API is slow | Any time Proxmox is under load or network is congested |
| Storing full VM config JSON in drift baseline per-scan | SQLite rows grow unboundedly if scans happen frequently | Store only fields relevant to drift (status, CPU, memory, network config), not full API response | After ~100 scans on a 10-VM homelab, rows become large but still manageable; mainly wastes space |
| Sending `notifications/resources/updated` for every tool call | Noisy; clients that do support subscriptions get flooded | Only send notification when the resource content would actually change (compare hash before/after) | Any client that subscribes to multiple resources and triggers many tools |

---

## Security Mistakes

Domain-specific security issues for dry-run and drift detection features.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Dry-run response includes full VM config / disk layout in "would affect" field | Credential or topology information leak via AI context | Sanitize dry-run output through the same `sanitize_error` / `CredentialFilter` as real responses |
| Drift report exposes Proxmox API token format or SSH private key paths in "config drift" fields | Credential exposure in tool output | Ensure drift comparison excludes credential fields; add credential fields to `CredentialFilter` patterns |
| MCP Resource URI scheme that encodes device IPs directly (`homelab://device/192.168.1.5`) | URI leaks network topology in client logs | Use opaque IDs: `homelab://device/{device_id}` where ID is the SQLite row ID, not the IP |
| API key auth fix (`Fix: API key authentication wired into HTTP transport`) disables auth during the refactor window | Unauthenticated access if deployed mid-refactor | Fix auth in a single atomic commit; add a test that asserts HTTP requests without a valid key are rejected before merging |

---

## UX Pitfalls

How these features will be experienced by the AI assistant and the homelab user.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Dry-run output is a wall of technical JSON | AI cannot summarize it; user gets confused | Structure dry-run output as `{"action": "stop_vm", "target": "pve-101", "reason": "...", "reversible": true}` — human-readable action items |
| Drift report lists every minor config variation as drift | User gets alert fatigue; stops caring about real drift | Distinguish severity: CRITICAL (VM down), WARNING (config changed), INFO (minor variation). Only surface CRITICAL and WARNING by default |
| MCP Resource for VM list includes every Proxmox field | AI includes irrelevant data in context; wastes token budget | Project to a minimal schema: `{id, name, status, node, cpu_cores, memory_mb}` — enough to reason about, not a full API dump |
| "Dry-run succeeded" message with no action summary | User approves without understanding what will happen | Dry-run response must include `"actions": [...]` listing every operation that would execute, ordered by execution sequence |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Dry-run for `decommission_device`:** Often missing cascade impact — what services depend on
  the device. Verify the dry-run output includes dependent services, not just "device would be removed."
- [ ] **Drift detection baseline:** Often missing mutation tracking. Verify that after a successful
  `manage_proxmox_vm` call, the drift baseline for that VM is updated in SQLite.
- [ ] **MCP Resources capability declared:** Often missing actual handler registration. Verify
  `resources/list` returns the declared resources and `resources/read` works for each URI.
- [ ] **`notifications/resources/updated` after mutations:** Often declared as "will implement"
  but never wired. Verify at least one tool handler calls `send_resource_updated` after a
  successful Proxmox or VM state change.
- [ ] **Tech debt: `proxmox_session` wiring:** Fix appears done when `get_resource_manager()` is
  called, but session may still not reach `ProxmoxAPIClient`. Verify with
  `grep -r "ClientSession()" src/homelab_mcp/proxmox_api.py` — should have zero results in
  non-init code after the fix.
- [ ] **Dry-run + existing `validate_only` param:** Two different parameters doing similar things.
  Verify they are aligned or one is removed before the phase closes.
- [ ] **Drift scanner excludes transient states:** Verify the scanner output includes a
  `scan_timestamp` and a disclaimer for state-type drift findings.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Dry-run diverged from real execution path | HIGH | Audit every destructive handler; refactor to single-path pattern; add comparison tests that run both paths and assert they describe the same actions |
| Drift baseline full of false positives from MCP mutations | MEDIUM | Add `mcp_last_changed_at` column; run a migration to set it to `now()` for all existing rows; re-run baseline scan |
| MCP Resources declared but no notifications wired | LOW | Add `send_resource_updated` calls in tool handler post-success paths; no schema change needed |
| `proxmox_session` wiring incomplete; Resource handlers open their own sessions | MEDIUM | Identify all Proxmox API instantiation sites; pass shared session; update all affected mocks in tests |
| Dry-run executing real side effects (db writes, SSH mutations) | HIGH | Add integration test asserting db is unchanged after dry-run; add SSH operation audit; fix each side effect site |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Dry-run diverging from real path | Dry-run implementation | Test: run dry-run then real execution, assert descriptions match |
| Dry-run performing real side effects | Dry-run implementation | Test: run dry-run, assert SQLite unchanged, assert no SSH mutations |
| Drift false positives from transient state | Drift detection implementation | Test: mock VM as "stopped" briefly, assert classified as "suspected" not "confirmed" |
| Drift baseline not updated on mutation | Drift detection implementation | Test: call `manage_proxmox_vm`, assert SQLite baseline row has updated `expected_state` |
| MCP Resources stale without notification | MCP Resources implementation | Test: call tool that changes VM state, assert `send_resource_updated` was called |
| `proxmox_session` not wired | Tech debt cleanup (before Resources phase) | `grep -r "ClientSession()" src/homelab_mcp/proxmox_api.py` returns zero non-init hits |
| `validate_only` vs `dry_run` parameter collision | Dry-run implementation | `grep -r "validate_only" src/` — zero hits after alignment |
| API key auth not wired during fix | Tech debt cleanup | Integration test: HTTP request without API key returns 401 |

---

## Sources

- Direct codebase analysis of `/home/shaun/projects/mcp_python_server/src/` — HIGH confidence
- MCP Resources specification at https://modelcontextprotocol.io/specification/2025-06-18/server/resources — HIGH confidence
- MCP Python SDK `send_resource_updated` / `send_resource_list_changed` patterns (community discussion https://github.com/orgs/modelcontextprotocol/discussions/301) — MEDIUM confidence
- Terraform dry-run (plan vs apply) discrepancy patterns — https://spacelift.io/blog/terraform-dry-run — MEDIUM confidence
- Infrastructure drift detection false positive causes — https://snyk.io/blog/infrastructure-drift-detection-mitigation/ — MEDIUM confidence
- Kubernetes dry-run implementation design (side effects handling) — https://github.com/kubernetes/enhancements/blob/master/keps/sig-api-machinery/576-dry-run/README.md — HIGH confidence (well-established pattern)
- Known MCP client subscription support limitations (Claude Desktop does not support resource subscriptions as of 2025) — https://github.com/orgs/modelcontextprotocol/discussions/391 — MEDIUM confidence

---
*Pitfalls research for: v1.1 Safety & Observability — dry-run, drift detection, MCP Resources, tech debt*
*Researched: 2026-03-11*
