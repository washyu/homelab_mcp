import requests

BASE_URL = "http://localhost:8080"
TIMEOUT = 30


def post_api_tools_bulk_discover_and_map_handles_multiple_hosts():
    url = f"{BASE_URL}/api/tools/bulk_discover_and_map"
    # Provide multiple hosts including one that is likely unreachable to test both scenarios
    payload = {
        "hosts": [
            {"hostname": "192.0.2.11"},  # Assume reachable or test behaves correctly if unreachable
            {"hostname": "192.0.2.99"},  # Known unreachable host per PRD example, triggers failure inside results
        ]
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"Request to {url} failed: {e}"

    # The bulk endpoint should return 200 always regardless of host reachability
    assert response.status_code == 200, f"Expected status code 200 but got {response.status_code}"

    data = response.json()
    # Validate that results is a list with entries for each host
    assert "results" in data, "Response missing 'results' field"
    results = data["results"]
    assert isinstance(results, list), "'results' field is not a list"
    assert len(results) == len(payload["hosts"]), (
        f"Expected results for {len(payload['hosts'])} hosts but got {len(results)}"
    )

    # Create sets to track hostnames found and validate each item
    hosts_sent = {host["hostname"] for host in payload["hosts"]}
    hosts_returned = set()

    for result in results:
        # Each result must have hostname and status
        assert "hostname" in result, "Result missing 'hostname'"
        hostname = result["hostname"]
        hosts_returned.add(hostname)
        assert hostname in hosts_sent, f"Unexpected hostname '{hostname}' in results"
        assert "status" in result, f"Result for host {hostname} missing 'status'"

        status = result["status"]
        # Status must be either 'success' or 'failed'
        assert status in ("success", "failed"), f"Invalid status '{status}' for host {hostname}"

        # For host marked success, 'result' field should be present and non-empty dictionary
        if status == "success":
            assert "result" in result, f"Successful host {hostname} missing 'result'"
            assert isinstance(result["result"], dict), f"'result' for host {hostname} is not a dict"
            assert result["result"], f"'result' for host {hostname} is empty"
            # Optional: result may contain device info or discovery data
        else:
            # For failed hosts, 'error' field should be present and a non-empty string
            assert "error" in result, f"Failed host {hostname} missing 'error'"
            error = result["error"]
            assert isinstance(error, str) and error, f"Invalid error message for host {hostname}"

    # All hosts requested must be present in the results
    assert hosts_sent == hosts_returned, "Mismatch between sent hosts and returned hosts"


post_api_tools_bulk_discover_and_map_handles_multiple_hosts()
