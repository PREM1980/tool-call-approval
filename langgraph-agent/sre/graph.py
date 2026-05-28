from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from sre.agents import aws_agent_node, k8s_agent_node, obs_agent_node
from sre.router import router_node


class SREState(TypedDict):
    query: str
    domain: str
    reasoning: list
    conclusion: str
    iterations: int


def _route_from_router(state: SREState) -> str:
    return state["domain"]


def _route_after_agent(state: SREState) -> str:
    return "end" if state.get("conclusion") else "continue"


def build_graph():
    graph = StateGraph(SREState)
    graph.add_node("router", router_node)
    graph.add_node("k8s_agent", k8s_agent_node)
    graph.add_node("aws_agent", aws_agent_node)
    graph.add_node("obs_agent", obs_agent_node)

    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        _route_from_router,
        {"kubernetes": "k8s_agent", "aws": "aws_agent", "observability": "obs_agent"},
    )
    for agent_name in ["k8s_agent", "aws_agent", "obs_agent"]:
        graph.add_conditional_edges(
            agent_name,
            _route_after_agent,
            {"end": END, "continue": agent_name},
        )

    return graph.compile()
