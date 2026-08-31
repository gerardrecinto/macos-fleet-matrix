# macOS Fleet Matrix

A production-oriented reference architecture for ephemeral Apple Silicon macOS CI runners using Tart, Packer, Ansible, GitHub Actions, Buildkite, Spinnaker, Prometheus, OpenTelemetry, and Grafana.

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
- `packer/` image-build contract and validation scripts
- `ansible/` host bootstrap and hardening role
- `deploy/` Kubernetes/Spinnaker examples for the control plane
- `observability/` Prometheus and Grafana configuration
- `.github/workflows/` lint, test, and policy checks
- `docs/` operational runbooks and threat model

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
```

Simulation is the default. Real Tart execution is an explicit adapter boundary and should only be enabled on an Apple Silicon host with the required tooling and entitlements.

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

## Operational targets

These are targets for validation, not historical claims:

| Metric | Target | Measurement |
| --- | --- | --- |
| Runner acquisition | < 30 s at warm capacity | lease latency histogram |
| Job cleanup | < 60 s | destroy lifecycle timer |
| Image promotion | gated by canary health | promotion events |
| Stale runner rate | < 0.1% | unhealthy leases / total leases |
| Fleet recovery | automated | time-to-replenish |

## License

MIT. See `LICENSE`.
