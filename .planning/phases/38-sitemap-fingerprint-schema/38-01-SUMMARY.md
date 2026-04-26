---
phase: 38-sitemap-fingerprint-schema
plan: 01
subsystem: discovery
tags: [ssh, fingerprint, drift-detection, dpkg, uname, os-release, phase35-d09a, sc-4]

requires:
  - phase: 35-sitemap-discovery-reliability-fix-discover-and-map-field-los
    provides: "_run_with_timeout helper, partial:True / timed_out_commands convention, AST guard at tests/test_ast_regression.py:447 enforcing per-probe timeout wrapping"
provides:
  - "data['fingerprint'] sub-dict on every successful ssh_discover_system payload (kernel_name, kernel_version, os_name, os_version, package_fingerprint)"
  - "Locale-pinned (LC_ALL=C) sha256 dpkg digest as the universal-core package fingerprint"
  - "Refactored test_ssh_discover_success using STDOUT_BY_CMD lookup (mirrors Phase 35 D-17c convention) so adding more probes never silently breaks the test"
  - "RED→GREEN harness for two new fingerprint regression tests (test_ssh_discover_populates_fingerprint_phase38, test_ssh_discover_partial_when_dpkg_missing_phase38)"
affects: [38-02-sitemap-fingerprint-parser, 38-03-sqlite-postgres-schema, 38-04-update-device-fingerprint-tool, 38-05-configure-host-fingerprint-prompt, 38-06-docs-and-integration, 39-changed-bucket-detection]

tech-stack:
  added: []  # No new packages — uses existing asyncssh + stdlib
  patterns:
    - "Phase 38 D-04 universal-core fingerprint sub-dict on discovery payload"
    - "Explicit timed_out_commands enrollment when a probe's exit_status != 0 (extending Phase 35 D-09a beyond the timeout-only path)"

key-files:
  created: []
  modified:
    - "src/homelab_mcp/ssh_tools.py (lines 385-465: new fingerprint_info block immediately after legacy os-release block at line 383; 79 lines added)"
    - "tests/test_ssh_tools.py (lines 16-444: test_ssh_discover_success refactor + 2 new fingerprint tests + _phase38_install_mocks helper; 287 net lines added)"

key-decisions:
  - "Phase 38 D-04: data['fingerprint'] sub-dict alongside existing data['cpu']/['memory']/etc. — mirrors the existing inventory-key convention without disturbing data['os'] back-compat (D-07)"
  - "RESEARCH.md Pitfall 1 — LC_ALL=C prefix on dpkg pipeline forces byte-wise sort, locale-independent digests across hosts that default to non-en_US locales"
  - "Empty-input sha256 (d41d8cd98f00b204e9800998ecf8427e) explicitly skipped — that's what sha256sum returns when dpkg is absent and the pipe sources nothing; treat as 'no fingerprint' instead of recording a misleading constant"
  - "When dpkg-fingerprint probe returns non-zero exit (e.g., on Alpine without dpkg), explicitly enroll 'dpkg-fingerprint' in timed_out_commands so the existing partial:True flag fires per CONTEXT.md D-04's literal contract — extends Phase 35 D-09a's timeout-only enrollment to also cover the missing-tool branch (Rule 2 — required for correctness per locked decision)"
  - "test_ssh_discover_success refactor uses STDOUT_BY_CMD dict-by-cmd_name lookup instead of fixed-order list-of-results so future probe additions never silently shift the call-order index"
  - "_phase38_install_mocks helper mirrors the inline plumbing in the existing test_ssh_discover_system_partial_mode_on_probe_timeout_phase35 — keeps the new tests in lockstep with the established Phase 35 fixture convention"

patterns-established:
  - "data['fingerprint'] sub-dict pattern — Phase 39 changed-bucket detection (DRFT-19) reads from this; subsequent Phase 38 plans (02-05) extend the same pattern through parser → DB → tool → prompt"
  - "Explicit timed_out_commands.append() on exit_status!=0 for missing-tool branches that need to participate in the partial:True payload contract"

requirements-completed: [DRFT-20]

duration: ~45min
completed: 2026-04-26
---

# Phase 38 Plan 01: Universal-Core Fingerprint Probes Summary

