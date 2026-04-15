import requests

BASE_URL = "http://localhost:8080"
TIMEOUT = 30


def test_post_api_tools_scan_infrastructure_drift_no_baseline():
    url = f"{BASE_URL}/api/tools/scan_infrastructure_drift"
    # Use a hostname that is expected to have no baseline or no PROXMOX_HOST configured
    payload = {"hostname": "no-baseline-host"}
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"

    # Acceptable expected statuses: 412 precondition_failed or 424 failed_dependency if unreachable
    if response.status_code == 412:
        json_resp = response.json()
        assert json_resp.get("status") == "precondition_failed", (
            f"Expected status 'precondition_failed', got {json_resp.get('status')}"
        )
        assert json_resp.get("tool") == "scan_infrastructure_drift"
        error_msg = json_resp.get("error", "")
        err_lower = error_msg.lower()
        assert "no baseline" in err_lower or "proxmox_host" in err_lower, f"Unexpected error message: {error_msg}"
    elif response.status_code == 424:
        json_resp = response.json()
        assert json_resp.get("status") == "failed_dependency"
        assert json_resp.get("host") == payload["hostname"]
        assert "port" in json_resp
        assert "protocol" in json_resp
        assert "requires" in json_resp
    else:
        assert False, f"Unexpected response status code: {response.status_code}, response: {response.text}"


test_post_api_tools_scan_infrastructure_drift_no_baseline()
