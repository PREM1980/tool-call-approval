"""Simple SSE client to test the agent and verify Langfuse tracing."""
import json
import sys
import httpx

BASE_URL = "http://localhost:8000"
DEFAULT_MESSAGE = "command to list all my pods?"


def run(message: str = DEFAULT_MESSAGE) -> None:
    with httpx.Client(timeout=60) as client:
        # 1. Create session
        session_id = client.post(
            f"{BASE_URL}/sessions",
            json={"session": {}, "messages": []},
        ).json()["session_id"]
        print(f"Session: {session_id}\n")

        # 2. Send message (non-blocking — agent runs in background)
        client.post(
            f"{BASE_URL}/sessions/{session_id}/chat",
            json={
                "session": {"session_id": session_id},
                "messages": [{"role": "user", "content": message}],
            },
        )
        print(f"You: {message}\n")
        print("Agent: ", end="", flush=True)

        # 3. Stream SSE events
        with client.stream("GET", f"{BASE_URL}/sessions/{session_id}/stream", timeout=None) as resp:
            for line in resp.iter_lines():
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[len("data:"):].strip())

                match event["type"]:
                    case "thinking":
                        print("(thinking...)", end=" ", flush=True)
                    case "message":
                        print(event.get("content", ""), end="", flush=True)
                    case "tool_call_pending":
                        tool_name = event.get("tool_name", "unknown")
                        tool_input = event.get("tool_input", {})
                        print(f"\n[Tool call: {tool_name}({tool_input})]")
                        answer = input("Approve? (y/n): ").strip().lower()
                        approved = answer == "y"
                        httpx.post(
                            f"{BASE_URL}/sessions/{session_id}/approve",
                            json={
                                "session": {"session_id": session_id},
                                "messages": [],
                                "approval": {
                                    "tool_use_id": event.get("tool_use_id"),
                                    "approved": approved,
                                },
                            },
                        )
                    case "tool_result":
                        print(f"\n[tool: {event['tool_name']} → {event['result']}]", end="\n", flush=True)
                    case "done":
                        print()
                        break
                    case "error":
                        print(f"\nError: {event.get('content')}", file=sys.stderr)
                        break

        print(f"\n\nTrace visible at: http://localhost:3000")


if __name__ == "__main__":
    message = " ".join(sys.argv[1:]) or DEFAULT_MESSAGE
    run(message)
