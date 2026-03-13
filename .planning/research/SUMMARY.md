# Project Research Summary

**Project:** Homelab MCP Server — v1.2 Protocol Completeness
**Domain:** Python MCP server — PyPI distribution, MCP Prompts, dry-run tool split, drift Resource
**Researched:** 2026-03-12
**Confidence:** HIGH

## Executive Summary

The v1.2 milestone completes the MCP protocol surface of an already-functional homelab automation server. The foundation is solid: the installed mcp 1.9.4 SDK already ships all the types and decorator hooks needed for Prompts support, and the existing codebase patterns (resource readers, tool annotations, dry-run handlers) provide clear templates for every new feature. Zero new runtime dependencies are required. The recommended approach is to implement the four v1.2 features in dependency order — entrypoint fix first (it is a live bug blocking PyPI), then drift Resource, then Prompts, then the dry-run tool split — with each phase building on structural patterns already established in v1.1.

The primary risk is not technical complexity but completeness discipline: each feature requires coordinated updates across multiple registries (schemas, handlers, annotations, resource dicts) and missing any one update produces a silent gap rather than an immediate error. Research identified six critical pitfalls, all of which have clear mechanical prevention strategies. An automated test asserting schema/annotation parity is the single highest-leverage safeguard and should be added at the start of the dry-run split phase to catch any gaps introduced throughout the milestone.

PyPI distribution adds a secondary risk: the package entry point is currently broken (no `main()` function exists in `server.py`), and the `service_templates/*.yaml` files may be silently excluded from the wheel. Both must be fixed and smoke-tested before publishing. Once addressed, the distribution path is straightforward: `uv build` produces a working wheel, `uv publish` with OIDC Trusted Publisher is the recommended publish mechanism, and `uvx homelab-mcp` becomes the install path users will see.

---

## Key Findings

### Recommended Stack

No new runtime dependencies are needed for v1.2. The existing stack — Python 3.12+, uv, mcp[cli] 1.9.4, hatchling build backend — handles all four features without additions. The decision to keep hatchling rather than migrate to `uv_build` is correct: `uv_build` only stabilised mid-2025 and migration adds risk with no functional benefit at this milestone. See `.planning/research/STACK.md` for full rationale.

**Core technologies:**
- **mcp[cli] 1.9.4** (already installed): MCP Prompts SDK support — `@server.list_prompts()` and `@server.get_prompt()` decorators verified present in installed source; capability auto-detection is automatic on registration, matching the existing resources pattern
- **hatchling** (keep as-is): Build backend — correctly packages `src/` layout; requires an explicit `artifacts` rule added to pyproject.toml to ensure `service_templates/*.yaml` files are included in the wheel
- **uv build + uv publish**: PyPI distribution — no additional tooling needed; Trusted Publisher (OIDC) preferred over API token for CI publish; avoids long-lived secret management
- **SQLite** (existing): Drift report cache — new single-row `drift_latest_report` table stores the most recent scan result for the `homelab://drift/latest` resource; uses existing `INSERT OR REPLACE` pattern

### Expected Features

Research cross-referenced against mcp 1.9.4 installed source, MCP spec (2025-06-18), and direct codebase analysis. See `.planning/research/FEATURES.md` for full prioritization.

**Must have (table stakes):**
- `*_preview` tool variants for all 6 destructive tools — annotation accuracy: MCP clients show confirmation dialogs for all non-`readOnlyHint` tools; a dry-run preview that still triggers a "destructive operation" warning is degraded UX; PROJECT.md explicitly targets this; tool count grows 50 → 56 (acceptable)
- MCP Prompts (`prompts/list` + `prompts/get`) with at least 3 homelab workflow templates — completing the MCP protocol surface; Claude Desktop and VS Code both surface the prompts UI; an empty prompt list defeats the purpose
- `homelab://drift/latest` Resource — drift scan data is currently only accessible via tool call; a Resource exposes it passively for AI context and enables `notifications/resources/updated` without re-running the scan
- `uvx homelab-mcp` install path — `[project.scripts]` entry point already exists in pyproject.toml but `main()` is missing; this is a live bug that will crash every user's first install

