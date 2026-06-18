import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

@dataclass
class Session:
    id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    approval_event: asyncio.Event = field(default_factory=asyncio.Event)
    approval_result: bool = False


def _extract_after(message: str, *prefixes: str) -> str:
    """Return text after the first matching prefix, else the full message."""
    lower = message.lower()
    for prefix in prefixes:
        idx = lower.find(prefix)
        if idx != -1:
            return message[idx + len(prefix):].strip(" ?.")
    return message.strip()


_TOOL_SCENARIOS = [
    {
        "keywords": ["calculat", "math", "×", "*", "sqrt", "square root", "percent", "%"],
        "tool_name": "calculate",
        "tool_input_fn": lambda msg: {"expression": _extract_after(msg, "calculate ", "math ", "what is ", "what's ")},
        "result": "7,006,652",
        "message": "The calculation is complete. 1234 × 5678 = **7,006,652**.",
    },
    {
        "keywords": ["weather", "temperature", "forecast", "rain", "sunny"],
        "tool_name": "get_weather",
        "tool_input_fn": lambda msg: {"city": _extract_after(msg, "weather in ", "weather for ", "forecast for ", "temperature in ")},
        "result": "Partly cloudy, 18°C, humidity 65%, wind 12 km/h NW",
        "message": "Current conditions: partly cloudy, 18°C with 65% humidity and a light north-westerly breeze.",
    },
    {
        "keywords": ["search", "find", "look up", "black hole", "information about"],
        "tool_name": "search_web",
        "tool_input_fn": lambda msg: {"query": _extract_after(msg, "search for ", "search ", "find ", "look up ", "information about ")},
        "result": "Found 8 relevant results.",
        "message": (
            "Here's what I found: Black holes are regions of spacetime where gravity is so strong "
            "that nothing — not even light — can escape once it crosses the event horizon. "
            "They form when massive stars collapse at the end of their life cycle."
        ),
    },
]

_FALLBACK = (
    "I'm a mock assistant running without an API key. "
    "Try asking me to **calculate** something, check the **weather** in a city, "
    "or **search** for a topic — I'll simulate a full tool-approval flow."
)


async def run_agent(session: Session, user_message: str) -> None:
    session.messages.append({"role": "user", "content": user_message})
    await session.queue.put({"type": "thinking", "content": "Thinking..."})
    await asyncio.sleep(1.0)

    msg_lower = user_message.lower()
    scenario = next(
        (s for s in _TOOL_SCENARIOS if any(k in msg_lower for k in s["keywords"])),
        None,
    )

    if scenario:
        tool_use_id = f"mock_{uuid.uuid4().hex[:8]}"

        await session.queue.put({
            "type": "tool_call_pending",
            "tool_use_id": tool_use_id,
            "tool_name": scenario["tool_name"],
            "tool_input": scenario["tool_input_fn"](user_message),
        })

        session.approval_event.clear()
        await session.approval_event.wait()

        if session.approval_result:
            await asyncio.sleep(0.6)
            await session.queue.put({
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "tool_name": scenario["tool_name"],
                "result": scenario["result"],
            })
            await asyncio.sleep(0.4)
            await session.queue.put({"type": "message", "content": scenario["message"]})
        else:
            await session.queue.put({
                "type": "tool_rejected",
                "tool_use_id": tool_use_id,
                "tool_name": scenario["tool_name"],
            })
            await asyncio.sleep(0.3)
            await session.queue.put({
                "type": "message",
                "content": "Understood, I won't use that tool. Is there anything else I can help with?",
            })
    else:
        await session.queue.put({"type": "message", "content": _FALLBACK})

    await session.queue.put({"type": "done"})
