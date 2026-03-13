# Domain Pitfalls

**Domain:** Python MCP server — v1.2 Protocol Completeness (PyPI packaging, MCP Prompts, dry-run tool split, drift MCP Resource)
**Researched:** 2026-03-12
**Project context:** homelab-mcp-server v1.2, existing lowlevel.Server, hatchling build backend, service_templates YAML files on disk

> **Note:** This file covers v1.2 Protocol Completeness pitfalls.
> v1.1 Safety & Observability pitfalls (dry-run divergence, drift false positives, ResourceManager session wiring, MCP Resource staleness) are appended at the bottom of this file.

---

## Critical Pitfalls

Mistakes that cause broken installs, silent protocol failures, or rewrites.

---

### Pitfall 1: service_templates YAML files excluded from wheel

**What goes wrong:** `service_templates/*.yaml` files live inside the Python package directory (`src/homelab_mcp/service_templates/`) but are not `.py` files. With hatchling as the build backend, non-Python files inside the package tree are included in wheels by default, but this is version-dependent and can be silently broken by an accidental `exclude` rule or a future hatchling upgrade. If the wheel ships without them, `ServiceInstaller` raises `FileNotFoundError` at runtime on any `uvx`-installed deployment.

**Why it happens:** The pyproject.toml declares `[tool.hatch.build.targets.wheel] packages = ["src/homelab_mcp"]`. This covers Python modules. YAML template inclusion relies on hatchling's implicit behaviour, which is fragile under tooling churn. The current code reads templates from `__file__`-relative paths that work in a local clone but depend on disk layout assumptions that wheels do not guarantee.

**Consequences:** Server starts, tools register, `list_available_services` returns names, but any actual `install_service` call fails with a path error. Not caught by unit tests that mock `ServiceInstaller`. Only manifests on installed packages, not in `uv run` dev mode.

**Prevention:**
- Explicitly declare YAML inclusion in pyproject.toml using hatchling's `include` pattern:
  ```toml
  [tool.hatch.build.targets.wheel]
  packages = ["src/homelab_mcp"]
  # Ensure non-Python package data is included
  artifacts = ["src/homelab_mcp/service_templates/*.yaml"]
  ```
- Migrate template path resolution from `__file__`-relative to `importlib.resources.files("homelab_mcp.service_templates")`, which is the correct approach for installed packages and works identically in dev and installed modes.
- Add a build smoke test: unzip the built wheel and assert each YAML filename is present before publishing.

**Detection:** `python -c "import zipfile, glob; [print(zipfile.ZipFile(w).namelist()) for w in glob.glob('dist/*.whl')]"` — scan for `.yaml` in the output.

**Phase:** PyPI packaging phase.

---

### Pitfall 2: Version mismatch between pyproject.toml and `__init__.py`

**What goes wrong:** `pyproject.toml` has `version = "0.2.0"` but `src/homelab_mcp/__init__.py` hard-codes `__version__ = "0.1.0"`. These will continue to diverge with every release. Users checking `homelab_mcp.__version__` programmatically see `0.1.0`; `importlib.metadata.version("homelab-mcp-server")` returns `0.2.0`; the MCP server's `version=` argument in `server.py` hard-codes `"0.2.0"` as a third value. Three sources of truth that can never all be correct simultaneously.

**Why it happens:** The `__init__.__version__` was added before the project migrated to a pyproject.toml-first workflow. Manual synchronisation is unreliable.

**Consequences:** Incorrect version reported in MCP `initialize` response; misleading debug output; CI/release automation that reads `__version__` will be wrong; MCP Inspector shows wrong server version.

**Prevention:** Remove `__version__` from `__init__.py` and read it dynamically from package metadata:
```python
from importlib.metadata import version, PackageNotFoundError
try:
    __version__ = version("homelab-mcp-server")
except PackageNotFoundError:
    __version__ = "dev"  # running from source without install
```
This makes pyproject.toml the single source of truth. The `Server("homelab-mcp", version=...)` instantiation in `server.py` should also use this value.

**Detection:** `grep -rn "__version__" src/` and compare with `grep "^version" pyproject.toml`.

**Phase:** PyPI packaging phase.

---

### Pitfall 3: `uvx homelab-mcp` fails because `server.py:main` does not exist

