"""AST meta-tests: regression guards against reintroduction of removed/forbidden patterns.

Phase 33 D-15 + D-25: forbidden credential-DB method names (see FORBIDDEN_SOURCE_STRINGS).

Phase 33.1 additions:
- D-08: username='mcp_admin' defaults are forbidden in function signatures under
  src/homelab_mcp/, except for files in DEFERRED_MCP_ADMIN_DEFAULT_FILES. The
  allowlist documents Phase 33.2 scope; see ROADMAP Phase 33.2 and
  .planning/phases/33.1-*/33.1-CONTEXT.md deferred section.
- D-09: password properties and username=mcp_admin defaults are forbidden in tool
  schemas, except for tools in ALLOWED_PASSWORD_TOOLS / ALLOWED_MCP_ADMIN_DEFAULT_TOOLS.
  Both allowlists document Phase 33.2 scope (SSH family tools retaining password +
  9 service tools deferred for separate cleanup sweep).
- D-10: forbidden identifiers extended with `update_mcp_admin_groups` and
  `verify_mcp_admin_access` (removed by Plan 33.1-03).
"""

from __future__ import annotations

import ast
from pathlib import Path

# Strings whose presence in source AST (as Name, Attribute, or string literals) indicates regression
FORBIDDEN_SOURCE_STRINGS: list[str] = [
    "ssh_credentials",            # D-15: DB table name
    "add_credential",             # D-15: removed DB method
    "get_credential_by_hostname", # D-15: removed DB method
    "get_credential_by_id",       # D-15/D-02: removed DB method (NOTE: do NOT add "get_credential"/"delete_credential"/"list_credentials" — those are legit credential_store.py method names)
    "update_credential",          # D-15: removed DB method (distinct from update_server_credentials MCP tool name below)
    "update_last_verified",       # D-15: removed DB method
    "setup_remote_mcp_admin",     # D-25: deleted function
    "setup_mcp_admin",            # D-25: removed MCP tool name
    "update_server_credentials",  # D-25: removed MCP tool name
    "remove_server",              # D-25: removed MCP tool name (D-21)
    "update_mcp_admin_groups",    # D-10: removed by Plan 33.1-03
    "verify_mcp_admin_access",    # D-10: removed by Plan 33.1-03
]

# Narrow allowlist: certain files may legitimately contain specific forbidden strings
# without it being a regression (e.g., migration.py names ssh_credentials inside DROP logic).
ALLOWED_EXCEPTIONS: dict[str, set[str]] = {
    # migration.py legitimately names `ssh_credentials` inside the DROP statement
    # (removing this reference would prevent the drop from firing — self-defeating).
    "ssh_credentials": {"migration.py"},
}

# Phase 33.2 scope — mcp_admin cleanup sweep extension. These files retain
# username='mcp_admin' defaults pending Phase 33.2. Every entry is tracked in
# ROADMAP Phase 33.2 and documented in
# .planning/phases/33.1-*/33.1-CONTEXT.md deferred section.
DEFERRED_MCP_ADMIN_DEFAULT_FILES: frozenset[str] = frozenset({
    "src/homelab_mcp/ssh_connection.py",       # Phase 33.2 scope
    "src/homelab_mcp/service_installer.py",    # Phase 33.2 scope
})


def _collect_string_literals(tree: ast.AST) -> list[str]:
    """Walk AST and collect all string constant values."""
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def _collect_name_and_attr_ids(tree: ast.AST) -> list[str]:
    """Walk AST and collect all Name.id and Attribute.attr values."""
    ids: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            ids.append(node.id)
        elif isinstance(node, ast.Attribute):
            ids.append(node.attr)
    return ids


