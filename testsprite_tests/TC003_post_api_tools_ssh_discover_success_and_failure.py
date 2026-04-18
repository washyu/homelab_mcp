import requests

BASE_URL = "http://localhost:8080"
SSH_DISCOVER_ENDPOINT = "/api/tools/ssh_discover"
TIMEOUT = 30


def test_post_api_tools_ssh_discover_success_and_failure():
    headers = {"Content-Type": "application/json"}

    # Test case 1: Successful TCP preflight to port 22 (likely unreachable but treat 424 as valid)
    # Using hostname that presumably is reachable: "192.0.2.10" as per PRD example
    payload_success = {"hostname": "192.0.2.10", "username": "root"}

    try:
        response = requests.post(
            BASE_URL + SSH_DISCOVER_ENDPOINT,
            json=payload_success,
            headers=headers,
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        assert False, f"Request to {SSH_DISCOVER_ENDPOINT} failed unexpectedly: {e}"

    if response.status_code == 200:
        # Expected success response structure
        json_data = response.json()
        assert json_data.get("status") == "success"
        assert json_data.get("tool") == "ssh_discover"
        assert isinstance(json_data.get("result"), dict)
    elif response.status_code == 424:
        # Expected when TCP preflight fails to the given host
        json_data = response.json()
        assert json_data.get("status") == "failed_dependency"
        assert json_data.get("host") == "192.0.2.10"
        assert json_data.get("port") == 22
        assert json_data.get("protocol") == "SSH"
        # 'requires' field must be present as per spec
        assert "requires" in json_data
    else:
        assert False, f"Unexpected status code {response.status_code} for successful preflight test"

    # Test case 2: Failed TCP preflight
    # Using hostname that presumably is unreachable: "192.0.2.99" as per PRD example
    payload_failure = {"hostname": "192.0.2.99"}

    try:
        response = requests.post(
            BASE_URL + SSH_DISCOVER_ENDPOINT,
            json=payload_failure,
            headers=headers,
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        assert False, f"Request to {SSH_DISCOVER_ENDPOINT} failed unexpectedly: {e}"

    assert response.status_code == 424, f"Expected HTTP 424 for failed TCP preflight but got {response.status_code}"
    json_data = response.json()
    assert json_data.get("status") == "failed_dependency"
    assert json_data.get("host") == "192.0.2.99"
    assert json_data.get("port") == 22
    assert json_data.get("protocol") == "SSH"
    assert "requires" in json_data


test_post_api_tools_ssh_discover_success_and_failure()
