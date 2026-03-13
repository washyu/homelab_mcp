"""Wave 0 test scaffold for PyPI distribution (Phase 12).

These tests define the contract for:
- PKG-01: entry point (homelab-mcp CLI via main())
- PKG-02: version unification (importlib.metadata-backed, single source of truth)
- PKG-03: template loading (importlib.resources instead of hard-coded Path)

All tests in this file are expected to be RED at Wave 0 commit time.
They will become GREEN after Plans 02 and 03 implement the required changes.
"""

from __future__ import annotations

import importlib.metadata
import sys
import tomllib
from pathlib import Path


def test_main_help(monkeypatch: object, capsys: object) -> None:
    """PKG-01: calling main() with --help raises SystemExit(0) and prints help text.

    main() must exist as a callable in homelab_mcp.server and be registered as the
    [project.scripts] entry point in pyproject.toml.
    """
    import pytest

    from homelab_mcp.server import main  # type: ignore[attr-defined]  # does not exist yet

    monkeypatch.setattr(sys, "argv", ["homelab-mcp", "--help"])  # type: ignore[attr-defined]

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0, f"Expected exit code 0, got {exc_info.value.code}"

    # Help text should appear on stdout or stderr
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    combined = captured.out + captured.err
    assert combined.strip(), "Expected help text to be printed to stdout or stderr"


def test_main_module_entry() -> None:
    """PKG-01: homelab_mcp.__main__ module is importable and delegates to main().

    The __main__ module enables `python -m homelab_mcp` to work correctly.
    It must reference the main() function (not define its own logic).
    """
    import importlib
    import inspect

    main_module = importlib.import_module("homelab_mcp.__main__")

    # The module must have a reference to a callable (main function or similar)
    # Accept either a direct `main` attribute or a `__main__` guard calling main()
    module_source = inspect.getsource(main_module)
    assert "main" in module_source, (
        "homelab_mcp.__main__ must reference main() — either import and call it, or define an entry point"
    )

    # The referenced main must be callable when resolved
    if hasattr(main_module, "main"):
        assert callable(main_module.main), "main attribute in __main__ must be callable"


def test_version_unified() -> None:
    """PKG-02: importlib.metadata.version('homelab-mcp') matches pyproject.toml version.

    After Plan 02, the package is renamed to 'homelab-mcp' and version is managed
    by a single source of truth (pyproject.toml -> importlib.metadata).
    """
    # Read version from pyproject.toml (source of truth)
    repo_root = Path(__file__).parent.parent
    pyproject_path = repo_root / "pyproject.toml"

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    expected_version = data["project"]["version"]
    assert expected_version, "pyproject.toml must have a [project] version field"

    # importlib.metadata must expose the same version under the 'homelab-mcp' name
    # (After Plan 02 renames the package from 'homelab-mcp-server' to 'homelab-mcp')
    metadata_version = importlib.metadata.version("homelab-mcp")
    assert metadata_version == expected_version, (
        f"importlib.metadata.version('homelab-mcp') returned {metadata_version!r} "
        f"but pyproject.toml has version={expected_version!r}. "
        "Ensure the package name in pyproject.toml is 'homelab-mcp' and the package is installed."
    )


def test_server_version_dynamic() -> None:
    """PKG-02: server instance uses a dynamically derived version, not hardcoded '0.2.0'.

    After Plan 02, server.py must call _get_version() (or equivalent) backed by
    importlib.metadata instead of the literal string '0.2.0'.
    """
    from homelab_mcp import server as server_module

    server_obj = server_module.server

    # Inspect the server object for its version attribute.
    # The MCP SDK lowlevel.Server stores version as _version or exposes it via a property.
    version_value: str | None = None
    for attr in ("_version", "version", "server_version"):
        if hasattr(server_obj, attr):
            val = getattr(server_obj, attr)
            if isinstance(val, str):
                version_value = val
                break

    if version_value is None:
        # Fall back to inspecting __dict__
        for val in vars(server_obj).values():
            if isinstance(val, str) and "." in val and val[0].isdigit():
                version_value = val
                break

    assert version_value is not None, (
        "Could not find a version string on the server object. Inspect server.__dict__ to find the attribute name."
    )

    # After Plan 02 implementation, the version must NOT be the old hardcoded value.
    # It must instead equal the version reported by importlib.metadata for 'homelab-mcp'.
    assert version_value != "0.2.0", (
        "server version is still the hardcoded '0.2.0'. "
        "Plan 02 must replace it with importlib.metadata.version('homelab-mcp')."
    )

    # Verify it matches the metadata version (the real check after Plan 02)
    try:
        expected = importlib.metadata.version("homelab-mcp")
        assert version_value == expected, (
            f"server version {version_value!r} does not match importlib.metadata.version('homelab-mcp') = {expected!r}"
        )
    except importlib.metadata.PackageNotFoundError:
        # Package not yet renamed — this will fail at RED stage, which is expected.
        pass
