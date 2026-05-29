# SRE Tool-Calling + Multi-Agent Collaboration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `sre/orchestrate/` with a real `execute_command` tool (kubectl/aws CLI with safety allowlist) and an adaptive multi-agent loop where agents share a message thread and escalate to other domain specialists as needed.

**Architecture:** A single `active_agent` node adapts its system prompt based on `state["domain"]` and uses `bind_tools` + LangGraph's `ToolNode` for tool dispatch. After each agent concludes, `escalation_check` asks the LLM whether another domain specialist is needed. Agents share one `messages` list (via `add_messages` reducer) so each sees all prior findings. Guardrails cap the chain at 5 agent calls and block the same domain consecutively.

**Tech Stack:** LangGraph, LangChain Google GenAI (Gemini 1.5 Pro), `langchain_core.tools.tool`, `langgraph.prebuilt.ToolNode`, `langgraph.graph.message.add_messages`, pytest + unittest.mock

---

## File Map

| File | Action | Role |
|---|---|---|
| `sre/orchestrate/tools/__init__.py` | Create | Package marker |
| `sre/orchestrate/tools/execute.py` | Create | `_check_safe`, `execute_command` tool |
| `sre/orchestrate/tool_agents.py` | Create | `active_agent_node`, `after_agent`, `conclude_node` |
| `sre/orchestrate/escalation.py` | Create | `escalation_check_node`, `after_escalation`, `escalate_setup_node` |
| `sre/orchestrate/graph.py` | Replace | `OrchestrateState`, `build_graph()` with full topology |
| `sre/orchestrate/main.py` | Replace | `run()`, `pretty_print()` updated for new state |
| `sre/orchestrate/orchestrator.py` | Unchanged | — |
| `sre/orchestrate/resolver.py` | Unchanged | — |
| `test_sre_execute.py` | Create | Unit tests for tool safety and execution |
| `test_sre_tool_agents.py` | Create | Unit tests for agent node and routing |
| `test_sre_escalation.py` | Create | Unit tests for escalation logic |
| `test_sre_orchestrate_graph.py` | Create | Integration tests for full graph |

---

### Task 1: Tools package — `execute_command` with safety allowlist (TDD)

**Files:**
- Create: `sre/orchestrate/tools/__init__.py`
- Create: `sre/orchestrate/tools/execute.py`
- Create: `test_sre_execute.py`

- [ ] **Step 1: Create tools package**

```bash
mkdir sre/orchestrate/tools && touch sre/orchestrate/tools/__init__.py
```

- [ ] **Step 2: Write the failing tests**

Create `test_sre_execute.py`:

```python
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from sre.orchestrate.tools.execute import _check_safe, execute_command


def test_check_safe_blocks_delete():
    with pytest.raises(ValueError, match="delete"):
        _check_safe("kubectl delete pod payments-api")


def test_check_safe_blocks_force():
    with pytest.raises(ValueError, match="--force"):
        _check_safe("kubectl drain node-1 --force")


def test_check_safe_blocks_terminate():
    with pytest.raises(ValueError, match="terminate"):
        _check_safe("aws ec2 terminate-instances --instance-ids i-123")


def test_check_safe_blocks_rm():
    with pytest.raises(ValueError, match="rm"):
        _check_safe("aws s3 rm s3://bucket/key")


def test_check_safe_allows_get():
    _check_safe("kubectl get pods -n default")


def test_check_safe_allows_describe():
    _check_safe("kubectl describe pod payments-api -n payments")


def test_check_safe_allows_aws_describe():
    _check_safe("aws ec2 describe-instances --instance-ids i-123")


@patch("sre.orchestrate.tools.execute.subprocess.run")
def test_execute_command_returns_stdout(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="NAME   STATUS\npod-1  Running", stderr="")
    result = execute_command.invoke({"command": "kubectl get pods -n default"})
    assert result == "NAME   STATUS\npod-1  Running"


@patch("sre.orchestrate.tools.execute.subprocess.run")
def test_execute_command_returns_stderr_on_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error from server: not found")
    result = execute_command.invoke({"command": "kubectl get pods -n missing"})
    assert result == "Error from server: not found"


@patch("sre.orchestrate.tools.execute.subprocess.run")
def test_execute_command_timeout(mock_run):
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="kubectl", timeout=30)
    result = execute_command.invoke({"command": "kubectl get pods -n default"})
    assert result == "Command timed out after 30 seconds"


@patch("sre.orchestrate.tools.execute.subprocess.run")
def test_execute_command_not_found(mock_run):
    err = FileNotFoundError()
    err.filename = "kubectl"
    mock_run.side_effect = err
    result = execute_command.invoke({"command": "kubectl get pods"})
    assert result == "Command not available: kubectl"


def test_execute_command_blocks_destructive():
    with pytest.raises(ValueError):
        execute_command.invoke({"command": "kubectl delete namespace production"})
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest test_sre_execute.py -v
```

