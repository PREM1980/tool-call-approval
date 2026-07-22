# Kubernetes deployment

This directory deploys the three images built by the GitLab pipeline:
`tool-call-agent`, `tool-call-api`, and `tool-call-k8s`. PostgreSQL is included as
an in-cluster dependency with ephemeral storage for development.

Before deploying, create a real `secret.yaml` from `secret.example.yaml` and set
the database URLs to use the same password as `POSTGRES_PASSWORD`. The real
secret is ignored by Git.

The cluster also needs pull credentials for the private Artifactory registry:

```sh
kubectl create namespace tool-call-approval
kubectl -n tool-call-approval create secret docker-registry artifactory-registry \
  --docker-server=10.49.19.241 \
  --docker-username=service-account \
  --docker-password="$ARTIFACTORY_TOKEN"
kubectl apply -f k8s-deploy/secret.yaml
kubectl apply -k k8s-deploy/
```

`tool-call-k8s` uses a saved kubeconfig to manage other workloads. Grant its
service account only the permissions appropriate for the target namespace before
using that API in a shared cluster.
