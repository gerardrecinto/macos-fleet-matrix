"""Real Tart end to end. Skipped unless tart is on PATH and MFM_TART_E2E=1.

It clones a real macOS VM, boots it headless and waits for an IP, then tears it down.
The first run pulls the image (many GB). Set MFM_TART_E2E_IMAGE to use another image.
Check Apple's software license agreement before running macOS VMs on a host.
"""
import json
import os
import shutil
import subprocess
import time

import pytest

from mfm.cli import main
from mfm.inventory import Inventory
from mfm.model import Runner, RunnerState

IMAGE = os.environ.get("MFM_TART_E2E_IMAGE", "ghcr.io/cirruslabs/macos-tahoe-base:latest")

pytestmark = pytest.mark.skipif(
    not (shutil.which("tart") and os.environ.get("MFM_TART_E2E") == "1"),
    reason="needs tart on PATH and MFM_TART_E2E=1",
)


def run(monkeypatch, capsys, state, *argv):
    monkeypatch.setattr("sys.argv", ["mfm", "--state", str(state), *argv])
    code = main()
    out = capsys.readouterr()
    return code, out.out, out.err


def test_real_vm_boots_gets_an_ip_and_is_destroyed(tmp_path, monkeypatch, capsys):
    state = tmp_path / "state.json"
    inv = Inventory([Runner(runner_id="e2e-01", image=IMAGE)])
    inv.save(str(state))
    job = f"e2e-{int(time.time())}"
    vm = f"mfm-e2e-01-{job}"
    try:
        code, out, err = run(monkeypatch, capsys, state, "lease", "acquire", "--backend", "tart",
                             "--runner", "e2e-01", "--job", job, "--boot-timeout", "300", "--json")
        assert code == 0, err
        doc = json.loads(out)
        assert doc["vm_name"] == vm and doc["vm_ip"].count(".") == 3
        listed = subprocess.run(["tart", "list", "--source", "local", "--quiet"],
                                capture_output=True, text=True, check=True).stdout.split()
        assert vm in listed
        code, _, err = run(monkeypatch, capsys, state, "lease", "release", "--runner", "e2e-01",
                           "--job", job, "--result", "success")
        assert code == 0, err
        assert Inventory.load(str(state)).get("e2e-01").state is RunnerState.DRAINING
        listed = subprocess.run(["tart", "list", "--source", "local", "--quiet"],
                                capture_output=True, text=True, check=True).stdout.split()
        assert vm not in listed
    finally:
        subprocess.run(["tart", "stop", vm], capture_output=True, check=False)
        subprocess.run(["tart", "delete", vm], capture_output=True, check=False)
