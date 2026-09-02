# Continuous deployment (ArgoCD)

`application.yaml` is a real ArgoCD `Application` resource. It points at
`deploy/k8s/control-plane` in this repository, watches `main`, and syncs
automatically with pruning and self-heal enabled — the standard GitOps loop:
a change merged to `main` is the only way a manifest change reaches a
cluster running this Application.

What it deploys is described in
[`deploy/k8s/control-plane`](../k8s/control-plane): a namespace and a
CronJob that pulls the real published `ghcr.io/gerardrecinto/macos-fleet-matrix`
image and runs `inventory sample` on a schedule. The control plane is a CLI,
not a server (see the root README's "Container image" section), so a
`Deployment` here would misrepresent what the container does — a periodic
smoke check is the honest Kubernetes-native equivalent of what the Terraform
cloud-init templates in `terraform/control-plane/` already do on a VM.

## Validation vs. deployment

CI (`.github/workflows/ci.yml`, job `k8s-manifests`) runs
`kubectl kustomize deploy/k8s/control-plane | kubeconform -strict`, validating
the rendered manifests against the real Kubernetes OpenAPI schema, and
validates `application.yaml` itself against ArgoCD's `Application` CRD schema
from the community CRDs-catalog. That confirms every manifest here is
well-formed and schema-valid.

None of it has been applied to a live cluster from this repository. `spec.destination.server` is ArgoCD's own placeholder for "the cluster ArgoCD
runs in" (`https://kubernetes.default.svc`) — not a claim that an ArgoCD
instance has ever registered or synced this Application. There is no cluster
endpoint, kubeconfig, or ArgoCD credential in this repository, on purpose,
matching the "public repository, private credentials" principle in the root
README.
