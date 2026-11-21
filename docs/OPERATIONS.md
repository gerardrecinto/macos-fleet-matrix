# Operations

## Before a pilot on a new host

Run `mfm doctor` with the same `MFM_STATE` the CI jobs will use. A `FAIL` (old Python, a state file that cannot be read or written) must be fixed first. A `WARN` only blocks the feature it names: no Tart means no `--backend tart`, no reaper binary means expired leases are not quarantined, no Swift means no `--health`. Doctor only reads: it never creates the state file, boots a VM or runs the reaper. To undo anything it points you to, delete the state file, and nothing else changes.

## Stale lease

1. Stop scheduling the runner immediately.
2. Record the lease ID and last heartbeat.
3. Attempt graceful guest shutdown only if the workload identity is still responsive.
4. Otherwise destroy the Tart VM and mark the runner `quarantined`. With `--backend tart`, `mfm reap` does this for expired leases and retries it on later sweeps if the delete failed; a quarantined runner that still shows a `vm_name` in `mfm inventory list` has a VM that was not removed. See `docs/TART.md`.
5. Recreate from the current promoted image.
6. Compare the new runner's health and job outcome with the canary baseline.

## Bad image

Never repair a promoted image in place. Mark the image failed, stop new leases against it, and roll the fleet back to the previous green image. Preserve the failed image manifest and lifecycle telemetry for investigation.

## Host failure

Drain all guests on the host, remove the host from scheduling, and replenish capacity elsewhere. Host recovery must not require a workload credential.

## Incident evidence

Capture image digest, runner ID, job ID, lease timestamps, host ID, guest health, exit status, and lifecycle events. Do not capture secrets or full build logs in the fleet control plane.
