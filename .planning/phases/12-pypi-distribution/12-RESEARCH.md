# Phase 12: PyPI Distribution - Research

**Researched:** 2026-03-13
**Domain:** Python packaging, PyPI distribution, `importlib.metadata`, `importlib.resources`, hatchling wheel configuration
**Confidence:** HIGH

## Summary

Phase 12 is a pure packaging fix. The MCP server code is working correctly in dev; the task is to make the installed wheel reproduce that behavior for end users running `uvx homelab-mcp`. There are four distinct sub-problems: (1) rename the PyPI package from `homelab-mcp-server` to `homelab-mcp` so `uvx homelab-mcp` resolves correctly, (2) create a `main()` entry point in `server.py` and a `__main__.py` so both `uvx homelab-mcp` and `python -m homelab_mcp` work, (3) replace four hardcoded version strings across `__init__.py`, `server.py`, `http_app.py`, and `http_transport.py` with `importlib.metadata.version("homelab-mcp")`, and (4) ensure `service_templates/*.yaml` files are bundled in the wheel and loaded via `importlib.resources.files()` instead of `Path(__file__).parent`.

The critical packaging insight is that hatchling's behavior for non-Python files inside the package directory is inconsistent unless explicitly configured — the safest approach is to add an `include` pattern in `[tool.hatch.build.targets.wheel]`. The `service_templates/` subdirectory does NOT need an `__init__.py` to be traversable via `importlib.resources.files()` — data subdirectories work without it.

**Primary recommendation:** Make all four changes in a single "packaging fix" wave: rename, add entry point, unify versions, fix resource loading, verify with `uvx --from dist/*.whl homelab-mcp --help`, then publish.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Rename from `homelab-mcp-server` to `homelab-mcp` in `pyproject.toml`
- `uvx homelab-mcp` is the target install command
- First PyPI release: `1.2.0`
- Update `pyproject.toml` version from `0.2.0` → `1.2.0`
- Version must flow from `pyproject.toml` only — no hardcoded strings anywhere
- Remove hardcoded `__version__ = "0.1.0"` from `__init__.py` — replace with `importlib.metadata`
- Remove hardcoded `version="0.2.0"` from `Server(...)` call in `server.py` — replace with `importlib.metadata`
- `uvx homelab-mcp` with no arguments → start in stdio mode (correct for MCP clients)
- `--help` flag → print help text (success criteria requirement)
- Same behavior as current `run_server.py` default
- Manual: build wheel with `uv build`, publish with `uv publish`
- No GitHub Actions CI workflow for publishing (out of scope per REQUIREMENTS.md)
- PyPI Trusted Publisher (OIDC) setup is a manual one-time step for the project owner

### Claude's Discretion
- Whether `__main__.py` calls `main()` directly or re-imports from server.py
- Exact `importlib.resources` traversal pattern for YAML loading
- Whether to add a `MANIFEST.in` or rely purely on hatchling `include` config

