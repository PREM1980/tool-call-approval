import contextvars
import math as _math
import os
import shlex
import subprocess
import tempfile

_kubeconfig_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "kubeconfig", default=None
)


def set_kubeconfig(kubeconfig: str | None) -> contextvars.Token:
    return _kubeconfig_ctx.set(kubeconfig)


def reset_kubeconfig(token: contextvars.Token) -> None:
    _kubeconfig_ctx.reset(token)

TOOL_DEFINITIONS = [
    {
        "name": "calculate",
        "description": "Evaluate a mathematical expression. Use math.sqrt(), math.pi, etc. for math functions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A Python math expression, e.g. '2 + 3' or 'math.sqrt(16)'",
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name": "get_weather",
        "description": "Get current weather conditions for a city.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name, e.g. 'London'"}
            },
            "required": ["city"],
        },
    },
    {
        "name": "search_web",
        "description": "Search the web for information on a topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query string"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "kubectl",
        "description": (
            "Execute a kubectl command against the configured Kubernetes cluster. "
            "Provide only the arguments after 'kubectl', e.g. 'get pods -n default'. "
            "Read-only commands (get, describe, logs, top, explain, version, cluster-info) "
            "are preferred. Mutating commands (apply, delete, scale, rollout) require "
            "explicit user approval."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "args": {
                    "type": "string",
                    "description": "kubectl arguments, e.g. 'get pods -n kube-system -o wide'",
                }
            },
            "required": ["args"],
        },
    },
]

_WEATHER_DB = {
    "london": "Cloudy, 15°C, humidity 80%",
    "new york": "Sunny, 22°C, humidity 45%",
    "tokyo": "Rainy, 18°C, humidity 90%",
    "paris": "Partly cloudy, 17°C, humidity 60%",
    "sydney": "Clear, 25°C, humidity 50%",
}


def execute_tool(name: str, tool_input: dict) -> str:
    if name == "calculate":
        try:
            result = eval(  # noqa: S307
                tool_input["expression"],
                {"__builtins__": {}},
                {"math": _math},
            )
            return str(result)
        except Exception as exc:
            return f"Error: {exc}"

    if name == "get_weather":
        city = tool_input["city"]
        return _WEATHER_DB.get(city.lower(), f"Weather data unavailable for {city}")

    if name == "search_web":
        query = tool_input["query"]
        return (
            f"Search results for '{query}': "
            f"[Mock] Top result — Wikipedia article about {query}. "
            f"Additional results at example.com/search?q={query.replace(' ', '+')}"
        )

    if name == "kubectl":
        return _run_kubectl(tool_input["args"])

    return f"Unknown tool: {name}"


_KUBECTL_TIMEOUT = 30  # seconds

# Only developer-workflow commands are permitted; anything not in this set is rejected.
_ALLOWED_SUBCOMMANDS = {
    # Read / inspect
    "get", "describe", "logs", "top", "explain", "version",
    "cluster-info", "api-resources", "api-versions", "config", "events",
    # Mutating (namespace-scoped, developer-safe)
    "apply", "create", "delete", "edit", "patch", "replace",
    "rollout", "scale", "autoscale", "set",
    "run", "expose", "label", "annotate",
    # Interaction
    "exec", "port-forward", "cp", "debug",
    # Diff / dry-run
    "diff", "wait",
}

# Specific (subcommand, resource) pairs that are denied even though the subcommand is allowed.
_DENIED_ARGS: set[tuple[str, str]] = {
    # cluster-info dump exposes sensitive cluster data
    ("cluster-info", "dump"),
    # delete of cluster-scoped resources is an infra-engineer operation
    ("delete", "node"), ("delete", "nodes"), ("delete", "no"),
    ("delete", "namespace"), ("delete", "namespaces"), ("delete", "ns"),
    ("delete", "pv"), ("delete", "persistentvolume"), ("delete", "persistentvolumes"),
    ("delete", "clusterrole"), ("delete", "clusterroles"),
    ("delete", "clusterrolebinding"), ("delete", "clusterrolebindings"),
}


def _is_allowed(parts: list[str]) -> bool:
    if not parts:
        return False
    cmd = parts[0].lower()
    if cmd not in _ALLOWED_SUBCOMMANDS:
        return False
    if len(parts) >= 2 and (cmd, parts[1].lower()) in _DENIED_ARGS:
        return False
    return True


def _run_kubectl(args: str) -> str:
    try:
        parts = shlex.split(args)
    except ValueError as exc:
        return f"Error parsing kubectl args: {exc}"

    if parts and parts[0].lower() == "kubectl":
        parts = parts[1:]

    if not _is_allowed(parts):
        cmd = parts[0] if parts else "(empty)"
        return (
            f"Error: '{cmd}' is not an allowed kubectl command for this developer agent. "
            "Permitted operations cover get, describe, logs, apply, delete, rollout, scale, "
            "exec, port-forward, and similar developer workflows. Node management and "
            "cluster-admin operations are reserved for infrastructure engineers."
        )

    kubeconfig = _kubeconfig_ctx.get()
    env = os.environ.copy()
    tmp_path: str | None = None

    if kubeconfig:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as tmp:
            tmp.write(kubeconfig)
            tmp_path = tmp.name
        env["KUBECONFIG"] = tmp_path

    try:
        result = subprocess.run(
            ["kubectl"] + parts,
            capture_output=True,
            text=True,
            timeout=_KUBECTL_TIMEOUT,
            env=env,
        )
    finally:
        if tmp_path:
            os.unlink(tmp_path)

    output = result.stdout.strip()
    if result.returncode != 0:
        stderr = result.stderr.strip()
        return f"Error (exit {result.returncode}):\n{stderr}" if stderr else f"Exit code {result.returncode}"
    return output or "(no output)"
