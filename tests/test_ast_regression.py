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

# Phase 33.2 scope — service-tool + SSH-family surface deferred for separate cleanup sweep.
# Every entry here is tracked in ROADMAP Phase 33.2 and documented in
# .planning/phases/33.1-*/33.1-CONTEXT.md deferred section.
#
# Empirical check against src/homelab_mcp/tool_schemas/ssh_tools_schema.py (2026-04-22):
#   - ssh_discover / ssh_execute_command / start_interactive_shell each carry a
#     `password` property, so they belong in ALLOWED_PASSWORD_TOOLS.
#   - update_mcp_admin_groups also carries a `password` property today, but it is
#     deleted entirely by Plan 33.1-03 — intentionally NOT allowlisted so the D-09
#     test stays RED until Plan 03 lands (Wave-0-TDD handoff contract).
#
# Empirical check against src/homelab_mcp/tool_schemas/proxmox_tools_schema.py (2026-04-22):
#   - create_proxmox_lxc has a `password` property (line ~196) that is semantically
#     DISTINCT from SSH credential: it is the root password assigned to a new LXC
#     container at creation time. Phase 33's "passwords live in the keyring" model
#     does not apply — the container does not exist yet, so there is no hostname to
#     key a keyring entry on. Included here as an out-of-Phase-33.1-scope surface
#     that Phase 33.2 (or a later phase) can revisit if/when a new keyring-storage
#     model for container-creation secrets is defined. Not currently on ROADMAP 33.2
#     but documented here so the entry is visible to any future refactor.
ALLOWED_PASSWORD_TOOLS: frozenset[str] = frozenset({
    # SSH family (out-of-scope for Phase 33.1 CONTEXT D-01/D-02 enumeration)
    "ssh_discover",                           # Phase 33.2 scope
    "ssh_execute_command",                    # Phase 33.2 scope
    "start_interactive_shell",                # Phase 33.2 scope
    # Service family (deferred to Phase 33.2) — each of the 9 tools has a password property
    "check_service_requirements",             # Phase 33.2 scope
    "install_service",                        # Phase 33.2 scope
    "get_service_status",                     # Phase 33.2 scope
    "plan_terraform_service",                 # Phase 33.2 scope
    "destroy_terraform_service",              # Phase 33.2 scope
    "refresh_terraform_service",              # Phase 33.2 scope
    "check_ansible_service",                  # Phase 33.2 scope
    "run_ansible_playbook",                   # Phase 33.2 scope
    "destroy_terraform_service_preview",      # Phase 33.2 scope
    # Proxmox provisioning surface (semantically distinct: container-root-password
    # at creation, not an SSH login credential). See module-level comment above.
    "create_proxmox_lxc",                     # Phase 33.2 scope (semantic-exception — container root password)
})

