# Technology Stack

**Project:** Homelab MCP Server — v1.2 Protocol Completeness
**Researched:** 2026-03-12
**Scope:** Stack additions and changes for PyPI distribution, MCP Prompts support, and dry-run tool variants. Does not re-research the validated v1.0/v1.1 stack.

---

## Summary: What Changes for v1.2

Three features, three verdicts:

| Feature | Stack Change? | Verdict |
|---------|--------------|---------|
| MCP Prompts | No new deps | `@server.list_prompts()` and `@server.get_prompt()` exist in mcp 1.9.4 (installed) |
| Dry-run tool split | No new deps | Purely structural: new `*_preview` tool schemas + handler dispatch |
| PyPI distribution | No new deps, one structural fix | `main()` function must exist in installed package; entry point is misconfigured today |

**Net new runtime dependencies for v1.2: zero.**

---

## Recommended Stack

### Core Framework — No Changes

| Technology | Version Pinned | Purpose | Why |
|------------|---------------|---------|-----|
| Python | 3.12+ | Runtime | Established, not changing |
| uv | latest | Package manager, build runner, publisher | Established; `uv build` + `uv publish` handles PyPI distribution |
| mcp[cli] | >=1.9.1 (1.9.4 installed) | MCP SDK, lowlevel.Server | Already supports Prompts — no upgrade needed |
| hatchling | via build-system | Build backend | Keep — handles src/ layout correctly; uv_build migration adds risk for zero benefit |

### Supporting Libraries — No Changes

All of asyncssh, aiohttp, starlette, uvicorn, SQLite, rich, websockets, pydantic (transitive) remain exactly as in v1.1.

---

## Feature 1: MCP Prompts

**Confidence: HIGH** — verified by direct inspection of installed mcp 1.9.4 SDK source.

### No New Dependencies

`lowlevel.Server` in mcp 1.9.4 already provides two decorator methods for Prompts:

```python
# Signatures from .venv/lib/python3.12/site-packages/mcp/server/lowlevel/server.py
@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    ...

@server.get_prompt()
async def handle_get_prompt(
    name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    ...
```

Capability advertisement is automatic: `get_capabilities()` checks whether `types.ListPromptsRequest` is registered in `request_handlers` and sets `prompts=PromptsCapability(listChanged=...)`. No manual capability wiring needed — same behaviour as tools and resources.

### Types Available in mcp.types (1.9.4)

All types needed are already present with no imports from new packages:

| Type | Purpose |
|------|---------|
| `types.Prompt` | Prompt descriptor — name, description, arguments |
| `types.PromptArgument` | Argument definition — name, description, required |
| `types.GetPromptResult` | Response from get_prompt — description, messages |
| `types.PromptMessage` | Single message — role, content |
| `types.ListPromptsResult` | Wrapper; SDK constructs internally, not needed in handler return |
| `types.PromptsCapability` | Capability flag; SDK constructs via get_capabilities() |
| `types.PromptListChangedNotification` | Push notification for prompt list changes (static prompts: not needed) |

### Implementation Pattern

Mirrors the existing `@server.list_resources()` / `@server.read_resource()` pattern in `server.py`. The natural home for v1.2 is:

1. `@server.list_prompts()` handler in `server.py` — returns static `list[types.Prompt]`
2. `@server.get_prompt()` handler in `server.py` — dispatches on `name`, returns `types.GetPromptResult`
3. New module `src/homelab_mcp/prompt_handlers.py` — homelab workflow template logic (mirrors `resource_readers.py`)

For v1.2 static prompt templates, `NotificationOptions(prompts_changed=False)` is correct. Set `prompts_changed=True` only if prompts will change at runtime — not required here.

### What NOT to Add for Prompts

