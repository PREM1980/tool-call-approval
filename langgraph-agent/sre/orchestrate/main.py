import sys

from sre.orchestrate.graph import OrchestrateState, build_graph


def run(query: str) -> dict:
    app = build_graph()
    initial_state: OrchestrateState = {
        "query": query,
        "domain": "",
        "messages": [],
        "agents_called": [],
        "conclusion": "",
        "escalate_to": "",
        "resolution": "",
    }
    result = app.invoke(initial_state)
    return {
        "agent": result["domain"],
        "agents_called": result["agents_called"],
        "diagnosis": result["conclusion"],
        "resolution": result["resolution"],
        "steps_taken": len(result["agents_called"]),
    }


def pretty_print(output: dict) -> None:
    print("\n=== SRE Orchestrator Result ===")
    print(f"Domain   : {output['agent']}")
    print(f"Chain    : {' → '.join(output['agents_called'])}")
    print(f"Steps    : {output['steps_taken']}")
    print(f"Diagnosis: {output['diagnosis']}")
    print(f"\nResolution:\n{output['resolution']}")


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Pods are crashing in the default namespace"
    output = run(query)
    pretty_print(output)
