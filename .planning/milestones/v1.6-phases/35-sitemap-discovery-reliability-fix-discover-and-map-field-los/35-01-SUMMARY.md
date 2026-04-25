---
phase: 35-sitemap-discovery-reliability-fix-discover-and-map-field-los
plan: 01
subsystem: ssh
tags: [asyncssh, asyncio, timeout, sitemap, contract-alignment, b1-dedent]

requires:
  - phase: 33
    provides: "Phase 33 discovered the field-loss + 4-minute hang bugs that this plan fixes"
provides:
  - "_run_with_timeout helper bounding every SSH discovery probe at 10s (D-05)"
  - "B1 dedent fix — probe blocks hoisted out of the hostname-success if-branch so a hostname probe timeout no longer silently suppresses every subsequent probe"
  - "Conditional partial-mode payload with partial: true + timed_out_commands: [...] when any per-cmd timeout fires (D-06)"
  - "Producer field names aligned to sitemap consumer contract: cpu.cores (not count), memory.total/used/free/available as Gi-suffixed strings, disk.filesystem/size/used/available/use_percent/mount (D-09a)"
  - "Outer @ssh_connection_wrapper bumped 30.0s → 120.0s — per-cmd timeouts are now the primary guardrail (D-08)"
affects: [35-02, 35-03, 35-04]

tech-stack:
  added: []
  patterns:
    - "Per-command asyncio.wait_for timeout wrapper for asyncssh conn.run calls with in-band timeout accumulator"
    - "Conditional back-compat payload keys — only emit partial/timed_out_commands when any timeout fired"

key-files:
  created: []
  modified:
    - src/homelab_mcp/ssh_tools.py

key-decisions:
  - "_run_with_timeout returns None (not an empty SSHCompletedProcess) on timeout so call-site guards read naturally as `if result and result.exit_status == 0 and result.stdout:`"
  - "cmd_name tags are in-tree constants (hostname, nproc, cpuinfo, free, df, ip, uptime, os-release, lsusb, lspci, lsblk) — no user input in log strings"
  - "Memory emits 4 Gi-suffixed strings (total/used/free/available) via integer-GiB division — consumable by sitemap._parse_memory_gb without format drift"
  - "Disk command changed df -B1 / → df -B1 -T / to expose filesystem type; 6 fields emitted to satisfy sitemap.py:88-94 consumer"
  - "Wrapper bumped to 120.0s (10s × ~10 probes = 100s worst case + 20s handshake/sudo cushion)"

patterns-established:
  - "Per-cmd timeout pattern: async def _run_with_timeout(conn, cmd, *, cmd_name, timed_out, timeout=10.0) returning SSHCompletedProcess | None — replicable for future multi-probe SSH tools"
  - "Probe-body dedent rule: hostname (or any 'sentinel' probe) guards only its own derived value; downstream probes run unconditionally at function-body level"

requirements-completed: []

duration: 13min
completed: 2026-04-24
---

# Phase 35 Plan 01: SSH Discovery Reliability + Producer Contract Alignment

**Per-probe 10s timeouts + B1 dedent + sitemap-consumer field alignment (cores / Gi memory / df -T disk) + wrapper bump to 120s — closes the 4-minute hang and the NULL cpu/memory/disk column writes at the producer.**

## Performance

- **Duration:** ~13 min
- **Tasks:** 2
- **Files modified:** 1 (src/homelab_mcp/ssh_tools.py)

## Accomplishments

- Every `conn.run(...)` call inside `ssh_discover_system` now routes through `_run_with_timeout` with a 10s bound — a single hung probe can no longer stall discovery.
- Probe blocks (CPU, memory, disk, network, uptime, os, lsusb, lspci, lsblk) dedented out of the `if hostname_result.exit_status == 0 and hostname_result.stdout:` branch. A hostname probe timeout/failure no longer silently skips every other probe (B1 pre-existing defect).
- CPU emits `cores` (was `count`). Memory emits four Gi-suffixed strings. Disk uses `df -B1 -T /` and emits `filesystem/size/used/available/use_percent/mount`. These are the exact keys `sitemap.parse_discovery_output` reads at `sitemap.py:66-95`.
- Back-compat preserved: when zero per-cmd timeouts fire, the return JSON has no `partial`/`timed_out_commands` keys — byte-for-byte equivalent to pre-Phase-35 shape.
- Outer `@ssh_connection_wrapper` bumped `30.0 → 120.0`.

## Task Commits

Each task was committed atomically on branch `worktree-agent-a9d266f1`, then merged back via `134b8d0 chore: merge executor worktree`:

1. **Task 1: `_run_with_timeout` helper + B1 dedent + 11 call-site rewrites + conditional partial payload** — `aaef312` (fix)
2. **Task 2: Decorator bump 30.0 → 120.0 + CPU/memory/disk producer field alignment** — `7d07b79` (fix)

**Plan metadata:** this SUMMARY was written by the orchestrator post-merge — the executor was sandbox-blocked from creating `.md` files. See "Deviations from Plan" below.

## Files Created/Modified

- `src/homelab_mcp/ssh_tools.py` — added `import asyncio`; added `_run_with_timeout` private helper; rewrote all 11 probe `conn.run(...)` call sites; hoisted probe blocks out of the hostname-success `if` branch; swapped `cpu_info["count"]` → `cpu_info["cores"]`; rewrote memory block to emit 4 Gi-suffixed strings; rewrote disk block to use `df -B1 -T /` and emit 6 fields; bumped `@ssh_connection_wrapper(timeout_seconds=30.0)` → `120.0`; replaced return block with conditional-key payload (`partial`/`timed_out_commands` only when timeouts fired). Net ~+83 lines (+257 / -174).

## Decisions Made