### Deferred Ideas (OUT OF SCOPE)
- CI auto-publish via GitHub Actions OIDC — future milestone (v1.3+)
- Per-version release notes / changelog automation — out of scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PKG-01 | User can install with `uvx homelab-mcp` and run without cloning the repo | Entry point wiring: pyproject.toml `[project.scripts]` already has the mapping; `main()` in server.py must be implemented; rename to `homelab-mcp` makes `uvx` resolve correctly |
| PKG-02 | Version reported consistently — `pyproject.toml`, `__init__.py`, and server version string agree via `importlib.metadata` | Four hardcoded version strings found: `__init__.py`, `server.py:91`, `http_app.py:131`, `http_transport.py:394` — all replaced with `importlib.metadata.version("homelab-mcp")` |
| PKG-03 | `service_templates/*.yaml` files included in wheel and loaded via `importlib.resources` (not `__file__`-relative paths) | `TEMPLATES_DIR` in `service_installer.py` must switch to `importlib.resources.files("homelab_mcp").joinpath("service_templates")`; pyproject.toml wheel include config needed for YAML files |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `importlib.metadata` | stdlib (Python 3.12) | Read package version from installed dist-info | PEP 517/518 compliant; no external dep; works in editable installs when `uv sync` has run |
| `importlib.resources` | stdlib (Python 3.12) | Access data files bundled in wheels | Works in zip archives (wheels) and on filesystem; `files()` API is the current standard since 3.9 |
| hatchling | already in build-system | Build backend for wheel/sdist | Already configured; `packages = ["src/homelab_mcp"]` is the existing pattern |
| uv build | astral uv | Build wheel and sdist | Wraps hatchling; `uv build` produces `dist/*.whl` and `dist/*.tar.gz` |
| uv publish | astral uv | Upload to PyPI | `uv publish --token $PYPI_TOKEN` or `UV_PUBLISH_TOKEN` env var |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| argparse | stdlib | CLI argument parsing | Already used in `run_server.py`; reuse exact pattern for `main()` in `server.py` |
| anyio | transitive dep via mcp | Async runtime for stdio transport | Already in use via `run_server.py` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `importlib.metadata` | `pkg_resources.get_distribution` | `pkg_resources` is deprecated; `importlib.metadata` is the stdlib replacement |
| `importlib.resources.files()` | `Path(__file__).parent` | `Path(__file__)` breaks in zip-imported packages; `files()` works everywhere |
| hatchling `include` | `MANIFEST.in` | `MANIFEST.in` is setuptools-era; hatchling uses `include` in `pyproject.toml` |

**Installation:** No new runtime packages needed. This phase only modifies packaging config and replaces stdlib calls.

---

## Architecture Patterns

### Recommended Project Structure (no changes to layout)
```
src/homelab_mcp/
├── __init__.py           # Replace __version__ with importlib.metadata
├── __main__.py           # NEW: enables `python -m homelab_mcp`
├── server.py             # Add main(), replace hardcoded version
├── http_app.py           # Replace hardcoded version "0.2.0"
├── http_transport.py     # Replace hardcoded version "0.2.0"
├── service_installer.py  # Replace TEMPLATES_DIR with importlib.resources
└── service_templates/    # 10 YAML files — no __init__.py needed
    ├── *.yaml
    ...
```

### Pattern 1: Single-source version via importlib.metadata

**What:** `importlib.metadata.version()` reads from the installed `dist-info` directory, which is populated from `pyproject.toml`'s `version` field at install time.

**When to use:** In every file that currently has a hardcoded version string.

**Critical detail about package name:** After the rename, the argument MUST match the new `pyproject.toml` `name` field exactly: `"homelab-mcp"`. Python normalizes hyphens and underscores, so `"homelab_mcp"` also works, but using the canonical hyphenated form is clearer.

**Editable install behavior:** In editable installs (`uv sync`), `importlib.metadata.version("homelab-mcp")` works correctly after the package is renamed because `uv sync` regenerates the dist-info directory. Verified on this project with the current name `homelab-mcp-server` returning `"0.2.0"` correctly.

```python
# Source: https://docs.python.org/3.12/library/importlib.metadata.html
from importlib.metadata import version, PackageNotFoundError

try:
    __version__: str = version("homelab-mcp")
except PackageNotFoundError:
    __version__ = "unknown"  # fallback for running from source without install
```

**For `server.py` Server() instantiation:**
```python
# Source: https://docs.python.org/3.12/library/importlib.metadata.html
from importlib.metadata import version, PackageNotFoundError

def _get_version() -> str:
    try:
        return version("homelab-mcp")
    except PackageNotFoundError:
        return "unknown"

server = Server("homelab-mcp", version=_get_version(), lifespan=app_lifespan)
```

### Pattern 2: importlib.resources for data files in subdirectories

**What:** `importlib.resources.files()` returns a `Traversable` that works whether the package is installed as a wheel, editable install, or zip archive. `__init__.py` is NOT required in the data subdirectory — data directories are traversable without being Python packages.

**When to use:** Any code currently using `Path(__file__).parent / "service_templates"`.