**Should have (differentiators):**
- `notifications/resources/updated` emitted after `scan_infrastructure_drift` — 5-line addition that lets subscribed clients refresh without polling; extends the Phase 10 notification pattern from v1.1
- Prompts that chain `*_preview` before destructive execution — bakes safety into the workflow, not just individual tools; makes the server meaningfully different from generic homelab automation
- `python -m homelab_mcp` invocation — enabled automatically by creating `__main__.py`; no extra cost

**Defer to v1.3:**
- Auto-publish CI (manual first publish is appropriate while the release process is being proven)
- Per-device drift resources (`homelab://drift/device/{id}`) — requires device-scoped scans not yet implemented
- Dynamic prompts that change based on infra state — adds complexity for minimal benefit in a single-operator homelab
- Background drift polling

### Architecture Approach

All four v1.2 features follow structural patterns already established in v1.1. New features are new modules and registry entries, not architectural changes. The `server.py` file acts as the registration hub (decorator registrations, resource dicts, dispatch branches) while business logic lives in dedicated modules (`prompt_registry.py`, `preview_handlers.py`, `resource_readers.py`). The critical constraint is that `server.py` must not accumulate inline definitions — the established separation of schemas, handlers, annotations, and readers must be maintained. See `.planning/research/ARCHITECTURE.md` for component map and data flow diagrams.

**New or extended components:**
1. `src/homelab_mcp/__main__.py` (new) — `main()` entrypoint for `uvx homelab-mcp` and `python -m homelab_mcp`; consolidates startup logic currently split across `run_server.py` and `server.py`
2. `prompt_registry.py` (new) — `HOMELAB_PROMPTS` dict with `get_all_prompts()` and `get_prompt_by_name()`; mirrors the `tool_schemas/__init__.py` registry pattern exactly
3. `tool_schemas/preview_tools_schema.py` + `tool_handlers/preview_handlers.py` (new) — 6 `*_preview` tool schemas and thin handler wrappers that call existing dry-run paths with `dry_run=True` injected implicitly
4. `resource_readers.py` (extended) — `read_drift_resource()` reading from new `drift_latest_report` SQLite table
5. `database.py` (extended) — `drift_latest_report` single-row table; `upsert_drift_latest()` and `get_drift_latest()` methods using existing `INSERT OR REPLACE` pattern

### Critical Pitfalls

Full analysis in `.planning/research/PITFALLS.md`. Top five by severity and probability for v1.2:

1. **Missing `server.py:main()` breaks `uvx homelab-mcp`** — every user who installs from PyPI gets an `AttributeError` on first run; fix by creating `__main__.py` with a `main()` function and updating the pyproject.toml entry point; smoke-test with `uvx --from ./dist/*.whl homelab-mcp --help` before publishing to PyPI

2. **`service_templates/*.yaml` excluded from wheel** — non-Python files may be silently dropped; fix by adding an explicit hatchling `artifacts` rule and migrating template path resolution to `importlib.resources.files()`; verify by unzipping the wheel and checking for `.yaml` files before publish

3. **`*_preview` tools missing from `tool_annotations.py`** — three-file parallel update (schema, handler, annotations) with no compile-time enforcement; fix by adding a test asserting every key in `get_all_tool_schemas()` has a corresponding entry in `TOOL_ANNOTATIONS`; add this test at the start of the dry-run split phase, before any schema changes

4. **Drift Resource URI not added to `HOMELAB_RESOURCES` dict** — the resource can be read by URI but is invisible to `resources/list`; fix by adding `homelab://drift/latest` to `HOMELAB_RESOURCES` in the same commit as the reader function; add a structural test comparing registered URIs to dispatch cases

5. **Renaming existing destructive tools breaks client allowlists** — the dry-run split must be additive-only; the 6 existing tool names must remain unchanged and keep their `dry_run` parameter for backward compatibility; `*_preview` variants are new entries, not replacements

---

## Implications for Roadmap

Based on research, the implementation dependency graph (confirmed in ARCHITECTURE.md build order) suggests four phases. Ordering is driven by two constraints: the entrypoint bug is a live defect and must be fixed before any PyPI-visible work; the drift Resource should precede Prompts because the most valuable prompt references `homelab://drift/latest`.

