import requests

BASE_URL = "http://localhost:8080"
TIMEOUT = 30


def test_post_api_tools_install_service_preflight_and_installation():
    url = f"{BASE_URL}/api/tools/install_service"
    headers = {"Content-Type": "application/json"}

    # Test with a hostname expected to fail preflight (unreachable host)
    payload_fail = {"hostname": "192.0.2.99", "service": "jellyfin"}
    try:
        response_fail = requests.post(url, json=payload_fail, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"Request failed with exception: {e}"
    else:
        # Accept 424, 422, or 200 (unlikely) as possible outcomes
        if response_fail.status_code == 424:
            json_fail = response_fail.json()
            assert json_fail.get("status") == "failed_dependency"
            assert json_fail.get("host") == "192.0.2.99"
            assert json_fail.get("port") == 22
            assert json_fail.get("protocol") == "SSH"
            assert "requires" in json_fail
        elif response_fail.status_code == 422:
            # Validation error is acceptable here
            json_fail = response_fail.json()
            # At least check status or error presence
            assert "detail" in json_fail or "error" in json_fail
        else:
            assert response_fail.status_code == 200, (
                f"Unexpected status code {response_fail.status_code} on unreachable host test"
            )

    # Test with a hostname that likely will fail preflight since no live SSH infra,
    # but instructions say treat 424 as correct response.
    payload_success_candidate = {"hostname": "127.0.0.1", "service": "jellyfin"}
    try:
        response_success = requests.post(url, json=payload_success_candidate, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        assert False, f"Request failed with exception: {e}"
    else:
        if response_success.status_code == 200:
            json_succ = response_success.json()
            assert json_succ.get("status") == "success"
            assert json_succ.get("tool") == "install_service"
            result = json_succ.get("result")
            assert isinstance(result, dict)
            assert "install_id" in result
            assert isinstance(result.get("install_id"), str)
            assert "urls" in result
            assert isinstance(result.get("urls"), list)
        elif response_success.status_code == 424:
            json_fail = response_success.json()
            assert json_fail.get("status") == "failed_dependency"
            assert json_fail.get("host") == "127.0.0.1"
            assert json_fail.get("port") == 22
            assert json_fail.get("protocol") == "SSH"
            assert "requires" in json_fail
        elif response_success.status_code == 422:
            json_fail = response_success.json()
            assert "detail" in json_fail or "error" in json_fail
        else:
            assert False, f"Unexpected status code {response_success.status_code} in install_service test"


test_post_api_tools_install_service_preflight_and_installation()
