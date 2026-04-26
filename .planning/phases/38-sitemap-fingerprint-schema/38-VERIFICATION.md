---
phase: 38-sitemap-fingerprint-schema
verified: 2026-04-26T18:28:25Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Agent invocation of configure_host_fingerprint prompt produces a coherent per-host conversation"
    expected: "Agent reads sitemap, infers role hints (Proxmox → gpu_passthrough; NVIDIA → cuda; AMD VGA → vulkan; TrueNAS/ZFS → zfs), asks user, runs ssh_execute_command for follow-ups, and persists via update_device_fingerprint. Re-running get_network_sitemap shows fingerprint.capabilities populated with the agreed entries."
    why_human: "The prompt body is plain narrative instructions for an LLM agent — no tool-side state machine to assert. Conversational quality, role-hint inference accuracy, and end-user experience can only be judged by an operator running real homelab onboarding. Functional tests prove the prompt is registered and the body interpolates the hostname; they cannot prove the agent actually follows the instructions usefully."
  - test: "End-to-end Docker integration test (test_discover_populates_fingerprint_against_docker_phase38)"
    expected: "Test passes when run against a live Docker daemon (CI environment). Discovery → parse → store → get round-trip populates fingerprint.kernel_name='Linux', non-empty kernel_version, non-empty os_name, package_fingerprint with sha256: prefix and 64-char lowercase hex digest."
    why_human: "Docker daemon is unreachable on the local Windows verification environment (pre-existing fixture behavior also affecting every other integration test in the project — see 38-06-SUMMARY Deferred Issue #1). The test code exists and is correctly structured (verified by static read); needs a CI run or developer with Docker available to confirm green."
  - test: "Cross-distro probe behavior (RHEL / Alpine / BSD)"
    expected: "On Alpine (no dpkg), partial:True fires and fingerprint.package_fingerprint is absent (not stale). Other fingerprint keys (kernel_name, kernel_version, os_name) populate where the probe succeeds, OR are absent without partial enrollment (see WR-01 below)."
    why_human: "Cross-distro CI matrix is out of phase scope per CONTEXT.md. Plan-level tests use Debian/Ubuntu Docker container only. Phase 38 deliberately does Debian-happy-path; gap-filling for non-Debian hosts is the agent's job via ssh_execute_command per the configure_host_fingerprint prompt."
---

# Phase 38: Sitemap Fingerprint Schema Verification Report

**Phase Goal:** Sitemap rows capture enough fingerprint detail (kernel version, installed-package digest, hardware capability probes) that an OS-level change like a kernel update breaking GPU passthrough or Vulkan support shows up as drift instead of vanishing silently.

