# Control-plane infrastructure (multi-cloud)

The `mfm` control plane in this repository is a stateless Linux container
(`src/mfm/`, packaged by the root `Dockerfile`). Nothing about the inventory
and lease API is Apple-Silicon-specific, so it can run on any cloud that can
run a Linux VM. Each directory here is a small, self-contained Terraform root
module that provisions one host for that container on a different provider:

| Provider  | Directory     | Compute resource            |
| --------- | ------------- | ---------------------------- |
| AWS       | `aws/`        | `aws_instance`                |
| GCP       | `gcp/`        | `google_compute_instance`     |
| Azure     | `azure/`      | `azurerm_linux_virtual_machine` |
| OpenStack | `openstack/`  | `openstack_compute_instance_v2` |
| AliCloud  | `alicloud/`   | `alicloud_instance`           |

Each module:

- provisions a single Ubuntu host with no inbound network access and HTTPS-only egress,
- boots it with the shared `cloud-init.yaml.tpl`, which pulls the published
  `ghcr.io/gerardrecinto/macos-fleet-matrix` image and runs `inventory sample`
  as a one-shot systemd unit — the same smoke test CI runs on every push,
- takes network/project identifiers (VPC, subnet, resource group, and
  similar) as required variables rather than assuming a specific account
  layout.

`terraform validate` and `terraform fmt -check` run for all five providers in
CI (see `.github/workflows/ci.yml`, job `terraform`) on every push. That
confirms each module is syntactically correct and internally consistent
against the current provider schema. None of them have been applied against
a live cloud account from this repository — there are no credentials, state
backend, or CI job that runs `terraform apply` here, on purpose, matching the
"public repository, private credentials" principle in the root README.

## What this does not cover

The macOS/Xcode image pipeline (`packer/`, `terraform/variables.tf`) and the
Tart runner fleet itself are a different tier and require real Apple Silicon
hardware — either on-prem Mac hardware or AWS EC2 Mac instances (the only
major-cloud offering with Apple's licensing to run macOS in a public cloud).
No Terraform in this directory creates a macOS host on any provider; that
would misrepresent what Terraform, or these clouds, can actually do.
