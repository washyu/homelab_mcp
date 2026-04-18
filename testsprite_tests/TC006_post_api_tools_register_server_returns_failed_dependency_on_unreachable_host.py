import requests


def test_post_api_tools_register_server_unreachable_host():
    base_url = "http://localhost:8080"
    url = f"{base_url}/api/tools/register_server"
    payload = {"hostname": "unreachable-host", "username": "admin", "password": "dummy"}
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
    except requests.RequestException as e:
        assert False, f"Request failed unexpectedly: {e}"

    assert response.status_code == 424, f"Expected status code 424, got {response.status_code}"
    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    # Validate required fields for failed_dependency response
    expected_fields = {"status", "host", "port", "protocol", "requires"}
    assert data.get("status") == "failed_dependency", f"Expected status 'failed_dependency', got {data.get('status')}"
    assert data.get("host") == payload["hostname"], f"Expected host '{payload['hostname']}', got {data.get('host')}"
    assert data.get("port") == 22, f"Expected port 22, got {data.get('port')}"
    assert data.get("protocol") == "SSH", f"Expected protocol 'SSH', got {data.get('protocol')}"
    assert isinstance(data.get("requires"), str) and len(data.get("requires")) > 0, "Field 'requires' missing or empty"


test_post_api_tools_register_server_unreachable_host()