Expected: `ModuleNotFoundError: No module named 'sre.orchestrate.tools.execute'`

- [ ] **Step 4: Implement `sre/orchestrate/tools/execute.py`**

```python
import subprocess

from langchain_core.tools import tool

_BLOCKED = {
    "delete", "rm", "remove", "terminate", "destroy",
    "drain", "cordon", "--force", "truncate", "drop", "stop", "kill",
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

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest test_sre_execute.py -v
```

Expected: 11 passed.

- [ ] **Step 6: Commit**

```bash
git add sre/orchestrate/tools/__init__.py sre/orchestrate/tools/execute.py test_sre_execute.py
git commit -m "feat(sre): add execute_command tool with safety allowlist"
```

---

### Task 2: Tool-calling agent node (TDD)

**Files:**
- Create: `sre/orchestrate/tool_agents.py`
- Create: `test_sre_tool_agents.py`

- [ ] **Step 1: Write the failing tests**

Create `test_sre_tool_agents.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest test_sre_tool_agents.py -v
```

Expected: `ModuleNotFoundError: No module named 'sre.orchestrate.tool_agents'`

- [ ] **Step 3: Implement `sre/orchestrate/tool_agents.py`**

```python
from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from sre.orchestrate.tools.execute import execute_command

llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0)
llm_with_tools = llm.bind_tools([execute_command])

_SYSTEM_PROMPTS = {
    "kubernetes": (
        "You are a Kubernetes SRE expert. Use the execute_command tool to run kubectl commands "
        "and investigate the incident. Focus on pods, nodes, deployments, services, and namespaces. "
        "When you have a definitive conclusion, start your response with 'CONCLUSION:'."
    ),
    "aws": (
        "You are an AWS SRE expert. Use the execute_command tool to run aws CLI commands "
        "and investigate the incident. Focus on EC2, S3, IAM, VPC, CloudWatch, and Lambda. "
        "When you have a definitive conclusion, start your response with 'CONCLUSION:'."
    ),
    "observability": (
        "You are an Observability SRE expert. Use the execute_command tool to run relevant commands "
        "and investigate the incident. Focus on metrics, logs, traces, alerts, and dashboards. "
        "When you have a definitive conclusion, start your response with 'CONCLUSION:'."
    ),
}


def active_agent_node(state: dict) -> dict:
    system_prompt = _SYSTEM_PROMPTS[state["domain"]]
    messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def after_agent(state: dict) -> str:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return "conclude"


def conclude_node(state: dict) -> dict:
    content = state["messages"][-1].content.strip()
    conclusion = content[len("CONCLUSION:"):].strip() if content.startswith("CONCLUSION:") else content
    return {"conclusion": conclusion}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest test_sre_tool_agents.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add sre/orchestrate/tool_agents.py test_sre_tool_agents.py
git commit -m "feat(sre): add tool-calling active agent node with conclude logic"
```

---

### Task 3: Escalation check + escalate setup (TDD)

**Files:**
- Create: `sre/orchestrate/escalation.py`
- Create: `test_sre_escalation.py`

- [ ] **Step 1: Write the failing tests**

Create `test_sre_escalation.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest test_sre_escalation.py -v
```

Expected: `ModuleNotFoundError: No module named 'sre.orchestrate.escalation'`

