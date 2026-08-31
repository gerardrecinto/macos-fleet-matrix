# Architecture Animation

The hero animation is intentionally a repository-local SVG rather than a remote image. It shows the lifecycle that matters operationally: queue, lease, boot, build, teardown, and recovery.

The visual is not decorative. Each state maps to a control-plane transition and each transition is backed by the repository's lifecycle model, operational runbook, and observability contract.

## State mapping

| Visual state | Control-plane responsibility | Failure action |
| --- | --- | --- |
| Queue | Select compatible image and available capacity | Backoff and capacity signal |
| Lease | Bind one runner to one job with TTL | Expire lease and quarantine |
| Boot | Verify guest health and runner registration | Destroy and replace |
| Build | Execute workload with short-lived identity | Capture outcome, never reuse state |
| Teardown | Stop guest and destroy disposable VM | Force cleanup after timeout |
| Recover | Replenish from known-good image | Roll back image if canary fails |

The animation respects `prefers-reduced-motion` so documentation remains accessible to users who disable motion.
