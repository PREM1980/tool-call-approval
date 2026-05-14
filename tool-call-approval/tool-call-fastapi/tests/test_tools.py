from tools import execute_tool, TOOL_DEFINITIONS


def test_calculate_addition():
    result = execute_tool("calculate", {"expression": "2 + 3"})
    assert result == "5"


def test_calculate_sqrt():
    result = execute_tool("calculate", {"expression": "math.sqrt(16)"})
    assert result == "4.0"


def test_calculate_invalid():
    result = execute_tool("calculate", {"expression": "import os"})
    assert "Error" in result


def test_get_weather_known_city():
    result = execute_tool("get_weather", {"city": "London"})
    assert "°C" in result


def test_get_weather_unknown_city():
    result = execute_tool("get_weather", {"city": "Atlantis"})
    assert "unavailable" in result


def test_search_web_returns_query():
    result = execute_tool("search_web", {"query": "Python testing"})
    assert "Python testing" in result


def test_unknown_tool():
    result = execute_tool("nonexistent", {})
    assert "Unknown tool" in result


def test_tool_definitions_have_required_keys():
    for tool in TOOL_DEFINITIONS:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
