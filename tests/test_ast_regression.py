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

    # ── D-11 + Phase 40 D-06: PROXMOX_HOST forbidden in drift + proxmox surface ──

    # PROXMOX_HOST-hygiene source files (Phase 37 D-11 + Phase 40 D-06).
    # Drift surface (Phase 37) + Proxmox surface (Phase 40 POL-03 hard-
    # removed the env-var fallback at proxmox_api.py:474). openapi_app.py
    # is NOT in this file list — its PROXMOX_HOST hygiene is verified via
    # the INFRA_REQUIREMENTS dict-value scans below.
    _DRIFT_SURFACE_FILES: tuple[str, ...] = (
        "drift_detection.py",
        "tool_handlers/drift_handlers.py",
        "tool_schemas/drift_tools_schema.py",
        "proxmox_api.py",  # Phase 40 D-06 / POL-03
        "tool_schemas/proxmox_tools_schema.py",  # Phase 40 D-06 / POL-02 + D-05
    )

    def test_no_proxmox_host_in_drift_files(self) -> None:
        """Phase 37 D-11 + Phase 40 D-06: PROXMOX_HOST-surface files contain no PROXMOX_HOST references.

        Scans each of:
          - src/homelab_mcp/drift_detection.py
          - src/homelab_mcp/tool_handlers/drift_handlers.py
          - src/homelab_mcp/tool_schemas/drift_tools_schema.py
          - src/homelab_mcp/proxmox_api.py                       (Phase 40 D-06 / POL-03)
          - src/homelab_mcp/tool_schemas/proxmox_tools_schema.py (Phase 40 D-06 / POL-02 + D-05)

        for the substring `PROXMOX_HOST` (must be zero matches per file). Then
        imports INFRA_REQUIREMENTS from openapi_app and verifies that BOTH the
        "Drift Detection" entry (Phase 37) AND the "Proxmox" entry (Phase 40)
        lack PROXMOX_HOST.
        """
        src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
        violations: list[str] = []

        # File scan: each PROXMOX_HOST-surface file must have zero PROXMOX_HOST.
        for relative_path in self._DRIFT_SURFACE_FILES:
            file_path = src_root / relative_path
            assert file_path.exists(), (
                f"Phase 37 D-11 / Phase 40 D-06 setup error: {file_path} does not exist. "
                f"_DRIFT_SURFACE_FILES is out of sync with the source tree."
            )
            source = file_path.read_text(encoding="utf-8")
            if "PROXMOX_HOST" in source:
                violations.append(
                    f"{relative_path}: contains PROXMOX_HOST (Phase 37 D-11 / DRFT-15 + "
                    f"Phase 40 D-06 / POL-03 — surface must reference the credentials "
                    f"CLI (`homelab-mcp credentials add --type proxmox`) and sitemap "
                    f"CRUD tools, not the deprecated env var)"
                )

        # Dict-value scans: openapi_app.py INFRA_REQUIREMENTS entries must lack
        # PROXMOX_HOST. Done via import to avoid fragile line-number coupling.
        from homelab_mcp.openapi_app import INFRA_REQUIREMENTS

        drift_entry = INFRA_REQUIREMENTS.get("Drift Detection", "")
        if "PROXMOX_HOST" in drift_entry:
            violations.append(
                "openapi_app.py INFRA_REQUIREMENTS['Drift Detection']: contains PROXMOX_HOST (Phase 37 D-11 / DRFT-15)"
            )

        # Phase 40 D-06: openapi_app.py "Proxmox" INFRA_REQUIREMENTS entry must
        # also lack PROXMOX_HOST (POL-03 D-04 + D-05 ripple). Pre-Phase-40 this
        # entry contained "Set PROXMOX_HOST..."; Phase 40 Plan 02 rewrote it to
        # point at `homelab-mcp credentials add --type proxmox`.
        proxmox_entry = INFRA_REQUIREMENTS.get("Proxmox", "")
        if "PROXMOX_HOST" in proxmox_entry:
            violations.append(
                "openapi_app.py INFRA_REQUIREMENTS['Proxmox']: contains PROXMOX_HOST (Phase 40 D-06 / POL-03)"
            )

        assert not violations, (
            "Phase 37 D-11 + Phase 40 D-06 regression — PROXMOX_HOST reintroduced "
            "in drift/proxmox surface:\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nText should reference 'homelab-mcp credentials add --type proxmox' "
            "(per-node) or '--scope cluster:<name>' (cluster-wide), and sitemap CRUD "
            "tools (discover_and_map / get_network_sitemap / purge_failed_discoveries "
            "/ decommission_device) — never the deprecated PROXMOX_HOST env var."
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
                        f"{py_file.relative_to(src_root.parent.parent)}: contains forbidden tool name {forbidden!r}"
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


# ─────────────────────────────────────────────────────────────────────────────
# Phase 38.1 AST regression guards (D-15 / D-17)
# ─────────────────────────────────────────────────────────────────────────────


class TestPhase381CredBinding:
    """Phase 38.1 D-15/D-17: drift's row loop never silently skips a sitemap row.

    D-15: no ``ast.Continue`` may appear inside the row-iter for-loop body of
        ``drift_detection.scan_drift``. Every row MUST land in one of five buckets
        (probed_ok / unreachable / not_eligible / unknown / changed).
    D-17: degenerate-row routing now goes to ``not_eligible``, not ``continue`` —
        D-15 catches this structurally.
    D-16: scope is ONLY ``scan_drift`` for now; Phase 39's unknown/changed helpers
        will extend.

    NOTE on function name: ``scan_drift`` (drift_detection.py:54), NOT
    ``scan_infrastructure_drift`` (the latter is the MCP tool name in
    tool_handlers/drift_handlers.py). RESEARCH Pitfall 1.
    """

    def test_scan_drift_no_continue_in_row_loop_phase38_1(self) -> None:
        """Phase 38.1 D-15: no ``continue`` in scan_drift row loop.

        The for-loop body must route EVERY row into one of the five buckets.
        A bare ``continue`` is the original Bug O shape (silent skip).
        """
        src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
        source = (src_root / "drift_detection.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename="drift_detection.py")

        target = next(
            (
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == "scan_drift"
            ),
            None,
        )
        assert target is not None, (
            "Phase 38.1 D-15: scan_drift not found in drift_detection.py "
            "(if you renamed the function, update this guard)"
        )

        # Find the row-iter for-loop ("for row in rows:")
        row_loops = [
            n
            for n in ast.walk(target)
            if isinstance(n, ast.For) and isinstance(n.target, ast.Name) and n.target.id == "row"
        ]
        assert len(row_loops) == 1, (
            f"Phase 38.1 D-15: expected one `for row in rows:` loop in scan_drift, "
            f"found {len(row_loops)}. If you intentionally split the loop, update "
            f"this guard's row-loop discovery shape."
        )

        violations = [n.lineno for n in ast.walk(row_loops[0]) if isinstance(n, ast.Continue)]
        assert not violations, (
            f"Phase 38.1 D-15 regression — `continue` reappeared in scan_drift row "
            f"loop at line(s): {violations}. Every row must land in one of five "
            f"buckets (probed_ok, unreachable, not_eligible, unknown, changed)."
        )

    def test_drift_loop_routes_degenerate_to_not_eligible_phase38_1(self) -> None:
        """Phase 38.1 D-17: scan_drift must contain at least one not_eligible.append(...)
        call — degenerate-row routing per D-17 + credential-failure routing per D-15.
        """
        src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
        source = (src_root / "drift_detection.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename="drift_detection.py")
        target = next(
            (
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == "scan_drift"
            ),
            None,
        )
        assert target is not None, "Phase 38.1 D-15: scan_drift not found"
        not_eligible_appends = [
            n
            for n in ast.walk(target)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "not_eligible"
            and n.func.attr == "append"
        ]
        assert not_eligible_appends, (
            "Phase 38.1 D-17: scan_drift must contain at least one "
            "`not_eligible.append(...)` call (degenerate-row routing per D-17 + "
            "credential-failure routing per D-15). Current source has none."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 39.1 AST regression guard (R6-regression closure; D-16 anticipated extension)
# ─────────────────────────────────────────────────────────────────────────────


class TestPhase39_1NoSkipInDriftEnum:
    """Phase 39.1 R6-regression: every get_proxmox_client(...) call inside
    drift_detection.py threads credential_id= as a keyword.

    Regression closed: Phase 39 commit e05df24 introduced
    ``_enumerate_proxmox_vms._enum_one`` which called
    ``get_proxmox_client(host=h, session=session)`` WITHOUT ``credential_id=``,
    regressing the Phase 38.1 R6 binding contract on the unknown-VM
    enumeration path. The Phase 38.1 D-15 guard covered only ``scan_drift``'s
    row loop body — D-16 explicitly anticipated this extension point:
    "Phase 39's unknown/changed detection helpers will likely extend the
    guard's target list when they land."

    Scope (per threat model T-39.1-02 — precise carve-out):
      * Covers ONLY direct ``get_proxmox_client(...)`` calls inside
        ``src/homelab_mcp/drift_detection.py``. Other modules and
        ``getattr(...)``-indirected calls are NOT in scope.
      * Import aliasing (``from .proxmox_api import get_proxmox_client as
        <other>``) is BLOCKED by an explicit canonical-name assertion at
        the top of the guard (WR-03 mitigation) — an alias rebinding
        would otherwise be invisible to the ast.Name match.
      * A future ``/version`` ping helper that intentionally does NOT need
        credentials (e.g., capability-discovery before binding) would need
        an explicit allowlist entry — but no such helper exists today, and
        the cost of adding one is minimal.

    Threat model T-39.1-03 mitigation: walk the AST (match
    ``ast.Call`` where ``func.id == 'get_proxmox_client'``), do NOT regex
    source text. Source-text matching misses ``getattr`` indirection.
    """

    def test_get_proxmox_client_calls_thread_credential_id_phase39_1(self) -> None:
        """Every direct get_proxmox_client(...) call inside drift_detection.py
        includes credential_id= as a keyword argument."""
        src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
        source = (src_root / "drift_detection.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename="drift_detection.py")

        # WR-03 (Phase 39.1 review): guard against import aliasing. The
        # ast.Call match below keys on `func.id == "get_proxmox_client"`,
        # which silently drops any call site bound to a different local
        # name (e.g., `from .proxmox_api import get_proxmox_client as gpc`
        # makes the call site `await gpc(...)` invisible to this guard).
        # Pin the canonical name here so a future refactor that aliases
        # the import fails LOUDLY at this assertion instead of silently
        # weakening the guard's coverage. Option (b) — extending the
        # guard to track aliased local names — is more permissive but
        # requires walking ImportFrom nodes and resolving call.func.id
        # back to its originating import; option (a) below is simpler
        # and matches the project's "make implicit assumptions explicit"
        # convention.
        imports = [
            a
            for n in ast.walk(tree)
            if isinstance(n, ast.ImportFrom) and (n.module or "").endswith("proxmox_api")
            for a in n.names
            if a.name == "get_proxmox_client"
        ]
        assert imports and all(a.asname is None for a in imports), (
            "Phase 39.1 guard (WR-03): get_proxmox_client must be imported "
            "under its canonical name in drift_detection.py — aliasing "
            "(`from .proxmox_api import get_proxmox_client as <other>`) "
            "would bypass the ast.Name match below and silently drop call "
            "sites from this guard's coverage. If you have a legitimate "
            "reason to alias, either rewrite this guard to track aliased "
            "local names or remove the alias."
        )

        calls = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "get_proxmox_client"
        ]
        assert calls, (
            "Phase 39.1 guard: zero get_proxmox_client(...) calls found in "
            "drift_detection.py — either the file was renamed/refactored "
            "(update this guard) or all calls were removed (the guard is "
            "now vacuous and should be re-evaluated)."
        )

        violations: list[int] = []
        for call in calls:
            kw_names = {kw.arg for kw in call.keywords if kw.arg is not None}
            if "credential_id" not in kw_names:
                violations.append(call.lineno)

        assert not violations, (
            f"Phase 39.1 R6-regression — get_proxmox_client(...) called "
            f"WITHOUT credential_id= keyword inside drift_detection.py at "
            f"line(s): {violations}. This is the Phase 38.1 R6 binding "
            f"contract: every Proxmox-touching call on the drift call chain "
            f"must thread the binding UUID via credential_id=. If you have "
            f"a legitimate non-credentialed call (e.g., a /version ping "
            f"helper that intentionally bypasses the resolver), add it to "
            f"an explicit allowlist in this guard with a comment explaining "
            f"why credential_id= is not needed."
        )

    def test_phase39_1_guard_call_site_floor(self) -> None:
        """WR-02 (Phase 39.1 review): rename of
        ``test_phase39_1_guard_catches_added_helper``. The original name
        promised behavior the test does not deliver — it does NOT exercise
        an "added helper" scenario, only enumerates call-site count.

        Defensive sanity check: the guard ENUMERATES at least 2 call sites
        (row-loop in scan_drift + _enum_one in _enumerate_proxmox_vms).
        This protects against a refactor that accidentally drops one of
        the known call sites entirely (e.g., inlining _enum_one and
        forgetting to re-add the get_proxmox_client call) — the primary
        guard above would then become vacuous on a 1-call file. If a
        future refactor LEGITIMATELY consolidates these to a single
        helper, this count drops and the floor must be updated to match
        the new structure (or this test removed if the consolidation
        eliminates the regression risk it was added to defend against).
        """
        src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
        source = (src_root / "drift_detection.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename="drift_detection.py")

        calls = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "get_proxmox_client"
        ]
        assert len(calls) >= 2, (
            f"Phase 39.1 guard discovery: expected >= 2 get_proxmox_client(...) "
            f"call sites in drift_detection.py (scan_drift row loop + "
            f"_enumerate_proxmox_vms._enum_one), found {len(calls)}. If you "
            f"intentionally consolidated, update this floor or remove the "
            f"defensive test."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 39 AST regression guards (D-11 / D-12)
# ─────────────────────────────────────────────────────────────────────────────


class TestPhase39DriftCases:
    """Phase 39 D-11/D-12: helpers added in Phase 39 stay loop-free.

    Recommended path D-11(b): rather than extending an allowlist, the new
    helpers (``_diff_fingerprints``, ``_enumerate_unknown_vms``,
    ``_classify_unreachable``) are written without ``continue`` inside any
    loop body that appends to a bucket-shaped list. This keeps the AST guard
    scope unchanged from Phase 38.1.

    D-12 carve-out (continue invariant only): ``_enumerate_proxmox_vms`` is
    OUT of the ``continue``-invariant guard scope — it builds enumeration
    TARGETS (does not iterate sitemap rows feeding bucket appends), so its
    defensive ``continue`` for empty hostname is allowed. Phase 39.1 added
    ``TestPhase39_1NoSkipInDriftEnum`` which DOES cover
    ``_enumerate_proxmox_vms`` for a different invariant — every
    ``get_proxmox_client(...)`` call must thread ``credential_id=``.
    """

    PHASE_39_NEW_HELPERS = (
        "_diff_fingerprints",
        "_enumerate_unknown_vms",
        "_classify_unreachable",
    )

    def test_phase39_helpers_no_continue(self) -> None:
        """Each helper named in PHASE_39_NEW_HELPERS has zero ``ast.Continue``
        nodes (D-11(b))."""
        src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
        source = (src_root / "drift_detection.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename="drift_detection.py")

        for helper_name in self.PHASE_39_NEW_HELPERS:
            target = next(
                (
                    n
                    for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == helper_name
                ),
                None,
            )
            assert target is not None, f"Phase 39 D-11: helper {helper_name!r} not found in drift_detection.py"
            violations = [n.lineno for n in ast.walk(target) if isinstance(n, ast.Continue)]
            assert not violations, (
                f"Phase 39 D-11 regression — `continue` in {helper_name} at "
                f"line(s): {violations}. Recommended: refactor to comprehension "
                f"or early-return."
            )

    def test_phase381_d15_still_green(self) -> None:
        """D-12 sibling guard: re-asserts the Phase 38.1 D-15 invariant locally
        so a Phase 39 row-loop edit can't slip a ``continue`` past the existing
        ``test_scan_drift_no_continue_in_row_loop_phase38_1`` check.
        """
        src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
        source = (src_root / "drift_detection.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename="drift_detection.py")

        target = next(
            (
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == "scan_drift"
            ),
            None,
        )
        assert target is not None, "Phase 39 D-12: scan_drift not found"

        row_loops = [
            n
            for n in ast.walk(target)
            if isinstance(n, ast.For) and isinstance(n.target, ast.Name) and n.target.id == "row"
        ]
        assert len(row_loops) == 1, (
            f"Phase 39 D-12: expected one `for row in rows:` loop in scan_drift, found {len(row_loops)}"
        )
        violations = [n.lineno for n in ast.walk(row_loops[0]) if isinstance(n, ast.Continue)]
        assert not violations, (
            f"Phase 39 D-12 regression — `continue` slipped into scan_drift's row loop at line(s): {violations}"
        )


class TestPhase41_1KeyringHygiene:
    """Phase 41.1 SC-2: any test that calls ``store_credential`` or
    ``register_credential`` outside the audited allowlist fails CI.

    The session-autouse ``_isolate_keyring`` fixture in
    ``tests/conftest.py`` (Plan 02 / Wave 1) is the load-bearing safety
    net — it installs an in-memory keyring backend AND redirects
    ``_REGISTRY_PATH`` for the entire session, so most callers do not
    need per-test monkeypatching. The allowlist below documents which
    test files were AUDITED in Phase 41.1 and confirmed safe under the
    session fixture.

    A new test that calls ``store_credential`` or ``register_credential``
    must be either:
      1. Added to the allowlist with a one-line comment explaining why
         the session-autouse fixture is sufficient (default case), OR
      2. Refactored to use ``mocker.patch("keyring.set_password", ...)``
         per-test (the existing ``tests/test_credential_store.py``
         pattern) and any per-test ``_REGISTRY_PATH`` redirect must use
         the dual-alias form.

    Scope (per threat model T-41.1-02 — precise carve-out):
      * Covers ONLY direct ``store_credential(...)`` and
        ``register_credential(...)`` Name-bound calls under ``tests/``.
      * ``getattr(...)``-indirected calls and aliased imports are
        BLOCKED by the canonical-name pin in
        ``test_guarded_symbols_not_aliased_in_tests``.
      * The two read-only helpers (``find_credential_by_id``,
        ``list_credentials``, etc.) are NOT in scope — they do not
        write to the keyring or registry (RESEARCH §Open Question 3).
      * Eager-binding via ``from keyring import set_password`` is
        BLOCKED by ``test_no_eager_keyring_function_imports``
        (RESEARCH §Pitfall 4 — eager binding defeats the session
        fixture's Layer 2 monkeypatch).

    Threat model T-41.1-02 mitigation: deny-by-default. Allowlist
    entries must cite a fixture path or CONTEXT decision. New entries
    require explicit Phase 41.1 audit.
    """

    # Symbols that WRITE to the keyring or registry. Read-only helpers
    # (find_credential_by_id, list_credentials, get_credential, etc.)
    # are intentionally NOT included — they cannot leak.
    _GUARDED_SYMBOLS = ("store_credential", "register_credential")

    # Test files audited in Phase 41.1 and confirmed safe under the
    # session-autouse ``_isolate_keyring`` fixture installed in
    # ``tests/conftest.py``.
    #
    # Each entry is the path RELATIVE TO THE REPO ROOT in posix form
    # (use ``Path.as_posix()`` for the comparison key — this works on
    # Windows + macOS + Linux without backslash drama).
    #
    # To add a new entry: confirm the file is covered by the session
    # fixture (default), then add the path with a one-line citation
    # comment. CI fails if a non-allowlisted file calls a guarded
    # symbol.
    _ALLOWLIST: frozenset[str] = frozenset(
        {
            # Owns the session-autouse fixture itself; safe by definition.
            "tests/conftest.py",
            # Uses mocker.patch + per-test _REGISTRY_PATH dual-alias
            # redirect (existing pattern from v1.6 Phase 33).
            "tests/test_credential_store.py",
            # Phase 38.1 integration round-trip — already has dual-alias
            # _REGISTRY_PATH + per-test keyring monkeypatch in
            # _setup_isolated_environment (lines 48-90). Belt-and-braces
            # under the session fixture.
            "tests/integration/test_credential_binding_round_trip.py",
            # Phase 41.1 Plan 02 fixed the test_R3 path (lines 947-952)
            # to use dual-alias _REGISTRY_PATH; runs under session fixture.
            "tests/test_sitemap.py",
            # CLI coverage — calls server.store_credential indirectly via
            # _cmd_credentials_add; covered by session-autouse fixture.
            "tests/test_credentials_cli.py",
            # Phase 41.1 SC-3 regression pin — drives register_credential
            # ("test-host", "test-user") through the dual-alias-fixed call
            # site to verify the leak is closed. Covered by session fixture.
            "tests/test_keyring_isolation_phase41_1.py",
        }
    )

    def test_no_unprotected_credential_writes_in_tests(self) -> None:
        """Phase 41.1 SC-2: every direct call to a guarded symbol under
        ``tests/`` must be in an allowlisted file.
        """
        tests_root = Path(__file__).parent
        repo_root = tests_root.parent
        violations: list[str] = []

        for py_file in sorted(tests_root.rglob("*.py")):
            rel = py_file.relative_to(repo_root).as_posix()
            if rel in self._ALLOWLIST:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
            except OSError:
                continue
            try:
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                # Skip files that genuinely fail to parse — the broader
                # test suite covers syntax validation.
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in self._GUARDED_SYMBOLS
                ):
                    violations.append(f"{rel}:{node.lineno} — {node.func.id}(...) in non-allowlisted file")

        assert not violations, (
            "Phase 41.1 SC-2: unprotected store_credential / "
            "register_credential call sites in tests/. The session-"
            "autouse fixture in tests/conftest.py covers most callers, "
            "but each new test file must be explicitly added to the "
            "allowlist in TestPhase41_1KeyringHygiene._ALLOWLIST with "
            "a one-line comment explaining why the session fixture is "
            "sufficient. If a per-test monkeypatch is required, follow "
            "the dual-alias pattern from "
            "tests/integration/test_credential_binding_round_trip.py:"
            "62-65.\n\nViolations:\n  " + "\n  ".join(violations)
        )

    def test_no_eager_keyring_function_imports(self) -> None:
        """Phase 41.1 SC-2 + RESEARCH §Pitfall 4: forbid
        ``from keyring import set_password`` / ``get_password`` /
        ``delete_password`` in ``tests/``. Eager binding captures the
        function reference at import time, BEFORE the session-autouse
        ``_isolate_keyring`` fixture's Layer 2 monkeypatch runs —
        silently leaking writes to the real OS keyring.

        Production code is exempt — it does ``import keyring`` lazy
        inside function bodies (``credential_store.py:58``) and
        accesses ``keyring.set_password`` via attribute lookup, which
        the monkeypatch covers.
        """
        tests_root = Path(__file__).parent
        repo_root = tests_root.parent
        forbidden = {"set_password", "get_password", "delete_password"}
        violations: list[str] = []

        for py_file in sorted(tests_root.rglob("*.py")):
            rel = py_file.relative_to(repo_root).as_posix()
            try:
                source = py_file.read_text(encoding="utf-8")
            except OSError:
                continue
            try:
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and (node.module or "") == "keyring":
                    for alias in node.names:
                        if alias.name in forbidden:
                            violations.append(f"{rel}:{node.lineno} — from keyring import {alias.name}")

        assert not violations, (
            "Phase 41.1 SC-2 + RESEARCH §Pitfall 4: eager-bound keyring "
            "imports defeat the session fixture. Use lazy imports "
            "(``import keyring`` inside the function body, then "
            "``keyring.set_password(...)``) so the monkeypatch covers "
            "the call.\n\nViolations:\n  " + "\n  ".join(violations)
        )

    def test_guarded_symbols_not_aliased_in_tests(self) -> None:
        """Phase 41.1 SC-2 + RESEARCH WR-03: forbid aliasing of
        ``store_credential`` and ``register_credential`` on import in
        ``tests/``. The AST guard above keys on
        ``func.id == "<symbol>"``, so aliasing
        (``from homelab_mcp.credential_store import store_credential
        as foo``) silently bypasses the guard.
        """
        tests_root = Path(__file__).parent
        repo_root = tests_root.parent
        violations: list[str] = []

        for py_file in sorted(tests_root.rglob("*.py")):
            rel = py_file.relative_to(repo_root).as_posix()
            try:
                source = py_file.read_text(encoding="utf-8")
            except OSError:
                continue
            try:
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("credential_store"):
                    for alias in node.names:
                        if alias.name in self._GUARDED_SYMBOLS and alias.asname is not None:
                            violations.append(
                                f"{rel}:{node.lineno} — from ...credential_store import {alias.name} as {alias.asname}"
                            )

        assert not violations, (
            "Phase 41.1 SC-2 + RESEARCH WR-03: aliased imports of "
            "store_credential/register_credential bypass the AST guard "
            "(it keys on func.id, which sees the alias). Remove the "
            "``as <other>`` from the import.\n\nViolations:\n  " + "\n  ".join(violations)
        )

    def test_phase41_1_guard_call_site_floor(self) -> None:
        """Defensive sanity check: the guard ENUMERATES at least one
        guarded-symbol call across the allowlist files. If the count
        drops to zero, the entire credential test suite has been gutted
        and the guard is vacuous — fail loudly so a future refactor
        cannot silently weaken coverage.
        """
        tests_root = Path(__file__).parent
        repo_root = tests_root.parent
        total_calls = 0

        for py_file in sorted(tests_root.rglob("*.py")):
            rel = py_file.relative_to(repo_root).as_posix()
            if rel not in self._ALLOWLIST:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
            except OSError:
                continue
            try:
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in self._GUARDED_SYMBOLS
                ):
                    total_calls += 1

        assert total_calls >= 1, (
            "Phase 41.1 guard floor: zero store_credential / "
            "register_credential calls found across the allowlist files "
            f"({sorted(self._ALLOWLIST)}). Either the credential test "
            "suite has been deleted (legitimate consolidation — update "
            "this floor) or the allowlist no longer reflects reality "
            "(stale entries — audit and trim)."
        )


class TestPhase41BindingAwareResolver:
    """Phase 41 SC-4: discover_and_store and drift's _probe_one BOTH call
    the shared row-binding-aware helper resolve_ssh_for_sitemap_row.

    RED in Wave 0 (xfail strict), flips GREEN when Plans 02-04 land.
    A future regression that drops one of the call sites or aliases the
    import re-RED's the test.

    Three checks (mirror TestPhase41_1KeyringHygiene + TestPhase39_1NoSkipInDriftEnum):
      1. test_resolve_ssh_for_sitemap_row_helper_exists — the new symbol
         exists in src/homelab_mcp/ssh_tools.py.
      2. test_shared_helper_used_by_both_call_sites — both sitemap.py and
         drift_detection.py have at least one direct call to the helper
         under its canonical name (no `as` aliasing).
      3. test_no_unguarded_resolve_ssh_credentials_in_call_chain — direct
         calls to resolve_ssh_credentials in sitemap.py / drift_detection.py
         must be on the allowlist (intentional bypass) or zero — the
         post-fix invariant is "go through the new helper, not the
         underlying resolver."

    Pitfall 5 (function-rename gotcha): the AST guards key on the
    IMPLEMENTATION symbol names (`discover_and_store`, `_probe_one`) NOT
    the MCP tool names (`discover_and_map`, `scan_infrastructure_drift`).
    A future refactor that renames the implementation symbols must
    update this guard.
    """

    _SCANNED_FILES = ("sitemap.py", "drift_detection.py")
    _RESOLVER_CALLS_ALLOWLIST: frozenset[tuple[str, str]] = frozenset()
    # Phase 41 audit (post-Plan-04): zero direct resolve_ssh_credentials(...)
    # call sites in sitemap.py or drift_detection.py. The shared
    # resolve_ssh_for_sitemap_row helper is the only path. Empty allowlist
    # = strongest invariant; any future direct call fails the guard.

    def test_resolve_ssh_for_sitemap_row_helper_exists(self) -> None:
        """Phase 41 Bug AA: ssh_tools.py must define resolve_ssh_for_sitemap_row."""
        src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
        source = (src_root / "ssh_tools.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename="ssh_tools.py")
        targets = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == "resolve_ssh_for_sitemap_row"
        ]
        assert targets, (
            "Phase 41 Bug AA: src/homelab_mcp/ssh_tools.py must define "
            "function resolve_ssh_for_sitemap_row — the shared row-binding-"
            "aware credential resolver. RESEARCH §Pattern 1 (lines 175-240) "
            "is the proposed signature."
        )

    def test_shared_helper_used_by_both_call_sites(self) -> None:
        """Phase 41 Bug AA + V: both sitemap.py and drift_detection.py must
        call resolve_ssh_for_sitemap_row under its canonical name (no aliasing).
        """
        src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
        per_file_calls: dict[str, int] = {}
        for fname in self._SCANNED_FILES:
            source = (src_root / fname).read_text(encoding="utf-8")
            tree = ast.parse(source, filename=fname)
            # WR-03 / Phase 39.1 pattern: pin canonical name to defeat aliasing.
            imports = [
                a
                for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom) and (n.module or "").endswith("ssh_tools")
                for a in n.names
                if a.name == "resolve_ssh_for_sitemap_row"
            ]
            if imports:
                assert all(a.asname is None for a in imports), (
                    f"Phase 41 guard (canonical-name pin): {fname} imports "
                    f"resolve_ssh_for_sitemap_row under an alias; aliasing "
                    f"defeats the ast.Name match below. Drop the alias."
                )
            calls = [
                n
                for n in ast.walk(tree)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id == "resolve_ssh_for_sitemap_row"
            ]
            per_file_calls[fname] = len(calls)
        missing = [f for f, c in per_file_calls.items() if c == 0]
        assert not missing, (
            f"Phase 41 Bug AA + V: resolve_ssh_for_sitemap_row not called in "
            f"{missing}. Each of {list(self._SCANNED_FILES)} must call the "
            f"shared helper at least once. Per-file call counts: {per_file_calls}."
        )
        assert sum(per_file_calls.values()) >= 2, (
            f"Phase 41 call-site floor: expected >= 2 total call sites "
            f"(at least one per file), found {sum(per_file_calls.values())}. "
            f"If a refactor consolidated to a helper, update this floor."
        )

    def test_no_unguarded_resolve_ssh_credentials_in_call_chain(self) -> None:
        """Phase 41 Bug AA: no unguarded direct resolve_ssh_credentials calls
        in sitemap.py or drift_detection.py — these must go through the helper.
        """
        src_root = Path(__file__).parent.parent / "src" / "homelab_mcp"
        violations: list[str] = []
        for fname in self._SCANNED_FILES:
            source = (src_root / fname).read_text(encoding="utf-8")
            tree = ast.parse(source, filename=fname)
            # Build line-number → enclosing function name lookup so allowlist
            # entries can name the function (more readable than raw line
            # numbers, more stable across small refactors).
            line_to_func: dict[int, str] = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    start = node.lineno
                    end = getattr(node, "end_lineno", start) or start
                    for ln in range(start, end + 1):
                        # Inner functions overwrite outer; we want the most-specific scope.
                        line_to_func[ln] = node.name
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "resolve_ssh_credentials"
                ):
                    enclosing = line_to_func.get(node.lineno, "<module>")
                    key = (fname, enclosing)
                    if key in self._RESOLVER_CALLS_ALLOWLIST:
                        continue
                    violations.append(
                        f"{fname}:{node.lineno} (in {enclosing}) — "
                        f"direct resolve_ssh_credentials(...) call (use "
                        f"resolve_ssh_for_sitemap_row instead, or add "
                        f"{(fname, enclosing)!r} to _RESOLVER_CALLS_ALLOWLIST "
                        f"with a one-line justification)"
                    )
        assert not violations, (
            "Phase 41 Bug AA shared-helper invariant: direct "
            "resolve_ssh_credentials(...) calls in the discover/drift "
            "call chain. Replace with resolve_ssh_for_sitemap_row, OR "
            "if a legitimate bypass is required (e.g., a non-row-scoped "
            "auth helper), add (filename, enclosing_function) to "
            "_RESOLVER_CALLS_ALLOWLIST with a one-line justification "
            "comment.\n\nViolations:\n  " + "\n  ".join(violations)
        )
