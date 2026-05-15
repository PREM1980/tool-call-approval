import asyncio
from dataclasses import dataclass, field
from typing import Any

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
from agno.run.requirement import RunRequirement
from dotenv import load_dotenv
from langfuse.decorators import langfuse_context, observe

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
            model=AwsBedrock(id="us.anthropic.claude-sonnet-4-20250514-v1:0"),
            tools=[calculate, get_weather, search_web],
            instructions="You are a helpful assistant with access to tools. Always use tools when appropriate to provide accurate information.",
            stream=True,
            cache_session=True,
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


async def _process_event(session: Session, event: Any, tool_spans: list, response_parts: list) -> bool:
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
            return False

        async for resumed_event in session.agent.acontinue_run(
            run_id=event.run_id,
            requirements=[requirement],
            stream=True,
            stream_events=True,
            yield_run_output=True,
        ):
            if isinstance(resumed_event, ToolCallCompletedEvent) and resumed_event.tool:
                result = str(resumed_event.content)
                tool_spans.append({"tool": tool_execution.tool_name, "result": result})
                await _send_tool_result(session, resumed_event.tool, resumed_event.content)
            elif await _process_event(session, resumed_event, tool_spans, response_parts):
                return True

        return True

    if isinstance(event, ToolCallCompletedEvent):
        if event.tool:
            await _send_tool_result(session, event.tool, event.content)
        return False

    if isinstance(event, RunContentEvent):
        if event.content:
            response_parts.append(str(event.content))
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


@observe(name="agent-run", capture_input=False, capture_output=False)
async def run_agent(session: Session, user_message: str) -> None:
    langfuse_context.update_current_trace(
        user_id=session.id,
        tags=["tool-call-approval"],
    )
    langfuse_context.update_current_observation(input=user_message)

    session.messages.append({"role": "user", "content": user_message})
    await session.queue.put({"type": "thinking", "content": "Thinking..."})

    tool_spans: list = []
    response_parts: list = []

    try:
        async for event in session.agent.arun(
            user_message,
            stream=True,
            stream_events=True,
            yield_run_output=True,
        ):
            handled = await _process_event(session, event, tool_spans, response_parts)
            if handled and isinstance(event, RunCompletedEvent):
                break
    except Exception as e:
        langfuse_context.update_current_observation(
            level="ERROR",
            status_message=str(e),
        )
        await session.queue.put({"type": "error", "content": f"Unexpected error: {str(e)}"})
        await session.queue.put({"type": "done"})
        return

    final_output = "".join(response_parts)
    langfuse_context.update_current_observation(
        output=final_output,
        metadata={"tool_calls": tool_spans, "turn": len(session.messages)},
    )
    langfuse_context.update_current_trace(output=final_output)
