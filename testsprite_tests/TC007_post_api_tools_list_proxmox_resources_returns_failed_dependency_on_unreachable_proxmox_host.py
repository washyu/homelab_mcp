import requests


def test_post_api_tools_list_proxmox_resources_failed_dependency_unreachable_host():
    base_url = "http://localhost:8080"
    endpoint = "/api/tools/list_proxmox_resources"
    url = base_url + endpoint
    # Use a host known to be unreachable for Proxmox API on port 8006
    payload = {"host": "unreachable-proxmox"}
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
    except requests.RequestException as e:
        assert False, f"Request to {url} failed unexpectedly: {e}"

    # 424 is expected for unreachable Proxmox API host as per instructions
    assert response.status_code == 424, f"Expected status code 424, got {response.status_code}"

    try:
        resp_json = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # Validate expected fields in response for failed_dependency
    expected_status = "failed_dependency"
    assert resp_json.get("status") == expected_status, (
        f"Expected status '{expected_status}', got '{resp_json.get('status')}'"
    )
    assert resp_json.get("host") == payload["host"], f"Expected host '{payload['host']}', got '{resp_json.get('host')}'"
    assert resp_json.get("port") == 8006, f"Expected port 8006, got '{resp_json.get('port')}'"
    assert resp_json.get("protocol") == "Proxmox API", (
        f"Expected protocol 'Proxmox API', got '{resp_json.get('protocol')}'"
    )
    assert "requires" in resp_json and isinstance(resp_json["requires"], str) and resp_json["requires"], (
        "Missing or empty 'requires' field"
    )
    assert "error" in resp_json and isinstance(resp_json["error"], str) and resp_json["error"], (
        "Missing or empty 'error' field"
    )


test_post_api_tools_list_proxmox_resources_failed_dependency_unreachable_host()
