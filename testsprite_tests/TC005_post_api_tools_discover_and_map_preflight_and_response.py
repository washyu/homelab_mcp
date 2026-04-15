import requests

BASE_URL = "http://localhost:8080"
TIMEOUT = 30


def test_post_api_tools_discover_and_map_preflight_and_response():
    url = f"{BASE_URL}/api/tools/discover_and_map"
    headers = {"Content-Type": "application/json"}

    reachable_host = "127.0.0.1"
    unreachable_host = "192.0.2.99"

    payload_reachable = {"hostname": reachable_host}

    try:
        response = requests.post(url, json=payload_reachable, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"Request to {url} with reachable host payload failed: {e}"

    assert response.status_code in (200, 424, 422), (
        f"Unexpected status code {response.status_code} for reachable_host request"
    )
    resp_json = response.json()
    if response.status_code == 200:
        assert resp_json.get("status") == "success", f"Expected status 'success', got: {resp_json.get('status')}"
        assert resp_json.get("tool") == "discover_and_map", (
            f"Expected tool 'discover_and_map', got: {resp_json.get('tool')}"
        )
        result = resp_json.get("result")
        assert isinstance(result, dict), "Expected 'result' to be a dictionary"
        assert "device_id" in result, "'device_id' key missing in result"
        assert "ip" in result, "'ip' key missing in result"
        assert "metadata" in result, "'metadata' key missing in result"
    elif response.status_code == 424:
        assert resp_json.get("status") == "failed_dependency", (
            f"Expected status 'failed_dependency', got: {resp_json.get('status')}"
        )
        assert resp_json.get("host") == reachable_host, (
            f"Expected host '{reachable_host}' in response, got: {resp_json.get('host')}"
        )
        assert resp_json.get("port") == 22, f"Expected port 22 in response, got: {resp_json.get('port')}"
        assert resp_json.get("protocol") == "SSH", f"Expected protocol 'SSH', got: {resp_json.get('protocol')}"
        assert "requires" in resp_json, "'requires' field missing in failed_dependency response"
    else:  # 422 validation error
        assert resp_json.get("status") == "error" or resp_json.get("detail") or resp_json.get("error"), (
            "Expected error details in 422 response"
        )

    payload_unreachable = {"hostname": unreachable_host}
    try:
        response = requests.post(url, json=payload_unreachable, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"Request to {url} with unreachable host payload failed: {e}"

    assert response.status_code in (424, 422), (
        f"Expected status code 424 or 422 for unreachable host, got {response.status_code}"
    )
    resp_json = response.json()
    if response.status_code == 424:
        assert resp_json.get("status") == "failed_dependency", (
            f"Expected status 'failed_dependency' for unreachable host, got: {resp_json.get('status')}"
        )
        assert resp_json.get("host") == unreachable_host, (
            f"Expected host '{unreachable_host}' in failed_dependency response, got: {resp_json.get('host')}"
        )
        assert resp_json.get("port") == 22, (
            f"Expected port 22 in failed_dependency response, got: {resp_json.get('port')}"
        )
        assert resp_json.get("protocol") == "SSH", (
            f"Expected protocol 'SSH' in failed_dependency response, got: {resp_json.get('protocol')}"
        )
        assert "requires" in resp_json, "'requires' field missing in failed_dependency response"
    else:  # 422 validation error fallback
        assert resp_json.get("status") == "error" or resp_json.get("detail") or resp_json.get("error"), (
            "Expected error details in 422 response for unreachable host"
        )


test_post_api_tools_discover_and_map_preflight_and_response()
