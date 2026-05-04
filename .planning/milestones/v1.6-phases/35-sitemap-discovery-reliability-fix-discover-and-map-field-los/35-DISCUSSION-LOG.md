# Phase 35: Sitemap + Discovery Reliability - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 35-sitemap-discovery-reliability-fix-discover-and-map-field-los
**Areas discussed:** Zombie row upsert key, Per-subprocess SSH timeout

---

## Gray Area Selection

The orchestrator proposed 4 candidate gray areas based on the ROADMAP Phase 35 description:

| Area | Selected |
|------|----------|
| Discovery schema reconciliation (field-loss: cpu.count ≠ cpu.cores; memory.free/disk.filesystem/mount missing; usb/pci/block absent from schema) | |
| Zombie row upsert key (hostname+IP match produces duplicates on DHCP change) | ✓ |
| Per-subprocess SSH timeout (~10 sequential conn.run calls; bulk iterates serially; 8×30s = 4 min) | ✓ |
| Null-threshold defensiveness (analyze_network_topology + suggest_deployments mix guard styles) | |

Discovery schema reconciliation and Null-threshold defensiveness were consolidated into Claude's Discretion at the end (see final question below).

---

## Zombie Row Upsert Key

### Q1: When a known hostname is re-discovered with a different connection_ip, what should the upsert do?

| Option | Description | Selected |
|--------|-------------|----------|
| Match on hostname only, update IP in place | SELECT id WHERE hostname = ?. Overwrite connection_ip on UPDATE. Hostname becomes natural key. | ✓ |
| Match on hostname OR connection_ip | SELECT ... WHERE hostname = ? OR connection_ip = ?. Handles hostname-change too. Tiebreaker needed. | |
| Keep hostname+IP, add reconciler step | Leave store_device unchanged; add separate reconcile pass to collapse duplicates. | |

**User's choice:** Match on hostname only, update IP in place
**Notes:** Recommended option. Cleanest fix; matches the "one host = one sitemap row" mental model.

### Q2: Zombie rows already exist in some users' DBs — what do we do on first run with the fix?

| Option | Description | Selected |
|--------|-------------|----------|
| Migration: collapse duplicates on hostname, keep most-recent last_seen | One-time pass: keep greatest last_seen row per hostname; merge non-null fields; delete siblings. Idempotent. | ✓ |
| Log warning, leave existing zombies alone | New discoveries correct; old zombies remain. | |
| Add a new cleanup MCP tool / CLI subcommand | Ship prune_sitemap_duplicates tool; explicit user action. | |

**User's choice:** Migration: collapse duplicates on hostname, keep most-recent last_seen
**Notes:** Matches Phase 33's DROP TABLE startup migration pattern (D-01). Non-null merge prevents info loss.

### Q3: Should we track per-host IP history for audit/debugging?

| Option | Description | Selected |
|--------|-------------|----------|
| No — discovery_history already stores full JSON snapshots | Existing discovery_history table carries per-discovery JSON including connection_ip; IP timeline queryable already. | ✓ |
| Yes — add ip_history JSON column on devices table | Convenient for quick queries without scanning history. Adds migration. | |
| Punt to a future phase | Note as deferred idea. | |

**User's choice:** No — discovery_history already stores full JSON snapshots
**Notes:** Avoids adding a second audit surface. IP-change queries still possible via discovery_history.

### Q4: Stale sitemap rows (hosts never re-discovered) — prune or leave?

| Option | Description | Selected |
|--------|-------------|----------|
| Leave alone in this phase | Separate decision (retention window, soft vs hard, opt-in vs automatic). Deferred. | ✓ |
| Add stale prune to migration + expose a tool | prune_stale_devices CLI/MCP tool, 90d default. | |
| Soft-delete flag only | is_stale column set when last_seen > N days; filter by default. | |

**User's choice:** Leave alone in this phase
**Notes:** Phase 35 is reliability fixes, not cleanup policy. Deferred to a future phase.

### Q5 (follow-up): When discovery fails and hostname = '' or 'unknown', how should the upsert behave?

| Option | Description | Selected |
|--------|-------------|----------|
| Fall back to (hostname, connection_ip) match for degenerate hostnames | Real hostnames use hostname-only; degenerate fall back to legacy match. Failing hosts remain distinct rows. | ✓ |
| Don't store failed discoveries at all | Skip DB write when status='error' and hostname degenerate. Loses visibility. | |
| Store under connection_ip as hostname when remote hostname is degenerate | Write connection_ip into hostname column so row is self-identifying. | |
| Move questions about Area 2 instead | Skip edge case. | |