| Avoid | Why |
|-------|-----|
| Jinja2 / string.Template | Prompt templates are Python dicts with f-strings; a template engine adds unnecessary dependency |
| FastMCP | Contradicts the established lowlevel.Server decision; FastMCP abstracts away protocol control the project needs |
| Separate prompts microservice | All prompts are homelab-domain-specific; same process is correct |

---

## Feature 2: Dry-Run Tool Split

**Confidence: HIGH** — structural decision, no library research needed.

### No New Dependencies

The v1.2 change splits the 6 destructive tools that currently accept `dry_run: bool` into:
- `tool_name` — mutates, `destructiveHint: true`, no dry_run parameter
- `tool_name_preview` — never mutates, `readOnlyHint: true`, no dry_run parameter (inherently preview)

This is schema changes in `tool_schemas.py` / `tool_annotations.py` and handler dispatch in `tool_handlers.py`. No new libraries.

The `_preview` variants must:
- Mirror the same input schema minus any `dry_run` parameter
- Always call the existing dry-run code path internally (the `dry_run.py` module from v1.1)
- Carry `readOnlyHint: true` in `get_tool_annotations()`

The existing `dry_run.py` module from v1.1 remains unchanged. The split is a calling convention change, not a logic change.

---

## Feature 3: PyPI Distribution

**Confidence: HIGH** on gap identification (direct source inspection); **MEDIUM** on publish workflow details (official docs via WebSearch).

### What Already Works

The `pyproject.toml` has the correct build infrastructure:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/homelab_mcp"]

[project.scripts]
homelab-mcp = "homelab_mcp.server:main"
```

`uv build` produces wheel + sdist. `uv publish` publishes to PyPI. `uvx homelab-mcp` resolves `[project.scripts]` entry points automatically — no additional tooling needed.

### Critical Gap: Missing `main()` Function

The entry point `homelab_mcp.server:main` is declared but **`main()` does not exist in `server.py`**. The actual entrypoint logic lives in `run_server.py`, which also imports from `src.homelab_mcp.server` — a path that only resolves from the project root, not from an installed package.

This means `uvx homelab-mcp` would fail with `AttributeError` today.

**Fix required:**

1. Create `src/homelab_mcp/__main__.py` containing `main()` — replicates `parse_args()` + `asyncio.run(run_stdio() | run_http())` from `run_server.py`, importing from `homelab_mcp.server` (not `src.homelab_mcp.server`)
2. Update `pyproject.toml` entry point to `homelab_mcp.__main__:main`
3. Keep `run_server.py` at project root for the current `uv run python run_server.py` development workflow (fix its import to `homelab_mcp.server` too, or retire it in favour of `python -m homelab_mcp`)

The `__main__.py` approach also enables `python -m homelab_mcp` as a supported invocation.

### pyproject.toml Changes Required

```toml
# Change [project.scripts]:
[project.scripts]
homelab-mcp = "homelab_mcp.__main__:main"

# No new [project.dependencies] entries needed.
# No new [dependency-groups] dev entries needed.
```

### Build and Publish Commands

```bash
# Build wheel + sdist
uv build

# Publish to PyPI (preferred: Trusted Publisher — no token needed)
# Configure at pypi.org/manage/project/homelab-mcp-server/settings/publishing/
uv publish

# Or with token
UV_PUBLISH_TOKEN=pypi-... uv publish
```

### GitHub Actions Publish Job

Add to `.github/workflows/main.yml`, triggered on version tags:

```yaml
publish:
  needs: [test]
  if: startsWith(github.ref, 'refs/tags/v')
  runs-on: ubuntu-latest
  environment: pypi
  permissions:
    id-token: write
  steps:
    - uses: actions/checkout@v4
    - uses: astral-sh/setup-uv@v5
    - run: uv build
    - run: uv publish
