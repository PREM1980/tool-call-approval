import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import k8s_service


@pytest.fixture(autouse=True)
def patch_kubeconfig_path(tmp_path, monkeypatch):
    monkeypatch.setattr(k8s_service, "_KUBECONFIG_PATH", str(tmp_path / "kubeconfig.yaml"))


def _make_proc(stdout: str, returncode: int = 0) -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = ""
    return m


def _existing_kubeconfig():
    Path(k8s_service._KUBECONFIG_PATH).write_text("apiVersion: v1")


def _dep_json(name: str, image: str = "img:latest", replicas: int = 1, ready: int = 1) -> dict:
    return {
        "metadata": {"name": name, "namespace": "default"},
        "spec": {
            "replicas": replicas,
            "template": {"spec": {"containers": [{"image": image}]}},
        },
        "status": {"readyReplicas": ready},
    }


# ── write_kubeconfig ────────────────────────────────────────────────────────

def test_write_kubeconfig_creates_file():
    k8s_service.write_kubeconfig("apiVersion: v1")
    assert Path(k8s_service._KUBECONFIG_PATH).read_text() == "apiVersion: v1"


def test_write_kubeconfig_creates_parent_dirs(tmp_path, monkeypatch):
    deep = str(tmp_path / "a" / "b" / "kubeconfig.yaml")
    monkeypatch.setattr(k8s_service, "_KUBECONFIG_PATH", deep)
    k8s_service.write_kubeconfig("apiVersion: v1")
    assert Path(deep).exists()


# ── _run guards ─────────────────────────────────────────────────────────────

def test_run_raises_when_no_kubeconfig():
    with pytest.raises(RuntimeError, match="kubeconfig not configured"):
        k8s_service._run(["get", "pods"])


def test_run_raises_on_nonzero_exit():
    _existing_kubeconfig()
    with patch("subprocess.run", return_value=_make_proc("", returncode=1)):
        with pytest.raises(RuntimeError):
            k8s_service._run(["get", "pods"])


# ── create_deployment ────────────────────────────────────────────────────────

def test_create_deployment_uses_ui_agents_suffix():
    _existing_kubeconfig()
    dep = _dep_json("my-agent-ui-agents")
    calls = []
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _make_proc(json.dumps(dep) if "get" in cmd else "created")
    with patch("subprocess.run", side_effect=fake_run):
        result = k8s_service.create_deployment("my-agent", "img:latest", "default", 1, [])
    create_cmd = next(c for c in calls if "create" in c)
    assert "my-agent-ui-agents" in create_cmd
    assert result["name"] == "my-agent-ui-agents"
    assert result["status"] == "Running"


def test_create_deployment_sets_env_vars():
    _existing_kubeconfig()
    dep = _dep_json("x-ui-agents")
    calls = []
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _make_proc(json.dumps(dep) if "get" in cmd else "ok")
    with patch("subprocess.run", side_effect=fake_run):
        k8s_service.create_deployment("x", "img", "default", 1, [{"key": "FOO", "value": "bar"}])
    set_cmd = next(c for c in calls if "set" in c)
    assert "FOO=bar" in set_cmd


def test_create_deployment_skips_set_env_when_no_env():
    _existing_kubeconfig()
    dep = _dep_json("x-ui-agents")
    calls = []
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _make_proc(json.dumps(dep) if "get" in cmd else "ok")
    with patch("subprocess.run", side_effect=fake_run):
        k8s_service.create_deployment("x", "img", "default", 1, [])
    assert not any("set" in c for c in calls)


# ── list_deployments ─────────────────────────────────────────────────────────

def test_list_deployments_filters_by_suffix():
    _existing_kubeconfig()
    items = {
        "items": [
            _dep_json("my-agent-ui-agents"),
            _dep_json("unrelated-deployment"),
        ]
    }
    with patch("subprocess.run", return_value=_make_proc(json.dumps(items))):
        result = k8s_service.list_deployments()
    assert len(result) == 1
    assert result[0]["name"] == "my-agent-ui-agents"


def test_list_deployments_empty():
    _existing_kubeconfig()
    with patch("subprocess.run", return_value=_make_proc(json.dumps({"items": []}))):
        assert k8s_service.list_deployments() == []


# ── delete_deployment ────────────────────────────────────────────────────────

def test_delete_deployment_calls_kubectl_delete():
    _existing_kubeconfig()
    with patch("subprocess.run", return_value=_make_proc("deleted")) as mock:
        k8s_service.delete_deployment("my-agent-ui-agents", "default")
    cmd = mock.call_args[0][0]
    assert "delete" in cmd
    assert "my-agent-ui-agents" in cmd
    assert "--namespace" in cmd


# ── restart_deployment ────────────────────────────────────────────────────────

def test_restart_deployment_calls_rollout_restart():
    _existing_kubeconfig()
    with patch("subprocess.run", return_value=_make_proc("restarted")) as mock:
        k8s_service.restart_deployment("my-agent-ui-agents", "default")
    cmd = mock.call_args[0][0]
    assert "rollout" in cmd
    assert "restart" in cmd
    assert "deployment/my-agent-ui-agents" in cmd


# ── scale_deployment ─────────────────────────────────────────────────────────

def test_scale_deployment_calls_kubectl_scale():
    _existing_kubeconfig()
    with patch("subprocess.run", return_value=_make_proc("scaled")) as mock:
        k8s_service.scale_deployment("my-agent-ui-agents", "default", 3)
    cmd = mock.call_args[0][0]
    assert "scale" in cmd
    assert "--replicas=3" in cmd
    assert "my-agent-ui-agents" in cmd


# ── status derivation ────────────────────────────────────────────────────────

def test_status_running():
    dep = _dep_json("x-ui-agents", replicas=2, ready=2)
    assert k8s_service._derive_status(dep) == "Running"


def test_status_pending():
    dep = _dep_json("x-ui-agents", replicas=2, ready=0)
    assert k8s_service._derive_status(dep) == "Pending"


def test_status_failed():
    dep = _dep_json("x-ui-agents", replicas=1, ready=0)
    dep["status"]["conditions"] = [{"type": "Available", "status": "False"}]
    assert k8s_service._derive_status(dep) == "Failed"
