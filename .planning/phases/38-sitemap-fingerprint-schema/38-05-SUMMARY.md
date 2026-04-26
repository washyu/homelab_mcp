---
phase: 38-sitemap-fingerprint-schema
plan: 05
subsystem: mcp-prompt-registry+mcp-tool-surface+docs
tags: [mcp-prompt, preview-tool, thin-delegation, agent-instructions, role-hint-inference, documentation, idempotent, read-only]

# Dependency graph
requires:
  - phase: 38-sitemap-fingerprint-schema
    plan: 04
    provides: "update_device_fingerprint MCP tool + adapter method (deep-merge contract); merge_fingerprint module-level helper used by the new preview wrapper; 5-site MCP tool registration template (schema + handler + TOOL_HANDLERS + tool_annotations + MUTATING_TOOLS)"
  - phase: 14-mcp-prompts
    provides: "HOMELAB_PROMPTS dict + _build_*_result builder + get_prompt_result dispatcher elif-chain (registration trio); _make_user_message helper; types.Prompt + types.PromptArgument + types.GetPromptResult + types.PromptMessage + types.TextContent imports"
  - phase: 15-preview-tools
    provides: "thin-delegation *_preview wrapper convention with readOnlyHint=True; registered in _READ_ONLY_TOOLS list, NOT in MUTATING_TOOLS frozenset; analog: decommission_device_preview"
provides:
  - "configure_host_fingerprint MCP prompt registered in HOMELAB_PROMPTS with required hostname argument"
  - "_build_configure_host_fingerprint_result builder interpolates hostname, references get_network_sitemap / ssh_execute_command / update_device_fingerprint / update_device_fingerprint_preview, encodes 4 role-hint inference rules per D-06b (Proxmox VE → gpu_passthrough; NVIDIA → cuda; AMD VGA → vulkan; TrueNAS/ZFS → zfs)"
  - "get_prompt_result dispatcher routes 'configure_host_fingerprint' to the new builder"
  - "update_device_fingerprint_preview MCP tool registered through 4 sites (schema + handler + TOOL_HANDLERS + _READ_ONLY_TOOLS) — explicitly NOT in MUTATING_TOOLS"
  - "handle_update_device_fingerprint_preview: read-only thin wrapper around merge_fingerprint; reads via get_all_devices, computes merge, returns dict with preview=true; adapter's update_device_fingerprint method is NEVER called"
  - "discover_and_map and ssh_discover descriptions append a sentence pointing to the configure_host_fingerprint prompt as the recommended follow-up"
  - "docs/tool-reference.md TOC + entries for update_device_fingerprint, update_device_fingerprint_preview, configure_host_fingerprint MCP prompt; follow-up notes added inline to discover_and_map and ssh_discover sections"
