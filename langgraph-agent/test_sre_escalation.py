from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage


def _mock_response(content: str) -> MagicMock:
    mock = MagicMock()
    mock.content = content
    return mock


def _base_state(domain: str = "kubernetes", agents_called: list = None) -> dict:
    return {
        "query": "pods crashing in payments",
        "domain": domain,
        "agents_called": agents_called or [],
        "conclusion": "OOMKilled — memory limits too low",
        "escalate_to": "",
    }


@patch("sre.orchestrate.escalation.llm")
def test_escalation_check_escalates_to_aws(mock_llm):
    from sre.orchestrate.escalation import escalation_check_node
    mock_llm.invoke.return_value = _mock_response("aws")
    result = escalation_check_node(_base_state())
    assert result["escalate_to"] == "aws"
    assert result["agents_called"] == ["kubernetes"]


@patch("sre.orchestrate.escalation.llm")
def test_escalation_check_resolves_on_none(mock_llm):
    from sre.orchestrate.escalation import escalation_check_node
    mock_llm.invoke.return_value = _mock_response("none")
    result = escalation_check_node(_base_state())
    assert result["escalate_to"] == ""


@patch("sre.orchestrate.escalation.llm")
def test_escalation_blocks_same_domain_consecutive(mock_llm):
    from sre.orchestrate.escalation import escalation_check_node
    mock_llm.invoke.return_value = _mock_response("kubernetes")
    result = escalation_check_node(_base_state(domain="kubernetes"))
    assert result["escalate_to"] == ""


@patch("sre.orchestrate.escalation.llm")
def test_escalation_blocks_at_max_calls(mock_llm):
    from sre.orchestrate.escalation import escalation_check_node
    state = _base_state(agents_called=["kubernetes", "aws", "kubernetes", "aws"])
    result = escalation_check_node(state)
    assert result["escalate_to"] == ""
    mock_llm.invoke.assert_not_called()


@patch("sre.orchestrate.escalation.llm")
def test_escalation_blocks_unrecognized_domain(mock_llm):
    from sre.orchestrate.escalation import escalation_check_node
    mock_llm.invoke.return_value = _mock_response("network")
    result = escalation_check_node(_base_state())
    assert result["escalate_to"] == ""


def test_after_escalation_returns_escalate_when_domain_set():
    from sre.orchestrate.escalation import after_escalation
    assert after_escalation({"escalate_to": "aws"}) == "escalate"


def test_after_escalation_returns_resolve_when_empty():
    from sre.orchestrate.escalation import after_escalation
    assert after_escalation({"escalate_to": ""}) == "resolve"


def test_escalate_setup_node_updates_domain_and_adds_handoff():
    from sre.orchestrate.escalation import escalate_setup_node
    state = {
        "query": "pods crashing",
        "domain": "kubernetes",
        "conclusion": "OOMKilled",
        "escalate_to": "aws",
    }
    result = escalate_setup_node(state)
    assert result["domain"] == "aws"
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], HumanMessage)
    assert "kubernetes" in result["messages"][0].content
    assert "aws" in result["messages"][0].content
    assert "OOMKilled" in result["messages"][0].content
