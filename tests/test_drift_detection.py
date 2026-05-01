"""Tests for drift detection — Phase 36/37 (sitemap-as-baseline, 4-bucket stable shape)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homelab_mcp.drift_detection import (
    _classify_unreachable,
    _diff_fingerprints,
    _enumerate_unknown_vms,
    _missing_threshold_days,
    _parse_last_seen,
    scan_drift,
)
from homelab_mcp.proxmox_api import CredentialNotFoundError
from homelab_mcp.ssh_tools import _probe_universal_core


class TestScanDrift4Bucket:
    """Phase 37 D-01/D-02/D-04/D-05/D-07/D-09/D-10: scan_drift 4-bucket envelope.

    Combines Phase 36's 2-bucket sanity tests (preserved verbatim) with Phase 37's
    envelope/filter/guidance regression tests. The class was renamed from
    TestScanDrift2Bucket to TestScanDrift4Bucket per CONTEXT Claude's Discretion
    bullet 8. Phase 36 tests cover the per-row record shape and silent-skip /
    sanitize-error / inert-filter behavior that Phase 37 D-10 explicitly preserves.
    Phase 37 tests cover the 4-bucket envelope, counts sub-dict, conditional
    guidance, and hostname filter semantics that Plan 01 shipped.
    """

    # ───────────────────────────────────────────────────────────────────────
    # Phase 36 sanity tests (preserved verbatim from TestScanDrift2Bucket)
    # ───────────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_three_row_classification(self):
        """3-row sitemap: pve1 -> probed_ok, truenas1 -> not_eligible/unbound, pi-lab -> unreachable.

        Phase 38.1 D-15/D-17 (Bug O fix): truenas1 (no proxmox creds) was
        previously silently skipped — now routes to not_eligible/unbound so
        the row stays visible to the user with a recovery pointer.
        """
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"},
            {"hostname": "truenas1", "connection_ip": "10.0.0.11", "status": "success"},
            {"hostname": "pi-lab", "connection_ip": "10.0.0.12", "status": "success"},
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            # Phase 41 Bug V: drift now dials connection_ip when set; accept both forms.
            if host in ("pve1", "10.0.0.10"):
                client = MagicMock()
                client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
                return client
            if host in ("truenas1", "10.0.0.11"):
                raise CredentialNotFoundError(f"no creds for {host}")
            if host in ("pi-lab", "10.0.0.12"):
                client = MagicMock()
                client.get = AsyncMock(side_effect=aiohttp.ClientError("connection refused to pve.home"))
                return client
            raise AssertionError(f"unexpected host: {host}")

        async def fake_resolve(host, session=None, *, credential_id=None):
            if host == "pve1":
                return ("token@node", "node", None)
            if host == "pi-lab":
                return ("token@cluster", "cluster", "homelab-prod")
            raise AssertionError(f"unexpected host: {host}")

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["status"] == "success"
        # Phase 38.1: every row lands in some bucket; no silent skips.
        assert result["scanned"] == 3
        assert len(result["probed_ok"]) == 1
        assert result["probed_ok"][0]["hostname"] == "pve1"
        assert result["probed_ok"][0]["scope"] == "node"
        assert result["probed_ok"][0]["cluster_name"] is None
        assert result["probed_ok"][0]["status"] == "probed-ok"
        assert result["probed_ok"][0]["error"] is None
        assert len(result["unreachable"]) == 1
        assert result["unreachable"][0]["hostname"] == "pi-lab"
        assert result["unreachable"][0]["scope"] == "cluster"
        assert result["unreachable"][0]["cluster_name"] == "homelab-prod"
        assert "connection refused" in result["unreachable"][0]["error"].lower()
        # Phase 38.1: truenas1 routes to not_eligible/unbound (no binding column set).
        assert len(result["not_eligible"]) == 1
        assert result["not_eligible"][0]["hostname"] == "truenas1"
        assert result["not_eligible"][0]["reason"] == "unbound"

    @pytest.mark.asyncio
    async def test_empty_sitemap_returns_success(self):
        """D-03: zero rows -> successful empty result, never an error."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = []

        result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["status"] == "success"
        assert result["scanned"] == 0
        assert result["probed_ok"] == []
        assert result["unreachable"] == []
        assert "scan_timestamp" in result

    @pytest.mark.asyncio
    async def test_degenerate_rows_excluded(self):
        """Phase 38.1 D-17: rows with status=='error' OR hostname in ('', 'unknown', None)
        route to not_eligible/degenerate (pre-resolver — get_proxmox_client never called).

        Pre-Plan-06 these rows were silently skipped (Phase 36 D-10a). Plan 06
        keeps the pre-resolver routing but lands them in the not_eligible bucket
        with reason='degenerate' so the user sees them.
        """
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "", "connection_ip": "10.0.0.1", "status": "success"},
            {"hostname": "unknown", "connection_ip": "10.0.0.2", "status": "success"},
            {"hostname": None, "connection_ip": "10.0.0.3", "status": "success"},
            {"hostname": "errored-host", "connection_ip": "10.0.0.4", "status": "error"},
        ]

        # Degenerate routing fires BEFORE the resolver — get_proxmox_client never called.
        with patch("homelab_mcp.drift_detection.get_proxmox_client") as mock_client:
            result = await scan_drift(session=None, db_adapter=db_adapter)

        mock_client.assert_not_called()
        # Phase 38.1: all 4 degenerate rows route to not_eligible/degenerate.
        assert result["scanned"] == 4
        assert result["probed_ok"] == []
        assert result["unreachable"] == []
        assert len(result["not_eligible"]) == 4
        assert all(r["reason"] == "degenerate" for r in result["not_eligible"])

    @pytest.mark.asyncio
    async def test_silent_skip_on_credential_not_found(self):
        """Phase 38.1 D-15 (Bug O fix): CredentialNotFoundError on get_proxmox_client
        routes to not_eligible bucket (no longer a silent skip).

        Pre-Plan-06 this raised silently and the row vanished from the response.
        Plan 06 routes it to not_eligible with reason classified by binding state
        — here, no proxmox_credential_id column → reason='unbound'.
        """
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "not-a-proxmox-host", "connection_ip": "10.0.0.1", "status": "success"},
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            raise CredentialNotFoundError("no proxmox creds")

        with patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        # Phase 38.1: no row vanishes; the row lands in not_eligible/unbound.
        assert result["scanned"] == 1
        assert result["probed_ok"] == []
        assert result["unreachable"] == []
        assert len(result["not_eligible"]) == 1
        assert result["not_eligible"][0]["hostname"] == "not-a-proxmox-host"
        assert result["not_eligible"][0]["reason"] == "unbound"

    @pytest.mark.asyncio
    async def test_unreachable_error_is_sanitized(self):
        """D-09a: probe exception messages pass through sanitize_error."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "leaky", "connection_ip": "10.0.0.1", "status": "success"},
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()
            # Simulate an exception that contains a "secret-looking" token
            client.get = AsyncMock(
                side_effect=aiohttp.ClientError("connection refused (token=PVEAPIToken=user@pam!id=secretsecret)")
            )
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert len(result["unreachable"]) == 1
        # The raw secret string should not appear verbatim in the sanitized error
        # (sanitize_error redacts PVEAPIToken=...)
        err = result["unreachable"][0]["error"]
        assert "secretsecret" not in err

    @pytest.mark.asyncio
    async def test_inert_filter_passthrough(self):
        """D-04: node and vm_type kwargs are accepted but inert in Phase 36."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = []

        # Pass filter args; assert they don't break or produce errors
        result = await scan_drift(session=None, db_adapter=db_adapter, node="pve1", vm_type="qemu")
        assert result["status"] == "success"

        result = await scan_drift(session=None, db_adapter=db_adapter, node=None, vm_type="all")
        assert result["status"] == "success"

    # ───────────────────────────────────────────────────────────────────────
    # Phase 37 envelope shape regression tests (D-04 / D-05 / D-06 / D-07)
    # ───────────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_envelope_has_all_four_bucket_keys(self):
        """D-04 / D-05: response always contains probed_ok, unreachable, unknown, changed keys.

        Verified across two scenarios: empty sitemap (zero rows) AND populated sitemap
        (one probed_ok row). Both responses must have ALL FOUR bucket keys. Phase 37
        clients can iterate without dict.get(..., []) defensive checks.
        """
        # Scenario 1: empty sitemap
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = []
        result_empty = await scan_drift(session=None, db_adapter=db_adapter)
        for bucket_key in ("probed_ok", "unreachable", "unknown", "changed"):
            assert bucket_key in result_empty, (
                f"empty-sitemap response missing bucket key {bucket_key!r}; keys present: {list(result_empty.keys())}"
            )

        # Scenario 2: one probed_ok row
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"},
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()
            client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result_populated = await scan_drift(session=None, db_adapter=db_adapter)

        for bucket_key in ("probed_ok", "unreachable", "unknown", "changed"):
            assert bucket_key in result_populated, (
                f"populated-sitemap response missing bucket key {bucket_key!r}; "
                f"keys present: {list(result_populated.keys())}"
            )

    @pytest.mark.asyncio
    async def test_counts_subdict_mirrors_bucket_sizes(self):
        """D-07 + Phase 38.1: response['counts'] has exactly five keys, each equal to len(bucket).

        Phase 38.1 added 'not_eligible' to the counts sub-dict (slots between
        'unreachable' and 'unknown'). 'unknown' and 'changed' remain 0 in
        Phase 38.1 (reserved for Phase 39 DRFT-17/19).
        """
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"},
            {"hostname": "pi-lab", "connection_ip": "10.0.0.12", "status": "success"},
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            # Phase 41 Bug V: drift dials connection_ip when set.
            if host in ("pve1", "10.0.0.10"):
                client = MagicMock()
                client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
                return client
            client = MagicMock()
            client.get = AsyncMock(side_effect=aiohttp.ClientError("connection refused"))
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert "counts" in result, f"missing 'counts' key; keys: {list(result.keys())}"
        counts = result["counts"]
        assert isinstance(counts, dict), f"counts is not a dict: {type(counts).__name__}"
        assert set(counts.keys()) == {
            "probed_ok",
            "unreachable",
            "not_eligible",
            "unknown",
            "changed",
        }, f"counts has unexpected key set: {set(counts.keys())}"
        assert counts["probed_ok"] == len(result["probed_ok"]) == 1
        assert counts["unreachable"] == len(result["unreachable"]) == 1
        assert counts["not_eligible"] == len(result["not_eligible"]) == 0
        assert counts["unknown"] == len(result["unknown"]) == 0
        assert counts["changed"] == len(result["changed"]) == 0

    @pytest.mark.asyncio
    async def test_counts_sum_equals_top_level_scanned(self):
        """D-07 invariant: scanned == sum(counts.values()) (defensive vs Phase 39).

        Plan 1's action note: 'Use sum(counts.values()) (not the explicit two-bucket
        addition) so that Phase 39's bucket-population work cannot silently break
        the invariant.' Verified across empty-sitemap and populated-sitemap scenarios.
        """
        # Empty sitemap
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = []
        result = await scan_drift(session=None, db_adapter=db_adapter)
        assert result["scanned"] == sum(result["counts"].values()) == 0

        # Populated sitemap with mixed outcomes
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"},
            {"hostname": "pi-lab", "connection_ip": "10.0.0.12", "status": "success"},
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            if host == "pve1":
                client = MagicMock()
                client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
                return client
            client = MagicMock()
            client.get = AsyncMock(side_effect=aiohttp.ClientError("refused"))
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["scanned"] == sum(result["counts"].values()) == 2

    # ───────────────────────────────────────────────────────────────────────
    # Phase 37 conditional-guidance tests (D-09)
    # ───────────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_guidance_present_when_scanned_zero(self):
        """D-09: 'guidance' key is present and non-empty when scanned == 0."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = []

        result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["scanned"] == 0
        assert "guidance" in result, f"empty-sitemap response missing 'guidance' key; keys: {list(result.keys())}"
        assert isinstance(result["guidance"], str), f"guidance is not a string: {type(result['guidance']).__name__}"
        assert len(result["guidance"]) > 0, "guidance string is empty"

    @pytest.mark.asyncio
    async def test_guidance_absent_when_scanned_nonzero(self):
        """D-09: 'guidance' key is absent from the response dict when scanned > 0.

        Uses the canonical 3-row mock harness from test_three_row_classification.
        Phase 38.1: yields scanned == 3 (pve1 probed_ok + pi-lab unreachable +
        truenas1 not_eligible/unbound — no longer silently skipped per D-15).
        """
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"},
            {"hostname": "truenas1", "connection_ip": "10.0.0.11", "status": "success"},
            {"hostname": "pi-lab", "connection_ip": "10.0.0.12", "status": "success"},
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            # Phase 41 Bug V: drift dials connection_ip when set.
            if host in ("pve1", "10.0.0.10"):
                client = MagicMock()
                client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
                return client
            if host in ("truenas1", "10.0.0.11"):
                raise CredentialNotFoundError(f"no creds for {host}")
            client = MagicMock()
            client.get = AsyncMock(side_effect=aiohttp.ClientError("refused"))
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["scanned"] == 3
        assert "guidance" not in result, (
            f"populated-sitemap response unexpectedly contains 'guidance' key; "
            f"D-09 requires absence when scanned > 0. Keys: {list(result.keys())}"
        )

    @pytest.mark.asyncio
    async def test_guidance_text_references_sitemap_crud_tools(self):
        """D-09 / DRFT-15: guidance text mentions discover_and_map AND get_network_sitemap.

        Plan 1 also documented that one of purge_failed_discoveries / decommission_device
        must appear; this test asserts both anchor tool names are present (the third is
        verified by Plan 1's own acceptance criteria).
        """
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = []

        result = await scan_drift(session=None, db_adapter=db_adapter)
        guidance = result.get("guidance", "")

        assert "discover_and_map" in guidance, f"guidance missing 'discover_and_map' reference; got: {guidance!r}"
        assert "get_network_sitemap" in guidance, f"guidance missing 'get_network_sitemap' reference; got: {guidance!r}"

    @pytest.mark.asyncio
    async def test_guidance_text_does_not_mention_proxmox_host(self):
        """D-09 / DRFT-15: guidance text does NOT contain the deprecated PROXMOX_HOST.

        Architectural lock — drift surface text must reference sitemap CRUD tools and
        the credentials CLI, never the deprecated env var. Plan 3's AST guard catches
        this at the file level; this test catches it at the runtime-string level.
        """
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = []

        result = await scan_drift(session=None, db_adapter=db_adapter)
        guidance = result.get("guidance", "")

        assert "PROXMOX_HOST" not in guidance, (
            f"guidance contains forbidden PROXMOX_HOST reference (DRFT-15 regression); got: {guidance!r}"
        )

    # ───────────────────────────────────────────────────────────────────────
    # Phase 37 hostname-filter tests (D-01 / D-03)
    # ───────────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_node_filter_exact_hostname_match(self):
        """D-01: node='pve1' against a 3-row sitemap narrows iteration to that one row.

        Other hosts must NOT be probed (get_proxmox_client never called for them) and
        must NOT appear in any bucket of the response.
        """
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"},
            {"hostname": "pve2", "connection_ip": "10.0.0.11", "status": "success"},
            {"hostname": "pve3", "connection_ip": "10.0.0.12", "status": "success"},
        ]

        called_hosts: list[str] = []

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            called_hosts.append(host)
            # Phase 41 Bug V: drift dials connection_ip when set.
            if host in ("pve1", "10.0.0.10"):
                client = MagicMock()
                client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
                return client
            raise AssertionError(f"D-01 violation: get_proxmox_client called for non-matching host {host!r}")

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter, node="pve1")

        # D-01 filter intent: filtered-out rows are never probed. The number of
        # calls to get_proxmox_client per surviving host is an implementation
        # detail (Phase 39 DRFT-17 added a post-loop /cluster/resources call,
        # so probed_ok hosts get a second call for VM enumeration). The
        # invariant is the *set* of called hosts, not the count.
        # Phase 41-06 CR-01: drift passes host=hostname (resolver/cache key)
        # and dial_host=connection_ip; called_hosts captures host= = hostname.
        assert set(called_hosts) == {"pve1"}, f"D-01 filter failed: expected only pve1, got {called_hosts}"
        assert result["scanned"] == 1
        assert len(result["probed_ok"]) == 1
        assert result["probed_ok"][0]["hostname"] == "pve1"
        all_hostnames = {r["hostname"] for r in result["probed_ok"] + result["unreachable"]}
        assert "pve2" not in all_hostnames
        assert "pve3" not in all_hostnames

    @pytest.mark.asyncio
    async def test_node_filter_no_match_returns_success_empty(self):
        """D-01 / D-03 / D-09: node='nonexistent' returns success + empty buckets + guidance.

        Empty match is a successful empty result — never status='error'. Closes Bugs
        A and E (both manifested as scope errors on missing-baseline filter scopes).
        """
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"},
        ]

        # If the filter works, get_proxmox_client is never called
        with patch("homelab_mcp.drift_detection.get_proxmox_client") as mock_client:
            result = await scan_drift(session=None, db_adapter=db_adapter, node="nonexistent-host")

        mock_client.assert_not_called()
        assert result["status"] == "success"
        assert result["scanned"] == 0
        assert result["probed_ok"] == []
        assert result["unreachable"] == []
        assert result["unknown"] == []
        assert result["changed"] == []
        assert "guidance" in result, (
            f"no-match filter response missing 'guidance' key; D-09 requires presence "
            f"when scanned == 0. Keys: {list(result.keys())}"
        )

    @pytest.mark.asyncio
    async def test_node_filter_none_means_no_filter(self):
        """D-01: node=None (default) iterates all sitemap rows — Phase 36 behavior preserved."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"},
            {"hostname": "pve2", "connection_ip": "10.0.0.11", "status": "success"},
        ]

        called_hosts: list[str] = []

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            called_hosts.append(host)
            # Phase 41 Bug V: drift dials connection_ip; map back to hostname for the mock node response.
            host_to_name = {"10.0.0.10": "pve1", "10.0.0.11": "pve2"}
            client = MagicMock()
            client.get = AsyncMock(return_value=[{"type": "node", "name": host_to_name.get(host, host)}])
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter, node=None)

        # Phase 39 DRFT-17: probed_ok hosts get a second get_proxmox_client
        # call from the /cluster/resources enumeration pre-pass. Assert on the
        # *set* of hosts probed, not the call count.
        # Phase 41-06 CR-01: drift now passes host=hostname (resolver/cache key)
        # and dial_host=connection_ip via separate kwargs. called_hosts records
        # the host= arg, which is the hostname (CR-01 fix).
        assert set(called_hosts) >= {"pve1", "pve2"}, f"node=None should iterate every sitemap row; got: {called_hosts}"
        assert result["scanned"] == 2
        all_hostnames = {r["hostname"] for r in result["probed_ok"]}
        assert all_hostnames == {"pve1", "pve2"}

    # ───────────────────────────────────────────────────────────────────────
    # Phase 37 vm_type inertness tests (D-02)
    # ───────────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_vm_type_inert_across_qemu_lxc_all(self):
        """D-02: vm_type stays inert at host-scan level — same shape across qemu/lxc/all.

        Run scan_drift three times against the SAME mocked sitemap (one probed_ok row)
        with vm_type='qemu', vm_type='lxc', vm_type='all' and assert the responses are
        structurally identical: same envelope keys, same bucket sizes, same counts dict,
        same guidance presence/absence.
        """
        # Standard 1-row sitemap
        rows = [{"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"}]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()
            client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        results: dict[str, dict] = {}
        for vm_type_value in ("qemu", "lxc", "all"):
            db_adapter = MagicMock()
            db_adapter.get_all_devices.return_value = list(rows)
            with (
                patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
                patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
            ):
                results[vm_type_value] = await scan_drift(
                    session=None,
                    db_adapter=db_adapter,
                    vm_type=vm_type_value,
                )

        # All three responses must have the SAME structural shape.
        # Compare keys (excluding scan_timestamp which differs per-call).
        for vm_type_value in ("lxc", "all"):
            keys_qemu = set(results["qemu"].keys())
            keys_other = set(results[vm_type_value].keys())
            assert keys_qemu == keys_other, (
                f"D-02 violation: vm_type='qemu' keys {keys_qemu} differ from "
                f"vm_type={vm_type_value!r} keys {keys_other}"
            )
            # Bucket sizes identical
            for bucket_key in ("probed_ok", "unreachable", "unknown", "changed"):
                assert len(results["qemu"][bucket_key]) == len(results[vm_type_value][bucket_key]), (
                    f"D-02 violation: bucket {bucket_key!r} size differs between "
                    f"vm_type='qemu' ({len(results['qemu'][bucket_key])}) and "
                    f"vm_type={vm_type_value!r} ({len(results[vm_type_value][bucket_key])})"
                )
            # counts dicts equal
            assert results["qemu"]["counts"] == results[vm_type_value]["counts"], (
                f"D-02 violation: counts differ between vm_type='qemu' "
                f"({results['qemu']['counts']}) and vm_type={vm_type_value!r} "
                f"({results[vm_type_value]['counts']})"
            )
            # scanned identical
            assert results["qemu"]["scanned"] == results[vm_type_value]["scanned"]
            # guidance presence identical
            assert ("guidance" in results["qemu"]) == ("guidance" in results[vm_type_value]), (
                f"D-02 violation: guidance presence differs between vm_type='qemu' and vm_type={vm_type_value!r}"
            )

    # ───────────────────────────────────────────────────────────────────────
    # Phase 37 envelope key-order tests (Plan 1 contract)
    # ───────────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_envelope_key_order_is_locked(self):
        """Plan 1 contract + Phase 38.1 D-08: top-level dict insertion order is locked.

        When scanned == 0:
          ['status', 'scan_timestamp', 'scanned', 'counts', 'guidance',
           'probed_ok', 'unreachable', 'not_eligible', 'unknown', 'changed']

        When scanned > 0 (no 'guidance'):
          ['status', 'scan_timestamp', 'scanned', 'counts',
           'probed_ok', 'unreachable', 'not_eligible', 'unknown', 'changed']

        Phase 38.1: 'not_eligible' slots between 'unreachable' and 'unknown'
        (R7 envelope position; the rest of the Phase 37 order is preserved).
        """
        # scanned == 0 case
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = []
        result_empty = await scan_drift(session=None, db_adapter=db_adapter)
        expected_empty_order = [
            "status",
            "scan_timestamp",
            "scanned",
            "counts",
            "guidance",
            "probed_ok",
            "unreachable",
            "not_eligible",
            "unknown",
            "changed",
        ]
        assert list(result_empty.keys()) == expected_empty_order, (
            f"scanned==0 key order broken; got {list(result_empty.keys())}"
        )

        # scanned > 0 case (no guidance)
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"},
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()
            client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result_populated = await scan_drift(session=None, db_adapter=db_adapter)

        expected_populated_order = [
            "status",
            "scan_timestamp",
            "scanned",
            "counts",
            "probed_ok",
            "unreachable",
            "not_eligible",
            "unknown",
            "changed",
        ]
        assert list(result_populated.keys()) == expected_populated_order, (
            f"scanned>0 key order broken; got {list(result_populated.keys())}"
        )

    # ───────────────────────────────────────────────────────────────────────
    # Phase 37 per-row-record preservation tests (D-10 / Phase 36 D-02)
    # ───────────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_per_row_record_shape_preserved_for_probed_ok(self):
        """D-10 / Phase 36 D-02: probed_ok entries retain seven canonical keys."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"},
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()
            client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert len(result["probed_ok"]) == 1
        record = result["probed_ok"][0]
        expected_keys = {
            "hostname",
            "connection_ip",
            "scope",
            "cluster_name",
            "status",
            "error",
            "scan_timestamp",
        }
        assert set(record.keys()) == expected_keys, (
            f"probed_ok record key set drifted from Phase 36 D-02; expected {expected_keys}, got {set(record.keys())}"
        )
        assert record["status"] == "probed-ok"
        assert record["error"] is None

    @pytest.mark.asyncio
    async def test_per_row_record_shape_preserved_for_unreachable(self):
        """D-10 / Phase 36 D-02: unreachable entries retain seven canonical keys."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "pi-lab", "connection_ip": "10.0.0.12", "status": "success"},
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()
            client.get = AsyncMock(side_effect=aiohttp.ClientError("connection refused"))
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@cluster", "cluster", "homelab-prod")

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert len(result["unreachable"]) == 1
        record = result["unreachable"][0]
        expected_keys = {
            "hostname",
            "connection_ip",
            "scope",
            "cluster_name",
            "status",
            "error",
            "scan_timestamp",
        }
        assert set(record.keys()) == expected_keys, (
            f"unreachable record key set drifted from Phase 36 D-02; expected {expected_keys}, got {set(record.keys())}"
        )
        assert record["status"] == "unreachable"
        assert isinstance(record["error"], str) and len(record["error"]) > 0

    @pytest.mark.asyncio
    async def test_per_row_record_shape_for_missing_substatus_phase39(self):
        """WR-02 (Phase 39 review): unreachable[] records with status=='missing'
        carry the 7-key base shape PLUS ``last_seen`` and ``message``,
        for a total of 9 canonical keys. Locks the docstring contract:
        7 keys for unreachable, 9 keys for missing.
        """
        old_ts = "2020-01-01T00:00:00"  # >7 days ago by any reasonable threshold
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {
                "hostname": "pi-lab",
                "connection_ip": "10.0.0.12",
                "status": "success",
                "last_seen": old_ts,
            },
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()
            client.get = AsyncMock(side_effect=aiohttp.ClientError("connection refused"))
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@cluster", "cluster", "homelab-prod")

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert len(result["unreachable"]) == 1
        record = result["unreachable"][0]
        expected_keys = {
            "hostname",
            "connection_ip",
            "scope",
            "cluster_name",
            "status",
            "error",
            "scan_timestamp",
            "last_seen",
            "message",
        }
        assert set(record.keys()) == expected_keys, (
            f"missing record key set drifted from Phase 39 D-01; expected {expected_keys}, got {set(record.keys())}"
        )
        assert record["status"] == "missing"
        assert isinstance(record["last_seen"], str) and record["last_seen"]
        assert isinstance(record["message"], str) and "decommission_device" in record["message"]

    # ───────────────────────────────────────────────────────────────────────
    # Phase 37 reserved-empty bucket tests (D-05 / D-06)
    # ───────────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_unknown_and_changed_buckets_always_empty_in_phase_37(self):
        """D-05 / D-06: unknown and changed buckets are ALWAYS [] in Phase 37.

        Phase 39 (DRFT-17 / DRFT-19) will populate them; Phase 37 reserves the
        shape. Verified across empty-sitemap, populated-sitemap, and filtered
        scenarios.
        """
        # Scenario 1: empty sitemap
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = []
        r1 = await scan_drift(session=None, db_adapter=db_adapter)
        assert r1["unknown"] == [], f"empty-sitemap unknown not []: {r1['unknown']}"
        assert r1["changed"] == [], f"empty-sitemap changed not []: {r1['changed']}"

        # Scenario 2: populated with mixed outcomes
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"},
            {"hostname": "pi-lab", "connection_ip": "10.0.0.12", "status": "success"},
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            if host == "pve1":
                client = MagicMock()
                client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
                return client
            client = MagicMock()
            client.get = AsyncMock(side_effect=aiohttp.ClientError("refused"))
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            r2 = await scan_drift(session=None, db_adapter=db_adapter)

        assert r2["unknown"] == [], f"populated-sitemap unknown not []: {r2['unknown']}"
        assert r2["changed"] == [], f"populated-sitemap changed not []: {r2['changed']}"

        # Scenario 3: node filter no-match
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"},
        ]
        r3 = await scan_drift(session=None, db_adapter=db_adapter, node="nonexistent")
        assert r3["unknown"] == [], f"no-match unknown not []: {r3['unknown']}"
        assert r3["changed"] == [], f"no-match changed not []: {r3['changed']}"

    @pytest.mark.asyncio
    async def test_resolver_runs_once_when_hostname_differs_from_connection_ip(self):
        """Phase 41-06 CR-01: when hostname != connection_ip on a row,
        scan_drift must invoke resolve_proxmox_credentials EXACTLY ONCE per
        host (keyed on hostname). Plan 41-04 had set host=connection_ip on
        get_proxmox_client, forcing the resolver to write the telemetry cache
        as (connection_ip, binding); the very next
        get_resolution_telemetry(hostname, binding) call in scan_drift then
        missed and re-ran the resolver — double-resolution.

        After Plan 41-06's host/dial_host split, the resolver runs once
        keyed on hostname; the telemetry cache lookup hits.
        """
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {
                "hostname": "pve",
                "connection_ip": "192.168.10.20",
                "proxmox_credential_id": "00000000-0000-0000-0000-000000000abc",
                "status": "success",
            },
        ]

        resolve_calls: list[tuple[str, str | None]] = []

        async def fake_resolve(host, *, session=None, credential_id=None):
            resolve_calls.append((host, credential_id))
            return ("user@pam!tok=secret", "node", None)

        captured: dict[str, str | None] = {}

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            captured["host"] = host
            captured["dial_host"] = dial_host
            # Drive the resolver via the same path get_proxmox_client uses in
            # production (so the telemetry cache gets populated keyed on host).
            await fake_resolve(host, session=session, credential_id=credential_id)
            client = MagicMock()
            client.get = AsyncMock(return_value=[])
            return client

        with (
            patch(
                "homelab_mcp.drift_detection.get_proxmox_client",
                side_effect=fake_get_client,
            ),
            patch(
                "homelab_mcp.drift_detection.resolve_proxmox_credentials",
                side_effect=fake_resolve,
            ),
            patch(
                "homelab_mcp.drift_detection._bulk_universal_core_probes",
                AsyncMock(return_value={}),
            ),
        ):
            await scan_drift(session=None, db_adapter=db_adapter)

        # CR-01 invariant: get_proxmox_client receives host=hostname (resolver/cache key)
        # and dial_host=connection_ip (TCP target).
        assert captured.get("host") == "pve", (
            f"Phase 41-06 CR-01: get_proxmox_client got host={captured.get('host')!r}, "
            f"expected 'pve' (the hostname is the canonical resolver/cache key)."
        )
        assert captured.get("dial_host") == "192.168.10.20", (
            f"Phase 41-06 CR-01: get_proxmox_client got dial_host={captured.get('dial_host')!r}, "
            f"expected '192.168.10.20' (row.connection_ip)."
        )

        # CR-01 functional invariant: resolver was called keyed on hostname.
        assert resolve_calls, "resolver was never invoked"
        assert all(call[0] == "pve" for call in resolve_calls), (
            f"Phase 41-06 CR-01: resolver called with non-hostname identifiers: {resolve_calls!r}. "
            f"Plan 41-04's regression would have invoked it with '192.168.10.20' (connection_ip)."
        )

    @pytest.mark.asyncio
    async def test_probe_one_forwards_db_adapter(self):
        """Phase 41-07 WR-02: scan_drift's db_adapter argument must be threaded
        through _bulk_universal_core_probes into _probe_one's
        resolve_ssh_for_sitemap_row call. Without the thread, the helper
        falls through to get_database_adapter() which constructs a fresh
        SQLiteAdapter / PostgreSQLAdapter — potentially against a different
        db_path than the one scan_drift was handed.

        See .planning/phases/41-binding-aware-resolver-hygiene/41-REVIEW.md WR-02.
        """
        from homelab_mcp.ssh_tools import CredentialNotFoundError

        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {
                "hostname": "host1",
                "connection_ip": "10.0.0.10",
                "ssh_credential_id": "00000000-0000-0000-0000-00000000abc1",
                "proxmox_credential_id": None,
                "status": "success",
            },
        ]

        helper_calls: list[tuple[tuple, dict]] = []

        def fake_resolver(*args, **kwargs):
            helper_calls.append((args, kwargs))
            # Short-circuit past ssh_connect — _probe_one's bare ``except
            # Exception`` catches this and returns (hostname, {"_error": ...}).
            raise CredentialNotFoundError("test stub: short-circuit before ssh_connect")

        with patch(
            "homelab_mcp.drift_detection.resolve_ssh_for_sitemap_row",
            side_effect=fake_resolver,
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert helper_calls, (
            "Phase 41-07 WR-02: resolve_ssh_for_sitemap_row was never called. "
            "Either scan_drift didn't reach the SSH pre-pass, or _probe_one "
            "is bypassing the helper. Check _bulk_universal_core_probes wiring."
        )
        for args, kwargs in helper_calls:
            assert "db_adapter" in kwargs, (
                f"Phase 41-07 WR-02: resolve_ssh_for_sitemap_row called "
                f"without db_adapter= kwarg. args={args!r} kwargs={kwargs!r}. "
                "Without the keyword, the helper falls through to "
                "get_database_adapter() (a fresh adapter from os.environ), "
                "breaking scan_drift's single-source-of-truth contract."
            )
            assert kwargs["db_adapter"] is db_adapter, (
                f"Phase 41-07 WR-02: resolve_ssh_for_sitemap_row received a "
                f"DIFFERENT db_adapter than scan_drift was handed. "
                f"Expected (id={id(db_adapter)}): {db_adapter!r}; "
                f"received (id={id(kwargs['db_adapter'])}): {kwargs['db_adapter']!r}. "
                "The same instance must thread through end-to-end."
            )

        # Sanity: scan_drift completed and produced a 5-bucket envelope.
        assert "status" in result


# ─────────────────────────────────────────────────────────────────────────────
# Phase 38.1 D-18: TestScanDriftNotEligible — functional routing regression
# ─────────────────────────────────────────────────────────────────────────────


class TestScanDriftNotEligible:
    """Phase 38.1 D-18: routing-semantics regression.

    Companion to the AST guard (D-15): the AST guard catches structural
    regressions (a stray ``continue``); this class catches semantic regressions
    (rows landing in the wrong bucket).

    Each test patches ``get_proxmox_client`` and/or ``resolve_proxmox_credentials``
    to simulate the four not_eligible reason codes from D-08:
        - unbound       — proxmox_credential_id IS NULL
        - binding_stale — UUID not in registry
        - keyring_desync — UUID in registry but keyring secret missing
        - degenerate    — row has bad hostname/status before resolver runs
    """

    @pytest.mark.asyncio
    async def test_unbound_row_routes_to_not_eligible(self) -> None:
        """Row with NULL proxmox_credential_id + no cluster cred → not_eligible/unbound."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {
                "hostname": "pve1",
                "connection_ip": "10.0.0.10",
                "status": "success",
                "proxmox_credential_id": None,
                "ssh_credential_id": None,
            },
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            raise CredentialNotFoundError(f"No Proxmox credentials found for {host}.")

        with patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["status"] == "success"
        assert len(result["probed_ok"]) == 0
        assert result["counts"]["not_eligible"] == 1
        assert result["not_eligible"][0]["hostname"] == "pve1"
        assert result["not_eligible"][0]["reason"] == "unbound"
        assert "credentials add --type proxmox" in result["not_eligible"][0]["message"]

    @pytest.mark.asyncio
    async def test_bound_row_with_valid_uuid_routes_to_probed_ok(self) -> None:
        """Row with valid proxmox_credential_id → probed_ok (UUID short-circuit hits)."""
        db_adapter = MagicMock()
        valid_uuid = "11111111-1111-4111-8111-111111111111"
        db_adapter.get_all_devices.return_value = [
            {
                "hostname": "pve2",
                "connection_ip": "10.0.0.20",
                "status": "success",
                "proxmox_credential_id": valid_uuid,
                "ssh_credential_id": None,
            },
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()
            client.get = AsyncMock(return_value=[{"type": "node", "name": "pve2"}])
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["status"] == "success"
        assert len(result["probed_ok"]) == 1
        assert result["probed_ok"][0]["hostname"] == "pve2"
        assert result["counts"].get("not_eligible", 0) == 0

    @pytest.mark.asyncio
    async def test_bound_row_stale_uuid_routes_to_not_eligible(self) -> None:
        """Row with stale proxmox_credential_id → not_eligible/binding_stale."""
        db_adapter = MagicMock()
        stale_uuid = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        db_adapter.get_all_devices.return_value = [
            {
                "hostname": "pve3",
                "connection_ip": "10.0.0.30",
                "status": "success",
                "proxmox_credential_id": stale_uuid,
                "ssh_credential_id": None,
            },
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            raise CredentialNotFoundError(
                f"binding stale: UUID {stale_uuid} not in registry. "
                f"Run `credentials add --type proxmox {host}` to register."
            )

        with patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["status"] == "success"
        assert result["counts"]["not_eligible"] == 1
        assert result["not_eligible"][0]["hostname"] == "pve3"
        assert result["not_eligible"][0]["reason"] == "binding_stale"

    @pytest.mark.asyncio
    async def test_degenerate_row_routes_to_not_eligible(self) -> None:
        """Row with hostname='' → not_eligible/degenerate (filter fires before resolver)."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {
                "hostname": "",
                "connection_ip": "10.0.0.40",
                "status": "success",
                "proxmox_credential_id": None,
                "ssh_credential_id": None,
            },
        ]

        # No patch on get_proxmox_client — degenerate filter fires before resolver
        with patch("homelab_mcp.drift_detection.get_proxmox_client") as mock_client:
            result = await scan_drift(session=None, db_adapter=db_adapter)

        mock_client.assert_not_called()
        assert result["status"] == "success"
        assert result["counts"]["not_eligible"] == 1
        assert result["not_eligible"][0]["reason"] == "degenerate"

    @pytest.mark.asyncio
    async def test_no_row_vanishes(self) -> None:
        """4-row fixture: every row lands in exactly one bucket; no row silently dropped.

        I7: closure invariant — scanned == sum(len(result[bucket]) for all buckets).
        """
        valid_uuid = "22222222-2222-4222-8222-222222222222"
        stale_uuid = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            # Row 1: bound-fresh → probed_ok
            {
                "hostname": "pve-fresh",
                "connection_ip": "10.0.0.1",
                "status": "success",
                "proxmox_credential_id": valid_uuid,
                "ssh_credential_id": None,
            },
            # Row 2: unbound → not_eligible
            {
                "hostname": "pve-unbound",
                "connection_ip": "10.0.0.2",
                "status": "success",
                "proxmox_credential_id": None,
                "ssh_credential_id": None,
            },
            # Row 3: stale UUID → not_eligible
            {
                "hostname": "pve-stale",
                "connection_ip": "10.0.0.3",
                "status": "success",
                "proxmox_credential_id": stale_uuid,
                "ssh_credential_id": None,
            },
            # Row 4: degenerate hostname → not_eligible
            {
                "hostname": "unknown",
                "connection_ip": "10.0.0.4",
                "status": "success",
                "proxmox_credential_id": None,
                "ssh_credential_id": None,
            },
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            # Phase 41 Bug V: drift dials connection_ip when set.
            if host in ("pve-fresh", "10.0.0.1"):
                client = MagicMock()
                client.get = AsyncMock(return_value=[{"type": "node", "name": "pve-fresh"}])
                return client
            if host in ("pve-unbound", "10.0.0.2"):
                raise CredentialNotFoundError(f"No Proxmox credentials found for {host}.")
            if host in ("pve-stale", "10.0.0.3"):
                raise CredentialNotFoundError(f"binding stale: UUID {stale_uuid} not in registry.")
            raise AssertionError(f"unexpected host in fake_get_client: {host}")

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        buckets = ("probed_ok", "unreachable", "not_eligible", "unknown", "changed")
        total_in_buckets = sum(len(result[b]) for b in buckets)
        assert total_in_buckets == 4, (
            f"I7 closure violation: 4 rows in, only {total_in_buckets} rows landed in buckets. "
            f"Bucket sizes: { {b: len(result[b]) for b in buckets} }"
        )
        # I7: scanned must equal sum of all bucket lengths
        assert result["scanned"] == sum(len(result[b]) for b in buckets), (
            f"I7 scanned invariant violated: scanned={result['scanned']} but "
            f"sum(bucket lengths)={sum(len(result[b]) for b in buckets)}"
        )