**Adds three new probes (uname -s/-r, /etc/os-release full parse, locale-pinned dpkg sha256 digest) to ssh_discover_system, populating a new `data['fingerprint']` sub-dict — the substrate Phase 39's `changed` drift bucket (DRFT-19) will diff against — without disturbing the legacy `data['os']` field that `analyze_network_topology` reads.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-04-26T06:14Z (approx — worktree base reset to ab219bf)
- **Completed:** 2026-04-26T06:59Z
- **Tasks:** 2 / 2
- **Files modified:** 2 (`src/homelab_mcp/ssh_tools.py`, `tests/test_ssh_tools.py`)

## Accomplishments

- **Universal-core fingerprint substrate now lives on every successful discovery payload.** Three probes (uname-s, uname-r, os-release-full) plus a fourth (dpkg-fingerprint) populate `data['fingerprint']` with `kernel_name`, `kernel_version`, `os_name`, `os_version`, `package_fingerprint`. Phase 39's `changed` bucket detection (DRFT-19) now has the data to diff against; subsequent Phase 38 plans (02-05) wire it through parser → DB → tool → prompt.
- **Brittle test mock retired.** `test_ssh_discover_success` previously used a fixed-order list-of-MagicMocks at lines 76-100 that broke whenever a new probe was added (the 9th call fell through to a default failure result, causing previously-passing assertions to fail depending on probe order shifts). Replaced with a `STDOUT_BY_CMD` dict-by-`cmd_name` lookup mirroring the Phase 35 D-17c convention at lines 507-525 of the same file.
- **Phase 35 D-15 AST guard still bites.** Every new probe (uname-s, uname-r, os-release-full, dpkg-fingerprint) goes through `_run_with_timeout`. The AST regression test at `tests/test_ast_regression.py:447` (`test_ssh_discover_system_wraps_every_conn_run_phase35`) inspected each new `_run_with_timeout(conn, ...)` call and passes — proving SC-4 reliability discipline holds.

## Task Commits

Each task was committed atomically:

1. **Task 1: Refactor test_ssh_discover_success to STDOUT_BY_CMD + add fingerprint RED tests** — `6f23c79` (`test`)
2. **Task 2: Add universal-core fingerprint probes to ssh_discover_system** — `1ec3067` (`feat`)

_Note: This is a TDD plan (RED at Task 1, GREEN at Task 2). No REFACTOR commit was needed — the GREEN implementation follows the established Phase 35 probe-block shape verbatim._

## Files Created/Modified

- `src/homelab_mcp/ssh_tools.py` — Added `fingerprint_info` block (lines 385-465) immediately after the legacy `os-release` block at line 383. Three `_run_with_timeout` probe calls (uname-s, uname-r, os-release-full, dpkg-fingerprint), each gating on `result and result.exit_status == 0 and result.stdout`. Locale-pinned dpkg pipeline `LC_ALL=C dpkg -l 2>/dev/null | sort | sha256sum` strips the trailing `-` filename field from `sha256sum` stdin output. Explicit `timed_out_commands.append("dpkg-fingerprint")` when dpkg returns non-zero exit so `partial:True` fires per CONTEXT.md D-04. The existing `data['os']` PRETTY_NAME-only field stays unchanged for D-07 back-compat.
- `tests/test_ssh_tools.py` — Replaced `test_ssh_discover_success` (16-152) with the STDOUT_BY_CMD lookup pattern. Added two new tests: `test_ssh_discover_populates_fingerprint_phase38` (D-04 — fingerprint sub-dict populated) and `test_ssh_discover_partial_when_dpkg_missing_phase38` (D-04 + Phase 35 D-09a — `package_fingerprint` absent + `partial:True` when dpkg unavailable). Added `_phase38_install_mocks` helper that mirrors the inline plumbing in the existing `test_ssh_discover_system_partial_mode_on_probe_timeout_phase35`.

### Probe commands (exact strings sent over SSH)

| Probe cmd_name        | Command string                                          | Maps to                                |
| --------------------- | ------------------------------------------------------- | -------------------------------------- |
| `uname-s`             | `uname -s`                                              | `fingerprint.kernel_name`              |
| `uname-r`             | `uname -r`                                              | `fingerprint.kernel_version`           |
| `os-release-full`     | `cat /etc/os-release 2>/dev/null`                       | `fingerprint.os_name`, `os_version`    |
| `dpkg-fingerprint`    | `LC_ALL=C dpkg -l 2>/dev/null \| sort \| sha256sum`     | `fingerprint.package_fingerprint`      |

### Tests added/refactored

