import requests

BASE_URL = "http://localhost:8080"
TIMEOUT = 30


def test_post_api_tools_ssh_discover_unreachable_host_returns_failed_dependency():
    url = f"{BASE_URL}/api/tools/ssh_discover"
    payload = {
        "hostname": "10.0.0.254"  # Unreachable host expected to trigger 424
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"Request to {url} failed with exception: {e}"

    # According to instructions, 424 is expected for unreachable host scenario
    assert response.status_code == 424, f"Expected status code 424, got {response.status_code}"

    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # Validate required fields for failed_dependency response
    assert data.get("status") == "failed_dependency", f"Expected status 'failed_dependency', got {data.get('status')}"
    assert "host" in data, "Response missing 'host' field"
    assert data["host"] == payload["hostname"], (
        f"Response host '{data.get('host')}' does not match request hostname '{payload['hostname']}'"
    )
    assert "port" in data, "Response missing 'port' field"
    assert data["port"] == 22, f"Expected port 22 for SSH, got {data.get('port')}"
    assert "protocol" in data, "Response missing 'protocol' field"
    assert data["protocol"] == "SSH", f"Expected protocol 'SSH', got {data.get('protocol')}"
    assert "requires" in data, "Response missing 'requires' field"
    assert isinstance(data["requires"], str) and data["requires"], "'requires' field should be a non-empty string"
    # 'error' field is optional but typically present
    assert "error" in data and isinstance(data["error"], str), "Response missing or invalid 'error' field"


test_post_api_tools_ssh_discover_unreachable_host_returns_failed_dependency()