class TestPhase39Helpers:
    """Phase 39 helpers (Plan 01) — diff/enumerate/classify/threshold/parse +
    universal-core probe extraction. RED in Plan 01 Task 1; GREEN in Tasks 2/3.

    D-08, D-09a, D-01, D-02, D-05, D-06, D-07 — see 39-CONTEXT.md.
    """

    # -- _diff_fingerprints (D-08, D-09a) ---------------------------------

    def test_diff_fingerprints_per_leaf_present_in_both(self) -> None:
        """D-09a: a stored leaf absent from current is NOT diffed."""
        stored = {"capabilities": {"vulkan": {"available": True}}}
        current: dict = {"capabilities": {}}
        assert _diff_fingerprints(stored, current) == {}

    def test_diff_fingerprints_dotted_path(self) -> None:
        """D-08: nested capability sub-keys emit dotted-path entries."""
        stored = {"capabilities": {"vulkan": {"available": True}}}
        current = {"capabilities": {"vulkan": {"available": False}}}
        assert _diff_fingerprints(stored, current) == {
            "capabilities.vulkan.available": {"stored": True, "current": False},
        }

    def test_diff_fingerprints_top_level_kernel(self) -> None:
        """Top-level kernel field diff uses bare key (no dotted prefix)."""
        stored = {"kernel_version": "6.5.13"}
        current = {"kernel_version": "6.8.4"}
        assert _diff_fingerprints(stored, current) == {
            "kernel_version": {"stored": "6.5.13", "current": "6.8.4"},
        }

    def test_diff_fingerprints_empty_when_equal(self) -> None:
        stored = {"kernel_version": "6.5.13", "os_name": "Proxmox VE"}
        current = {"kernel_version": "6.5.13", "os_name": "Proxmox VE"}
        assert _diff_fingerprints(stored, current) == {}

    def test_diff_fingerprints_current_only_top_level_emits_phase39_wr05(self) -> None:
        """WR-05: a top-level key present only in ``current`` emits a diff
        with stored=None. Models a host that just gained dpkg and now
        reports ``package_fingerprint`` for the first time.
        """
        stored: dict = {"kernel_version": "6.5.13"}
        current = {
            "kernel_version": "6.5.13",
            "package_fingerprint": "deadbeef",
        }
        assert _diff_fingerprints(stored, current) == {
            "package_fingerprint": {"stored": None, "current": "deadbeef"},
        }

    def test_diff_fingerprints_current_only_nested_emits_phase39_wr05(self) -> None:
        """WR-05: a nested capability sub-key present only in ``current``
        emits a dotted-path diff with stored=None.
        """
        stored = {"capabilities": {"vulkan": {"available": True}}}
        current = {
            "capabilities": {
                "vulkan": {"available": True},
                "rocm": {"available": True},
            }
        }
        assert _diff_fingerprints(stored, current) == {
            "capabilities.rocm": {"stored": None, "current": {"available": True}},
        }

    def test_diff_fingerprints_stored_only_still_suppressed_phase39_wr05(self) -> None:
        """WR-05 / D-09a: stored-only keys remain suppressed (capability
        drop is expected, not drift). Lock the asymmetry.
        """
        stored = {"capabilities": {"vulkan": {"available": True}, "rocm": {"available": True}}}
        current = {"capabilities": {"vulkan": {"available": True}}}
        # rocm appears only in stored → suppressed.
        assert _diff_fingerprints(stored, current) == {}

    # -- _classify_unreachable (D-01, D-02) -------------------------------

    def test_classify_unreachable_old_last_seen_returns_missing(
        self, freeze_now: datetime, sitemap_row_old_last_seen: dict
    ) -> None:
        status, message = _classify_unreachable(
            sitemap_row_old_last_seen,
            TimeoutError("connection timeout"),
            threshold_days=7,
            now=freeze_now,
        )
        assert status == "missing"
        assert "decommission_device" in message

    def test_classify_unreachable_recent_last_seen_returns_unreachable(
        self, freeze_now: datetime, sitemap_row_recent_last_seen: dict
    ) -> None:
        status, _msg = _classify_unreachable(
            sitemap_row_recent_last_seen,
            aiohttp.ClientError("connection refused"),
            threshold_days=7,
            now=freeze_now,
        )
        assert status == "unreachable"

    def test_classify_unreachable_timezone_normalization(self, freeze_now: datetime) -> None:
        """Pitfall 4: naive ``last_seen`` string must not raise TypeError."""
        row = {
            "hostname": "pi-lab",
            "last_seen": "2026-04-10T10:00:00",  # naive, >7d before frozen now
        }
        status, _msg = _classify_unreachable(
            row,
            TimeoutError(),
            threshold_days=7,
            now=freeze_now,
        )
        assert status == "missing"

    # -- _missing_threshold_days (D-02) -----------------------------------

    def test_missing_threshold_days_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS", raising=False)
        assert _missing_threshold_days() == 7

    def test_missing_threshold_days_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS", "3")
        assert _missing_threshold_days() == 3

    def test_missing_threshold_days_invalid_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS", "abc")
        assert _missing_threshold_days() == 7
        monkeypatch.setenv("HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS", "-1")
        assert _missing_threshold_days() == 7
        monkeypatch.setenv("HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS", "0")
        assert _missing_threshold_days() == 7

    # -- _parse_last_seen (Pitfall 4) -------------------------------------

    def test_parse_last_seen_naive_string(self) -> None:
        result = _parse_last_seen("2026-04-15T10:00:00")
        assert result is not None
        assert result.tzinfo is UTC

    def test_parse_last_seen_none_or_malformed(self) -> None:
        assert _parse_last_seen(None) is None
        assert _parse_last_seen("") is None
        assert _parse_last_seen("not-a-date") is None

    # -- _enumerate_unknown_vms (D-05, D-06, D-07) ------------------------

    def test_enumerate_unknown_case_insensitive(self) -> None:
        """D-06: case-insensitive VM-name vs sitemap-hostname match.

        VM ``Plex-Server`` matches sitemap ``plex-server`` -> not in unknown.
        """
        cluster_vm_map = {
            "pve1": [
                {"type": "qemu", "name": "Plex-Server", "vmid": 100, "node": "pve1", "status": "running"},
            ],
        }
        sitemap_hostnames = {"plex-server"}
        result = _enumerate_unknown_vms(
            cluster_vm_map,
            sitemap_hostnames,
            "2026-04-27T12:00:00+00:00",
        )
        assert result == []

    def test_enumerate_unknown_unmatched_vm_in_result(self) -> None:
        """D-07: unmatched VM produces a per-VM record with discover_and_map
        recovery pointer."""
        cluster_vm_map = {
            "pve1": [
                {"type": "qemu", "name": "ubuntu-test", "vmid": 110, "node": "pve1", "status": "stopped"},
            ],
        }
        sitemap_hostnames = {"pve1"}
        result = _enumerate_unknown_vms(
            cluster_vm_map,
            sitemap_hostnames,
            "2026-04-27T12:00:00+00:00",
        )
        assert len(result) == 1
        row = result[0]
        assert row["vmid"] == 110
        assert row["vm_type"] == "qemu"
        assert row["vm_name"] == "ubuntu-test"
        assert row["hypervisor_hostname"] == "pve1"
        assert row["scan_timestamp"] == "2026-04-27T12:00:00+00:00"
        assert "discover_and_map" in row["message"]

    # -- _probe_universal_core (D-03, extracted from ssh_discover_system) -

    @pytest.mark.asyncio
    async def test_probe_universal_core_extraction_parity(self) -> None:
        """D-03: extracted helper returns the same Phase 38 fingerprint shape
        as the ssh_discover_system inline block (lines 614-691).

        Mocks ``conn.run`` per cmd_name to canned stdouts; asserts dict
        contains all 5 universal-core keys.
        """
        timed_out: list[str] = []

        # Map command-string substrings to canned stdouts (matches the
        # production order: uname-s, uname-r, os-release-full, dpkg).
        responses = {
            "uname -s": MagicMock(exit_status=0, stdout="Linux\n"),
            "uname -r": MagicMock(exit_status=0, stdout="6.5.13-1-pve\n"),
            "/etc/os-release": MagicMock(
                exit_status=0,
                stdout=('PRETTY_NAME="Proxmox VE 8.2.4"\nNAME="Proxmox VE"\nVERSION_ID="8.2.4"\n'),
            ),
            "dpkg -l": MagicMock(
                exit_status=0,
                stdout=("abc123def456abc123def456abc123def456abc123def456abc123def456abc123defab  -\n"),
            ),
        }

        async def _run(cmd: str, *args: object, **kwargs: object) -> MagicMock:
            for needle, response in responses.items():
                if needle in cmd:
                    return response
            return MagicMock(exit_status=0, stdout="")

        conn = MagicMock()
        conn.run = AsyncMock(side_effect=_run)

        result = await _probe_universal_core(conn, timed_out)

        assert result.get("kernel_name") == "Linux"
        assert result.get("kernel_version") == "6.5.13-1-pve"
        assert result.get("os_name") == "Proxmox VE 8.2.4"
        assert result.get("os_version") == "8.2.4"
        assert result.get("package_fingerprint", "").startswith("sha256:")


