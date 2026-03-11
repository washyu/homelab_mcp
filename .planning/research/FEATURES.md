# Feature Research

**Domain:** MCP Server Safety and Observability — Dry-run preview, drift detection, MCP Resources
**Researched:** 2026-03-11
**Confidence:** HIGH (MCP Resources spec verified against official 2025-11-25 docs; drift patterns verified against multiple IaC sources; dry-run patterns verified against Terraform, CloudFormation, Puppet precedents)

---

## Context: What Already Exists

The server already ships 49 tools with `readOnlyHint`, `destructiveHint`, and `idempotentHint` annotations. Several
infrastructure handlers already accept a `validate_only` boolean parameter (`deploy_infrastructure_plan`,
`decommission_network_device`, `update_device_configuration`, `scale_infrastructure_services`). The
`ResourceManager` class manages the aiohttp session and SQLite database lifecycle. The `get_device_changes()`
database method tracks discovery history via SHA hashes, giving an existing foundation for drift detection.

This research is scoped to: **dry-run modes**, **drift detection**, and **MCP Resources**. It maps table stakes vs.
differentiators specifically for the v1.1 milestone.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features the target audience (homelabbers, AI clients using the server) expects. Missing these makes the v1.1
milestone feel incomplete or unsafe.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `dry_run` parameter on all destructive tools | Six tools are annotated `destructiveHint=True`. Users need "show me what would happen" before deleting a VM or decommissioning a device. Terraform plan, CloudFormation Change Sets, and Puppet noop all set this expectation. | MEDIUM | Infrastructure handlers already pass `validate_only` to the business layer; VM and Proxmox handlers do not yet. The six `_DESTRUCTIVE_TOOLS`: `decommission_device`, `remove_vm`, `remove_server`, `delete_proxmox_vm`, `destroy_terraform_service`, `rollback_infrastructure_changes`. |
| Structured dry-run report format | A preview must return actionable detail — not "would execute". Industry standard returns what *would* change, what *would* be deleted, and estimated impact. | LOW | JSON response with `mode: "dry_run"`, `would_affect`, `risk_level`, `reversible` fields. Handlers return the action plan, not the execution result. |
| On-demand drift scan tool | Users need a way to ask "is my infra as I last saw it?" after manual changes. This is the `terraform refresh + plan` pattern applied to homelab. | MEDIUM | New `scan_infrastructure_drift` tool. Compares live state (SSH probe + Proxmox API) to SQLite last-known state. Returns structured report. |
| Config drift detection | Detect when CPU, memory, disk, or network config changed outside MCP (e.g., manually via Proxmox UI). "Expected config != actual config." | HIGH | Requires a stored baseline (last MCP-managed values) and a live-query function per device/VM. SHA-hash approach already used in `store_discovery_history` needs extending to store full config dicts for field-level diffing. |
| State drift detection | Detect when services or VMs are offline unexpectedly — "expected running != actually running". Simpler than config drift (binary check). | MEDIUM | SSH service-status probe + Proxmox status API. Compares last known `running/stopped` state to current. |
| MCP Resources: `resources/list` | MCP spec (2025-11-25, verified) requires servers to declare a `resources` capability and respond to `resources/list`. Clients (Claude Desktop, etc.) surface resources to users as context. | MEDIUM | Implement `@server.list_resources()` decorator. Expose VM list, device inventory, service status as named resources with custom URIs like `homelab://vms`, `homelab://devices`, `homelab://services/{name}`. |
| MCP Resources: `resources/read` | Clients that discover resources via `resources/list` must be able to fetch content via `resources/read`. A server that lists but cannot read is broken per spec. | LOW | Implement `@server.read_resource()` decorator. Each URI dispatches to the appropriate live-query (Proxmox API, SSH probe, SQLite). Returns JSON content with `mimeType: "application/json"`. |
| `resources` capability declaration | The MCP SDK server must include `{"capabilities": {"resources": {}}}` in the `initialize` response. Without it, clients will not attempt resource operations. | LOW | One-time server capability registration. The MCP SDK lowlevel.Server advertises the capability automatically when `@server.list_resources()` and `@server.read_resource()` handlers are registered. |
| Error code `-32002` for unknown resource URI | MCP spec requires this specific JSON-RPC error code for resource-not-found. Using wrong codes breaks client compatibility. | LOW | Standard guard in `read_resource` handler. |

