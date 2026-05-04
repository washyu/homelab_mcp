"""Phase 40 Plan 02 regression tests: Proxmox tools schema (POL-02 D-03 + D-05).

Asserts:
  - `create_proxmox_vm` schema requires `host` (POL-02 D-03)
  - `create_proxmox_vm.host.description` points at the credentials-add CLI and
    advertises the `--scope cluster:` cluster-token form
  - Zero `PROXMOX_HOST` substrings remain anywhere in
    `tool_schemas/proxmox_tools_schema.py` (D-05 sweep)
  - Each tool whose description was rewritten by the sweep
    (`list_proxmox_resources`, `get_proxmox_node_status`, `get_proxmox_vm_status`)
    points at the credentials-add CLI in its host property's description
"""

from __future__ import annotations

from pathlib import Path

from homelab_mcp.tool_schemas.proxmox_tools_schema import PROXMOX_TOOLS

CREDENTIALS_CLI_LITERAL = "homelab-mcp credentials add --type proxmox"
CLUSTER_SCOPE_LITERAL = "--scope cluster:"


class TestCreateProxmoxVmRequiresHost:
    """POL-02 D-03: create_proxmox_vm declares host required."""

    def test_host_in_required_list(self) -> None:
        required = PROXMOX_TOOLS["create_proxmox_vm"]["inputSchema"]["required"]
        assert "host" in required, (
            f"POL-02 D-03 regression: create_proxmox_vm.required missing 'host'; got {required!r}"
        )

    def test_required_order(self) -> None:
        required = PROXMOX_TOOLS["create_proxmox_vm"]["inputSchema"]["required"]
        assert required == ["node", "vmid", "name", "host"], (
            f"POL-02 D-03: required order should be node, vmid, name, host; got {required!r}"
        )

    def test_host_description_points_at_credentials_cli(self) -> None:
        desc = PROXMOX_TOOLS["create_proxmox_vm"]["inputSchema"]["properties"]["host"]["description"]
        assert CREDENTIALS_CLI_LITERAL in desc, (
            f"POL-02 D-03 regression: create_proxmox_vm.host.description does not "
            f"reference {CREDENTIALS_CLI_LITERAL!r}; got {desc!r}"
        )

    def test_host_description_advertises_cluster_scope(self) -> None:
        desc = PROXMOX_TOOLS["create_proxmox_vm"]["inputSchema"]["properties"]["host"]["description"]
        assert CLUSTER_SCOPE_LITERAL in desc, (
            f"POL-02 D-03 regression: create_proxmox_vm.host.description does not "
            f"advertise {CLUSTER_SCOPE_LITERAL!r}; got {desc!r}"
        )


class TestProxmoxHostSweep:
    """D-05: zero PROXMOX_HOST substrings remain in proxmox_tools_schema.py."""

    def test_no_proxmox_host_in_schema_file(self) -> None:
        schema_path = Path(__file__).parent.parent / "src" / "homelab_mcp" / "tool_schemas" / "proxmox_tools_schema.py"
        assert schema_path.exists(), f"schema file missing: {schema_path}"
        source = schema_path.read_text(encoding="utf-8")
        assert "PROXMOX_HOST" not in source, (
            "D-05 regression: PROXMOX_HOST substring reintroduced in "
            "tool_schemas/proxmox_tools_schema.py — every host-bearing tool "
            f"description must reference {CREDENTIALS_CLI_LITERAL!r} instead."
        )

    def test_list_proxmox_resources_tool_description_no_env_var(self) -> None:
        desc = PROXMOX_TOOLS["list_proxmox_resources"]["description"]
        assert "PROXMOX_HOST" not in desc, (
            f"D-05 regression: list_proxmox_resources tool description still mentions PROXMOX_HOST; got {desc!r}"
        )

    def test_swept_host_descriptions_point_at_credentials_cli(self) -> None:
        """D-05: every swept tool's host property description references the CLI."""
        target_tools = (
            "list_proxmox_resources",
            "get_proxmox_node_status",
            "get_proxmox_vm_status",
        )
        violations: list[str] = []
        for tool in target_tools:
            host_props = PROXMOX_TOOLS[tool]["inputSchema"]["properties"].get("host")
            if host_props is None:
                violations.append(f"{tool}: host property missing")
                continue
            desc = host_props.get("description", "")
            if "PROXMOX_HOST" in desc:
                violations.append(f"{tool}: host description still contains PROXMOX_HOST: {desc!r}")
            if CREDENTIALS_CLI_LITERAL not in desc:
                violations.append(f"{tool}: host description does not reference {CREDENTIALS_CLI_LITERAL!r}: {desc!r}")
        assert not violations, "D-05 regression — swept host descriptions:\n" + "\n".join(
            f"  - {v}" for v in violations
        )

    def test_credentials_cli_literal_count_at_least_four(self) -> None:
        """D-05: file should contain at least 4 credentials-add CLI references.

        create_proxmox_vm.host + 3 swept tool host descriptions = 4 minimum.
        """
        schema_path = Path(__file__).parent.parent / "src" / "homelab_mcp" / "tool_schemas" / "proxmox_tools_schema.py"
        source = schema_path.read_text(encoding="utf-8")
        count = source.count(CREDENTIALS_CLI_LITERAL)
        assert count >= 4, (
            f"D-05 regression: expected ≥ 4 occurrences of {CREDENTIALS_CLI_LITERAL!r} "
            f"in proxmox_tools_schema.py; found {count}"
        )
