from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from sre.orchestrate.escalation import (
    after_escalation,
    escalate_setup_node,
    escalation_check_node,
)
from sre.orchestrate.orchestrator import orchestrator_node
from sre.orchestrate.resolver import resolver_node
from sre.orchestrate.tool_agents import active_agent_node, after_agent, conclude_node
from sre.orchestrate.tools.execute import execute_command


class OrchestrateState(TypedDict):
    query: str
    domain: str
    messages: Annotated[list, add_messages]
    agents_called: list
    conclusion: str
    escalate_to: str
    resolution: str


def _init_messages(state: OrchestrateState) -> dict:
    return {"messages": [HumanMessage(content=state["query"])]}


def build_graph():
    graph = StateGraph(OrchestrateState)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("init_messages", _init_messages)
    graph.add_node("active_agent", active_agent_node)
    graph.add_node("tool_node", ToolNode([execute_command]))
    graph.add_node("conclude", conclude_node)
    graph.add_node("escalation_check", escalation_check_node)
    graph.add_node("escalate_setup", escalate_setup_node)
    graph.add_node("resolver", resolver_node)

    graph.add_edge(START, "orchestrator")
    graph.add_edge("orchestrator", "init_messages")
    graph.add_edge("init_messages", "active_agent")
    graph.add_conditional_edges(
        "active_agent", after_agent, {"tools": "tool_node", "conclude": "conclude"}
    )
    graph.add_edge("tool_node", "active_agent")
    graph.add_edge("conclude", "escalation_check")
    graph.add_conditional_edges(
        "escalation_check", after_escalation,
        {"escalate": "escalate_setup", "resolve": "resolver"},
    )
    graph.add_edge("escalate_setup", "active_agent")
    graph.add_edge("resolver", END)
    return graph.compile()
