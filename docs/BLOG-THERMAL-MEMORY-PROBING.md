# Preventing CI Queue Starvation: Native Thermal & Memory Probing on Apple Silicon

*Draft — technical deep-dive, not yet published.*

## Introduction

Every macOS CI fleet I've operated has hit the same failure mode eventually: a worker keeps accepting jobs while its SoC is already thermally throttled, and the build queue looks starved even though the scheduler thinks every machine is healthy. Nothing crashes. Nothing pages anyone. The job just gets slower — six minutes becomes eleven, then twenty-two — until someone opens a ticket blaming Xcode, or the linker, or "flaky CI," and three engineers spend an afternoon bisecting a problem that was never in the code.

The instinct is to reach for `top`, `vm_stat`, or `powermetrics` in a cron loop and call it monitoring. That works, right up until it doesn't: you're forking a process per sample, parsing whatever text format that binary happens to emit this OS version, and hoping the column order didn't change. `powermetrics` also wants root, which is its own fight to get onto a CI worker's launchd job without widening the worker's privilege footprint.

The fix that actually holds up is unglamorous: read the same kernel counters those tools read, directly, through the APIs Apple ships for exactly this. No fork, no text parsing, no privilege escalation. This post is about building that probe for a macOS Apple Silicon build fleet, and about a wrong assumption I had to walk back on the way — the sysctl I expected to use for thermal state doesn't exist on Apple Silicon at all.

## Outline

1. **The failure mode: queue starvation that looks like a scheduler bug**
   What thermal throttling actually does to build wall-clock time, why it's silent, and why "the queue is starved" and "a worker is cooked" produce identical symptoms from the scheduler's point of view.

2. **Why shelling out to `top` or `powermetrics` doesn't scale**
   Fork/exec cost per sample, brittle text parsing across OS versions, and the root requirement `powermetrics` imposes on a CI worker's launchd identity.

3. **The wrong turn: `machdep.xcpm.cpu_thermal_level` doesn't exist on Apple Silicon**
   XCPM (X86 Core Performance Management) is an Intel-only kernel subsystem. That sysctl was a reasonable guess coming from x86 CI experience, and it fails silently with `ENOENT` on every M-series Mac. The right signal is `ProcessInfo.thermalState`, the same public API powerd exposes across both architectures.

4. **What actually works: three calls, no shell-outs**
   `ProcessInfo.thermalState` for throttling, `host_statistics64(HOST_VM_INFO64)` for free/active/inactive/wired/compressed memory, and `sysctlbyname("vm.swapusage")` for swap accounting — the exact counters `vm_stat` and Activity Monitor read, minus the subprocess.

5. **Turning a probe into a scheduling signal**
   What's built today is a probe, not a scheduler integration: it returns a `Codable` snapshot on demand. Gating lease acquisition on thermal/memory state, and exporting the same data as Prometheus metrics, is the next step — not yet shipped.

6. **What this doesn't fix**
   A probe tells you a worker is unhealthy after the fact. It doesn't predict thermal throttling before you assign the job, and it says nothing about noisy-neighbor contention between concurrent VMs on the same SoC. Being explicit about that boundary matters more than the probe itself.
