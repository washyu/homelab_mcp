import requests


def test_post_api_tools_setup_mcp_admin_missing_hostname():
    url = "http://localhost:8080/api/tools/setup_mcp_admin"
    headers = {"Content-Type": "application/json"}
    payload = {}  # Missing 'hostname' field intentionally

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        assert response.status_code in (400, 422), f"Expected status 400 or 422 but got {response.status_code}"

        data = response.json()
        assert "status" in data and data["status"] == "error", "Response status is not 'error'"
        assert "tool" in data and data["tool"] == "setup_mcp_admin", "Response tool field is incorrect or missing"

        error_msg = data.get("error", "")
        assert ("hostname" in error_msg.lower()) or ("missing required field" in error_msg.lower()), (
            "Error message does not indicate missing required field 'hostname'"
        )

    except requests.RequestException as e:
        assert False, f"Request failed: {e}"


test_post_api_tools_setup_mcp_admin_missing_hostname()