**User's choice:** Fall back to (hostname, connection_ip) match for degenerate hostnames
**Notes:** Prevents the hostname-only match from collapsing all error-rows into one poisoned bucket. Targeted edge-case fix to D-01.

---

## Per-Subprocess SSH Timeout

### Q1: Per-conn.run() timeout default?

| Option | Description | Selected |
|--------|-------------|----------|
| 10s per command | Upper bound for any single info-gathering shell command; ~100s max for a full 10-command discovery. | ✓ |
| 5s per command | Tighter; fast fail. May false-positive on loaded hosts. | |
| 15s per command | More tolerant. ~150s max. | |
| Configurable via env var, 10s default | HOMELAB_MCP_SSH_CMD_TIMEOUT env var, 10s default. | |

**User's choice:** 10s per command
**Notes:** Recommended. Balances fail-fast with tolerance of legitimately slow commands on healthy homelab hosts.

### Q2: When an individual subprocess times out, what happens to the discovery result?

| Option | Description | Selected |
|--------|-------------|----------|
| Skip that field, continue discovery, mark partial | Timed-out command contributes null; remaining commands run. Response marks partial:true + timed_out_commands list. | ✓ |
| Abort the whole discovery on first timeout | Any per-cmd timeout → ssh_timeout error; loses fields that succeeded. | |
| Retry once, then skip | Doubles worst-case runtime. | |

**User's choice:** Skip that field, continue discovery, mark partial
**Notes:** Partial data is better than no data for sitemap purposes. The partial:true marker lets callers detect degraded captures.

### Q3: bulk_discover_and_map currently iterates serially (8 unreachable × 30s = 4 min). Fix?

| Option | Description | Selected |
|--------|-------------|----------|
| Parallel with asyncio.gather + concurrency cap of 10 | asyncio.Semaphore(10), return_exceptions=True. Bulk total drops from N×T to ceil(N/10)×T. | ✓ |
| Parallel, uncapped | Full fan-out; risks FD exhaustion / SSH flood on large target lists. | |
| Keep serial, rely on per-cmd timeout to bound each host | Per-cmd timeout lowers each host's worst-case but serial still sums linearly. | |

**User's choice:** Parallel with asyncio.gather + concurrency cap of 10
**Notes:** Fixes the primary 4-min hang surface. Cap prevents runaway concurrency on large inventories.

### Q4: Overall ssh_discover_system wrapper timeout (today 30s)?

| Option | Description | Selected |
|--------|-------------|----------|
| Bump to 120s to comfortably accommodate per-cmd × ~10 commands | Per-cmd 10s × 10 = 100s; 120s gives cushion. Per-cmd becomes primary guardrail. | ✓ |
| Keep 30s overall; per-cmd is the real bound | May false-timeout on slow healthy hosts. | |
| Compute dynamically from per-cmd budget | Self-adjusting but adds surface area. | |
| Configurable via env var, 120s default | HOMELAB_MCP_SSH_DISCOVER_TIMEOUT env var. | |

**User's choice:** Bump to 120s
**Notes:** Outer timeout becomes safety net, not primary control. Per-cmd is where the real bounding happens.

---

## Claude's Discretion (Final Question)

### The two unselected areas — how should they be treated?

| Option | Description | Selected |
|--------|-------------|----------|
| Claude's Discretion — write both as implementation details the planner decides | Discovery schema: fix both ends on canonical names + add usb/pci/block JSON columns. Null-threshold: shared helper, skip-silently, debug log. Bug-fix phase → AST meta-tests apply. | ✓ |
| Quick pass on Discovery schema | Targeted questions on canonical direction + usb/pci/block representation. | |
| Quick pass on Null-threshold defensiveness | Targeted questions on threshold-input set + helper extraction. | |
| Quick pass on both | Targeted questions on both. | |

**User's choice:** Claude's Discretion
**Notes:** Planner gets the guidance in CONTEXT.md D-09 (discovery schema) and D-10/D-11/D-12/D-13 (null-threshold) but does not need user input for routine implementation decisions.

---

## Deferred Ideas

- IP-history column on devices table (discovery_history already covers the audit trail)
- Automatic stale-row pruning (its own decision on retention window + destructiveness)
- prune_sitemap_duplicates as a standalone MCP tool (migration handles the one-time collapse)
- Per-subprocess and overall timeout env-var tunables (offered, user accepted plain constants)
- Normalized sub-tables for usb/pci/block inventory (JSON columns sufficient at homelab scope)
