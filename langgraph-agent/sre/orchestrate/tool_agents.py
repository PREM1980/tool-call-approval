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
