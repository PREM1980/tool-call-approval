import json
import os
import subprocess
from pathlib import Path

_KUBECONFIG_PATH = os.getenv("KUBECONFIG_PATH", "/data/kubeconfig.yaml")
_KUBECTL_TIMEOUT = 30
_SUFFIX = "-agent"


def write_kubeconfig(content: str) -> None:
    path = Path(_KUBECONFIG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _kubeconfig_exists() -> bool:
    return Path(_KUBECONFIG_PATH).exists()


def _run(args: list[str], stdin: str | None = None) -> str:
    if not _kubeconfig_exists():
        raise RuntimeError("kubeconfig not configured")
    result = subprocess.run(
        ["kubectl", "--kubeconfig", _KUBECONFIG_PATH] + args,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=_KUBECTL_TIMEOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"exit {result.returncode}")
    return result.stdout.strip()


def _derive_status(dep: dict) -> str:
    spec_replicas = dep.get("spec", {}).get("replicas", 1)
    ready = dep.get("status", {}).get("readyReplicas") or 0
    if ready >= spec_replicas:
        return "Running"
    conditions = dep.get("status", {}).get("conditions", [])
    for c in conditions:
        if c.get("type") == "Available" and c.get("status") == "False":
            return "Failed"
    return "Pending"


def _parse_deployment(dep: dict) -> dict:
    containers = (
        dep.get("spec", {})
        .get("template", {})
        .get("spec", {})
        .get("containers", [])
    )
    return {
        "name": dep["metadata"]["name"],
        "namespace": dep["metadata"].get("namespace", "default"),
        "image": containers[0]["image"] if containers else "",
        "replicas": dep.get("spec", {}).get("replicas", 1),
        "ready_replicas": dep.get("status", {}).get("readyReplicas") or 0,
        "status": _derive_status(dep),
    }


def create_deployment(
    name: str, image: str, namespace: str, replicas: int, env: list[dict]
) -> dict:
    full_name = f"{name}{_SUFFIX}"
    env_block = (
        "\n".join(f"        - name: {e['key']}\n          value: {json.dumps(str(e['value']))}" for e in env)
        if env else ""
    )
    manifest = f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {full_name}
  namespace: {namespace}
spec:
  replicas: {replicas}
  selector:
    matchLabels:
      app: {full_name}
  template:
    metadata:
      labels:
        app: {full_name}
    spec:
      containers:
      - name: {full_name}
        image: {image}
        imagePullPolicy: IfNotPresent
        env:
{env_block}
"""
    _run(["apply", "-f", "-"], stdin=manifest)
    raw = _run(["get", "deployment", full_name, "--namespace", namespace, "-o", "json"])
    return _parse_deployment(json.loads(raw))


def list_deployments() -> list[dict]:
    raw = _run(["get", "deployments", "--all-namespaces", "-o", "json"])
    data = json.loads(raw)
    return [
        _parse_deployment(dep)
        for dep in data.get("items", [])
        if dep["metadata"]["name"].endswith(_SUFFIX)
    ]


def delete_deployment(name: str, namespace: str) -> None:
    _run(["delete", "deployment", name, "--namespace", namespace])


def restart_deployment(name: str, namespace: str) -> None:
    _run(["rollout", "restart", f"deployment/{name}", "--namespace", namespace])


def scale_deployment(name: str, namespace: str, replicas: int) -> None:
    _run(["scale", "deployment", name, f"--replicas={replicas}", "--namespace", namespace])
