# Operations

## Stale lease

1. Stop scheduling the runner immediately.
2. Record the lease ID and last heartbeat.
3. Attempt graceful guest shutdown only if the workload identity is still responsive.
4. Otherwise destroy the Tart VM and mark the runner `quarantined`.
5. Recreate from the current promoted image.
6. Compare the new runner's health and job outcome with the canary baseline.

## Bad image

Never repair a promoted image in place. Mark the image failed, stop new leases against it, and roll the fleet back to the previous green image. Preserve the failed image manifest and lifecycle telemetry for investigation.

## Host failure

Drain all guests on the host, remove the host from scheduling, and replenish capacity elsewhere. Host recovery must not require a workload credential.

## Incident evidence

Capture image digest, runner ID, job ID, lease timestamps, host ID, guest health, exit status, and lifecycle events. Do not capture secrets or full build logs in the fleet control plane.
