# Control-plane infrastructure (multi-cloud)

The `mfm` control plane in this repository is a stateless Linux container
(`src/mfm/`, packaged by the root `Dockerfile`). Nothing about the inventory
and lease API is Apple-Silicon-specific, so it can run on any cloud that can
run a Linux VM. This directory provisions one host for that container per
provider, structured the way HashiCorp's own guidance recommends splitting
reusable modules from the environments that call them:
<https://developer.hashicorp.com/terraform/cloud-docs/recommended-practices>.

```text
control-plane/
  root.hcl              Terragrunt root config shared by every stack below
                         (local backend, common inputs — see "Terragrunt")
  modules/               reusable, provider-scoped Terraform modules
    aws/                 versions.tf, variables.tf, network.tf, compute.tf, outputs.tf
    gcp/                 same file split
    azure/                same file split
    openstack/            same file split
    alicloud/             same file split
  live/                  one Terragrunt stack per provider — the actual
                          "environment" that calls a module with real inputs
    aws/terragrunt.hcl
    gcp/terragrunt.hcl
    azure/terragrunt.hcl
    openstack/terragrunt.hcl
    alicloud/terragrunt.hcl
```

| Provider  | Module            | Compute resource                  |
| --------- | ----------------- | ---------------------------------- |
| AWS       | `modules/aws/`      | `aws_instance`                       |
| GCP       | `modules/gcp/`      | `google_compute_instance`            |
| Azure     | `modules/azure/`    | `azurerm_linux_virtual_machine`      |
| OpenStack | `modules/openstack/`| `openstack_compute_instance_v2`      |
| AliCloud  | `modules/alicloud/` | `alicloud_instance`                  |

Each module:

- provisions a single Ubuntu host with no inbound network access and HTTPS-only egress,
- boots it with an inlined cloud-init template that pulls the published
  `ghcr.io/gerardrecinto/macos-fleet-matrix` image and runs `inventory sample`
  as a one-shot systemd unit — the same smoke test CI runs on every push,
- takes network/project identifiers (VPC, subnet, resource group, and
  similar) as required variables rather than assuming a specific account
  layout,
- declares no `provider` block of its own. Reusable modules shouldn't hard-code
  provider configuration; the caller supplies it. Here that caller is
  Terragrunt's `generate "provider"` block in each `live/<provider>/terragrunt.hcl`.
- inlines its own copy of the cloud-init template (`locals.cloud_init` in
  `compute.tf`) instead of reading a shared file. Terragrunt copies only the
  module directory itself into its working cache — a shared file one level up
  would not exist there — and a module that doesn't reach outside its own
  directory is also the more portable, registry-publishable shape anyway.

## Terragrunt

[Terragrunt](https://terragrunt.gruntwork.io/) is a thin orchestration layer
over Terraform that keeps `live/` DRY: `root.hcl` defines the local-backend
pattern and any values shared across providers once, and each
`live/<provider>/terragrunt.hcl` inherits it via `include`, points at its
module with `terraform { source = ... }`, and supplies only what's specific
to that provider.

```bash
cd terraform/control-plane/live/aws
terragrunt validate   # or: plan / apply, once you replace the REPLACE_ME inputs

# from terraform/control-plane, run the same command across every provider:
terragrunt run --all validate
```

Backend: `root.hcl` uses a **local** backend on purpose. This is a reference
repository with no provisioned cloud account or state bucket behind it — see
"public repository, private credentials" in the root README. Each
`live/<provider>` stack gets its own local state file, keyed by its path, so
running all five never collides. Pointing `remote_state.backend` at
`s3`/`gcs`/`azurerm`/etc. for a real deployment is a change to `root.hcl`
alone; nothing in `modules/` or `live/` needs to change.

CI validates both layers on every push (`.github/workflows/ci.yml`):

- `terraform` (matrix over the five providers) runs `terraform validate` and
  `terraform fmt -check` directly against each module in `modules/`, the way
  you'd validate a module meant to be reused or published on its own.
- `terragrunt` (matrix over the five providers) runs `terragrunt validate`
  against each `live/<provider>` stack — the same command a real Terragrunt
  workflow would run, against the same local backend, with the same
  `REPLACE_ME` placeholder inputs committed here.

None of the five stacks have been applied against a live cloud account from
this repository — there are no real credentials, no remote state bucket, and
no CI job that runs `apply` or `terragrunt run --all apply`, on purpose.

## What this does not cover

The macOS/Xcode image pipeline (`packer/`, `terraform/variables.tf`) and the
Tart runner fleet itself are a different tier and require real Apple Silicon
hardware — either on-prem Mac hardware or AWS EC2 Mac instances (the only
major-cloud offering with Apple's licensing to run macOS in a public cloud).
No Terraform in this directory creates a macOS host on any provider; that
would misrepresent what Terraform, or these clouds, can actually do.
