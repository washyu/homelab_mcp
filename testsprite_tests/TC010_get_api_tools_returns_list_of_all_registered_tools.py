import requests


def test_get_api_tools_returns_all_registered_tools():
    base_url = "http://localhost:8080"
    url = f"{base_url}/api/tools"
    timeout = 30

    try:
        response = requests.get(url, timeout=timeout)
    except requests.RequestException as e:
        assert False, f"Request to {url} failed with exception: {e}"

    assert response.status_code == 200, f"Expected status code 200 but got {response.status_code}"
    try:
        data = response.json()
    except ValueError:
        assert False, "Response is not valid JSON"

    assert isinstance(data, dict), "Response JSON is not an object"
    assert "tools" in data, "'tools' key missing in response JSON"
    assert "count" in data, "'count' key missing in response JSON"

    tools = data["tools"]
    count = data["count"]

    assert isinstance(tools, list), "'tools' is not a list"
    assert isinstance(count, int), "'count' is not an integer"
    assert count == 56, f"Expected count to be 56 but got {count}"
    assert len(tools) == count, f"Length of tools list {len(tools)} does not match count {count}"

    required_fields = {"name", "description", "category", "requires_infrastructure", "input_schema"}
    for index, tool in enumerate(tools):
        assert isinstance(tool, dict), f"Tool at index {index} is not an object"
        missing_fields = required_fields - tool.keys()
        assert not missing_fields, f"Tool at index {index} missing fields: {missing_fields}"

        # Validate types of fields
        assert isinstance(tool["name"], str), f"Tool at index {index} field 'name' is not a string"
        assert isinstance(tool["description"], str), f"Tool at index {index} field 'description' is not a string"
        assert isinstance(tool["category"], str), f"Tool at index {index} field 'category' is not a string"
        assert isinstance(tool["requires_infrastructure"], bool), (
            f"Tool at index {index} field 'requires_infrastructure' is not a boolean"
        )
        # input_schema can be any JSON object (dict or null)
        assert isinstance(tool["input_schema"], dict) or tool["input_schema"] is None, (
            f"Tool at index {index} field 'input_schema' is not object or null"
        )


test_get_api_tools_returns_all_registered_tools()
