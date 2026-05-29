# SRE Tool-Calling + Multi-Agent Collaboration Design

**Date:** 2026-05-28
**Status:** Approved

## Overview

Extend `sre/orchestrate/` with two capabilities:

1. **Real tool execution** — specialist agents can run `kubectl` and `aws` CLI commands via a single `execute_command` tool with a safety allowlist. The LLM picks which command to run; the tool executes it and returns real output.
2. **Adaptive multi-agent collaboration** — after each agent concludes, an escalation check decides whether another domain specialist is needed. Agents share a single message thread so each one sees all prior findings. The chain can bounce between domains (k8s → aws → k8s) with guardrails to prevent loops.

---

## Folder Structure

```
sre/orchestrate/
├── tools/
│   ├── __init__.py
│   └── execute.py          # execute_command tool + _check_safe allowlist
├── tool_agents.py          # single active_agent node (adapts on state["domain"])
├── escalation.py           # escalation check node
├── graph.py                # updated graph (replaces current graph.py)
├── main.py                 # updated CLI
├── orchestrator.py         # unchanged
└── resolver.py             # unchanged
```

---

## State

```python
from langgraph.graph.message import add_messages
from typing import Annotated, TypedDict

class OrchestrateState(TypedDict):
    query: str
    domain: str                               # currently active agent domain
    messages: Annotated[list, add_messages]   # shared message thread — all agents contribute
    agents_called: list                        # e.g. ["kubernetes", "aws", "kubernetes"]
    conclusion: str                            # latest conclusion from active agent
    escalate_to: str                           # next domain ("") or "" to resolve
    resolution: str                            # final resolution from resolver
```

`add_messages` is a LangGraph reducer that appends rather than replaces — required because the tool loop produces multiple messages across iterations. All agents share one thread so each specialist sees all prior findings when it starts.

---

## Tools Layer

### `sre/orchestrate/tools/execute.py`

Single `execute_command` tool. The LLM picks the full command string; the tool validates and executes it.

```python
import subprocess
from langchain_core.tools import tool

_BLOCKED = {
    "delete", "rm", "remove", "terminate", "destroy",
    "drain", "cordon", "--force", "truncate", "drop", "stop", "kill"
}

def _check_safe(command: str) -> None:
    tokens = set(command.lower().split())
    blocked = tokens & _BLOCKED
    if blocked:
        raise ValueError(f"Blocked destructive command token(s): {blocked}")

@tool
def execute_command(command: str) -> str:
    """Execute a kubectl or aws CLI command for SRE investigation. Read-only commands only."""
    _check_safe(command)
    try:
        result = subprocess.run(
            command.split(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout if result.returncode == 0 else result.stderr
    except FileNotFoundError as e:
        return f"Command not available: {e.filename}"
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds"
```

**Safety:** `_check_safe` raises `ValueError` before execution if any blocked token is found. The LLM receives the error as a `ToolMessage` and picks a different command. It never silently ignores the block.

---

## Active Agent Node

### `sre/orchestrate/tool_agents.py`

A single node that adapts its system prompt based on `state["domain"]`. No separate k8s/aws/obs nodes — domain is a runtime parameter.

```python
_SYSTEM_PROMPTS = {
    "kubernetes": "You are a Kubernetes SRE expert...",
    "aws": "You are an AWS SRE expert...",
    "observability": "You are an Observability SRE expert...",
}

llm_with_tools = llm.bind_tools([execute_command])

def active_agent_node(state: dict) -> dict:
    system_prompt = _SYSTEM_PROMPTS[state["domain"]]
    messages = [SystemMessage(system_prompt)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}
```

**Tool loop logic** — conditional edge after `active_agent`:
- Response has `tool_calls` → route to `tool_node` → back to `active_agent`
- No `tool_calls` and content starts with `CONCLUSION:` → route to `escalation_check`

```python
def after_agent(state: dict) -> str:
    last = state["messages"][-1]
    if last.tool_calls:
        return "tools"
    return "conclude"
```

When routing to `"conclude"`, a `conclude_node` runs before `escalation_check`. It extracts the `CONCLUSION:` text from the last message into `state["conclusion"]` so the escalation check and resolver can read it cleanly:

```python
def conclude_node(state: dict) -> dict:
    content = state["messages"][-1].content.strip()
    conclusion = content[len("CONCLUSION:"):].strip() if content.startswith("CONCLUSION:") else content
    return {"conclusion": conclusion}
```

---

## Escalation Check Node

### `sre/orchestrate/escalation.py`

Runs after the active agent concludes. Asks the LLM whether another domain specialist is needed.

```python
def escalation_check_node(state: dict) -> dict:
    agents_called = state["agents_called"] + [state["domain"]]

    # Guardrail: max 5 total agent calls
    if len(agents_called) >= 5:
        return {"agents_called": agents_called, "escalate_to": ""}

    prompt = (
        f"Incident: {state['query']}\n\n"
        f"Current conclusion: {state['conclusion']}\n\n"
        f"Agents already called: {agents_called}\n\n"
        "Does this conclusion indicate another domain needs investigation?\n"
        "Reply with one of: kubernetes, aws, observability, or 'none'.\n"
        "Reply 'none' if the issue is resolved or if the same domain would be called again consecutively."
    )
    response = llm.invoke(prompt)
    next_domain = response.content.strip().lower()

    valid = {"kubernetes", "aws", "observability"}
    # Block same domain twice in a row
    if next_domain not in valid or next_domain == state["domain"]:
        next_domain = ""

    return {"agents_called": agents_called, "escalate_to": next_domain}


def after_escalation(state: dict) -> str:
    return "escalate" if state["escalate_to"] else "resolve"
```