# Phase 33.2 scope — username=mcp_admin default retention.
#
# Empirical check against src/homelab_mcp/tool_schemas/ssh_tools_schema.py (2026-04-22):
#   - NONE of ssh_discover / ssh_execute_command / start_interactive_shell / verify_mcp_admin /
#     update_mcp_admin_groups have `"default": "mcp_admin"` on their username property.
#     Their username schemas omit the `default` key entirely.
#   - Only the 9 service tools in service_tools_schema.py currently advertise
#     `"default": "mcp_admin"` on username — so they are the only entries here.
#   - If a future refactor reintroduces the default to an SSH tool's schema, adding it
#     here should be an explicit scope decision (not a silent widening).
ALLOWED_MCP_ADMIN_DEFAULT_TOOLS: frozenset[str] = frozenset({
    # Service family (deferred to Phase 33.2) — all 9 carry "default": "mcp_admin"
    "check_service_requirements",             # Phase 33.2 scope
    "install_service",                        # Phase 33.2 scope
    "get_service_status",                     # Phase 33.2 scope
    "plan_terraform_service",                 # Phase 33.2 scope
    "destroy_terraform_service",              # Phase 33.2 scope
    "refresh_terraform_service",              # Phase 33.2 scope
    "check_ansible_service",                  # Phase 33.2 scope
    "run_ansible_playbook",                   # Phase 33.2 scope
    "destroy_terraform_service_preview",      # Phase 33.2 scope
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


def test_no_password_or_mcp_admin_default_in_tool_registries() -> None:
    """D-09: No tool schema may advertise a `password` property (at any nesting depth)
    or default `username` to `mcp_admin`.

    Imports every `*_TOOLS` dict under `src/homelab_mcp/tool_schemas/` and recursively
    traverses `inputSchema.properties` including `items.properties` for array items.

    Narrow scope (BLOCKER 4 resolution): Phase 33.1 D-01/D-02 removed password only
    from `discover_and_map`, `bulk_discover_and_map.targets[]`, and
    `update_mcp_admin_groups`. Other SSH tools (`ssh_discover`, `ssh_execute_command`,
    `start_interactive_shell`) retain password per CONTEXT narrow scope. The 9 service
    tools also retain both password and mcp_admin default, deferred to Phase 33.2 per
    user's "Narrow + defer" decision. Both allowlists (ALLOWED_PASSWORD_TOOLS,
    ALLOWED_MCP_ADMIN_DEFAULT_TOOLS) mirror the current source that Phase 33.1 does
    not touch; widening requires a future phase.

    Catches regression of Phase 33.1 Plan 02 (schema cleanup D-01/D-02/D-03) within
    the narrow scope.
    """
    import importlib
    import pkgutil

    import homelab_mcp.tool_schemas as tool_schemas_pkg

    # Discover every module in tool_schemas/, import it, find every dict-valued
    # top-level attribute whose entries look like tool schema definitions.
    tool_registries: dict[str, dict] = {}
    for modinfo in pkgutil.iter_modules(tool_schemas_pkg.__path__):
        module = importlib.import_module(f"homelab_mcp.tool_schemas.{modinfo.name}")
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(module, attr_name)
            if not isinstance(attr, dict) or not attr:
                continue
            # Detect "this is a TOOLS-style dict": every value is a dict with "inputSchema"
            if all(isinstance(v, dict) and "inputSchema" in v for v in attr.values()):
                tool_registries[f"{modinfo.name}.{attr_name}"] = attr

    assert tool_registries, "No tool registries discovered — D-09 would be a no-op (check pkgutil)"

    violations: list[str] = []

    def _recurse(
        properties: dict,
        path: str,
        *,
        check_password: bool,
        check_mcp_admin_default: bool,
    ) -> None:
        if not isinstance(properties, dict):
            return
        for prop_name, prop_schema in properties.items():
            if not isinstance(prop_schema, dict):
                continue
            # username=mcp_admin default check — gated by per-tool allowlist
            if (
                check_mcp_admin_default
                and prop_name == "username"
                and prop_schema.get("default") == "mcp_admin"
            ):
                violations.append(
                    f"{path}.{prop_name} — D-09: username must not default to 'mcp_admin'"
                )
            # password property check — gated by per-tool allowlist
            if check_password and prop_name == "password":
                violations.append(f"{path}.{prop_name} — D-09: password property forbidden")
            # Recurse into nested object properties
            nested = prop_schema.get("properties")
            if isinstance(nested, dict):
                _recurse(
                    nested,
                    f"{path}.{prop_name}.properties",
                    check_password=check_password,
                    check_mcp_admin_default=check_mcp_admin_default,
                )
            # Recurse into array items.properties
            items = prop_schema.get("items")
            if isinstance(items, dict):
                items_props = items.get("properties")
                if isinstance(items_props, dict):
                    _recurse(
                        items_props,
                        f"{path}.{prop_name}.items.properties",
                        check_password=check_password,
                        check_mcp_admin_default=check_mcp_admin_default,
                    )

    for registry_name, registry in tool_registries.items():
        for tool_name, tool_def in registry.items():
            props = tool_def.get("inputSchema", {}).get("properties")
            if not isinstance(props, dict):
                continue
            check_password = tool_name not in ALLOWED_PASSWORD_TOOLS
            check_mcp_admin_default = tool_name not in ALLOWED_MCP_ADMIN_DEFAULT_TOOLS
            _recurse(
                props,
                f"{registry_name}[{tool_name!r}].inputSchema.properties",
                check_password=check_password,
                check_mcp_admin_default=check_mcp_admin_default,
            )

    assert not violations, (
        "Phase 33.1 regression (D-09): found forbidden `password` property or "
        "`username` default of 'mcp_admin' in tool schemas (outside allowlists).\n"
        + "\n".join(f"  - {v}" for v in violations)
    )
