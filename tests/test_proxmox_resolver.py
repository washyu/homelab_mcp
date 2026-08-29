"""
Tests for resolve_proxmox_credentials — Phase 34 Plan 02 (D-13 through D-16).

Seven tests covering two-tier resolution, short-circuit on per-node match,
cluster walk, cache hits, error messages, debug-log tier trace, and desync warnings.
"""

import logging
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, patch

import aiohttp
import pytest

from homelab_mcp.proxmox_api import _HOST_CLUSTER_CACHE, resolve_proxmox_credentials
from homelab_mcp.ssh_tools import CredentialNotFoundError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Clear the module-level host→cluster cache before and after every test."""
    _HOST_CLUSTER_CACHE.clear()
    yield  # type: ignore[misc]
    _HOST_CLUSTER_CACHE.clear()


# ---------------------------------------------------------------------------
# Helper: stub the /cluster/status probe
# ---------------------------------------------------------------------------


class _ProbeRecorder:
    """Serves queued /cluster/status results and records each probe.

    Replaces aioresponses, which cannot be used here: 0.7.9 is the latest
    release and it breaks on aiohttp 3.14's ClientResponse signature, which
    pinned the project below 3.14 and held 27 advisories open.

    Patching ProxmoxAPIClient.get is also a better seam than the wire layer --
    it is the resolver's actual dependency, and unlike a URL matcher it can see
    which candidate token each probe was made with.
    """

    def __init__(self, results: list[Any]) -> None:
        self._results = list(results)
        self.probes: list[tuple[str, str, str | None]] = []

    def record(self, client: Any, endpoint: str) -> Any:
        self.probes.append((client.host, endpoint, client.api_token))
        if not self._results:
            raise AssertionError(f"Unexpected probe #{len(self.probes)} to {endpoint} — no queued result")
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    @property
    def call_count(self) -> int:
        return len(self.probes)


@contextmanager
def _probe(*results: Any):
    """Patch ProxmoxAPIClient.get with a queue of results, one per probe.

    Each result is either a value to return or an exception to raise, letting a
    test express "first candidate 401s, second succeeds" in order.
    """
    recorder = _ProbeRecorder(list(results))

    # Must be a real function, not a callable instance: only functions
    # implement the descriptor protocol, so only they get `self` bound when
    # patched onto a class.
    async def _fake_get(self: Any, endpoint: str, params: Any = None) -> Any:
        return recorder.record(self, endpoint)

    with patch("homelab_mcp.proxmox_api.ProxmoxAPIClient.get", _fake_get):
        yield recorder


def _cluster_status(node: str, cluster: str | None = None) -> list[dict[str, str]]:
    """Build a /cluster/status payload as ProxmoxAPIClient.get returns it.

    The client strips the "data" wrapper, so the resolver sees the list directly.
    """
    rows = [{"type": "node", "name": node}]
    if cluster is not None:
        rows.append({"type": "cluster", "name": cluster})
    return rows


def _unauthorized() -> aiohttp.ClientResponseError:
    """A 401 shaped the way the resolver's except clause expects.

    request_info must not be None: the resolver logs the error, and
    ClientResponseError.__str__ dereferences request_info.real_url.
    """
    return aiohttp.ClientResponseError(request_info=MagicMock(), history=(), status=401, message="Unauthorized")


# ---------------------------------------------------------------------------
# Helper: registry entry factories
# ---------------------------------------------------------------------------


def _node_entry(hostname: str, username: str) -> dict[str, str]:
    return {
        "hostname": hostname,
        "username": username,
        "credential_type": "proxmox",
        "auth_type": "password",
        "scope": "node",
        "cluster_name": "",
    }


def _cluster_entry(cluster_name: str, username: str) -> dict[str, str]:
    return {
        "hostname": "",
        "username": username,
        "credential_type": "proxmox",
        "auth_type": "password",
        "scope": "cluster",
        "cluster_name": cluster_name,
    }


# ---------------------------------------------------------------------------
# Test 1 (D-13): cluster-only match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("homelab_mcp.proxmox_api.get_credential")
@patch("homelab_mcp.proxmox_api.list_credentials")
async def test_resolver_cluster_only_match(
    mock_list_creds: object,
    mock_get_cred: object,
) -> None:
    """D-13: No per-node entry; one cluster entry; /cluster/status confirms cluster match."""
    mock_list_creds.return_value = [  # type: ignore[attr-defined]
        _cluster_entry("homelab-prod", "root@pam!clustertok"),
    ]
    # get_credential returns different secrets depending on call signature;
    # cluster scope call uses scope="cluster", cluster_name="homelab-prod"
    mock_get_cred.return_value = "secret-uuid-abc"  # type: ignore[attr-defined]

    with _probe(_cluster_status("pve1.home", "homelab-prod")) as probe:
        result = await resolve_proxmox_credentials("pve1.home")

    assert probe.probes == [("pve1.home", "/cluster/status", "root@pam!clustertok=secret-uuid-abc")]

    api_token, scope, cluster_name = result
    assert scope == "cluster"
    assert cluster_name == "homelab-prod"
    assert api_token == "root@pam!clustertok=secret-uuid-abc"


# ---------------------------------------------------------------------------
# Test 2 (D-14): per-node entry short-circuits; /cluster/status NEVER called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("homelab_mcp.proxmox_api.get_credential")
@patch("homelab_mcp.proxmox_api.list_credentials")
async def test_resolver_per_node_overrides_cluster_no_probe(
    mock_list_creds: object,
    mock_get_cred: object,
) -> None:
    """D-14: Per-node entry exists → node token returned; /cluster/status NEVER requested."""
    mock_list_creds.return_value = [  # type: ignore[attr-defined]
        _node_entry("pve1.home", "root@pam!nodetok"),
        _cluster_entry("homelab-prod", "root@pam!clustertok"),
    ]
    mock_get_cred.return_value = "node-secret"  # type: ignore[attr-defined]

    with _probe() as probe:
        result = await resolve_proxmox_credentials("pve1.home")

    # /cluster/status must NEVER have been called
    assert probe.call_count == 0, "Expected zero HTTP requests (per-node short-circuit)"

    api_token, scope, cluster_name = result
    assert scope == "node"
    assert cluster_name is None
    assert api_token == "root@pam!nodetok=node-secret"


# ---------------------------------------------------------------------------
# Test 3 (D-15): standalone node — /cluster/status returns no cluster row → error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("homelab_mcp.proxmox_api.get_credential")
@patch("homelab_mcp.proxmox_api.list_credentials")
async def test_resolver_standalone_node_raises_with_actionable_message(
    mock_list_creds: object,
    mock_get_cred: object,
) -> None:
    """D-15: No cluster row in /cluster/status → CredentialNotFoundError with actionable message."""
    mock_list_creds.return_value = [  # type: ignore[attr-defined]
        _cluster_entry("homelab-prod", "root@pam!tok"),
    ]
    mock_get_cred.return_value = "some-secret"  # type: ignore[attr-defined]

    with _probe(_cluster_status("pve-standalone")):
        with pytest.raises(CredentialNotFoundError) as exc_info:
            await resolve_proxmox_credentials("pve-standalone")

    error_msg = str(exc_info.value)
    assert "pve-standalone" in error_msg
    assert "homelab-prod" in error_msg
    assert "credentials add --type proxmox" in error_msg


# ---------------------------------------------------------------------------
# Test 4 (D-05b): multi-cluster walk — first auth error skipped, second wins
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("homelab_mcp.proxmox_api.get_credential")
@patch("homelab_mcp.proxmox_api.list_credentials")
async def test_resolver_multi_cluster_first_match_wins(
    mock_list_creds: object,
    mock_get_cred: object,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """D-05b: Two cluster entries; first gets 401 (skipped at DEBUG), second matches."""
    mock_list_creds.return_value = [  # type: ignore[attr-defined]
        _cluster_entry("clusterA", "root@pam!tokA"),
        _cluster_entry("clusterB", "root@pam!tokB"),
    ]

    def _get_cred_side_effect(hostname: str, username: str, **kwargs: object) -> str:
        if kwargs.get("cluster_name") == "clusterA":
            return "secretA"
        return "secretB"

    mock_get_cred.side_effect = _get_cred_side_effect  # type: ignore[attr-defined]

    with caplog.at_level(logging.DEBUG, logger="homelab_mcp.proxmox_api"):
        # clusterA 401s and is skipped; clusterB then matches.
        with _probe(_unauthorized(), _cluster_status("pve-b1", "clusterB")) as probe:
            result = await resolve_proxmox_credentials("pve-b1")

    # Both candidates were tried, each with its own token
    assert [t for _, _, t in probe.probes] == [
        "root@pam!tokA=secretA",
        "root@pam!tokB=secretB",
    ]

    api_token, scope, cluster_name = result
    assert scope == "cluster"
    assert cluster_name == "clusterB"
    assert "tokB=secretB" in api_token

    # clusterA's error should appear in DEBUG log
    debug_msgs = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
    assert any(
        "clusterA" in msg and ("skip" in msg.lower() or "error" in msg.lower() or "fail" in msg.lower())
        for msg in debug_msgs
    ), f"Expected DEBUG log mentioning clusterA skip/error. DEBUG records: {debug_msgs}"


# ---------------------------------------------------------------------------
# Test 5 (D-05a): cache hit skips second /cluster/status probe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("homelab_mcp.proxmox_api.get_credential")
@patch("homelab_mcp.proxmox_api.list_credentials")
async def test_resolver_cache_hit_skips_probe(
    mock_list_creds: object,
    mock_get_cred: object,
) -> None:
    """D-05a: Second call for the same host uses the in-memory cache; no extra HTTP probe."""
    mock_list_creds.return_value = [  # type: ignore[attr-defined]
        _cluster_entry("homelab-prod", "root@pam!tok"),
    ]
    mock_get_cred.return_value = "cache-secret"  # type: ignore[attr-defined]

    # Only ONE queued result -- a second probe would raise from the recorder.
    with _probe(_cluster_status("pve1.home", "homelab-prod")) as probe:
        result1 = await resolve_proxmox_credentials("pve1.home")
        # Second call -- cache should be hit, no extra HTTP call
        result2 = await resolve_proxmox_credentials("pve1.home")

    assert probe.call_count == 1, "Cache hit should have avoided a second probe"

    assert result1 == result2
    assert result1[1] == "cluster"
    assert result1[2] == "homelab-prod"


# ---------------------------------------------------------------------------
# Test 6 (D-11 + SC-2): debug-log tier trace
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("homelab_mcp.proxmox_api.get_credential")
@patch("homelab_mcp.proxmox_api.list_credentials")
async def test_resolver_debug_log_tier_trace(
    mock_list_creds: object,
    mock_get_cred: object,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """D-11 + SC-2: Verify DEBUG tier log records for cluster-match (Test 1 scenario)
    and node-match (Test 2 scenario).
    """
    # ---- Scenario A: cluster match (D-13 scenario) ----
    mock_list_creds.return_value = [  # type: ignore[attr-defined]
        _cluster_entry("homelab-prod", "root@pam!clustertok"),
    ]
    mock_get_cred.return_value = "secret-for-log-test"  # type: ignore[attr-defined]

    with caplog.at_level(logging.DEBUG, logger="homelab_mcp.proxmox_api"):
        with _probe(_cluster_status("pve1.home", "homelab-prod")):
            await resolve_proxmox_credentials("pve1.home")

    records_a = [r.message for r in caplog.records]
    assert any("tier=node" in msg and "MISS" in msg for msg in records_a), (
        f"Expected 'tier=node MISS' record. Records: {records_a}"
    )
    assert any("tier=cluster" in msg for msg in records_a), f"Expected 'tier=cluster' record. Records: {records_a}"
    assert any("source=cluster" in msg for msg in records_a), (
        f"Expected terminal 'source=cluster' record. Records: {records_a}"
    )

    # ---- Scenario B: per-node short-circuit (D-14 scenario) ----
    caplog.clear()
    _HOST_CLUSTER_CACHE.clear()
    mock_list_creds.return_value = [  # type: ignore[attr-defined]
        _node_entry("pve1.home", "root@pam!nodetok"),
        _cluster_entry("homelab-prod", "root@pam!clustertok"),
    ]
    mock_get_cred.return_value = "node-secret-for-log-test"  # type: ignore[attr-defined]

    with caplog.at_level(logging.DEBUG, logger="homelab_mcp.proxmox_api"):
        with _probe():
            await resolve_proxmox_credentials("pve1.home")

    records_b = [r.message for r in caplog.records]
    assert any("source=node" in msg for msg in records_b), (
        f"Expected terminal 'source=node' record. Records: {records_b}"
    )
    assert not any("tier=cluster" in msg for msg in records_b), (
        f"Expected ZERO 'tier=cluster' records (short-circuit). Records: {records_b}"
    )


# ---------------------------------------------------------------------------
# Test 7: desync — registry entry exists but keyring returns None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("homelab_mcp.proxmox_api.get_credential")
@patch("homelab_mcp.proxmox_api.list_credentials")
async def test_resolver_desync_warning_on_missing_keyring_secret(
    mock_list_creds: object,
    mock_get_cred: object,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Desync: cluster entry in registry but keyring returns None → WARNING logged, resolver continues."""
    mock_list_creds.return_value = [  # type: ignore[attr-defined]
        _cluster_entry("homelab-prod", "root@pam!tok"),
    ]
    mock_get_cred.return_value = None  # keyring desync — secret missing  # type: ignore[attr-defined]

    with caplog.at_level(logging.WARNING, logger="homelab_mcp.proxmox_api"):
        with pytest.raises(CredentialNotFoundError):
            # The resolver must NOT raise on the desync entry itself — it logs
            # a warning and continues; eventually raises because no match found.
            await resolve_proxmox_credentials("pve-desync")

    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING and "desync" in r.message.lower()]
    assert len(warning_records) >= 1, "Expected at least one WARNING containing 'desync'"
    assert "credentials add --type proxmox --scope cluster:" in warning_records[0].message