def test_no_forbidden_strings_in_source() -> None:
    """D-15 + D-25: No source file contains removed credential DB names or deleted tool references."""
    src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
    assert src_root.exists(), f"Source root not found: {src_root}"

    violations: list[str] = []

    for py_file in sorted(src_root.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")

        # Fast pre-check: skip files that don't contain any forbidden string
        if not any(forbidden in source for forbidden in FORBIDDEN_SOURCE_STRINGS):
            continue

        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as e:
            violations.append(f"{py_file}: SyntaxError during AST parse: {e}")
            continue

        all_strings = _collect_string_literals(tree)
        all_ids = _collect_name_and_attr_ids(tree)
        all_tokens = set(all_strings + all_ids)

        for forbidden in FORBIDDEN_SOURCE_STRINGS:
            if forbidden in all_tokens:
                allowed_files = ALLOWED_EXCEPTIONS.get(forbidden, set())
                if py_file.name in allowed_files:
                    continue
                violations.append(
                    f"{py_file.relative_to(src_root.parent.parent)}: "
                    f"contains forbidden identifier/string {forbidden!r}"
                )

    assert not violations, (
        "Phase 33 regression: found removed DB/tool references in source files.\n"
        "These strings must not appear outside test files:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


def test_no_removed_db_methods_in_source() -> None:
    """D-15: AST scan proves removed DB methods are not called anywhere in source."""
    # Wraps test_no_forbidden_strings_in_source with explicit DB-method focus — same assertion shape.
    # This is the `-k "no_removed_db_methods"` test referenced in VALIDATION.md.
    test_no_forbidden_strings_in_source()


def test_register_server_handler_no_verify_connection_param() -> None:
    """D-25: register_server in ssh_tools.py must not have verify_connection/key_path/password params."""
    import inspect

    from homelab_mcp.ssh_tools import register_server

    sig = inspect.signature(register_server)
    assert "verify_connection" not in sig.parameters, (
        "register_server must not accept verify_connection parameter after Phase 33 (D-07)"
    )
    assert "key_path" not in sig.parameters, (
        "register_server must not accept key_path parameter after Phase 33 (D-03)"
    )
    assert "password" not in sig.parameters, (
        "register_server must not accept password parameter after Phase 33 (D-06)"
    )


def test_no_username_mcp_admin_default_in_function_signatures() -> None:
    """D-08: No function in src/homelab_mcp/ may default `username` to the literal 'mcp_admin'.

    Narrow scope per Phase 33.1 CONTEXT + user's 'Narrow + defer' decision:
    files listed in DEFERRED_MCP_ADMIN_DEFAULT_FILES are allowlisted pending
    Phase 33.2's cleanup sweep. Every allowlist entry is tracked in ROADMAP
    Phase 33.2.

    Catches regression of Phase 33.1 Plan 04 (sitemap.py default cleanup).
    Catches any future re-introduction of `username='mcp_admin'` anywhere outside
    the narrow-scope allowlist.
    """
    src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
    repo_root = src_root.parent.parent
    assert src_root.exists(), f"Source root not found: {src_root}"

    violations: list[str] = []

    for py_file in sorted(src_root.rglob("*.py")):
        # File-level allowlist: compare via POSIX path for cross-platform consistency.
        rel_posix = py_file.relative_to(repo_root).as_posix()
        if rel_posix in DEFERRED_MCP_ADMIN_DEFAULT_FILES:
            continue  # Phase 33.2 scope

        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError as e:
            violations.append(f"{py_file}: SyntaxError during AST parse: {e}")
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            args = node.args
            # Positional args with defaults: defaults are right-aligned.
            all_positional = args.args
            pos_defaults = args.defaults
            defaults_start = len(all_positional) - len(pos_defaults)
            for idx, arg in enumerate(all_positional):
                if arg.arg != "username":
                    continue
                default_idx = idx - defaults_start
                if default_idx < 0:
                    continue  # No default
                default_node = pos_defaults[default_idx]
                if isinstance(default_node, ast.Constant) and default_node.value == "mcp_admin":
                    violations.append(
                        f"{rel_posix}:{node.lineno} "
                        f"function `{node.name}` has `username='mcp_admin'` default — "
                        f"remove per Phase 33.1 D-08"
                    )

            # Keyword-only args: args.kwonlyargs parallel with args.kw_defaults (same-index).
            for kw_arg, kw_default in zip(args.kwonlyargs, args.kw_defaults, strict=False):
                if kw_arg.arg != "username":
                    continue
                if kw_default is None:
                    continue
                if isinstance(kw_default, ast.Constant) and kw_default.value == "mcp_admin":
                    violations.append(
                        f"{rel_posix}:{node.lineno} "
                        f"function `{node.name}` has kw-only `username='mcp_admin'` default — "
                        f"remove per Phase 33.1 D-08"
                    )

    assert not violations, (
        "Phase 33.1 regression (D-08): found `username='mcp_admin'` defaults in source files "
        "outside DEFERRED_MCP_ADMIN_DEFAULT_FILES allowlist.\n"
        + "\n".join(f"  - {v}" for v in violations)
    )
