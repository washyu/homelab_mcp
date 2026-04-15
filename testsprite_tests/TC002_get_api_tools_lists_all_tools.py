import requests


def test_get_api_tools_lists_all_tools():
    base_url = "http://localhost:8080"
    url = f"{base_url}/api/tools"
    headers = {"Accept": "application/json"}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        assert response.status_code == 200, f"Expected HTTP 200 but got {response.status_code}"
        data = response.json()
        assert "tools" in data, "Response JSON missing 'tools' key"
        assert "count" in data, "Response JSON missing 'count' key"
        assert isinstance(data["tools"], list), "'tools' should be a list"
        assert data["count"] == 56, f"Expected 56 tools but got {data['count']}"
        # Validate each tool's fields
        for tool in data["tools"]:
            assert "name" in tool and isinstance(tool["name"], str), "Tool missing 'name' or not a string"
            assert "description" in tool and isinstance(tool["description"], str), (
                "Tool missing 'description' or not a string"
            )
            assert "category" in tool and isinstance(tool["category"], str), "Tool missing 'category' or not a string"
            assert "requires_infrastructure" in tool and isinstance(tool["requires_infrastructure"], bool), (
                "Tool missing 'requires_infrastructure' or not a bool"
            )
            assert "input_schema" in tool, "Tool missing 'input_schema'"
    except requests.RequestException as e:
        assert False, f"Request failed: {e}"


test_get_api_tools_lists_all_tools()
