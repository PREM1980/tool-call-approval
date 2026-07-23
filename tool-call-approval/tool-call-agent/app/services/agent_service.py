from __future__ import annotations

import asyncio
import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from os import getenv
from pathlib import Path
from typing import Annotated, Any, TypedDict
from uuid import uuid4

import httpx
from fpdf import FPDF
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
# Langfuse tracing is disabled for the local Compose deployment.
# from langfuse.decorators import langfuse_context, observe
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from app.core.system_prompts import (
    DEFAULT_INSTRUCTIONS as _DEFAULT_INSTRUCTIONS,
    DEFAULT_SYSTEM_PROMPT_NAME as _DEFAULT_SYSTEM_PROMPT_NAME,
)
from app.domain.session import Session
from app.repositories.admin_repository import AdminRepository
from app.repositories.agent_repository import IAgentStorage
from app.tools.registry import execute_tool, reset_kubeconfig, set_kubeconfig

_AWS_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
_GCP_MODEL_ID = "claude-sonnet-4-6"
_LOCAL_MODEL_ID = "gemma-4"
_LOCAL_BASE_URL = "https://models.k8s.aip.mitre.org/v1"
_THROTTLE_MAX_RETRIES = 3
_THROTTLE_BASE_DELAY = 5
_AUTO_APPROVE = getenv("AUTO_APPROVE_TOOLS", "false").lower() == "true"
_APPROVAL_TIMEOUT = float(getenv("APPROVAL_TIMEOUT_SECONDS", "300"))
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---", re.DOTALL)
_SKILL_NAME_RE = re.compile(r"^\s*name\s*:\s*(?P<name>.+?)\s*$", re.MULTILINE)
_MAX_TOOL_CALLS = 12
_NAMESPACE_NAME_RE = re.compile(r"^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$")
_ALL_NAMESPACES_SCOPE = "__all__"
_SENSITIVE_EVENT_KEYS = {"authorization", "credential", "credentials", "kubeconfig", "password", "secret", "token", "api_key"}
_CLUSTER_SCOPED_COMMAND_RE = re.compile(
    r"^(?:get|describe)\s+(?:ns|namespace|namespaces|node|nodes|"
    r"persistentvolume|persistentvolumes|pv|pvs|clusterrole|clusterroles|"
    r"clusterrolebinding|clusterrolebindings)\b|^(?:cluster-info|version|api-resources)\b",
    re.IGNORECASE,
)
_NAMESPACE_INTENT_PROMPT = """You detect requested Kubernetes namespace changes.
Return JSON only with exactly this shape: {\"namespace\": string|null}.
Set namespace only when the user asks to change the active namespace for this
conversation, including natural phrases such as 'switch to payments', 'work on the
payments workloads', 'use the payments namespace', or a kubectl command with -n
or --namespace. If the user asks to work across all namespaces, including -A or
--all-namespaces, return the exact string "__all__". Return null otherwise."""


def _requires_live_kubectl(message: str) -> bool:
    """Return whether a request needs current cluster data rather than guidance."""
    text = message.strip().lower()
    if not text:
        return False
    if re.match(r"^(how\s+(do|can|to)|explain\b|what\s+is\b|define\b|why\s+is\b)", text):
        return False
    return bool(re.search(
        r"\b(list|show|get|check|inspect|describe|find|view|status|health|logs?|events?|"
        r"pods?|nodes?|namespaces?|deployments?|services?|ingresses?|configmaps?|pvcs?|"
        r"secrets?|cluster|workloads?|apply|delete|scale|rollout|patch|create|exec|port-forward|kubectl)\b",
        text,
    ))


