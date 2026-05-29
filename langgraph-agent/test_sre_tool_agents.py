from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage


def _ai_message_with_tools(command: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": "execute_command", "args": {"command": command}, "id": "call_1"}],
    )


def _ai_message_conclusion(text: str) -> AIMessage:
    return AIMessage(content=f"CONCLUSION: {text}")


def _base_state(domain: str = "kubernetes") -> dict:
    return {
        "query": "pods crashing in payments",
        "domain": domain,
        "messages": [HumanMessage(content="pods crashing in payments")],
        "agents_called": [],
        "conclusion": "",
        "escalate_to": "",
        "resolution": "",
    }


@patch("sre.orchestrate.tool_agents.llm_with_tools")
def test_active_agent_returns_ai_message(mock_llm):
    from sre.orchestrate.tool_agents import active_agent_node
    mock_llm.invoke.return_value = _ai_message_conclusion("OOMKilled")
    result = active_agent_node(_base_state())
    assert len(result["messages"]) == 1
    assert isinstance(result["messages"][0], AIMessage)


@patch("sre.orchestrate.tool_agents.llm_with_tools")
def test_active_agent_uses_domain_prompt(mock_llm):
    from sre.orchestrate.tool_agents import active_agent_node
    mock_llm.invoke.return_value = _ai_message_conclusion("issue found")
    active_agent_node(_base_state("aws"))
    call_args = mock_llm.invoke.call_args[0][0]
    system_content = call_args[0].content
    assert "AWS" in system_content


def test_after_agent_returns_tools_when_tool_calls_present():
    from sre.orchestrate.tool_agents import after_agent
    state = {"messages": [_ai_message_with_tools("kubectl get pods")]}
    assert after_agent(state) == "tools"


def test_after_agent_returns_conclude_when_no_tool_calls():
    from sre.orchestrate.tool_agents import after_agent
    state = {"messages": [_ai_message_conclusion("OOMKilled")]}
    assert after_agent(state) == "conclude"


def test_conclude_node_extracts_conclusion():
    from sre.orchestrate.tool_agents import conclude_node
    state = {"messages": [AIMessage(content="CONCLUSION: pods are OOMKilled due to memory limits")]}
    result = conclude_node(state)
    assert result == {"conclusion": "pods are OOMKilled due to memory limits"}


def test_conclude_node_uses_full_content_if_no_prefix():
    from sre.orchestrate.tool_agents import conclude_node
    state = {"messages": [AIMessage(content="Memory limits exceeded")]}
    result = conclude_node(state)
    assert result == {"conclusion": "Memory limits exceeded"}
