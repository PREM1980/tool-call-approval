from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0)

_VALID_DOMAINS = {"kubernetes", "aws", "observability"}


def router_node(state: dict) -> dict:
    prompt = (
        "Classify this SRE query as exactly one of: kubernetes, aws, observability.\n"
        "Reply with only the domain word, lowercase.\n\n"
        f"Query: {state['query']}"
    )
    response = llm.invoke(prompt)
    domain = response.content.strip().lower()
    if domain not in _VALID_DOMAINS:
        domain = "observability"
    return {"domain": domain}
