"""Feed the live fleet state to the Rust lease reaper and write its result back."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

from .inventory import Inventory
from .model import RunnerState
from .tart import Tart, TartError, find_tart, log_dir_for


def find_reaper(explicit: str | None) -> str:
    candidate = explicit or os.environ.get("MFM_REAPER") or "mfm-reaper"
    found = shutil.which(candidate)
    if not found:
        raise ValueError(
            f"reaper binary not found: {candidate} (build src/mfm/Reaper, then pass --reaper or set MFM_REAPER)"
        )
    return found


def reap_once(state: str, reaper: str) -> list[str]:
    """One sweep: snapshot the state, run the reaper over it, save what it changed.

    Held under the state lock the whole time, so a lease taken while the reaper runs
    waits for the sweep instead of being overwritten by it. Returns quarantined ids.
    """
    with Inventory.transaction(state) as inventory:
        proc = subprocess.run(
            [reaper],
            input=inventory.to_json(),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise ValueError(f"reaper failed ({proc.returncode}): {proc.stderr.strip()}")
        inventory.replace_with(Inventory.from_json(proc.stdout))
        _teardown_vms(inventory, state)
    prefix = "mfm-reaper: quarantined "
    return [
        line[len(prefix):].split(" ", 1)[0]
        for line in proc.stderr.splitlines()
        if line.startswith(prefix)
    ]


def _teardown_vms(inventory: Inventory, state: str) -> None:
    """Destroy the Tart VM behind every quarantined runner that still has one.

    This covers runners the reaper just quarantined and runners whose release-time
    teardown failed earlier, so a stuck VM is retried on every sweep. A runner keeps
    its vm_name until the delete succeeds. Failures are reported, not raised, so one
    bad VM cannot stop the sweep or lose the reaper's result.
    """
    stuck = [r for r in inventory.all() if r.state is RunnerState.QUARANTINED and r.vm_name]
    if not stuck:
        return
    try:
        tart = Tart(find_tart(), log_dir=log_dir_for(state))
    except TartError as exc:
        print(f"mfm: cannot tear down {len(stuck)} VM(s): {exc}", file=sys.stderr, flush=True)
        return
    for runner in stuck:
        try:
            tart.teardown(runner.vm_name)
        except TartError as exc:
            print(f"mfm: runner {runner.runner_id} stays quarantined with VM: {exc}",
                  file=sys.stderr, flush=True)
            continue
        print(f"tore down VM {runner.vm_name} (runner {runner.runner_id})", flush=True)
        runner.vm_name = None
        runner.vm_ip = None


def reap_loop(state: str, reaper: str, interval: float, once: bool) -> None:
    while True:
        for runner_id in reap_once(state, reaper):
            print(f"quarantined {runner_id} (lease expired)", flush=True)
        if once:
            return
        time.sleep(interval)


def main_loop(state: str, reaper_arg: str | None, interval: float, once: bool) -> int:
    try:
        reap_loop(state, find_reaper(reaper_arg), interval, once)
    except KeyboardInterrupt:
        print("stopped", file=sys.stderr)
    return 0
