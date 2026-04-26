---
phase: 38
slug: sitemap-fingerprint-schema
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-25
---

# Phase 38 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio (versions pinned by `uv sync`) |
| **Config file** | `pyproject.toml` (no separate `pytest.ini`) |
| **Quick run command** | `uv run pytest tests/ -m "not integration" -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~30 seconds (unit, current 732-test state); integration adds ~60s when Docker available |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -m "not integration" -x`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd-verify-work`:** Full suite must be green AND `./scripts/quality-check.sh` must be clean (ruff + mypy + bandit)
- **Max feedback latency:** 30 seconds for the unit slice

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 38-XX-01 | XX | 1 | DRFT-20 | — | New `fingerprint` sub-dict populated by `ssh_discover_system` (kernel_name, kernel_version, os_name, os_version, package_fingerprint) | unit | `uv run pytest tests/test_ssh_tools.py -k fingerprint -x` | ❌ W0 | ⬜ pending |
| 38-XX-02 | XX | 1 | DRFT-20 / SC-4 | — | Every new probe wrapped with `_run_with_timeout`; `partial: True` fires on miss/timeout | AST regression (existing) | `uv run pytest tests/test_ast_regression.py::test_ssh_discover_system_wraps_every_conn_run_phase35 -x` | ✅ EXISTING (line 447) | ⬜ pending |
| 38-XX-03 | XX | 1 | DRFT-20 | — | `parse_discovery_output` populates `NetworkDevice.fingerprint` from `data["fingerprint"]` | unit | `uv run pytest tests/test_sitemap.py -k fingerprint -x` | ❌ W0 | ⬜ pending |
| 38-XX-04 | XX | 1 | DRFT-20 / SC-3 | — | SQLite `ALTER TABLE ADD COLUMN fingerprint TEXT` migration is idempotent + non-destructive | unit | `uv run pytest tests/test_migration.py -k fingerprint -x` | ❌ W0 | ⬜ pending |
| 38-XX-05 | XX | 1 | DRFT-20 / SC-3 | — | Schema-rebuild branch carries `fingerprint` column across rebuild | unit | `uv run pytest tests/test_migration.py -k schema_rebuild -x` | ❌ W0 | ⬜ pending |
| 38-XX-06 | XX | 1 | DRFT-20 | — | SQLite `store_device` round-trips `fingerprint` (UPDATE + INSERT branches); `get_all_devices` returns it | unit | `uv run pytest tests/test_database.py -k "sqlite and fingerprint" -x` | ❌ W0 | ⬜ pending |
| 38-XX-07 | XX | 1 | DRFT-20 | — | Postgres `store_device` lands `fingerprint` inside `system_info` JSONB | integration | `uv run pytest tests/test_database.py -k "postgres and fingerprint" -m integration -x` | ❌ W0 | ⬜ pending |
| 38-XX-08 | XX | 1 | DRFT-20 | — | Postgres `get_all_devices` flattens `fingerprint` to top-level key (parity with SQLite) | integration | `uv run pytest tests/test_database.py -k "postgres and flatten" -m integration -x` | ❌ W0 | ⬜ pending |
| 38-XX-09 | XX | 2 | DRFT-20 | — | `update_device_fingerprint` adapter method does deep-merge on `capabilities` | unit | `uv run pytest tests/test_database.py -k update_device_fingerprint_capabilities -x` | ❌ W0 | ⬜ pending |
| 38-XX-10 | XX | 2 | DRFT-20 | — | `update_device_fingerprint` adapter method overwrites top-level keys (kernel/os/package) | unit | `uv run pytest tests/test_database.py -k update_device_fingerprint_overwrite -x` | ❌ W0 | ⬜ pending |
| 38-XX-11 | XX | 2 | DRFT-20 | — | `update_device_fingerprint` MCP tool routes through `execute_tool` and merges via adapter | unit | `uv run pytest tests/test_tools.py -k update_device_fingerprint_routing -x` | ❌ W0 | ⬜ pending |
| 38-XX-12 | XX | 2 | DRFT-20 | — | `update_device_fingerprint` filters unknown top-level keys (D-05b in handler) | unit | `uv run pytest tests/test_tools.py -k update_device_fingerprint_unknown_keys -x` | ❌ W0 | ⬜ pending |
| 38-XX-13 | XX | 2 | DRFT-20 | — | `update_device_fingerprint` returns structured error on missing hostname (pointer to `discover_and_map`) | unit | `uv run pytest tests/test_tools.py -k update_device_fingerprint_missing_host -x` | ❌ W0 | ⬜ pending |
| 38-XX-14 | XX | 2 | DRFT-20 | — | `update_device_fingerprint` registered in `tool_annotations.py` `_MUTATING_ANNOTATIONS` | unit | `uv run pytest tests/test_tools.py -k annotations -x` | ❌ W0 | ⬜ pending |
| 38-XX-15 | XX | 2 | DRFT-20 | — | `update_device_fingerprint` added to `server.py` `MUTATING_TOOLS` so resource notifications fire | unit | `uv run pytest tests/test_logging_notifications.py -k update_device_fingerprint -x` | ❌ W0 | ⬜ pending |
| 38-XX-16 | XX | 2 | DRFT-20 | — | `configure_host_fingerprint` prompt registered, accepts `hostname`, body interpolates the value | unit | `uv run pytest tests/test_mcp_prompts.py -k configure_host_fingerprint -x` | ❌ W0 | ⬜ pending |
| 38-XX-17 | XX | 3 | DRFT-20 / SC-1 / SC-2 | — | End-to-end discovery against the existing Debian Docker harness populates `fingerprint` sub-dict; before/after re-discovery shows `kernel_version` field as comparable | integration | `uv run pytest tests/integration/test_sitemap_integration.py -k fingerprint -m integration -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs use the `38-XX-NN` placeholder until `gsd-planner` assigns real plan numbers; the planner is responsible for substituting plan/wave fields when it generates per-plan task lists.*

