"""Phase 40 Plan 02 Task 2 regression tests: openapi_app INFRA_REQUIREMENTS Proxmox entry.

D-05 ripple: rewrite INFRA_REQUIREMENTS["Proxmox"] to mirror the Phase 37 D-08
"Drift Detection" entry — point at the credentials-add CLI, drop PROXMOX_HOST
and the deprecated POST /api/tools/register_server pointer.
"""

from __future__ import annotations

from pathlib import Path

from homelab_mcp.openapi_app import INFRA_REQUIREMENTS

CREDENTIALS_CLI_LITERAL = "homelab-mcp credentials add --type proxmox"
CLUSTER_SCOPE_LITERAL = "--scope cluster:"


class TestInfraRequirementsProxmoxEntry:
    """D-05 ripple: Proxmox entry rewritten to mirror Drift Detection phrasing."""

    def test_proxmox_entry_references_credentials_cli(self) -> None:
        value = INFRA_REQUIREMENTS["Proxmox"]
        assert CREDENTIALS_CLI_LITERAL in value, (
            f"D-05 regression: INFRA_REQUIREMENTS['Proxmox'] does not reference "
            f"{CREDENTIALS_CLI_LITERAL!r}; got {value!r}"
        )

    def test_proxmox_entry_advertises_cluster_scope(self) -> None:
        value = INFRA_REQUIREMENTS["Proxmox"]
        assert CLUSTER_SCOPE_LITERAL in value, (
            f"D-05 regression: INFRA_REQUIREMENTS['Proxmox'] does not advertise "
            f"{CLUSTER_SCOPE_LITERAL!r}; got {value!r}"
        )

    def test_proxmox_entry_no_proxmox_host(self) -> None:
        value = INFRA_REQUIREMENTS["Proxmox"]
        assert "PROXMOX_HOST" not in value, (
            f"D-05 regression: INFRA_REQUIREMENTS['Proxmox'] still mentions "
            f"PROXMOX_HOST; got {value!r}"
        )

    def test_proxmox_entry_no_register_server_pointer(self) -> None:
        value = INFRA_REQUIREMENTS["Proxmox"]
        assert "POST /api/tools/register_server" not in value, (
            "D-05 regression: INFRA_REQUIREMENTS['Proxmox'] still references the "
            f"deprecated POST /api/tools/register_server endpoint; got {value!r}"
        )

    def test_drift_detection_entry_unchanged(self) -> None:
        """Sibling guard: Drift Detection entry must remain the canonical phrase."""
        drift = INFRA_REQUIREMENTS["Drift Detection"]
        # Phase 37 D-08 phrasing — sanity-check structural substrings only.
        assert CREDENTIALS_CLI_LITERAL in drift
        assert "discover_and_map" in drift
        assert "PROXMOX_HOST" not in drift

    def test_openapi_app_file_no_proxmox_host(self) -> None:
        """File-level sweep: zero PROXMOX_HOST substrings in openapi_app.py."""
        openapi_path = (
            Path(__file__).parent.parent
            / "src"
            / "homelab_mcp"
            / "openapi_app.py"
        )
        assert openapi_path.exists(), f"file missing: {openapi_path}"
        source = openapi_path.read_text(encoding="utf-8")
        assert "PROXMOX_HOST" not in source, (
            "D-05 regression: PROXMOX_HOST substring present in openapi_app.py — "
            "the Proxmox entry rewrite should have removed it."
        )
