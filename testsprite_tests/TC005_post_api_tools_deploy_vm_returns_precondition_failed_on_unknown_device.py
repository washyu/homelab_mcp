import requests

BASE_URL = "http://localhost:8080"
TIMEOUT = 30


def test_post_api_tools_deploy_vm_precondition_failed_on_unknown_device():
    url = f"{BASE_URL}/api/tools/deploy_vm"
    payload = {
        "device_id": 9999,  # Unknown device_id as per test case
        "platform": "docker",
        "vm_name": "web-unknown",
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"Request failed with exception: {e}"

    if response.status_code == 412:
        # Expected precondition_failed response
        try:
            json_resp = response.json()
        except ValueError:
            assert False, "Response is not valid JSON"

        # Assert expected fields and error message indicating device not found or no infrastructure registered
        assert json_resp.get("status") == "precondition_failed", "Expected status 'precondition_failed'"
        assert json_resp.get("tool") == "deploy_vm", "Expected tool 'deploy_vm'"
        error_msg = json_resp.get("error", "").lower()
        assert "device not found" in error_msg or "no infrastructure registered" in error_msg, (
            "Error message does not indicate missing device or infrastructure"
        )
        assert "requires" in json_resp, "Expected 'requires' field in response for precondition failed"
    elif response.status_code == 424:
        # Acceptable in scenarios where TCP preflight unreachable, per instructions
        try:
            json_resp = response.json()
        except ValueError:
            assert False, "Response is not valid JSON"

        assert json_resp.get("status") == "failed_dependency", "Expected status 'failed_dependency' on 424"
        assert "host" in json_resp and "port" in json_resp and "protocol" in json_resp and "requires" in json_resp, (
            "Expected fields missing in 424 failed_dependency response"
        )
    else:
        assert False, f"Unexpected HTTP status code {response.status_code}. Response body: {response.text}"


test_post_api_tools_deploy_vm_precondition_failed_on_unknown_device()