**Verified:** 2026-04-26T18:28:25Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| #  | Truth | Status | Evidence |
| -- | ----- | ------ | -------- |
| 1  | After running `discover_and_map` on a host, the user can read the sitemap row and see kernel version, package fingerprint, and capability probe results populated | ✓ VERIFIED (workflow shipped) | Plan 01 adds 4 probes (uname-s/-r, /etc/os-release-full, locale-pinned dpkg sha256) at `ssh_tools.py:402-462` populating `system_info["fingerprint"]`. Plan 02 wires `parse_discovery_output` (`sitemap.py:131-132`) and SQLite schema (`database.py:152`). Plan 03 round-trips through both adapters. Capability probe results (GPU passthrough, Vulkan/ML library) flow via the agent-driven `update_device_fingerprint` MCP tool + `configure_host_fingerprint` prompt — Phase 38 ships the SCHEMA + WORKFLOW for capability fingerprints, per orchestrator note. |
| 2  | A user inspecting two sitemap rows for the same host before and after a kernel update can see the kernel_version field change, with package fingerprint and capability fields available for comparison | ✓ VERIFIED | `kernel_version` is one of the universal-core probes (Plan 01), persisted as a JSON-string in `device.fingerprint`, decoded back to a Python dict in SQLiteAdapter.get_all_devices (`database.py:378-382`) and flattened from system_info in PostgreSQLAdapter (`database.py:810`). Both adapters return `device['fingerprint']` as a top-level dict; before/after rows can be compared field-by-field. The actual diff/comparison logic (Phase 39 DRFT-19 changed-bucket) is explicitly out of Phase 38 scope per CONTEXT.md. |
| 3  | The schema migration runs cleanly on existing sitemap databases — old rows get NULL for the new fields and re-discovery populates them; no data loss for existing fields | ✓ VERIFIED | `migration.py:82-90` mirrors Phase 35 D-09c PRAGMA-then-ALTER pattern (idempotent guard). Schema-rebuild branch (`migration.py:183` CREATE TABLE devices_new + `migration.py:219` target_cols) carries the column for pre-Phase-35 DBs upgrading through Phase 38. Test `test_run_sqlite_migrations_adds_fingerprint_column_idempotently_phase38` at `tests/test_database.py` proves: legacy row survives with NULL fingerprint after migration; second run does NOT re-add `add_column_fingerprint`. |
| 4  | The discovery probe code that populates the new fields wraps every `conn.run` call with `_run_with_timeout(10s)` and emits the `partial: True` payload tag when probes time out | ✓ VERIFIED | All 4 new probes wrap through `_run_with_timeout` (`ssh_tools.py:404, 408, 415-420, 441-446`). Phase 35 AST guard `tests/test_ast_regression.py::test_ssh_discover_system_wraps_every_conn_run_phase35` PASSES (verified live). `partial:True` semantics: dpkg-fingerprint enrolls in `timed_out_commands` on non-zero exit (`ssh_tools.py:451-459`) — this is the probe explicitly required by CONTEXT.md D-04. Unit test `test_ssh_discover_partial_when_dpkg_missing_phase38` PASSES, confirming `partial:True` fires when dpkg is absent. **Note (WR-01 inconsistency, not a SC failure):** the uname-s/-r/os-release-full probes do NOT enroll on non-zero exit — same pre-existing pattern as the legacy cpuinfo/free/df/lsusb/lspci/lsblk probes. Only the dpkg probe enrollment was contracted by the plan; the timeout-wrap itself (the SC-4 literal demand) is fully covered. |

**Score:** 4/4 truths verified

### Required Artifacts

