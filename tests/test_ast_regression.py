"""D-15 + D-25 AST meta-test: no source file re-introduces removed credential DB paths.

Scans src/homelab_mcp/**/*.py for forbidden strings that indicate a regression.
Test files are excluded (they may mention removed names in negative assertions).
"""

from __future__ import annotations

import ast
from pathlib import Path


FORBIDDEN_SOURCE_STRINGS: list[str] = [
    "ssh_credentials",           # D-15: DB table name
    "add_credential",            # D-15: removed DB method
    "get_credential_by_hostname", # D-15: removed DB method
    "get_credential_by_id",      # D-15/D-02: removed DB method (NOTE: do NOT add "get_credential"/"delete_credential"/"list_credentials" — those are legit credential_store.py method names)
    "update_credential",         # D-15: removed DB method (distinct from update_server_credentials MCP tool name below)
    "update_last_verified",      # D-15: removed DB method
    "setup_remote_mcp_admin",    # D-25: deleted function
    "setup_mcp_admin",           # D-25: removed MCP tool name
    "update_server_credentials", # D-25: removed MCP tool name
    "remove_server",             # D-25: removed MCP tool name (D-21)
]


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