**What goes wrong:** The pyproject.toml declares `homelab-mcp = "homelab_mcp.server:main"` as the console script entry point. If `server.py` does not export a `main()` function (the existing startup logic lives in `run_server.py`), `uvx homelab-mcp` fails with `AttributeError: module 'homelab_mcp.server' has no attribute 'main'`. This only surfaces when installing from PyPI — local `uv run python run_server.py` continues to work, so the bug is invisible during development.

**Why it happens:** Entry point targets are validated by the build tool at install time by checking that the module is importable and the attribute exists, but this check only happens on the installing machine. If the developer uses `run_server.py` as the dev path and never calls `homelab_mcp.server.main()` directly, the gap is undetected until a user installs the package.

**Consequences:** Every user who installs via `uvx` gets a crash on first run. First impression of the PyPI package is a failure.

**Prevention:**
- Add `def main() -> None:` to `server.py` that replicates the startup logic from `run_server.py`.
- Add a test: `from homelab_mcp.server import main; assert callable(main)`.
- After building, run `uvx --from ./dist/homelab_mcp_server-*.whl homelab-mcp --help` locally to confirm the entry point resolves before publishing to PyPI.

**Detection:** `python -c "from homelab_mcp.server import main"` after `uv sync` — must succeed without error.

**Phase:** PyPI packaging phase.

---

### Pitfall 4: `*_preview` dry-run tools omitted from `tool_annotations.py` — silent annotation gap

**What goes wrong:** Adding 6 `*_preview` tool variants requires parallel updates to three files: the tool schema (in `tool_schemas/`), the tool handler (in `tool_handlers/`), and the annotations registry (`tool_annotations.py`). If annotations are omitted, `get_tool_annotations(name)` returns `None` for the new tools. The server emits those tools without any `readOnlyHint`, `destructiveHint`, or `idempotentHint` annotations. MCP clients that use annotations to gate operations will not recognise preview tools as safe/read-only, defeating the purpose of the split.

**Why it happens:** `tool_annotations.py` is a separate registry with no compile-time enforcement. The three-file parallel update pattern has already caused annotation gaps in the codebase (the existing 50 tools are only complete because of explicit audit). Preview tools will be added during a focused sprint and annotations are the step most likely to be forgotten.

**Consequences:** Preview tools appear unannoted. Clients may prompt users for destructive-tool confirmation even for dry-run previews. MCP Inspector will show preview tools as having no safety metadata.

**Prevention:**
- Add an automated test that asserts every key in `get_all_tool_schemas()` has a corresponding entry in `TOOL_ANNOTATIONS`:
  ```python
  def test_all_tools_have_annotations():
      from homelab_mcp.tool_schemas import get_all_tool_schemas
      from homelab_mcp.tool_annotations import TOOL_ANNOTATIONS
      missing = set(get_all_tool_schemas().keys()) - set(TOOL_ANNOTATIONS.keys())
      assert missing == set(), f"Tools missing annotations: {missing}"
  ```
- This test will fail CI as soon as any new tool (including `*_preview` variants) is added without annotations.

**Detection:** Run the test above after adding preview tool schemas.

**Phase:** Dry-run tool split phase.

---

### Pitfall 5: Renaming existing destructive tools breaks MCP clients that have allowlisted them

**What goes wrong:** Some MCP clients maintain allowlists keyed by tool name, or users have saved workflows/automations referencing specific tool names like `delete_proxmox_vm`. If the dry-run split renames existing destructive tools to `delete_proxmox_vm_preview`, any client configuration or user automation referencing the old name breaks silently — the tool no longer appears in `tools/list` for the old name and the LLM may hallucinate or silently skip the operation.

**Why it happens:** MCP has no tool versioning or aliasing mechanism. A tool name change is a breaking API change. The split feels like a rename ("the old tool becomes the preview") but clients and users experience it as deletion.

**Consequences:** Existing user workflows break after upgrade. Users who have stored prompts or Claude Desktop instructions referencing tool names by name get silent failures.

**Prevention:**
- Keep all existing destructive tool names unchanged. Add `*_preview` variants as new, additional tools (additive-only, not replacement).
- The 6 existing destructive tools (`decommission_device`, `remove_vm`, `remove_server`, `delete_proxmox_vm`, `destroy_terraform_service`, `rollback_infrastructure_changes`) retain their names, schemas, and annotations exactly as they are.
- New `*_preview` variants are separate entries with `readOnlyHint: true` and descriptions that clarify they preview-only.
- Document this in the CHANGELOG as "added `*_preview` variants; original tools unchanged and backward-compatible."

