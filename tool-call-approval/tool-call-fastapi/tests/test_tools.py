from unittest.mock import patch, MagicMock
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


def _mock_kubectl(returncode: int, stdout: str, stderr: str = "") -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


def test_kubectl_success():
    with patch("tools.subprocess.run", return_value=_mock_kubectl(0, "pod/nginx Running")):
        result = execute_tool("kubectl", {"args": "get pods"})
    assert result == "pod/nginx Running"


def test_kubectl_strips_kubectl_prefix():
    with patch("tools.subprocess.run") as mock_run:
        mock_run.return_value = _mock_kubectl(0, "ok")
        execute_tool("kubectl", {"args": "kubectl get pods"})
        cmd = mock_run.call_args[0][0]
    assert cmd[0] == "kubectl"
    assert cmd[1] == "get"


def test_kubectl_nonzero_exit_returns_stderr():
    with patch("tools.subprocess.run", return_value=_mock_kubectl(1, "", "Error from server: not found")):
        result = execute_tool("kubectl", {"args": "get pod missing"})
    assert "Error" in result
    assert "not found" in result


def test_kubectl_empty_output():
    with patch("tools.subprocess.run", return_value=_mock_kubectl(0, "")):
        result = execute_tool("kubectl", {"args": "get pods"})
    assert result == "(no output)"


def test_kubectl_invalid_args():
    result = execute_tool("kubectl", {"args": "get pods --namespace 'unclosed"})
    assert "Error" in result