def _build_model(model_id: str | None = None, provider: str | None = None) -> Any:
    """Create the LangChain chat model used by the LangGraph agent."""
    provider = (provider or getenv("LLM_PROVIDER", "AWS")).upper()
    if provider == "LOCAL":
        api_key = getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY is required when LLM_PROVIDER=LOCAL")
        if not api_key.startswith("sk-"):
            raise EnvironmentError("OPENAI_API_KEY must start with 'sk-' for LLM_PROVIDER=LOCAL")
        verify_ssl = getenv("LOCAL_VERIFY_SSL", "true").lower() not in {"0", "false", "no"}
        verify: bool | str = getenv("LOCAL_CA_BUNDLE") or verify_ssl
        return ChatOpenAI(
            model=model_id or getenv("MODEL_ID") or getenv("LOCAL_MODEL_ID", _LOCAL_MODEL_ID),
            api_key=api_key,
            base_url=getenv("BASE_URL") or getenv("LOCAL_BASE_URL", _LOCAL_BASE_URL),
            http_client=httpx.Client(verify=verify),
            http_async_client=httpx.AsyncClient(verify=verify),
        )
    if provider == "GCP":
        try:
            from langchain_google_vertexai import ChatVertexAI
        except ImportError as exc:  # pragma: no cover - deployment dependency
            raise RuntimeError("langchain-google-vertexai is required for LLM_PROVIDER=GCP") from exc
        return ChatVertexAI(
            model_name=model_id or _GCP_MODEL_ID,
            project=getenv("GOOGLE_CLOUD_PROJECT"),
            location=getenv("GOOGLE_CLOUD_LOCATION", "us-east5"),
            temperature=0,
        )
    try:
        from langchain_aws import ChatBedrock
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise RuntimeError("langchain-aws is required for LLM_PROVIDER=AWS") from exc
    return ChatBedrock(model_id=model_id or _AWS_MODEL_ID, model_kwargs={"temperature": 0})


@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression. Use math.sqrt(), math.pi, etc. for math functions."""
    return execute_tool("calculate", {"expression": expression})


@tool
def get_weather(city: str) -> str:
    """Get current weather conditions for a city."""
    return execute_tool("get_weather", {"city": city})


@tool
def search_web(query: str) -> str:
    """Search the web for information on a topic."""
    return execute_tool("search_web", {"query": query})


@tool
async def kubectl(command: str) -> str:
    """Execute a kubectl command, for example 'get pods -n default'."""
    return await asyncio.to_thread(execute_tool, "kubectl", {"args": command})


def _build_pdf(title: str, content: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, content)
    return bytes(pdf.output())


def _normalize_tool_args(
    name: str, args: dict[str, Any], active_namespace: str | None = None,
) -> dict[str, Any]:
    """Normalize OpenAI-compatible positional tool calls to this app's schema."""
    if name != "kubectl":
        return args

    value = args.get("command", args.get("args"))
    if value is None:
        value = next(
            (item for key, item in args.items() if key != "args" and key.endswith("args")),
            None,
        )
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    if isinstance(value, str):
        command = value.strip()
        has_scope = bool(re.search(
            r"(?:^|\s)(?:-A\b|--all-namespaces\b|-n\s+\S+|--namespace(?:=|\s+)\S+)",
            command,
        ))
        if active_namespace and not has_scope and not _CLUSTER_SCOPED_COMMAND_RE.search(command):
            flag = "--all-namespaces" if active_namespace == _ALL_NAMESPACES_SCOPE else f"-n {active_namespace}"
            command = f"{command} {flag}"
        return {"command": command}
    return args


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    final_output: str


@dataclass
class _SessionGraph:
    graph: Any
    messages: list[AnyMessage]


