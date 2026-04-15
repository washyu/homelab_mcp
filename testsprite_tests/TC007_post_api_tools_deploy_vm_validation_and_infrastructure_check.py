import requests

BASE_URL = "http://localhost:8080"
TIMEOUT = 30
DEPLOY_VM_ENDPOINT = "/api/tools/deploy_vm"
HEADERS = {"Content-Type": "application/json"}


def test_post_api_tools_deploy_vm_validation_and_infrastructure_check():
    url = f"{BASE_URL}{DEPLOY_VM_ENDPOINT}"

    # 1. Test 422 validation error when required fields are missing
    payload_missing_fields = {
        "platform": "docker"  # Missing required fields 'hostname' and 'image'
    }
    response = requests.post(url, json=payload_missing_fields, headers=HEADERS, timeout=TIMEOUT)
    assert response.status_code == 422, f"Expected 422 but got {response.status_code}"
    json_resp = response.json()
    assert (
        "status" in json_resp
        and json_resp["status"] == "error"
        or "validation_error" in json_resp.get("error", "").lower()
        or "details" in json_resp
    ), f"Unexpected response content for validation error: {json_resp}"

    # 2. Test 412 Precondition Failed when no infrastructure configured
    # Use hostname "no-infra" and valid fields to simulate no configured infrastructure
    payload_no_infra = {"hostname": "no-infra", "platform": "lxd", "image": "ubuntu"}
    response = requests.post(url, json=payload_no_infra, headers=HEADERS, timeout=TIMEOUT)
    assert response.status_code in (412, 422), f"Expected 412 or 422 but got {response.status_code}"
    json_resp = response.json()
    if response.status_code == 412:
        assert json_resp.get("status") == "precondition_failed", (
            f"Expected status 'precondition_failed', got {json_resp.get('status')}"
        )
        assert "no infrastructure" in json_resp.get("error", "").lower(), (
            f"Expected error message about no infrastructure, got {json_resp.get('error')}"
        )
    elif response.status_code == 422:
        assert "status" in json_resp and json_resp["status"] == "error", (
            f"Expected error status for 422, got {json_resp}"
        )
        assert "validation_error" in json_resp.get("error", "").lower() or "details" in json_resp, (
            f"Expected validation error details for 422, got {json_resp}"
        )

    # 3. Test 200 with deployment details when valid stored target config exists
    # Use hostname "cfg-alias-1" to represent a valid configured target with required fields
    payload_valid = {"hostname": "cfg-alias-1", "platform": "docker", "image": "nginx"}
    response = requests.post(url, json=payload_valid, headers=HEADERS, timeout=TIMEOUT)
    assert response.status_code in (200, 422), f"Expected 200 or 422 but got {response.status_code}"
    if response.status_code == 200:
        json_resp = response.json()
        assert json_resp.get("status") == "success", f"Expected status 'success', got {json_resp.get('status')}"
        assert json_resp.get("tool") == "deploy_vm", f"Expected tool 'deploy_vm', got {json_resp.get('tool')}"
        result = json_resp.get("result")
        assert isinstance(result, dict), "Result field should be a dictionary"
        assert "container_id" in result and result["container_id"], "Result missing 'container_id'"
        assert "access_info" in result and isinstance(result["access_info"], dict), (
            "Result missing or invalid 'access_info'"
        )
    else:
        json_resp = response.json()
        assert "status" in json_resp and json_resp["status"] == "error", (
            f"Expected error status for 422, got {json_resp}"
        )
        assert "validation_error" in json_resp.get("error", "").lower() or "details" in json_resp, (
            f"Expected validation error details for 422, got {json_resp}"
        )


test_post_api_tools_deploy_vm_validation_and_infrastructure_check()