- [ ] **Step 3: Implement `sre/orchestrate/escalation.py`**

```python
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0)

_VALID_DOMAINS = {"kubernetes", "aws", "observability"}
MAX_AGENT_CALLS = 5


def escalation_check_node(state: dict) -> dict:
    agents_called = state["agents_called"] + [state["domain"]]

    if len(agents_called) >= MAX_AGENT_CALLS:
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

    if next_domain not in _VALID_DOMAINS or next_domain == state["domain"]:
        next_domain = ""

    return {"agents_called": agents_called, "escalate_to": next_domain}


def after_escalation(state: dict) -> str:
    return "escalate" if state["escalate_to"] else "resolve"


def escalate_setup_node(state: dict) -> dict:
    handoff = HumanMessage(
        content=(
            f"[Handoff from {state['domain']} agent]\n"
            f"Incident: {state['query']}\n"
            f"Prior conclusion: {state['conclusion']}\n"
            f"Now investigate from the {state['escalate_to']} perspective."
        )
    )
    return {"domain": state["escalate_to"], "messages": [handoff]}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest test_sre_escalation.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add sre/orchestrate/escalation.py test_sre_escalation.py
git commit -m "feat(sre): add adaptive escalation check and setup nodes"
```

---

### Task 4: Updated graph + integration tests (TDD)

**Files:**
- Replace: `sre/orchestrate/graph.py`
- Create: `test_sre_orchestrate_graph.py`

- [ ] **Step 1: Write the failing tests**

Create `test_sre_orchestrate_graph.py`:

```python
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest test_sre_orchestrate_graph.py -v
```

Expected: import errors or graph build errors since `graph.py` still has old structure.

- [ ] **Step 3: Replace `sre/orchestrate/graph.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest test_sre_orchestrate_graph.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add sre/orchestrate/graph.py test_sre_orchestrate_graph.py
git commit -m "feat(sre): replace graph with tool-calling multi-agent topology"
```

---

### Task 5: Update main + run all tests

**Files:**
- Replace: `sre/orchestrate/main.py`

- [ ] **Step 1: Replace `sre/orchestrate/main.py`**

```python
import sys

from sre.orchestrate.graph import OrchestrateState, build_graph


def run(query: str) -> dict:
    app = build_graph()
    initial_state: OrchestrateState = {
        "query": query,
        "domain": "",
        "messages": [],
        "agents_called": [],
        "conclusion": "",
        "escalate_to": "",
        "resolution": "",
    }
    result = app.invoke(initial_state)
    return {
        "agent": result["domain"],
        "agents_called": result["agents_called"],
        "diagnosis": result["conclusion"],
        "resolution": result["resolution"],
        "steps_taken": len(result["agents_called"]),
    }


def pretty_print(output: dict) -> None:
    print("\n=== SRE Orchestrator Result ===")
    print(f"Domain   : {output['agent']}")
    print(f"Chain    : {' → '.join(output['agents_called'])}")
    print(f"Steps    : {output['steps_taken']}")
    print(f"Diagnosis: {output['diagnosis']}")
    print(f"\nResolution:\n{output['resolution']}")


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Pods are crashing in the default namespace"
    output = run(query)
    pretty_print(output)
```

- [ ] **Step 2: Run all SRE orchestrate tests together**

```bash
pytest test_sre_execute.py test_sre_tool_agents.py test_sre_escalation.py test_sre_orchestrate_graph.py -v
```

Expected: 31 passed, 0 failed.

- [ ] **Step 3: Verify graph topology compiles and prints correctly**

```bash
python -c "
import os; os.environ.setdefault('GOOGLE_API_KEY', 'dummy')
from sre.orchestrate.graph import build_graph
print(build_graph().get_graph().draw_mermaid())
"
```

Expected: Mermaid diagram showing `orchestrator → init_messages → active_agent → tool_node/conclude → escalation_check → escalate_setup/resolver → END`

- [ ] **Step 4: Commit**

```bash
git add sre/orchestrate/main.py
git commit -m "feat(sre): update orchestrate main for multi-agent state"
```
