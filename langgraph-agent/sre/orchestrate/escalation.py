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
