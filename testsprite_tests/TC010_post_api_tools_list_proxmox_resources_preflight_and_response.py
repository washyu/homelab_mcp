import requests

BASE_URL = "http://localhost:8080"
TIMEOUT = 30
ENDPOINT = "/api/tools/list_proxmox_resources"
URL = BASE_URL + ENDPOINT


def test_post_api_tools_list_proxmox_resources_preflight_and_response():
    # Hosts to test: one assumed unreachable, one assumed reachable or simulated
    unreachable_host = "192.0.2.199"
    reachable_host = "192.0.2.200"

    # Test unreachable host scenario expecting 424 with failed_dependency error
    payload_unreachable = {"host": unreachable_host}
    try:
        resp_unreachable = requests.post(URL, json=payload_unreachable, timeout=TIMEOUT)
        # For unreachable host, 424 expected
        assert resp_unreachable.status_code == 424, (
            f"Expected 424 for unreachable host, got {resp_unreachable.status_code}"
        )
        json_unreachable = resp_unreachable.json()
        assert json_unreachable.get("status") == "failed_dependency", (
            "Status should be 'failed_dependency' for unreachable host"
        )
        assert json_unreachable.get("host") == unreachable_host, "'host' field mismatch in failed_dependency response"
        assert json_unreachable.get("port") == 8006, "Port should be 8006 for Proxmox preflight failure"
        assert json_unreachable.get("protocol") == "Proxmox API", (
            "Protocol should be 'Proxmox API' for preflight failure"
        )
        # 'requires' field should be a non-empty string explaining what's required
        assert isinstance(json_unreachable.get("requires"), str) and json_unreachable["requires"], (
            "'requires' field missing or empty"
        )
    except requests.RequestException as e:
        raise AssertionError(f"Request to unreachable host test failed: {e}")

    # Test reachable host scenario expecting 200 with nodes, vms, and storage keys
    payload_reachable = {"host": reachable_host}
    try:
        resp_reachable = requests.post(URL, json=payload_reachable, timeout=TIMEOUT)
        if resp_reachable.status_code == 424:
            # Preflight failed, treat as expected for no live Proxmox infra in test environment
            json_fail = resp_reachable.json()
            assert json_fail.get("status") == "failed_dependency"
            assert json_fail.get("host") == reachable_host
            assert json_fail.get("port") == 8006
            assert json_fail.get("protocol") == "Proxmox API"
            # Test ends here in this environment without infra
            return
        assert resp_reachable.status_code == 200, f"Expected 200 for reachable host, got {resp_reachable.status_code}"
        json_reachable = resp_reachable.json()
        assert json_reachable.get("status") == "success", "Status should be 'success' for reachable host"
        assert json_reachable.get("tool") == "list_proxmox_resources", "Tool name mismatch in response"
        result = json_reachable.get("result")
        assert isinstance(result, dict), "'result' should be a dictionary"
        # Check presence and type of nodes, vms, storage in result
        for key in ("nodes", "vms", "storage"):
            assert key in result, f"'{key}' key missing in result"
            assert isinstance(result[key], list), f"'{key}' should be a list"
    except requests.RequestException as e:
        raise AssertionError(f"Request to reachable host test failed: {e}")


test_post_api_tools_list_proxmox_resources_preflight_and_response()
