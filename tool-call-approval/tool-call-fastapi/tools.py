import math as _math

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

    return f"Unknown tool: {name}"
