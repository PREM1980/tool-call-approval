import asyncio
from dataclasses import dataclass, field


@dataclass
class Session:
    id: str
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    approval_event: asyncio.Event = field(default_factory=asyncio.Event)
    approval_result: bool = False
    kubeconfig: str | None = None