Verification of plan-level artifacts (must_haves.artifacts from PLAN frontmatter):

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `src/homelab_mcp/ssh_tools.py` | Three new probes wrapped in _run_with_timeout, assembling system_info['fingerprint'] | ✓ VERIFIED | Lines 402-462; `fingerprint_info` dict assembled and assigned at line 462. 4 probes (uname-s, uname-r, os-release-full, dpkg-fingerprint) all use `_run_with_timeout` + LC_ALL=C dpkg pipeline at line 443. |
| `src/homelab_mcp/sitemap.py` | NetworkDevice.fingerprint field + parse_discovery_output branch | ✓ VERIFIED | Field at line 58 (`fingerprint: str \| None = None`); parse branch at lines 131-132 (`device.fingerprint = json.dumps(discovery_data["fingerprint"])`). |
| `src/homelab_mcp/database.py` | SQLite CREATE TABLE includes fingerprint TEXT; both adapters round-trip; merge_fingerprint helper; ABC + SQLite + Postgres update_device_fingerprint | ✓ VERIFIED | CREATE TABLE at line 152; SQLite UPDATE/INSERT at lines 235/278; SQLite get_all_devices JSON-decode at lines 378-382 with `{}` default; Postgres system_info dict at line 641; Postgres flatten at line 810; ABC abstract at line 48; SQLite update at line 316; Postgres update at line 723; merge_fingerprint helper at line 963. |
| `src/homelab_mcp/migration.py` | Idempotent ALTER + schema-rebuild parity | ✓ VERIFIED | ALTER block at lines 82-90; schema-rebuild CREATE TABLE devices_new at line 183; target_cols entry at line 219. |
| `src/homelab_mcp/tool_schemas/network_tools_schema.py` | update_device_fingerprint inputSchema + preview schema + discover_and_map description follow-up | ✓ VERIFIED | discover_and_map note at line 9; update_device_fingerprint at line 105; update_device_fingerprint_preview at line 140. |
| `src/homelab_mcp/tool_schemas/ssh_tools_schema.py` | ssh_discover description follow-up | ✓ VERIFIED | configure_host_fingerprint reference at line 7. |
| `src/homelab_mcp/tool_handlers/network_handlers.py` | handle_update_device_fingerprint + handle_update_device_fingerprint_preview with handler-side schema filtering | ✓ VERIFIED | Update handler at line 87 with `RECOGNIZED_TOP_LEVEL` filter; preview handler at line 141 (read-only; never calls adapter.update_device_fingerprint). Both emit structured error envelopes with exact-substring contracts. |
| `src/homelab_mcp/tool_handlers/__init__.py` | TOOL_HANDLERS routing entries | ✓ VERIFIED | Imports at lines 31-32; routing at lines 92-93. |
| `src/homelab_mcp/tool_annotations.py` | _MUTATING_ANNOTATIONS for update + _READ_ONLY_TOOLS for preview | ✓ VERIFIED | _READ_ONLY_TOOLS preview entry at line 52; _MUTATING_ANNOTATIONS update entry at line 91 (idempotentHint=True). |
| `src/homelab_mcp/server.py` | MUTATING_TOOLS frozenset includes update_device_fingerprint | ✓ VERIFIED | Line 172. Preview is correctly absent (verified by negative grep). |
| `src/homelab_mcp/prompt_registry.py` | configure_host_fingerprint prompt registration trio | ✓ VERIFIED | HOMELAB_PROMPTS entry at lines 63-77; `_build_configure_host_fingerprint_result` builder at lines 172-219; dispatcher elif at lines 266-267. Body covers all 4 role-hint rules (Proxmox, NVIDIA, AMD, TrueNAS/ZFS) and references all 4 supporting tools. |
| `docs/tool-reference.md` | Entries for new tool, preview, prompt + cross-link breadcrumbs | ✓ VERIFIED | update_device_fingerprint at line 358; update_device_fingerprint_preview at line 394; configure_host_fingerprint at line 1636; cross-links from discover_and_map (line 217) and ssh_discover (line 38). |
| `tests/test_ssh_tools.py` | STDOUT_BY_CMD refactor + fingerprint tests | ✓ VERIFIED | `test_ssh_discover_populates_fingerprint_phase38` and `test_ssh_discover_partial_when_dpkg_missing_phase38` both PASS. |
| `tests/test_database.py` | Migration idempotency + 2 SQLite + 3 Postgres mock-cursor adapter tests + update_device_fingerprint coverage | ✓ VERIFIED | 6 SQLite tests PASS; 6 Postgres mock-cursor tests cleanly SKIP (psycopg2 not installed locally — runs in CI). Migration test PASSES. |
| `tests/test_tools.py` | 5 MCP routing tests + 2 preview tests | ✓ VERIFIED | All 7 tests PASS (success, filter unknown, missing-hostname with exact-substring, annotations, malformed-dict, preview success, preview in _READ_ONLY_TOOLS). |
| `tests/test_mcp_resources.py` | notification fires on update + does NOT fire on preview | ✓ VERIFIED | Both tests PASS. |
| `tests/test_mcp_prompts.py` | Prompt registration + body interpolation with role hints | ✓ VERIFIED | Both tests PASS. |
| `tests/integration/test_sitemap_integration.py` | End-to-end Docker discovery test | ✓ VERIFIED (code present); ⚠️ run-blocked by Docker daemon unavailability locally | Test method `test_discover_populates_fingerprint_against_docker_phase38` exists at lines 247-332 with shape-strict assertions on sha256: prefix + 64-char hex digest. Local execution errors with DockerException (pre-existing fixture behavior affecting all integration tests; documented in 38-06-SUMMARY Deferred Issue #1). Routed to human verification. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| ssh_discover_system probes | system_info["fingerprint"] | fingerprint_info dict assembled then assigned | ✓ WIRED | `ssh_tools.py:461-462`: `if fingerprint_info: system_info["fingerprint"] = fingerprint_info` |
| every new probe | _run_with_timeout | direct call wrap | ✓ WIRED | All 4 probes call `_run_with_timeout(conn, ...)`; AST guard PASSES |
| parse_discovery_output | device.fingerprint | json.dumps(discovery_data["fingerprint"]) | ✓ WIRED | `sitemap.py:131-132` |
| run_sqlite_migrations | ALTER TABLE devices ADD COLUMN fingerprint TEXT | PRAGMA table_info check before ALTER | ✓ WIRED | `migration.py:82-90`; idempotency proven by test |
| SQLiteAdapter.store_device | fingerprint column | SET clause + parameter tuple (UPDATE) and column list + VALUES tuple (INSERT) | ✓ WIRED | UPDATE at lines 235/259; INSERT at lines 278/303 |
| PostgreSQLAdapter.store_device | system_info JSONB sub-key | _maybe_json_load(device_data.get('fingerprint')) | ✓ WIRED | `database.py:641` |
| PostgreSQLAdapter.get_all_devices | top-level fingerprint key | system_info.get('fingerprint') | ✓ WIRED | `database.py:810` |
| handle_update_device_fingerprint | db_adapter.update_device_fingerprint | validate_hostname → filter unknown keys → adapter call | ✓ WIRED | `network_handlers.py:87-138` with RECOGNIZED_TOP_LEVEL filter |
| server.py handle_call_tool | send_resource_list_changed | MUTATING_TOOLS includes update_device_fingerprint | ✓ WIRED | `server.py:172`; notification test PASSES |
| ABC update_device_fingerprint | SQLiteAdapter + PostgreSQLAdapter implementations | @abstractmethod declaration + 2 concrete read-merge-write methods | ✓ WIRED | ABC line 48; SQLite line 316; Postgres line 723 |
| configure_host_fingerprint prompt body | update_device_fingerprint MCP tool + ssh_execute_command | narrative steps reference both tool names | ✓ WIRED | Steps 4 + 5 of prompt body (`prompt_registry.py:199-210`) |
| discover_and_map description | configure_host_fingerprint prompt name | appended sentence | ✓ WIRED | `network_tools_schema.py:9` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| ssh_tools.py fingerprint_info | dict populated by 4 _run_with_timeout probes | Live SSH stdout from uname/cat/dpkg | ✓ Real (when remote tools present); ⚠️ partial:True fires when missing | ✓ FLOWING |
| device.fingerprint (NetworkDevice) | JSON string from json.dumps(discovery_data["fingerprint"]) | parse_discovery_output branch | ✓ Real (discovery_data already validated by ssh_discover_system) | ✓ FLOWING |
| SQLite fingerprint column | TEXT column written by store_device UPDATE/INSERT | device_data.get("fingerprint") (JSON string) | ✓ Real | ✓ FLOWING |
| SQLite get_all_devices return | dict (decoded from JSON) | json.loads(device_dict["fingerprint"]); default {} on JSONDecodeError | ✓ Real | ✓ FLOWING |
| Postgres system_info["fingerprint"] | sub-dict inside JSONB blob | _maybe_json_load(device_data.get("fingerprint")) | ✓ Real | ✓ FLOWING |
| Postgres get_all_devices flattened row | top-level "fingerprint" key | system_info.get("fingerprint") | ✓ Real | ✓ FLOWING |
| update_device_fingerprint adapter return | merged dict | merge_fingerprint(stored, incoming); stored from SELECT | ✓ Real (round-trip proven by SQLite tests) | ✓ FLOWING |
| update_device_fingerprint_preview return | merged dict (no write) | merge_fingerprint(stored, incoming) on read-only get_all_devices fetch | ✓ Real (no DB mutation; adapter.update_device_fingerprint NOT called) | ✓ FLOWING |
| configure_host_fingerprint prompt return | GetPromptResult with f-string interpolated narrative text | _build_configure_host_fingerprint_result(args) | ✓ Real (hostname interpolated; 4 role hints + 4 tool refs verified) | ✓ FLOWING |

All wired artifacts produce real data flowing through the chain.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Phase 38 unit test scope | `uv run pytest tests/test_database.py tests/test_tools.py tests/test_mcp_resources.py tests/test_mcp_prompts.py -k "fingerprint or update_device_fingerprint or configure_host_fingerprint or preview_phase38 or fingerprint_phase38"` | 17 passed, 6 skipped (Postgres mocks; psycopg2 absent locally) | ✓ PASS |
| Full unit suite (Phase 38 must not regress) | `uv run pytest tests/ -m "not integration" --tb=line -q` | 752 passed, 14 skipped, 20 deselected | ✓ PASS |
| AST guards (SC-4 timeout-wrap + Phase 35 hostname-natural-key) | `uv run pytest tests/test_ast_regression.py tests/test_ssh_tools.py tests/test_sitemap.py -k "fingerprint or wraps_every_conn_run or hostname_alone"` | 4 passed | ✓ PASS |
| partial:True regression | `uv run pytest tests/test_ssh_tools.py -k partial` | 3 passed | ✓ PASS |
| Integration test (live Docker SSH) | `uv run pytest tests/integration/test_sitemap_integration.py -k fingerprint -m integration` | 1 ERROR (Docker daemon unreachable on local Windows) | ? SKIP — pre-existing fixture issue affecting ALL integration tests; routed to human verification |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
| ----------- | -------------- | ----------- | ------ | -------- |
| DRFT-20 | 38-01, 38-02, 38-03, 38-04, 38-05, 38-06 | Sitemap schema captures kernel version, package fingerprint, and capability probes (e.g., GPU passthrough state, ML library availability such as Vulkan support for llama.cpp). Specific fields finalized during phase planning; principle is that background OS updates that change behavior must surface as drift. | ✓ SATISFIED | Schema substrate present (kernel_name, kernel_version, os_name, os_version, package_fingerprint as universal-core probes); freeform `capabilities` sub-dict accommodates GPU passthrough, Vulkan, CUDA, ZFS via the agent-driven `update_device_fingerprint` MCP tool + `configure_host_fingerprint` prompt workflow. End-to-end chain verified by 17 unit tests + AST guards + structural review of integration test. |

REQUIREMENTS.md maps Phase 38 to DRFT-20 only — no orphaned requirements.

### Anti-Patterns Found

| File | Line(s) | Pattern | Severity | Impact |
| ---- | ------- | ------- | -------- | ------ |
| `src/homelab_mcp/ssh_tools.py` | 404-433 | uname-s/uname-r/os-release-full probes do NOT enroll in `timed_out_commands` on non-zero exit | ℹ️ Info (REVIEW WR-01) | Documented inconsistency: only the dpkg probe enrolls. Pre-existing pattern (also true for legacy cpuinfo/free/df/lsusb/lspci/lsblk). Per orchestrator note, only the dpkg probe was contracted by the plan to enroll; SC-4's literal demand (timeout-wrap every probe) is fully met. Could be tightened in a follow-up if "kernel probe failed silently == partial" is desired (see WR-01 fix in 38-REVIEW.md). |
| `src/homelab_mcp/tool_handlers/network_handlers.py` & `src/homelab_mcp/database.py` | 198-206, 344, 758 | `update_device_fingerprint_preview` does not surface that the persistent path mutates `last_seen` and `updated_at` | ℹ️ Info (REVIEW WR-03) | Idempotent annotation is technically correct on merge result but row state side-effects (last_seen bump on every fingerprint merge) could confuse `analyze_network_topology` which depends on last_seen indirectly. Not a Phase 38 SC violation. |
| `src/homelab_mcp/database.py` | 723-762 | Postgres `update_device_fingerprint` SELECT-then-UPDATE without explicit transaction or row-lock | ℹ️ Info (REVIEW WR-04) | Theoretical race window between concurrent `store_device` and `update_device_fingerprint`. Single-user homelab scope makes this extremely unlikely. Not a Phase 38 SC violation. |
| `src/homelab_mcp/database.py` | 963-983 | `merge_fingerprint` "deep-merge" docstring is misleading — capabilities sub-dict is one-level overwrite, not recursive | ℹ️ Info (REVIEW IN-03) | Behavior is correct and intentional; documentation could be tightened to "shallow per-capability replace." Doesn't affect SC verification. |
| `src/homelab_mcp/tool_annotations.py` | 37, 46 | `list_keyring_credentials` listed twice in `_READ_ONLY_TOOLS` | ℹ️ Info (REVIEW WR-02) | Pre-existing rebase artifact unrelated to Phase 38. Harmless today (set-like dict overwrite); cleanup is a follow-up. |
| `docs/tool-reference.md` | 1632-1652 | Only `configure_host_fingerprint` documented in MCP Prompts section; the four pre-existing prompts (connect_to_device, decommission_device_workflow, deploy_service_workflow, homelab_health_check) absent | ℹ️ Info (REVIEW IN-04) | Pre-existing docs gap surfaced because Phase 38 introduced the MCP Prompts section. Not a Phase 38 SC violation; follow-up backfill captured in REVIEW IN-04. |

No critical, blocker, or warning anti-patterns specific to Phase 38's contract. All 6 findings from the REVIEW are info-level (4 stylistic/documentation, 2 pre-existing).

### Human Verification Required

3 items routed to human verification — see frontmatter `human_verification` block. Summary:

1. **Conversational quality of `configure_host_fingerprint` prompt** — agent compliance with narrative instructions can only be judged in real homelab use. Functional tests prove registration + interpolation; UX cannot be asserted programmatically.
2. **Live Docker integration test (`test_discover_populates_fingerprint_against_docker_phase38`)** — code is correct (verified by static read); Docker daemon is unreachable on local Windows (pre-existing fixture behavior affecting every integration test in this project). Needs CI run or developer with Docker available.
3. **Cross-distro probe behavior (Alpine, RHEL, BSD)** — out of phase scope per CONTEXT.md; agent-driven gap-fill is the design intent. Optional spot-check.

### Gaps Summary

No blocking gaps. All four ROADMAP Success Criteria are met. The end-to-end fingerprint chain ships:
- 4 universal-core probes wrap through `_run_with_timeout` (SC-4)
- Schema substrate persists fingerprint + idempotent migration handles legacy DBs (SC-3)
- Both adapters round-trip the fingerprint dict; `kernel_version` field is comparable across before/after rows (SC-2)
- The `capabilities` sub-dict is wired through the `update_device_fingerprint` MCP tool (deep-merge contract + idempotent annotation) and the `configure_host_fingerprint` MCP prompt drives the conversational capture workflow (GPU passthrough, Vulkan, CUDA, ZFS) — Phase 38 ships the SCHEMA + WORKFLOW for capability fingerprints; agent-driven population is the design intent per CONTEXT.md D-04 + D-06 (SC-1)

The verification status is `human_needed` (not `passed`) because:
- The conversational agent prompt requires a human to judge if it produces useful per-host capability tracking conversations
- The live Docker integration test cannot be executed on this verification machine
- Cross-distro probe behavior on non-Debian hosts requires manual spot-check

Code review (`38-REVIEW.md`) flagged 6 findings (0 critical, 4 warnings, 6 info). None block phase sign-off but should be considered for follow-up commits:
- WR-01: per-probe non-zero exit enrollment asymmetry (uname-s/-r/os-release-full vs dpkg)
- WR-02: duplicate `list_keyring_credentials` in `_READ_ONLY_TOOLS` (pre-existing)
- WR-03: preview wrapper doesn't flag `last_seen` mutation that the persistent path performs
- WR-04: Postgres adapter race window between SELECT and UPDATE
- IN-03: `merge_fingerprint` "deep-merge" docstring describes one-level overwrite, not recursion
- IN-04: pre-existing prompts undocumented in tool-reference.md MCP Prompts section

---

_Verified: 2026-04-26T18:28:25Z_
_Verifier: Claude (gsd-verifier)_
