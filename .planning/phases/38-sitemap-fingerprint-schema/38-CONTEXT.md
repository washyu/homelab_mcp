# Phase 38: Sitemap Fingerprint Schema - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Add fingerprint-detection fields to sitemap rows so OS-level changes (kernel updates, package changes, capability regressions like Vulkan/GPU-passthrough breakage) are detectable as drift in Phase 39's `changed` bucket (DRFT-19).

Phase 38's substrate has two layers:

1. **Universal core probes** that `discover_and_map` / `ssh_discover_system` always run on every host (best-effort): kernel name + version, OS name + version, package fingerprint digest. These satisfy DRFT-20's literal wording.
2. **Per-host freeform capabilities** that the AGENT — not the probe code — populates by interpreting the discovery payload, asking the user what to track on this host, optionally using `ssh_execute_command` to fill gaps, and persisting through a new `update_device_fingerprint` MCP tool.

Scope anchor: ROADMAP.md §Phase 38 + REQUIREMENTS.md §DRFT-20.

**This phase delivers exactly one requirement** (DRFT-20) plus the SC-4 reliability discipline (Phase 35 D-05's `_run_with_timeout` pattern, already enforced by the existing AST guard at `tests/test_ast_regression.py:447`).

Out of this phase:
- The `changed` detection logic that diffs stored vs current fingerprint values — Phase 39 (DRFT-19).
- Role tags (`tags` column on devices), role-aware drift profiles (gateway routing, NAS expected-services), and role-driven default probe sets — v1.7.2 (TAGS-* + ROLE-*).
- Lifecycle-hook fingerprint touchpoints — `create_proxmox_vm`, `create_proxmox_lxc`, Proxmox community-script onboarding all live in v1.7.1 (LIFE-01..04, LIFE-09, LIFE-10). Phase 38 ships only the discovery-time path (`discover_and_map` / `ssh_discover_system` + the new `configure_host_fingerprint` prompt). v1.7.1 will reuse the same `update_device_fingerprint` tool from those other touchpoints.
- AST meta-tests for forbidden patterns. Phase 38 is a new-feature phase, not footgun-removal — per `feedback_regression_test_scope.md` the meta-test pattern doesn't apply. SC-4 (per-probe `_run_with_timeout` wrapping) is already enforced by Phase 35 D-15's existing AST guard against `ssh_discover_system`; Phase 38 adds new probes inside the same function and inherits the guard.
- Wider PROXMOX_HOST sweep / proxmox tool family error guidance — Phase 40 (POL-03).
- Cross-OS branching logic in probe code. Probe code does the Debian/Linux happy path; cross-OS coverage is the agent's job at runtime via `ssh_execute_command`. No distro detection logic is added to `ssh_tools.py`.
- Auto-inferring drift from kernel/package/capability changes without sitemap re-discovery — already declared out of scope at the milestone level (REQUIREMENTS.md §Out of Scope). Drift surfaces only when the user re-runs discovery.
- CVE/security advisory lookup against the captured kernel/package fingerprint — captured separately as backlog 999.9 (`probe_pending_updates`). Phase 38's fingerprint is for change-detection, not vulnerability assessment.

</domain>

<decisions>
## Implementation Decisions

### Schema Shape (DRFT-20)

- **D-01 (single freeform `fingerprint` JSON column):** Add one new column to the `devices` table on SQLite (`fingerprint TEXT` holding a JSON-serialized object). On Postgres, the new keys land inside the existing `system_info` JSONB column — no schema change needed on the Postgres side beyond the universal-core key additions and the `capabilities` sub-key. `get_all_devices()` flattens the Postgres path back to a top-level `fingerprint` key for parity with SQLite (Phase 35 D-09b convention). One blob per device. The agent populates whatever sub-keys are relevant per host; Phase 39 diffs whatever keys exist in both stored and current. No separate `tracking_config` field — "what to track on this host" is implicit as "whatever keys have been populated for this host."
- **D-02 (top-level structure inside `fingerprint` JSON):**
  ```
  {
    "kernel_name": "Linux",                    // uname -s
    "kernel_version": "6.5.13-1-pve",          // uname -r
    "os_name": "Proxmox VE",                   // /etc/os-release PRETTY_NAME (or NAME)
    "os_version": "8.2.4",                     // /etc/os-release VERSION_ID
    "package_fingerprint": "sha256:abc123...", // sha256 of `dpkg -l` (or rpm -qa) sorted output
    "capabilities": {                          // freeform, agent-populated, per-host
      // examples — no fixed schema:
      "vulkan": {"available": true, "loader_version": "1.3.275"},
      "gpu_passthrough": {"iommu_groups": 14, "vfio_loaded": true, "cmdline": "intel_iommu=on,iommu=pt"},
      "cuda": {"driver_version": "535.183.06", "runtime_version": "12.2"}
    }
  }
  ```
  Top-level keys (`kernel_*`, `os_*`, `package_fingerprint`) are populated by discovery probe code. `capabilities` is populated by the agent via `update_device_fingerprint`. Empty `capabilities: {}` is the default for newly-discovered hosts that haven't gone through the agent's per-host Q&A yet.
- **D-03 (column naming on SQLite):** New SQLite column is `fingerprint TEXT` (single column). Phase 35 D-09c established the column-per-field convention for usb/pci/block, but capabilities is genuinely freeform per host; per-field columns aren't workable. Drift on the universal-core fields can still query into the JSON via `JSON_EXTRACT(fingerprint, '$.kernel_version')` if needed, but Phase 38 doesn't add SQL convenience views — Phase 39's diff code reads the JSON directly.

### Universal Core Probes (DRFT-20 + SC-1, SC-3, SC-4)

- **D-04 (probes inside `ssh_discover_system`):** Three new probes are added to the existing `ssh_discover_system` function in `src/homelab_mcp/ssh_tools.py` (the same function that already does CPU/memory/disk/network/USB/PCI/block):
  - `uname -s` → `kernel_name`
  - `uname -r` → `kernel_version`
  - `cat /etc/os-release` → parse `PRETTY_NAME` (fallback to `NAME` + `VERSION_ID` if absent) → `os_name`, `os_version`
  - `dpkg -l 2>/dev/null | sort | sha256sum` → `package_fingerprint`. On hosts without dpkg, the probe's exit_status is non-zero and the field stays absent (Phase 35 `partial: True` semantics fire automatically). No fallback to `rpm -qa` in probe code — non-Debian hosts get the field absent and the agent decides whether to fill it via `ssh_execute_command`.
- **D-04a (probe wrapping):** Every new probe MUST be wrapped with `_run_with_timeout(conn, "<cmd>", cmd_name="<name>", timed_out=timed_out_commands)` — the same helper Phase 35 D-05 introduced. SC-4 demands this; the existing AST guard (`tests/test_ast_regression.py:447 test_ssh_discover_system_wraps_every_conn_run_phase35`) already enforces it for any new `conn.run` call inside `ssh_discover_system`. No new AST guard required.
- **D-04b (payload location):** New keys land in the discovery JSON payload under a top-level `fingerprint` sub-dict, mirroring the existing `cpu`, `memory`, `disk`, `network`, `usb_devices`, `pci_devices`, `block_devices` siblings. The full discovery payload becomes:
  ```
  {
    "status": "success",
    "hostname": "...",
    "connection_ip": "...",
    "data": {
      "cpu": {...},
      "memory": {...},
      ...existing keys...,
      "fingerprint": {
        "kernel_name": "Linux",
        "kernel_version": "6.5.13-1-pve",
        "os_name": "Proxmox VE",
        "os_version": "8.2.4",
        "package_fingerprint": "sha256:..."
      }
    },
    "partial": true,         // existing Phase 35 flag — fires if any probe (new or old) timed out / unavailable
    "timed_out_commands": ["dpkg-fingerprint"]   // existing Phase 35 list
  }
  ```
  `capabilities` is NOT in the discovery payload — it's added later by the agent via `update_device_fingerprint`.
- **D-04c (parse_discovery_output mapping):** `sitemap.parse_discovery_output` (in `src/homelab_mcp/sitemap.py`) gets a new branch: when `data["fingerprint"]` exists, JSON-serialize it as the value of the new `fingerprint` field on `NetworkDevice`. Existing `os_info` field stays for back-compat (continues to be populated from `data["os"]` if discovery payload provides it; new `os_name`/`os_version` live inside `fingerprint`). Phase 39 reads the new fields; existing consumers (`analyze_network_topology`) continue reading `os_info`.

### Persistence Path (D-05)

- **D-05 (new MCP tool `update_device_fingerprint`):** Phase 38 ships a new MCP tool registered in `tools.py` (or wherever the tool registry lives — verify during research). Signature:
  ```
  update_device_fingerprint(hostname: str, fingerprint: dict) -> dict
  ```
  Behavior:
  1. Look up the device row by hostname (Phase 35 hostname-as-natural-key path).
  2. Read existing `fingerprint` JSON from the row (default `{}` if null).
  3. Merge incoming `fingerprint` dict:
     - Top-level keys (`kernel_name`, `kernel_version`, `os_name`, `os_version`, `package_fingerprint`) — overwrite (last write wins). Lets the agent correct values it learned via `ssh_execute_command`.
     - `capabilities` sub-dict — deep-merge: incoming keys overwrite, missing keys preserve. So calling `update_device_fingerprint("hostX", {"capabilities": {"vulkan": {...}}})` only touches the `vulkan` sub-key, leaving any pre-existing `gpu_passthrough` etc. intact.
  4. Write the merged JSON back to the row via `db_adapter.store_device` (or a new lighter adapter method if the planner prefers). `last_seen` and `updated_at` get refreshed.
  5. Return the merged fingerprint as the response payload (so the agent can confirm what was persisted).
  Errors: missing hostname → structured error pointing to `discover_and_map`; malformed JSON dict → schema-level validation rejection (MCP framework gates on the JSON Schema).
- **D-05a (no auth gating in Phase 38):** `update_device_fingerprint` accepts any caller. There is no per-host write authorization in Phase 38 — homelab single-user scope makes it superfluous. Mirrors how `discover_and_map` already accepts any caller.
- **D-05b (input schema permissive but bounded):** The MCP tool's `inputSchema` accepts `fingerprint` as `type: object` with no required sub-keys. Only the recognized top-level keys (`kernel_name`, `kernel_version`, `os_name`, `os_version`, `package_fingerprint`, `capabilities`) are validated by the schema; unknown top-level keys are silently dropped to keep the structure stable. Inside `capabilities`, anything goes (`additionalProperties: true`). Catches typos at the protocol boundary while keeping the per-host capability vocabulary fully open.
- **D-05c (preview variant per Phase 15 convention):** Add `update_device_fingerprint_preview` as a thin delegation wrapper (per Phase 15 D-* preview-tool conventions and v1.2 6 `*_preview` shipped). `readOnlyHint=True`. Returns the dry-run merge result without writing. Agent can use this to confirm a merge before committing. Optional but matches existing tool-surface convention; planner may defer if scope is tight (then captured as backlog).

### Agent Instruction Layer (D-06)

- **D-06 (new MCP prompt `configure_host_fingerprint`):** Phase 38 adds a new MCP prompt template registered in `src/homelab_mcp/prompt_registry.py`. Mirrors Phase 14's pattern (`connect_to_device`, `decommission_device_workflow`, `deploy_service_workflow`, `homelab_health_check`). Argument: `hostname: str` (required).

  Prompt body (rough outline — planner finalizes):
  1. Read the current sitemap row for `hostname` via `get_network_sitemap`. If not found, redirect user to `discover_and_map` first.
  2. Interpret the discovery payload's role hints from existing fields. Examples (planner decides level of specificity):
     - `os_name` contains "Proxmox VE" → likely a Proxmox host; suggest tracking `gpu_passthrough` (IOMMU groups, vfio modules), VM-passthrough kernel cmdline, ZFS module if present.
     - `pci_devices` contains "NVIDIA" → likely a GPU host; suggest tracking CUDA driver/runtime version, nvidia-smi-reported driver version.
     - `pci_devices` contains "AMD" + "VGA" → suggest tracking ROCm libraries, mesa-vulkan-drivers version.
     - `block_devices` show ZFS pool members or `os_name` contains "TrueNAS" → suggest tracking ZFS module version, expected-running services (note: full role profile lands in v1.7.2; Phase 38 captures whatever the user wants to track).
  3. Ask the user (free-form conversational): "Based on what I see on `hostX`, here are signals I'd suggest tracking as drift indicators: [bulleted list with rationale]. Should I track these? Anything else to add?"
  4. For each agreed signal: use `ssh_execute_command` to capture the current value (the agent picks the right command per host — `vulkaninfo --summary | head`, `nvidia-smi --query-gpu=driver_version --format=csv,noheader`, etc.).
  5. Build a `capabilities` dict from the captured values and call `update_device_fingerprint(hostname, {"capabilities": {...}})`.
  6. Confirm the persisted fingerprint to the user.

  This is the discovery-time touchpoint Phase 38 owns. VM/LXC/Proxmox-script touchpoints are v1.7.1's job and will reuse `update_device_fingerprint` from those flows.
- **D-06a (prompt as instruction, not tool callback):** The prompt body is plain narrative instructions interpolated with `hostname`. The MCP client surfaces the prompt to the agent; the agent follows the steps in conversation with the user. There is no tool-side state machine, no required tool-call sequence, no per-step return validation. This is the "static instruction" path the user picked over a wired callback — relies on agent compliance with prompt instructions, which Phase 14's existing prompts have shown is sufficient for similar flows.
- **D-06b (role-hint inference rules — Claude's discretion):** The exact rule set baked into the prompt body for "if you see X in discovery payload, suggest tracking Y" is left to the planner. Recommended starting set (planner may polish): Proxmox VE → gpu_passthrough; NVIDIA in pci_devices → cuda; AMD VGA + Vulkan-relevant → vulkan; TrueNAS / ZFS pool members → zfs. Rules go in the prompt body as English text; agent applies them. No code-side classifier.
- **D-06c (tool description echoes the prompt):** Even with the prompt template as the primary instruction surface, `discover_and_map`'s description in `tools.py` SHOULD reference `configure_host_fingerprint` as a recommended follow-up step (one sentence). MCP clients that don't surface prompts will at least get the agent breadcrumb via tool description. Same hint added to `ssh_discover_system`. This is belt-and-braces around D-06's relying-on-prompt-discovery.

### Discovery Payload Backward Compat (D-07)

- **D-07 (back-compat for existing `os_info` field):** The Phase 35-era `os_info` field on `NetworkDevice` (and the SQLite `os_info` column) stays. `parse_discovery_output` continues to populate it from `data["os"]` when present. Phase 38 ADDITIONALLY populates the new `fingerprint` JSON's `os_name`/`os_version` from `data["fingerprint"]["os_name"]`/`["os_version"]`. Existing consumers (`analyze_network_topology`) read `os_info`; new consumers (Phase 39 drift detection) read `fingerprint.os_name` / `fingerprint.os_version`. Both fields are populated on every successful discovery; cleanup (deprecating `os_info` once Phase 39 is stable) is captured as deferred.

### Migration (SC-3)

- **D-08 (SQLite ALTER TABLE ADD COLUMN):** New migration step in `src/homelab_mcp/migration.py` `run_sqlite_migrations`. Mirrors Phase 35 D-09c verbatim:
  ```python
  cursor.execute("PRAGMA table_info(devices)")
  existing_columns = {row[1] for row in cursor.fetchall()}
  if "fingerprint" not in existing_columns:
      cursor.execute("ALTER TABLE devices ADD COLUMN fingerprint TEXT")
      conn.commit()
      applied_migrations.append("add_column_fingerprint")
  ```
  Idempotent — no banner needed (Phase 35 D-09c added 3 columns silently; Phase 38 follows the same convention). Old rows get NULL `fingerprint`; re-discovery populates them. SC-3 satisfied.
- **D-08a (Postgres — no schema change needed):** New keys land inside the existing `system_info` JSONB column. No DDL migration; the JSONB is permissive of new sub-keys. Phase 38's Postgres-side change is purely in `store_device` (D-09) and `get_all_devices` (D-10).
- **D-08b (schema-rebuild branch update):** The Phase 35 schema-rebuild branch in `migration.py:149-178` builds a `devices_new` table when stale UNIQUE(hostname, connection_ip) is detected. That CREATE TABLE block needs `fingerprint TEXT` added to its column list, AND the `target_cols` list at line 185 needs `fingerprint` added so the dynamic column copy includes it. Failing to update this branch would mean: a pre-Phase-35 DB upgrading through Phase 38's migration path could lose the `fingerprint` column on rebuild. Idempotent guard already exists; just needs the new column included.
- **D-08c (no migration banner):** Adding columns is silent (Phase 35 D-09c convention). Banners are reserved for table drops and architectural shifts (Phase 33 ssh_credentials, Phase 36 drift_baselines).

### Database Adapter Updates (D-09, D-10)

- **D-09 (`SQLiteAdapter.store_device` accepts `fingerprint`):** Update both the UPDATE and INSERT branches in `database.py:218-294` to include `fingerprint` (param → row). Same pattern as Phase 35 D-09b for usb_devices/pci_devices/block_devices. The hostname-as-natural-key match clause is unchanged (the existing AST guard at `tests/test_ast_regression.py:392 test_store_device_matches_on_hostname_alone_phase35` continues to enforce).
- **D-09a (`PostgreSQLAdapter.store_device` lands `fingerprint` in `system_info` JSONB):** The Postgres branch builds the `system_info` dict at lines 557-583. Add a `fingerprint` key to that dict from `device_data.get("fingerprint")` (which arrives as a JSON string from `parse_discovery_output`'s `json.dumps`). Need to re-parse the JSON string back to a dict before placing into `system_info` — or change `parse_discovery_output` to store as already-parsed dict and SQLite serializes at write time. Planner picks the cleaner path (recommended: parse in adapter consistent with Phase 35 D-09b's `_maybe_json_load` helper).
- **D-10 (`PostgreSQLAdapter.get_all_devices` flattens `fingerprint`):** Add `"fingerprint": system_info.get("fingerprint")` to the flattening dict at lines 686-708 so SQL consumers see top-level `fingerprint` key (matching SQLite). Mirrors Phase 35 D-09b's `usb_devices/pci_devices/block_devices` flattening additions.

### `update_device_fingerprint` Adapter Method (D-11)

- **D-11 (lightweight adapter method or piggyback on store_device):** Two implementation options:
  - (Option A — recommended) Add `update_device_fingerprint(hostname, fingerprint_dict)` method to both `DatabaseAdapter` ABC and concrete adapters. SQLite reads existing `fingerprint`, parses JSON, merges (per D-05's deep-merge for `capabilities`, overwrite for top-level), writes back. Postgres uses JSONB merge (`jsonb_set` or `||` operator with deep-merge logic in Python). Cleaner separation of concerns.
  - (Option B — fallback) The MCP tool handler reads the device row via `get_all_devices`, merges in Python, calls `store_device` with the full merged record. Less efficient (full row write); but no adapter changes needed.
  Planner picks; A recommended for clean separation, B acceptable if A's scope balloons. Either way the merge logic is in one place.

### Tests (D-12)

- **D-12 (functional tests, no AST meta-tests):** Per `feedback_regression_test_scope.md` — Phase 38 is a new-feature phase. Functional + unit tests only. Recommended test files (planner picks final naming):
  - `tests/test_sitemap_fingerprint.py` (or extend `tests/test_sitemap.py`) — `parse_discovery_output` populates `fingerprint` from a fixture JSON containing `data.fingerprint`; round-trip via SQLite store + get; Postgres path tested via existing `tests/integration/` Docker harness.
  - `tests/test_ssh_tools.py` — extend with a fixture that mocks new probe outputs (uname, /etc/os-release, dpkg) and asserts they land in the discovery payload's `fingerprint` sub-dict; assert `partial: True` fires when any new probe times out.
  - `tests/test_database.py` (extend) — `update_device_fingerprint` adapter method round-trip: insert empty fingerprint, update with kernel_version + capabilities.vulkan, read back and assert deep-merge preserved unrelated keys.
  - `tests/test_tools.py` or `tests/test_tool_handlers.py` — `update_device_fingerprint` MCP tool routing: schema validation, missing-host error, successful merge response.
  - `tests/test_prompt_registry.py` — `configure_host_fingerprint` prompt registration; argument schema accepts `hostname`; prompt body interpolates correctly.
- **D-12a (no Phase 38 AST guards):** SC-4 already enforced by Phase 35 D-15 AST guard against `ssh_discover_system`. New probes inherit the guard automatically. No new AST tests in Phase 38.
- **D-12b (integration test scope):** New probe paths against a real SSH connection should land in `tests/integration/` if the existing Docker harness already covers `ssh_discover_system`. Planner verifies coverage; if missing, adds a basic "discover against a Debian Docker container, assert fingerprint sub-dict is populated" test.

### Documentation (D-13)

- **D-13 (docs sweep):** Update the following:
  - `docs/tool-reference.md` — new entries for `update_device_fingerprint` and (if D-05c picks A) `update_device_fingerprint_preview`. Existing `discover_and_map` and `ssh_discover_system` entries get a one-line note about the `fingerprint` sub-dict in the response payload + a pointer to the `configure_host_fingerprint` prompt.
  - `docs/configuration.md` — no changes (no new env vars).
  - `docs/setup-guide.md` — optional one-paragraph addition describing the discover → configure_host_fingerprint flow as the recommended onboarding for hosts where drift detection matters.
  - README.md — bullet list under "What's New" / current capability table gets `update_device_fingerprint` added to the tool count if a tool count is published there.

### Claude's Discretion

- Exact name of the fingerprint column on SQLite (`fingerprint` recommended; `device_fingerprint` or `system_fingerprint` are equally fine — picks readability over precision).
- Exact name of the new MCP tool (`update_device_fingerprint` recommended; `set_device_fingerprint` would imply replace-not-merge so avoid).
- Exact name of the new MCP prompt (`configure_host_fingerprint` recommended; `setup_drift_tracking` or similar would also work — picks consistency with existing `connect_to_device` / `decommission_device_workflow` naming).
- Whether `update_device_fingerprint_preview` (D-05c) ships in Phase 38 or is captured as a follow-up. Recommended: ship in Phase 38 to maintain Phase 15's preview-tool convention; defer if scope balloons.
- Adapter strategy for `update_device_fingerprint` — D-11 Option A (dedicated adapter method) vs Option B (piggyback on `store_device`). A recommended; B acceptable.
- Exact role-hint inference rules baked into `configure_host_fingerprint` prompt body (D-06b). Recommended starting set listed; planner polishes language.
- Whether `parse_discovery_output` stores `fingerprint` as a JSON string (matching the existing `network_interfaces` / `usb_devices` / `pci_devices` / `block_devices` convention) or as an already-deserialized dict that the adapter serializes at write time. JSON-string-in-dataclass recommended for consistency with Phase 35 D-09b.
- Whether `os_info` is deprecated in Phase 38 alongside the new `fingerprint.os_name` / `fingerprint.os_version`, or kept indefinitely for back-compat. Recommended: keep indefinitely; deprecation is its own future phase if `analyze_network_topology` migrates to the new fields.
- Test class naming conventions (`TestPhase38Fingerprint` vs feature-named like `TestFingerprintPersistence`) — planner picks per existing `tests/` conventions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 38 Scope

- `.planning/ROADMAP.md` §Phase 38 — Phase goal + 4 Success Criteria (SC-1..SC-4); the scope anchor.
- `.planning/REQUIREMENTS.md` §Active Requirements — DRFT-20 (sitemap schema captures kernel/package/capability fingerprints); §Coverage Map ("Kernel update breaks Vulkan / llama.cpp" → DRFT-19 + DRFT-20); §Future Requirements §v1.7.2 (TAGS-* + ROLE-*) — informs the role-hint inference scope boundary in D-06.
- `.planning/PROJECT.md` §Current Milestone (v1.7) + §Out of Scope (no auto-detect drift, no per-device drift resources). §Constraints (Python 3.12+, asyncssh, MCP). §Key Decisions for sitemap-natural-key + Phase 35 reliability patterns Phase 38 carries forward.
- `.planning/STATE.md` §v1.7 Phase Summary — Phase 38 builds on Phase 36 (drift = sitemap state); ships in parallel with Phase 37.

### Prior Phase Decisions (locked, inherited)

- `.planning/phases/36-drift-sitemap-foundation/36-CONTEXT.md` §Implementation Decisions — D-01 (sitemap-as-source-of-truth), D-09 (per-row credential resolution), D-10/D-10a (per-row resolve + degenerate-row skip). Phase 38 doesn't touch the scan path, but Phase 39's `changed` detection will read the fingerprint Phase 38 stores.
- `.planning/phases/37-drift-output-shape-error-hygiene/37-CONTEXT.md` §Implementation Decisions — D-04 (4-bucket envelope: probed_ok / unreachable / unknown / changed; `changed` will be Phase 39 + Phase 38 fingerprint diff). D-06 (Phase 39 detection logic deferred — Phase 38 ships the data Phase 39 needs).
- `.planning/milestones/v1.6-phases/35-sitemap-discovery-reliability-fix-discover-and-map-field-los/35-CONTEXT.md` §D-01 (hostname-as-natural-key for sitemap rows — Phase 38 keeps), §D-05 (`_run_with_timeout(10s)` per-probe — Phase 38's new probes use the same helper), §D-09a (`partial: True` payload tag on probe timeout — Phase 38 inherits), §D-09b (column-per-field convention for inventory JSON strings — Phase 38 uses ONE column for `fingerprint` because capabilities is freeform), §D-09c (`ALTER TABLE ADD COLUMN` migration pattern — Phase 38 mirrors verbatim).
- `.planning/milestones/v1.0-phases/14-mcp-prompts/...` (or wherever Phase 14 lives) — `prompt_registry.py` pattern; D-06's `configure_host_fingerprint` follows this convention (`connect_to_device`, `decommission_device_workflow`, `deploy_service_workflow`, `homelab_health_check`). Verify exact path during research.
- v1.2 Phase 15 — `*_preview` thin-delegation wrapper convention (`readOnlyHint=True`); D-05c's `update_device_fingerprint_preview` follows.

### Memory / User Feedback

- `~/.claude/projects/C--Users-washy-projects-mcp-python-server/memory/feedback_regression_test_scope.md` — AST meta-tests guard known footguns; new-feature phases use functional + unit tests only. Phase 38 is **new-feature** (adding fields, not removing footguns), so D-12a explicitly skips the AST meta-test pattern. Existing Phase 35 D-15 AST guard at `tests/test_ast_regression.py:447` already covers SC-4.
- `~/.claude/projects/C--Users-washy-projects-mcp-python-server/memory/project_credential_architecture.md` — keyring-only credential pattern; Phase 38 doesn't touch credentials but the existing `resolve_ssh_credentials` flow inside `ssh_discover_system` (which Phase 38 extends) inherits this constraint.

### Source Files Affected

- `src/homelab_mcp/ssh_tools.py` (D-04, D-04a, D-04b)
  - `ssh_discover_system()` (lines ~225-487) — add three probes (uname, /etc/os-release parse, dpkg fingerprint) under the existing `_run_with_timeout` wrapping; assemble `fingerprint` sub-dict at the bottom alongside the existing `cpu`/`memory`/`disk`/etc. payload assembly. The existing `data.os` field is independent and stays.
- `src/homelab_mcp/sitemap.py` (D-04c)
  - `NetworkDevice` dataclass (lines ~34-60) — add `fingerprint: str | None = None` field (JSON-string per Phase 35 D-09b convention).
  - `parse_discovery_output()` (lines ~75-146) — add a branch: when `data["fingerprint"]` exists, JSON-serialize it to `device.fingerprint`.
- `src/homelab_mcp/database.py` (D-09, D-09a, D-10)
  - `SQLiteAdapter.init_schema()` `CREATE TABLE devices` block (lines ~121-149) — add `fingerprint TEXT`.
  - `SQLiteAdapter.store_device()` (lines ~188-300) — UPDATE branch and INSERT branch both add `fingerprint` (param + row).
  - `SQLiteAdapter.get_all_devices()` — verify it returns `fingerprint` (it should, since the SELECT * pattern picks up the new column automatically; planner checks).
  - `PostgreSQLAdapter.init_schema()` (lines ~481-540) — no DDL change (system_info JSONB accommodates).
  - `PostgreSQLAdapter.store_device()` (lines ~548-662) — `system_info` dict at lines ~557-583 gets a `fingerprint` key from `device_data.get("fingerprint")` (parsed back to dict via the existing `_maybe_json_load` helper).
  - `PostgreSQLAdapter.get_all_devices()` (lines ~664-713) — flattening dict at lines ~686-708 adds `"fingerprint": system_info.get("fingerprint")`.
  - (D-11 Option A) `DatabaseAdapter` ABC + `SQLiteAdapter` + `PostgreSQLAdapter` — add `update_device_fingerprint(hostname, fingerprint_dict)` method.
- `src/homelab_mcp/migration.py` (D-08, D-08b)
  - `run_sqlite_migrations()` — add `ALTER TABLE devices ADD COLUMN fingerprint TEXT` step (mirror Phase 35 D-09c block at lines 65-79).
  - Schema-rebuild branch (lines ~149-178) — add `fingerprint TEXT` to the `devices_new` CREATE TABLE; add `fingerprint` to the `target_cols` list (line ~185).
  - `run_postgres_migrations()` — no DDL changes; verify nothing in the existing Postgres path needs updating.
- `src/homelab_mcp/tools.py` (D-05, D-05b, D-06c) — register `update_device_fingerprint` (and optionally `update_device_fingerprint_preview`); add follow-up note to `discover_and_map` and `ssh_discover_system` descriptions referencing `configure_host_fingerprint`.
- `src/homelab_mcp/tool_handlers/` — new handler module or file for `update_device_fingerprint` (planner picks; existing handlers for sitemap CRUD live in their respective files — likely `sitemap_handlers.py` if it exists, or a new module).
- `src/homelab_mcp/prompt_registry.py` (D-06) — register new `configure_host_fingerprint` prompt with `hostname` argument.
- `docs/tool-reference.md` (D-13) — entries for new tool(s) + prompt + payload sub-dict.
- `docs/setup-guide.md` (D-13) — optional one-paragraph onboarding flow note.
- Test files (D-12):
  - `tests/test_sitemap.py` (extend) — fingerprint round-trip.
  - `tests/test_ssh_tools.py` (extend) — new probe assertions; `partial: True` regression.
  - `tests/test_database.py` (extend) — adapter `update_device_fingerprint` round-trip + deep-merge.
  - `tests/test_tools.py` or `tests/test_tool_handlers.py` (extend) — MCP tool routing for `update_device_fingerprint`.
  - `tests/test_prompt_registry.py` (extend) — `configure_host_fingerprint` registration + argument schema.
  - `tests/integration/` — extend the existing discover-against-Docker test if present; otherwise add a basic discover→fingerprint-populated assertion.

### External / Linux Tooling Reference

- `uname -s` / `uname -r` — universal on Linux + BSD; the only truly cross-platform probe in the universal core.
- `/etc/os-release` (https://www.freedesktop.org/software/systemd/man/os-release.html) — standardized on Linux distros for ~10 years; PRETTY_NAME and VERSION_ID are reliable.
- `dpkg -l` — Debian/Ubuntu/Proxmox VE package list; sortable, hashable. `dpkg-query -W` is the more programmatic variant; planner picks. Output volume is on the order of 100KB on a typical Proxmox host — sha256 hashing is O(input), no storage concern.
- `vulkaninfo` (mesa-vulkan-tools / vulkan-tools package) — agent's go-to for Vulkan presence/version checks via `ssh_execute_command` per host.
- `nvidia-smi --query-gpu=driver_version --format=csv,noheader` — agent's go-to for CUDA driver version per host.
- `/proc/cmdline` — kernel command line; agent reads via `ssh_execute_command` for IOMMU passthrough probes.
- `lsmod | grep vfio` — agent reads via `ssh_execute_command` for vfio module presence (passthrough readiness).

### Pattern / Architecture Reference

- `_run_with_timeout()` helper (`ssh_tools.py:490-516`) — Phase 35 D-05's per-probe timeout wrapper. Phase 38's new probes wrap with it (D-04a). Existing AST guard enforces.
- `error_handling.sanitize_error()` — used by Phase 35/36 for error-message scrubbing. Phase 38's `update_device_fingerprint` errors should sanitize per the same convention.
- `db_adapter.get_all_devices()` flattening pattern (Postgres `system_info` JSONB → top-level keys) — Phase 35 D-09b established for usb/pci/block; Phase 38 follows for `fingerprint`.
- `prompt_registry.py` Phase 14 conventions — `connect_to_device`, `decommission_device_workflow`, `deploy_service_workflow`, `homelab_health_check`. `configure_host_fingerprint` follows.
- `*_preview` thin delegation wrapper convention (Phase 15) — `readOnlyHint=True`, dry-run path. `update_device_fingerprint_preview` follows if D-05c ships in Phase 38.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`_run_with_timeout()` helper** (`ssh_tools.py:490-516`) — Phase 35 D-05; Phase 38's three new probes (uname, /etc/os-release, dpkg-fingerprint) wrap with it. Existing AST guard (`tests/test_ast_regression.py:447`) auto-enforces.
- **`partial: True` payload tag + `timed_out_commands` accumulator** — Phase 35; Phase 38 inherits without modification. Missing tools / timed-out probes trip the same flag.
- **`NetworkDevice` dataclass + `parse_discovery_output()` / `store_device()` round-trip** — Phase 35 D-09b for usb/pci/block established the pattern; Phase 38 adds one more JSON-string field (`fingerprint`).
- **Phase 35 D-09c `ALTER TABLE ADD COLUMN` migration** — Phase 38 mirrors verbatim for `fingerprint`.
- **Postgres `system_info` JSONB + `_maybe_json_load` helper** — Phase 35 D-09b; Phase 38 lands `fingerprint` inside `system_info`. Same flatten-on-read pattern in `get_all_devices`.
- **`prompt_registry.py` Phase 14 prompt registration** — Phase 38's `configure_host_fingerprint` follows the same convention.
- **`_HOST_CLUSTER_CACHE` + Phase 34 `resolve_proxmox_credentials`** — irrelevant to Phase 38 directly, but `update_device_fingerprint` has no Proxmox concerns; SSH-side hosts are reachable via the existing keyring-resolved SSH path inside `ssh_discover_system`. No new credential plumbing.
- **Existing `os_info` field on `NetworkDevice`** — D-07 keeps for back-compat. New `fingerprint.os_name` / `fingerprint.os_version` are additive.
- **MCP tool schema validation at protocol boundary** — Phase 38's `update_device_fingerprint` `inputSchema` enforces dict shape before handler invocation; consistent with Phase 32 SCH-01 (enum on `credential_type`).

### Established Patterns

- **`_run_with_timeout(10s)` per-probe in `ssh_discover_system`** — locked since Phase 35; AST-guarded.
- **`partial: True` for any probe miss/timeout** — locked since Phase 35; Phase 38's new probes participate.
- **`ALTER TABLE ADD COLUMN` for SQLite + JSONB sub-key for Postgres** — locked since Phase 35 D-09b/D-09c.
- **Hostname-as-natural-key sitemap upsert** — locked since Phase 35 D-01; Phase 38's `update_device_fingerprint` uses hostname for the lookup.
- **Phase 14 MCP prompt convention** — locked since v1.2; Phase 38's `configure_host_fingerprint` extends the prompt registry, not invents a new mechanism.
- **`*_preview` thin-delegation convention** — locked since Phase 15; D-05c's preview variant follows.
- **MCP tool descriptions reference companion prompts** — Phase 38's discover_and_map / ssh_discover_system descriptions get a follow-up pointer to `configure_host_fingerprint`. Mirrors Phase 18 / Phase 14 prompt-and-tool co-evolution.
- **No AST meta-tests for new-feature phases** — locked by `feedback_regression_test_scope.md`. Phase 38 explicitly opts out (D-12a).

### Integration Points

- **`ssh_discover_system` is the single discovery probe entry point.** All new probes land inside it. The discovery payload it returns flows through `parse_discovery_output` to `store_device`. Phase 38 extends each link of that chain with the new `fingerprint` data; no new entry points.
- **`db_adapter.get_all_devices()` is the single sitemap read funnel** (Phase 36 D-09 established for drift; Phase 39 will use it for `changed` detection). Phase 38 ensures both adapters surface `fingerprint` as a top-level key on the returned row dicts.
- **`update_device_fingerprint` MCP tool is a new entry point** but feeds into the same `db_adapter.store_device` / new `update_device_fingerprint` adapter method. Reuses the existing hostname-natural-key path; no new lookup convention.
- **`configure_host_fingerprint` MCP prompt is a new entry point** for the agent. The prompt is plain instructions — no tool-side state machine. Relies on `ssh_execute_command` (existing tool, v1.0) for gap-fill probes and `update_device_fingerprint` (new) for persistence.
- **Phase 39's `changed` detection (DRFT-19) reads `fingerprint` from `get_all_devices` rows**, runs a fresh discovery, diffs the two `fingerprint` JSONs. Phase 38 ships the read shape Phase 39 needs.
- **v1.7.1 LIFE-* hooks (create_proxmox_vm / create_proxmox_lxc / Proxmox script onboarding) will reuse `update_device_fingerprint`** as the persistence path for VM/container fingerprints. Phase 38 ships the tool; v1.7.1 wires the touchpoints.
- **v1.7.2 TAGS-* / ROLE-* will read `fingerprint` and layer role-driven default probe profiles on top.** Phase 38's freeform `capabilities` sub-dict accommodates whatever role profiles end up specifying.

</code_context>

<specifics>
## Specific Ideas

- **Reframed approach: per-host freeform capabilities instead of fixed schema.** User's pivotal vision in this discussion: rejected the original "every device has columns/fields like `gpu_passthrough_ready`, `vulkan_available`" approach because each system has a different role (gateway, NAS, Ollama server, Pi-hole). Instead: a single freeform `fingerprint` JSON column with a small universal core (kernel, OS strings, package fingerprint) that's universal-ish, and a `capabilities` sub-object the agent populates per host based on what's worth tracking on THIS system. This drives D-01, D-02, D-05, D-06.
- **Agent as the cross-OS adapter, not probe code.** User's principle: probe code does the Linux/Debian happy path; agent uses `ssh_execute_command` to fill gaps on BSD / RHEL / Alpine / etc. Don't add distro detection branches to probe code. Phase 38's only OS-detection in code is reading `/etc/os-release` to populate `os_name` and `os_version` strings — those are stored values, not branching predicates. This drives D-04 (probes attempt happy path; absent fields trigger `partial: True` per Phase 35 convention) and D-06 (prompt body instructs agent to run ssh_execute_command for any signal not in the universal core).
- **"Ask the user what to track per host" as conversational instruction, not wired callback.** User chose the lightweight path: a new MCP prompt template (`configure_host_fingerprint`) with English instructions for the agent to follow during discovery. The agent — not a tool-side state machine — interprets discovery payload role hints, asks the user, runs ssh_execute_command for follow-ups, and persists via `update_device_fingerprint`. Relies on agent compliance with prompt instructions, which Phase 14's existing prompts have shown is sufficient.
- **Discovery touchpoint only in Phase 38; VM/LXC/script touchpoints in v1.7.1.** User's topology: the natural moments to ask "what should we track" are (a) VM/LXC creation, (b) SSH discovery, (c) Proxmox script onboarding. Of those, (a) and (c) are already in v1.7.1's locked scope (LIFE-01..04, LIFE-09, LIFE-10). Phase 38 owns (b). v1.7.1 will reuse Phase 38's `update_device_fingerprint` tool from the other touchpoints — clean tool-surface reuse without scope overlap.
- **`partial: True` semantics inherited from Phase 35 — no new sentinel for absent tools.** User picked the "same flag for missing tools and timeouts" path (D-04a). When `vulkaninfo` isn't installed, the row simply doesn't get a `vulkan` key — the agent doesn't add what it can't measure. No `unsupported` marker. Simpler downstream handling in Phase 39 ("if key absent in either side, can't compare").
- **Universal core = kernel + OS strings + package digest.** User chose the "match DRFT-20 verbatim" universal core: `kernel_name`, `kernel_version`, `os_name`, `os_version`, `package_fingerprint`. Capabilities are 100% per-host opt-in via the agent. Phase 39's `changed` bucket will diff these universal fields out-of-the-box (regardless of whether the agent has set up per-host capability tracking yet).
- **Opaque package digest, not named-subset.** User chose `sha256(`dpkg -l`)` over per-package version tracking. Tradeoff: Phase 39's drift report says "package fingerprint changed" without saying which package. Agent can layer per-package tracking inside `capabilities` if a host's drift story benefits from it (e.g., explicitly track `libvulkan1`, `nvidia-driver-535` as named keys under `capabilities.tracked_packages`). Phase 38 doesn't ship that helper — agent maintains the per-host list.
- **Single freeform JSON column, not per-field columns.** User chose D-01's "one blob" path. Trades SQL queryability for schema flexibility. Phase 39 reads the JSON directly; if a future phase needs `JSON_EXTRACT`-style queryability, that's additive.

</specifics>

<deferred>
## Deferred Ideas

- **Per-VM / per-LXC fingerprints** — Phase 39's DRFT-19 detection focuses on host-level `changed` infrastructure. Per-VM fingerprints are v1.7.1 LIFE-01..04 territory (lifecycle hooks update sitemap on VM create/destroy). Phase 38 ships only host-level fingerprints.
- **Lifecycle-hook integration (VM/LXC/Proxmox-script touchpoints)** — v1.7.1 LIFE-01..04, LIFE-09, LIFE-10. Phase 38 ships the persistence tool (`update_device_fingerprint`) so v1.7.1 can wire it.
- **Role tags + role-driven default probe profiles** — v1.7.2 TAGS-* + ROLE-*. Phase 38's freeform `capabilities` sub-dict accommodates whatever role profiles end up specifying. Until v1.7.2 ships, capability tracking is per-host via the agent's discovery-time Q&A.
- **Auto-detect drift via background polling** — REQUIREMENTS.md §Out of Scope. Drift surfaces only when the user re-runs `discover_and_map` / `scan_infrastructure_drift`.
- **CVE / pending-update advisory lookup against fingerprint** — captured as backlog 999.9 (`probe_pending_updates`). Phase 38 stores fingerprints for change-detection, not vulnerability assessment. Sibling concept; different milestone.
- **Auto-update sitemap when drift detected** — REQUIREMENTS.md §Out of Scope at the milestone level. Drift reports differences; user accepts via re-running `discover_and_map`. Preserves the "kernel update breaks Vulkan" use case where you want an alert, not silent acceptance.
- **`unsupported` sentinel value distinct from `partial: True` for absent tools** — user chose the simpler "same flag" path. If a future phase needs the distinction (e.g., security advisory needs to know "Vulkan was definitively absent" vs "we couldn't probe"), introduce per-key sentinels then.
- **Cross-distro probe branching in code** — user chose "agent fills gaps via `ssh_execute_command`" over distro-detection branches. If the agent route proves too noisy (e.g., users running on RHEL routinely have to walk the agent through dpkg-equivalent manually), reconsider in v1.8.
- **`update_device_fingerprint_preview`** (D-05c) — recommended for inclusion in Phase 38 to maintain the Phase 15 preview-tool convention; planner may defer to a follow-up commit if scope balloons.
- **Per-package version tracking inside `package_fingerprint`** — user chose opaque digest over named-subset. Per-package detail (libvulkan1 from 1.3.250 → 1.3.275) only surfaces if the agent persists named keys under `capabilities.tracked_packages`. Phase 38 doesn't ship a helper; emerges per-host as the agent's discretion.
- **Deprecating `os_info` once `fingerprint.os_name` / `fingerprint.os_version` ship** — D-07 keeps both for back-compat indefinitely. A future phase could migrate `analyze_network_topology` to read the new fields and deprecate `os_info`.
- **SQL convenience views over `fingerprint` JSON** — Phase 38 doesn't add `JSON_EXTRACT`-style materialized columns or virtual columns. If Phase 39's diff queries become slow on the Postgres path, that's where to add JSONB indexes.
- **Schema validation for `capabilities` sub-keys** — D-05b accepts `additionalProperties: true` inside `capabilities`. A future phase could ship a known-capability registry (e.g., enforce `capabilities.vulkan` matches `{available, loader_version}` shape) once v1.7.2 establishes role profiles. Not in Phase 38 scope.
- **Agent retry / backoff on `update_device_fingerprint` failures** — single-shot per call; agent's natural conversation handles retry. No exponential backoff or queue.

</deferred>

---

*Phase: 38-sitemap-fingerprint-schema*
*Context gathered: 2026-04-25*