### Differentiators (Competitive Advantage)

Features that go beyond what is expected and align with the "trustworthy AI infra management" positioning.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Risk classification in dry-run output | Show `risk_level: high/medium/low` and `reversible: true/false` alongside what would happen. Most tools only report *what*, not *how bad*. | LOW | Derive directly from existing `destructiveHint` and `idempotentHint` annotations already on each tool. No new data source needed. |
| Drift report with root-cause hints | Instead of "CPU changed from 2 to 4", output "CPU changed — possible cause: Proxmox live resize, manual edit via UI, or VM migration" | MEDIUM | Heuristic mapping of common drift sources to human-readable explanations. Increases operator trust in the scan result. |
| MCP Resource subscriptions (`resources/subscribe`) | Clients can register for change notifications. When a VM goes offline or drift is detected by a scan, the server pushes `notifications/resources/updated`. Most MCP servers do not implement this. | HIGH | Requires a subscription registry (in-memory dict) and asyncio notification dispatch. In v1.1, trigger notifications from explicit scan results only — do not poll. Protocol plumbing can ship before full auto-detect. |
| `listChanged` notification after device discovery | When `ssh_discover` runs and adds new devices, emit `notifications/resources/list_changed` so clients refresh their resource picker without polling. | LOW | Fire-and-forget notification after `discover_and_store` completes. Depends on subscription infrastructure being wired first. |
| Drift scan exposed as both tool and resource | `scan_infrastructure_drift` is a tool (imperative, triggers a scan) and `homelab://drift/latest` is a resource (the last report, readable without re-running). Dual exposure maximizes client flexibility. | LOW | Store the last drift report in SQLite or memory. Resource read returns it without re-scanning. Complements rather than duplicates the tool. |
| Dry-run preview as a readable resource | After calling a destructive tool with `dry_run: true`, the preview is also accessible as `homelab://dry-run/{device_id}`. Lets clients cache the preview for human-confirmation workflows. | LOW | Store last dry-run result per device_id. Expose via resource URI template. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Auto-polling drift detection (background loop) | "Tell me as soon as something drifts" sounds ideal | Requires a persistent async loop, SSH connections constantly reconnected, and creates noisy notifications for transient states (VM rebooting = false positive drift). PROJECT.md explicitly deferred this. | On-demand `scan_infrastructure_drift` tool. Use resource subscriptions to notify *after* a scan completes, not from a poller. |
| `dry_run` on read-only tools | Asking "what would `get_network_sitemap` do in dry-run?" adds no value — read-only tools do not change state | Adds `dry_run` to 21 tools that do not need it; clutters schemas; confuses AI clients that read tool descriptions | Restrict `dry_run` exclusively to tools annotated `destructiveHint=True` (the six `_DESTRUCTIVE_TOOLS`). |
| Full workflow simulation (dry-run beyond destructive) | "Simulate the entire deploy pipeline" | Requires mock state, counterfactual execution, and test doubles for SSH and Proxmox — effectively a parallel simulation environment. Massive complexity for marginal gain. | Dry-run scoped to the destructive terminal step only. The mutating-non-destructive tools already have `validate_only` where meaningful. |
| Resource versioning and history via Resources | Expose every past state snapshot as a separate resource | Unbounded resource list growth; pagination required; clients become confused by hundreds of historical snapshots | Single `homelab://drift/latest` resource plus the existing `get_device_changes` tool for history. Keep the resource list small and predictable. |
| Automated remediation after drift | "Fix it when you detect it" | Unattended automated changes to production infra is exactly the risk the safety milestone exists to reduce | Report drift clearly with actionable detail. Let the operator decide whether to run the corrective tool. MCP clients handle this interaction loop natively. |
| Resource templates for every tool parameter | Expose every tool input as a parameterized resource | Creates a very large resource surface; most MCP clients do not yet navigate templates well; maintenance burden is high | Four concrete, high-value resources: VMs, devices, services, drift. Use URI templates only for services since users query individual services by name. |