```

PyPI Trusted Publishers with OIDC (`id-token: write`) is preferred — avoids long-lived API token secrets in GitHub. Configure once at pypi.org before first publish.

### Build Backend: Keep Hatchling

Do not migrate to `uv_build` in v1.2. Hatchling handles the `src/` layout with `[tool.hatch.build.targets.wheel]` correctly. The `uv_build` backend became stable only mid-2025, and migration from hatchling adds risk for zero functional benefit in this milestone.

### Package Name Verification

The current `[project.name]` is `homelab-mcp-server`. The `[project.scripts]` key `homelab-mcp` is the installed command name. These are independent. Verify `homelab-mcp-server` is available on PyPI before publishing — `pip index versions homelab-mcp-server` (no conflicting package was found in search results, but a direct check is required before the publish step).

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Build backend | hatchling (keep) | uv_build | Stable mid-2025; migration risk with no functional benefit for v1.2 |
| PyPI publish auth | Trusted Publisher (OIDC) | UV_PUBLISH_TOKEN secret | Token-based requires secret rotation; OIDC is keyless and auto-expiring |
| Prompts wiring | Add to server.py (mirrors resources) | New dedicated prompts module | server.py is the registration point; template logic goes in prompt_handlers.py |
| Prompts templating | Python dicts + f-strings | Jinja2 | No new dependency warranted for a handful of static workflow templates |
| Dry-run split | `*_preview` tool variants | Keep `dry_run: bool` parameter | A parameter-based approach cannot carry `readOnlyHint: true` correctly |
| Entrypoint | `__main__.py:main` | Inline `main()` in server.py | `__main__.py` enables `python -m homelab_mcp`; keeps server.py focused on MCP protocol |

---

## Installation

No new packages to install for v1.2. The only changes are:

```bash
# No uv add commands needed

# After adding __main__.py and fixing entry point, verify locally:
uv run homelab-mcp --help

# Build for PyPI
uv build

# Publish (first time: configure Trusted Publisher at pypi.org)
uv publish
```

---

## Sources

- mcp 1.9.4 SDK — direct inspection of installed sources (HIGH confidence):
  - `.venv/lib/python3.12/site-packages/mcp/server/lowlevel/server.py` — `list_prompts()`, `get_prompt()` decorators and capability auto-detection
  - `.venv/lib/python3.12/site-packages/mcp/types.py` — `Prompt`, `PromptArgument`, `GetPromptResult`, `PromptMessage`, `PromptListChangedNotification`
- `pyproject.toml` and `run_server.py` — direct inspection revealing the missing `main()` gap (HIGH confidence)
- [uv Building and publishing a package](https://docs.astral.sh/uv/guides/package/) — MEDIUM confidence (official docs, WebSearch-found)
- [uv Build backend](https://docs.astral.sh/uv/concepts/build-backend/) — MEDIUM confidence (official docs, WebSearch-found)
- [PyPI Trusted Publishers](https://docs.pypi.org/trusted-publishers/) — MEDIUM confidence (official docs, WebSearch-found)
- [Python Build Backends in 2025: uv_build vs Hatchling](https://medium.com/@dynamicy/python-build-backends-in-2025-what-to-use-and-why-uv-build-vs-hatchling-vs-poetry-core-94dd6b92248f) — LOW confidence (Medium article; corroborates stable date for uv_build)

---

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| MCP Prompts — SDK support | HIGH | Direct inspection of installed mcp 1.9.4 source; decorators and types verified present |
| MCP Prompts — implementation pattern | HIGH | Mirrors existing resources pattern in codebase |
| Dry-run split — no new deps | HIGH | Structural decision; verified against existing dry_run.py module |
| PyPI — missing main() gap | HIGH | Direct source inspection of server.py (no main) and run_server.py (src-prefixed imports) |
| PyPI — build/publish workflow | MEDIUM | Official uv docs found via WebSearch; not directly fetched |
| PyPI — Trusted Publisher setup | MEDIUM | Official PyPI docs found via WebSearch; process well-documented |

---

*Stack research for: Homelab MCP Server v1.2 Protocol Completeness*
*Researched: 2026-03-12*
