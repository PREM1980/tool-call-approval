from __future__ import annotations

import asyncio
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fpdf import FPDF
from os import getenv

import httpx
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

from app.domain.session import Session
from app.repositories.admin_repository import AdminRepository
from app.repositories.agent_repository import IAgentStorage
from app.core.system_prompts import (
    DEFAULT_INSTRUCTIONS as _DEFAULT_INSTRUCTIONS,
    DEFAULT_SYSTEM_PROMPT_NAME as _DEFAULT_SYSTEM_PROMPT_NAME,
)
from app.tools.registry import execute_tool, reset_kubeconfig, set_kubeconfig

_AWS_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
_GCP_MODEL_ID = "claude-sonnet-4-6"
_LOCAL_MODEL_ID = "nemotron-3-super"
_LOCAL_BASE_URL = "https://models.k8s.aip.mitre.org/v1"
_THROTTLE_MAX_RETRIES = 3
_THROTTLE_BASE_DELAY = 5  # seconds; backoff: 5s, 10s, 20s
_AUTO_APPROVE = getenv("AUTO_APPROVE_TOOLS", "false").lower() == "true"
_APPROVAL_TIMEOUT = float(getenv("APPROVAL_TIMEOUT_SECONDS", "300"))  # 5 minutes
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---", re.DOTALL)
_SKILL_NAME_RE = re.compile(r"^\s*name\s*:\s*(?P<name>.+?)\s*$", re.MULTILINE)