```python
# Source: https://docs.python.org/3.12/library/importlib.resources.html
from importlib.resources import files

# Get the service_templates directory as a Traversable
templates_dir = files("homelab_mcp").joinpath("service_templates")

# Iterate YAML files (replaces TEMPLATES_DIR.glob("*.yaml"))
for item in templates_dir.iterdir():
    if item.is_file() and item.name.endswith(".yaml"):
        content = item.read_text(encoding="utf-8")
        service_data = yaml.safe_load(content)
        service_name = item.name.removesuffix(".yaml")
        templates[service_name] = service_data
```

**Note on `mkdir(exist_ok=True)`:** Line 99 of `service_installer.py` calls `TEMPLATES_DIR.mkdir(exist_ok=True)`. This must be removed — the Traversable returned by `importlib.resources.files()` is read-only and cannot be created via `mkdir`. The templates are bundled in the package; creating the directory is unnecessary in a wheel context.

### Pattern 3: main() entry point in server.py

**What:** `pyproject.toml` already declares `homelab-mcp = "homelab_mcp.server:main"`. The `main()` function just needs to be implemented in `server.py` by extracting the argument-parsing and dispatch logic currently in `run_server.py`.

**When to use:** Called by the console script shim created by pip/uv during installation, and by `__main__.py`.

```python
# Pattern from run_server.py — extract into server.py:main()
import argparse
import asyncio
import sys

def main() -> None:
    """Console script entry point for `uvx homelab-mcp` and `python -m homelab_mcp`."""
    parser = argparse.ArgumentParser(
        description="Homelab MCP Server - AI-powered homelab infrastructure management",
    )
    parser.add_argument("--http", action="store_true", ...)
    parser.add_argument("--host", ...)
    parser.add_argument("--port", ...)
    # ... (mirror run_server.py parse_args exactly)
    args = parser.parse_args()

    if args.http:
        asyncio.run(run_http(...))
    else:
        asyncio.run(run_stdio())
```

**Note:** `run_server.py` imports from `src.homelab_mcp.server` (with `src.` prefix). The new `main()` function inside the package uses relative/absolute imports without the `src.` prefix — this is the key difference. `run_server.py` can remain as a development convenience script for the project root.

### Pattern 4: __main__.py for python -m homelab_mcp

**What:** A minimal `__main__.py` that delegates to `main()`. This enables `python -m homelab_mcp --help`.

```python
# src/homelab_mcp/__main__.py
from homelab_mcp.server import main

if __name__ == "__main__":
    main()
```

### Pattern 5: Hatchling wheel include for YAML files

**What:** Explicitly include `*.yaml` files inside the package directory in the wheel. Hatchling's default behavior for non-Python files is inconsistent — explicitly specifying is safer and the documented recommendation.

```toml
# In pyproject.toml
[tool.hatch.build.targets.wheel]
packages = ["src/homelab_mcp"]
include = [
    "src/homelab_mcp/**/*.yaml",
]
```

**Verification:** After `uv build`, run:
```bash
python -c "import zipfile; zf = zipfile.ZipFile('dist/homelab_mcp-1.2.0-py3-none-any.whl'); print([f for f in zf.namelist() if '.yaml' in f])"
```
This must show 10 YAML files under `homelab_mcp/service_templates/`.

### Anti-Patterns to Avoid

- **`Path(__file__).parent / "service_templates"`:** Breaks when the package is installed from a wheel because `__file__` may not exist or point to a path without the data files. Always use `importlib.resources.files()`.
- **`TEMPLATES_DIR.mkdir(exist_ok=True)`:** Data directories bundled in wheels cannot be created at runtime. Remove this call entirely.
- **`from src.homelab_mcp.server import server`:** This is a dev-only import that works only when running from the project root with `src/` on the path. The packaged `main()` and `__main__.py` must use `from homelab_mcp.server import server` (no `src.` prefix).
- **Hardcoding the new version in `importlib.metadata.version()` fallback:** The fallback should return a neutral string like `"unknown"`, not a hardcoded version — the whole point is a single source of truth.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Reading package version | Custom version file parsing | `importlib.metadata.version()` | Reads from installed dist-info; zero additional files |
| Bundling data files | Custom file copy script | hatchling `include` in pyproject.toml | Build backend handles it; works for wheels, sdists, editable installs |
| Accessing bundled data at runtime | `Path(__file__)` hacks | `importlib.resources.files()` | Works in zip archives; guaranteed by Python stdlib |
| Console script wiring | Custom sys.path manipulation | `[project.scripts]` in pyproject.toml | pip/uv generate the shim automatically |

