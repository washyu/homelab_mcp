import requests

BASE_URL = "http://localhost:8080"
TIMEOUT = 30


def test_post_api_tools_bulk_discover_and_map_missing_targets_array():
    url = f"{BASE_URL}/api/tools/bulk_discover_and_map"
    headers = {"Content-Type": "application/json"}

    # Test case 1: missing 'targets' field entirely
    payload_missing = {}
    response_missing = requests.post(url, json=payload_missing, headers=headers, timeout=TIMEOUT)
    assert response_missing.status_code == 422, (
        f"Expected status 422 for missing targets, got {response_missing.status_code}"
    )
    json_missing = response_missing.json()
    assert isinstance(json_missing, dict), "Response JSON is not a dictionary"
    assert json_missing.get("status") == "error" or "error" in json_missing, (
        "Expected error status or error field in response"
    )
    # The error message should indicate missing or malformed targets array
    error_msg_missing = json_missing.get("error", "").lower()
    assert "missing" in error_msg_missing or "malformed" in error_msg_missing or "targets" in error_msg_missing, (
        f"Error message does not mention missing or malformed targets array: {error_msg_missing}"
    )

    # Test case 2: 'targets' field empty list
    payload_empty = {"targets": []}
    response_empty = requests.post(url, json=payload_empty, headers=headers, timeout=TIMEOUT)
    assert response_empty.status_code == 422, (
        f"Expected status 422 for empty targets array, got {response_empty.status_code}"
    )
    json_empty = response_empty.json()
    assert isinstance(json_empty, dict), "Response JSON is not a dictionary"
    assert json_empty.get("status") == "error" or "error" in json_empty, (
        "Expected error status or error field in response"
    )
    error_msg_empty = json_empty.get("error", "").lower()
    assert "missing" in error_msg_empty or "malformed" in error_msg_empty or "targets" in error_msg_empty, (
        f"Error message does not mention missing or malformed targets array: {error_msg_empty}"
    )


test_post_api_tools_bulk_discover_and_map_missing_targets_array()
