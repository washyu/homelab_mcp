# Phase 12: PyPI Distribution - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix the broken PyPI packaging so `uvx homelab-mcp` works correctly — entrypoint resolves without error, version is reported consistently, and service templates are bundled in the wheel. Publish the first release (1.2.0) manually to PyPI. No new server features.

</domain>

<decisions>
## Implementation Decisions

### Package name
- Rename from `homelab-mcp-server` to `homelab-mcp` in `pyproject.toml`
- `uvx homelab-mcp` is the target install command
- Both PyPI names are currently unclaimed

### Release version
- First PyPI release: `1.2.0`
- Update `pyproject.toml` version from `0.2.0` → `1.2.0`
- Version must flow from `pyproject.toml` only — no hardcoded strings anywhere

### Version unification
- Remove hardcoded `__version__ = "0.1.0"` from `__init__.py` — replace with `importlib.metadata`
- Remove hardcoded `version="0.2.0"` from `Server(...)` call in `server.py` — replace with `importlib.metadata`
- Single source of truth: `pyproject.toml`

### Default invocation behavior
- `uvx homelab-mcp` with no arguments → start in stdio mode (correct for MCP clients)
- `--help` flag → print help text (success criteria requirement)
- Same behavior as current `run_server.py` default

### Publishing workflow
- Manual: build wheel with `uv build`, publish with `uv publish`
- No GitHub Actions CI workflow for publishing (out of scope per REQUIREMENTS.md)
- PyPI Trusted Publisher (OIDC) setup is a manual one-time step for the project owner

### Claude's Discretion
- Whether `__main__.py` calls `main()` directly or re-imports from server.py
- Exact `importlib.resources` traversal pattern for YAML loading
- Whether to add a `MANIFEST.in` or rely purely on hatchling `include` config

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `run_server.py`: Existing startup logic — `main()` in `server.py` should mirror this
- `src/homelab_mcp/service_installer.py` line 18: `TEMPLATES_DIR = Path(__file__).parent / "service_templates"` — this is the line that breaks in a wheel; replace with `importlib.resources.files("homelab_mcp.service_templates")`

### Established Patterns
- `pyproject.toml` already has `[project.scripts] homelab-mcp = "homelab_mcp.server:main"` — just need to implement `main()`
- `[tool.hatch.build.targets.wheel] packages = ["src/homelab_mcp"]` — hatchling already pointed at src layout; need to add include for `*.yaml`

### Integration Points
- `Server("homelab-mcp", version="0.2.0", lifespan=app_lifespan)` in `server.py:91` — version arg needs `importlib.metadata.version("homelab-mcp")`
- `service_templates/` has 10 YAML files — all must be importable via `importlib.resources` after packaging
- `__init__.py` currently only defines `__version__` — replace with `importlib.metadata` call

</code_context>

<specifics>
## Specific Ideas

- Success test: `uvx --from ./dist/*.whl homelab-mcp --help` should print help without AttributeError or ImportError before pushing to PyPI
- `python -m homelab_mcp --help` must also work (requires `__main__.py`)
- Unzip the built wheel and confirm `service_templates/*.yaml` are present inside

</specifics>

<deferred>
## Deferred Ideas

- CI auto-publish via GitHub Actions OIDC — future milestone (v1.3+)
- Per-version release notes / changelog automation — out of scope

</deferred>

---

*Phase: 12-pypi-distribution*
*Context gathered: 2026-03-13*