---

## Feature Dependencies

```
[dry_run flag on destructive tools]
    └──requires──> [validate_only path in business logic for VM/Proxmox handlers]
                       └──requires──> [structured dry-run report format]

[config drift detection]
    └──requires──> [stored baseline config dict in SQLite]
                       └──requires──> [live-query function per device/VM]

[state drift detection]
    └──requires──> [last-known state in SQLite] (partially exists via discovery_history)
                       └──requires──> [live SSH/Proxmox probe at scan time]

[on-demand drift scan tool]
    └──requires──> [config drift detection]
    └──requires──> [state drift detection]

[MCP Resources: resources/read]
    └──requires──> [MCP Resources: resources/list]
                       └──requires──> [resources capability declaration]

[resource subscriptions (resources/subscribe)]
    └──requires──> [MCP Resources: resources/list]
    └──requires──> [MCP Resources: resources/read]
    └──requires──> [subscription registry (in-memory dict)]

[listChanged notification after ssh_discover]
    └──requires──> [resource subscriptions infrastructure]
    └──enhances──> [MCP Resources: resources/list]

[homelab://drift/latest resource]
    └──requires──> [on-demand drift scan tool]
    └──requires──> [MCP Resources: resources/read]

[homelab://dry-run/{device_id} resource]
    └──requires──> [dry_run flag on destructive tools]
    └──requires──> [MCP Resources: resources/read]

[risk classification in dry-run output]
    └──enhances──> [dry_run flag on destructive tools]
    └──requires──> [existing tool_annotations data] (already built, no new work)

[ResourceManager proxmox_session fix (tech debt)]
    └──enables──> [config drift detection via Proxmox API]
    └──enables──> [state drift detection via Proxmox API]

[API key auth fix (tech debt)]
    └──enables──> [MCP Resources: resources/read via HTTP transport]
```

### Dependency Notes

- **Dry-run requires validate_only in VM/Proxmox handlers**: Infrastructure handlers already have this path. VM handlers (`remove_vm`, `remove_server`) and Proxmox handlers (`delete_proxmox_vm`) do not. Extend those before exposing the `dry_run` flag on those tools.
- **Drift scan requires both detection types**: Config drift and state drift are separate checks but both feed the single scan report. Build as separate internal functions, compose in the scan tool.
- **resources/read requires resources/list**: The MCP SDK lowlevel.Server registers both handlers together. Implementing one without the other is a spec violation. Always implement as a pair.
- **Subscriptions are isolated from basic Resources**: The subscription registry is in-memory and optional per spec. It does not block the simpler resources/list + resources/read implementation. Add incrementally.
- **Tech debt fixes are load-bearing**: `proxmox_session` wiring and API key auth are prerequisites for any feature that touches Proxmox state. If these are not fixed first, drift detection via Proxmox will silently use incorrect sessions.

---

## MVP Definition

### Launch With (v1.1)

Minimum scope to deliver the milestone goal: "trustworthy for real use."

- [ ] **Fix ResourceManager proxmox_session wiring** — prerequisite for Proxmox-backed features; drift detection depends on correct session
- [ ] **Fix API key auth in HTTP transport** — prerequisite for authenticated resource access; known bug from v1.0
- [ ] **Fix vm_providers error handling** — replace raw `str(e)` with structured errors; improves dry-run and drift output quality
- [ ] **`dry_run` parameter on all six `_DESTRUCTIVE_TOOLS`** — consistent UX; extends `validate_only` path in infrastructure handlers, adds it to VM and Proxmox handlers
- [ ] **Structured dry-run report format** — JSON with `mode`, `would_affect`, `risk_level`, `reversible` fields; feeds AI confirmation workflows
- [ ] **State drift detection** — SSH + Proxmox status probe vs. last-known state in SQLite; binary online/offline, running/stopped check; simpler and higher value than config drift
- [ ] **Config drift detection** — CPU/memory/network config compare via re-SSH discovery + Proxmox VM config API vs. stored baseline
- [ ] **`scan_infrastructure_drift` tool** — composes state and config drift into one report; on-demand, not polled
- [ ] **MCP Resources: `resources/list` and `resources/read`** — expose `homelab://vms`, `homelab://devices`, `homelab://services/{name}` with live data; declare `resources` capability

