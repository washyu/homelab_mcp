"""Wave 0 test scaffold for Phase 13: drift resource (DRFT-07, DRFT-08, DRFT-09, DRFT-10).

These tests are intentionally RED at commit time. They define the contract that
Plan 02 will implement. The only GREEN test is test_drift_resource_uri_roundtrip,
which depends only on pydantic (already installed).
"""

# pydantic is already installed — module-level import is safe here
from pydantic import AnyUrl


def test_drift_resource_registered() -> None:
    """DRFT-07: homelab://drift/latest is registered in HOMELAB_RESOURCES.

    Will be RED until Plan 02 adds the entry to server.py.
    """
    from homelab_mcp.server import HOMELAB_RESOURCES  # type: ignore[attr-defined]

    assert "homelab://drift/latest" in HOMELAB_RESOURCES
    entry = HOMELAB_RESOURCES["homelab://drift/latest"]
    assert "name" in entry
    assert "description" in entry


def test_drift_resource_empty_state() -> None:
    """DRFT-08: read_drift_resource() returns {"drift_detected": None} before any scan.

    Will be RED until Plan 02 adds read_drift_resource to resource_readers.py.
    """
    import asyncio

    from homelab_mcp.resource_readers import read_drift_resource  # type: ignore[import]
    from homelab_mcp.server import set_latest_drift_report  # type: ignore[attr-defined]

    # Clear any prior state from a previous test
    set_latest_drift_report(None)  # type: ignore[arg-type]

    result = asyncio.run(read_drift_resource())
    assert result == {"drift_detected": None}


def test_drift_resource_after_scan() -> None:
    """DRFT-08: read_drift_resource() returns the report set via set_latest_drift_report.

    Will be RED until Plan 02 adds both set_latest_drift_report and read_drift_resource.
    """
    import asyncio

    from homelab_mcp.resource_readers import read_drift_resource  # type: ignore[import]
    from homelab_mcp.server import set_latest_drift_report  # type: ignore[attr-defined]

    sample_report = {
        "drift_detected": True,
        "drifted_vms": [],
        "scanned_at": "2026-01-01T00:00:00",
    }

    set_latest_drift_report(sample_report)
    try:
        result = asyncio.run(read_drift_resource())
        assert result == sample_report
    finally:
        # Reset state so other tests are not affected
        set_latest_drift_report(None)  # type: ignore[arg-type]


def test_drift_resource_notification() -> None:
    """DRFT-10: scan_infrastructure_drift is in DRIFT_SCAN_TOOLS frozenset.

    This verifies the notification wiring constant is declared (Plan 02 will add it).
    Full notification integration is verified by manual MCP client test per
    13-VALIDATION.md.

    Will be RED until Plan 02 declares DRIFT_SCAN_TOOLS in server.py.
    """
    from homelab_mcp.server import DRIFT_SCAN_TOOLS  # type: ignore[attr-defined]

    assert "scan_infrastructure_drift" in DRIFT_SCAN_TOOLS


def test_drift_resource_uri_roundtrip() -> None:
    """DRFT-09: pydantic AnyUrl does not normalise homelab:// URIs unexpectedly.

    This test is GREEN at Wave 0 — it depends only on pydantic, which is already
    installed. It confirms no URI normalisation surprises before Plan 02 uses
    AnyUrl("homelab://drift/latest") in send_resource_updated calls.
    """
    uri = AnyUrl("homelab://drift/latest")
    assert str(uri) == "homelab://drift/latest"
