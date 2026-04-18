import requests


def test_post_api_tools_ssh_discover_returns_success_on_reachable_host():
    url = "http://localhost:8080/api/tools/ssh_discover"
    # Using a typical local network reachable IP example; no real SSH server needed, expecting either 200 or 424
    payload = {"hostname": "127.0.0.1", "username": "root", "password": "testpass"}
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

    if response.status_code == 200:
        data = response.json()
        assert data.get("status") == "success", f"Expected status 'success', got {data.get('status')}"
        assert data.get("tool") == "ssh_discover", f"Expected tool 'ssh_discover', got {data.get('tool')}"
        result = data.get("result")
        assert isinstance(result, dict), "Result field is missing or not a dict"
        # Validate expected fields in result
        expected_fields = {"cpu", "memory", "disks", "interfaces", "os_version"}
        missing = expected_fields - result.keys()
        assert not missing, f"Missing expected fields in result: {missing}"

    elif response.status_code == 424:
        # Expected for unreachable target per instructions
        data = response.json()
        assert data.get("status") == "failed_dependency", (
            f"Expected status 'failed_dependency', got {data.get('status')}"
        )
        assert data.get("host") == payload["hostname"], f"Expected host {payload['hostname']}, got {data.get('host')}"
        assert data.get("port") == 22, f"Expected port 22, got {data.get('port')}"
        assert data.get("protocol") == "SSH", f"Expected protocol 'SSH', got {data.get('protocol')}"
        # requires field must be present
        assert "requires" in data, "Missing 'requires' field in failed_dependency response"
    else:
        assert False, f"Unexpected HTTP status code: {response.status_code}"


test_post_api_tools_ssh_discover_returns_success_on_reachable_host()