**Key insight:** All four problems in this phase have stdlib or build-tool solutions. No third-party packages or custom scripts needed.

---

## Common Pitfalls

### Pitfall 1: importlib.metadata.version() uses the PyPI package name, not the import name
**What goes wrong:** After renaming `pyproject.toml` to `homelab-mcp`, calling `version("homelab_mcp")` (with underscore) may work due to normalization, but `version("homelab-mcp-server")` (old name) will raise `PackageNotFoundError` in the installed wheel.
**Why it happens:** The metadata lookup uses the dist-info directory name, which is derived from `pyproject.toml`'s `name` field. After rename + rebuild, only `"homelab-mcp"` resolves.
**How to avoid:** Update all four callsites to `version("homelab-mcp")` simultaneously with the `pyproject.toml` rename.
**Warning signs:** `PackageNotFoundError: homelab-mcp-server` after building and testing the wheel.

### Pitfall 2: TEMPLATES_DIR.mkdir() call fails in wheel context
**What goes wrong:** `service_installer.py` line 99 calls `TEMPLATES_DIR.mkdir(exist_ok=True)`. If `TEMPLATES_DIR` is switched to an `importlib.resources` Traversable, calling `.mkdir()` on it raises `AttributeError` because Traversable doesn't support filesystem write operations.
**Why it happens:** The original code defensively created the directory for development use. In a wheel, the templates directory is read-only.
**How to avoid:** Delete line 99. The templates directory is guaranteed to exist because it's bundled in the wheel.
**Warning signs:** `AttributeError: 'MultiplexedPath' object has no attribute 'mkdir'` (or similar Traversable type).

### Pitfall 3: run_server.py uses src.-prefixed imports that break in a wheel
**What goes wrong:** `run_server.py` imports `from src.homelab_mcp.server import server`. If `main()` in `server.py` copies this pattern, the installed console script will fail with `ModuleNotFoundError: No module named 'src'`.
**Why it happens:** `run_server.py` lives at the repo root and relies on Python's implicit namespace — `src/` is on `sys.path` in development. In an installed wheel, there is no `src/` — the package is just `homelab_mcp`.
**How to avoid:** `main()` and `__main__.py` inside the package must use `from homelab_mcp.server import server` or relative imports.
**Warning signs:** `ModuleNotFoundError: No module named 'src'` when running `uvx --from dist/*.whl homelab-mcp`.

### Pitfall 4: YAML files not present in the wheel
**What goes wrong:** `uv build` produces a wheel, but unzipping it reveals no `service_templates/` directory. `ServiceInstaller` initializes with zero templates.
**Why it happens:** Hatchling's default inclusion rules for non-Python files within a `packages`-configured wheel are inconsistent based on project name normalization. Without explicit `include`, YAML files may be silently excluded.
**How to avoid:** Add `include = ["src/homelab_mcp/**/*.yaml"]` under `[tool.hatch.build.targets.wheel]`. Verify with `zipfile` inspection after every `uv build`.
**Warning signs:** `ServiceInstaller.templates` is empty dict after running `uvx homelab-mcp`.

### Pitfall 5: uv build includes tool.uv.sources, breaking the wheel for end users
**What goes wrong:** If `tool.uv.sources` has local path overrides, `uv build` may produce a wheel that works locally but fails on PyPI.
**Why it happens:** uv can include source overrides in builds.
**How to avoid:** Run `uv build --no-sources` before publishing. This is the documented pre-publish step.
**Warning signs:** Wheel installs correctly locally but `uvx homelab-mcp` fails for users installing from PyPI.

