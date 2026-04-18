import requests

BASE_URL = "http://localhost:8080"
TIMEOUT = 30


def test_post_api_tools_register_server_preflight_and_storage():
    url = f"{BASE_URL}/api/tools/register_server"
    headers = {"Content-Type": "application/json"}

    # Test with an unreachable host (expected 424)
    payload_fail = {"hostname": "192.0.2.99", "username": "admin"}
    try:
        response = requests.post(url, json=payload_fail, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"Request failed unexpectedly: {e}"
    else:
        assert response.status_code == 424, f"Expected 424 for unreachable host, got {response.status_code}"
        json_resp = response.json()
        assert json_resp.get("status") == "failed_dependency"
        assert json_resp.get("host") == payload_fail["hostname"]
        assert json_resp.get("port") == 22
        assert json_resp.get("protocol") == "SSH"
        assert "requires" in json_resp and isinstance(json_resp["requires"], str)

    # Test with a host expected to be unreachable as per instructions (no real live infra)
    # So pick a reserved TEST-NET-1 IP that should fail preflight, so 424 is expected
    # But to test a successful registration case, we simulate by picking localhost with port 22.
    # However, since no live SSH infra, this will likely respond with 424 as well.
    # To follow instructions, treat 424 as expected for unreachable target.
    payload_success = {"hostname": "127.0.0.1", "username": "testuser", "password": "testpassword"}
    try:
        response = requests.post(url, json=payload_success, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"Request failed unexpectedly: {e}"
    else:
        if response.status_code == 200:
            json_resp = response.json()
            assert json_resp.get("status") == "success"
            assert json_resp.get("tool") == "register_server"
            assert json_resp.get("result") == "registered"

            # Cleanup: remove the registered server
            try:
                remove_url = f"{BASE_URL}/api/tools/remove_server"
                remove_payload = {"hostname": payload_success["hostname"], "username": payload_success["username"]}
                remove_resp = requests.post(remove_url, json=remove_payload, headers=headers, timeout=TIMEOUT)
                assert remove_resp.status_code == 200
                remove_json = remove_resp.json()
                assert remove_json.get("status") == "success"
            except requests.RequestException as e:
                assert False, f"Cleanup request failed: {e}"
        elif response.status_code == 424:
            # Expected failure for unreachable target per instructions
            json_resp = response.json()
            assert json_resp.get("status") == "failed_dependency"
            assert json_resp.get("host") == payload_success["hostname"]
            assert json_resp.get("port") == 22
            assert json_resp.get("protocol") == "SSH"
            assert "requires" in json_resp and isinstance(json_resp["requires"], str)
        else:
            assert False, f"Unexpected response code for preflight: {response.status_code}"


test_post_api_tools_register_server_preflight_and_storage()