affects: [38-06, 39, drift-detection-changed-bucket, lifecycle-hooks-v1.7.1, mcp-clients-that-discover-via-prompts-list]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Phase 38 D-06 narrative-instruction prompt body — pure f-string interpolation of the hostname arg into a multi-step English instruction block; no tool-side state machine, no required tool-call sequence. Relies on agent compliance with prompt instructions (the same path Phase 14's existing prompts already use)."
    - "Phase 38 D-06b in-text role-hint inference rules — Proxmox VE → gpu_passthrough; NVIDIA in pci_devices → cuda; AMD VGA → vulkan; TrueNAS / ZFS → zfs. Rules live in the prompt body as English text; the agent applies them. No code-side classifier."
    - "Phase 38 D-05c thin-delegation preview wrapper — handler reads device row via get_all_devices, computes merge_fingerprint(stored, incoming), returns the would-be merged dict with preview=true; adapter's update method is NEVER called. Mirrors decommission_device_preview thin-delegation convention from Phase 15."
    - "Phase 15 preview-tool registration: 4 sites (schema + handler + TOOL_HANDLERS routing + _READ_ONLY_TOOLS list) — explicitly NOT 5 sites because preview is read-only, no MUTATING_TOOLS membership and no resource notification fire."

key-files:
  created: []
  modified:
    - "src/homelab_mcp/prompt_registry.py (HOMELAB_PROMPTS entry lines 63-77; _build_configure_host_fingerprint_result builder lines 172-220; dispatcher elif lines 266-267)"
    - "src/homelab_mcp/tool_schemas/network_tools_schema.py (discover_and_map description lines 6-12 — appended follow-up sentence; update_device_fingerprint_preview schema lines 140-173)"
    - "src/homelab_mcp/tool_schemas/ssh_tools_schema.py (ssh_discover description line 7 — appended follow-up sentence)"
    - "src/homelab_mcp/tool_handlers/network_handlers.py (handle_update_device_fingerprint_preview lines 141-198)"
    - "src/homelab_mcp/tool_handlers/__init__.py (import line 32; TOOL_HANDLERS routing line 93)"
    - "src/homelab_mcp/tool_annotations.py (_READ_ONLY_TOOLS entry line 52)"
    - "docs/tool-reference.md (TOC line 17; discover_and_map description note; ssh_discover description note; update_device_fingerprint + update_device_fingerprint_preview entries after get_device_changes; new MCP Prompts section + configure_host_fingerprint entry at end)"
    - "tests/test_mcp_prompts.py (2 prompt tests added at end: test_configure_host_fingerprint_prompt_registered_phase38, test_configure_host_fingerprint_prompt_body_phase38)"
    - "tests/test_tools.py (test_get_available_tools count bumped 53 → 54; 2 preview tests appended: test_execute_update_device_fingerprint_preview_phase38, test_update_device_fingerprint_preview_in_read_only_tools_phase38)"
    - "tests/test_mcp_resources.py (1 no-notification test appended: test_update_device_fingerprint_preview_no_notification_phase38)"

key-decisions:
  - "Preview registered in 4 sites NOT 5 — read-only by design, MUST NOT be in MUTATING_TOOLS. test_update_device_fingerprint_preview_in_read_only_tools_phase38 asserts both halves: present in _READ_ONLY_TOOLS AND absent from MUTATING_TOOLS. test_update_device_fingerprint_preview_no_notification_phase38 asserts the negative behavior (assert_not_awaited on send_resource_list_changed)."
  - "Preview reads via get_all_devices then computes merge_fingerprint directly — does NOT call adapter.update_device_fingerprint. This is critical: the preview's value proposition is 'show me the merge result without writing'. Calling the adapter (even with a no-op flag) would couple the preview to write-path latency and could fire side-effects via timestamps. test_execute_update_device_fingerprint_preview_phase38 explicitly asserts mock_adapter.update_device_fingerprint.assert_not_called()."
  - "Role-hint inference rules embedded in prompt body as English text per D-06b — Proxmox VE → gpu_passthrough; NVIDIA → cuda; AMD VGA → vulkan; TrueNAS/ZFS → zfs. Test asserts ≥3 of {Proxmox, NVIDIA, AMD, TrueNAS, ZFS} appear in the body so the rule set is provably present without hard-coding the exact wording."
  - "Prompt body references update_device_fingerprint_preview alongside update_device_fingerprint — the prompt now teaches the agent the dry-run-first pattern Phase 15 established for destructive-adjacent tools. Step 5 of the prompt body explicitly says: 'Use update_device_fingerprint_preview first if you want to confirm the merge before persisting.'"
  - "Both new tool-description follow-ups (discover_and_map, ssh_discover) point to 'configure_host_fingerprint prompt' — D-06c belt-and-braces for MCP clients that don't surface prompts. Even if a client doesn't expose prompts/list, the agent still sees a breadcrumb in the tool description after every successful discovery."
  - "tool-reference.md TOC adds 'MCP Prompts' as a new top-level section — section is appended at the end of the file (after Proxmox Tools) with anchor links from update_device_fingerprint and ssh_discover entries. Sets a precedent for documenting future MCP prompts in the same place."

patterns-established:
  - "Phase 38 D-06 prompt+description co-evolution — when adding an MCP prompt, also update the descriptions of the tools that prompt depends on so MCP clients without prompt support still surface the breadcrumb. discover_and_map and ssh_discover descriptions both end with: 'Recommended follow-up: run the configure_host_fingerprint prompt to capture per-host capability signals for drift detection.'"
  - "Phase 15 preview-tool registration: 4 sites NOT 5 (schema + handler + TOOL_HANDLERS + _READ_ONLY_TOOLS) — preview must NEVER appear in MUTATING_TOOLS. Two assertions guard this: (1) presence in _READ_ONLY_TOOLS, (2) absence from MUTATING_TOOLS via `assert 'foo_preview' not in MUTATING_TOOLS`. Negative test mirrors the affirmative test for the underlying mutating tool — tests both halves of the dichotomy."
  - "Phase 38 D-05c preview-handler thin delegation — preview reads via get_all_devices, calls merge_fingerprint(stored, incoming), returns merged with `preview=true` flag. Does NOT call adapter's update method. Test asserts adapter.update_device_fingerprint.assert_not_called() to lock the contract."

requirements-completed: [DRFT-20]

# Metrics
duration: ~20min
completed: 2026-04-26
---

# Phase 38 Plan 05: configure_host_fingerprint Prompt + Preview Tool + Docs Summary

**The agent-instruction surface for Phase 38's discovery-time fingerprint workflow now ships end-to-end: a `configure_host_fingerprint` MCP prompt with role-hint inference rules; an `update_device_fingerprint_preview` thin-delegation wrapper per Phase 15 convention; tool-description follow-up notes on `discover_and_map` and `ssh_discover` so MCP clients without prompt support still see the breadcrumb; and `docs/tool-reference.md` entries so users discover the workflow.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-04-26 (sequential executor on credential-cleanup branch, after Plan 04 commits)
- **Completed:** 2026-04-26
- **Tasks:** 2 (TDD: RED gate + GREEN implementation gate)
- **Files modified:** 10 (7 source/docs, 3 test)

## Accomplishments

- **`configure_host_fingerprint` MCP prompt registered through all 3 Phase 14 sites.** HOMELAB_PROMPTS dict entry, `_build_configure_host_fingerprint_result` builder function, and `get_prompt_result` dispatcher elif clause — the established Phase 14 trio for prompt registration.
- **Prompt body interpolates hostname and encodes role-hint inference rules per D-06b.** The body covers all 4 recommended rules (Proxmox VE → gpu_passthrough; NVIDIA in pci_devices → cuda; AMD VGA → vulkan; TrueNAS/ZFS → zfs) plus references the four supporting tools the agent needs (`get_network_sitemap`, `ssh_execute_command`, `update_device_fingerprint`, `update_device_fingerprint_preview`).
- **Prompt body teaches the dry-run-first pattern.** Step 5 explicitly says: *"Use update_device_fingerprint_preview first if you want to confirm the merge before persisting."* This propagates Phase 15's preview-then-commit convention into the agent's runtime instructions for fingerprint configuration.
- **`update_device_fingerprint_preview` MCP tool registered through 4 sites.** Schema (`network_tools_schema.py:140`), handler (`network_handlers.py:141`), routing dict (`__init__.py:93`), `_READ_ONLY_TOOLS` (`tool_annotations.py:52`). Explicitly NOT in MUTATING_TOOLS — preview is read-only and fires no resource notification.
- **Preview handler is genuinely thin-delegation.** `handle_update_device_fingerprint_preview` reads the device row via `get_all_devices`, calls `merge_fingerprint(stored, incoming)` directly (the same module-level helper Plan 04 introduced), and returns the would-be merged dict with `preview: true`. The adapter's `update_device_fingerprint` method is NEVER called — `test_execute_update_device_fingerprint_preview_phase38` asserts `mock_adapter.update_device_fingerprint.assert_not_called()`.
- **Preview correctly surfaces deep-merge semantics.** When the test stores a row with `capabilities.vulkan` and previews adding `capabilities.cuda`, the response contains BOTH keys — proving the preview honors Plan 04's deep-merge contract identically to the real write path.
- **`discover_and_map` and `ssh_discover` descriptions append the configure_host_fingerprint follow-up sentence.** D-06c belt-and-braces for MCP clients that don't surface prompts via `prompts/list`. The agent still sees the breadcrumb after every successful discovery.
- **`docs/tool-reference.md` documents three new surfaces.** Entries for `update_device_fingerprint` (description, schema, response shape, error envelopes), `update_device_fingerprint_preview` (read-only flavor of the same surface), and the `configure_host_fingerprint` MCP prompt under a new top-level "MCP Prompts" section. Anchor cross-links wire the discover_and_map and ssh_discover entries to the prompt section.
- **TDD discipline observed.** Wave-0 RED gate (Task 1, 5 tests intentionally RED — 2 prompt + 2 preview routing + 1 count assertion; the no-notification test passed for the wrong reason in RED phase because the dispatcher errored out before the MUTATING_TOOLS check, but is now provably correct in GREEN phase since preview is wired AND not in MUTATING_TOOLS) → GREEN gate (Task 2, all 5 RED tests + 81 prompt+tools+resources tests + 752-test full unit suite all green).

## Task Commits

Each task committed atomically with pre-commit hooks (no `--no-verify`):

1. **Task 1: Wave-0 RED tests** — `b60cc1b` (test) — 2 prompt tests + 2 preview routing tests + 1 no-notification test + count-assertion bump (53 → 54). All intentionally RED at Task 1; no implementation files touched.
2. **Task 2: Wire prompt + preview + descriptions + docs** — `8ea8f88` (feat) — prompt registration trio in `prompt_registry.py`; preview wired through 4 sites; description follow-ups on `discover_and_map` and `ssh_discover`; new tool + prompt entries in `docs/tool-reference.md` + new "MCP Prompts" top-level section; full test suite green.

_Note: This is a TDD plan (RED at Task 1, GREEN at Task 2). No REFACTOR commit was needed — the implementation follows established patterns (Phase 14 prompt trio + Phase 15 preview-tool 4-site convention) verbatim and warranted no cleanup pass._

## Files Created/Modified

### `src/homelab_mcp/prompt_registry.py`

| Change | Location | Description |
| --- | --- | --- |
| HOMELAB_PROMPTS entry | lines 63-77 | `configure_host_fingerprint` Prompt with required `hostname` argument; description references Phase 39 changed-infrastructure drift detection |
| Builder function | lines 172-220 | `_build_configure_host_fingerprint_result(args)` — interpolates hostname; 6-step narrative instruction body covering get_network_sitemap, role-hint inference, user Q&A, ssh_execute_command probes, update_device_fingerprint persistence (with preview-first hint), and confirmation |
| Dispatcher elif | lines 266-267 | `elif name == "configure_host_fingerprint": return _build_configure_host_fingerprint_result(args)` |

### `src/homelab_mcp/tool_schemas/network_tools_schema.py`

| Change | Location | Description |
| --- | --- | --- |
| discover_and_map description | lines 6-12 | Appended sentence: "Recommended follow-up: run the configure_host_fingerprint prompt to capture per-host capability signals for drift detection." |
| update_device_fingerprint_preview schema | lines 140-173 | Same shape as update_device_fingerprint (hostname + fingerprint with bounded top-level keys); description names "Read-only — no DB write occurs" |

### `src/homelab_mcp/tool_schemas/ssh_tools_schema.py`

| Change | Location | Description |
| --- | --- | --- |
| ssh_discover description | line 7 | Appended sentence: "Recommended follow-up after onboarding: run the configure_host_fingerprint prompt to capture per-host capability signals for drift detection." (preserved keyring auto-inject hint and credentials-add error guidance verbatim) |

### `src/homelab_mcp/tool_handlers/network_handlers.py`

| Change | Location | Description |
| --- | --- | --- |
| handle_update_device_fingerprint_preview | lines 141-198 | Read-only thin wrapper: validate_hostname → reject non-dict fingerprint → filter unknown top-level keys via RECOGNIZED_TOP_LEVEL → fetch row via `db_adapter.get_all_devices()` → reject missing hostname with structured error envelope → call `merge_fingerprint(stored, incoming)` → return dict with `preview: true`. Local import of `merge_fingerprint` from `..database` to avoid circular issues. |

### `src/homelab_mcp/tool_handlers/__init__.py`

| Change | Location | Description |
| --- | --- | --- |
| Import | line 32 | `handle_update_device_fingerprint_preview,  # Phase 38 D-05c (Plan 05)` added to `from .network_handlers import (...)` block |
| TOOL_HANDLERS routing | line 93 | `"update_device_fingerprint_preview": handle_update_device_fingerprint_preview,  # Phase 38 D-05c (Plan 05)` after `update_device_fingerprint` |

### `src/homelab_mcp/tool_annotations.py`

| Change | Location | Description |
| --- | --- | --- |
| `_READ_ONLY_TOOLS` entry | line 52 | `"update_device_fingerprint_preview",  # Phase 38 D-05c (Plan 05)` appended to the list (NOT to `_MUTATING_ANNOTATIONS`) |

### `docs/tool-reference.md`

| Change | Location | Description |
| --- | --- | --- |
| TOC link | line 17 | Added `- [MCP Prompts](#mcp-prompts)` |
| ssh_discover note | description | Appended same follow-up sentence + cross-link to MCP Prompts section |
| discover_and_map note | description | Appended same follow-up sentence + cross-link to MCP Prompts section |
| update_device_fingerprint entry | after get_device_changes | Description, schema (hostname + fingerprint with bounded top-level keys), example, returns shape, structured-error envelopes (Hostname not in sitemap; fingerprint must be an object) |
| update_device_fingerprint_preview entry | immediately after | Description (read-only dry-run); schema same shape as update_device_fingerprint; example; returns shape with `preview: true` |
| MCP Prompts section | end of file | New top-level section with `configure_host_fingerprint` entry: 4-step workflow description (sitemap read + role-hint inference + ssh_execute_command capture + update_device_fingerprint persistence with preview-first option); related-tools cross-link block |

### `tests/test_mcp_prompts.py`

| Test | Lines (final) | Purpose |
| --- | --- | --- |
| `test_configure_host_fingerprint_prompt_registered_phase38` | added at end | Asserts prompt key exists in HOMELAB_PROMPTS and the required `hostname` argument is declared |
| `test_configure_host_fingerprint_prompt_body_phase38` | added at end | Asserts get_prompt_result interpolates the hostname; body references all 4 supporting tools (get_network_sitemap, ssh_execute_command, update_device_fingerprint, capabilities); body covers ≥3 of {Proxmox, NVIDIA, AMD, TrueNAS, ZFS} role hints per D-06b |

### `tests/test_tools.py`

| Test | Lines (final) | Purpose |
| --- | --- | --- |
| `test_get_available_tools` count assertion | line 16 | Bumped from 53 to 54 (RED at Task 1; GREEN once preview is registered in Task 2). New assertion `update_device_fingerprint_preview in tools` added at line 21. |
| `test_execute_update_device_fingerprint_preview_phase38` | added at end | Patches `NetworkSiteMap`; mocks `get_all_devices` to return a row with vulkan capability; calls `execute_tool("update_device_fingerprint_preview", {"hostname": "h", "fingerprint": {"capabilities": {"cuda": ...}}})`; asserts response shows BOTH vulkan (preserved) and cuda (incoming) AND `mock_adapter.update_device_fingerprint.assert_not_called()` |
| `test_update_device_fingerprint_preview_in_read_only_tools_phase38` | added at end | Asserts BOTH halves of the dichotomy: `"update_device_fingerprint_preview" in _READ_ONLY_TOOLS` AND `"update_device_fingerprint_preview" not in MUTATING_TOOLS` |

### `tests/test_mcp_resources.py`

| Test | Lines (final) | Purpose |
| --- | --- | --- |
| `test_update_device_fingerprint_preview_no_notification_phase38` | appended after test_update_device_fingerprint_sends_list_changed_phase38 | Mirror of the affirmative notification test but for the preview wrapper; asserts `mock_session.send_resource_list_changed.assert_not_awaited()` — preview is read-only, no homelab://devices refresh fired |

## Decisions Made

- **Preview registered in 4 sites NOT 5 — read-only by design.** Preview MUST NOT be in MUTATING_TOOLS. `test_update_device_fingerprint_preview_in_read_only_tools_phase38` asserts both halves: present in `_READ_ONLY_TOOLS` AND absent from `MUTATING_TOOLS`. `test_update_device_fingerprint_preview_no_notification_phase38` asserts the negative behavior (`assert_not_awaited` on `send_resource_list_changed`). The two tests together prove the read-only contract is wired correctly at all the relevant sites.
- **Preview reads via `get_all_devices` then computes `merge_fingerprint` directly — does NOT call `adapter.update_device_fingerprint`.** This is critical: the preview's value proposition is "show me the merge result without writing." Calling the adapter would couple preview to write-path latency, fire side-effects via `last_seen` / `updated_at` timestamps, and could trigger Plan 04's structured-error envelope on missing hostname (which is desirable behavior but not via the same code path). `test_execute_update_device_fingerprint_preview_phase38` explicitly asserts `mock_adapter.update_device_fingerprint.assert_not_called()` to lock this contract.
- **Role-hint inference rules embedded in prompt body as English text per D-06b.** Proxmox VE → gpu_passthrough; NVIDIA in pci_devices → cuda; AMD VGA → vulkan; TrueNAS/ZFS → zfs. Test asserts ≥3 of `{Proxmox, NVIDIA, AMD, TrueNAS, ZFS}` appear in the body so the rule set is provably present without hard-coding the exact wording — leaves the planner discretion to evolve language without breaking the test.
- **Prompt body references `update_device_fingerprint_preview` alongside `update_device_fingerprint`.** Step 5 of the prompt body explicitly says: *"Use update_device_fingerprint_preview first if you want to confirm the merge before persisting."* This propagates Phase 15's preview-then-commit convention into the agent's runtime instructions for fingerprint configuration — without forcing the agent to use preview every time, but making it the recommended pattern for high-stakes merges.
- **Both new tool-description follow-ups (`discover_and_map`, `ssh_discover`) point to `configure_host_fingerprint` prompt — D-06c belt-and-braces.** Some MCP clients don't surface prompts via `prompts/list`. Even if a client doesn't expose prompts at all, the agent still sees a breadcrumb in the tool description after every successful discovery: *"Recommended follow-up: run the configure_host_fingerprint prompt to capture per-host capability signals for drift detection."*
- **`docs/tool-reference.md` adds new top-level "MCP Prompts" section.** Section is appended at the end of the file (after Proxmox Tools) with anchor links from `update_device_fingerprint`, `update_device_fingerprint_preview`, `discover_and_map`, and `ssh_discover` entries. Sets a precedent for documenting future MCP prompts in the same place — Phase 14 prompts (decommission_device_workflow, deploy_service_workflow, homelab_health_check, connect_to_device) can be retro-documented in this section in a future phase if desired.
- **Out-of-scope ruff-format reformatting on `drift_detection.py` / `test_ast_regression.py` / `test_migration.py` reverted via `git checkout -- ...` per executor SCOPE BOUNDARY rule.** Pre-existing format drift unrelated to Plan 38-05 — same pattern as Plans 03 + 04's pre-existing reformat-and-revert dance. The plan's `<sequential_execution>` block explicitly warned about this.

## Deviations from Plan

None — plan executed exactly as written.

The 5 Wave-0 RED tests landed verbatim per the plan's specification; the prompt registration in Task 2 mirrors the Phase 14 trio pattern; the preview wiring in Task 2 mirrors the Phase 15 4-site convention; the docs sweep added all three documented surfaces (tool, preview, prompt) plus the cross-link breadcrumbs.

The only out-of-band activity was the ruff-format reformat-and-revert dance documented above — plan-anticipated behavior under the executor SCOPE BOUNDARY rule.

## Verification Results

```
uv run pytest tests/test_mcp_prompts.py -k configure_host_fingerprint -x        → 2 passed (registration + body interpolation w/ role hints)
uv run pytest tests/test_tools.py -k preview_phase38 -x                          → 2 passed (execute success path + _READ_ONLY_TOOLS membership)
uv run pytest tests/test_mcp_resources.py -k preview_no_notification -x          → 1 passed (preview fires NO resource notification)
uv run pytest tests/test_tools.py::test_get_available_tools -x                   → 1 passed (count is now 54; preview registered)
uv run pytest tests/test_mcp_prompts.py -x                                       → 14 passed (existing prompt tests stay green)
uv run pytest tests/test_tools.py tests/test_mcp_prompts.py tests/test_mcp_resources.py → 81 passed
uv run pytest tests/ -m "not integration" -x                                     → 752 passed, 14 skipped, 19 deselected
./scripts/quality-check.sh                                                       → All checks passed (ruff, mypy, etc.)
```

### Manual greps (acceptance criteria from plan)

```
grep -n '"configure_host_fingerprint"' src/homelab_mcp/prompt_registry.py        → lines 63, 64 (registry entry); +line 266 dispatcher elif
grep -n 'def _build_configure_host_fingerprint_result' src/homelab_mcp/prompt_registry.py → line 172
grep -n 'configure_host_fingerprint' src/homelab_mcp/tool_schemas/network_tools_schema.py → lines 9, 110 (discover_and_map description + update_device_fingerprint description)
grep -n 'configure_host_fingerprint' src/homelab_mcp/tool_schemas/ssh_tools_schema.py     → line 7 (ssh_discover description)
grep -n '"update_device_fingerprint_preview"' src/homelab_mcp/tool_schemas/network_tools_schema.py → line 140 (preview schema entry)
grep -n 'def handle_update_device_fingerprint_preview' src/homelab_mcp/tool_handlers/network_handlers.py → line 141
grep -n 'update_device_fingerprint_preview' src/homelab_mcp/tool_annotations.py           → line 52 (_READ_ONLY_TOOLS entry)
grep -L 'update_device_fingerprint_preview' src/homelab_mcp/server.py                     → file IS returned (preview NOT in MUTATING_TOOLS — verifies negative)
grep -n 'update_device_fingerprint' docs/tool-reference.md                                → 9 hits (>= 2 required: tool entry + preview entry + cross-links)
grep -n 'configure_host_fingerprint' docs/tool-reference.md                               → 2 hits (anchor + section heading)
```

All 9 acceptance-criteria greps return the expected lines/counts. The negative grep on `server.py` (preview NOT in MUTATING_TOOLS) is verified by `test_update_device_fingerprint_preview_in_read_only_tools_phase38`.

## Success Criteria Coverage

- [x] `configure_host_fingerprint` MCP prompt registered in `HOMELAB_PROMPTS` with role-hint inference rules — proven by `test_configure_host_fingerprint_prompt_registered_phase38` + `test_configure_host_fingerprint_prompt_body_phase38`
- [x] `discover_and_map` and `ssh_discover` tool descriptions updated with follow-up notes pointing to the prompt — verified by greps in `network_tools_schema.py:9` and `ssh_tools_schema.py:7`
- [x] Optional `update_device_fingerprint_preview` thin-delegation wrapper added per Phase 15 convention — wired through 4 sites (schema, handler, TOOL_HANDLERS, _READ_ONLY_TOOLS), explicitly NOT in MUTATING_TOOLS; verified by `test_update_device_fingerprint_preview_in_read_only_tools_phase38` + `test_execute_update_device_fingerprint_preview_phase38` + `test_update_device_fingerprint_preview_no_notification_phase38`
- [x] `docs/tool-reference.md` updated so users discover the workflow — TOC + 3 new entries (tool + preview + prompt) + 2 cross-link breadcrumbs (discover_and_map + ssh_discover descriptions)
- [x] Both 2 tasks executed and committed individually with hooks (no `--no-verify`) — `b60cc1b` (test RED) + `8ea8f88` (feat GREEN)
- [x] Commits scoped to plan 38-05 — out-of-scope reformat drift on `drift_detection.py` / `test_ast_regression.py` / `test_migration.py` was reverted via `git checkout --` per executor SCOPE BOUNDARY
- [x] Full unit suite + quality-check green — 752 passed, 14 skipped, 19 deselected; `./scripts/quality-check.sh` exits 0

## Threat Model Coverage

| Threat ID | Plan disposition | Implementation outcome |
| --------- | ---------------- | ---------------------- |
| T-38-05-01 | accept (Tampering — prompt body interpolation) | Confirmed: hostname is interpolated via Python f-string into a narrative text block. Not executed, not used as query/shell parameter. Worst case: malicious hostname containing markdown injection confuses the agent. Single-user homelab scope. |
| T-38-05-02 | mitigate (Tampering — preview handler input filtering) | Confirmed: `RECOGNIZED_TOP_LEVEL` frozen literal in handler restricts which keys reach `merge_fingerprint`. Same set used by Plan 04's update handler. |
| T-38-05-03 | accept (Information Disclosure — preview reads device row) | Preview returns same fingerprint information already exposed via `homelab://devices` resource. No new information channel. |
| T-38-05-04 | mitigate (Spoofing — preview hostname matching) | Confirmed: `next((d for d in devices if d.get("hostname") == arguments["hostname"]), None)` is exact-match string comparison. No regex, no SQL. |
| T-38-05-05 | accept (Repudiation — preview is silent, no audit) | No mutation = no audit need. The corresponding `update_device_fingerprint` call (if the user proceeds) updates `last_seen` / `updated_at` per Plan 04's path. |
| T-38-05-06 | mitigate (Elevation of Privilege — preview annotation correctness) | `_READ_ONLY_TOOLS` membership AND absence from `MUTATING_TOOLS` both asserted by `test_update_device_fingerprint_preview_in_read_only_tools_phase38`. Negative behavior also asserted by `test_update_device_fingerprint_preview_no_notification_phase38` (`assert_not_awaited` on resource notification). |

## Threat Flags

None — Plan 05 introduces no new network endpoints, auth paths, file access patterns, or trust-boundary crossings beyond what existed before. The new MCP prompt is a sibling of the existing Phase 14 prompts (`connect_to_device`, `deploy_service_workflow`, etc.) and uses the same registration trio. The new MCP tool is a read-only sibling of `update_device_fingerprint` (Plan 04) and uses the same `merge_fingerprint` helper without writing.

## Known Stubs

None — every code path lands real data. The prompt body is fully written (no "TODO" placeholders, no "coming soon" markers). The preview handler is fully implemented and round-trips through `merge_fingerprint`. The docs entries fully describe the new surfaces with examples and return shapes.

## Notes for Plan 06

- **Plan 06 is unblocked.** All Phase 38 source code changes (Plans 01-05) are now landed. Plan 06's job is the end-to-end integration test against a Debian Docker container (per the plan list at `.planning/ROADMAP.md` line 159). The integration test should:
  1. Spin up the Debian Docker container fixture from `tests/integration/conftest.py:19-78`.
  2. Call `discover_and_map` against the container — assert the fingerprint sub-dict is populated (kernel_name=Linux, kernel_version present, package_fingerprint starts with `sha256:`).
  3. Optionally call `update_device_fingerprint` with a fake capability and assert the round-trip via `get_network_sitemap`.
  4. Optionally call `update_device_fingerprint_preview` with a different fake capability and assert the response shows the merge but the stored row is unchanged.
- **Phase 39 is unblocked on the agent-instruction side.** The `configure_host_fingerprint` prompt + the underlying `update_device_fingerprint` tool give Phase 39's `changed`-bucket detection a known-shape, agent-populated baseline to diff against. Phase 39 will read `device['fingerprint']` from `get_all_devices()` (Plan 03 substrate) and diff against the current live-probe state per discovery run.
- **The prompt is a candidate for retro-documentation in `docs/tool-reference.md` MCP Prompts section.** Phase 14's existing prompts (decommission_device_workflow, deploy_service_workflow, homelab_health_check, connect_to_device) are not yet documented in `tool-reference.md`. The new "MCP Prompts" top-level section establishes the pattern; a follow-up commit could backfill those four entries to bring the docs to full coverage. Captured here as a deferred polish item, not a Plan 05 blocker.

## User Setup Required

None — no external service configuration required. The new MCP prompt is auto-discoverable via the existing `prompts/list` endpoint as soon as the server is restarted (or re-imported in tests). The new preview tool is auto-discoverable via the existing `tools/list` endpoint. The docs are static markdown — no rebuild step.

## Next Phase Readiness

- **Plan 06 (integration test) unblocked.** Source code is complete; Plan 06 is purely additional test coverage against the Docker fixture.
- **Phase 39 (changed-bucket detection — DRFT-19) unblocked on the agent-instruction side.** The agent can now follow the `configure_host_fingerprint` prompt to build per-host capability tracking baselines that Phase 39's drift detection will diff against. Phase 39's actual diff logic is its own implementation phase.
- **v1.7.1 lifecycle hooks (LIFE-01..04, LIFE-09, LIFE-10) unblocked on the persistence + preview side.** VM/LXC/Proxmox-script touchpoints can reuse `update_device_fingerprint` (Plan 04) and `update_device_fingerprint_preview` (Plan 05) as the persistence + dry-run paths. The merge contract (top-level overwrite + capabilities deep-merge) handles all three touchpoints identically to the discovery-time touchpoint.

## Self-Check

- [x] `src/homelab_mcp/prompt_registry.py` registers `configure_host_fingerprint` in HOMELAB_PROMPTS (line 63), defines `_build_configure_host_fingerprint_result` (line 172), and routes via dispatcher elif (line 266) — VERIFIED (3 grep hits)
- [x] `src/homelab_mcp/tool_schemas/network_tools_schema.py` has `update_device_fingerprint_preview` schema entry at line 140 + discover_and_map description points to configure_host_fingerprint at line 9 — VERIFIED (greps)
- [x] `src/homelab_mcp/tool_schemas/ssh_tools_schema.py` ssh_discover description points to configure_host_fingerprint at line 7 — VERIFIED (grep)
- [x] `src/homelab_mcp/tool_handlers/network_handlers.py` defines `handle_update_device_fingerprint_preview` at line 141 — VERIFIED (grep)
- [x] `src/homelab_mcp/tool_handlers/__init__.py` imports + routes `handle_update_device_fingerprint_preview` (lines 32 + 93) — VERIFIED (greps)
- [x] `src/homelab_mcp/tool_annotations.py` `_READ_ONLY_TOOLS` contains `update_device_fingerprint_preview` at line 52 — VERIFIED (grep)
- [x] `src/homelab_mcp/server.py` MUTATING_TOOLS does NOT contain `update_device_fingerprint_preview` — VERIFIED (negative grep returns the file unchanged from Plan 04 — preview correctly absent)
- [x] `docs/tool-reference.md` contains entries for update_device_fingerprint, update_device_fingerprint_preview, configure_host_fingerprint MCP prompt — VERIFIED (greps return 9+2 hits)
- [x] `tests/test_mcp_prompts.py` contains both new prompt tests — VERIFIED (pytest --collect-only -k configure_host_fingerprint reports 2 tests)
- [x] `tests/test_tools.py` contains both new preview tests + count assertion bumped to 54 — VERIFIED (pytest --collect-only -k preview_phase38 reports 2 tests)
- [x] `tests/test_mcp_resources.py` contains the no-notification test — VERIFIED (grep)
- [x] Commit `b60cc1b` (test RED gate) exists — VERIFIED
- [x] Commit `8ea8f88` (feat GREEN gate) exists — VERIFIED
- [x] All 5 Plan 05 tests pass — VERIFIED (pytest run shown in Verification Results)
- [x] Full unit suite green (752 passed) — VERIFIED
- [x] `./scripts/quality-check.sh` exits 0 — VERIFIED
- [x] No out-of-scope reformat noise leaked into the 2 commits — VERIFIED (drift_detection.py / test_ast_regression.py / test_migration.py reverted before Task 2 commit)

## Self-Check: PASSED

---
*Phase: 38-sitemap-fingerprint-schema*
*Completed: 2026-04-26*
