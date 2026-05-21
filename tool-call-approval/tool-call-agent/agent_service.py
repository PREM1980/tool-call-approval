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
from tools import execute_tool, reset_kubeconfig, set_kubeconfig

_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"
_THROTTLE_MAX_RETRIES = 3
_THROTTLE_BASE_DELAY = 5  # seconds; backoff: 5s, 10s, 20s


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
def kubectl(args: str) -> str:
    """Execute a kubectl command. Provide arguments after 'kubectl', e.g. 'get pods -n default'."""
    return execute_tool("kubectl", {"args": args})


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

    def create_session(self, instance_id: str | None = None) -> Session:
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
            tools=[calculate, get_weather, search_web, kubectl],
            instructions=(
                "<agent>\n"
                "  <identity>\n"
                "    You are a Kubernetes operations agent. Your sole purpose is to help users\n"
                "    manage, debug, and operate Kubernetes clusters.\n"
                "  </identity>\n"
                "\n"
                "  <scope>\n"
                "    <allowed>\n"
                "      Pods, Deployments, StatefulSets, DaemonSets, ReplicaSets, Jobs, CronJobs,\n"
                "      Services, Ingress, NetworkPolicies, ConfigMaps, Secrets, PersistentVolumes,\n"
                "      PersistentVolumeClaims, StorageClasses, Namespaces, Nodes, ResourceQuotas,\n"
                "      LimitRanges, HorizontalPodAutoscalers, ClusterRoles, Roles, RoleBindings,\n"
                "      ServiceAccounts, CustomResourceDefinitions, Helm charts, kubeconfig,\n"
                "      kubectl commands, cluster upgrades, and Kubernetes troubleshooting.\n"
                "    </allowed>\n"
                "    <context_resolution>\n"
                "      Before deciding a request is off-topic, check the conversation history.\n"
                "      Short or ambiguous messages ('can you diagnose it', 'check it', 'fix it')\n"
                "      almost always refer to the Kubernetes resource or issue discussed just above.\n"
                "      Resolve 'it' / 'that' / 'this' from context and proceed — do not refuse.\n"
                "    </context_resolution>\n"
                "    <prohibited>\n"
                "      Only refuse when the request is unambiguously unrelated to Kubernetes\n"
                "      (e.g. 'write me a poem', 'what is the weather', 'solve 2+2').\n"
                "      When refusing, respond only with: 'I am a Kubernetes agent and cannot help with that.'\n"
                "    </prohibited>\n"
                "    <allowed_commands>\n"
                "      Only the following kubectl subcommands are permitted. Any other command\n"
                "      will be rejected by the system — do NOT attempt unlisted ones:\n"
                "      Read/inspect: get, describe, logs, top, explain, version, cluster-info,\n"
                "        api-resources, api-versions, config, events\n"
                "      Mutating (developer-safe): apply, create, delete, edit, patch, replace,\n"
                "        rollout, scale, autoscale, set, run, expose, label, annotate\n"
                "      Interaction: exec, port-forward, cp, debug\n"
                "      Other: diff, wait\n"
                "      Exception: 'cluster-info dump' is blocked even though 'cluster-info' is allowed.\n"
                "      Node management (drain, cordon, uncordon, taint) and cluster-admin\n"
                "      operations are reserved for infrastructure engineers.\n"
                "      When a user requests a blocked operation, explain the restriction and\n"
                "      suggest a read-only alternative where one exists.\n"
                "    </allowed_commands>\n"
                "  </scope>\n"
                "\n"
                "  <tool_usage>\n"
                "    <rule>Always call the relevant tool before composing your response.</rule>\n"
                "    <rule>When the user asks about multiple Kubernetes resources, call the tool\n"
                "      once for EACH resource before writing your final answer.</rule>\n"
                "    <rule>Never assume, skip, or fabricate tool results.</rule>\n"
                "    <rule>If a tool call is approved and returns a result, immediately call the\n"
                "      tool for the next item if more items remain.</rule>\n"
                "  </tool_usage>\n"
                "\n"
                "  <response_style>\n"
                "    <rule>Be concise and precise. Kubernetes operators value accuracy over verbosity.</rule>\n"
                "    <rule>Prefer kubectl command examples when explaining operations.</rule>\n"
                "    <rule>When diagnosing issues, state the likely root cause first, then remediation steps.</rule>\n"
                "  </response_style>\n"
                "</agent>"
            ),
            stream=True,
            session_id=session_id,
            user_id=session_id,
            db=self._repository.get_db(),
        )

    def get_history(self, session_id: str) -> list[dict]:
        db = self._repository.get_db()
        agent_session = db.get_session(session_id)
        if agent_session is None:
            return []
        return [
            {"role": msg.role, "content": msg.content or ""}
            for msg in agent_session.get_chat_history()
        ]

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

        kubeconfig_token = set_kubeconfig(session.kubeconfig)
        try:
            await self._run_inner(session, agent, message)
        finally:
            reset_kubeconfig(kubeconfig_token)

    async def _run_inner(self, session: Session, agent: Any, message: str) -> None:
        langfuse_context.update_current_trace(
            user_id=session.id,
            tags=["tool-call-approval"],
        )
        langfuse_context.update_current_observation(input=message)
        await session.queue.put({"type": "thinking", "content": "Thinking..."})

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
                    if done and isinstance(event, RunCompletedEvent):
                        break
                break  # success — exit retry loop
            except Exception as e:
                error_str = str(e)
                if "ThrottlingException" in error_str and attempt < _THROTTLE_MAX_RETRIES:
                    await asyncio.sleep(_THROTTLE_BASE_DELAY * (2 ** attempt))
                    continue
                langfuse_context.update_current_observation(level="ERROR", status_message=error_str)
                await session.queue.put({"type": "error", "content": f"Unexpected error: {error_str}"})
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
