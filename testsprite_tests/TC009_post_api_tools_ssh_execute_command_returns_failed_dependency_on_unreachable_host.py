import requests


def test_post_api_tools_ssh_execute_command_unreachable_host():
    base_url = "http://localhost:8080"
    endpoint = "/api/tools/ssh_execute_command"
    url = base_url + endpoint
    payload = {"hostname": "unreachable.example.com", "command": "uptime"}
    headers = {"Content-Type": "application/json"}
    timeout = 30

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        assert False, f"Request failed with exception: {e}"

    # Expected HTTP 424 Failed Dependency response for unreachable SSH target
    assert response.status_code == 424, f"Expected status code 424 but got {response.status_code}"

    try:
        resp_json = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # Validate required fields in 424 response
    assert resp_json.get("status") == "failed_dependency", (
        f"Expected status 'failed_dependency' but got {resp_json.get('status')}"
    )
    assert resp_json.get("host") == payload["hostname"], (
        f"Expected host '{payload['hostname']}' but got {resp_json.get('host')}"
    )
    assert resp_json.get("port") == 22, f"Expected port 22 but got {resp_json.get('port')}"
    assert resp_json.get("protocol") == "SSH", f"Expected protocol 'SSH' but got {resp_json.get('protocol')}"
    assert "requires" in resp_json and isinstance(resp_json["requires"], str) and resp_json["requires"], (
        "Missing or empty 'requires' field in response"
    )


test_post_api_tools_ssh_execute_command_unreachable_host()