| Test                                                          | Type    | Phase 38 D-Ref       | State after Task 2 |
| ------------------------------------------------------------- | ------- | -------------------- | ------------------ |
| `test_ssh_discover_success` (refactored)                      | unit    | D-04 + Phase 35 D-09b | GREEN              |
| `test_ssh_discover_populates_fingerprint_phase38` (new)       | unit    | D-04                  | GREEN (was RED)    |
| `test_ssh_discover_partial_when_dpkg_missing_phase38` (new)   | unit    | D-04 + Phase 35 D-09a | GREEN (was RED)    |

## Decisions Made

- **Auto-enrolled `dpkg-fingerprint` in `timed_out_commands` when exit_status != 0** (Rule 2 — required for correctness per CONTEXT.md D-04's "Phase 35 partial:True semantics fire automatically" claim). Phase 35's `_run_with_timeout` only appends to `timed_out` on `TimeoutError`, not on non-zero exit. Without this enrollment, an Alpine host (no dpkg) would silently get a `data['fingerprint']` dict missing `package_fingerprint` AND no `partial:True` flag — violating CONTEXT.md D-04. The enrollment is one explicit `timed_out_commands.append("dpkg-fingerprint")` in the missing-tool branch; documented inline.
- **Skipped distro detection branching in probe code** per CONTEXT.md D-04 (locked) and `<deferred>` "Cross-distro probe branching in code". The agent's job is to fill cross-OS gaps via `ssh_execute_command` later (Plan 05's `configure_host_fingerprint` prompt orchestrates this).
- **Did NOT touch the existing `data['os']` PRETTY_NAME line** per D-07. `analyze_network_topology` reads it; back-compat preserved. New consumers (Phase 39 drift) read `data['fingerprint']['os_name']` / `['os_version']`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Explicit timed_out_commands.append on dpkg exit_status!=0**

- **Found during:** Task 2 (verifying test_ssh_discover_partial_when_dpkg_missing_phase38 GREEN)
- **Issue:** Phase 35's `_run_with_timeout` only appends to `timed_out_commands` on `TimeoutError`. CONTEXT.md D-04 asserts "Phase 35 partial:True semantics fire automatically" when dpkg is missing — but a non-zero exit_status alone (without timeout) does NOT trigger the existing accumulator path. The test would have passed only because the test mock did the appending; production behavior would have silently dropped the `partial:True` flag on Alpine hosts.
- **Fix:** Added an explicit `elif dpkg_result is not None and dpkg_result.exit_status != 0` branch that calls `timed_out_commands.append("dpkg-fingerprint")` once. Documented inline with reference to CONTEXT.md D-04 + Phase 35 D-09a.
- **Files modified:** `src/homelab_mcp/ssh_tools.py` (lines 459-468 of the new fingerprint block)
- **Verification:** `test_ssh_discover_partial_when_dpkg_missing_phase38` GREEN; `partial:True` and `timed_out_commands` both correctly populated on the simulated missing-dpkg host.
- **Committed in:** `1ec3067` (part of Task 2 commit)

**2. [Lint cleanup] Removed redundant blank line introduced by Task 1 commit**

- **Found during:** Task 2 verification (running `./scripts/quality-check.sh`)
- **Issue:** Task 1's diff inserted a section-header comment block right after the import block, leaving two blank lines between the imports and the comment. `ruff format` flagged it as I001 (single blank line expected after the import block).
- **Fix:** Removed the extra blank line.
- **Files modified:** `tests/test_ssh_tools.py` (line 14)
- **Verification:** `uv run ruff check tests/test_ssh_tools.py` exits 0.
- **Committed in:** `1ec3067` (rolled into Task 2 commit since the cleanup belongs with the GREEN-state final verification)

**3. [Out of scope - reverted] ruff format reformatted unrelated files**

- **Found during:** Task 2 verification (`./scripts/quality-check.sh` invoked the pre-commit ruff-format hook)
- **Issue:** The hook reformatted `src/homelab_mcp/drift_detection.py`, `tests/test_ast_regression.py`, and `tests/test_migration.py` — none of which are in Phase 38 Plan 01's scope.
- **Fix:** Reverted those three files via `git checkout HEAD -- ...` per the executor's SCOPE BOUNDARY rule (only auto-fix issues directly caused by the current task's changes).
- **Outcome:** Logged as a pre-existing-format-debt deviation; no further action in this plan.