class AgentService:
    def __init__(self, repository: IAgentStorage, admin_repository: AdminRepository) -> None:
        self._repository = repository
        self._admin_repository = admin_repository
        self._sessions: dict[str, tuple[Session, _SessionGraph]] = {}

    def create_session(self, instance_id: str | None = None, persona_id: str | None = None,
                       persona_ids: list[str] | None = None, system_prompt_id: str | None = None,
                       model_id: str | None = None, provider: str | None = None) -> Session:
        session = Session(id=str(uuid4()))
        prompt = self._resolve_system_prompt(system_prompt_id)
        selected = self._selected_persona_ids(persona_id, persona_ids)
        tmpdir, skill_instructions, personas = self._load_skills(instance_id, selected)
        session.tmpdir, session.instance_id = tmpdir, instance_id
        self._apply_persona_snapshot(session, persona_id, personas)
        session.system_prompt_id = prompt["id"]
        session.system_prompt_name = prompt["name"]
        session.system_prompt_instructions_snapshot = prompt["instructions"]
        session.model_id, session.provider = model_id, provider
        instructions = str(prompt["instructions"])
        if skill_instructions:
            instructions = f"{instructions}\n\n<skills>\n{skill_instructions}\n</skills>"
        runtime = _SessionGraph(self._build_graph(session, instructions, model_id, provider), [])
        self._sessions[session.id] = (session, runtime)
        return session

    def get_session(self, session_id: str) -> Session | None:
        pair = self._sessions.get(session_id)
        return pair[0] if pair else None

    def approve(self, session: Session, tool_use_id: str | None, approved: bool,
                tool_input: dict[str, Any] | None = None) -> None:
        if tool_use_id not in session.pending_approvals:
            return
        if tool_input is not None:
            original = session.pending_tool_inputs.get(tool_use_id, {})
            if set(tool_input) != set(original):
                raise ValueError("Only existing tool parameters can be edited")
            if any(type(tool_input[key]) is not type(original[key]) for key in tool_input):
                raise ValueError("Tool parameter types cannot be changed")
            session.approval_inputs[tool_use_id] = tool_input
        session.approval_results[tool_use_id] = approved
        self._emit_nowait(session, "approval_received", tool_use_id=tool_use_id,
                          approved=approved, tool_input=tool_input)
        session.pending_approvals[tool_use_id].set()

    def _build_graph(self, session: Session, instructions: str, model_id: str | None, provider: str | None) -> Any:
        tools = [calculate, get_weather, search_web, kubectl, self._save_report_tool(session)]
        tools_by_name = {item.name: item for item in tools}
        model = _build_model(model_id, provider).bind_tools(tools)
        kubectl_required_model = _build_model(model_id, provider).bind_tools(
            [kubectl], tool_choice="required"
        )

        async def agent_node(state: AgentState) -> dict[str, Any]:
            history = state["messages"][-11:]
            latest_user_index = max(
                (index for index, item in enumerate(state["messages"])
                 if isinstance(item, HumanMessage)),
                default=-1,
            )
            is_first_turn_after_user = latest_user_index >= 0 and not any(
                isinstance(item, ToolMessage)
                for item in state["messages"][latest_user_index + 1:]
            )
            latest_user = (
                str(state["messages"][latest_user_index].content)
                if latest_user_index >= 0 else ""
            )
            active_model = (
                kubectl_required_model
                if is_first_turn_after_user and _requires_live_kubectl(latest_user)
                else model
            )
            namespace_note = (
                f"\n\nThe active Kubernetes namespace is `{session.k8s_namespace}`. "
                "Use it unless the user explicitly specifies another namespace."
                if session.k8s_namespace else ""
            )
            await self._emit(session, "model_request", model_id=session.model_id, provider=session.provider)
            response: Any = None
            async for chunk in active_model.astream([
                SystemMessage(content=f"{instructions}{namespace_note}"), *history,
            ]):
                response = chunk if response is None else response + chunk
                text = self._chunk_text(chunk)
                if text:
                    await self._emit(session, "message_delta", content=text)
            if response is None:
                raise RuntimeError("The model returned no response")
            await self._emit(session, "model_response", has_tool_calls=bool(getattr(response, "tool_calls", None)))
            return {"messages": [response]}

        async def tools_node(state: AgentState) -> dict[str, Any]:
            last = state["messages"][-1]
            results: list[ToolMessage] = []
            for call in getattr(last, "tool_calls", []) or []:
                name, args, call_id = call["name"], dict(call.get("args", {})), call["id"]
                args = _normalize_tool_args(name, args, session.k8s_namespace)
                self._track_tool_command(session, call_id, name, args)
                approved, args = await self._await_approval(session, call_id, name, args)
                if not approved:
                    content = "Tool call rejected by user. Continue without executing it."
                else:
                    try:
                        await self._emit(session, "tool_started", tool_use_id=call_id,
                                         tool_name=name, tool_input=args)
                        content = str(await tools_by_name[name].ainvoke(args))
                    except Exception as exc:
                        content = f"Tool error: {exc}"
                        await self._emit(session, "tool_failed", tool_use_id=call_id,
                                         tool_name=name, content=str(exc))
                    display = self._format_tool_result(name, args, content)
                    self._track_tool_result(session, call_id, display)
                    await self._emit(session, "tool_result", tool_use_id=call_id,
                                     tool_name=name, result=display)
                results.append(ToolMessage(content=content, name=name, tool_call_id=call_id))
            return {"messages": results}

        def after_agent(state: AgentState) -> str:
            calls = getattr(state["messages"][-1], "tool_calls", []) or []
            tools_used = sum(isinstance(message, ToolMessage) for message in state["messages"])
            return "tools" if calls and tools_used < _MAX_TOOL_CALLS else "finalize"

        async def finalize_node(state: AgentState) -> dict[str, str]:
            last = state["messages"][-1]
            content = str(getattr(last, "content", "") or "")
            if not content:
                content = "I completed the requested tool calls, but did not receive a final text response."
            await self._emit(session, "message", content=content)
            return {"final_output": content}

        graph = StateGraph(AgentState)
        graph.add_node("agent", agent_node)
        graph.add_node("tools", tools_node)
        graph.add_node("finalize", finalize_node)
        graph.add_edge(START, "agent")
        graph.add_conditional_edges("agent", after_agent, {"tools": "tools", "finalize": "finalize"})
        graph.add_edge("tools", "agent")
        graph.add_edge("finalize", END)
        return graph.compile()

    def _save_report_tool(self, session: Session) -> Any:
        @tool
        async def save_report(title: str, content: str) -> str:
            """Generate a PDF report for this session and return a download URL."""
            report_id = str(uuid4())
            Path(session.tmpdir or tempfile.gettempdir(), f"{report_id}.pdf").write_bytes(_build_pdf(title, content))
            return f"/sessions/{session.id}/reports/{report_id}"
        return save_report

    async def _await_approval(self, session: Session, tool_id: str, name: str,
                              args: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
        if _AUTO_APPROVE:
            self._mark_tool_approval(session, tool_id, True)
            await self._emit(session, "approval_received", tool_use_id=tool_id, approved=True,
                             content="Automatically approved")
            return True, args
        event = asyncio.Event()
        session.pending_approvals[tool_id] = event
        session.pending_tool_inputs[tool_id] = args
        await self._emit(session, "tool_call_pending", tool_use_id=tool_id,
                         tool_name=name, tool_input=args)
        try:
            await asyncio.wait_for(event.wait(), timeout=_APPROVAL_TIMEOUT)
        except asyncio.TimeoutError:
            session.approval_results[tool_id] = False
            await self._emit(session, "approval_timed_out", tool_use_id=tool_id, tool_name=name)
        approved = session.approval_results.pop(tool_id, False)
        edited = session.approval_inputs.pop(tool_id, None)
        session.pending_approvals.pop(tool_id, None)
        session.pending_tool_inputs.pop(tool_id, None)
        final_args = edited if approved and edited is not None else args
        self._mark_tool_approval(session, tool_id, approved)
        if not approved:
            await self._emit(session, "tool_rejected", tool_use_id=tool_id, tool_name=name)
        return approved, final_args

    # @observe(name="agent-run", capture_input=False, capture_output=False)
    async def run(self, session: Session, message: str) -> None:
        pair = self._sessions.get(session.id)
        if not pair:
            return
        self._reset_tool_data(session)
        session.current_run_id = str(uuid4())
        token = set_kubeconfig(session.kubeconfig)
        try:
            # langfuse_context.update_current_trace(user_id=session.id, tags=["tool-call-approval"])
            # langfuse_context.update_current_observation(input=message)
            await self._emit(session, "run_started", content=message)
            await self._emit(session, "thinking", content="Thinking...")
            requested_namespace = await self._detect_requested_namespace(session, message)
            command_to_execute = message
            if requested_namespace:
                approved, updated_args = await self._await_approval(
                    session,
                    f"namespace-{uuid4()}",
                    "set_namespace",
                    {"namespace": requested_namespace},
                )
                namespace = str(updated_args.get("namespace", "")).strip().lower()
                if approved and self._is_valid_namespace_scope(namespace):
                    session.k8s_namespace = namespace
                    label = "all namespaces" if namespace == _ALL_NAMESPACES_SCOPE else f"`{namespace}`"
                    confirmation = f"Active namespace set to {label}."
                    self.record_agent_message(session, confirmation)
                    await self._emit(session, "message", content=confirmation)
                    if session.pending_namespace_command:
                        command_to_execute = session.pending_namespace_command
                        session.pending_namespace_command = None
                elif approved:
                    await self._emit(session, "message", content="The selected namespace is not valid.")
                    await self._emit(session, "done")
                    return
                else:
                    await self._emit(session, "message", content="Namespace change was not applied.")
                    await self._emit(session, "done")
                    return
            elif session.k8s_namespace is None and _requires_live_kubectl(message):
                session.pending_namespace_command = message
                await self._list_namespaces_and_request_selection(session)
                await self._emit(session, "done")
                return
            result: dict[str, Any] | None = None
            for attempt in range(_THROTTLE_MAX_RETRIES + 1):
                try:
                    result = await pair[1].graph.ainvoke({
                        "messages": [*pair[1].messages, HumanMessage(content=command_to_execute)],
                        "final_output": "",
                    })
                    break
                except Exception as exc:
                    if "ThrottlingException" in str(exc) and attempt < _THROTTLE_MAX_RETRIES:
                        await asyncio.sleep(_THROTTLE_BASE_DELAY * 2 ** attempt)
                        continue
                    raise
            final_output = (result or {}).get("final_output", "")
            if result:
                pair[1].messages = list(result.get("messages", []))[-12:]
            if final_output:
                self.record_agent_message(session, final_output)
            # langfuse_context.update_current_observation(output=final_output)
            # langfuse_context.update_current_trace(output=final_output)
            await self._emit(session, "run_completed")
            await self._emit(session, "done")
        except Exception as exc:
            # langfuse_context.update_current_observation(level="ERROR", status_message=str(exc))
            await self._emit(session, "run_failed", content=str(exc))
            await self._emit(session, "error", content=f"Unexpected error: {exc}")
            await self._emit(session, "done")
            self._remove_session(session.id)
        finally:
            reset_kubeconfig(token)
            session.current_run_id = None

    async def _detect_requested_namespace(self, session: Session, message: str) -> str | None:
        """Run a focused model pass to detect an active-namespace change request."""
        await self._emit(session, "model_request", model_id=session.model_id,
                         provider=session.provider, operation="namespace_detection")
        response = await _build_model(session.model_id, session.provider).ainvoke([
            SystemMessage(content=_NAMESPACE_INTENT_PROMPT),
            HumanMessage(content=message),
        ])
        await self._emit(session, "model_response", operation="namespace_detection")
        content = str(getattr(response, "content", "") or "").strip()
        try:
            candidate = json.loads(content).get("namespace")
        except (json.JSONDecodeError, AttributeError):
            match = re.search(r"\{\s*\"namespace\"\s*:\s*(?:\"([^\"]+)\"|null)\s*\}", content)
            candidate = match.group(1) if match else None
        namespace = str(candidate).strip().lower() if candidate else None
        return namespace if namespace and self._is_valid_namespace_scope(namespace) else None

    async def _list_namespaces_and_request_selection(self, session: Session) -> None:
        """List available namespaces before allowing the first scoped operation."""
        tool_id = f"namespace-list-{uuid4()}"
        args = {"command": "get namespaces"}
        self._track_tool_command(session, tool_id, "kubectl", args)
        approved, args = await self._await_approval(session, tool_id, "kubectl", args)
        if approved:
            try:
                await self._emit(session, "tool_started", tool_use_id=tool_id,
                                 tool_name="kubectl", tool_input=args)
                output = str(await kubectl.ainvoke(args))
            except Exception as exc:
                output = f"Tool error: {exc}"
                await self._emit(session, "tool_failed", tool_use_id=tool_id,
                                 tool_name="kubectl", content=str(exc))
            display = self._format_tool_result("kubectl", args, output)
            self._track_tool_result(session, tool_id, display)
            await self._emit(session, "tool_result", tool_use_id=tool_id,
                             tool_name="kubectl", result=display)
            message = (
                f"Available namespaces:\n\n{self._format_namespace_list(output)}\n\n"
                "Choose a namespace by saying `use <namespace> namespace`. "
                "To work across the cluster, say `use all namespaces`.\n\n"
                f"After your selection is approved, I’ll run: **{session.pending_namespace_command or 'your request'}**."
            )
        else:
            message = (
                "I need to list the available namespaces before running a Kubernetes command. "
                "Approve that request, then choose a namespace (or say `use all namespaces`)."
            )
        self.record_agent_message(session, message)
        await self._emit(session, "message", content=message)

    @staticmethod
    def _format_namespace_list(output: str) -> str:
        """Convert `kubectl get namespaces` tabular output into chat-friendly Markdown."""
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if len(lines) < 2 or lines[0].split()[:3] != ["NAME", "STATUS", "AGE"]:
            return output
        rows = [line.split(maxsplit=2) for line in lines[1:]]
        if not all(len(row) == 3 for row in rows):
            return output
        table = ["| Namespace | Status | Age |", "| --- | --- | --- |"]
        table.extend(f"| {name} | {status} | {age} |" for name, status, age in rows)
        return "\n".join(table)

    @staticmethod
    def _is_valid_namespace(namespace: str) -> bool:
        return len(namespace) <= 63 and bool(_NAMESPACE_NAME_RE.fullmatch(namespace))

    @classmethod
    def _is_valid_namespace_scope(cls, namespace: str) -> bool:
        return namespace == _ALL_NAMESPACES_SCOPE or cls._is_valid_namespace(namespace)

    # ── Persona, skill, and persistence helpers ──────────────────────────
    def _load_skills(self, instance_id: str | None, persona_ids: list[str]) -> tuple[str, str, list[dict[str, Any]]]:
        if not persona_ids and instance_id:
            instance = self._admin_repository.get_agent_instance(instance_id)
            if instance and instance.get("persona_id"):
                persona_ids = [str(instance["persona_id"])]
        personas, contents, skill_ids = [], [], []
        for persona_id in persona_ids:
            persona = self._admin_repository.get_persona(persona_id)
            if not persona:
                continue
            personas.append(persona)
            for skill_id in persona.get("skill_ids") or []:
                if skill_id not in skill_ids:
                    skill_ids.append(skill_id)
        for skill_id in skill_ids:
            result = self._admin_repository.get_skill_content(skill_id)
            if result:
                filename, content = result
                contents.append(f"## {self._skill_directory_name(filename, content)}\n{content}")
        return tempfile.mkdtemp(prefix="langgraph_session_"), "\n\n".join(contents), personas

    def _selected_persona_ids(self, persona_id: str | None, persona_ids: list[str] | None) -> list[str]:
        selected = list(dict.fromkeys(item for item in (persona_ids or []) if item))
        if persona_id and persona_id not in selected:
            selected.insert(0, persona_id)
        return selected

    def _apply_persona_snapshot(self, session: Session, fallback: str | None, personas: list[dict[str, Any]]) -> None:
        session.persona_ids = [str(persona["id"]) for persona in personas if persona.get("id")]
        session.persona_names = [str(persona["name"]) for persona in personas if persona.get("name")]
        session.persona_id = session.persona_ids[0] if session.persona_ids else fallback
        session.persona_name = session.persona_names[0] if session.persona_names else None
        session.skill_ids = list(dict.fromkeys(skill for persona in personas for skill in persona.get("skill_ids") or []))

    def _resolve_system_prompt(self, system_prompt_id: str | None) -> dict[str, str | None]:
        if system_prompt_id and (get_prompt := getattr(self._admin_repository, "get_system_prompt", None)):
            prompt = get_prompt(system_prompt_id)
            if prompt and prompt.get("instructions"):
                return {"id": str(prompt.get("id")), "name": prompt.get("name"), "instructions": prompt["instructions"]}
        active = getattr(self._admin_repository, "get_active_system_prompt_record", lambda: None)()
        if active and active.get("instructions"):
            return {"id": str(active.get("id")), "name": active.get("name"), "instructions": active["instructions"]}
        instructions = getattr(self._admin_repository, "get_active_system_prompt", lambda: None)()
        return {"id": None, "name": _DEFAULT_SYSTEM_PROMPT_NAME, "instructions": instructions or _DEFAULT_INSTRUCTIONS}

    def _skill_directory_name(self, filename: str, content: str) -> str:
        frontmatter = _FRONTMATTER_RE.match(content)
        match = _SKILL_NAME_RE.search(frontmatter.group("body")) if frontmatter else None
        return ((match.group("name").strip().strip("\"'") if match else Path(filename).stem).replace("/", "-").replace("\\", "-").strip() or "skill")

    def get_history(self, session_id: str) -> list[dict]: return self._repository.get_session_history(session_id)
    def get_events(self, session_id: str, after_sequence: int = 0) -> list[dict]:
        return self._repository.get_session_events(session_id, after_sequence)
    def record_event(self, session: Session, event_type: str, **payload: Any) -> dict:
        return self._repository.append_session_event(
            session.id, session.current_run_id, event_type, self._redact_event_data(payload),
        )
    async def _emit(self, session: Session, event_type: str, **payload: Any) -> None:
        event = self.record_event(session, event_type, **payload)
        await session.queue.put({"type": event_type, **payload, **({"sequence": event["sequence"], "run_id": event.get("run_id"), "occurred_at": event.get("occurred_at")} if event else {})})
    def _emit_nowait(self, session: Session, event_type: str, **payload: Any) -> None:
        event = self.record_event(session, event_type, **payload)
        session.queue.put_nowait({"type": event_type, **payload, **({"sequence": event["sequence"], "run_id": event.get("run_id"), "occurred_at": event.get("occurred_at")} if event else {})})
    def delete_session(self, session_id: str) -> None:
        self._remove_session(session_id)
        self._repository.delete_session(session_id)
    def record_user_message(self, session: Session, message: str, message_object: dict[str, Any] | None = None) -> None:
        self._repository.append_session_message(session.id, "user", message, session.instance_id, session.system_prompt_id, session.system_prompt_name, session.system_prompt_instructions_snapshot, message=message_object)
    def record_agent_message(self, session: Session, message: str) -> None:
        payload = {"role": "assistant", "content": message, "data": self._clone_tool_data(session.active_tool_data), "timestamp": datetime.now(timezone.utc).isoformat(), "user": None, "agent": self._agent_message_metadata(session)}
        self._repository.append_session_message(session.id, "assistant", message, message=payload)
    def _agent_message_metadata(self, session: Session) -> dict[str, Any]:
        return {"session_id": session.id, "run_id": session.current_run_id, "instance_id": session.instance_id, "persona_id": session.persona_id, "persona_ids": session.persona_ids, "persona_name": session.persona_name, "persona_names": session.persona_names, "skill_ids": session.skill_ids, "system_prompt_id": session.system_prompt_id, "system_prompt_name": session.system_prompt_name, "model_id": session.model_id, "provider": session.provider}
    def _remove_session(self, session_id: str) -> None:
        pair = self._sessions.pop(session_id, None)
        if pair and pair[0].tmpdir: shutil.rmtree(pair[0].tmpdir, ignore_errors=True)
    def _reset_tool_data(self, session: Session) -> None:
        session.active_tool_data = {"cmds": [], "executed_cmds": [], "url_configs": [], "user_file_uploads": []}; session.active_tool_commands.clear()
    def _track_tool_command(self, session: Session, tool_id: str, name: str, args: dict[str, Any]) -> None:
        command = {"command": self._format_tool_command(name, args), "execute": False}; session.active_tool_commands[tool_id] = command; session.active_tool_data["cmds"].append(command)
    def _mark_tool_approval(self, session: Session, tool_id: str, approved: bool) -> None:
        command = session.active_tool_commands.get(tool_id)
        if command:
            command["execute"] = approved
            if not approved: command["rejection_reason"] = "User rejected tool call"
    def _track_tool_result(self, session: Session, tool_id: str, result: str) -> None:
        command = session.active_tool_commands.get(tool_id)
        if command:
            command["execute"] = True; command.pop("rejection_reason", None); session.active_tool_data["executed_cmds"].append({"command": command["command"], "output": result})
    def _format_tool_command(self, name: str, args: dict[str, Any]) -> str:
        return f"kubectl {str(args.get('args') or '').strip()}".strip() if name == "kubectl" else (name if not args else f"{name}({args})")
    def _format_tool_result(self, name: str, args: dict[str, Any], content: str) -> str:
        return f"{name}({', '.join(f'{key}={value}' for key, value in args.items())}) {content}".strip()
    @staticmethod
    def _chunk_text(chunk: Any) -> str:
        """Extract visible text while preserving tool-call chunks for LangGraph."""
        content = getattr(chunk, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        return ""
    def _clone_tool_data(self, data: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
        return {key: [dict(item) for item in value] for key, value in data.items()}
    @classmethod
    def _redact_event_data(cls, value: Any, key: str | None = None) -> Any:
        if key and any(secret in key.lower() for secret in _SENSITIVE_EVENT_KEYS):
            return "[REDACTED]"
        if isinstance(value, dict):
            return {str(item_key): cls._redact_event_data(item_value, str(item_key)) for item_key, item_value in value.items()}
        if isinstance(value, list):
            return [cls._redact_event_data(item, key) for item in value]
        return value
