# macOS Fleet Matrix

New here? This is a pretend fleet of Mac build machines. It hands each build job its own clean machine, then takes it away when the job ends.

A lease-per-job control plane for disposable Apple Silicon macOS CI runners, with a simulated default, an opt-in Tart VM backend, a host health probe, a lease reaper, and Spinnaker pipeline definitions.

<p align="center">
  <img src="docs/assets/fleet-lifecycle.svg" alt="Animated runner lifecycle in six stages: queue, lease, boot, build, teardown, recover" width="100%">
</p>

<p align="center"><strong>QUEUE → LEASE → BOOT → BUILD → TEARDOWN → RECOVER</strong></p>

## Quick start (about 60 seconds)

Requires Python 3.11+. Nothing here needs Tart, Spinnaker or a Mac.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest
mfm lease acquire --runner m1-01 --job demo-123
mfm lease release --runner m1-01 --job demo-123 --result success
mfm lease acquire --backend tart --runner m1-02 --job demo-124 --dry-run
mfm pipeline validate deploy/spinnaker/*.json
```

The first lease only changes a record in a local state file. The `--dry-run` line prints the exact `tart` commands and runs nothing. The last line checks the Spinnaker pipeline JSON.

## What it does and does not do

Does:

- Lease one runner to one job with a TTL, and save fleet state between commands (`mfm inventory`, `lease acquire`, `lease release`, `metrics`, `reap`).
- With `--backend tart`: clone a VM from the runner image, boot it headless, wait for its IP, record the VM name and IP, and stop and delete it on release or when the reaper expires the lease. If teardown fails the runner is quarantined. See [`docs/TART.md`](docs/TART.md).
- Skip hot or swapping hosts when picking a runner (`--health`), using JSON from the Swift probe.
- Quarantine expired leases with a Rust reaper, then tear down their VMs.
- Ship three Spinnaker pipelines (control-plane deploy, image promotion, rollback) and a validator for them. See [`deploy/SPINNAKER.md`](deploy/SPINNAKER.md).

Does not:

- Run against a real VM in CI or in the author's testing. The Tart backend is tested against a fake `tart` executable. A gated test for real Tart exists and has not been run by the author.
- Apply the Spinnaker pipelines anywhere. They are validated structurally (CI) and have never been saved to or run on a live Spinnaker.
- Build images. There is no Packer template, so the immutable Xcode image is a contract in `packer/IMAGE-PIPELINE.md`, not working code.
- Enforce Apple's limit on concurrent macOS VMs per host. Check Apple's software license agreement.
- Collect telemetry from hosts, export OpenTelemetry, or run the reaper as a service.

## Status

| Status | What |
| --- | --- |
| Implemented and tested | Python lease CLI with state saved between commands; Swift thermal and memory probe; Rust lease reaper; container image for the Linux control plane; Terraform, Terragrunt, Kubernetes, ArgoCD and Kyverno files validated in CI |
| Implemented, tested against a fake only | Tart backend (`--backend tart`, `--dry-run`, teardown, failure cleanup, reaper teardown): tested with a fake `tart` script, not real Tart or a VM. A gated real-Tart test is in `tests/test_tart_e2e.py` |
| Implemented, validated structurally only | Spinnaker pipelines in `deploy/spinnaker/` and `mfm pipeline validate`, run in CI. Never saved to or run on a live Spinnaker |
| Designed only | Packer image builder and APFS cloning; Xcode and Simulator switching; Ansible host role; applied Terraform in any cloud; live ArgoCD sync; running telemetry collection on hosts |
| Not started | launchd or systemd unit for the reaper; OpenTelemetry export; remote Terraform state |

The Rust change that carries the VM fields through a sweep was not compiled on the machine that wrote it; the `rust` CI job is the check for it.

The host probe reads thermal state and memory and swap pressure straight from the kernel, and `mfm lease acquire --health` refuses hot or swapping hosts. The write-up is in [`docs/BLOG-THERMAL-MEMORY-PROBING.md`](docs/BLOG-THERMAL-MEMORY-PROBING.md).

Details live in the places that own them:

- Tart backend: [`docs/TART.md`](docs/TART.md)
- Spinnaker pipelines and how to apply them: [`deploy/SPINNAKER.md`](deploy/SPINNAKER.md)
- Cloud control-plane infrastructure: [`terraform/control-plane/README.md`](terraform/control-plane/README.md)
- Continuous deployment: [`deploy/argocd/README.md`](deploy/argocd/README.md)
- Kubernetes workloads, Kyverno, Cosign, Trivy: `terraform/kubernetes/`, `deploy/k8s/`, `.harness/`. None of it has been applied to a live cluster. The Kyverno signature policy is in `Audit` mode because images published before the Cosign step have no signature.
- Tested versions: [`docs/SUPPORT-MATRIX.md`](docs/SUPPORT-MATRIX.md)
- Reporting a vulnerability: [`SECURITY.md`](SECURITY.md); contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md)

## State and CLI notes

State lives in `--state FILE`, then `$MFM_STATE`, then `$XDG_STATE_HOME/mfm/state.json`, so consecutive commands see the same fleet. `mfm inventory list` prints every runner in every state; `mfm inventory sample` prints a fresh sample fleet and touches no state. `lease acquire` and `lease release` take `--json`, and `--version` prints the version.

`mfm metrics` prints runners by state and seconds until each lease expires (negative once overdue) in Prometheus text format. It does not serve HTTP; write it to node-exporter's textfile collector directory on a timer, as described in `observability/prometheus.yml`.

Let the scheduler pick the runner from host telemetry instead of naming one:

```bash
mfm lease acquire --job demo-124 --image macos-15-xcode-16 --health health.json
```

`health.json` maps runner id to the probe's `HostHealthState` JSON. Hosts at `serious` or `critical` thermal state, or with more than half their swap in use, are skipped. The rest are ranked coolest and least-swapped first, and a runner with no entry ranks last. If every ready runner is refused, the command exits 2 and leases nothing.

## Why this exists

macOS CI capacity is expensive and stateful by default. This project treats each runner as disposable infrastructure:

1. Build an immutable macOS/Xcode image (design only, see above).
2. Register capacity in a small inventory plane.
3. Lease a runner for exactly one job.
4. Execute the workload with a constrained identity.
5. Collect telemetry and lifecycle events.
6. Destroy or quarantine the VM after the job.
7. Replenish capacity from the known-good image.

## Architecture

```text
GitHub Actions / Buildkite
          |
          v
     Fleet API / CLI -----> Inventory + leases
          |                         |
          v                         v
      Tart runner <----------- health controller
          |
          +---- OpenTelemetry ----> Prometheus/Grafana
          |
          +---- lifecycle events -> audit log

Image pipeline:
Packer -> macOS/Xcode image -> signed artifact -> Tart import -> immutable pool

Promotion:
image -> Spinnaker canary -> bake/health gate -> blue/green fleet

Host configuration:
Ansible -> launchd / Tart prerequisites / observability agent
```

Boxes that exist as code: the CLI and inventory, the Tart runner step (fake-tested), the health gate, the reaper, and the Spinnaker pipeline files (not applied). Packer, OpenTelemetry and the Ansible role are design only.

## Repository layout

- `src/mfm/` Python control-plane library and CLI (`tart.py` is the Tart adapter, `pipeline.py` the Spinnaker validator)
- `src/mfm/Telemetry/` Swift host telemetry probe (thermal state, memory/swap)
- `src/mfm/Reaper/` Rust lease reaper (fail-closed lease TTL enforcement)
- `tests/mfmTests/` XCTest suite for the telemetry probe (alongside the pytest suite; macOS's default case-insensitive filesystem treats `Tests/` and `tests/` as the same directory, so both live under the lowercase name)
- `Package.swift` Swift package manifest for the telemetry module
- `packer/` image-build contract (no template yet)
- `ansible/` host bootstrap and hardening role
- `deploy/SPINNAKER.md` and `deploy/spinnaker/` promotion contract and the three pipeline JSON files
- `terraform/control-plane/modules/` reusable per-provider Terraform modules for the Linux control-plane host (AWS, GCP, Azure, OpenStack, AliCloud)
- `terraform/control-plane/live/` Terragrunt stacks that call those modules, one per provider
- `deploy/k8s/control-plane/` Kustomize manifests for the control-plane CronJob
- `deploy/argocd/` ArgoCD `Application` manifest for continuous deployment of those manifests
- `terraform/kubernetes/` Terraform modules and Terragrunt stacks for ACK and Azure Red Hat OpenShift clusters
- `deploy/k8s/policies/` Kyverno cluster policies; `deploy/k8s/overlays/openshift/` OpenShift SCC-friendly overlay
- `.harness/pipelines/` Harness deploy pipeline
- `observability/` Prometheus and Grafana configuration
- `.github/workflows/` lint, test, policy, and GHCR release workflows
- `Dockerfile` multi-stage Linux container for the control plane
- `docs/` operational runbooks, threat model, Tart backend notes, and visual architecture mapping
- `docs/assets/` self-contained documentation graphics

## Lease reaper (Rust)

Requires Rust 1.75+ (stable channel).

```bash
cd src/mfm/Reaper
cargo test
mfm inventory list | cargo run --quiet
```

To run it against the live fleet state instead of a pasted snapshot, build it and let the CLI drive it:

```bash
cargo build --release --manifest-path src/mfm/Reaper/Cargo.toml
mfm reap --reaper src/mfm/Reaper/target/release/mfm-reaper --interval 30
```

`mfm reap` sweeps the saved state every `--interval` seconds (or once with `--once`): it takes the state lock, pipes the fleet to `mfm-reaper`, and writes the result back, so a lease taken during a sweep waits for it instead of being overwritten. If the binary is missing or exits non-zero, the state is left untouched and the command exits 2. Binary lookup is `--reaper`, then `$MFM_REAPER`, then `PATH`. The container image does not ship the Rust binary.

`mfm-reaper` reads a fleet inventory snapshot as JSON — the same shape `mfm inventory list` prints — and applies one rule: a runner in the `leased` state whose `lease_expires_at` is at or before the current time is quarantined, its job and lease fields cleared. Every other state passes through unchanged. This is the "fail closed" design principle from below expressed as a small, independently testable unit, in a second language on purpose: the Python model owns the state machine, the Rust binary only enforces one invariant against a snapshot of it. `mfm reap` feeds it the live state file on a timer. CI builds the binary and runs that path end to end.

## Host telemetry probe (Swift)

Requires macOS 13+ on Apple Silicon and Swift 5.9+.

```bash
swift build
swift test
```

`HostTelemetryProbe.sample()` returns a `HostHealthState`: thermal state from `ProcessInfo.thermalState`, and memory/swap pressure read via `host_statistics64(HOST_VM_INFO64)` and `sysctlbyname("vm.swapusage")` — the same kernel counters `vm_stat` and Activity Monitor read, without forking a process and parsing its text output. The struct is `Codable`; `HostHealthState.jsonData()` gives a stable, ISO 8601-timestamped JSON snapshot.

This is a standalone probe today. The Python CLI reads its JSON to gate lease acquisition (`mfm lease acquire --health`), but nothing collects it from live hosts on a schedule, and it is not exported as Prometheus metrics. See the [roadmap](#roadmap).

## Container image

The Docker image packages the **Linux control plane only**. It does not virtualize macOS and does not replace the Apple Silicon Tart host layer.

```bash
docker build --pull --tag mfm:dev .
docker run --rm mfm:dev inventory sample
```

The image uses a multi-stage build, an explicit Python package build backend, a minimal Debian runtime, a non-root UID, bytecode compilation, OCI metadata, and a `.dockerignore`. CI builds and smoke-tests the image on every push and pull request.

Release images are published to GHCR from the GitHub release workflow with version tags and provenance attestations. GitHub's Container Registry supports provenance attestations and recommends associating the package with the repository through the `org.opencontainers.image.source` label.

## Architecture animation

The hero SVG is part of the repository and is tested in CI. It maps the visual states directly to control-plane lifecycle states rather than presenting an unrelated decorative diagram. It also includes a reduced-motion mode for accessibility.

See [`docs/ARCHITECTURE-ANIMATION.md`](docs/ARCHITECTURE-ANIMATION.md) for the state-by-state mapping.

## Design principles

### Ephemeral by default
A runner is leased to one job and then destroyed. Reuse is an exceptional, quarantined path rather than the normal lifecycle.

### Public repository, private credentials
This repository contains no cloud credentials, runner registration tokens, signing keys, or production endpoints. Workload credentials should be short-lived and injected by the CI platform.

### Fail closed
A runner that misses a heartbeat, reports an unhealthy guest, or exceeds its lease is removed from scheduling before recovery begins.

### Canary before capacity
New images enter a canary pool first. Only a healthy canary cohort can replace the current green fleet.

### Claims are measured, not assumed
Performance, cost, reliability, and recovery targets in this project are explicit hypotheses until backed by fleet telemetry.

## Security model

Public pull requests are untrusted workloads. The runner broker must not give a pull-request job host credentials, signing keys, persistent developer credentials, or unrestricted access to the management network. Prefer GitHub OIDC or Buildkite-issued short-lived identity for cloud access. Separate build identities from fleet-management identities.

The real deployment should also enforce network egress policy, artifact allowlists, image provenance verification, macOS privacy permissions, audit logging, and secret rotation outside this repository.

The container release workflow grants only `contents: read`, `packages: write`, `attestations: write`, and `id-token: write`, and uses immutable action references. GitHub documents `GITHUB_TOKEN` authentication for GHCR and recommends artifact attestations for container provenance.

## Operational targets

These are targets for validation, not historical claims:

| Metric | Target | Measurement |
| --- | --- | --- |
| Runner acquisition | < 30 s at warm capacity | lease latency histogram |
| Job cleanup | < 60 s | destroy lifecycle timer |
| Image promotion | gated by canary health | promotion events |
| Stale runner rate | < 0.1% | unhealthy leases / total leases |
| Fleet recovery | automated | time-to-replenish |

## Roadmap

Not yet done, listed so the architecture diagram above isn't mistaken for shipped functionality:

- **Real VM verification**: the Tart backend boots and destroys VMs through the `tart` CLI, but it has only been exercised against a fake `tart` script. Nobody has run it against real Tart yet; `tests/test_tart_e2e.py` is the opt-in test for that. Direct Virtualization.framework use is not implemented.
- **APFS copy-on-write image cloning** — the "immutable pool" step in the image pipeline is a documented contract in `packer/`, not exercised by any script.
- **Xcode/Simulator toolchain matrix switching** — no code touches `xcode-select` or CoreSimulator runtime state.
- **Live telemetry collection** — `mfm lease acquire --health` gates on a health file you supply; nothing yet runs the Swift probe on each host and gathers the results.
- **Prometheus/OpenTelemetry export**: `mfm metrics` prints fleet gauges in Prometheus text, but nothing serves or schedules it, the host probe is not exported, and there is no OpenTelemetry.
- **Packer image builds**: `packer/IMAGE-PIPELINE.md` is a contract. There is no Packer template, and one cannot be checked without installing Packer.
- **Spinnaker on a live server**: the three pipelines in `deploy/spinnaker/` pass `mfm pipeline validate` in CI but have never been saved to a Spinnaker. The image-promotion pipelines call a promotion API that this repository does not provide. Ansible is documented in `ansible/` and not driven by CI.
- **Deployed reaping** — `mfm reap` runs the reaper on a timer against a local state file, but no launchd unit, systemd timer or CronJob runs it on a real control-plane host, and the state file is single-host.
- **Live multi-cloud deployment** — the Terraform in `terraform/control-plane/` is validated in CI but has never been applied against a real AWS, GCP, Azure, OpenStack, or AliCloud account; there is no remote state backend or CI job authorized to run `terraform apply` or `terragrunt run --all apply`.
- **Live ArgoCD sync** — `deploy/argocd/application.yaml` is a real, validated manifest, but it has never been applied to a cluster from this repository; there is no cluster endpoint or credential here to sync against.

## License

MIT. See `LICENSE`.