---

## Graph Topology

```
START → orchestrator → active_agent ←──────────────────────────────┐
                            │                                        │
                     tool_calls? ──yes──► tool_node ────────────────┘
                            │ no
                            ▼
                     escalation_check
                            │
                   ─────────┴──────────
                   │ escalate           │ resolve
                   ▼                    ▼
            escalate_setup         resolver → END
            (sets domain to         
             escalate_to,          
             adds HumanMessage      
             with prior conclusion) 
                   │
                   └──────────────────► active_agent (now new domain)
```

```python
def build_graph():
    graph = StateGraph(OrchestrateState)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("active_agent", active_agent_node)
    graph.add_node("tool_node", ToolNode([execute_command]))
    graph.add_node("escalation_check", escalation_check_node)
    graph.add_node("escalate_setup", escalate_setup_node)  # updates domain, adds context message
    graph.add_node("resolver", resolver_node)

    graph.add_edge(START, "orchestrator")
    graph.add_edge("orchestrator", "active_agent")
    graph.add_conditional_edges("active_agent", after_agent,
                                {"tools": "tool_node", "conclude": "escalation_check"})
    graph.add_edge("tool_node", "active_agent")
    graph.add_conditional_edges("escalation_check", after_escalation,
                                {"escalate": "escalate_setup", "resolve": "resolver"})
    graph.add_edge("escalate_setup", "active_agent")
    graph.add_edge("resolver", END)
    return graph.compile()
```

### `escalate_setup_node`

Transitions between agents — updates domain and injects a handoff message so the next agent starts with context:

```python
def escalate_setup_node(state: dict) -> dict:
    handoff = HumanMessage(
        f"[Handoff from {state['domain']} agent]\n"
        f"Incident: {state['query']}\n"
        f"Prior conclusion: {state['conclusion']}\n"
        f"Now investigate from the {state['escalate_to']} perspective."
    )
    return {"domain": state["escalate_to"], "messages": [handoff]}
```

---

## Error Handling

| Scenario | Handling |
|---|---|
| Destructive command attempted | `_check_safe` raises `ValueError` → returned as ToolMessage → LLM picks safer command |
| CLI command fails (non-zero exit) | `stderr` returned as tool output — LLM sees error and adapts |
| `kubectl`/`aws` not on PATH | `FileNotFoundError` caught → returns `"Command not available: kubectl/aws"` |
| Command hangs | 30s timeout → `"Command timed out"` returned as tool output |
| Max 5 agent calls reached | Escalation check forces `escalate_to = ""` → routes to resolver |
| Same domain twice in a row | Escalation check blocks it → forces `escalate_to = ""` |
| Escalation LLM returns unknown domain | Defaults to `""` → forces resolve |
| Resolver fails | Exception propagates — no silent swallowing |

---

## Covered Scenarios

| Incident type | Agent chain |
|---|---|
| Single domain | k8s → resolve |
| Two domains | k8s → aws → resolve |
| Bounce back | k8s → aws → k8s → resolve |
| All three | k8s → aws → obs → resolve |
| Circular attempt (same domain twice in a row) | blocked → resolve |
| Runaway chain | capped at 5 agent calls → resolve |

---

## Testing

| Test | What it covers |
|---|---|
| `test_check_safe_blocks_delete` | `_check_safe("kubectl delete pod x")` raises `ValueError` |
| `test_check_safe_blocks_force` | `_check_safe("kubectl drain node --force")` raises |
| `test_check_safe_allows_get` | `_check_safe("kubectl get pods -n default")` passes |
| `test_execute_command_returns_stdout` | Mock `subprocess.run` → stdout returned |
| `test_execute_command_returns_stderr_on_failure` | Non-zero exit → stderr returned |
| `test_execute_command_timeout` | `TimeoutExpired` caught → timeout message returned |
| `test_execute_command_not_found` | `FileNotFoundError` caught → not available message |
| `test_active_agent_calls_tool` | Mock LLM returns tool call → routes to tool_node |
| `test_active_agent_concludes` | Mock LLM returns CONCLUSION → routes to escalation_check |
| `test_escalation_check_escalates` | Mock LLM returns "aws" → escalate_to set |
| `test_escalation_check_resolves` | Mock LLM returns "none" → escalate_to empty |
| `test_escalation_blocks_same_domain` | domain="k8s", LLM returns "k8s" → blocked |
| `test_escalation_blocks_at_max_calls` | agents_called has 5 entries → forced resolve |
| `test_full_graph_single_domain` | End-to-end single agent with tool calls → resolution |
| `test_full_graph_two_domain` | End-to-end k8s → aws → resolution |
| `test_full_graph_bounce_back` | End-to-end k8s → aws → k8s → resolution |
