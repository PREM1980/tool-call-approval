---
name: kubernetes-troubleshooting-runbook
description: structured diagnosis paths for common kubernetes failure modes. use when a pod, deployment, node, or service is in a failing or degraded state. maps each failure mode to a specific kubectl command sequence and what to look for in the output.
---

# Kubernetes Troubleshooting Runbook

## How to use this runbook

1. Identify the failure mode from the pod status or event type.
2. Run ALL commands for that failure mode in a single parallel turn — do not wait between calls.
3. Present findings using the Root Cause Analysis format at the bottom.

---

## CrashLoopBackOff

**What it means:** The container starts, crashes, and Kubernetes keeps restarting it.

**Commands to run (all at once):**
- `kubectl describe pod <pod> -n <ns>`
- `kubectl logs <pod> -n <ns> --previous`
- `kubectl logs <pod> -n <ns>` (current, if not yet crashed)
- `kubectl get events -n <ns> --field-selector involvedObject.name=<pod> --sort-by=.lastTimestamp`

**What to look for:**
- Exit code in `describe` → `OOMKilled` (exit 137) means memory limit hit; non-zero exit means application crash
- Last lines of `--previous` logs → application error, missing config, failed DB connection
- Liveness probe failure in events → probe misconfigured or app too slow to start
- `Back-off restarting failed container` event confirms the loop

---

## OOMKilled

**What it means:** The container exceeded its memory limit and was killed by the kernel.

**Commands to run (all at once):**
- `kubectl describe pod <pod> -n <ns>`
- `kubectl top pod <pod> -n <ns> --containers`
- `kubectl get pod <pod> -n <ns> -o yaml`

**What to look for:**
- `lastState.terminated.reason: OOMKilled` in describe or yaml
- Memory `requests` vs `limits` in the yaml — limits set too low or requests not set
- `kubectl top` showing memory near or at the limit before the kill
- Repeated restarts with exit code 137

---

## Pending (Pod stuck in Pending)

**What it means:** The scheduler cannot place the pod on any node.

**Commands to run (all at once):**
- `kubectl describe pod <pod> -n <ns>`
- `kubectl get nodes -o wide`
- `kubectl describe nodes` (if node pressure suspected)
- `kubectl get events -n <ns> --field-selector involvedObject.name=<pod>`

**What to look for:**
- `Events` section of describe → `Insufficient cpu`, `Insufficient memory`, `No nodes are available that match all of the following predicates`
- `kubectl get nodes` → any node in `NotReady` or `SchedulingDisabled`
- Taint/toleration mismatch in describe output
- PVC unbound → `kubectl get pvc -n <ns>` if pod mounts a volume

---

## ImagePullBackOff / ErrImagePull

**What it means:** Kubernetes cannot pull the container image.

**Commands to run (all at once):**
- `kubectl describe pod <pod> -n <ns>`
- `kubectl get events -n <ns> --field-selector involvedObject.name=<pod> --sort-by=.lastTimestamp`

**What to look for:**
- Image name and tag in describe → typo, wrong tag, or `:latest` on a private registry
- `Failed to pull image` event → `unauthorized` means missing or expired imagePullSecret; `not found` means wrong image name/tag
- `imagePullSecrets` in pod spec → missing or wrong secret name
- Registry reachability — if internal registry, check if registry pod is running

---

## CreateContainerConfigError

**What it means:** Kubernetes cannot create the container due to missing config (secret or configmap).

**Commands to run (all at once):**
- `kubectl describe pod <pod> -n <ns>`
- `kubectl get secret -n <ns>`
- `kubectl get configmap -n <ns>`

**What to look for:**
- `Error: secret "<name>" not found` or `configmap "<name>" not found` in events
- Cross-reference pod spec `envFrom` / `env.valueFrom` / `volumes` against what actually exists in the namespace

---

## Service not reachable / no traffic

**What it means:** A service exists but requests are not reaching pods.

**Commands to run (all at once):**
- `kubectl describe svc <svc> -n <ns>`
- `kubectl get endpoints <svc> -n <ns>`
- `kubectl get pods -n <ns> -l <selector-from-service>`
- `kubectl describe ingress -n <ns>` (if ingress is involved)

**What to look for:**
- `Endpoints` is `<none>` → label selector on the service does not match any running pod labels
- Pods are running but not Ready → failing readiness probe prevents them from being added to endpoints
- Port mismatch → service `targetPort` does not match container `containerPort`
- Ingress backend service name or port wrong

---

## Node NotReady

**What it means:** A node has lost contact with the control plane or has a local condition preventing scheduling.

**Commands to run (all at once):**
- `kubectl describe node <node>`
- `kubectl get pods --all-namespaces --field-selector spec.nodeName=<node>`
- `kubectl get events --all-namespaces --field-selector involvedObject.name=<node>`

**What to look for:**
- `Conditions` block → `MemoryPressure`, `DiskPressure`, `PIDPressure`, or `KubeletNotReady`
- `kubelet stopped posting node status` in events → kubelet process down or network partition
- Evicted pods on that node → node was under pressure before going NotReady

---

## Root Cause Analysis output format

Use this structure when presenting findings for any failure mode:

**What failed:** one sentence describing the resource and symptom

**Probable cause:** one sentence identifying the root cause found in logs/events/describe

**Evidence:**
- bullet list of key findings (exit code, event message, missing resource name, etc.)

**Recommended fix:** concrete next step (update resource limit, add imagePullSecret, fix label selector, etc.)