### Add After Validation (v1.x)

- [ ] **Resource subscriptions (`resources/subscribe`)** — implement protocol plumbing; trigger notifications from scan results not from polling; emit `listChanged` after `ssh_discover` discovers new devices
- [ ] **`homelab://drift/latest` resource** — stores last scan report; readable without re-running; complements the tool
- [ ] **`homelab://dry-run/{device_id}` resource** — stores last dry-run preview per device; supports AI confirmation workflows

### Future Consideration (v2+)

- [ ] **Background drift polling** — only when explicit user demand exists; needs false-positive suppression strategy first; explicitly deferred in PROJECT.md
- [ ] **Full workflow simulation** — mock state plus counterfactual execution; high complexity, unclear ROI for single-operator homelab; explicitly deferred in PROJECT.md

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| proxmox_session wiring fix | HIGH (correctness, load-bearing) | LOW | P1 |
| API key auth fix | HIGH (security) | LOW | P1 |
| vm_providers error handling fix | MEDIUM (quality) | LOW | P1 |
| `dry_run` on destructive tools | HIGH | MEDIUM | P1 |
| Structured dry-run report | HIGH | LOW | P1 |
| State drift detection | HIGH | MEDIUM | P1 |
| `scan_infrastructure_drift` tool | HIGH | MEDIUM | P1 |
| MCP Resources: list + read | HIGH | MEDIUM | P1 |
| Config drift detection | MEDIUM | HIGH | P1 |
| Risk classification in dry-run output | MEDIUM | LOW | P2 |
| Resource subscriptions | MEDIUM | HIGH | P2 |
| `homelab://drift/latest` resource | MEDIUM | LOW | P2 |
| `homelab://dry-run/{device_id}` resource | LOW | LOW | P2 |
| Drift report root-cause hints | LOW | MEDIUM | P3 |
| Background drift polling | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for v1.1 launch
- P2: Should have, add when P1 is stable and validated
- P3: Nice to have, future consideration

---

## Domain Behavior: How These Features Work

### Dry-Run Mode

**Verified pattern (Terraform plan, CloudFormation Change Sets, Puppet noop):** A dry-run is a second pass through the
same execution path with side effects suppressed. It does NOT create a separate simulation. The same business logic
runs with a `dry_run=True` flag that causes I/O calls (SSH writes, Proxmox API mutations) to be skipped, and their
*would-be* results are returned instead.

**Critical implementation note (sourced from Hacker News post-mortems):** The underlying logic must be factored cleanly
so side-effect points are isolated. If SSH writes and Proxmox mutations are not separated from the read/compute path,
dry-run support degrades into `if dry_run / else` soup with high bug risk. The correct pattern: collect the action
plan first (pure computation), then execute it (side effects). Dry-run returns the plan, not the execution result.

**Existing `validate_only` precedent in this codebase:** `deploy_infrastructure_plan`, `decommission_network_device`,
`update_device_configuration`, and `scale_infrastructure_services` already have this pattern. The new `dry_run` flag
on destructive tools should follow the same approach and unify naming to `dry_run` throughout.

**Expected output structure:**
```json
{
  "mode": "dry_run",
  "tool": "decommission_device",
  "device_id": 42,
  "would_affect": [
    "Device 42 removed from SQLite inventory",
    "SSH keys revoked on 192.168.1.50",
    "Entry removed from network sitemap"
  ],
  "risk_level": "high",
  "reversible": false,
  "warnings": ["No backup found for device 42"]
}
```

**Scope boundary:** Dry-run applies only to the six `_DESTRUCTIVE_TOOLS`. The 21 read-only tools need no dry-run.
The 22 mutating-non-destructive tools already have `validate_only` where meaningful and are out of scope here.

### Drift Detection

**Two distinct detection types (standard IaC terminology, multiple verified sources):**

1. **State drift** (simpler): Last known state = "running". Current state = "stopped". Detect via Proxmox status API
   (`GET /nodes/{node}/qemu/{vmid}/status/current`) or SSH `systemctl is-active` probe. Binary comparison. Fast.

