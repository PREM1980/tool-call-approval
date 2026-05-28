from unittest.mock import MagicMock, patch

from sre.graph import build_graph
from sre.main import run


def _mock_response(content: str) -> MagicMock:
    mock = MagicMock()
    mock.content = content
    return mock


def test_build_graph_compiles():
    app = build_graph()
    assert app is not None


@patch("sre.agents.llm")
@patch("sre.router.llm")
def test_full_graph_routes_to_k8s_and_concludes(mock_router_llm, mock_agents_llm):
    mock_router_llm.invoke.return_value = _mock_response("kubernetes")
    mock_agents_llm.invoke.return_value = _mock_response("CONCLUSION: Pod OOMKilled — increase memory limits")

    app = build_graph()
    result = app.invoke({
        "query": "pods are crashing",
        "domain": "",
        "reasoning": [],
        "conclusion": "",
        "iterations": 0,
    })
    assert result["domain"] == "kubernetes"
    assert result["conclusion"] == "Pod OOMKilled — increase memory limits"
    assert len(result["reasoning"]) == 1


@patch("sre.agents.llm")
@patch("sre.router.llm")
def test_full_graph_routes_to_aws(mock_router_llm, mock_agents_llm):
    mock_router_llm.invoke.return_value = _mock_response("aws")
    mock_agents_llm.invoke.return_value = _mock_response("CONCLUSION: Missing IAM permissions on S3 bucket")

    app = build_graph()
    result = app.invoke({
        "query": "S3 access denied",
        "domain": "",
        "reasoning": [],
        "conclusion": "",
        "iterations": 0,
    })
    assert result["domain"] == "aws"
    assert result["conclusion"] == "Missing IAM permissions on S3 bucket"


@patch("sre.agents.llm")
@patch("sre.router.llm")
def test_run_returns_structured_output(mock_router_llm, mock_agents_llm):
    mock_router_llm.invoke.return_value = _mock_response("observability")
    mock_agents_llm.invoke.return_value = _mock_response("CONCLUSION: Alert threshold set too low")

    output = run("alerts firing constantly")
    assert output == {
        "agent": "observability",
        "diagnosis": "Alert threshold set too low",
        "steps_taken": 1,
    }


@patch("sre.agents.llm")
@patch("sre.router.llm")
def test_graph_loops_until_conclusion(mock_router_llm, mock_agents_llm):
    mock_router_llm.invoke.return_value = _mock_response("kubernetes")
    mock_agents_llm.invoke.side_effect = [
        _mock_response("Checking pod events"),
        _mock_response("CONCLUSION: ImagePullBackOff — invalid image tag"),
    ]

    app = build_graph()
    result = app.invoke({
        "query": "pod not starting",
        "domain": "",
        "reasoning": [],
        "conclusion": "",
        "iterations": 0,
    })
    assert result["conclusion"] == "ImagePullBackOff — invalid image tag"
    assert len(result["reasoning"]) == 2
    assert result["iterations"] == 2
