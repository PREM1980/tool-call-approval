# Design: Migrate LLM from Gemini to Claude on AWS Bedrock

**Date:** 2026-05-21  
**Status:** Approved

## Overview

Replace `ChatGoogleGenerativeAI` (Gemini) with `ChatBedrock` (Claude Sonnet) in both `agent.py` and `workflow.py`. AWS credentials are loaded from a `.env` file via `python-dotenv`. No changes to agent logic, graph structure, or tool wiring.

## Dependencies

Changes to `requirements.txt`:

- **Remove:** `langchain-google-genai`
- **Add:** `langchain-aws`, `python-dotenv`

## Credentials

AWS credentials are stored in a `.env` file at the project root (not committed):

```dotenv
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
```

A `.env.example` with the above keys (empty values) is committed as documentation. `.env` is added to `.gitignore`. `ChatBedrock` reads the standard AWS env vars automatically — no explicit credential passing in code.

## Code Changes

### `agent.py` and `workflow.py`

Both files receive identical changes at the top:

**Remove:**

```python
from langchain_google_genai import ChatGoogleGenerativeAI
llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0)
```

**Add:**

```python
from dotenv import load_dotenv
from langchain_aws import ChatBedrock
load_dotenv()
llm = ChatBedrock(model_id="anthropic.claude-3-5-sonnet-20241022-v2:0", model_kwargs={"temperature": 0})
```

All downstream code (StateGraph nodes, `initialize_agent`, `Tool` wiring) is unchanged — `ChatBedrock` is a drop-in LangChain chat model.

## README

- Replace `export GOOGLE_API_KEY=...` setup instruction with instructions to copy `.env.example` to `.env` and fill in the three AWS vars.
- Remove any Gemini-specific references.

## Tests

`test_workflow.py` patches `workflow.llm` directly (the module-level instance), not the class. No changes needed — the tests are already model-agnostic and will pass after the swap.

## Error Handling

No new error handling needed. If credentials are missing or invalid, `ChatBedrock` raises a descriptive `botocore` exception at LLM invocation time — same pattern as the existing Gemini key error.
