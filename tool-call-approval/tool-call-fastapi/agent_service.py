import asyncio
from typing import Any
from uuid import uuid4

from agno.agent import Agent
from agno.models.aws.bedrock import AwsBedrock
from agno.run.agent import (
    RunCompletedEvent,
    RunContentEvent,
    RunErrorEvent,
    RunPausedEvent,
    ToolCallCompletedEvent,
)
from agno.tools import tool
from langfuse.decorators import langfuse_context, observe

from repository import IAgentStorage
from session import Session
from tools import execute_tool

_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"


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


class AgentService:
    def __init__(self, repository: IAgentStorage) -> None:
        self._repository = repository
        self._sessions: dict[str, tuple[Session, Agent]] = {}
        self._handlers: dict[type, Any] = {
            RunPausedEvent: self._on_paused,
            RunContentEvent: self._on_content,
            RunCompletedEvent: self._on_completed,
            RunErrorEvent: self._on_error,
            ToolCallCompletedEvent: self._on_tool_completed,
        }

    # ── Session lifecycle ──────────────────────────────────────────────────

    def create_session(self) -> Session:
        session = Session(id=str(uuid4()))
        agent = self._build_agent(session.id)
        self._sessions[session.id] = (session, agent)
        return session

    def get_session(self, session_id: str) -> Session | None:
        pair = self._sessions.get(session_id)
        return pair[0] if pair else None

    def approve(self, session: Session, approved: bool) -> None:
        session.approval_result = approved
        session.approval_event.set()

    # ── Factory ───────────────────────────────────────────────────────────

    def _build_agent(self, session_id: str) -> Agent:
        return Agent(
            model=AwsBedrock(id=_MODEL_ID),
            tools=[calculate, get_weather, search_web],
            instructions=(
                "You are a helpful assistant with access to tools. "
                "Always use tools when appropriate to provide accurate information."
            ),
            stream=True,
            session_id=session_id,
            user_id=session_id,
            db=self._repository.get_db(),
        )

    def _get_agent(self, session_id: str) -> Agent | None:
        pair = self._sessions.get(session_id)
        return pair[1] if pair else None

    def _remove_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    # ── Run loop ──────────────────────────────────────────────────────────

    @observe(name="agent-run", capture_input=False, capture_output=False)
    async def run(self, session: Session, message: str) -> None:
        agent = self._get_agent(session.id)
        if agent is None:
            return

        langfuse_context.update_current_trace(
            user_id=session.id,
            tags=["tool-call-approval"],
        )
        langfuse_context.update_current_observation(input=message)
        await session.queue.put({"type": "thinking", "content": "Thinking..."})

        tool_spans: list = []
        response_parts: list = []

        try:
            async for event in agent.arun(
                message,
                stream=True,
                stream_events=True,
                yield_run_output=True,
            ):
                done = await self._dispatch(session, event, tool_spans, response_parts)
                if done and isinstance(event, RunCompletedEvent):
                    break
        except Exception as e:
            langfuse_context.update_current_observation(
                level="ERROR", status_message=str(e)
            )
            await session.queue.put({"type": "error", "content": f"Unexpected error: {str(e)}"})
            await session.queue.put({"type": "done"})
            self._remove_session(session.id)
            return

        final_output = "".join(response_parts)
        langfuse_context.update_current_observation(
            output=final_output,
            metadata={"tool_calls": tool_spans},
        )
        langfuse_context.update_current_trace(output=final_output)

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
        requirements = event.requirements or []
        requirement = next((r for r in requirements if r.needs_confirmation), None)
        if requirement is None or requirement.tool_execution is None:
            return False

        tool_execution = requirement.tool_execution
        await session.queue.put({
            "type": "tool_call_pending",
            "tool_use_id": tool_execution.tool_call_id,
            "tool_name": tool_execution.tool_name,
            "tool_input": tool_execution.tool_args or {},
        })

        session.approval_event.clear()
        await session.approval_event.wait()

        if not session.approval_result:
            requirement.reject()
            await session.queue.put({
                "type": "tool_rejected",
                "tool_use_id": tool_execution.tool_call_id,
                "tool_name": tool_execution.tool_name,
            })
            return False

        requirement.confirm()
        agent = self._get_agent(session.id)
        if agent is None:
            return False

        async for resumed_event in agent.acontinue_run(
            run_id=event.run_id,
            requirements=[requirement],
            stream=True,
            stream_events=True,
            yield_run_output=True,
        ):
            if isinstance(resumed_event, ToolCallCompletedEvent) and resumed_event.tool:
                result = str(resumed_event.content)
                tool_spans.append({"tool": tool_execution.tool_name, "result": result})
                await session.queue.put({
                    "type": "tool_result",
                    "tool_use_id": resumed_event.tool.tool_call_id,
                    "tool_name": resumed_event.tool.tool_name,
                    "result": result,
                })
            else:
                done = await self._dispatch(session, resumed_event, tool_spans, response_parts)
                if done:
                    return True

        return True

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
        await session.queue.put({"type": "done"})
        self._remove_session(session.id)
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
            await session.queue.put({
                "type": "tool_result",
                "tool_use_id": event.tool.tool_call_id,
                "tool_name": event.tool.tool_name,
                "result": str(event.content),
            })
        return False
