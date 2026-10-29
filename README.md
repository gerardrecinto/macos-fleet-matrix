# macOS Fleet Matrix

Give every macOS CI job a fresh, disposable Apple Silicon VM, then throw it away. This repository is a reference design and a working simulation of the control plane for that: a lease model, a thermal and memory probe that keeps jobs off sick hosts, and a fail-closed lease reaper. It is built around Tart, Packer, Ansible, GitHub Actions, Buildkite, Spinnaker, Prometheus, OpenTelemetry, and Grafana. No real VM boots from this code yet; see the status table.

<p align="center">
  <img src="docs/assets/fleet-lifecycle.svg" alt="Animated runner lifecycle in six stages: queue, lease, boot, build, teardown, recover" width="100%">
</p>

<p align="center"><strong>QUEUE → LEASE → BOOT → BUILD → TEARDOWN → RECOVER</strong></p>

## Status

| Status | What |
| --- | --- |
| Implemented | Python lease CLI with state saved between commands (`mfm inventory`, `lease acquire`, `lease release`, `metrics`, `reap`); Swift thermal and memory probe; Rust lease reaper; container image for the Linux control plane; Terraform and Terragrunt validated in CI; Kubernetes, ArgoCD and Kyverno manifests validated in CI |
| Designed only | VM boot through Tart or Virtualization.framework; Packer image builder and APFS cloning; Xcode and Simulator switching; Spinnaker image promotion; Ansible host role; applied Terraform in any cloud; live ArgoCD sync; running telemetry collection on hosts |
| Not started | Real Tart adapter; launchd or systemd unit for the reaper; OpenTelemetry export; remote Terraform state |

The lead differentiator is the host probe: it reads thermal state and memory and swap pressure straight from the kernel, and `mfm lease acquire --health` refuses hot or swapping hosts. The write-up is in [`docs/BLOG-THERMAL-MEMORY-PROBING.md`](docs/BLOG-THERMAL-MEMORY-PROBING.md).

Details live in the places that own them:

