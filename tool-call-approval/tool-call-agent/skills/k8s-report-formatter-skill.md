---
name: kubernetes-report-formatter
description: format kubernetes operations reports from kubectl output into clean markdown summaries, tables, and fenced code blocks. use when the user asks to present cluster status, node, pod, deployment, service, ingress, pvc, or event results in a polished report, especially when raw kubectl output, tool transcripts, or malformed headings must be normalized.
---

# Kubernetes Report Formatter

## Purpose

Turn kubectl-driven findings into a polished markdown report without echoing raw terminal output.

## Report rules

- Start with a short **Summary** line.
- Put every heading on its own line.
- If a section has a status sentence, put it on the next paragraph after the heading.
- Never merge headings with body text, backticks, or URLs.
- Convert structured resource data into markdown tables.
- Use fenced code blocks only for logs, YAML, describe output, or other unstructured text.
- Omit tool transcripts, shell commands, and intermediate reasoning.
- Keep prose concise, factual, and readable.

## Required shape

Use this layout when the data supports it:

# Cluster Status Report

**Summary:** ...

### Cluster Info
| Field | Value |
|---|---|
| ... | ... |

### Node Status

All nodes are Ready.

| Node | Status | Roles | Age | Version | Internal IP | OS Image | Kernel | Runtime |
|---|---|---|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... | ... | ... | ... |

## Table guidance

- For nodes, pods, deployments, services, PVCs, and events, prefer one table per resource type.
- Include only fields present in the data; do not invent missing columns.
- Use the most useful sort order for the report: newest events first, most relevant failures first, otherwise the default cluster order.
- If a section has no rows, say so plainly instead of leaving it blank.

## Validation checklist

Before finalizing, verify that:

- every heading is on its own line
- no title is appended to a heading line
- no raw kubectl transcript appears
- tables are valid markdown
- code fences contain only unstructured content
