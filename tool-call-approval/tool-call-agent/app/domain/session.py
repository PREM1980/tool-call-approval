from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Session:
    id: str
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    # Per-tool approval used by the HITL batch path
    pending_approvals: dict[str, asyncio.Event] = field(default_factory=dict)
    approval_results: dict[str, bool] = field(default_factory=dict)
    kubeconfig: str | None = None
    tmpdir: str | None = None
    instance_id: str | None = None
    persona_id: str | None = None
    persona_ids: list[str] = field(default_factory=list)
    persona_name: str | None = None
    persona_names: list[str] = field(default_factory=list)
    skill_ids: list[str] = field(default_factory=list)
    system_prompt_id: str | None = None
    system_prompt_name: str | None = None
    system_prompt_instructions_snapshot: str | None = None
    model_id: str | None = None
    provider: str | None = None
    active_tool_data: dict[str, list[dict[str, Any]]] = field(default_factory=lambda: {
        "cmds": [],
        "executed_cmds": [],
        "url_configs": [],
        "user_file_uploads": [],
    })
    active_tool_commands: dict[str, dict[str, Any]] = field(default_factory=dict)