class TestPhase39Unknown:
    """Phase 39 D-05/D-06/D-07 + DRFT-17: unknown VM detection via /cluster/resources.

    Wave 2 functional tests covering the post-loop VM-enumeration pre-pass that
    feeds scan_drift's ``unknown[]`` bucket. Each test mocks
    ``homelab_mcp.drift_detection.get_proxmox_client`` to return a client whose
    ``.get`` is wired up per-test to (a) succeed for ``/cluster/status`` (so the
    host lands in ``probed_ok``) and (b) return / raise per-test on
    ``/cluster/resources``.
    """

    @pytest.mark.asyncio
    async def test_unmatched_vm_in_unknown_bucket(
        self,
        mock_cluster_resources_response: list[dict[str, object]],
    ) -> None:
        """D-06 / D-07: a single sitemap row whose Proxmox cluster reports two
        unmatched VMs (``ubuntu-test`` qemu, ``pi-hole`` lxc) → both surface in
        ``unknown[]`` with the per-VM record shape and ``discover_and_map``
        message. The matched ``ubuntu-prod`` VM is filtered out by the
        case-insensitive sitemap match. The ``node``-type record from
        ``/cluster/resources`` is filtered to VM-types only.
        """
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {
                "hostname": "ubuntu-prod",
                "connection_ip": "10.0.0.10",
                "status": "success",
                "proxmox_credential_id": "11111111-1111-4111-8111-111111111111",
                "ssh_credential_id": None,
            },
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()

            async def _get(path: str) -> object:
                if path == "/cluster/status":
                    return [{"type": "node", "name": host}]
                if path == "/cluster/resources":
                    return mock_cluster_resources_response
                raise AssertionError(f"unexpected path: {path}")

            client.get = AsyncMock(side_effect=_get)
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
            patch.dict("homelab_mcp.proxmox_api._HOST_CLUSTER_CACHE", {}, clear=True),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        # Host stayed in probed_ok (D-10: unknown[] is parallel surface).
        assert result["counts"]["probed_ok"] == 1
        # Two unmatched VMs (ubuntu-test, pi-hole); ubuntu-prod matched, node-type filtered.
        assert result["counts"]["unknown"] == 2, f"expected 2 unknown VMs, got: {result['unknown']}"
        vmids = sorted(row["vmid"] for row in result["unknown"])
        assert vmids == [110, 200], f"unexpected vmids: {vmids}"
        for row in result["unknown"]:
            assert row["hypervisor_hostname"] == "ubuntu-prod"
            assert row["vm_type"] in ("qemu", "lxc")
            assert "discover_and_map" in row["message"]
            assert "scan_timestamp" in row

    @pytest.mark.asyncio
    async def test_cluster_dedup_single_enumeration(self) -> None:
        """D-05: 5 sitemap rows for the same cluster → exactly ONE
        ``/cluster/resources`` call across the whole scan (de-dupe via
        ``_HOST_CLUSTER_CACHE`` cluster_name).
        """
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {
                "hostname": f"pve{n}",
                "connection_ip": f"10.0.0.{10 + n}",
                "status": "success",
                "proxmox_credential_id": "22222222-2222-4222-8222-222222222222",
                "ssh_credential_id": None,
            }
            for n in range(1, 6)
        ]

        # Counter recording how many times /cluster/resources is hit.
        resources_call_count = 0

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()

            async def _get(path: str) -> object:
                nonlocal resources_call_count
                if path == "/cluster/status":
                    return [{"type": "node", "name": host}]
                if path == "/cluster/resources":
                    resources_call_count += 1
                    # Return only matched VMs so unknown[] stays empty.
                    return [
                        {"type": "qemu", "vmid": 100, "name": "pve1", "node": "pve1", "status": "running"},
                    ]
                raise AssertionError(f"unexpected path: {path}")

            client.get = AsyncMock(side_effect=_get)
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@cluster", "cluster", "homelab-prod")

        # Pre-populate cluster cache so all 5 hosts resolve to the same cluster_name.
        cache_seed = {f"pve{n}": "homelab-prod" for n in range(1, 6)}

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
            patch.dict("homelab_mcp.proxmox_api._HOST_CLUSTER_CACHE", cache_seed, clear=True),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["counts"]["probed_ok"] == 5
        assert resources_call_count == 1, (
            f"expected exactly 1 /cluster/resources call (dedup); got {resources_call_count}"
        )

    @pytest.mark.asyncio
    async def test_case_insensitive_match(self) -> None:
        """D-06: VM name ``Plex-Server`` (capitals) matches sitemap hostname
        ``plex-server`` (lowercase) — VM does NOT appear in unknown[].
        """
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {
                "hostname": "plex-server",
                "connection_ip": "10.0.0.20",
                "status": "success",
                "proxmox_credential_id": "33333333-3333-4333-8333-333333333333",
                "ssh_credential_id": None,
            },
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()

            async def _get(path: str) -> object:
                if path == "/cluster/status":
                    return [{"type": "node", "name": host}]
                if path == "/cluster/resources":
                    return [
                        {"type": "qemu", "vmid": 101, "name": "Plex-Server", "node": "pve1", "status": "running"},
                    ]
                raise AssertionError(f"unexpected path: {path}")

            client.get = AsyncMock(side_effect=_get)
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
            patch.dict("homelab_mcp.proxmox_api._HOST_CLUSTER_CACHE", {}, clear=True),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["counts"]["unknown"] == 0, (
            f"case-insensitive match should suppress unknown; got: {result['unknown']}"
        )
        assert result["counts"]["probed_ok"] == 1

    @pytest.mark.asyncio
    async def test_enumeration_failure_keeps_host_in_probed_ok(self) -> None:
        """T-39-07 / D-10: ``/cluster/resources`` raising aiohttp.ClientError does
        NOT promote the host out of ``probed_ok`` — host stays where the
        ``/cluster/status`` probe placed it; just contributes no unknown[] rows.
        """
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {
                "hostname": "pve1",
                "connection_ip": "10.0.0.30",
                "status": "success",
                "proxmox_credential_id": "44444444-4444-4444-8444-444444444444",
                "ssh_credential_id": None,
            },
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()

            async def _get(path: str) -> object:
                if path == "/cluster/status":
                    return [{"type": "node", "name": host}]
                if path == "/cluster/resources":
                    raise aiohttp.ClientError("api 500")
                raise AssertionError(f"unexpected path: {path}")

            client.get = AsyncMock(side_effect=_get)
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
            patch.dict("homelab_mcp.proxmox_api._HOST_CLUSTER_CACHE", {}, clear=True),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["counts"]["probed_ok"] == 1
        assert result["counts"]["unreachable"] == 0
        assert result["counts"]["unknown"] == 0
        assert result["unknown"] == []

    @pytest.mark.asyncio
    async def test_unknown_independent_of_host_bucket(self) -> None:
        """D-10: ``unknown[]`` is a parallel per-VM surface — a probed_ok host
        can still contribute unknown[] entries for VMs missing from sitemap.
        """
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {
                "hostname": "pve1",
                "connection_ip": "10.0.0.40",
                "status": "success",
                "proxmox_credential_id": "55555555-5555-4555-8555-555555555555",
                "ssh_credential_id": None,
            },
        ]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()

            async def _get(path: str) -> object:
                if path == "/cluster/status":
                    return [{"type": "node", "name": host}]
                if path == "/cluster/resources":
                    return [
                        # One unmatched VM (sitemap only has pve1).
                        {"type": "qemu", "vmid": 444, "name": "rogue-vm", "node": "pve1", "status": "running"},
                    ]
                raise AssertionError(f"unexpected path: {path}")

            client.get = AsyncMock(side_effect=_get)
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
            patch.dict("homelab_mcp.proxmox_api._HOST_CLUSTER_CACHE", {}, clear=True),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        # Host is in probed_ok AND unknown[] has the rogue VM — both at once.
        assert result["counts"]["probed_ok"] == 1
        assert result["counts"]["unknown"] == 1
        assert result["unknown"][0]["vm_name"] == "rogue-vm"
        assert result["unknown"][0]["hypervisor_hostname"] == "pve1"


