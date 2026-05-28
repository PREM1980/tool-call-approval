import sys

from sre.graph import SREState, build_graph


def run(query: str) -> dict:
    app = build_graph()
    initial_state: SREState = {
        "query": query,
        "domain": "",
        "reasoning": [],
        "conclusion": "",
        "iterations": 0,
    }
    result = app.invoke(initial_state)
    return {
        "agent": result["domain"],
        "diagnosis": result["conclusion"],
        "steps_taken": len(result["reasoning"]),
    }


def pretty_print(output: dict) -> None:
    print("\n=== SRE Agent Result ===")
    print(f"Domain   : {output['agent']}")
    print(f"Steps    : {output['steps_taken']}")
    print(f"Diagnosis: {output['diagnosis']}")


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Pods are crashing in the default namespace"
    output = run(query)
    pretty_print(output)