---

## Wave 0 Requirements

- [ ] `tests/test_ssh_tools.py` — refactor brittle `test_ssh_discover_success` (lines 16-152) to use `STDOUT_BY_CMD` lookup pattern (mirror lines 507-525); then add new test methods asserting `fingerprint` sub-dict population and `partial: True` firing on probe miss.
- [ ] `tests/test_sitemap.py` — extend existing `sample_ssh_discovery_success` fixture (line 28) to include a `fingerprint` block; add `test_parse_discovery_output_fingerprint` and `test_store_and_retrieve_fingerprint`.
- [ ] `tests/test_database.py` — extend `TestSQLiteAdapter` and `TestPostgreSQLAdapter` classes with fingerprint round-trip tests + `update_device_fingerprint` adapter method tests (deep-merge, overwrite-on-top-level, missing-hostname error).
- [ ] `tests/test_migration.py` — add migration test for the new ALTER TABLE step (idempotency, NULL on old rows, schema-rebuild branch carries new column).
- [ ] `tests/test_tools.py` — add MCP tool routing tests for `update_device_fingerprint` (success, missing hostname, malformed dict, unknown top-level key filter, annotations registration).
- [ ] `tests/test_mcp_prompts.py` — add `configure_host_fingerprint` registration test + builder text-content test (mirror `test_connect_to_device_prompt` at line 96).
- [ ] `tests/test_logging_notifications.py` — extend with assertion that `update_device_fingerprint` fires a resource notification (mirror existing `discover_and_map` / `store_device` patterns).
- [ ] `tests/integration/test_sitemap_integration.py` — extend with a Docker-container discovery test asserting `fingerprint.kernel_name == "Linux"`, `fingerprint.kernel_version` matches `/proc/version`, `fingerprint.package_fingerprint` is non-null and starts with `sha256:`. Reuses the existing `test_container` fixture in `tests/integration/conftest.py:19-78`.

*No new framework install or config-file gap — pytest-asyncio is already installed and conftest is in place.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Agent invocation of `configure_host_fingerprint` prompt produces a coherent per-host conversation that asks the user what to track | DRFT-20 (D-06 prompt body) | The prompt is plain narrative instructions for an LLM agent — there is no tool-side state machine to assert; behavior depends on agent compliance with prompt text. Functional test asserts the prompt body interpolates `hostname` and registers correctly; the conversational quality is exercised end-to-end by the user during real homelab onboarding. | (1) Run `discover_and_map` against a real homelab host (e.g., a Proxmox node). (2) Trigger the `configure_host_fingerprint` prompt via the MCP client. (3) Verify the agent suggests at least one capability to track based on payload role hints (Proxmox → gpu_passthrough; NVIDIA in pci_devices → cuda; etc.). (4) Verify it uses `ssh_execute_command` to fill values and calls `update_device_fingerprint` to persist. (5) Re-run `get_network_sitemap` and confirm `fingerprint.capabilities` contains the agreed entries. |
| Cross-distro probe behavior (RHEL / Alpine / BSD where `dpkg` is absent) | DRFT-20 / SC-1 partial-payload semantics | Phase 38 deliberately keeps probe code Debian-happy-path; gap-filling is the agent's job via `ssh_execute_command`. Cross-distro CI matrix is out of scope per CONTEXT.md. | Optional spot-check: SSH-discover an Alpine container; assert `partial: True` fires and `fingerprint.package_fingerprint` is absent (not present-with-stale-value). Document the absent-key behavior in `docs/tool-reference.md`. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (the 8 Wave 0 items above)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s for the unit slice
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