### Pitfall 6: Version mismatch between pyproject.toml and dist-info after editable reinstall
**What goes wrong:** `importlib.metadata.version("homelab-mcp")` returns the old version or raises `PackageNotFoundError` because `uv sync` wasn't re-run after renaming.
**Why it happens:** `uv sync` must be re-run after any `pyproject.toml` name or version change to regenerate dist-info.
**How to avoid:** Run `uv sync` immediately after editing `pyproject.toml`. Include in the task checklist.
**Warning signs:** `PackageNotFoundError` in tests after rename.

---

## Code Examples

Verified patterns from official sources:

### Version unification (__init__.py)
```python
# Source: https://docs.python.org/3.12/library/importlib.metadata.html
from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version("homelab-mcp")
except PackageNotFoundError:
    __version__ = "unknown"
```

### importlib.resources YAML directory traversal (service_installer.py)
```python
# Source: https://docs.python.org/3.12/library/importlib.resources.html
from importlib.resources import files

def _load_service_templates(self) -> dict[str, dict[str, Any]]:
    """Load all service templates from the bundled templates directory."""
    templates: dict[str, dict[str, Any]] = {}
    templates_dir = files("homelab_mcp").joinpath("service_templates")
    for item in templates_dir.iterdir():
        if item.is_file() and item.name.endswith(".yaml"):
            try:
                service_data = yaml.safe_load(item.read_text(encoding="utf-8"))
                service_name = item.name.removesuffix(".yaml")
                templates[service_name] = service_data
            except Exception as e:
                print(f"Warning: Failed to load template {item.name}: {e}")
    return templates
```

### hatchling include config (pyproject.toml)
```toml
# Source: https://hatch.pypa.io/latest/config/build/
[tool.hatch.build.targets.wheel]
packages = ["src/homelab_mcp"]
include = [
    "src/homelab_mcp/**/*.yaml",
]
```

### Wheel content verification
```bash
# Source: verified with Python stdlib zipfile module
python -c "
import zipfile
whl = next(__import__('pathlib').Path('dist').glob('*.whl'))
with zipfile.ZipFile(whl) as zf:
    yaml_files = [f for f in zf.namelist() if f.endswith('.yaml')]
    print(f'{len(yaml_files)} YAML files in wheel:')
    for f in sorted(yaml_files):
        print(f'  {f}')
"
```

### Local wheel smoke test (pre-publish verification)
```bash
# Source: https://docs.astral.sh/uv/guides/package/
uvx --from ./dist/homelab_mcp-1.2.0-py3-none-any.whl homelab-mcp --help
```

### Publishing to PyPI
```bash
# Source: https://docs.astral.sh/uv/guides/package/
uv build --no-sources
uv publish --token $PYPI_TOKEN
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Path(__file__).parent / "data"` | `importlib.resources.files(pkg).joinpath("data")` | Python 3.9 (PEP 451) | Works in zip/wheel, not just filesystem |
| `pkg_resources.get_distribution().version` | `importlib.metadata.version(name)` | Python 3.8 (PEP 566) | No setuptools dependency required |
| `setup.py` + `MANIFEST.in` for data files | `pyproject.toml` `[tool.hatch.build.targets.wheel] include` | PEP 517/518 era | Single config file, no separate MANIFEST.in |
| `setup.cfg` `package_data` | hatchling `include` glob patterns | Hatch 1.x | Consistent with modern build backends |

**Deprecated/outdated:**
- `pkg_resources`: Deprecated; `importlib.metadata` is the stdlib replacement
- `importlib.resources.read_text(package, resource)`: Deprecated since 3.11; use `files().joinpath().read_text()` instead
- `importlib.resources.contents()`: Deprecated since 3.11; use `files().iterdir()` instead

---

## Open Questions

1. **Whether `service_templates/` needs an `__init__.py` for importlib.resources traversal**
   - What we know: Official docs say data subdirectories do not need `__init__.py` for `files().joinpath()` traversal. The `importlib_resources` backport documentation explicitly confirms this.
   - What's unclear: Edge cases with certain zip-import implementations that may still require it.
   - Recommendation: Do NOT add `__init__.py` to `service_templates/` — it would make Python treat it as a sub-package, which is semantically wrong for a data directory. The wheel include config ensures the files are present.

