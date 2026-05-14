import asyncio
from dataclasses import dataclass, field
from typing import Any

from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.run.agent import (
    RunCompletedEvent,
    RunContentEvent,
    RunErrorEvent,
    RunPausedEvent,
    ToolCallCompletedEvent,
)
from agno.tools import tool
from agno.run.requirement import RunRequirement
from dotenv import load_dotenv

from tools import execute_tool

load_dotenv()


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


@dataclass
class Session:
    id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    agent: Agent = field(init=False)
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    approval_event: asyncio.Event = field(default_factory=asyncio.Event)
    approval_result: bool = False

    def __post_init__(self):
        self.agent = Agent(
            model=Claude(id="claude-sonnet-4-6"),
            tools=[calculate, get_weather, search_web],
            instructions="You are a helpful assistant with access to tools. Always use tools when appropriate to provide accurate information.",
            stream=True,
        )


async def _send_message(session: Session, content: str) -> None:
    await session.queue.put({"type": "message", "content": content})


async def _send_tool_pending(session: Session, tool_execution: Any) -> None:
    await session.queue.put(
        {
            "type": "tool_call_pending",
            "tool_use_id": tool_execution.tool_call_id,
            "tool_name": tool_execution.tool_name,
            "tool_input": tool_execution.tool_args or {},
        }
    )


async def _send_tool_result(session: Session, tool_execution: Any, result: Any) -> None:
    await session.queue.put(
        {
            "type": "tool_result",
            "tool_use_id": tool_execution.tool_call_id,
            "tool_name": tool_execution.tool_name,
            "result": str(result),
        }
    )


async def _send_tool_rejected(session: Session, tool_execution: Any) -> None:
    await session.queue.put(
        {
            "type": "tool_rejected",
            "tool_use_id": tool_execution.tool_call_id,
            "tool_name": tool_execution.tool_name,
        }
    )


async def _process_event(session: Session, event: Any) -> bool:
    if isinstance(event, RunPausedEvent):
        requirements = event.requirements or []
        requirement = next((req for req in requirements if req.needs_confirmation), None)
        if requirement is None or requirement.tool_execution is None:
            return False

        tool_execution = requirement.tool_execution
        await _send_tool_pending(session, tool_execution)

        session.approval_event.clear()
        await session.approval_event.wait()

        if session.approval_result:
            requirement.confirm()
        else:
            requirement.reject()
            await _send_tool_rejected(session, tool_execution)

        async for resumed_event in session.agent.acontinue_run(
            run_id=event.run_id,
            requirements=[requirement],
            stream=True,
            stream_events=True,
            yield_run_output=True,
        ):
            if await _process_event(session, resumed_event):
                return True

        return True

    if isinstance(event, ToolCallCompletedEvent):
        if event.tool:
            await _send_tool_result(session, event.tool, event.content)
        return False

    if isinstance(event, RunContentEvent):
        if event.content:
            await _send_message(session, str(event.content))
        return False

    if isinstance(event, RunCompletedEvent):
        await session.queue.put({"type": "done"})
        return True

    if isinstance(event, RunErrorEvent):
        await session.queue.put({"type": "error", "content": f"Agent error: {event.content}"})
        await session.queue.put({"type": "done"})
        return True

    return False


async def run_agent(session: Session, user_message: str) -> None:
    session.messages.append({"role": "user", "content": user_message})
    await session.queue.put({"type": "thinking", "content": "Thinking..."})

    try:
        async for event in session.agent.arun(
            user_message,
            stream=True,
            stream_events=True,
            yield_run_output=True,
        ):
            handled = await _process_event(session, event)
            if handled and isinstance(event, RunCompletedEvent):
                break
    except Exception as e:
        await session.queue.put({"type": "error", "content": f"Unexpected error: {str(e)}"})
        await session.queue.put({"type": "done"})

