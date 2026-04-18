import requests


def test_get_health_endpoint_returns_server_status():
    url = "http://localhost:8080/health"
    try:
        response = requests.get(url, timeout=30)
        # Acceptable status codes: 200 or 424 (due to external dependencies)
        assert response.status_code in (200, 424), f"Unexpected status code {response.status_code}"
        json_data = response.json()
        assert isinstance(json_data, dict), "Response is not a JSON object"
        status = json_data.get("status")
        # For GET /health with no external dependency, expect 200 and status=success
        if response.status_code == 200:
            assert status == "success", f"Expected status 'success', got '{status}'"
            result = json_data.get("result")
            assert isinstance(result, dict), "'result' field missing or not a dict"
            # Verify required fields in result
            expected_fields = [
                "server_status",
                "uptime_seconds",
                "total_requests",
                "total_errors",
                "error_rate",
                "transport",
            ]
            for field in expected_fields:
                assert field in result, f"Missing field '{field}' in result"
            # Validate types: uptime_seconds (int/float), total_requests (int), total_errors (int), error_rate (float), transport (str)
            assert isinstance(result["uptime_seconds"], (int, float)), "'uptime_seconds' is not number"
            assert isinstance(result["total_requests"], int), "'total_requests' is not int"
            assert isinstance(result["total_errors"], int), "'total_errors' is not int"
            assert isinstance(result["error_rate"], (float, int)), "'error_rate' is not float/int"
            assert isinstance(result["transport"], str), "'transport' is not string"
        elif response.status_code == 424:
            # For 424 Failed Dependency, assert error details exist in response as per instructions.
            assert status == "failed_dependency", f"Expected status 'failed_dependency', got '{status}'"
            required_fields = {"host", "port", "protocol", "requires"}
            missing = required_fields - json_data.keys()
            assert not missing, f"Missing fields in 424 response: {missing}"
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"


test_get_health_endpoint_returns_server_status()
