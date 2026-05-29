# SRE Orchestrator

An extension of the SRE agent that adds **real tool execution** (kubectl / aws CLI) and **adaptive multi-agent collaboration** — specialist agents can escalate to each other when cross-domain involvement is detected.

---

## How It Differs from the SRE Agent

| | SRE Agent (`sre/`) | Orchestrator (`sre/orchestrate/`) |
|---|---|---|
| Classifies domain | yes | yes |
| Diagnoses via reasoning loop | yes | yes (+ real CLI tools) |
| Runs real kubectl / aws commands | no | **yes** |
| Calls multiple domain specialists | no | **yes (adaptive)** |
| Produces resolution steps | no | **yes** |
| Final output | `diagnosis` | `diagnosis` + `resolution` + `agents_called` |

---

## How It Works

```
Your query
    │
    ▼
┌──────────────┐
│ Orchestrator │  ← Classifies primary domain
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────┐
│  active_agent  (adapts on state.domain)  │
│  • Uses execute_command tool             │
│  • Runs kubectl / aws CLI commands       │
│  • Loops via ToolNode until no more      │
│    tool calls, then emits CONCLUSION:    │
└──────────────┬───────────────────────────┘
               │
        ┌──────▼──────┐
        │   conclude   │  ← extracts CONCLUSION: text into state
        └──────┬───────┘
               │
        ┌──────▼──────────────┐
        │  escalation_check   │  ← asks LLM: another domain needed?
        └──────┬──────────────┘
               │
       ────────┴────────
       │ escalate        │ resolve
       ▼                 ▼
 escalate_setup      resolver → END
 (updates domain,    (generates numbered
  adds handoff msg)   fix steps)
       │
       └──────► active_agent  (now a different domain specialist)
                (can bounce back: k8s → aws → k8s)
```

### Step-by-step

1. **Orchestrator** — Classifies query into `kubernetes`, `aws`, or `observability`. Falls back to `observability` for unrecognized input.

2. **active_agent** — A single node that adapts its system prompt based on `state["domain"]`. Uses Gemini with `execute_command` tool bound. Runs a tool loop: LLM picks a command → `ToolNode` executes it → output fed back → repeat until LLM emits `CONCLUSION:`.

3. **execute_command tool** — Shells out to real `kubectl` or `aws` CLI. A safety allowlist blocks destructive tokens (`delete`, `rm`, `terminate`, `--force`, etc.). The LLM sees blocked commands as errors and picks safer alternatives.

4. **escalation_check** — Asks the LLM whether another domain specialist is needed based on the current conclusion. Guardrails:
   - Max **5 total agent calls** across the investigation
   - Same domain **cannot run twice in a row**

5. **escalate_setup** — If escalation needed, injects a handoff message with prior findings and switches `state["domain"]` so `active_agent` runs as a different specialist.

6. **Resolver** — Takes the final conclusion and generates a numbered list of concrete fix steps.

---

## Files

| File | Role |
|------|------|
| `orchestrator.py` | Classifies query into primary domain |
| `tools/execute.py` | `execute_command` tool + `_check_safe` safety allowlist |
| `tool_agents.py` | `active_agent_node`, `after_agent`, `conclude_node` |
| `escalation.py` | `escalation_check_node`, `after_escalation`, `escalate_setup_node` |
| `graph.py` | `OrchestrateState`, `build_graph()` — full graph topology |
| `main.py` | `run()`, `pretty_print()`, CLI entry point |
| `resolver.py` | Takes conclusion → generates actionable resolution steps |

---

## Quickstart

### Prerequisites

```bash
pip install langgraph langchain langchain-google-genai
export GOOGLE_API_KEY=your_api_key_here
# kubectl and/or aws CLI must be on PATH for real tool execution
```

### CLI

```bash
# From the langgraph-agent/ directory:
python -m sre.orchestrate.main "Pods are OOMKilling in the payments namespace"
```

Output:

```
=== SRE Orchestrator Result ===
Domain   : kubernetes
Chain    : kubernetes
Steps    : 1
Diagnosis: Pods are OOMKilled — memory limits set too low.

Resolution:
1. kubectl describe pod <pod> -n payments   # confirm OOMKilled
2. kubectl edit deployment <name> -n payments  # increase resources.limits.memory
3. kubectl rollout status deployment/<name> -n payments
```

Cross-domain example (k8s → aws → k8s):

```
Chain    : kubernetes → aws → kubernetes
Steps    : 3
```

### Python

```python
from sre.orchestrate.main import run, pretty_print

output = run("Pod cannot read from S3 bucket in payments namespace")
pretty_print(output)

print(output["agent"])          # "kubernetes"  (final active domain)
print(output["agents_called"])  # ["kubernetes", "aws", "kubernetes"]
print(output["diagnosis"])      # "IAM role missing s3:GetObject ..."
print(output["resolution"])     # "1. Add s3:GetObject to the pod's IAM role ..."
print(output["steps_taken"])    # 3
```

---

## State

```python
class OrchestrateState(TypedDict):
    query: str                               # original incident query
    domain: str                              # currently active agent domain
    messages: Annotated[list, add_messages]  # shared thread — all agents contribute
    agents_called: list                      # e.g. ["kubernetes", "aws", "kubernetes"]
    conclusion: str                          # latest agent's conclusion
    escalate_to: str                         # next domain or "" to stop
    resolution: str                          # final actionable fix steps
```

All agents share one `messages` list so each specialist sees everything prior agents found.

---

## Safety

`execute_command` blocks any command containing these tokens before execution:

```
delete  rm  remove  terminate  destroy  drain
cordon  --force  truncate  drop  stop  kill
```

Blocked commands are returned as errors to the LLM, which picks a safer alternative. The LLM can never silently bypass the check.

---

## Graph Topology

```
START → orchestrator → init_messages → active_agent
                                           │
                              tool_calls?  │  no tool calls
                                  │        │
                                  ▼        ▼
                              tool_node  conclude
                                  │        │
                                  └──►active_agent
                                           │
                                      escalation_check
                                           │
                               ────────────┴────────────
                               │ escalate               │ resolve
                               ▼                        ▼
                         escalate_setup            resolver → END
                               │
                               └──► active_agent (new domain)
```

## Covered Scenarios

| Incident type | Agent chain |
|---|---|
| Single domain | k8s → resolve |
| Two domains | k8s → aws → resolve |
| Bounce back | k8s → aws → k8s → resolve |
| All three | k8s → aws → obs → resolve |
| Circular (same domain twice in a row) | blocked → resolve |
| Runaway chain | capped at 5 agent calls → resolve |

---

## Testing

```bash
# From langgraph-agent/ directory:
pytest test_sre_execute.py test_sre_tool_agents.py test_sre_escalation.py test_sre_orchestrate_graph.py -v
```

| Test file | What it covers |
|---|---|
| `test_sre_execute.py` | Safety allowlist, stdout/stderr, timeout, FileNotFoundError |
| `test_sre_tool_agents.py` | Active agent node, tool routing, conclude extraction |
| `test_sre_escalation.py` | Escalation decisions, same-domain block, max-calls cap |
| `test_sre_orchestrate_graph.py` | Single-domain, two-domain, bounce-back end-to-end |
