"""Tests for drift detection — Phase 36/37 (sitemap-as-baseline, 4-bucket stable shape)."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homelab_mcp.drift_detection import scan_drift
from homelab_mcp.proxmox_api import CredentialNotFoundError


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
        """3-row sitemap: pve1 -> probed_ok, truenas1 -> silently skipped, pi-lab -> unreachable."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"},
            {"hostname": "truenas1", "connection_ip": "10.0.0.11", "status": "success"},
            {"hostname": "pi-lab", "connection_ip": "10.0.0.12", "status": "success"},
        ]

        async def fake_get_client(host, session=None):
            if host == "pve1":
                client = MagicMock()
                client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
                return client
            if host == "truenas1":
                raise CredentialNotFoundError(f"no creds for {host}")
            if host == "pi-lab":
                client = MagicMock()
                client.get = AsyncMock(side_effect=aiohttp.ClientError("connection refused to pve.home"))
                return client
            raise AssertionError(f"unexpected host: {host}")

        async def fake_resolve(host, session=None):
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
        assert result["scanned"] == 2  # pve1 + pi-lab; truenas1 silently skipped
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
        all_hostnames = [r["hostname"] for r in result["probed_ok"] + result["unreachable"]]
        assert "truenas1" not in all_hostnames

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
        """D-10a: rows with status=='error' OR hostname in ('', 'unknown', None) skipped pre-resolve."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "", "connection_ip": "10.0.0.1", "status": "success"},
            {"hostname": "unknown", "connection_ip": "10.0.0.2", "status": "success"},
            {"hostname": None, "connection_ip": "10.0.0.3", "status": "success"},
            {"hostname": "errored-host", "connection_ip": "10.0.0.4", "status": "error"},
        ]

        # If degenerate-skip works, get_proxmox_client is never called
        with patch("homelab_mcp.drift_detection.get_proxmox_client") as mock_client:
            result = await scan_drift(session=None, db_adapter=db_adapter)

        mock_client.assert_not_called()
        assert result["scanned"] == 0
        assert result["probed_ok"] == []
        assert result["unreachable"] == []

    @pytest.mark.asyncio
    async def test_silent_skip_on_credential_not_found(self):
        """D-10: CredentialNotFoundError on get_proxmox_client -> row excluded from both buckets."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "not-a-proxmox-host", "connection_ip": "10.0.0.1", "status": "success"},
        ]

        async def fake_get_client(host, session=None):
            raise CredentialNotFoundError("no proxmox creds")

        with patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["scanned"] == 0
        assert result["probed_ok"] == []
        assert result["unreachable"] == []

    @pytest.mark.asyncio
    async def test_unreachable_error_is_sanitized(self):
        """D-09a: probe exception messages pass through sanitize_error."""
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "leaky", "connection_ip": "10.0.0.1", "status": "success"},
        ]

        async def fake_get_client(host, session=None):
            client = MagicMock()
            # Simulate an exception that contains a "secret-looking" token
            client.get = AsyncMock(
                side_effect=aiohttp.ClientError("connection refused (token=PVEAPIToken=user@pam!id=secretsecret)")
            )
            return client

        async def fake_resolve(host, session=None):
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

        async def fake_get_client(host, session=None):
            client = MagicMock()
            client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
            return client

        async def fake_resolve(host, session=None):
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
        """D-07: response['counts'] has exactly four keys, each equal to len(bucket).

        In Phase 37, counts['unknown'] == 0 and counts['changed'] == 0 always
        (the buckets are reserved-empty per D-05/D-06).
        """
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"},
            {"hostname": "pi-lab", "connection_ip": "10.0.0.12", "status": "success"},
        ]

        async def fake_get_client(host, session=None):
            if host == "pve1":
                client = MagicMock()
                client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
                return client
            client = MagicMock()
            client.get = AsyncMock(side_effect=aiohttp.ClientError("connection refused"))
            return client

        async def fake_resolve(host, session=None):
            return ("token", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert "counts" in result, f"missing 'counts' key; keys: {list(result.keys())}"
        counts = result["counts"]
        assert isinstance(counts, dict), f"counts is not a dict: {type(counts).__name__}"
        assert set(counts.keys()) == {"probed_ok", "unreachable", "unknown", "changed"}, (
            f"counts has unexpected key set: {set(counts.keys())}"
        )
        assert counts["probed_ok"] == len(result["probed_ok"]) == 1
        assert counts["unreachable"] == len(result["unreachable"]) == 1
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

        async def fake_get_client(host, session=None):
            if host == "pve1":
                client = MagicMock()
                client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
                return client
            client = MagicMock()
            client.get = AsyncMock(side_effect=aiohttp.ClientError("refused"))
            return client

        async def fake_resolve(host, session=None):
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

        Uses the canonical 3-row mock harness from test_three_row_classification
        which yields scanned == 2 (pve1 probed_ok + pi-lab unreachable; truenas1
        silently skipped via CredentialNotFoundError).
        """
        db_adapter = MagicMock()
        db_adapter.get_all_devices.return_value = [
            {"hostname": "pve1", "connection_ip": "10.0.0.10", "status": "success"},
            {"hostname": "truenas1", "connection_ip": "10.0.0.11", "status": "success"},
            {"hostname": "pi-lab", "connection_ip": "10.0.0.12", "status": "success"},
        ]

        async def fake_get_client(host, session=None):
            if host == "pve1":
                client = MagicMock()
                client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
                return client
            if host == "truenas1":
                raise CredentialNotFoundError(f"no creds for {host}")
            client = MagicMock()
            client.get = AsyncMock(side_effect=aiohttp.ClientError("refused"))
            return client

        async def fake_resolve(host, session=None):
            return ("token", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter)

        assert result["scanned"] == 2
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

        async def fake_get_client(host, session=None):
            called_hosts.append(host)
            if host == "pve1":
                client = MagicMock()
                client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
                return client
            raise AssertionError(f"D-01 violation: get_proxmox_client called for non-matching host {host!r}")

        async def fake_resolve(host, session=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter, node="pve1")

        assert called_hosts == ["pve1"], f"D-01 filter failed: expected only pve1 to be probed, got {called_hosts}"
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

        async def fake_get_client(host, session=None):
            called_hosts.append(host)
            client = MagicMock()
            client.get = AsyncMock(return_value=[{"type": "node", "name": host}])
            return client

        async def fake_resolve(host, session=None):
            return ("token@node", "node", None)

        with (
            patch("homelab_mcp.drift_detection.get_proxmox_client", side_effect=fake_get_client),
            patch("homelab_mcp.drift_detection.resolve_proxmox_credentials", side_effect=fake_resolve),
        ):
            result = await scan_drift(session=None, db_adapter=db_adapter, node=None)

        assert sorted(called_hosts) == ["pve1", "pve2"]
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

        async def fake_get_client(host, session=None):
            client = MagicMock()
            client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
            return client

        async def fake_resolve(host, session=None):
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
        """Plan 1 contract: top-level dict insertion order is locked.

        When scanned == 0:
          ['status', 'scan_timestamp', 'scanned', 'counts', 'guidance',
           'probed_ok', 'unreachable', 'unknown', 'changed']

        When scanned > 0 (no 'guidance'):
          ['status', 'scan_timestamp', 'scanned', 'counts',
           'probed_ok', 'unreachable', 'unknown', 'changed']
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

        async def fake_get_client(host, session=None):
            client = MagicMock()
            client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
            return client

        async def fake_resolve(host, session=None):
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

        async def fake_get_client(host, session=None):
            client = MagicMock()
            client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
            return client

        async def fake_resolve(host, session=None):
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

        async def fake_get_client(host, session=None):
            client = MagicMock()
            client.get = AsyncMock(side_effect=aiohttp.ClientError("connection refused"))
            return client

        async def fake_resolve(host, session=None):
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

        async def fake_get_client(host, session=None):
            if host == "pve1":
                client = MagicMock()
                client.get = AsyncMock(return_value=[{"type": "node", "name": "pve1"}])
                return client
            client = MagicMock()
            client.get = AsyncMock(side_effect=aiohttp.ClientError("refused"))
            return client

        async def fake_resolve(host, session=None):
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
