# Bedrock Claude Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Gemini (`ChatGoogleGenerativeAI`) with Claude on AWS Bedrock (`ChatBedrock`) in `workflow.py` and `agent.py`, loading credentials from a `.env` file.

**Architecture:** Swap the LLM instantiation in both files using `langchain-aws`'s `ChatBedrock` — a drop-in LangChain chat model. Credentials are loaded at startup via `python-dotenv`. No changes to graph structure, agent logic, or tool wiring.

**Tech Stack:** `langchain-aws`, `python-dotenv`, `boto3` (transitive), AWS Bedrock (`anthropic.claude-3-5-sonnet-20241022-v2:0`)

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Modify | `requirements.txt` | Remove `langchain-google-genai`, add `langchain-aws` + `python-dotenv` |
| Create | `.env.example` | Document required AWS env vars |
| Create | `.gitignore` | Exclude `.env` from version control |
| Modify | `workflow.py` | Swap LLM import + instantiation |
| Modify | `agent.py` | Swap LLM import + instantiation |
| Modify | `README.md` | Update setup instructions |
| Modify | `test_workflow.py` | Add LLM type assertion test |

---

### Task 1: Update dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Update `requirements.txt`**

Replace the entire file content:

```text
langgraph
langchain
langchain-aws
python-dotenv
```

- [ ] **Step 2: Install updated dependencies**

```bash
pip install -r requirements.txt
```

Expected: all packages install without errors. `langchain-aws` installs `boto3` as a transitive dependency.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: swap langchain-google-genai for langchain-aws and python-dotenv"
```

---

### Task 2: Add `.env.example` and `.gitignore`

**Files:**
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: Create `.env.example`**

```dotenv
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
.env
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 3: Commit**

```bash
git add .env.example .gitignore
git commit -m "chore: add .env.example and .gitignore"
```

---

### Task 3: Migrate `workflow.py` to ChatBedrock (TDD)

**Files:**
- Modify: `test_workflow.py`
- Modify: `workflow.py`

- [ ] **Step 1: Write the failing test**

Add this test at the bottom of `test_workflow.py`:

```python
def test_llm_is_chat_bedrock():
    from langchain_aws import ChatBedrock
    from workflow import llm
    assert isinstance(llm, ChatBedrock)
```

- [ ] **Step 2: Run it to verify it fails**

```bash
pytest test_workflow.py::test_llm_is_chat_bedrock -v
```

Expected: FAIL — `AssertionError` because `llm` is currently a `ChatGoogleGenerativeAI` instance.

- [ ] **Step 3: Create your `.env` file**

```bash
cp .env.example .env
```

Fill in your real AWS credentials in `.env`.

- [ ] **Step 4: Migrate `workflow.py`**

At the top of `workflow.py`, replace:

```python
from langchain_google_genai import ChatGoogleGenerativeAI
```

with:

```python
from dotenv import load_dotenv
from langchain_aws import ChatBedrock

load_dotenv()
```

Then replace the `llm` instantiation:

```python
# remove this line:
llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0)

# add this line:
llm = ChatBedrock(model_id="anthropic.claude-3-5-sonnet-20241022-v2:0", model_kwargs={"temperature": 0})
```

- [ ] **Step 5: Run the new test to verify it passes**

```bash
pytest test_workflow.py::test_llm_is_chat_bedrock -v
```

Expected: PASS

- [ ] **Step 6: Run all tests to verify nothing regressed**

```bash
pytest test_workflow.py -v
```

Expected: all 6 tests PASS (the existing tests mock `workflow.llm` directly and are model-agnostic).

- [ ] **Step 7: Commit**

```bash
git add workflow.py test_workflow.py
git commit -m "feat: migrate workflow.py LLM from Gemini to Claude on Bedrock"
```

---

### Task 4: Migrate `agent.py` to ChatBedrock

**Files:**
- Modify: `agent.py`

Note: `agent.py` has no test file. The migration is verified by running the script directly.

- [ ] **Step 1: Migrate `agent.py`**

At the top of `agent.py`, replace:

```python
from langchain_google_genai import ChatGoogleGenerativeAI
```

with:

```python
from dotenv import load_dotenv
from langchain_aws import ChatBedrock

load_dotenv()
```

Then replace the `llm` instantiation:

```python
# remove this line:
llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0, )

# add this line:
llm = ChatBedrock(model_id="anthropic.claude-3-5-sonnet-20241022-v2:0", model_kwargs={"temperature": 0})
```

- [ ] **Step 2: Smoke-test the agent**

```bash
python agent.py
```

Expected: output like `Hello, Alice!` — the greet tool is invoked and Claude returns a response.

- [ ] **Step 3: Commit**

```bash
git add agent.py
git commit -m "feat: migrate agent.py LLM from Gemini to Claude on Bedrock"
```

---

### Task 5: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the Setup section**

Replace the existing Setup section:

```markdown
## Setup

\```bash
pip install -r requirements.txt
export GOOGLE_API_KEY=your_api_key_here
\```
```

with:

```markdown
## Setup

\```bash
pip install -r requirements.txt
cp .env.example .env
\```

Fill in your AWS credentials in `.env`:

| Variable | Description |
| --- | --- |
| `AWS_ACCESS_KEY_ID` | Your AWS access key |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret key |
| `AWS_DEFAULT_REGION` | AWS region where Bedrock is enabled (e.g. `us-east-1`) |

Ensure your AWS account has access to `anthropic.claude-3-5-sonnet-20241022-v2:0` in the chosen region via the [Bedrock Model Access console](https://console.aws.amazon.com/bedrock/home#/modelaccess).
```

- [ ] **Step 2: Update the description in the README header**

Change the first line of the README description from:

```markdown
A multi-agent workflow built with [LangGraph](https://github.com/langchain-ai/langgraph) and Gemini that researches a topic and produces a structured markdown report.
```

to:

```markdown
A multi-agent workflow built with [LangGraph](https://github.com/langchain-ai/langgraph) and Claude on AWS Bedrock that researches a topic and produces a structured markdown report.
```

- [ ] **Step 3: Update the agent table in the Workflow section**

Change the two Gemini references in the agent table:

```markdown
| `researcher` | Researches the topic in depth using Gemini |
| `summarizer` | Condenses research into key bullet points |
```

to:

```markdown
| `researcher` | Researches the topic in depth using Claude |
| `summarizer` | Condenses research into key bullet points |
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: update README for AWS Bedrock / Claude setup"
```