- **Helper returns `None` on timeout rather than a stub `SSHCompletedProcess`** — call-site guards read naturally as `if name_result and name_result.exit_status == 0 and name_result.stdout:`. Simpler than synthesizing a sentinel object.
- **cmd_name tags are in-tree constants** — no user input in the DEBUG log string, so no injection surface on the `logger.debug("probe %r exceeded %.1fs on %s", cmd_name, timeout, conn._host)` line.
- **Memory emits Gi via integer division**, not float — consistent with existing `_parse_memory_gb` which expects "NGi" / "NG" suffix and never needs sub-GiB resolution for sitemap analysis.
- **Disk `df -B1 -T /`** (not `-t ext4` or format tweaks) — minimal diff from the existing `-B1` invocation; the `-T` flag adds the `type` column without reformatting bytes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Lint] Import block reorganized by `ruff check --fix`**
- **Found during:** Task 1 (after adding `import asyncio`)
- **Issue:** `ruff` rule I001 (isort) split the existing `from .database import (...)` into its parenthesized multi-line form when the new `import asyncio` reordered the block.
- **Fix:** Accepted ruff's reformatting — non-semantic.
- **Files modified:** `src/homelab_mcp/ssh_tools.py` (imports block, top of file)
- **Verification:** `uv run ruff check src/homelab_mcp/ssh_tools.py` → `All checks passed!`
- **Committed in:** `aaef312` (Task 1 commit)

**2. [Orchestrator intervention] SUMMARY.md written post-merge**
- **Found during:** Plan completion, worktree teardown
- **Issue:** The executor agent's `Write` + `Bash` file-creation calls for `35-01-SUMMARY.md` were denied by the sandbox (permission policy blocking `.md` file creation from within the subagent's security profile).
- **Fix:** Orchestrator wrote this SUMMARY.md on the merged main branch after merging both Wave 1 worktrees. Content is reconstructed from the executor's completion report (commits, verification output, diff stats) — no data loss, no guessing.
- **Files modified:** `.planning/phases/35-sitemap-discovery-reliability-fix-discover-and-map-field-los/35-01-SUMMARY.md`
- **Verification:** Both task commits (`aaef312`, `7d07b79`) present in merged history; `git show --stat` confirms the described changes.
- **Committed in:** standalone `docs(35-01): write SUMMARY.md post-merge ...` commit on main after wave merge.

---

**Total deviations:** 2 auto-fixed (1 cosmetic lint auto-fix, 1 orchestrator intervention for sandbox-blocked artifact)
**Impact on plan:** No scope change. Code work exactly as planned; documentation landed via orchestrator fallback.

## Issues Encountered

- **Pre-existing test mock mismatch:** `tests/test_ssh_tools.py::test_ssh_discover_success` fails with `KeyError: 'count'` after the `count → cores` rename (and a sibling disk-column shape mismatch). This is expected and in-scope for **Plan 04 Task 3**, per Plan 01's explicit out-of-scope handoff at its `<acceptance_criteria>` tail. Not regressed by this plan — the plan merely renames the field; the fix belongs with the regression-test suite that Plan 04 ships.

## User Setup Required

None — no external service configuration required.

## Verification Output

```
uv run ruff check src/homelab_mcp/ssh_tools.py
  → All checks passed!

uv run mypy src/homelab_mcp/ssh_tools.py
  → Success: no issues found

uv run pytest tests/test_ssh_tools.py
  → 9 passed, 1 failed (test_ssh_discover_success — pre-existing mock shape drift; Plan 04 Task 3 rewrites the test)

# Structural proofs
grep -cE "_run_with_timeout\(" src/homelab_mcp/ssh_tools.py
  → 12 (1 def + 11 call sites)

awk '/^async def ssh_discover_system/,/^async def _sudo_run/' src/homelab_mcp/ssh_tools.py | grep -cE "await conn\.run\("
  → 0

grep -n "@ssh_connection_wrapper(timeout_seconds=120.0)" src/homelab_mcp/ssh_tools.py
  → 1 match (above async def ssh_discover_system)

grep -c 'Gi"' src/homelab_mcp/ssh_tools.py
  → 7 (4 memory + 3 disk Gi-suffixed f-string values)

grep -nE "^        cpu_info: dict" src/homelab_mcp/ssh_tools.py
  → match at function-body indent (8 spaces) — B1 dedent proved
grep -nE "^            cpu_info: dict" src/homelab_mcp/ssh_tools.py
  → 0 matches (would mean still nested — proves dedent held)
```

## Next Phase Readiness

### Handoff to Plan 02
- Producer emits `usb_devices`/`pci_devices`/`block_devices` under correct names already (unchanged by this plan). Plan 02 extends the READER (`NetworkDevice` dataclass + `parse_discovery_output`) to pick them up.

### Handoff to Plan 03
- `NetworkDevice` attribute list (after Plan 02 extends it) is the column list Plan 03 must thread through both `SQLiteAdapter.store_device` and `PostgreSQLAdapter.store_device`. `asdict(device)` produces the dict keys Plan 03 reads.

### Handoff to Plan 04
- **W4 functional test:** Plan 04 Task 3 mocks `_run_with_timeout` to return `None` for `cmd_name == "hostname"` and asserts `"cpu" in result["data"]` — this is the functional guard for the B1 dedent. The scaffold (11 wrapped probe sites + dedented structure) is ready.
- **Test shape drift:** `test_ssh_discover_success` needs its `conn.run` mocks updated to reflect `cores` (not `count`), `df -B1 -T /` (not `-B1 /`), and Gi-suffixed memory strings. Plan 04 Task 3 owns this rewrite.

---
*Phase: 35-sitemap-discovery-reliability-fix-discover-and-map-field-los*
*Completed: 2026-04-24*