2. **Config drift** (complex): Last known CPU = 2, RAM = 4096 MB. Current = CPU 4, RAM 8192 MB. Detect via Proxmox VM
   config API (`GET /nodes/{node}/qemu/{vmid}/config`) and/or re-running SSH hardware detection. Requires storing the
   baseline as a full config dict (not just a hash) for field-level diffing.

**Baseline storage:** The existing `store_discovery_history` and `get_device_changes` pattern stores SHA hashes of
discovery data. For drift detection, extend the SQLite schema to store the last full config dict so field-level
diffing is possible. The hash remains useful for fast "anything changed?" checks before doing the full diff.

**Expected drift report structure:**
```json
{
  "scan_time": "2026-03-11T12:00:00Z",
  "devices_checked": 12,
  "vms_checked": 8,
  "drift_detected": true,
  "drift_items": [
    {
      "device_id": 5,
      "hostname": "proxmox-node-1",
      "drift_type": "config",
      "field": "memory_mb",
      "expected": 4096,
      "actual": 8192,
      "last_seen": "2026-03-10T08:00:00Z"
    },
    {
      "device_id": 3,
      "hostname": "pihole",
      "drift_type": "state",
      "field": "status",
      "expected": "running",
      "actual": "stopped",
      "last_seen": "2026-03-11T06:00:00Z"
    }
  ]
}
```

### MCP Resources

**Protocol behavior (verified against MCP spec 2025-11-25, official documentation):**

- Server declares `{"capabilities": {"resources": {"subscribe": true, "listChanged": true}}}` in `initialize`
- `resources/list` returns Resource objects with `uri`, `name`, `description`, `mimeType`, optional `annotations`
- `resources/read` returns content for a URI (text or binary blob); returns error code `-32002` for unknown URIs
- `resources/subscribe` lets clients request `notifications/resources/updated` when a resource changes
- `notifications/resources/list_changed` emitted when the set of available resources changes (e.g., after device discovery)

**SDK integration (verified against MCP Python SDK README):** The `lowlevel.Server` provides `@server.list_resources()`
and `@server.read_resource()` decorators that mirror the `@server.list_tools()` and `@server.call_tool()` pattern
already in use in `server.py`. No architecture change required. Handlers go alongside existing tool handlers.

**Recommended resource URIs for this server:**
- `homelab://vms` — live VM list from Proxmox (or Docker/LXD)
- `homelab://devices` — device inventory from SQLite plus last discovery data
- `homelab://services/{name}` — individual service status via SSH (URI template)
- `homelab://drift/latest` — last drift scan report (P2, after scan tool ships)

**Content type:** `application/json` for all resources. Return the same structured dicts the tools return. MCP clients
consuming these resources are AI assistants that parse JSON natively. The `audience: ["assistant"]` annotation is
appropriate for all homelab resources.

---

## Sources

- [MCP Resources specification (2025-11-25)](https://modelcontextprotocol.io/specification/2025-11-25/server/resources) — HIGH confidence, verified directly
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — HIGH confidence, decorator syntax confirmed via README fetch
- [Spacelift: Infrastructure Drift Detection](https://spacelift.io/blog/drift-detection) — MEDIUM confidence, patterns align with Terraform/Pulumi standard
- [Scalr: Understanding Detecting Infrastructure Drift Part 1](https://scalr.com/learning-center/understanding-detecting-infrastructure-drift-part-1/) — MEDIUM confidence, config vs. state drift taxonomy
- [Hacker News: In praise of --dry-run](https://news.ycombinator.com/item?id=27263136) — MEDIUM confidence, implementation pitfalls from practitioners
- [BoltOps: CloudFormation Change Sets = Dry Run Mode](https://blog.boltops.com/2017/04/07/a-simple-introduction-to-aws-cloudformation-part-4-change-sets-dry-run-mode/) — MEDIUM confidence, pattern confirmation
- [Pulumi: Day 2 Operations Drift Detection](https://www.pulumi.com/blog/day-2-operations-drift-detection-and-remediation/) — MEDIUM confidence, desired vs. actual state framing

---

*Feature research for: MCP Server Safety and Observability (v1.1 milestone)*
*Researched: 2026-03-11*