- Control-plane CLI: [Quick start](#quick-start) and `src/mfm/`
- Telemetry probe: [Host telemetry probe](#host-telemetry-probe-swift)
- Lease reaper: [Lease reaper](#lease-reaper-rust)
- Cloud control-plane infrastructure: [`terraform/control-plane/README.md`](terraform/control-plane/README.md)
- Continuous deployment: [`deploy/argocd/README.md`](deploy/argocd/README.md)
- Kubernetes workloads, Kyverno, Cosign, Trivy: `terraform/kubernetes/`, `deploy/k8s/`, `deploy/spinnaker/`, `.harness/`. None of it has been applied to a live cluster. The Kyverno signature policy is in `Audit` mode because images published before the Cosign step have no signature.
- Tested versions: [`docs/SUPPORT-MATRIX.md`](docs/SUPPORT-MATRIX.md)
- Reporting a vulnerability: [`SECURITY.md`](SECURITY.md); contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md)

## Why this exists

macOS CI capacity is expensive and stateful by default. This project treats each runner as disposable infrastructure:

1. Build an immutable macOS/Xcode image.
2. Register capacity in a small inventory plane.
3. Lease a runner for exactly one job.
4. Execute the workload with a constrained identity.
5. Collect telemetry and lifecycle events.
6. Destroy or quarantine the VM after the job.
7. Replenish capacity from the known-good image.

The repository is intentionally useful on a laptop in simulation mode while preserving clear seams for a real Apple Silicon fleet.

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

## Repository layout

- `src/mfm/` small Python control-plane library and CLI
- `src/mfm/Telemetry/` Swift host telemetry probe (thermal state, memory/swap)
- `src/mfm/Reaper/` Rust lease reaper (fail-closed lease TTL enforcement)
- `tests/mfmTests/` XCTest suite for the telemetry probe (alongside the existing pytest suite — macOS's default case-insensitive filesystem treats `Tests/` and `tests/` as the same directory, so both live under the lowercase name)
- `Package.swift` Swift package manifest for the telemetry module
- `packer/` image-build contract and validation scripts
- `ansible/` host bootstrap and hardening role
- `deploy/SPINNAKER.md` promotion contract for the macOS/Xcode image pipeline (a different tier — see `terraform/variables.tf` and `packer/`)
- `terraform/control-plane/modules/` reusable per-provider Terraform modules for the Linux control-plane host (AWS, GCP, Azure, OpenStack, AliCloud)
- `terraform/control-plane/live/` Terragrunt stacks that call those modules, one per provider
- `deploy/k8s/control-plane/` Kustomize manifests for the control-plane CronJob
- `deploy/argocd/` ArgoCD `Application` manifest for continuous deployment of those manifests
- `terraform/kubernetes/` Terraform modules and Terragrunt stacks for ACK and Azure Red Hat OpenShift clusters
- `deploy/k8s/policies/` Kyverno cluster policies; `deploy/k8s/overlays/openshift/` OpenShift SCC-friendly overlay
- `deploy/spinnaker/` and `.harness/pipelines/` multi-cluster deploy pipelines
- `observability/` Prometheus and Grafana configuration
- `.github/workflows/` lint, test, policy, and GHCR release workflows
- `Dockerfile` multi-stage Linux container for the control plane
- `docs/` operational runbooks, threat model, and visual architecture mapping
- `docs/assets/` self-contained documentation graphics

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
mfm inventory sample
mfm lease acquire --runner m1-01 --job demo-123
mfm lease release --runner m1-01 --job demo-123 --result success
mfm metrics
```

State lives in `--state FILE`, then `$MFM_STATE`, then `$XDG_STATE_HOME/mfm/state.json`, so the two commands above see the same fleet. `mfm inventory list` prints every runner in every state; `mfm inventory sample` prints a fresh sample fleet and touches no state. `lease acquire` and `lease release` take `--json` for machine-readable output, and `--version` prints the version.

`mfm metrics` prints runners by state and seconds until each lease expires (negative once overdue) in Prometheus text format. It does not serve HTTP; write it to node-exporter's textfile collector directory on a timer, as described in `observability/prometheus.yml`.

Let the scheduler pick the runner from host telemetry instead of naming one:

```bash
mfm lease acquire --job demo-124 --image macos-15-xcode-16 --health health.json
```

`health.json` maps runner id to the probe's `HostHealthState` JSON. Hosts at `serious` or `critical` thermal state, or with more than half their swap in use, are skipped. The rest are ranked coolest and least-swapped first, and a runner with no entry ranks last. If every ready runner is refused, the command exits 2 and leases nothing.
```

Simulation is the default. Real Tart execution is an explicit adapter boundary and should only be enabled on an Apple Silicon host with the required tooling and entitlements.

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

This is a standalone probe today. The Python CLI reads its JSON to gate lease acquisition (`mfm lease acquire --health`), but nothing collects it from live hosts on a schedule, and it is not exported as Prometheus metrics — see [Roadmap](#roadmap).

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

Not yet implemented — listed here so the architecture diagram above isn't mistaken for shipped functionality:

- **Virtualization.framework VM lifecycle** — no code boots, leases, or tears down a real VM. `mfm lease acquire` records state in a local JSON file only.
- **APFS copy-on-write image cloning** — the "immutable pool" step in the image pipeline is a documented contract in `packer/`, not exercised by any script.
- **Xcode/Simulator toolchain matrix switching** — no code touches `xcode-select` or CoreSimulator runtime state.
- **Live telemetry collection** — `mfm lease acquire --health` gates on a health file you supply; nothing yet runs the Swift probe on each host and gathers the results.
- **Prometheus/OpenTelemetry export**: `mfm metrics` prints fleet gauges in Prometheus text, but nothing serves or schedules it, the host probe is not exported, and there is no OpenTelemetry.
- **Tart, Spinnaker (image promotion), and Ansible integration** — documented in `deploy/SPINNAKER.md` and `ansible/`, not yet driven by CI. This is separate from the ArgoCD/Kubernetes manifests below, which are validated in CI.
- **Deployed reaping** — `mfm reap` runs the reaper on a timer against a local state file, but no launchd unit, systemd timer or CronJob runs it on a real control-plane host, and the state file is single-host.
- **Live multi-cloud deployment** — the Terraform in `terraform/control-plane/` is validated in CI but has never been applied against a real AWS, GCP, Azure, OpenStack, or AliCloud account; there is no remote state backend or CI job authorized to run `terraform apply` or `terragrunt run --all apply`.
- **Live ArgoCD sync** — `deploy/argocd/application.yaml` is a real, validated manifest, but it has never been applied to a cluster from this repository; there is no cluster endpoint or credential here to sync against.

## License

MIT. See `LICENSE`.
