import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from fpdf import FPDF
from os import getenv

from agno.agent import Agent
from agno.models.aws.bedrock import AwsBedrock
from agno.models.vertexai.claude import Claude as VertexAIClaude
from agno.run.agent import (
    RunCompletedEvent,
    RunContentEvent,
    RunErrorEvent,
    RunPausedEvent,
    ToolCallCompletedEvent,
)
from agno.skills import LocalSkills, Skills
from agno.tools import tool
from langfuse.decorators import langfuse_context, observe

from admin_repository import AdminRepository
from repository import IAgentStorage
from session import Session
from system_prompt_defaults import (
    DEFAULT_INSTRUCTIONS as _DEFAULT_INSTRUCTIONS,
    DEFAULT_SYSTEM_PROMPT_NAME as _DEFAULT_SYSTEM_PROMPT_NAME,
)
from tools import execute_tool, reset_kubeconfig, set_kubeconfig

_AWS_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
_GCP_MODEL_ID = "claude-sonnet-4-6"
_THROTTLE_MAX_RETRIES = 3
_THROTTLE_BASE_DELAY = 5  # seconds; backoff: 5s, 10s, 20s
_AUTO_APPROVE = getenv("AUTO_APPROVE_TOOLS", "false").lower() == "true"
_APPROVAL_TIMEOUT = float(getenv("APPROVAL_TIMEOUT_SECONDS", "300"))  # 5 minutes


def _build_model() -> AwsBedrock | VertexAIClaude:
    provider = getenv("LLM_PROVIDER", "AWS").upper()
    if provider == "GCP":
        return VertexAIClaude(
            id=_GCP_MODEL_ID,
            project_id=getenv("GOOGLE_CLOUD_PROJECT"),
            region=getenv("GOOGLE_CLOUD_LOCATION", "us-east5"),
            request_params={
                "tool_choice": {"type": "auto", "disable_parallel_tool_use": False}
            },
        )
    return AwsBedrock(
        id=_AWS_MODEL_ID,
        request_params={
            "additionalModelRequestFields": {
                "tool_choice": {"type": "auto", "disable_parallel_tool_use": False}
            }
        },
    )

