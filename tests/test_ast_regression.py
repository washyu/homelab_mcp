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
    "ssh_credentials",  # D-15: DB table name
    "add_credential",  # D-15: removed DB method
    "get_credential_by_hostname",  # D-15: removed DB method
    "get_credential_by_id",  # D-15/D-02: removed DB method (NOTE: do NOT add "get_credential"/"delete_credential"/"list_credentials" — those are legit credential_store.py method names)
    "update_credential",  # D-15: removed DB method (distinct from update_server_credentials MCP tool name below)
    "update_last_verified",  # D-15: removed DB method
    "setup_remote_mcp_admin",  # D-25: deleted function
    "setup_mcp_admin",  # D-25: removed MCP tool name
    "update_server_credentials",  # D-25: removed MCP tool name
    "remove_server",  # D-25: removed MCP tool name (D-21)
    "update_mcp_admin_groups",  # D-10: removed by Plan 33.1-03
    "verify_mcp_admin_access",  # D-10: removed by Plan 33.1-03
    # ─── Phase 36 D-12 additions ───
    "drift_baselines",  # Phase 36 D-12: dropped table name
    "upsert_drift_baseline",  # Phase 36 D-12: removed adapter method
    "get_drift_baseline",  # Phase 36 D-12: removed adapter method
    "get_all_drift_baselines",  # Phase 36 D-12: removed adapter method
]

# Narrow allowlist: certain files may legitimately contain specific forbidden strings
# without it being a regression (e.g., migration.py names ssh_credentials inside DROP logic).
ALLOWED_EXCEPTIONS: dict[str, set[str]] = {
    # migration.py legitimately names `ssh_credentials` inside the DROP statement
    # (removing this reference would prevent the drop from firing — self-defeating).
    "ssh_credentials": {"migration.py"},
    # ─── Phase 36 D-12 addition ───
    # migration.py legitimately names `drift_baselines` inside the DROP statement
    # (D-05 drop step references the literal table name).
    "drift_baselines": {"migration.py"},
}

# Phase 33.2 scope — mcp_admin cleanup sweep extension. These files retain
# username='mcp_admin' defaults pending Phase 33.2. Every entry is tracked in
# ROADMAP Phase 33.2 and documented in
# .planning/phases/33.1-*/33.1-CONTEXT.md deferred section.
DEFERRED_MCP_ADMIN_DEFAULT_FILES: frozenset[str] = frozenset(
    {
        "src/homelab_mcp/ssh_connection.py",  # Phase 33.2 scope
        "src/homelab_mcp/service_installer.py",  # Phase 33.2 scope
    }
)

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
ALLOWED_PASSWORD_TOOLS: frozenset[str] = frozenset(
    {
        # SSH family (out-of-scope for Phase 33.1 CONTEXT D-01/D-02 enumeration)
        "ssh_discover",  # Phase 33.2 scope
        "ssh_execute_command",  # Phase 33.2 scope
        "start_interactive_shell",  # Phase 33.2 scope
        # Service family (deferred to Phase 33.2) — each of the 9 tools has a password property
        "check_service_requirements",  # Phase 33.2 scope
        "install_service",  # Phase 33.2 scope
        "get_service_status",  # Phase 33.2 scope
        "plan_terraform_service",  # Phase 33.2 scope
        "destroy_terraform_service",  # Phase 33.2 scope
        "refresh_terraform_service",  # Phase 33.2 scope
        "check_ansible_service",  # Phase 33.2 scope
        "run_ansible_playbook",  # Phase 33.2 scope
        "destroy_terraform_service_preview",  # Phase 33.2 scope
        # Proxmox provisioning surface (semantically distinct: container-root-password
        # at creation, not an SSH login credential). See module-level comment above.
        "create_proxmox_lxc",  # Phase 33.2 scope (semantic-exception — container root password)
    }
)

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
ALLOWED_MCP_ADMIN_DEFAULT_TOOLS: frozenset[str] = frozenset(
    {
        # Service family (deferred to Phase 33.2) — all 9 carry "default": "mcp_admin"
        "check_service_requirements",  # Phase 33.2 scope
        "install_service",  # Phase 33.2 scope
        "get_service_status",  # Phase 33.2 scope
        "plan_terraform_service",  # Phase 33.2 scope
        "destroy_terraform_service",  # Phase 33.2 scope
        "refresh_terraform_service",  # Phase 33.2 scope
        "check_ansible_service",  # Phase 33.2 scope
        "run_ansible_playbook",  # Phase 33.2 scope
        "destroy_terraform_service_preview",  # Phase 33.2 scope
    }
)


