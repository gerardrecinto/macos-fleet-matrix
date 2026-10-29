"""Feed the live fleet state to the Rust lease reaper and write its result back."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

from .inventory import Inventory


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
    prefix = "mfm-reaper: quarantined "
    return [
        line[len(prefix):].split(" ", 1)[0]
        for line in proc.stderr.splitlines()
        if line.startswith(prefix)
    ]


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