**Detection:** Diff `tools.py` (or `tool_schemas/`) after the phase — zero existing tool names should be removed, only added.

**Phase:** Dry-run tool split phase.

---

### Pitfall 6: `homelab://drift/latest` not added to `HOMELAB_RESOURCES` — resource invisible to clients

**What goes wrong:** The `HOMELAB_RESOURCES` dict in `server.py` drives `handle_list_resources()`. If `homelab://drift/latest` is handled in the `handle_read_resource()` dispatch block but omitted from `HOMELAB_RESOURCES`, the resource can be read by URI (if the client knows it) but is not discoverable. Clients that call `resources/list` to discover available resources will not see it. Documentation may say it exists but MCP Inspector and Claude Desktop will not show it.

**Why it happens:** The `HOMELAB_RESOURCES` dict and the `handle_read_resource` dispatch are in the same file but are two separate data structures. Adding a dispatch case without updating the registry is a common cut-and-paste error.

**Consequences:** The drift resource is not discoverable. Users must know the URI in advance, undermining the MCP discovery model.

**Prevention:**
- Add `homelab://drift/latest` to `HOMELAB_RESOURCES` in the same commit as the reader function.
- Add a test asserting that every URI handled in `handle_read_resource` is registered in `HOMELAB_RESOURCES`. This is the same structural completeness check as the annotations test.

**Detection:** Compare the URI strings in `HOMELAB_RESOURCES.keys()` with the URI patterns matched in `handle_read_resource`.

**Phase:** Drift MCP Resource phase.

---

## Moderate Pitfalls

### Pitfall 1: `homelab://drift/latest` serves stale data with no staleness indicator

**What goes wrong:** The new drift Resource returns the most recent scan result from SQLite. If the last scan was hours ago (or never run), the Resource returns old or null data without signalling staleness. The LLM treats cached data as current state and may recommend incorrect remediation.

**Why it happens:** The existing resource readers (`read_vms_resource`, `read_devices_resource`) already include `scanned_at` timestamps — but a new drift reader added without this discipline will be the odd one out.

**Consequences:** LLM-driven drift remediation acts on stale data. A VM fixed an hour ago still appears as drifted.

**Prevention:**
- Always include `scanned_at` (ISO 8601 UTC) in the drift Resource payload, matching the pattern in `resource_readers.py`.
- Add a `staleness_warning` field when the scan age exceeds a threshold (e.g., 30 minutes): `"staleness_warning": "Drift data is 47 minutes old; run scan_infrastructure_drift to refresh."`
- Document that the Resource is a point-in-time snapshot, not a live stream.

**Phase:** Drift MCP Resource phase.

---

### Pitfall 2: `homelab://drift/latest` crashes when no scan has ever run

**What goes wrong:** If `scan_infrastructure_drift` has never been called, the `drift_baselines` table has no scan result to return. A `read_resource` for `homelab://drift/latest` must return a well-formed response — not raise an unhandled exception, not return an empty body, and not return malformed JSON.

**Why it happens:** The existing resource readers all handle empty-state gracefully (`{"vms": [], ...}`). A drift reader added without the same empty-state discipline will be the first resource to crash on first access.

**Consequences:** `McpError` or unhandled exception on the user's first read of the drift resource; the client may display an unhelpful error or crash.

**Prevention:**
- Mirror the existing pattern: return a structured no-data response:
  ```json
  {"drift_report": null, "scanned_at": null, "status": "no_scan_run",
   "message": "Run scan_infrastructure_drift to generate a drift report."}
  ```
- Add a test for the no-scan-yet case that asserts the response is well-formed and `status == "no_scan_run"`.

**Phase:** Drift MCP Resource phase.

---

### Pitfall 3: MCP Prompts ignored by non-Claude clients

**What goes wrong:** As of the MCP 2025-11-25 specification, `prompts/list` and `prompts/get` are first-class operations, but client support is inconsistent. Claude Desktop supports prompts; many other MCP-compatible clients (Cursor, Continue, custom HTTP clients) do not call `prompts/list` at all and do not declare `prompts` in their `initialize` capabilities. If homelab workflow prompts are designed as the primary user-facing interface, they will be invisible to a large fraction of users.

**Why it happens:** The MCP ecosystem built momentum around tools. Prompts are newer and clients treat them as optional capability.

**Consequences:** Prompts work in Claude Desktop testing but are invisible to other clients. The feature ships but is narrowly useful.

