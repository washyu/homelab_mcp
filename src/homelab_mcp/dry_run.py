"""Shared dry-run response contract builder (DRY-07)."""

from typing import Any


def build_dry_run_response(
    tool_name: str,
    would_affect: list[dict[str, Any]],
    risk_level: str,
    reversible: bool,
    preview_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the standard dry-run response contract.

    Args:
        tool_name: Name of the tool that would execute.
        would_affect: List of resource descriptors that would be affected.
        risk_level: One of "high", "medium", or "low".
        reversible: Whether the operation can be undone.
        preview_details: Optional dict merged under the "preview" key.

    Returns:
        A dict with mode="dry_run" and all required contract fields.
    """
    response: dict[str, Any] = {
        "mode": "dry_run",
        "tool": tool_name,
        "would_affect": would_affect,
        "risk_level": risk_level,
        "reversible": reversible,
    }
    if preview_details is not None:
        response["preview"] = preview_details
    return response
