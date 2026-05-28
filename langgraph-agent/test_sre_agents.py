from unittest.mock import MagicMock, patch

from sre.agents import aws_agent_node, k8s_agent_node, obs_agent_node


def _mock_response(content: str) -> MagicMock:
    mock = MagicMock()
    mock.content = content
    return mock


def _base_state(domain: str = "kubernetes") -> dict:
    return {"query": "pods crashing", "domain": domain, "reasoning": [], "conclusion": "", "iterations": 0}


@patch("sre.agents.llm")
def test_k8s_agent_adds_reasoning_step(mock_llm):
    mock_llm.invoke.return_value = _mock_response("Checking pod logs for OOMKilled events")
    result = k8s_agent_node(_base_state())
    assert result["reasoning"] == ["Checking pod logs for OOMKilled events"]
    assert result["iterations"] == 1
    assert result.get("conclusion", "") == ""


@patch("sre.agents.llm")
def test_k8s_agent_sets_conclusion_on_prefix(mock_llm):
    mock_llm.invoke.return_value = _mock_response("CONCLUSION: OOMKilled — increase memory limits")
    result = k8s_agent_node(_base_state())
    assert result["conclusion"] == "OOMKilled — increase memory limits"
    assert result["iterations"] == 1


@patch("sre.agents.llm")
def test_k8s_agent_accumulates_reasoning_over_iterations(mock_llm):
    mock_llm.invoke.return_value = _mock_response("Next diagnostic step")
    state = {**_base_state(), "reasoning": ["Step 1 analysis"], "iterations": 1}
    result = k8s_agent_node(state)
    assert result["reasoning"] == ["Step 1 analysis", "Next diagnostic step"]
    assert result["iterations"] == 2


@patch("sre.agents.llm")
def test_k8s_agent_caps_at_max_iterations(mock_llm):
    mock_llm.invoke.return_value = _mock_response("Still investigating")
    state = {**_base_state(), "iterations": 4}
    result = k8s_agent_node(state)
    assert result["iterations"] == 5
    assert "[Max iterations reached]" in result["conclusion"]


@patch("sre.agents.llm")
def test_aws_agent_sets_conclusion(mock_llm):
    mock_llm.invoke.return_value = _mock_response("CONCLUSION: Security group blocking port 443")
    result = aws_agent_node({**_base_state("aws"), "query": "EC2 unreachable"})
    assert result["conclusion"] == "Security group blocking port 443"


@patch("sre.agents.llm")
def test_obs_agent_sets_conclusion(mock_llm):
    mock_llm.invoke.return_value = _mock_response("CONCLUSION: Alert threshold misconfigured")
    result = obs_agent_node({**_base_state("observability"), "query": "false alerts firing"})
    assert result["conclusion"] == "Alert threshold misconfigured"
