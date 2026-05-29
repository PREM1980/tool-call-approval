import subprocess

from langchain_core.tools import tool

_BLOCKED = {
    "delete", "rm", "remove", "terminate", "destroy",
    "drain", "cordon", "--force", "truncate", "drop", "stop", "kill",
}


def _check_safe(command: str) -> None:
    for token in command.lower().split():
        for blocked in _BLOCKED:
            if blocked in token:
                raise ValueError(f"Blocked destructive command token(s): {blocked}")


@tool
def execute_command(command: str) -> str:
    """Execute a kubectl or aws CLI command for SRE investigation. Read-only commands only."""
    _check_safe(command)
    try:
        result = subprocess.run(
            command.split(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout if result.returncode == 0 else result.stderr
    except FileNotFoundError as e:
        return f"Command not available: {e.filename}"
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds"