## Verification Results

```
uv run pytest tests/test_ssh_tools.py -v                                                 → 15 passed
uv run pytest tests/test_ast_regression.py -x                                            → 11 passed (incl. test_ssh_discover_system_wraps_every_conn_run_phase35)
uv run pytest tests/ -m "not integration" --tb=line -q                                   → 734 passed, 8 skipped, 19 deselected
uv run mypy src/homelab_mcp/ssh_tools.py                                                 → Success: no issues found in 1 source file
uv run ruff check src/homelab_mcp/ssh_tools.py tests/test_ssh_tools.py                   → All checks passed!
uv run bandit -r src/homelab_mcp/ssh_tools.py -ll                                        → 0 medium/high issues
./scripts/quality-check.sh                                                               → All checks passed
```

### Manual greps (acceptance criteria from plan)

```
grep -n 'system_info\["fingerprint"\]' src/homelab_mcp/ssh_tools.py    → line 469: system_info["fingerprint"] = fingerprint_info
grep -c '_run_with_timeout' src/homelab_mcp/ssh_tools.py               → increased by 4 (uname-s, uname-r, os-release-full, dpkg-fingerprint)
grep -n 'LC_ALL=C dpkg -l' src/homelab_mcp/ssh_tools.py                → line ~454: confirmed locale-pinned probe
```

## Success Criteria Coverage

- [x] `data["fingerprint"]` exists in the discovery payload after `ssh_discover_system` runs against a Debian host (proven by `test_ssh_discover_populates_fingerprint_phase38`)
- [x] All 4 new probes (uname-s, uname-r, os-release-full, dpkg-fingerprint) wrap through `_run_with_timeout` (proven by AST guard staying green)
- [x] `partial:True` semantics work for missing dpkg (proven by `test_ssh_discover_partial_when_dpkg_missing_phase38` — explicit enrollment via Rule-2 deviation)
- [x] Existing `data["os"]` field unchanged (D-07 back-compat — Phase 35 `test_ssh_discover_success` and the refactored variant both still green)
- [x] Brittle test mock retired in favour of STDOUT_BY_CMD lookup (`grep STDOUT_BY_CMD tests/test_ssh_tools.py` returns 3 occurrences — the original Phase 35 one + 2 new Phase 38 ones)

## Threat Model Coverage

| Threat ID | Plan disposition | Implementation outcome |
| --------- | ----------------- | ---------------------- |
| T-38-01-01 | mitigate (sha256 on remote) | Confirmed: only `digest_field.split()[0]` parsed from remote stdout; full dpkg list never enters our process |
| T-38-01-02 | accept (os-release tampering) | Per-line `.strip().strip('"').strip("'")` parser implemented; no shell evaluation; values JSON-serialized later |
| T-38-01-03 | mitigate (per-probe timeout) | All 4 new probes wrap through `_run_with_timeout(timeout=10.0s)`; AST guard enforces |
| T-38-01-04 | mitigate (static dpkg pipeline) | Pipeline `LC_ALL=C dpkg -l 2>/dev/null \| sort \| sha256sum` is a static literal — no parameter interpolation |
| T-38-01-05 | accept (compromised host could fabricate) | Trust boundary unchanged — the host is already trusted by virtue of the SSH credential |

## Threat Flags

None — the new probes execute on already-authenticated SSH connections; no new network endpoints, auth paths, file access patterns, or trust-boundary crossings introduced.

## Known Stubs

None — every code path lands real data. Empty `fingerprint_info` (e.g., when ALL four probes fail simultaneously) results in the `system_info["fingerprint"]` key being absent rather than stubbed-empty, which is the intended Phase 35 D-09a partial-payload behavior.

## Self-Check: PASSED

**Files exist:**
- FOUND: `src/homelab_mcp/ssh_tools.py` (modified — fingerprint block at lines 385-465)
- FOUND: `tests/test_ssh_tools.py` (modified — STDOUT_BY_CMD refactor + 2 new fingerprint tests)
- FOUND: `.planning/phases/38-sitemap-fingerprint-schema/38-01-SUMMARY.md` (this file)

**Commits exist:**
- FOUND: `6f23c79` test(38-01): refactor test_ssh_discover_success to STDOUT_BY_CMD + add fingerprint RED tests
- FOUND: `1ec3067` feat(38-01): add universal-core fingerprint probes to ssh_discover_system
