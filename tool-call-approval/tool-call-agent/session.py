import asyncio
from dataclasses import dataclass, field


@dataclass
class Session:
    id: str
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    # Per-tool approval used by the HITL batch path
    pending_approvals: dict[str, asyncio.Event] = field(default_factory=dict)
    approval_results: dict[str, bool] = field(default_factory=dict)
    kubeconfig: str | None = None
    tmpdir: str | None = None
