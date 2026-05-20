from models import AgentResponse, DeployRequest, EnvVar, KubeconfigRequest, ScaleRequest


def test_kubeconfig_request():
    r = KubeconfigRequest(content="apiVersion: v1")
    assert r.content == "apiVersion: v1"


def test_deploy_request_defaults():
    r = DeployRequest(name="my-agent", image="img:latest")
    assert r.namespace == "default"
    assert r.replicas == 1
    assert r.env == []


def test_deploy_request_with_env():
    r = DeployRequest(name="x", image="y", env=[{"key": "K", "value": "V"}])
    assert r.env[0].key == "K"


def test_scale_request():
    r = ScaleRequest(replicas=3)
    assert r.replicas == 3


def test_agent_response():
    r = AgentResponse(
        name="x-ui-agents",
        namespace="default",
        image="img:latest",
        replicas=2,
        ready_replicas=2,
        status="Running",
    )
    assert r.status == "Running"