**Prevention:**
- Design prompts as convenience shortcuts layered on top of tools, not as required paths. Every operation achievable via a prompt must also be achievable by direct tool calls.
- Test prompts against MCP Inspector (which supports the full spec) and document which clients support them.
- Do not gate critical functionality behind `prompts/get`.

**Phase:** MCP Prompts phase.

---

### Pitfall 4: Prompt argument injection via unvalidated user-supplied strings

**What goes wrong:** MCP Prompts accept user-supplied argument values (e.g., `hostname`, `service_name`, `vmid`) and interpolate them into rendered message templates. If these values are embedded into shell command strings or path components in the rendered prompt, an adversarial or malformed value can steer the LLM toward unintended tool calls.

**Why it happens:** Prompts are text templates. The rendered message is passed to the LLM as context. The LLM may then call tools based on that context. This is the same attack surface as indirect prompt injection, but the input is user-supplied prompt arguments rather than external data.

**Consequences:** For a homelab server, the blast radius is the user's own infrastructure — data loss, VM deletion, SSH credential exposure. Low external threat, high internal trust risk.

**Prevention:**
- Validate all prompt arguments using the same validators in `validation.py` that tool inputs use: hostname format, IP range, alphanumeric-only service names, vmid numeric range.
- Do not interpolate raw argument values into rendered shell command strings within prompts.
- Keep prompt templates as structured guidance (`"To deploy {service_name}, use the install_service tool"`) rather than raw command strings.

**Phase:** MCP Prompts phase.

---

### Pitfall 5: MCP Prompts handler crashes on missing required arguments

**What goes wrong:** The MCP spec allows prompt arguments to declare `required: true`. The SDK's `prompts/get` handler receives argument values but does not enforce presence of required arguments — it passes whatever the client sends to the handler. If the handler assumes required arguments are present and does not guard against their absence, it raises `KeyError` or `AttributeError` when a client omits them.

**Why it happens:** The SDK treats argument validation as the server's responsibility, not its own (same as tools, where input schema validation is also not enforced). This is consistent behaviour but can surprise developers expecting the SDK to enforce required fields.

**Consequences:** Prompt handlers crash with unstructured internal errors when clients call `prompts/get` without required arguments.

**Prevention:**
- Validate argument presence at the start of each prompt handler. Check for missing required keys explicitly and raise `McpError` with a descriptive message rather than letting a `KeyError` propagate.
- Add tests for each prompt that call `prompts/get` with missing required arguments and assert the error response is well-formed.

**Phase:** MCP Prompts phase.

---

### Pitfall 6: PyPI package name / import name / command name three-way split confuses users

**What goes wrong:** The PyPI package is `homelab-mcp-server` (install with `pip install homelab-mcp-server`), the Python import is `homelab_mcp` (no "server"), and the entry point command is `homelab-mcp`. Users who see the PyPI name may try `import homelab_mcp_server` and get `ImportError`. This is a documentation and discoverability problem, not a functional bug.

**Why it happens:** Python packaging conventions allow and even encourage divergent names, but this creates a three-way split that users must learn explicitly.

**Consequences:** First-time users hit import errors or can't find the command. Documentation confusion leads to GitHub issues.

**Prevention:**
- Make the three-name split explicit in the README installation section with a code block showing each form.
- Evaluate whether the PyPI package can be renamed to `homelab-mcp` (matching the command name) at publication time, since it is currently unpublished and the name is still available.

**Phase:** PyPI packaging phase.

---

### Pitfall 7: `read_resource` exceptions surface as successful JSON rather than McpError

