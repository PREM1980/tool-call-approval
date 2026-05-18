import math as _math
import shlex
import subprocess

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


def _run_kubectl(args: str) -> str:
    try:
        parts = shlex.split(args)
    except ValueError as exc:
        return f"Error parsing kubectl args: {exc}"

    # Prevent callers from sneaking in a different binary
    if parts and parts[0].lower() == "kubectl":
        parts = parts[1:]

    result = subprocess.run(
        ["kubectl"] + parts,
        capture_output=True,
        text=True,
        timeout=_KUBECTL_TIMEOUT,
    )
    output = result.stdout.strip()
    if result.returncode != 0:
        stderr = result.stderr.strip()
        return f"Error (exit {result.returncode}):\n{stderr}" if stderr else f"Exit code {result.returncode}"
    return output or "(no output)"
