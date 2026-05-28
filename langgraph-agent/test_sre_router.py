from unittest.mock import MagicMock, patch

from sre.router import router_node


def _mock_response(content: str) -> MagicMock:
    mock = MagicMock()
    mock.content = content
    return mock


def _base_state() -> dict:
    return {"query": "pods crashing", "domain": "", "reasoning": [], "conclusion": "", "iterations": 0}


@patch("sre.router.llm")
def test_router_classifies_kubernetes(mock_llm):
    mock_llm.invoke.return_value = _mock_response("kubernetes")
    result = router_node(_base_state())
    assert result == {"domain": "kubernetes"}


@patch("sre.router.llm")
def test_router_classifies_aws(mock_llm):
    mock_llm.invoke.return_value = _mock_response("aws")
    result = router_node({**_base_state(), "query": "EC2 instance unreachable"})
    assert result == {"domain": "aws"}


@patch("sre.router.llm")
def test_router_classifies_observability(mock_llm):
    mock_llm.invoke.return_value = _mock_response("observability")
    result = router_node({**_base_state(), "query": "metrics not showing"})
    assert result == {"domain": "observability"}


@patch("sre.router.llm")
def test_router_defaults_unrecognized_to_observability(mock_llm):
    mock_llm.invoke.return_value = _mock_response("network")
    result = router_node(_base_state())
    assert result == {"domain": "observability"}


@patch("sre.router.llm")
def test_router_strips_whitespace(mock_llm):
    mock_llm.invoke.return_value = _mock_response("  kubernetes  \n")
    result = router_node(_base_state())
    assert result == {"domain": "kubernetes"}