**What goes wrong:** The MCP Python SDK has a documented inconsistency (SDK issue #396): exceptions raised inside `@app.call_tool` handlers are not correctly translated to JSON-RPC error responses — they are returned as plain-text successful responses. While `@app.read_resource` exceptions are documented to propagate as `McpError`, an unhandled non-`McpError` exception in a resource reader may behave differently depending on SDK version.

**Why it happens:** The existing `handle_read_resource` in `server.py` already wraps all non-`McpError` exceptions and returns structured JSON payloads — this is the correct pattern. But a new drift reader that raises a bare exception (e.g., a raw `KeyError`) rather than catching it will bypass this protection if the outer handler's except clause only catches specific types.

**Consequences:** Clients receive a 200-equivalent response with error data embedded in the JSON body rather than a proper JSON-RPC error. Some clients will not recognise this as an error state and will use the malformed payload.

**Prevention:**
- All new reader functions (`read_drift_resource`) must follow the pattern established in `resource_readers.py`: wrap all exceptions in try/except, return structured dicts with `error` or `status` fields, never raise bare exceptions from a reader function.
- The outer `handle_read_resource` dispatch should have a catch-all `except Exception` that wraps unexpected errors as `McpError`, consistent with the existing `RESOURCE_NOT_FOUND` pattern.

**Phase:** Drift MCP Resource phase.

---

## Minor Pitfalls

### Pitfall 1: `uvx homelab-mcp` installs a different version than local dev

**What goes wrong:** `uvx` runs tools from PyPI in isolated ephemeral environments. Users with a local clone at v1.1 who also install via `uvx homelab-mcp@latest` may have two server versions running under different Claude Desktop profiles without realising it. Configuration and tool schemas may differ between versions.

**Prevention:** Document in README that `uvx` always fetches from PyPI. Instruct users who need a specific version to use `uvx homelab-mcp@1.2.0`.

**Phase:** PyPI packaging phase.

---

### Pitfall 2: Tool count in README/docs not updated after adding `*_preview` variants

**What goes wrong:** The README and PROJECT.md currently reference "50 tools." Adding 6 `*_preview` tools without updating documentation creates documentation drift.

**Prevention:** Automate the tool count in CI: `python -c "from homelab_mcp.tool_schemas import get_all_tool_schemas; print(len(get_all_tool_schemas()))"`. Use this number in release notes. Never hard-code the count in prose.

**Phase:** Dry-run tool split phase.

---

### Pitfall 3: `notifications/resources/list_changed` emitted outside request context panics

**What goes wrong:** The SDK's `send_resource_list_changed()` must be called from within an active MCP request context. The existing `MUTATING_TOOLS` pattern in `call_tool` handler gates notification emission correctly. If drift or a background task emits notifications outside a request context, the SDK raises `RuntimeError`.

**Prevention:** Only emit resource notifications from within tool handler post-call paths (the existing pattern). Do not emit from background tasks, lifespan hooks, or module-level code.

**Phase:** Drift MCP Resource phase.

---

### Pitfall 4: `*_preview` tool response format inconsistent with `build_dry_run_response()`

**What goes wrong:** The existing `build_dry_run_response()` in `dry_run.py` returns a flat dict. The existing `_convert_result` fallback in the tool dispatcher handles this. New `*_preview` tools added without using `build_dry_run_response()` will produce ad-hoc response shapes that are inconsistent with each other and with the structured dry-run contract.

**Prevention:** All 6 `*_preview` handlers must call `build_dry_run_response()` and return its output unchanged. Do not add ad-hoc `mode: dry_run` dicts inline in handlers.

**Phase:** Dry-run tool split phase.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|---|---|---|
| PyPI packaging | YAML service templates missing from wheel | Explicit hatchling include rule + wheel smoke test |
| PyPI packaging | `__version__` / pyproject.toml version divergence | Single source via `importlib.metadata.version()` |
| PyPI packaging | Missing `server.py:main` entry point | Add `main()` function; test and smoke-test pre-publish |
| PyPI packaging | Package name / import name / command name confusion | Explicit three-name table in README |
| Dry-run tool split | `*_preview` tools missing from `tool_annotations.py` | Annotation coverage test asserting full parity |
| Dry-run tool split | Renaming existing tools breaks client allowlists | Additive-only: add `*_preview` names, keep originals |
| Dry-run tool split | Ad-hoc response shapes bypassing `build_dry_run_response()` | Enforce single response builder in all preview handlers |
| Dry-run tool split | Tool count docs not updated | Automate count from schema registry |
| MCP Prompts | Clients that don't support prompts silently ignore them | Prompts as convenience layer; tools remain primary path |
| MCP Prompts | Missing required arguments crash handler | Validate arguments at handler entry; raise `McpError` |
| MCP Prompts | Prompt injection via unvalidated argument strings | Use `validation.py` validators on all argument values |
| Drift Resource | No-scan-yet state raises exception | Empty-state handling: return `status: no_scan_run` |
| Drift Resource | Stale data served without staleness indicator | Include `scanned_at` + staleness warning in payload |
| Drift Resource | URI omitted from `HOMELAB_RESOURCES` dict | Add to registry atomically with reader function |
| Drift Resource | Exception in reader surfaces as successful JSON | Follow `resource_readers.py` try/except pattern exactly |

---

## Sources

- [MCP Prompts specification (2025-06-18)](https://modelcontextprotocol.io/specification/2025-06-18/server/prompts) — HIGH confidence
- [MCP SDK issue #396: Inconsistent exception handling in call_tool vs list_resources](https://github.com/modelcontextprotocol/python-sdk/issues/396) — HIGH confidence (confirmed SDK bug, first-party issue tracker)
- [SEP-986: MCP tool naming format standardisation](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/986) — MEDIUM confidence
- [The Silent Breakage: MCP tool versioning strategy](https://minherz.medium.com/the-silent-breakage-a-versioning-strategy-for-production-ready-mcp-tools-fbb998e3f71f) — MEDIUM confidence
- [MCP tool annotations (readOnlyHint, destructiveHint)](https://blog.marcnuri.com/mcp-tool-annotations-introduction) — HIGH confidence
- [uv building and publishing packages](https://docs.astral.sh/uv/guides/package/) — HIGH confidence (official docs)
- [Dynamic versioning with uv projects](https://slhck.info/software/2025/10/01/dynamic-versioning-uv-projects.html) — MEDIUM confidence
- [MCP prompt injection (Simon Willison, 2025)](https://simonwillison.net/2025/Apr/9/mcp-prompt-injection/) — MEDIUM confidence
- [MCP client capability gap (PulseMCP)](https://www.pulsemcp.com/posts/mcp-client-capabilities-gap) — MEDIUM confidence
- [MCP 2025-11-25 specification overview](https://workos.com/blog/mcp-2025-11-25-spec-update) — MEDIUM confidence
- [MCP notifications/resources discussion](https://github.com/orgs/modelcontextprotocol/discussions/1192) — MEDIUM confidence
- Codebase inspection: `server.py`, `resource_readers.py`, `dry_run.py`, `tool_annotations.py`, `pyproject.toml`, `__init__.py`, `service_templates/` — HIGH confidence (first-party)

---

---

## Appendix: v1.1 Safety & Observability Pitfalls

> Preserved from prior milestone research. These pitfalls are addressed in v1.1 and should be verified complete before v1.2 phases begin.

**Domain:** Adding dry-run mode, drift detection, and MCP Resources to an existing Python MCP server
**Researched:** 2026-03-11

### Critical: Dry-Run Preview That Cannot Execute the Real Path

The dry-run implementation must be structured as a parameter to the existing handler (shared read/validate/plan path, gated write step), not as a separate simulation function. Separate simulation functions drift from the real path after refactors.

**Phase:** Dry-run implementation — completed in v1.1.

---

### Critical: Dry-Run Performs Real Side Effects

Dry-run must not mutate SQLite, SSH connections must not trigger host-side operations, and Proxmox API calls during dry-run should be read-only state queries only.

**Phase:** Dry-run implementation — completed in v1.1.

---

### Critical: Drift Detection That Mistakes Transient State for Drift

Point-in-time drift scans will flag rebooting VMs and restarting services. Reports must include `scan_timestamp` and a transient-state disclaimer. State drift (VM stopped) should be "suspected drift," not "confirmed drift." Config drift (CPU/memory changed) is higher confidence.

**Phase:** Drift detection implementation — completed in v1.1.

---

### Critical: MCP Resources Returning Stale Data Without Signaling It

Every resource payload must include `scanned_at`. `notifications/resources/updated` must be sent after relevant tool mutations. Do not advertise `subscribe: true` unless notifications are actually wired.

**Phase:** MCP Resources implementation — completed in v1.1.

---

### Critical: ResourceManager.proxmox_session Not Wired Into Handlers

`ProxmoxAPIClient` was creating its own `aiohttp.ClientSession` per call, bypassing the shared session in `ResourceManager`. Fix was to pass `get_resource_manager().proxmox_session` at each Proxmox handler call site.

**Phase:** Tech debt cleanup — completed in v1.1.

---

### Critical: Drift Baseline That Does Not Track Expected Changes

After every successful mutation tool call, the stored baseline must be updated to reflect the new intended state. Baselines that store only the initial state will flag every MCP-driven change as drift.

**Phase:** Drift detection implementation — completed in v1.1.

---

*v1.1 pitfalls section condensed. Full detail in git history of this file.*

---

*Pitfalls research for: v1.2 Protocol Completeness — PyPI packaging, MCP Prompts, dry-run tool split, drift MCP Resource*
*Researched: 2026-03-12*