### Phase 1: PyPI Entrypoint Fix
**Rationale:** The missing `main()` function is a live bug that will make the package unusable the moment it is published. Structurally isolated — no dependencies on other v1.2 features. Fixing it first also unifies the version reporting and validates the build pipeline before feature work begins.
**Delivers:** `uvx homelab-mcp` works; `python -m homelab_mcp` works; version reporting unified via `importlib.metadata.version()`; `service_templates/*.yaml` confirmed in wheel; pyproject.toml entry point correct
**Addresses:** `uvx homelab-mcp` install path (table stakes)
**Avoids:** Critical Pitfalls 1, 2 (entrypoint crash, YAML exclusion); version triple-divergence pitfall

### Phase 2: Drift MCP Resource
**Rationale:** Extends the established resource reader pattern with the riskiest new integration point (SQLite schema change + `send_resource_updated` notification wiring). Doing this before Prompts means the `homelab_health_check` prompt can reference a functioning `homelab://drift/latest` resource. The empty-state and staleness concerns are well-specified and straightforward to address.
**Delivers:** `homelab://drift/latest` readable resource; `notifications/resources/updated` emitted after scan; `drift_latest_report` SQLite table; empty-state response before first scan
**Addresses:** Drift Resource (table stakes); notifications/resources/updated (differentiator)
**Avoids:** Critical Pitfall 4 (URI not registered); Moderate Pitfalls on stale data, no-scan-yet crash, and exception surfacing as JSON

### Phase 3: MCP Prompts
**Rationale:** Depends on Phase 2 because the `homelab_health_check` prompt references `homelab://drift/latest`. Depends on Phase 1 because Prompts are part of the publishable package. Self-contained new module (`prompt_registry.py`) with minimal server.py surface area — two new decorator registrations only.
**Delivers:** `prompts/list` and `prompts/get` handlers; `prompt_registry.py` with 3–4 workflow templates (`decommission_device_workflow`, `deploy_service_workflow`, `homelab_health_check`, optionally `audit_vm_drift`); `prompts` capability advertised in `initialize` response
**Addresses:** MCP Prompts (table stakes); drift-aware workflow prompts (differentiator)
**Avoids:** Moderate pitfalls on client support gap (prompts as convenience layer over tools, not replacement), argument injection, and missing required argument crashes

### Phase 4: Dry-Run Tool Split
**Rationale:** Last because it touches the most files (schema registry, handler registry, annotations, two new modules) and has no dependents within the milestone. Placing it last isolates its change surface. The annotation coverage test written at the start of this phase also serves as a regression guard for any annotation gaps introduced in Phases 2–3.
**Delivers:** 6 `*_preview` tool variants with `readOnlyHint=True`; tool count 50 → 56; original destructive tools unchanged and backward-compatible; `test_all_tools_have_annotations` coverage test
**Addresses:** `*_preview` variants (table stakes); self-describing preview tools (differentiator)
**Avoids:** Critical Pitfalls 3, 5 (annotation gap, backward compatibility break); response format consistency pitfall (all preview handlers must use `build_dry_run_response()`)

### Phase Ordering Rationale

- Phase 1 must be first: entrypoint bug is a live defect; build pipeline validation unblocks the other phases' ability to be smoke-tested via `uvx`
- Phase 2 before Phase 3: `homelab://drift/latest` resource is referenced by the `homelab_health_check` prompt; shipping Prompts before the resource they depend on produces a degraded user experience
- Phase 4 last: additive-only (no other v1.2 phase depends on `*_preview` tools), widest file footprint, and the annotation coverage test it introduces protects all earlier work
- The `test_all_tools_have_annotations` test should be committed at the very start of Phase 4, before any schema additions, so CI catches gaps immediately

### Research Flags

No phases require `/gsd:research-phase` — all integration points have been verified against the installed mcp 1.9.4 SDK source and existing codebase patterns. All four phases use standard, well-documented patterns.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Established Python packaging patterns; `__main__.py` entry point is standard; `importlib.resources` usage is well-documented
- **Phase 2:** Follows existing resource reader and notification patterns in the codebase exactly; SQLite schema addition is low-risk and follows existing `INSERT OR REPLACE` pattern
- **Phase 3:** SDK decorators verified in installed source; implementation mirrors existing `list_resources` / `read_resource` pattern already in `server.py`
- **Phase 4:** Additive schema/handler/annotation additions following established patterns; `build_dry_run_response()` contract already defined in `dry_run.py`

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All SDK mechanics verified by direct inspection of installed mcp 1.9.4 source; no new dependencies to evaluate; build backend decision corroborated by multiple sources |
| Features | HIGH | Feature set is well-scoped against PROJECT.md spec; table stakes verified against SDK capabilities; anti-features clearly reasoned with client behavior evidence |
| Architecture | HIGH | All four integration points verified against installed SDK source and existing codebase patterns; component boundaries are clear; data flows specified with code references |
| Pitfalls | HIGH | Critical pitfalls identified via direct source inspection (not inference); prevention strategies are mechanical (tests, explicit rules) rather than speculative |

