"""Check a host before pointing CI at it: what works, what is missing, and the fix."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass

from .inventory import Inventory, StateFileError
from .reap import find_reaper
from .tart import TartMissing, find_tart

PASS, WARN, FAIL = "pass", "warn", "fail"


@dataclass
class Check:
    name: str
    status: str
    detail: str
    fix: str = ""


def _python() -> Check:
    v = sys.version_info
    if (v.major, v.minor) >= (3, 11):
        return Check("python", PASS, f"{v.major}.{v.minor}.{v.micro}")
    return Check("python", FAIL, f"{v.major}.{v.minor}.{v.micro}", "Install Python 3.11 or later and recreate the virtualenv.")


def _writable_ancestor(path: str) -> str:
    d = os.path.dirname(os.path.abspath(path))
    while d and not os.path.exists(d):
        d = os.path.dirname(d)
    return d


def _state(path: str) -> Check:
    ancestor = _writable_ancestor(path)
    if not ancestor or not os.access(ancestor, os.W_OK):
        return Check("state file", FAIL, path, f"{ancestor or path} is not writable. Set MFM_STATE to a path you can write.")
    if not os.path.exists(path):
        return Check("state file", PASS, f"{path} (not created yet; the first lease seeds the sample fleet)")
    try:
        runners = Inventory.load(path).all()
    except StateFileError as exc:
        return Check("state file", FAIL, path, str(exc))
    counts = Counter(r.state.value for r in runners)
    summary = ", ".join(f"{n} {s}" for s, n in sorted(counts.items())) or "no runners"
    if not counts.get("ready"):
        return Check("state file", WARN, f"{path}: {summary}", "No runner is ready, so the next lease will be refused. Wait for draining runners to be reaped or add runners.")
    return Check("state file", PASS, f"{path}: {summary}")


def _apple_silicon() -> bool:
    if platform.system() != "Darwin":
        return False
    # Python built for Intel and run under Rosetta reports x86_64 on an M-series Mac, so ask the kernel.
    try:
        out = subprocess.run(["sysctl", "-n", "hw.optional.arm64"], capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            return out.stdout.strip() == "1"
    except (OSError, subprocess.SubprocessError):
        pass
    return platform.machine() == "arm64"


def _host() -> Check:
    if _apple_silicon():
        return Check("host", PASS, "Apple Silicon macOS")
    return Check("host", WARN, f"{platform.system()} {platform.machine()}", "This host cannot boot macOS VMs with Tart. The lease simulation still works.")


def _tart() -> Check:
    try:
        return Check("tart", PASS, find_tart())
    except TartMissing:
        return Check("tart", WARN, "not found", "Needed only for `--backend tart`. Install it with `brew install cirruslabs/cli/tart` or set MFM_TART.")


def _reaper() -> Check:
    try:
        return Check("reaper", PASS, find_reaper(None))
    except ValueError:
        return Check("reaper", WARN, "mfm-reaper not found", "Build src/mfm/Reaper, then put it on PATH or set MFM_REAPER. Without it, expired leases are not quarantined.")


def _swift() -> Check:
    found = shutil.which("swift")
    if found:
        return Check("swift", PASS, found)
    return Check("swift", WARN, "not found", "Needed only for `lease acquire --health`, which reads thermal state and memory pressure.")


def run_checks(state: str) -> list[Check]:
    return [_python(), _state(state), _host(), _tart(), _reaper(), _swift()]


def main(state: str, as_json: bool) -> int:
    checks = run_checks(state)
    if as_json:
        print(json.dumps([asdict(c) for c in checks], indent=2))
    else:
        for c in checks:
            print(f"{c.status.upper():<5} {c.name:<11} {c.detail}")
            if c.fix and c.status != PASS:
                print(f"      fix: {c.fix}")
        fails, warns = sum(c.status == FAIL for c in checks), sum(c.status == WARN for c in checks)
        print(f"\n{fails} fail, {warns} warn. " + ("Fix the failures before a pilot." if fails else "Warnings only block the features named in them."))
    return 1 if any(c.status == FAIL for c in checks) else 0