def _collect_string_literals(tree: ast.AST) -> list[str]:
    """Walk AST and collect all string constant values."""
    return [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]


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
                    f"{py_file.relative_to(src_root.parent.parent)}: contains forbidden identifier/string {forbidden!r}"
                )

    assert not violations, (
        "Phase 33+36 regression: found removed DB/tool references in source files.\n"
        "These strings must not appear outside test files:\n" + "\n".join(f"  - {v}" for v in violations)
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
    assert "key_path" not in sig.parameters, "register_server must not accept key_path parameter after Phase 33 (D-03)"
    assert "password" not in sig.parameters, "register_server must not accept password parameter after Phase 33 (D-06)"


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
        "outside DEFERRED_MCP_ADMIN_DEFAULT_FILES allowlist.\n" + "\n".join(f"  - {v}" for v in violations)
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
            if check_mcp_admin_default and prop_name == "username" and prop_schema.get("default") == "mcp_admin":
                violations.append(f"{path}.{prop_name} — D-09: username must not default to 'mcp_admin'")
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


# ─────────────────────────────────────────────────────────────────────────────
# Phase 35 AST regression guards (D-14, D-15, D-16)
# ─────────────────────────────────────────────────────────────────────────────


def test_store_device_matches_on_hostname_alone_phase35() -> None:
    """Phase 35 D-14: store_device in BOTH adapters must have a hostname-only
    match clause. The degenerate-hostname fallback branch (``hostname = ? AND
    connection_ip = ?`` / ``hostname = %s AND connection_ip = %s``) is
    permitted and expected — but a hostname-only branch MUST also exist in
    each function body.

    Prevents regression of Plan 03: if a future commit reverts the match
    clause to the Phase-33-era ``(hostname, connection_ip)`` composite match,
    this test fails and names the line.
    """
    src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
    db_source = (src_root / "database.py").read_text(encoding="utf-8")

    tree = ast.parse(db_source, filename="database.py")
    # Filter out the abstract-base method — it has no SQL strings, only `pass`.
    store_device_funcs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name == "store_device"
        and any(
            isinstance(c, ast.Constant) and isinstance(c.value, str) and "SELECT id FROM devices" in c.value
            for c in ast.walk(node)
        )
    ]
    assert len(store_device_funcs) == 2, (
        f"Phase 35 D-14: expected 2 concrete store_device functions (SQLite + Postgres), "
        f"found {len(store_device_funcs)}"
    )

    violations: list[str] = []
    for func in store_device_funcs:
        body_strings = [
            node.value for node in ast.walk(func) if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        hostname_only_found = any(
            (
                "SELECT id FROM devices" in s
                and ("WHERE hostname = ?" in s or "WHERE hostname = %s" in s)
                and "AND connection_ip" not in s
            )
            for s in body_strings
        )
        if not hostname_only_found:
            violations.append(
                f"store_device at line {func.lineno}: no hostname-only SELECT "
                f"found — Phase 35 D-14 regression (zombie-row fix reverted?)"
            )

    assert not violations, "Phase 35 D-14 regression — store_device must match hostname alone:\n" + "\n".join(
        f"  - {v}" for v in violations
    )


def test_ssh_discover_system_wraps_every_conn_run_phase35() -> None:
    """Phase 35 D-15: every ``conn.run(...)`` call inside ``ssh_discover_system``
    MUST be enclosed by either ``asyncio.wait_for(...)`` or the
    ``_run_with_timeout(...)`` helper. A bare ``await conn.run(...)`` inside
    ssh_discover_system is a regression of Plan 01.
    """
    src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
    source = (src_root / "ssh_tools.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="ssh_tools.py")

    # Annotate parent pointers for upward-walk.
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            setattr(child, "_parent", parent)  # noqa: B010

    target = next(
        (
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == "ssh_discover_system"
        ),
        None,
    )
    assert target is not None, "Phase 35 D-15: ssh_discover_system not found in ssh_tools.py"

    def _enclosing_allowed_call(call_node: ast.AST) -> bool:
        current = getattr(call_node, "_parent", None)
        while current is not None:
            if isinstance(current, ast.Call):
                func = current.func
                if isinstance(func, ast.Attribute) and func.attr == "wait_for":
                    return True
                if isinstance(func, ast.Name) and func.id == "_run_with_timeout":
                    return True
            current = getattr(current, "_parent", None)
        return False

    violations: list[int] = []
    for node in ast.walk(target):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "run"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "conn"
        ):
            continue
        if not _enclosing_allowed_call(node):
            violations.append(node.lineno)

    assert not violations, (
        "Phase 35 D-15 regression — bare `conn.run()` calls inside "
        "ssh_discover_system at line(s): "
        + ", ".join(map(str, violations))
        + ". Wrap each in `_run_with_timeout(...)` or `asyncio.wait_for(conn.run(...), ...)`."
    )


PHASE35_FORBIDDEN_COERCION_FIELDS: frozenset[str] = frozenset(
    {
        "cpu_cores",
        "memory_total",
        "disk_use_percent",
    }
)


def test_no_threshold_coercion_in_analyzer_bodies_phase35() -> None:
    """Phase 35 D-16: ``device.get("<field>") or 0`` and
    ``device.get("<field>") or ""`` coercion patterns are forbidden on
    threshold fields (cpu_cores, memory_total, disk_use_percent) inside
    ``analyze_network_topology`` or ``suggest_deployments``.
    """
    src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
    source = (src_root / "sitemap.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="sitemap.py")

    analyzers = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
        and n.name in ("analyze_network_topology", "suggest_deployments")
    ]
    assert len(analyzers) == 2, f"Phase 35 D-16: expected 2 analyzer functions, found {len(analyzers)}"

    violations: list[str] = []
    for func in analyzers:
        for node in ast.walk(func):
            if not (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or)):
                continue
            if len(node.values) != 2:
                continue
            left, right = node.values
            if not (isinstance(right, ast.Constant) and right.value in (0, "")):
                continue
            if not (
                isinstance(left, ast.Call)
                and isinstance(left.func, ast.Attribute)
                and left.func.attr == "get"
                and left.args
                and isinstance(left.args[0], ast.Constant)
                and isinstance(left.args[0].value, str)
                and left.args[0].value in PHASE35_FORBIDDEN_COERCION_FIELDS
            ):
                continue
            violations.append(
                f"{func.name}:{node.lineno} — "
                f'`device.get("{left.args[0].value}") or {right.value!r}` '
                f"coercion forbidden (D-16)"
            )

    assert not violations, (
        "Phase 35 D-16 regression — threshold-field coercion reappeared in "
        "analyzer bodies. Use explicit `is not None` guards or "
        "`_has_threshold_data(device, ...)`:\n" + "\n".join(f"  - {v}" for v in violations)
    )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 36 AST regression guards (D-13)