**Overall confidence:** HIGH

### Gaps to Address

- **Package name decision (`homelab-mcp` vs `homelab-mcp-server`):** FEATURES.md recommends renaming `[project.name]` to `homelab-mcp` for a cleaner `uvx homelab-mcp` experience; the name is currently unpublished and available; this decision must be made explicitly before Phase 1 completes and documented in the changelog
- **`uvx --from ./dist/*.whl` smoke test:** Must be run locally before the first PyPI publish; cannot be automated until the first wheel is built; should be documented as a manual gate in the Phase 1 checklist
- **PyPI Trusted Publisher setup:** Requires one-time OIDC configuration at pypi.org before CI can publish without a token secret; must be completed by the project owner before the first publish attempt
- **Prompt argument validation scope:** PITFALLS.md recommends using `validation.py` validators on prompt arguments; the specific validators available for hostname, service name, and vmid formats were not enumerated in research; Phase 3 implementation should audit `validation.py` before wiring up prompt argument validation

---

## Sources

### Primary (HIGH confidence)
- `mcp/server/lowlevel/server.py` (installed, `.venv`) — `list_prompts()`, `get_prompt()` decorator signatures at lines 219–245; `get_capabilities()` auto-detection at lines 181–210
- `mcp/types.py` (installed, `.venv`) — `Prompt`, `PromptArgument`, `GetPromptResult`, `PromptMessage` class definitions confirmed present
- `mcp/server/session.py` (installed, `.venv`) — `send_resource_updated()` line 196; `send_prompt_list_changed()` line 309
- `src/homelab_mcp/server.py` — existing handler patterns; `HOMELAB_RESOURCES` dict; notification block; confirmed absence of `main()` function
- `pyproject.toml` — confirmed broken entry point (`homelab_mcp.server:main` with no `def main`); hatchling build backend; version `0.2.0`
- `src/homelab_mcp/dry_run.py` — `build_dry_run_response()` contract
- `src/homelab_mcp/tool_annotations.py` — annotation patterns for `_DESTRUCTIVE_TOOLS` and `_READ_ONLY_TOOLS`
- [MCP tool annotations: readOnlyHint, destructiveHint](https://blog.marcnuri.com/mcp-tool-annotations-introduction) — client confirmation dialog behaviour
- [MCP SDK issue #396](https://github.com/modelcontextprotocol/python-sdk/issues/396) — inconsistent exception handling in call_tool vs list_resources
- [uv building and publishing packages](https://docs.astral.sh/uv/guides/package/) — build/publish workflow

### Secondary (MEDIUM confidence)
- [MCP Prompts specification (2025-06-18)](https://modelcontextprotocol.io/specification/2025-06-18/server/prompts) — protocol wire format
- [PyPI Trusted Publishers](https://docs.pypi.org/trusted-publishers/) — OIDC keyless publish workflow
- [uv Build backend](https://docs.astral.sh/uv/concepts/build-backend/) — hatchling vs uv_build decision
- [MCP client capability gap (PulseMCP)](https://www.pulsemcp.com/posts/mcp-client-capabilities-gap) — prompts client support landscape
- [MCP prompt injection (Simon Willison, 2025)](https://simonwillison.net/2025/Apr/9/mcp-prompt-injection/) — argument injection risk
- [Dynamic versioning with uv projects](https://slhck.info/software/2025/10/01/dynamic-versioning-uv-projects.html) — single-source version via importlib.metadata

### Tertiary (LOW confidence)
- [Python Build Backends in 2025: uv_build vs Hatchling](https://medium.com/@dynamicy/python-build-backends-in-2025-what-to-use-and-why-uv-build-vs-hatchling-vs-poetry-core-94dd6b92248f) — corroborates uv_build stable date; not sole basis for the hatchling decision

---
*Research completed: 2026-03-12*
*Ready for roadmap: yes*
