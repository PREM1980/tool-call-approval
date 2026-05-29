from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage


def _mock_response(content: str) -> MagicMock:
    mock = MagicMock()
    mock.content = content
    return mock


def _ai_conclusion(text: str) -> AIMessage:
    return AIMessage(content=f"CONCLUSION: {text}")


def _initial_state(query: str = "pods crashing") -> dict:
    return {
        "query": query,
        "domain": "",
        "messages": [],
        "agents_called": [],
        "conclusion": "",
        "escalate_to": "",
        "resolution": "",
    }


def test_build_graph_compiles():
    from sre.orchestrate.graph import build_graph
    app = build_graph()
    assert app is not None


@patch("sre.orchestrate.resolver.llm")
@patch("sre.orchestrate.escalation.llm")
@patch("sre.orchestrate.tool_agents.llm_with_tools")
@patch("sre.orchestrate.orchestrator.llm")
def test_full_graph_single_domain(mock_orch, mock_agent, mock_esc, mock_resolver):
    mock_orch.invoke.return_value = _mock_response("kubernetes")
    mock_agent.invoke.return_value = _ai_conclusion("OOMKilled — increase memory limits")
    mock_esc.invoke.return_value = _mock_response("none")
    mock_resolver.invoke.return_value = _mock_response("1. kubectl edit deployment\n2. Increase limits")

    from sre.orchestrate.graph import build_graph
    app = build_graph()
    result = app.invoke(_initial_state("pods crashing"))

    assert result["domain"] == "kubernetes"
    assert "OOMKilled" in result["conclusion"]
    assert result["agents_called"] == ["kubernetes"]
    assert result["resolution"] != ""


@patch("sre.orchestrate.resolver.llm")
@patch("sre.orchestrate.escalation.llm")
@patch("sre.orchestrate.tool_agents.llm_with_tools")
@patch("sre.orchestrate.orchestrator.llm")
def test_full_graph_two_domain(mock_orch, mock_agent, mock_esc, mock_resolver):
    mock_orch.invoke.return_value = _mock_response("kubernetes")
    mock_agent.invoke.side_effect = [
        _ai_conclusion("OOMKilled but node type may be too small"),
        _ai_conclusion("EC2 t3.micro insufficient for workload"),
    ]
    mock_esc.invoke.side_effect = [
        _mock_response("aws"),
        _mock_response("none"),
    ]
    mock_resolver.invoke.return_value = _mock_response("1. Upsize EC2\n2. Increase memory limits")

    from sre.orchestrate.graph import build_graph
    app = build_graph()
    result = app.invoke(_initial_state("pods crashing on EKS"))

    assert result["agents_called"] == ["kubernetes", "aws"]
    assert "EC2" in result["conclusion"]
    assert result["resolution"] != ""


@patch("sre.orchestrate.resolver.llm")
@patch("sre.orchestrate.escalation.llm")
@patch("sre.orchestrate.tool_agents.llm_with_tools")
@patch("sre.orchestrate.orchestrator.llm")
def test_full_graph_bounce_back(mock_orch, mock_agent, mock_esc, mock_resolver):
    mock_orch.invoke.return_value = _mock_response("kubernetes")
    mock_agent.invoke.side_effect = [
        _ai_conclusion("Node has IAM issue"),
        _ai_conclusion("IAM role missing s3:GetObject"),
        _ai_conclusion("Pod now fixed after IAM update"),
    ]
    mock_esc.invoke.side_effect = [
        _mock_response("aws"),
        _mock_response("kubernetes"),
        _mock_response("none"),
    ]
    mock_resolver.invoke.return_value = _mock_response("1. Add s3:GetObject to IAM role")

    from sre.orchestrate.graph import build_graph
    app = build_graph()
    result = app.invoke(_initial_state("pod cannot access S3"))

    assert result["agents_called"] == ["kubernetes", "aws", "kubernetes"]
    assert result["resolution"] != ""