def _build_model(model_id: str | None = None, provider: str | None = None) -> Any:
    provider = (provider or getenv("LLM_PROVIDER", "AWS")).upper()
    if provider == "GCP":
        return VertexAIClaude(
            id=_GCP_MODEL_ID,
            project_id=getenv("GOOGLE_CLOUD_PROJECT"),
            region=getenv("GOOGLE_CLOUD_LOCATION", "us-east5"),
            request_params={
                "tool_choice": {"type": "auto", "disable_parallel_tool_use": False}
            },
        )
    if provider == "LOCAL":
        from agno.models.openai import OpenAILike

        api_key = getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY is required when LLM_PROVIDER=LOCAL")
        if not api_key.startswith("sk-"):
            raise EnvironmentError("OPENAI_API_KEY must start with 'sk-' for LLM_PROVIDER=LOCAL")
        verify_ssl = getenv("LOCAL_VERIFY_SSL", "true").lower() not in {"0", "false", "no"}
        local_ca_bundle = getenv("LOCAL_CA_BUNDLE")
        http_client = None
        if local_ca_bundle:
            http_client = httpx.AsyncClient(verify=local_ca_bundle)
        elif not verify_ssl:
            http_client = httpx.AsyncClient(verify=False)
        local_kwargs: dict[str, Any] = {}
        if http_client is not None:
            local_kwargs["http_client"] = http_client
        return OpenAILike(
            id=model_id or getenv("MODEL_ID") or getenv("LOCAL_MODEL_ID", _LOCAL_MODEL_ID),
            api_key=api_key,
            base_url=getenv("BASE_URL") or getenv("LOCAL_BASE_URL", _LOCAL_BASE_URL),
            **local_kwargs,
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
        persona_id: str | None = None,
        persona_ids: list[str] | None = None,
        system_prompt_id: str | None = None,
        model_id: str | None = None,
        provider: str | None = None,
    ) -> Session:
        session = Session(id=str(uuid4()))
        prompt = self._resolve_system_prompt(system_prompt_id)
        selected_persona_ids = self._selected_persona_ids(persona_id, persona_ids)
        agent, tmpdir, personas = self._build_agent(
            session.id,
            instance_id,
            persona_id,
            selected_persona_ids,
            prompt["instructions"],
            model_id,
            provider,
        )
        session.tmpdir = tmpdir
        session.instance_id = instance_id
        self._apply_persona_snapshot(session, persona_id, personas)
        session.system_prompt_id = prompt["id"]
        session.system_prompt_name = prompt["name"]
        session.system_prompt_instructions_snapshot = prompt["instructions"]
        session.model_id = model_id
        session.provider = provider
        self._sessions[session.id] = (session, agent)
        return session

    def get_session(self, session_id: str) -> Session | None:
        pair = self._sessions.get(session_id)
        return pair[0] if pair else None

    def approve(self, session: Session, tool_use_id: str | None, approved: bool) -> None:
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
        persona_id: str | None = None,
        persona_ids: list[str] | None = None,
        instructions: str | None = None,
        model_id: str | None = None,
        provider: str | None = None,
    ) -> tuple[Agent, str, list[dict[str, Any]]]:
        selected_persona_ids = self._selected_persona_ids(persona_id, persona_ids)
        if selected_persona_ids:
            tmpdir, skills_obj, personas = self._load_personas_skills(selected_persona_ids)
        elif instance_id:
            tmpdir, skills_obj, personas = self._load_instance_skills(instance_id)
        else:
            tmpdir, skills_obj, personas = None, None, []

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
            model=_build_model(model_id, provider),
            tools=[calculate, get_weather, search_web, kubectl, save_report],
            instructions=instructions or _DEFAULT_INSTRUCTIONS,
            stream=True,
            session_id=session_id,
            user_id=session_id,
            add_history_to_context=True,
            num_history_runs=5,
        )
        if db is not None:
            agent_kwargs["db"] = db
        if skills_obj is not None:
            agent_kwargs["skills"] = skills_obj
        return Agent(**agent_kwargs), tmpdir, personas

    def _selected_persona_ids(
        self,
        persona_id: str | None,
        persona_ids: list[str] | None,
    ) -> list[str]:
        selected: list[str] = []
        for current_id in persona_ids or []:
            if current_id and current_id not in selected:
                selected.append(current_id)
        if persona_id and persona_id not in selected:
            selected.insert(0, persona_id)
        return selected

    def _apply_persona_snapshot(
        self,
        session: Session,
        fallback_persona_id: str | None,
        personas: list[dict[str, Any]],
    ) -> None:
        session.persona_ids = [
            str(persona["id"])
            for persona in personas
            if persona.get("id")
        ]
        session.persona_names = [
            str(persona["name"])
            for persona in personas
            if persona.get("name")
        ]
        session.persona_id = session.persona_ids[0] if session.persona_ids else fallback_persona_id
        session.persona_name = session.persona_names[0] if session.persona_names else None
        session.skill_ids = self._unique_skill_ids(personas)

    def _unique_skill_ids(self, personas: list[dict[str, Any]]) -> list[str]:
        skill_ids: list[str] = []
        for persona in personas:
            for skill_id in persona.get("skill_ids") or []:
                if skill_id not in skill_ids:
                    skill_ids.append(skill_id)
        return skill_ids

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

    def _load_instance_skills(
        self,
        instance_id: str,
    ) -> tuple[str | None, Any, list[dict[str, Any]]]:
        """Resolve instance → persona → skills; write to tmpdir."""
        instance = self._admin_repository.get_agent_instance(instance_id)
        if not instance or not instance.get("persona_id"):
            return None, None, []

        return self._load_personas_skills([str(instance["persona_id"])])

    def _load_persona_skills(
        self,
        persona_id: str,
    ) -> tuple[str | None, Any, dict[str, Any] | None]:
        tmpdir, skills_obj, personas = self._load_personas_skills([persona_id])
        return tmpdir, skills_obj, personas[0] if personas else None

    def _load_personas_skills(
        self,
        persona_ids: list[str],
    ) -> tuple[str | None, Any, list[dict[str, Any]]]:
        personas: list[dict[str, Any]] = []
        skill_ids: list[str] = []

        for persona_id in persona_ids:
            persona = self._admin_repository.get_persona(persona_id)
            if not persona:
                continue
            personas.append(persona)
            for skill_id in persona.get("skill_ids") or []:
                if skill_id not in skill_ids:
                    skill_ids.append(skill_id)

        if not skill_ids:
            return None, None, personas

        tmpdir = tempfile.mkdtemp(prefix="agno_skills_")
        loaded = 0
        for skill_id in skill_ids:
            result = self._admin_repository.get_skill_content(skill_id)
            if not result:
                continue
            filename, content = result
            skill_name = self._skill_directory_name(filename, content)
            skill_dir = Path(tmpdir) / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(content)
            loaded += 1

        if loaded == 0:
            shutil.rmtree(tmpdir, ignore_errors=True)
            return None, None, personas

        return tmpdir, Skills(loaders=[LocalSkills(tmpdir)]), personas

    def _skill_directory_name(self, filename: str, content: str) -> str:
        frontmatter = _FRONTMATTER_RE.match(content)
        if frontmatter:
            name_match = _SKILL_NAME_RE.search(frontmatter.group("body"))
            if name_match:
                skill_name = name_match.group("name").strip().strip("\"'")
                if skill_name:
                    return self._safe_skill_directory_name(skill_name)
        return self._safe_skill_directory_name(Path(filename).stem)

    def _safe_skill_directory_name(self, skill_name: str) -> str:
        cleaned = skill_name.replace("/", "-").replace("\\", "-").strip()
        return cleaned or "skill"

    def get_history(self, session_id: str) -> list[dict]:
        return self._repository.get_session_history(session_id)

    def record_user_message(
        self,
        session: Session,
        message: str,
        message_object: dict[str, Any] | None = None,
    ) -> None:
        self._repository.append_session_message(
            session.id,
            "user",
            message,
            session.instance_id,
            session.system_prompt_id,
            session.system_prompt_name,
            session.system_prompt_instructions_snapshot,
            message=message_object,
        )

    def record_agent_message(self, session: Session, message: str) -> None:
        tool_data = self._clone_tool_data(session.active_tool_data)
        message_object = {
            "role": "assistant",
            "content": message,
            "data": tool_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": None,
            "agent": self._agent_message_metadata(session),
        }

        self._repository.append_session_message(
            session.id,
            "assistant",
            message,
            message=message_object,
        )

    def _agent_message_metadata(self, session: Session) -> dict[str, Any]:
        return {
            "session_id": session.id,
            "instance_id": session.instance_id,
            "persona_id": session.persona_id,
            "persona_ids": session.persona_ids,
            "persona_name": session.persona_name,
            "persona_names": session.persona_names,
            "skill_ids": session.skill_ids,
            "system_prompt_id": session.system_prompt_id,
            "system_prompt_name": session.system_prompt_name,
            "model_id": session.model_id,
            "provider": session.provider,
        }

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

        self._reset_tool_data(session)
        kubeconfig_token = set_kubeconfig(session.kubeconfig)
        try:
            final_output = await self._run_inner(session, agent, message)
            if final_output:
                self.record_agent_message(session, final_output)
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
                    if done:
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
            self._track_tool_command(session, tid, req.tool_execution.tool_name, req.tool_execution.tool_args or {})

        if _AUTO_APPROVE:
            for req in pending:
                tid = req.tool_execution.tool_call_id
                del session.pending_approvals[tid]
                self._mark_tool_approval(session, tid, True)
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
                self._mark_tool_approval(session, tid, approved)
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
            content = str(event.content)
            tool_args = event.tool.tool_args or {}
            args_str = ", ".join(f"{k}={v}" for k, v in tool_args.items())
            # Extract "completed in X.XXXXs" from Agno's string; use full args instead of truncated
            import re as _re
            elapsed = next(iter(_re.findall(r"completed in [\d.]+s", content)), "")
            display = f"{event.tool.tool_name}({args_str}) {elapsed}".strip()
            tool_spans.append({"tool": event.tool.tool_name, "result": display})
            self._track_tool_result(session, event.tool.tool_call_id, display)
            await session.queue.put({
                "type": "tool_result",
                "tool_use_id": event.tool.tool_call_id,
                "tool_name": event.tool.tool_name,
                "result": display,
            })
        return False

    def _reset_tool_data(self, session: Session) -> None:
        session.active_tool_data = {
            "cmds": [],
            "executed_cmds": [],
            "url_configs": [],
            "user_file_uploads": [],
        }
        session.active_tool_commands.clear()

    def _track_tool_command(
        self,
        session: Session,
        tool_use_id: str,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> None:
        command = {
            "command": self._format_tool_command(tool_name, tool_input),
            "execute": False,
        }
        session.active_tool_commands[tool_use_id] = command
        session.active_tool_data["cmds"].append(command)

    def _mark_tool_approval(self, session: Session, tool_use_id: str, approved: bool) -> None:
        command = session.active_tool_commands.get(tool_use_id)
        if not command:
            return
        command["execute"] = approved
        if approved:
            command.pop("rejection_reason", None)
        else:
            command["rejection_reason"] = "User rejected tool call"

    def _track_tool_result(self, session: Session, tool_use_id: str, output: str) -> None:
        command = session.active_tool_commands.get(tool_use_id)
        if not command:
            return
        command["execute"] = True
        command.pop("rejection_reason", None)
        session.active_tool_data["executed_cmds"].append({
            "command": command["command"],
            "output": output,
        })

    def _format_tool_command(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        if tool_name == "kubectl":
            args = str(tool_input.get("args") or "").strip()
            return f"kubectl {args}".strip()
        if not tool_input:
            return tool_name
        return f"{tool_name}({tool_input})"

    def _has_tool_data(self, data: dict[str, list[dict[str, Any]]]) -> bool:
        return bool(data["cmds"] or data["executed_cmds"])

    def _clone_tool_data(
        self,
        data: dict[str, list[dict[str, Any]]],
    ) -> dict[str, list[dict[str, Any]]]:
        return {
            "cmds": [dict(command) for command in data["cmds"]],
            "executed_cmds": [dict(command) for command in data["executed_cmds"]],
            "url_configs": [dict(config) for config in data["url_configs"]],
            "user_file_uploads": [dict(file) for file in data["user_file_uploads"]],
        }
