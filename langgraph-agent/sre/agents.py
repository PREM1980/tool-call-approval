from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0)

MAX_ITERATIONS = 5

_SYSTEM_PROMPTS = {
    "kubernetes": (
        "You are a Kubernetes SRE expert. Focus on pods, nodes, deployments, services, and namespaces."
    ),
    "aws": (
        "You are an AWS SRE expert. Focus on EC2, S3, IAM, VPC, CloudWatch, and Lambda."
    ),
    "observability": (
        "You are an Observability SRE expert. Focus on metrics, logs, traces, alerts, and dashboards."
    ),
}


def _reasoning_loop(state: dict, domain: str) -> dict:
    system_prompt = _SYSTEM_PROMPTS[domain]
    prior_steps = "\n".join(
        f"Step {i + 1}: {step}" for i, step in enumerate(state["reasoning"])
    )
    prior_section = f"Prior reasoning:\n{prior_steps}\n\n" if prior_steps else ""
    prompt = (
        f"{system_prompt}\n\n"
        f"Query: {state['query']}\n\n"
        f"{prior_section}"
        "Continue diagnosing. If you have a definitive conclusion, start your response "
        "with 'CONCLUSION:'. Otherwise, provide your next reasoning step."
    )
    response = llm.invoke(prompt)
    content = response.content.strip()
    new_reasoning = state["reasoning"] + [content]
    new_iterations = state["iterations"] + 1

    if content.startswith("CONCLUSION:"):
        conclusion = content[len("CONCLUSION:"):].strip()
        return {"reasoning": new_reasoning, "iterations": new_iterations, "conclusion": conclusion}

    if new_iterations >= MAX_ITERATIONS:
        conclusion = f"[Max iterations reached] Best diagnosis: {content}"
        return {"reasoning": new_reasoning, "iterations": new_iterations, "conclusion": conclusion}

    return {"reasoning": new_reasoning, "iterations": new_iterations}


def k8s_agent_node(state: dict) -> dict:
    return _reasoning_loop(state, "kubernetes")


def aws_agent_node(state: dict) -> dict:
    return _reasoning_loop(state, "aws")


def obs_agent_node(state: dict) -> dict:
    return _reasoning_loop(state, "observability")