@tool(requires_confirmation=True)
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression. Use math.sqrt(), math.pi, etc. for math functions."""
    return execute_tool("calculate", {"expression": expression})


@tool(requires_confirmation=True)
def get_weather(city: str) -> str:
    """Get current weather conditions for a city."""
    return execute_tool("get_weather", {"city": city})


@tool(requires_confirmation=True)
def search_web(query: str) -> str:
    """Search the web for information on a topic."""
    return execute_tool("search_web", {"query": query})


@tool(requires_confirmation=True)
async def kubectl(args: str) -> str:
    """Execute a kubectl command. Provide arguments after 'kubectl', e.g. 'get pods -n default'."""
    return await asyncio.to_thread(execute_tool, "kubectl", {"args": args})


def _build_pdf(title: str, content: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, content)
    return bytes(pdf.output())


class AgentService:
    def __init__(self, repository: IAgentStorage, admin_repository: AdminRepository) -> None:
        self._repository = repository
        self._admin_repository = admin_repository
        self._sessions: dict[str, tuple[Session, Agent]] = {}
        self._handlers: dict[type, Any] = {
            RunPausedEvent: self._on_paused,
            RunContentEvent: self._on_content,
            RunCompletedEvent: self._on_completed,
            RunErrorEvent: self._on_error,
            ToolCallCompletedEvent: self._on_tool_completed,
        }

    # ── Session lifecycle ──────────────────────────────────────────────────

    def create_session(
        self,
        instance_id: str | None = None,
        system_prompt_id: str | None = None,
    ) -> Session:
        session = Session(id=str(uuid4()))
        prompt = self._resolve_system_prompt(system_prompt_id)
        agent, tmpdir = self._build_agent(session.id, instance_id, prompt["instructions"])
        session.tmpdir = tmpdir
        session.instance_id = instance_id
        session.system_prompt_id = prompt["id"]
        session.system_prompt_name = prompt["name"]
        session.system_prompt_instructions_snapshot = prompt["instructions"]
        self._sessions[session.id] = (session, agent)
        return session

    def get_session(self, session_id: str) -> Session | None:
        pair = self._sessions.get(session_id)
        return pair[0] if pair else None

    def approve(self, session: Session, tool_use_id: str, approved: bool) -> None:
        if tool_use_id in session.pending_approvals:
            session.approval_results[tool_use_id] = approved
            session.pending_approvals[tool_use_id].set()

    # ── Factory ───────────────────────────────────────────────────────────

    def _save_report_local(self, tmpdir: str, session_id: str, title: str, content: str) -> str:
        report_id = str(uuid4())
        Path(tmpdir, f"{report_id}.pdf").write_bytes(_build_pdf(title, content))
        return f"/sessions/{session_id}/reports/{report_id}"

    def _build_agent(
        self,
        session_id: str,
        instance_id: str | None = None,
        instructions: str | None = None,
    ) -> tuple[Agent, str]:
        if instance_id:
            tmpdir, skills_obj = self._load_instance_skills(instance_id)
        else:
            tmpdir, skills_obj = None, None

        if tmpdir is None:
            tmpdir = tempfile.mkdtemp(prefix="agno_session_")

        db = self._repository.get_db()

        @tool(requires_confirmation=True)
        async def save_report(title: str, content: str) -> str:
            """Generate a PDF report for this session and return a download URL."""
            return await asyncio.to_thread(
                self._save_report_local, tmpdir, session_id, title, content
            )

        agent_kwargs: dict[str, Any] = dict(
            model=_build_model(),
            tools=[calculate, get_weather, search_web, kubectl, save_report],
            instructions=instructions or _DEFAULT_INSTRUCTIONS,
            stream=True,
            session_id=session_id,
            user_id=session_id,
        )
        if db is not None:
            agent_kwargs["db"] = db
        if skills_obj is not None:
            agent_kwargs["skills"] = skills_obj
        return Agent(**agent_kwargs), tmpdir

    def _resolve_system_prompt(self, system_prompt_id: str | None = None) -> dict[str, str | None]:
        if system_prompt_id:
            get_prompt = getattr(self._admin_repository, "get_system_prompt", None)
            if callable(get_prompt):
                prompt = get_prompt(system_prompt_id)
                if prompt and prompt.get("instructions"):
                    return {
                        "id": str(prompt.get("id")),
                        "name": prompt.get("name"),
                        "instructions": prompt["instructions"],
                    }

            get_instructions = getattr(
                self._admin_repository,
                "get_system_prompt_instructions",
                None,
            )
            if callable(get_instructions):
                instructions = get_instructions(system_prompt_id)
                if instructions:
                    return {
                        "id": system_prompt_id,
                        "name": None,
                        "instructions": instructions,
                    }

        get_active_record = getattr(
            self._admin_repository,
            "get_active_system_prompt_record",
            None,
        )
        if callable(get_active_record):
            prompt = get_active_record()
            if prompt and prompt.get("instructions"):
                return {
                    "id": str(prompt.get("id")),
                    "name": prompt.get("name"),
                    "instructions": prompt["instructions"],
                }

        get_active = getattr(self._admin_repository, "get_active_system_prompt", None)
        if callable(get_active):
            instructions = get_active()
            if instructions:
                return {"id": None, "name": None, "instructions": instructions}

        return {
            "id": None,
            "name": _DEFAULT_SYSTEM_PROMPT_NAME,
            "instructions": _DEFAULT_INSTRUCTIONS,
        }

    def _load_instance_skills(self, instance_id: str) -> tuple[str | None, Any]:
        """Resolve instance → persona → skills; write to tmpdir. Returns (tmpdir, Skills) or (None, None)."""
        instance = self._admin_repository.get_agent_instance(instance_id)
        if not instance or not instance.get("persona_id"):
            return None, None

        persona = self._admin_repository.get_persona(str(instance["persona_id"]))
        if not persona or not persona.get("skill_ids"):
            return None, None

        tmpdir = tempfile.mkdtemp(prefix="agno_skills_")
        loaded = 0
        for skill_id in persona["skill_ids"]:
            result = self._admin_repository.get_skill_content(skill_id)
            if not result:
                continue
            filename, content = result
            skill_name = Path(filename).stem
            skill_dir = Path(tmpdir) / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(content)
            loaded += 1

        if loaded == 0:
            shutil.rmtree(tmpdir, ignore_errors=True)
            return None, None

        return tmpdir, Skills(loaders=[LocalSkills(tmpdir)])

    def get_history(self, session_id: str) -> list[dict]:
        return self._repository.get_session_history(session_id)

    def record_user_message(self, session: Session, message: str) -> None:
        self._repository.append_session_message(
            session.id,
            "user",
            message,
            session.instance_id,
            session.system_prompt_id,
            session.system_prompt_name,
            session.system_prompt_instructions_snapshot,
        )

    def _get_agent(self, session_id: str) -> Agent | None:
        pair = self._sessions.get(session_id)
        return pair[1] if pair else None

    def _remove_session(self, session_id: str) -> None:
        pair = self._sessions.pop(session_id, None)
        if pair:
            session = pair[0]
            if session.tmpdir:
                shutil.rmtree(session.tmpdir, ignore_errors=True)

    # ── Run loop ──────────────────────────────────────────────────────────

    @observe(name="agent-run", capture_input=False, capture_output=False)
    async def run(self, session: Session, message: str) -> None:
        agent = self._get_agent(session.id)
        if agent is None:
            return

        kubeconfig_token = set_kubeconfig(session.kubeconfig)
        try:
            final_output = await self._run_inner(session, agent, message)
            if final_output:
                self._repository.append_session_message(session.id, "assistant", final_output)
        finally:
            reset_kubeconfig(kubeconfig_token)

    async def _run_inner(self, session: Session, agent: Any, message: str) -> str:
        langfuse_context.update_current_trace(
            user_id=session.id,
            tags=["tool-call-approval"],
        )
        langfuse_context.update_current_observation(input=message)
        await session.queue.put({"type": "thinking", "content": "Thinking..."})

        final_output = await self._run_agent(session, agent, message)

        langfuse_context.update_current_observation(output=final_output)
        langfuse_context.update_current_trace(output=final_output)
        return final_output

    async def _run_agent(self, session: Session, agent: Any, message: str) -> str:
        """Run one agent turn, handling throttle retries. Returns the final text response."""
        tool_spans: list = []
        response_parts: list = []

        for attempt in range(_THROTTLE_MAX_RETRIES + 1):
            tool_spans = []
            response_parts = []
            try:
                async for event in agent.arun(
                    message,
                    stream=True,
                    stream_events=True,
                    yield_run_output=True,
                ):
                    done = await self._dispatch(session, event, tool_spans, response_parts)
                    if done and isinstance(event, (RunCompletedEvent, RunErrorEvent)):
                        break
                break
            except Exception as e:
                error_str = str(e)
                if "ThrottlingException" in error_str and attempt < _THROTTLE_MAX_RETRIES:
                    await asyncio.sleep(_THROTTLE_BASE_DELAY * (2 ** attempt))
                    continue
                langfuse_context.update_current_observation(level="ERROR", status_message=error_str)
                await session.queue.put({"type": "error", "content": f"Unexpected error: {error_str}"})
                await session.queue.put({"type": "done"})
                self._remove_session(session.id)
                return ""

        langfuse_context.update_current_observation(
            metadata={"tool_calls": tool_spans},
        )
        return "".join(response_parts)

    # ── Strategy dispatch ─────────────────────────────────────────────────

    async def _dispatch(
        self, session: Session, event: Any, tool_spans: list, response_parts: list
    ) -> bool:
        handler = self._handlers.get(type(event))
        if handler:
            return await handler(session, event, tool_spans, response_parts)
        return False

    async def _on_paused(
        self, session: Session, event: RunPausedEvent, tool_spans: list, response_parts: list
    ) -> bool:
        pending = [
            r for r in (event.requirements or [])
            if r.needs_confirmation and r.tool_execution is not None
        ]
        if not pending:
            return False

        for req in pending:
            tid = req.tool_execution.tool_call_id
            session.pending_approvals[tid] = asyncio.Event()

        if _AUTO_APPROVE:
            for req in pending:
                tid = req.tool_execution.tool_call_id
                del session.pending_approvals[tid]
                req.confirm()
        else:
            # Send ALL approval requests to the UI at once.
            for req in pending:
                await session.queue.put({
                    "type": "tool_call_pending",
                    "tool_use_id": req.tool_execution.tool_call_id,
                    "tool_name": req.tool_execution.tool_name,
                    "tool_input": req.tool_execution.tool_args or {},
                })
            # Wait for every decision concurrently — user can approve/reject in any order.
            try:
                await asyncio.gather(*[
                    asyncio.wait_for(
                        session.pending_approvals[req.tool_execution.tool_call_id].wait(),
                        timeout=_APPROVAL_TIMEOUT,
                    )
                    for req in pending
                ])
            except asyncio.TimeoutError:
                for req in pending:
                    tid = req.tool_execution.tool_call_id
                    session.approval_results.setdefault(tid, False)
                    session.pending_approvals[tid].set()

            # Apply decisions and clean up.
            for req in pending:
                tid = req.tool_execution.tool_call_id
                approved = session.approval_results.pop(tid, False)
                del session.pending_approvals[tid]
                if approved:
                    req.confirm()
                else:
                    req.reject()
                    await session.queue.put({
                        "type": "tool_rejected",
                        "tool_use_id": tid,
                        "tool_name": req.tool_execution.tool_name,
                    })

        agent = self._get_agent(session.id)
        if agent is None:
            return False

        async for resumed_event in agent.acontinue_run(
            run_id=event.run_id,
            requirements=pending,
            stream=True,
            stream_events=True,
            yield_run_output=True,
        ):
            done = await self._dispatch(session, resumed_event, tool_spans, response_parts)
            if done and isinstance(resumed_event, (RunCompletedEvent, RunErrorEvent)):
                return True

        return False

    async def _on_content(
        self, session: Session, event: RunContentEvent, tool_spans: list, response_parts: list
    ) -> bool:
        if event.content:
            response_parts.append(str(event.content))
            await session.queue.put({"type": "message", "content": str(event.content)})
        return False

    async def _on_completed(
        self, session: Session, event: RunCompletedEvent, tool_spans: list, response_parts: list
    ) -> bool:
        payload: dict = {"type": "done"}
        if event.metrics:
            payload["input_tokens"] = event.metrics.input_tokens
            payload["output_tokens"] = event.metrics.output_tokens
            payload["total_tokens"] = event.metrics.total_tokens
        await session.queue.put(payload)
        return True

    async def _on_error(
        self, session: Session, event: RunErrorEvent, tool_spans: list, response_parts: list
    ) -> bool:
        await session.queue.put({"type": "error", "content": f"Agent error: {event.content}"})
        await session.queue.put({"type": "done"})
        self._remove_session(session.id)
        return True

    async def _on_tool_completed(
        self, session: Session, event: ToolCallCompletedEvent, tool_spans: list, response_parts: list
    ) -> bool:
        if event.tool:
            result = str(event.content)
            tool_spans.append({"tool": event.tool.tool_name, "result": result})
            await session.queue.put({
                "type": "tool_result",
                "tool_use_id": event.tool.tool_call_id,
                "tool_name": event.tool.tool_name,
                "result": result,
            })
        return False
