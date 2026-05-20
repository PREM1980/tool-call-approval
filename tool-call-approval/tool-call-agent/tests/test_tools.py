import pytest
from unittest.mock import patch, MagicMock
from tools import execute_tool, TOOL_DEFINITIONS, _is_allowed


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


# ── Allowlist ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("args", [
    "get nodes",
    "get pods",
    "describe node node-1",
    "describe pod my-pod",
    "logs my-pod",
    "top pods",
    "explain deployment",
    "version",
    "cluster-info",
    "api-resources",
    "config view",
    "events -n default",
    "apply -f manifest.yaml",
    "create deployment my-deploy --image=nginx",
    "delete pod my-pod",
    "delete deployment my-deploy",
    "delete service my-svc",
    "edit deployment my-deploy",
    "patch deployment my-deploy -p '{}'",
    "rollout restart deployment/my-deploy",
    "scale deployment my-deploy --replicas=3",
    "exec my-pod -- ls",
    "port-forward pod/my-pod 8080:80",
    "diff -f manifest.yaml",
    "wait pod/my-pod --for=condition=Ready",
])
def test_is_allowed_returns_true(args):
    import shlex
    parts = shlex.split(args)
    assert _is_allowed(parts) is True


@pytest.mark.parametrize("args", [
    "drain node-1",
    "cordon node-1",
    "uncordon node-1",
    "taint nodes node-1 key=value:NoSchedule",
    "certificate approve csr-name",
    "cluster-info dump",
    "unknown-command foo",
    # delete of cluster-scoped resources
    "delete node node-1",
    "delete nodes node-1",
    "delete no node-1",
    "delete namespace production",
    "delete namespaces production",
    "delete ns production",
    "delete pv pv-name",
    "delete persistentvolume pv-name",
    "delete persistentvolumes pv-name",
    "delete clusterrole admin",
    "delete clusterroles admin",
    "delete clusterrolebinding admin-binding",
    "delete clusterrolebindings admin-binding",
])
def test_is_allowed_returns_false(args):
    import shlex
    parts = shlex.split(args)
    assert _is_allowed(parts) is False


def test_is_allowed_empty():
    assert _is_allowed([]) is False


def test_kubectl_denied_command_blocked():
    result = execute_tool("kubectl", {"args": "drain node-1"})
    assert "not an allowed kubectl command" in result


def test_kubectl_denied_does_not_call_subprocess():
    with patch("tools.subprocess.run") as mock_run:
        execute_tool("kubectl", {"args": "cordon node-1"})
        mock_run.assert_not_called()


def test_kubectl_cluster_info_dump_blocked():
    result = execute_tool("kubectl", {"args": "cluster-info dump"})
    assert "not an allowed kubectl command" in result
