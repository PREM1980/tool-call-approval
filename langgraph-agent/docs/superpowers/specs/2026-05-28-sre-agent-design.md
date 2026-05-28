# SRE Agent Design

**Date:** 2026-05-28
**Status:** Approved

## Overview

A LangGraph-based SRE agent that classifies an incoming query into a domain (Kubernetes, AWS, or Observability) and routes it to the appropriate sub-agent. Each sub-agent runs a reasoning loop — re-prompting the LLM with accumulated context until it reaches a definitive conclusion. The final result is both pretty-printed to terminal and returned as a structured dict.

## Folder Structure

```
sre/
├── __init__.py
├── graph.py       # builds and compiles the StateGraph
├── router.py      # LLM-based routing node
├── agents.py      # k8s, aws, observability reasoning loop nodes
└── main.py        # CLI entrypoint
```

## State

```python
class SREState(TypedDict):
    query: str          # original user query
    domain: str         # "kubernetes" | "aws" | "observability"
    reasoning: list     # accumulated reasoning steps (list of strings)
    conclusion: str     # final answer when loop terminates
    iterations: int     # loop counter, capped at 5
```

## Architecture

### Graph topology

```
START → [router] → conditional edge on domain
    → [k8s_agent | aws_agent | obs_agent]
        → loop back to self if not conclusive AND iterations < 5
        → END when conclusive or max iterations reached
```

### Router node (`router.py`)

Sends the query to Gemini with a zero-shot classification prompt:

> "Classify this SRE query as exactly one of: kubernetes, aws, observability. Reply with only the domain word."

Sets `domain` in state. A conditional edge reads `domain` to select the next node.

### Sub-agent reasoning loop (`agents.py`)

All three sub-agents (Kubernetes, AWS, Observability) share the same loop structure but use domain-specific system prompts:

- **Kubernetes:** focuses on pods, nodes, deployments, services, namespaces
- **AWS:** focuses on EC2, S3, IAM, VPC, CloudWatch, Lambda
- **Observability:** focuses on metrics, logs, traces, alerts, dashboards

Each iteration:
1. Builds a prompt from `query` + all prior `reasoning` steps
2. Asks the LLM to continue diagnosing; if conclusive, start response with `CONCLUSION:`
3. Appends the LLM response to `reasoning` and increments `iterations`
4. If response starts with `CONCLUSION:`, extracts and sets `conclusion`

Conditional edge logic after each sub-agent call:
- `conclusion` is set → route to `END`
- `iterations >= 5` → set `conclusion` to best reasoning so far with a max-iterations note, route to `END`
- Otherwise → loop back to the same sub-agent node

### Output (`main.py`)

After graph completion, pretty-prints:

```
=== SRE Agent Result ===
Domain   : kubernetes
Steps    : 3
Diagnosis: <conclusion text>
```

Returns structured dict:
```python
{"agent": domain, "diagnosis": conclusion, "steps_taken": len(reasoning)}
```

## Error Handling

| Scenario | Handling |
|---|---|
| LLM returns unrecognized domain | Default to `"observability"` |
| Max iterations (5) reached without CONCLUSION | Use accumulated reasoning as conclusion with a note |
| LLM API error | Propagate exception — no silent swallowing |

## Testing

- Unit test for router: mock LLM response, assert correct `domain` is set for each domain keyword
- Unit test for sub-agent loop: mock LLM to return `CONCLUSION:` on iteration N, assert loop terminates and `conclusion` is set
- Integration test: run full graph with a real query per domain, assert structured output shape
