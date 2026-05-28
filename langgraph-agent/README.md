# LangGraph Agent

A multi-agent workflow built with [LangGraph](https://github.com/langchain-ai/langgraph) and Gemini that researches a topic and produces a structured markdown report.

## Workflow

```text
[START] → researcher → summarizer → report_writer → [END]
```

| Agent | Role |
| --- | --- |
| `researcher` | Researches the topic in depth using Gemini |
| `summarizer` | Condenses research into key bullet points |
| `report_writer` | Writes a structured markdown report (Overview, Key Findings, Conclusion) |

## Setup

```bash
pip install -r requirements.txt
export GOOGLE_API_KEY=your_api_key_here
```

## Usage

Run from the command line with a topic:

```bash
python workflow.py "Impact of AI on healthcare"
```

Or import and call `run()` directly:

```python
from workflow import run

report = run("Impact of AI on healthcare")
print(report)
```

## Testing

```bash
pip install pytest
pytest test_workflow.py -v
```

## Files

- `workflow.py` — 3-agent LangGraph `StateGraph` (main entry point)
- `agent.py` — simple single-agent example with a greet tool
- `orchestrate.py` — lightweight sequential workflow skeleton
- `sre/` — SRE agent (see below)

---

## SRE Agent

An LLM-powered SRE agent that classifies an incident query into a domain (Kubernetes, AWS, or Observability) and runs a reasoning loop until it reaches a conclusion.

### How it works

```text
[START] → router → k8s_agent ──┐
                  aws_agent ───┤→ [END]
                  obs_agent ───┘
          (each agent loops until CONCLUSION: or 5 iterations)
```

1. **Router** — Gemini classifies the query as `kubernetes`, `aws`, or `observability`
2. **Sub-agent** — The matched agent re-prompts Gemini with accumulated reasoning until it prefixes a response with `CONCLUSION:` (max 5 iterations)
3. **Output** — Structured dict + pretty-printed terminal summary

### SRE Usage

```bash
python -m sre.main "Pods are OOMKilling in the payments namespace"
```

Or from Python:

```python
from sre.main import run, pretty_print

output = run("EC2 instance failing health checks")
pretty_print(output)
# === SRE Agent Result ===
# Domain   : aws
# Steps    : 2
# Diagnosis: Security group missing inbound rule on port 80

print(output)
# {"agent": "aws", "diagnosis": "...", "steps_taken": 2}
```

### SRE Testing

```bash
pytest test_sre_router.py test_sre_agents.py test_sre_graph.py -v
```
