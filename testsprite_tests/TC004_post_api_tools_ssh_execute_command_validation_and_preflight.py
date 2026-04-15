import requests
from requests.exceptions import RequestException

BASE_URL = "http://localhost:8080"
TIMEOUT = 30
ENDPOINT = "/api/tools/ssh_execute_command"
URL = BASE_URL + ENDPOINT
HEADERS = {"Content-Type": "application/json"}


def test_post_api_tools_ssh_execute_command_validation_and_preflight():
    # 1. Test missing required fields (e.g., missing hostname)
    payload_missing_hostname = {"command": "uname -a"}
    try:
        resp = requests.post(URL, json=payload_missing_hostname, headers=HEADERS, timeout=TIMEOUT)
        assert resp.status_code == 422, f"Expected 422 for missing hostname, got {resp.status_code}"
        json_resp = resp.json()
        assert "detail" in json_resp or "error" in json_resp, "422 response should have error details"
    except RequestException as e:
        assert False, f"Request failed during missing hostname test: {e}"

    # 2. Test successful TCP preflight to hostname:22 returns 200 with command output
    # Use hostname that likely fails for preflight to trigger 424
    test_host_reachable = "127.0.0.1"  # Assuming localhost:22 is reachable (adjust if needed)
    payload_success = {"hostname": test_host_reachable, "command": "echo test_command_output"}
    try:
        resp = requests.post(URL, json=payload_success, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code == 200:
            json_resp = resp.json()
            assert isinstance(json_resp, dict), "Response should be JSON object"
            assert json_resp.get("status") == "success", f"Expected status 'success', got {json_resp.get('status')}"
            assert "result" in json_resp, "Response should contain 'result' with command output"
            assert isinstance(json_resp["result"], str), "Command output 'result' should be a string"
        elif resp.status_code == 424:
            # If preflight fails, 424 is the expected response
            json_resp = resp.json()
            assert json_resp.get("status") == "failed_dependency", "Status should be 'failed_dependency' for 424"
            assert json_resp.get("host") == test_host_reachable, "Host in response should match requested hostname"
            assert json_resp.get("port") == 22, "Port should be 22 for SSH preflight"
            assert json_resp.get("protocol") == "SSH", "Protocol should be SSH for this endpoint"
            assert "requires" in json_resp, "'requires' field must be present in 424 response"
        else:
            assert False, f"Unexpected status code {resp.status_code} for reachable host test"
    except RequestException as e:
        assert False, f"Request failed during reachable host test: {e}"

    # 3. Test preflight fails and returns 424 for unreachable host
    test_host_unreachable = "192.0.2.254"  # Reserved TEST-NET-2 IP, should be unreachable
    payload_fail_preflight = {"hostname": test_host_unreachable, "command": "ls /"}
    try:
        resp = requests.post(URL, json=payload_fail_preflight, headers=HEADERS, timeout=TIMEOUT)
        assert resp.status_code == 424, f"Expected 424 for unreachable host, got {resp.status_code}"
        json_resp = resp.json()
        assert json_resp.get("status") == "failed_dependency", "Status should be 'failed_dependency' for 424"
        assert json_resp.get("host") == test_host_unreachable, "Host in response should match request"
        assert json_resp.get("port") == 22, "Port should be 22 for SSH preflight"
        assert json_resp.get("protocol") == "SSH", "Protocol should be SSH for this endpoint"
        assert "requires" in json_resp, "'requires' field must be present in 424 response"
    except RequestException as e:
        assert False, f"Request failed during unreachable host test: {e}"


test_post_api_tools_ssh_execute_command_validation_and_preflight()
