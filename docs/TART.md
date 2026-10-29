# Tart backend

`mfm lease acquire --backend tart` boots a real, disposable macOS VM for a lease. Simulation is still the default. The backend is `src/mfm/tart.py`.

## Status

Tested against a fake `tart` executable (`tests/fake_tart.py`), which records its arguments and simulates success and failure. It has not been run against real Tart or a real VM by the author. A test that does run against real Tart exists and is skipped unless you opt in (see below).

## Commands it runs

These were checked against the Tart quick start and the Tart source (`Commands/IP.swift`, `Stop.swift`, `List.swift`, `Run.swift`, `Delete.swift`).

| Step | Command |
| --- | --- |
| Collision check | `tart list --source local --quiet` |
| Optional pull (`--pull`) | `tart pull <image>` |
| Clone from the runner's image | `tart clone <image> <vm>` |
| Boot headless, in the background | `tart run <vm> --no-graphics` |
| Wait for an address | `tart ip <vm> --wait <seconds>` |
| Teardown | `tart stop <vm>` then `tart delete <vm>` |

The VM is named `mfm-<runner>-<job>`, and the runner's `image` field is what gets cloned, so it must be a local VM name or an OCI reference Tart can pull. The sample label `macos-15-xcode-16` is only a label until you create a VM or image with that name. Not used because the flags could not be confirmed here: `--timeout` on `tart stop`, `--dir` mounts, and any Tart Guest Agent options.

## Use

```bash
mfm lease acquire --backend tart --runner m1-01 --job build-42 --dry-run   # print the commands, run nothing
mfm lease acquire --backend tart --runner m1-01 --job build-42             # clone, boot, wait for IP
mfm lease release --runner m1-01 --job build-42 --result success           # stop, delete
```

Options on `acquire`: `--pull` runs `tart pull` first, `--boot-timeout N` is the seconds to wait for an IP (default 120). `--dry-run` also works on `release` and prints `tart stop` and `tart delete` for the VM recorded in the state. A dry run does not need Tart installed and never changes state.

The VM name and IP are saved in the runner's `vm_name` and `vm_ip` fields in the state file. `tart run` output goes to `tart-logs/<vm>.log` next to the state file and is deleted with the VM.

## Failure handling

- Tart not installed: one message, `mfm: tart not found on PATH. Install it with: brew install cirruslabs/cli/tart`, exit code 2, no state change. `MFM_TART` can point at a binary that is not on `PATH`.
- Name collision: if a VM with that name already exists, nothing is touched and the command exits 2.
- Timeouts: every Tart call has a timeout. A timeout is reported as an error and handled like any other failure.
- Half-started VM: if clone, boot or the IP wait fails, the VM is stopped and deleted, the lease is undone and the runner goes back to `ready`.
- Cleanup also fails: the runner is quarantined and keeps its `vm_name`, so the VM is not forgotten.
- Release: after `stop` and `delete` succeed the runner is `draining` as before. If teardown fails the runner is quarantined, keeps `vm_name`, and the command exits 2.
- Reaper: `mfm reap` quarantines expired leases as before, then tears down the VM of every quarantined runner that still has a `vm_name`. A failed teardown is reported and retried on the next sweep. The Rust reaper carries the VM fields through unchanged.
- `tart stop` failing is tolerated only if `tart delete` then succeeds, because a VM that already exited cannot be stopped.

The state lock is held while a VM boots, so other `mfm` commands on the same state file wait for it.

## Apple license limit

Apple's macOS license limits how many macOS VMs can run at once on Apple-branded hardware. This backend does not check or enforce that limit. Check Apple's software license agreement before sizing a fleet.

## Test on a real VM

```bash
brew install cirruslabs/cli/tart
tart pull ghcr.io/cirruslabs/macos-tahoe-base:latest      # many GB
MFM_TART_E2E=1 pytest tests/test_tart_e2e.py -v
```

The test clones the image, boots it headless, waits for an IP, releases the lease, and checks the VM is gone from `tart list`. Set `MFM_TART_E2E_IMAGE` to use a different image. It needs an Apple Silicon Mac.