2. **Whether `run_server.py` at the repo root should be updated or left as-is**
   - What we know: `run_server.py` uses `from src.homelab_mcp.server import server` which is dev-only import syntax. It is not included in the wheel.
   - What's unclear: Whether anyone relies on `run_server.py` for local development after this phase.
   - Recommendation: Leave `run_server.py` unchanged as a dev convenience tool. It is not part of the wheel and does not affect PKG-01/02/03.

3. **How to handle `importlib.metadata.version()` in tests that run without installing the package**
   - What we know: Tests run via `uv run pytest` in an editable install where `homelab_mcp_server-0.2.0.dist-info` exists. After rename, `uv sync` must be re-run to generate `homelab_mcp-1.2.0.dist-info`.
   - What's unclear: Whether the test for PKG-02 should mock `version()` or exercise it against the real installed package.
   - Recommendation: Test the installed package path with `importlib.metadata.version("homelab-mcp")` directly in a unit test that asserts the version matches `pyproject.toml`. No mocking needed — editable install provides the dist-info.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x with pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_packaging.py -x -v` |
| Full suite command | `uv run pytest tests/ -m "not integration" -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PKG-01 | `main()` callable without error; argparse produces help text | unit | `uv run pytest tests/test_packaging.py::test_main_help -x` | Wave 0 |
| PKG-01 | `__main__.py` delegates to `main()` correctly | unit | `uv run pytest tests/test_packaging.py::test_main_module_entry -x` | Wave 0 |
| PKG-02 | `importlib.metadata.version("homelab-mcp")` returns value matching pyproject.toml | unit | `uv run pytest tests/test_packaging.py::test_version_unified -x` | Wave 0 |
| PKG-02 | `server.py` server instance uses dynamic version (not hardcoded) | unit | `uv run pytest tests/test_packaging.py::test_server_version_dynamic -x` | Wave 0 |
| PKG-03 | `ServiceInstaller()` loads all 10 templates from importlib.resources | unit | `uv run pytest tests/test_service_installer.py -x -k "templates"` | Partial (needs update) |
| PKG-03 | Wheel zip contains `homelab_mcp/service_templates/*.yaml` | manual | `python -c "import zipfile; ..."` (see Code Examples) | manual |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_packaging.py -x`
- **Per wave merge:** `uv run pytest tests/ -m "not integration" -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_packaging.py` — new file covering PKG-01 (`test_main_help`, `test_main_module_entry`) and PKG-02 (`test_version_unified`, `test_server_version_dynamic`)
- [ ] `tests/test_service_installer.py` — update existing `patch("src.homelab_mcp.service_installer.TEMPLATES_DIR", ...)` to work with the importlib.resources-based approach (the module-level `TEMPLATES_DIR` constant will be removed, so the patch target changes)

---

## Sources

### Primary (HIGH confidence)
- Python 3.12 docs — importlib.metadata.version: https://docs.python.org/3.12/library/importlib.metadata.html
- Python 3.12 docs — importlib.resources.files: https://docs.python.org/3.12/library/importlib.resources.html
- Hatch build configuration docs: https://hatch.pypa.io/latest/config/build/
- uv packaging guide: https://docs.astral.sh/uv/guides/package/

### Secondary (MEDIUM confidence)
- importlib_resources usage guide (confirms no `__init__.py` needed for data subdirs): https://importlib-resources.readthedocs.io/en/latest/using.html
- hatch discussions/427 (data files within package dir approach): https://github.com/pypa/hatch/discussions/427
- hatch discussions/814 (default file inclusion rules — inconsistent, explicit better): https://github.com/pypa/hatch/discussions/814

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — All stdlib and uv; verified against official docs
- Architecture: HIGH — Entry point wiring, `importlib.metadata`, `importlib.resources` patterns all verified against Python 3.12 docs; hatchling config verified against hatch.pypa.io
- Pitfalls: HIGH — Most pitfalls derived from direct code inspection of the existing codebase (found 4 hardcoded version sites, `TEMPLATES_DIR.mkdir()` issue, `src.` import prefix issue)

**Research date:** 2026-03-13
**Valid until:** 2026-09-13 (stable stdlib APIs; hatchling config pattern stable)
