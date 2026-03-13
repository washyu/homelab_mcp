# Roadmap: Homelab MCP Server

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-03-11)
- ✅ **v1.1 Safety & Observability** — Phases 6-11 (shipped 2026-03-12)
- 🚧 **v1.2 Protocol Completeness** — Phases 12-16 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-5) — SHIPPED 2026-03-11</summary>

- [x] Phase 1: Architecture Foundation (3/3 plans) — completed 2026-03-08
- [x] Phase 2: Security Hardening (5/5 plans) — completed 2026-03-09
- [x] Phase 3: Functional Completeness (3/3 plans) — completed 2026-03-09
- [x] Phase 4: MCP Protocol Compliance (2/2 plans) — completed 2026-03-11
- [x] Phase 5: Documentation (2/2 plans) — completed 2026-03-11

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 Safety & Observability (Phases 6-11) — SHIPPED 2026-03-12</summary>

- [x] Phase 6: Tech Debt Cleanup (3/3 plans) — completed 2026-03-11
- [x] Phase 7: MCP Resources Plumbing (1/1 plan) — completed 2026-03-11
- [x] Phase 8: Dry-Run Mode (4/4 plans) — completed 2026-03-12
- [x] Phase 9: MCP Resources Live Data (2/2 plans) — completed 2026-03-12
- [x] Phase 10: Resource Notifications (1/1 plan) — completed 2026-03-12
- [x] Phase 11: Drift Detection (5/5 plans) — completed 2026-03-12

Full details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

### 🚧 v1.2 Protocol Completeness (In Progress)

**Milestone Goal:** Complete the MCP protocol surface — Prompts, Resources, and correct dry-run tool semantics — plus PyPI distribution for easier installation.

- [x] **Phase 12: PyPI Distribution** - Fix live entrypoint bug, unify versioning, and validate the wheel before any PyPI publish (completed 2026-03-13)
- [ ] **Phase 13: Drift Resource** - Expose `homelab://drift/latest` as a live MCP Resource with `notifications/resources/updated` after each scan
- [ ] **Phase 14: MCP Prompts** - Implement `prompts/list` and `prompts/get` with three homelab workflow prompt templates
- [ ] **Phase 15: Preview Tool Split** - Add 6 `*_preview` tool variants with `readOnlyHint: true` so MCP clients skip confirmation dialogs
- [ ] **Phase 16: Quality Gate** - Pass all pre-commit checks (ruff, mypy, bandit) cleanly across the full v1.2 change surface

## Phase Details

### Phase 12: PyPI Distribution
**Goal**: Users can install the server with `uvx homelab-mcp` and have it start correctly — the broken entrypoint is fixed, version reporting is unified, and service templates are confirmed present in the wheel.
**Depends on**: Phase 11 (v1.1 complete)
**Requirements**: PKG-01, PKG-02, PKG-03
**Success Criteria** (what must be TRUE):
  1. Running `uvx homelab-mcp --help` after installing from the built wheel prints help text without an `AttributeError` or `ImportError`
  2. Running `python -m homelab_mcp --help` from within a venv with the package installed also prints help text
  3. The version string returned at server startup matches `pyproject.toml` — there is no separate hardcoded version in `__init__.py` or `server.py`
  4. Unzipping the built wheel confirms `service_templates/*.yaml` files are present inside the package directory
**Plans**: 3 plans

Plans:
- [ ] 12-01-PLAN.md — Wave 0 test scaffold (test_packaging.py + updated test_service_installer.py)
- [ ] 12-02-PLAN.md — Package rename, version unification, main() entry point
- [ ] 12-03-PLAN.md — service_installer importlib.resources fix, wheel build, publish

### Phase 13: Drift Resource
**Goal**: The `homelab://drift/latest` resource is registered, readable, and kept current — clients can passively read the latest scan result, receive an update notification after each scan, and get a well-formed empty-state response before any scan has run.
**Depends on**: Phase 12
**Requirements**: DRFT-07, DRFT-08, DRFT-09, DRFT-10
**Success Criteria** (what must be TRUE):
  1. `resources/list` includes `homelab://drift/latest` with correct metadata (name, description, MIME type)
  2. `resources/read homelab://drift/latest` before any scan returns `{"drift_detected": null}` (not an error, not an empty object)
  3. After `scan_infrastructure_drift` completes, `resources/read homelab://drift/latest` returns the full structured report from that scan
  4. After each drift scan, the server emits `notifications/resources/updated` so subscribed clients know to re-fetch without polling