# ─────────────────────────────────────────────────────────────────────────────
# Phase 39 Plan 03 — Wave 0 RED tests for DRFT-18 (missing) and DRFT-19 (changed)
# Plus D-10 bucket invariants. All functional tests are RED until Plan 03 Task 3
# wires _classify_unreachable + _diff_fingerprints into scan_drift's row loop.
# ─────────────────────────────────────────────────────────────────────────────


class TestPhase39Missing:
    """Phase 39 D-01/D-02 + DRFT-18: missing-bucket sub-status under unreachable.

    A sitemap host that fails to probe AND has ``last_seen`` older than the
    threshold (``HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS``, default 7) lands in
    ``unreachable[]`` with ``status: "missing"`` (not a 6th bucket — sub-state
    only) plus a ``last_seen`` field and a recovery pointer to
    ``decommission_device`` / ``purge_failed_discoveries``.
    """

    @pytest.mark.asyncio
    async def test_old_last_seen_promotes_to_missing(
        self,
        sitemap_row_old_last_seen: dict[str, object],
    ) -> None:
        """Probe fails AND last_seen 12d > 7d threshold → status='missing'."""
        db_adapter = MagicMock()
        # Plan 03 wires _classify_unreachable on the existing aiohttp.ClientError
        # branch — give the row a proxmox_credential_id so the row enters that branch
        # (rather than not_eligible/unbound).
        row = dict(sitemap_row_old_last_seen)
        row["proxmox_credential_id"] = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        row["ssh_credential_id"] = None  # SSH pre-pass skips this row.
        db_adapter.get_all_devices.return_value = [row]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()
            client.get = AsyncMock(side_effect=aiohttp.ClientError("connection refused"))
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
            patch.dict("homelab_mcp.proxmox_api._HOST_CLUSTER_CACHE", {}, clear=True),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["counts"]["unreachable"] == 1
        record = result["unreachable"][0]
        assert record["status"] == "missing", (
            f"DRFT-18: 12d-old last_seen + probe failure must promote to 'missing'; got status={record['status']!r}"
        )
        assert "last_seen" in record, "missing record must surface last_seen field"
        assert "decommission_device" in record["message"], (
            f"missing message must point at decommission_device; got: {record['message']!r}"
        )

    @pytest.mark.asyncio
    async def test_recent_unreachable_not_promoted(
        self,
        sitemap_row_recent_last_seen: dict[str, object],
    ) -> None:
        """Probe fails BUT last_seen 1d < 7d threshold → status='unreachable'."""
        db_adapter = MagicMock()
        row = dict(sitemap_row_recent_last_seen)
        row["proxmox_credential_id"] = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        row["ssh_credential_id"] = None
        db_adapter.get_all_devices.return_value = [row]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()
            client.get = AsyncMock(side_effect=aiohttp.ClientError("connection refused"))
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
            patch.dict("homelab_mcp.proxmox_api._HOST_CLUSTER_CACHE", {}, clear=True),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["counts"]["unreachable"] == 1
        assert result["unreachable"][0]["status"] == "unreachable", (
            f"DRFT-18: recent last_seen must NOT promote to missing; got: {result['unreachable'][0]['status']!r}"
        )

    @pytest.mark.asyncio
    async def test_threshold_env_var_override(
        self,
        freeze_now: datetime,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS=3`` + 5d-old last_seen → missing."""
        from datetime import timedelta

        monkeypatch.setenv("HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS", "3")
        naive_now = freeze_now.replace(tzinfo=None)
        row = {
            "hostname": "stale-host",
            "connection_ip": "10.0.0.50",
            "status": "success",
            "proxmox_credential_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            "ssh_credential_id": None,
            "last_seen": (naive_now - timedelta(days=5)).isoformat(),
            "fingerprint": {},
        }
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [row]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()
            client.get = AsyncMock(side_effect=aiohttp.ClientError("timeout"))
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
            patch.dict("homelab_mcp.proxmox_api._HOST_CLUSTER_CACHE", {}, clear=True),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["unreachable"][0]["status"] == "missing", (
            f"D-02: env override threshold=3 + 5d last_seen must promote; got: {result['unreachable'][0]['status']!r}"
        )

    @pytest.mark.asyncio
    async def test_threshold_env_var_invalid_uses_default(
        self,
        freeze_now: datetime,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Invalid env var → falls back to default 7d; 5d-old stays unreachable."""
        from datetime import timedelta

        monkeypatch.setenv("HOMELAB_DRIFT_MISSING_THRESHOLD_DAYS", "abc")
        naive_now = freeze_now.replace(tzinfo=None)
        row = {
            "hostname": "stale-host",
            "connection_ip": "10.0.0.50",
            "status": "success",
            "proxmox_credential_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
            "ssh_credential_id": None,
            "last_seen": (naive_now - timedelta(days=5)).isoformat(),
            "fingerprint": {},
        }
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [row]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()
            client.get = AsyncMock(side_effect=aiohttp.ClientError("timeout"))
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
            patch.dict("homelab_mcp.proxmox_api._HOST_CLUSTER_CACHE", {}, clear=True),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        # Invalid env → default 7d; 5d-old < 7d → unreachable, NOT missing.
        assert result["unreachable"][0]["status"] == "unreachable", (
            f"T-39-01: invalid threshold env var must fall back to 7d default; "
            f"got: {result['unreachable'][0]['status']!r}"
        )


class TestPhase39Changed:
    """Phase 39 D-08/D-09a + DRFT-19: changed-bucket via universal-core diff.

    A host whose live universal-core fingerprint (kernel/os/package, optionally
    capabilities) differs from its stored sitemap fingerprint lands in
    ``changed[]`` with per-field diffs in a ``changed_fields`` dict-of-dicts
    (dotted-path keys). Hosts whose probe matches stored stay in ``probed_ok``.
    """

    @pytest.mark.asyncio
    async def test_kernel_change_in_changed_bucket(
        self,
        sitemap_row_with_stored_fingerprint: dict[str, object],
        mock_universal_core_probe_drifted: dict[str, object],
    ) -> None:
        """Stored 6.5.13-1-pve vs current 6.8.4-2-pve → host in changed[]."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [sitemap_row_with_stored_fingerprint]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()

            async def _get(path: str) -> object:
                if path == "/cluster/status":
                    return [{"type": "node", "name": host}]
                if path == "/cluster/resources":
                    return []
                raise AssertionError(f"unexpected path: {path}")

            client.get = AsyncMock(side_effect=_get)
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
            patch(
                "homelab_mcp.drift_detection._bulk_universal_core_probes",
                AsyncMock(
                    return_value={
                        # Phase 42 B1: probe map keyed on
                        # (hostname, ssh_credential_id) tuple — matches the
                        # row's ssh_credential_id from
                        # sitemap_row_with_stored_fingerprint fixture.
                        ("pve1", "22222222-2222-2222-2222-222222222222"): {
                            "fingerprint": mock_universal_core_probe_drifted,
                            "partial": False,
                            "timed_out_commands": [],
                        }
                    }
                ),
            ),
            patch.dict("homelab_mcp.proxmox_api._HOST_CLUSTER_CACHE", {}, clear=True),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["counts"]["changed"] == 1, (
            f"DRFT-19: drifted fingerprint must land host in changed[]; got "
            f"changed={result['changed']}, probed_ok={result['probed_ok']}"
        )
        assert result["counts"]["probed_ok"] == 0, "host must NOT be in probed_ok"
        record = result["changed"][0]
        assert record["status"] == "changed"
        assert record["changed_fields"]["kernel_version"] == {
            "stored": "6.5.13-1-pve",
            "current": "6.8.4-2-pve",
        }, f"unexpected kernel_version diff: {record['changed_fields']}"

    @pytest.mark.asyncio
    async def test_no_diff_stays_probed_ok(
        self,
        sitemap_row_with_stored_fingerprint: dict[str, object],
        mock_universal_core_probe_response: dict[str, object],
    ) -> None:
        """Probe returns IDENTICAL fingerprint → host stays in probed_ok."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [sitemap_row_with_stored_fingerprint]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()

            async def _get(path: str) -> object:
                if path == "/cluster/status":
                    return [{"type": "node", "name": host}]
                if path == "/cluster/resources":
                    return []
                raise AssertionError(f"unexpected path: {path}")

            client.get = AsyncMock(side_effect=_get)
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
            patch(
                "homelab_mcp.drift_detection._bulk_universal_core_probes",
                AsyncMock(
                    return_value={
                        "pve1": {
                            "fingerprint": mock_universal_core_probe_response,
                            "partial": False,
                            "timed_out_commands": [],
                        }
                    }
                ),
            ),
            patch.dict("homelab_mcp.proxmox_api._HOST_CLUSTER_CACHE", {}, clear=True),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["counts"]["changed"] == 0
        assert result["counts"]["probed_ok"] == 1

    @pytest.mark.asyncio
    async def test_capability_only_in_stored_does_not_diff(
        self,
        sitemap_row_with_stored_fingerprint: dict[str, object],
        mock_universal_core_probe_response: dict[str, object],
    ) -> None:
        """Stored has capabilities.vulkan; current has universal-core only.

        D-09a: leaf-level present-in-both check — capability sub-keys absent
        from current must NOT appear in changed_fields. Host stays in
        probed_ok with empty changed_fields.
        """
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [sitemap_row_with_stored_fingerprint]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()

            async def _get(path: str) -> object:
                if path == "/cluster/status":
                    return [{"type": "node", "name": host}]
                if path == "/cluster/resources":
                    return []
                raise AssertionError(f"unexpected path: {path}")

            client.get = AsyncMock(side_effect=_get)
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
            patch(
                "homelab_mcp.drift_detection._bulk_universal_core_probes",
                AsyncMock(
                    return_value={
                        "pve1": {
                            # Universal-core only — no `capabilities` sub-tree.
                            "fingerprint": mock_universal_core_probe_response,
                            "partial": False,
                            "timed_out_commands": [],
                        }
                    }
                ),
            ),
            patch.dict("homelab_mcp.proxmox_api._HOST_CLUSTER_CACHE", {}, clear=True),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["counts"]["changed"] == 0, (
            f"D-09a: capabilities present only in stored must not surface as diff; got changed={result['changed']}"
        )
        assert result["counts"]["probed_ok"] == 1

    @pytest.mark.asyncio
    async def test_drift_does_not_update_fingerprint(
        self,
        sitemap_row_with_stored_fingerprint: dict[str, object],
        mock_universal_core_probe_drifted: dict[str, object],
    ) -> None:
        """D-04b: drift NEVER calls db_adapter.update_device_fingerprint."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [sitemap_row_with_stored_fingerprint]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()

            async def _get(path: str) -> object:
                if path == "/cluster/status":
                    return [{"type": "node", "name": host}]
                if path == "/cluster/resources":
                    return []
                raise AssertionError(f"unexpected path: {path}")

            client.get = AsyncMock(side_effect=_get)
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
            patch(
                "homelab_mcp.drift_detection._bulk_universal_core_probes",
                AsyncMock(
                    return_value={
                        "pve1": {
                            "fingerprint": mock_universal_core_probe_drifted,
                            "partial": False,
                            "timed_out_commands": [],
                        }
                    }
                ),
            ),
            patch.dict("homelab_mcp.proxmox_api._HOST_CLUSTER_CACHE", {}, clear=True),
        ):
            await scan_drift(session=None, db_adapter=db_adapter)

        assert db_adapter.update_device_fingerprint.call_count == 0, (
            "D-04b: drift must NEVER write to devices.fingerprint; "
            f"got call_count={db_adapter.update_device_fingerprint.call_count}"
        )

    @pytest.mark.asyncio
    async def test_changed_field_dotted_path_for_capabilities(
        self,
        mock_universal_core_probe_response: dict[str, object],
    ) -> None:
        """Stored AND current both have capabilities.vulkan.available — diff
        emits the dotted-path key with stored=True, current=False."""
        stored_fp = dict(mock_universal_core_probe_response)
        stored_fp["capabilities"] = {"vulkan": {"available": True}}
        current_fp = dict(mock_universal_core_probe_response)
        current_fp["capabilities"] = {"vulkan": {"available": False}}

        row = {
            "hostname": "pve1",
            "connection_ip": "10.0.0.10",
            "status": "success",
            "proxmox_credential_id": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
            "ssh_credential_id": "ffffffff-ffff-4fff-8fff-ffffffffffff",
            "last_seen": "2026-04-27T11:00:00",
            "fingerprint": stored_fp,
        }
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [row]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()

            async def _get(path: str) -> object:
                if path == "/cluster/status":
                    return [{"type": "node", "name": host}]
                if path == "/cluster/resources":
                    return []
                raise AssertionError(f"unexpected path: {path}")

            client.get = AsyncMock(side_effect=_get)
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
            patch(
                "homelab_mcp.drift_detection._bulk_universal_core_probes",
                AsyncMock(
                    return_value={
                        # Phase 42 B1: probe map keyed on
                        # (hostname, ssh_credential_id) tuple — matches the
                        # row's ssh_credential_id literal defined inline above.
                        ("pve1", "ffffffff-ffff-4fff-8fff-ffffffffffff"): {
                            "fingerprint": current_fp,
                            "partial": False,
                            "timed_out_commands": [],
                        }
                    }
                ),
            ),
            patch.dict("homelab_mcp.proxmox_api._HOST_CLUSTER_CACHE", {}, clear=True),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["counts"]["changed"] == 1
        diffs = result["changed"][0]["changed_fields"]
        assert "capabilities.vulkan.available" in diffs, (
            f"D-08: dotted-path key must appear when both sides have leaf; got keys: {list(diffs.keys())}"
        )
        assert diffs["capabilities.vulkan.available"]["stored"] is True
        assert diffs["capabilities.vulkan.available"]["current"] is False


class TestPhase39Bucket:
    """Phase 39 D-10: bucket-priority + scanned-invariant guarantees.

    - ``scanned == sum(counts.values())`` holds across all 5 buckets + unknown.
    - ``unknown[]`` is a parallel per-VM surface independent of host buckets.
    - Bucket priority preserved: not_eligible > unreachable (sub-states) >
      changed > probed_ok.
    """

    @pytest.mark.asyncio
    async def test_scanned_equals_counts_sum(
        self,
        sitemap_row_with_stored_fingerprint: dict[str, object],
        mock_universal_core_probe_drifted: dict[str, object],
    ) -> None:
        """Mixed sitemap covering changed + probed_ok + unreachable + not_eligible
        plus 1 unknown VM → scanned == sum(counts.values())."""
        # 4-row sitemap touching 4 host buckets.
        rows = [
            # 1) probed_ok with NO drift (same fingerprint) and 1 unknown VM in cluster
            {
                "hostname": "pve-ok",
                "connection_ip": "10.0.0.10",
                "status": "success",
                "proxmox_credential_id": "11111111-1111-4111-8111-111111111111",
                "ssh_credential_id": None,
                "fingerprint": {},
            },
            # 2) changed (stored fingerprint differs from probe)
            sitemap_row_with_stored_fingerprint,
            # 3) unreachable (probe raises aiohttp.ClientError; recent last_seen)
            {
                "hostname": "pve-down",
                "connection_ip": "10.0.0.20",
                "status": "success",
                "proxmox_credential_id": "33333333-3333-4333-8333-333333333333",
                "ssh_credential_id": None,
                "last_seen": "2026-04-27T10:00:00",
                "fingerprint": {},
            },
            # 4) not_eligible (no proxmox binding → unbound)
            {
                "hostname": "truenas",
                "connection_ip": "10.0.0.30",
                "status": "success",
                "proxmox_credential_id": None,
                "ssh_credential_id": None,
                "fingerprint": {},
            },
        ]
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = rows

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()
            if host == "pve-down":
                client.get = AsyncMock(side_effect=aiohttp.ClientError("connection refused"))
                return client
            if host == "truenas":
                raise CredentialNotFoundError("no creds for truenas")

            async def _get(path: str) -> object:
                if path == "/cluster/status":
                    return [{"type": "node", "name": host}]
                if path == "/cluster/resources":
                    if host == "pve-ok":
                        return [
                            {
                                "type": "qemu",
                                "vmid": 100,
                                "name": "rogue-vm",
                                "node": "pve-ok",
                                "status": "running",
                            }
                        ]
                    return []
                raise AssertionError(f"unexpected path: {path}")

            client.get = AsyncMock(side_effect=_get)
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
            patch(
                "homelab_mcp.drift_detection._bulk_universal_core_probes",
                AsyncMock(
                    return_value={
                        "pve1": {
                            "fingerprint": mock_universal_core_probe_drifted,
                            "partial": False,
                            "timed_out_commands": [],
                        }
                    }
                ),
            ),
            patch.dict("homelab_mcp.proxmox_api._HOST_CLUSTER_CACHE", {}, clear=True),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["scanned"] == sum(result["counts"].values()), (
            f"D-10 invariant: scanned must equal sum(counts); scanned={result['scanned']}, counts={result['counts']}"
        )

    @pytest.mark.asyncio
    async def test_changed_host_with_unknown_vms(
        self,
        sitemap_row_with_stored_fingerprint: dict[str, object],
        mock_universal_core_probe_drifted: dict[str, object],
    ) -> None:
        """Drifted host yields counts.changed=1 AND counts.unknown=1 — parallel
        surfaces per D-10."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [sitemap_row_with_stored_fingerprint]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()

            async def _get(path: str) -> object:
                if path == "/cluster/status":
                    return [{"type": "node", "name": host}]
                if path == "/cluster/resources":
                    return [
                        {
                            "type": "qemu",
                            "vmid": 999,
                            "name": "rogue-vm",
                            "node": "pve1",
                            "status": "running",
                        },
                    ]
                raise AssertionError(f"unexpected path: {path}")

            client.get = AsyncMock(side_effect=_get)
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
            patch(
                "homelab_mcp.drift_detection._bulk_universal_core_probes",
                AsyncMock(
                    return_value={
                        # Phase 42 B1: probe map keyed on
                        # (hostname, ssh_credential_id) tuple — matches the
                        # row's ssh_credential_id from
                        # sitemap_row_with_stored_fingerprint fixture.
                        ("pve1", "22222222-2222-2222-2222-222222222222"): {
                            "fingerprint": mock_universal_core_probe_drifted,
                            "partial": False,
                            "timed_out_commands": [],
                        }
                    }
                ),
            ),
            patch.dict("homelab_mcp.proxmox_api._HOST_CLUSTER_CACHE", {}, clear=True),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["counts"]["changed"] == 1
        assert result["counts"]["unknown"] == 1, (
            f"D-10: unknown[] must be populated independently of changed[]; got: {result['unknown']}"
        )

    @pytest.mark.asyncio
    async def test_bucket_priority_unreachable_over_changed(
        self,
        sitemap_row_with_stored_fingerprint: dict[str, object],
        mock_universal_core_probe_drifted: dict[str, object],
    ) -> None:
        """Probe fails (aiohttp.ClientError) AND stored fingerprint exists →
        host lands in unreachable[], NOT changed[] (D-10 priority)."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [sitemap_row_with_stored_fingerprint]

        async def fake_get_client(host, *, dial_host=None, session=None, credential_id=None):
            client = MagicMock()
            client.get = AsyncMock(side_effect=aiohttp.ClientError("api down"))
            return client

        async def fake_resolve(host, session=None, *, credential_id=None):
            return ("token@node", "node", None)

        # Even though SSH pre-pass would offer a drifted fingerprint, the probe
        # failure on /cluster/status takes priority — host must be unreachable.
        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
            patch(
                "homelab_mcp.drift_detection._bulk_universal_core_probes",
                AsyncMock(
                    return_value={
                        "pve1": {
                            "fingerprint": mock_universal_core_probe_drifted,
                            "partial": False,
                            "timed_out_commands": [],
                        }
                    }
                ),
            ),
            patch.dict("homelab_mcp.proxmox_api._HOST_CLUSTER_CACHE", {}, clear=True),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["counts"]["unreachable"] == 1
        assert result["counts"]["changed"] == 0, (
            f"D-10 priority: probe failure must dominate fingerprint diff; got changed={result['changed']}"
        )