# ─────────────────────────────────────────────────────────────────────────────


def test_drift_detection_no_baseline_references_phase36() -> None:
    """Phase 36 D-13: drift_detection.py must contain no reference to the
    parallel baseline data layer — singular OR plural, in any source-text form
    (string literal, identifier, attribute access).

    Belt-and-braces guard: the broader test_no_forbidden_strings_in_source()
    catches reintroduction in any source file via AST walk; this test pins
    drift_detection.py specifically as the only module on the drift-scan call
    chain (per CONTEXT.md SC-4 wording).
    """
    src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
    source = (src_root / "drift_detection.py").read_text(encoding="utf-8")

    forbidden = [
        "drift_baseline",  # singular — covers e.g. db_adapter.upsert_drift_baseline()
        "drift_baselines",  # plural — covers table name + db_adapter.get_all_drift_baselines()
    ]
    violations = [s for s in forbidden if s in source]
    assert not violations, (
        f"Phase 36 D-13 regression — drift_detection.py contains forbidden baseline references: {violations}. "
        f"scan_drift must read from sitemap rows (db_adapter.get_all_devices()) only."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 37 AST regression guards (D-11 / D-12)
# ─────────────────────────────────────────────────────────────────────────────


class TestPhase37DriftHygiene:
    """Phase 37 D-11 + D-12: drift surface architectural lock-in.

    D-11 (PROXMOX_HOST forbidden in drift surface, DRFT-15 closure):
      Drift-family files must never reference the deprecated PROXMOX_HOST
      env var. Recovery should point to sitemap CRUD tools and the
      `homelab-mcp credentials add --type proxmox` CLI instead.

      Per CONTEXT.md D-08 the openapi_app.py "Proxmox" entry STILL contains
      PROXMOX_HOST (Phase 40 POL-03 territory) — this guard scopes the
      openapi_app.py check to ONLY the "Drift Detection" INFRA_REQUIREMENTS
      value, leaving the Proxmox entry to a future phase.

    D-12 (no baseline-lifecycle MCP tools, DRFT-16 closure):
      The Bug-C tool names register_drift_baseline / list_drift_baselines /
      delete_drift_baseline must NEVER appear anywhere under
      src/homelab_mcp/. Phase 36 architecturally dissolved Bug C by
      unifying drift detection with the sitemap; this guard locks that in.

    Per CONTEXT.md D-15, both guards are AST-only — no runtime registry
    check. CI catches reintroduction at merge time; the duplicate
    enforcement at server startup is not worth the production cost.
    """

    # ── D-11: PROXMOX_HOST forbidden in drift surface ──────────────────

    # Drift-family source files that must contain ZERO PROXMOX_HOST references.
    # NOTE: openapi_app.py is intentionally NOT in this list — it contains a
    # legitimate "Proxmox" PROXMOX_HOST reference (Phase 40 POL-03 territory).
    # The "Drift Detection" entry in openapi_app.py is checked separately via
    # dict access below.
    _DRIFT_SURFACE_FILES: tuple[str, ...] = (
        "drift_detection.py",
        "tool_handlers/drift_handlers.py",
        "tool_schemas/drift_tools_schema.py",
    )

    def test_no_proxmox_host_in_drift_files(self) -> None:
        """Phase 37 D-11: drift surface files contain no PROXMOX_HOST references.

        Scans each of:
          - src/homelab_mcp/drift_detection.py
          - src/homelab_mcp/tool_handlers/drift_handlers.py
          - src/homelab_mcp/tool_schemas/drift_tools_schema.py

        for the substring `PROXMOX_HOST` (must be zero matches per file). Then
        imports INFRA_REQUIREMENTS from openapi_app and verifies that the
        "Drift Detection" entry's value does not contain PROXMOX_HOST.

        The "Proxmox" entry in INFRA_REQUIREMENTS is intentionally NOT checked —
        it is Phase 40 POL-03 territory per CONTEXT.md D-08.
        """
        src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
        violations: list[str] = []

        # File scan: each drift-surface file must have zero PROXMOX_HOST.
        for relative_path in self._DRIFT_SURFACE_FILES:
            file_path = src_root / relative_path
            assert file_path.exists(), (
                f"Phase 37 D-11 setup error: {file_path} does not exist. "
                f"_DRIFT_SURFACE_FILES is out of sync with the source tree."
            )
            source = file_path.read_text(encoding="utf-8")
            if "PROXMOX_HOST" in source:
                violations.append(
                    f"{relative_path}: contains PROXMOX_HOST (Phase 37 D-11 / DRFT-15 — "
                    f"drift surface must reference sitemap CRUD tools + credentials CLI, "
                    f"not the deprecated env var)"
                )

        # Dict-value scan: openapi_app.py "Drift Detection" INFRA_REQUIREMENTS
        # entry must lack PROXMOX_HOST. Done via import to avoid fragile line-
        # number coupling; the "Proxmox" entry on the previous line is
        # intentionally not checked (Phase 40 POL-03).
        from homelab_mcp.openapi_app import INFRA_REQUIREMENTS

        drift_entry = INFRA_REQUIREMENTS.get("Drift Detection", "")
        if "PROXMOX_HOST" in drift_entry:
            violations.append(
                "openapi_app.py INFRA_REQUIREMENTS['Drift Detection']: "
                "contains PROXMOX_HOST (Phase 37 D-11 / DRFT-15)"
            )

        assert not violations, (
            "Phase 37 D-11 regression — PROXMOX_HOST reintroduced in drift surface:\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nDrift-family text should reference discover_and_map / "
            "get_network_sitemap / purge_failed_discoveries / decommission_device "
            "and the 'homelab-mcp credentials add --type proxmox' CLI instead."
        )

    # ── D-12: no baseline-lifecycle MCP tool names anywhere in src/ ─────

    # Forbidden tool names — Bug C architectural dissolution. Per CONTEXT.md
    # D-12, ZERO matches anywhere under src/homelab_mcp/. No allowed
    # exceptions: these tools were never built and must never be built.
    _FORBIDDEN_BASELINE_TOOL_NAMES: tuple[str, ...] = (
        "register_drift_baseline",
        "list_drift_baselines",
        "delete_drift_baseline",
    )

    def test_no_baseline_lifecycle_tool_names_in_source(self) -> None:
        """Phase 37 D-12: forbidden baseline-lifecycle MCP tool names absent.

        Walks every *.py under src/homelab_mcp/ and scans each file's source
        for register_drift_baseline / list_drift_baselines / delete_drift_baseline.
        Must be ZERO matches across all source files — no allowed exceptions
        (these tools were dissolved architecturally by Phase 36's sitemap
        unification per DRFT-16 / Bug C).

        Catches reintroduction in tool_schemas/, tools.py, handler files,
        docstrings, deferred imports, and any other source location.

        Per CONTEXT.md D-13, this scan is source-only; documentation drift is
        caught via D-08 sweep + code review.
        """
        src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
        assert src_root.exists(), f"Source root not found: {src_root}"

        violations: list[str] = []

        for py_file in sorted(src_root.rglob("*.py")):
            source = py_file.read_text(encoding="utf-8")
            for forbidden in self._FORBIDDEN_BASELINE_TOOL_NAMES:
                if forbidden in source:
                    violations.append(
                        f"{py_file.relative_to(src_root.parent.parent)}: "
                        f"contains forbidden tool name {forbidden!r}"
                    )

        assert not violations, (
            "Phase 37 D-12 regression — forbidden baseline-lifecycle MCP tool "
            "names reintroduced in source:\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nPhase 36 architecturally dissolved Bug C by unifying drift "
            "detection with the sitemap. The MCP tool surface must NEVER expose "
            "register_drift_baseline / list_drift_baselines / delete_drift_baseline "
            "(DRFT-16). Drift baselines ARE sitemap rows; lifecycle is handled by "
            "discover_and_map / decommission_device / purge_failed_discoveries."
        )