**Plans**: TBD

### Phase 14: MCP Prompts
**Goal**: The server advertises the `prompts` capability and provides three workflow prompt templates that guide AI assistants through safe, structured homelab operations — including one that references the drift resource from Phase 13.
**Depends on**: Phase 13
**Requirements**: PRMT-01, PRMT-02, PRMT-03, PRMT-04
**Success Criteria** (what must be TRUE):
  1. The `initialize` response includes `prompts` in the server capabilities object
  2. `prompts/list` returns at least three prompts: `decommission_device_workflow`, `deploy_service_workflow`, and `homelab_health_check`
  3. `prompts/get decommission_device_workflow` returns a prompt that instructs the AI to call `decommission_device_preview` first and present the result to the user before executing the real operation
  4. `prompts/get homelab_health_check` returns a prompt that instructs the AI to read `homelab://vms`, `homelab://devices`, and `homelab://drift/latest` and summarize infrastructure state
**Plans**: TBD

### Phase 15: Preview Tool Split
**Goal**: All six destructive tools have `*_preview` variants annotated `readOnlyHint: true` — MCP clients show no confirmation dialog for preview calls — while the original six tools remain unchanged and backward-compatible.
**Depends on**: Phase 12
**Requirements**: PREV-01, PREV-02, PREV-03, PREV-04, PREV-05, PREV-06, PREV-07, PREV-08
**Success Criteria** (what must be TRUE):
  1. Calling any of the six `*_preview` tools returns a dry-run structured response without mutating any infrastructure
  2. All six `*_preview` tools are present in `tools/list` with `readOnlyHint: true` and `destructiveHint: false` in their annotations
  3. The six original destructive tools (`decommission_device`, `delete_proxmox_vm`, `remove_vm`, `remove_server`, `destroy_terraform_service`, `rollback_infrastructure_changes`) still exist in `tools/list` with their `dry_run` parameter intact
  4. A test asserts that every key in the tool schema registry has a corresponding entry in the annotations registry — schema/annotation parity is enforced by CI
**Plans**: TBD

### Phase 16: Quality Gate
**Goal**: All pre-commit checks pass cleanly across the entire v1.2 change surface — ruff, mypy, and bandit report zero errors on every file touched in Phases 12-15.
**Depends on**: Phase 15
**Requirements**: QA-01
**Success Criteria** (what must be TRUE):
  1. `uv run ruff check src/ tests/` exits 0 with no warnings or errors across all v1.2 changes
  2. `uv run mypy src/` exits 0 — all new functions, handlers, and modules have complete type annotations with no `Any` escapes
  3. `uv run bandit -r src/` exits 0 — no new medium or high severity security findings introduced
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Architecture Foundation | v1.0 | 3/3 | Complete | 2026-03-08 |
| 2. Security Hardening | v1.0 | 5/5 | Complete | 2026-03-09 |
| 3. Functional Completeness | v1.0 | 3/3 | Complete | 2026-03-09 |
| 4. MCP Protocol Compliance | v1.0 | 2/2 | Complete | 2026-03-11 |
| 5. Documentation | v1.0 | 2/2 | Complete | 2026-03-11 |
| 6. Tech Debt Cleanup | v1.1 | 3/3 | Complete | 2026-03-11 |
| 7. MCP Resources Plumbing | v1.1 | 1/1 | Complete | 2026-03-11 |
| 8. Dry-Run Mode | v1.1 | 4/4 | Complete | 2026-03-12 |
| 9. MCP Resources Live Data | v1.1 | 2/2 | Complete | 2026-03-12 |
| 10. Resource Notifications | v1.1 | 1/1 | Complete | 2026-03-12 |
| 11. Drift Detection | v1.1 | 5/5 | Complete | 2026-03-12 |
| 12. PyPI Distribution | 3/3 | Complete    | 2026-03-13 | - |
| 13. Drift Resource | v1.2 | 0/TBD | Not started | - |
| 14. MCP Prompts | v1.2 | 0/TBD | Not started | - |
| 15. Preview Tool Split | v1.2 | 0/TBD | Not started | - |
| 16. Quality Gate | v1.2 | 0/TBD | Not started | - |
