import json
import os
import stat
import subprocess
import sys

import pytest

from mfm.cli import main
from mfm.inventory import Inventory
from mfm.model import RunnerState
from mfm.reap import reap_once
from mfm.tart import (
    INSTALL_HINT,
    Tart,
    TartCleanupError,
    TartError,
    TartMissing,
    find_tart,
    vm_name_for,
)

FAKE = os.path.join(os.path.dirname(__file__), "fake_tart.py")


class Calls:
    """An injectable runner that records argv and answers from a script."""

    def __init__(self, fail=(), existing=()):
        self.argv = []
        self.fail = set(fail)
        self.vms = set(existing)
        self.spawned = []

    def run(self, argv, timeout):
        self.argv.append(argv)
        sub = argv[1]
        if sub in self.fail:
            return subprocess.CompletedProcess(argv, 1, "", f"{sub} boom")
        out = ""
        if sub == "list":
            out = "\n".join(sorted(self.vms))
        elif sub == "clone":
            self.vms.add(argv[3])
        elif sub == "delete":
            self.vms.discard(argv[2])
        elif sub == "ip":
            out = "192.168.64.9\n"
        return subprocess.CompletedProcess(argv, 0, out, "")

    def spawn(self, argv, log_path):
        self.spawned.append(argv)
        self.argv.append(argv)

    def tart(self):
        return Tart(runner=self.run, spawner=self.spawn)

    def subs(self):
        return [a[1] for a in self.argv]


# Command construction and adapter behavior with an injected runner.

def test_command_construction():
    t = Tart()
    assert t.cmd_list() == ["tart", "list", "--source", "local", "--quiet"]
    assert t.cmd_pull("ghcr.io/x/y:1") == ["tart", "pull", "ghcr.io/x/y:1"]
    assert t.cmd_clone("img", "vm") == ["tart", "clone", "img", "vm"]
    assert t.cmd_run("vm") == ["tart", "run", "vm", "--no-graphics"]
    assert t.cmd_ip("vm", 90) == ["tart", "ip", "vm", "--wait", "90"]
    assert t.cmd_stop("vm") == ["tart", "stop", "vm"]
    assert t.cmd_delete("vm") == ["tart", "delete", "vm"]
    assert [a[1] for a in t.plan_acquire("img", "vm", 90, pull=True)] == ["pull", "clone", "run", "ip"]
    assert [a[1] for a in t.plan_release("vm")] == ["stop", "delete"]


def test_vm_name_is_safe_and_bounded():
    assert vm_name_for("m1-01", "demo 123/x") == "mfm-m1-01-demo-123-x"
    assert len(vm_name_for("r", "j" * 200)) <= 80


def test_acquire_runs_clone_boot_ip_in_order():
    calls = Calls()
    ip = calls.tart().acquire("img", "vm", wait=30)
    assert ip == "192.168.64.9"
    assert calls.subs() == ["list", "clone", "run", "ip"]
    assert calls.spawned == [["tart", "run", "vm", "--no-graphics"]]
    assert calls.argv[-1] == ["tart", "ip", "vm", "--wait", "30"]


def test_acquire_refuses_a_name_collision_without_touching_the_existing_vm():
    calls = Calls(existing={"vm"})
    with pytest.raises(TartError, match="already exists"):
        calls.tart().acquire("img", "vm")
    assert calls.subs() == ["list"]


def test_failed_ip_stops_and_deletes_the_half_started_vm():
    calls = Calls(fail={"ip"})
    with pytest.raises(TartError, match="ip failed"):
        calls.tart().acquire("img", "vm")
    assert calls.subs() == ["list", "clone", "run", "ip", "list", "stop", "delete"]
    assert calls.vms == set()


def test_failed_cleanup_is_reported_as_possibly_remaining():
    calls = Calls(fail={"ip", "delete"})
    with pytest.raises(TartCleanupError, match="cleanup also failed"):
        calls.tart().acquire("img", "vm")


def test_teardown_stops_before_deleting():
    calls = Calls(existing={"vm"})
    calls.tart().teardown("vm")
    assert calls.subs() == ["stop", "delete"]


def test_teardown_tolerates_a_vm_that_already_exited():
    calls = Calls(fail={"stop"}, existing={"vm"})
    calls.tart().teardown("vm")
    assert calls.subs() == ["stop", "delete"] and calls.vms == set()


def test_teardown_fails_when_delete_fails_and_vm_remains():
    calls = Calls(fail={"delete"}, existing={"vm"})
    with pytest.raises(TartError, match="could not tear down vm"):
        calls.tart().teardown("vm")


def test_timeout_becomes_a_clear_error():
    def slow(argv, timeout):
        raise subprocess.TimeoutExpired(argv, timeout)

    with pytest.raises(TartError, match=r"tart list timed out after 30s"):
        Tart(runner=slow).list_names()


def test_missing_binary_message(monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    monkeypatch.delenv("MFM_TART", raising=False)
    with pytest.raises(TartMissing) as exc:
        find_tart()
    assert INSTALL_HINT in str(exc.value) and "brew install cirruslabs/cli/tart" in str(exc.value)


# CLI behavior against a fake `tart` executable on PATH.

@pytest.fixture
def fake(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "tart"
    exe.write_text(f"#!{sys.executable}\nimport runpy\nrunpy.run_path({FAKE!r}, run_name='__main__')\n")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    home = tmp_path / "tart-home"
    log = tmp_path / "tart.log"
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_TART_HOME", str(home))
    monkeypatch.setenv("FAKE_TART_LOG", str(log))
    monkeypatch.delenv("FAKE_TART_FAIL", raising=False)
    monkeypatch.delenv("MFM_TART", raising=False)

    class Fake:
        def calls(self):
            return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

        def vms(self):
            return sorted(os.listdir(home / "vms")) if (home / "vms").exists() else []

    return Fake()


def cli(monkeypatch, capsys, state, *argv):
    monkeypatch.setattr("sys.argv", ["mfm", "--state", str(state), *argv])
    code = main()
    out = capsys.readouterr()
    return code, out.out, out.err


def acquire(monkeypatch, capsys, state, *extra):
    return cli(monkeypatch, capsys, state, "lease", "acquire", "--backend", "tart",
               "--runner", "m1-01", "--job", "demo-1", *extra)


def runner_of(state, rid="m1-01"):
    return Inventory.load(str(state)).get(rid)


def test_acquire_records_vm_name_and_ip_in_state(fake, tmp_path, monkeypatch, capsys):
    state = tmp_path / "s.json"
    code, out, _ = acquire(monkeypatch, capsys, state, "--boot-timeout", "45")
    assert code == 0 and "vm mfm-m1-01-demo-1, ip 192.168.64.7" in out
    r = runner_of(state)
    assert r.state is RunnerState.LEASED
    assert (r.vm_name, r.vm_ip) == ("mfm-m1-01-demo-1", "192.168.64.7")
    assert fake.vms() == ["mfm-m1-01-demo-1"]
    assert ["clone", "macos-15-xcode-16", "mfm-m1-01-demo-1"] in fake.calls()
    assert ["ip", "mfm-m1-01-demo-1", "--wait", "45"] in fake.calls()


def test_acquire_json_includes_vm_fields(fake, tmp_path, monkeypatch, capsys):
    code, out, err = acquire(monkeypatch, capsys, tmp_path / "s.json", "--json")
    assert code == 0, err
    doc = json.loads(out)
    assert code == 0 and doc["vm_name"] == "mfm-m1-01-demo-1" and doc["vm_ip"] == "192.168.64.7"


def test_pull_flag_runs_pull_first(fake, tmp_path, monkeypatch, capsys):
    code, _, _ = acquire(monkeypatch, capsys, tmp_path / "s.json", "--pull")
    assert code == 0 and ["pull", "macos-15-xcode-16"] in fake.calls()


def test_simulation_stays_the_default_and_never_calls_tart(fake, tmp_path, monkeypatch, capsys):
    code, out, _ = cli(monkeypatch, capsys, tmp_path / "s.json", "lease", "acquire",
                       "--runner", "m1-01", "--job", "j")
    assert code == 0 and out.strip() == "leased m1-01 to j" and fake.calls() == []
    assert runner_of(tmp_path / "s.json").vm_name is None


def test_release_stops_then_deletes_and_clears_vm(fake, tmp_path, monkeypatch, capsys):
    state = tmp_path / "s.json"
    acquire(monkeypatch, capsys, state)
    code, out, _ = cli(monkeypatch, capsys, state, "lease", "release", "--runner", "m1-01",
                       "--job", "demo-1", "--result", "success")
    assert code == 0 and out.strip() == "draining m1-01 after success"
    r = runner_of(state)
    assert r.state is RunnerState.DRAINING and r.vm_name is None and r.vm_ip is None
    subs = [c[0] for c in fake.calls()]
    assert subs[-2:] == ["stop", "delete"] and fake.vms() == []


def test_release_teardown_failure_quarantines_and_keeps_vm_name(fake, tmp_path, monkeypatch, capsys):
    state = tmp_path / "s.json"
    acquire(monkeypatch, capsys, state)
    monkeypatch.setenv("FAKE_TART_FAIL", "delete")
    code, _, err = cli(monkeypatch, capsys, state, "lease", "release", "--runner", "m1-01",
                       "--job", "demo-1", "--result", "success")
    assert code == 2 and "quarantined" in err
    r = runner_of(state)
    assert r.state is RunnerState.QUARANTINED and r.vm_name == "mfm-m1-01-demo-1"


def test_failed_boot_cleans_up_and_returns_runner_to_ready(fake, tmp_path, monkeypatch, capsys):
    state = tmp_path / "s.json"
    monkeypatch.setenv("FAKE_TART_FAIL", "ip")
    code, _, err = acquire(monkeypatch, capsys, state)
    assert code == 2 and "tart ip failed" in err
    r = runner_of(state)
    assert r.state is RunnerState.READY and r.job_id is None and r.vm_name is None
    assert fake.vms() == []


def test_failed_boot_and_failed_cleanup_quarantines(fake, tmp_path, monkeypatch, capsys):
    state = tmp_path / "s.json"
    monkeypatch.setenv("FAKE_TART_FAIL", "ip,delete")
    code, _, err = acquire(monkeypatch, capsys, state)
    assert code == 2 and "may remain" in err
    r = runner_of(state)
    assert r.state is RunnerState.QUARANTINED and r.vm_name == "mfm-m1-01-demo-1"


def test_clone_failure_leaves_nothing_and_runner_ready(fake, tmp_path, monkeypatch, capsys):
    state = tmp_path / "s.json"
    monkeypatch.setenv("FAKE_TART_FAIL", "clone")
    code, _, err = acquire(monkeypatch, capsys, state)
    assert code == 2 and "tart clone failed" in err
    assert runner_of(state).state is RunnerState.READY and fake.vms() == []


def test_name_collision_is_refused(fake, tmp_path, monkeypatch, capsys):
    state = tmp_path / "s.json"
    acquire(monkeypatch, capsys, state)
    code, _, err = cli(monkeypatch, capsys, state, "lease", "acquire", "--backend", "tart",
                       "--runner", "m1-02", "--job", "demo-1")
    assert code == 0  # different runner id gives a different VM name
    # same runner and job again after state was lost: the VM still exists on the host
    state2 = tmp_path / "s2.json"
    code, _, err = acquire(monkeypatch, capsys, state2)
    assert code == 2 and "already exists" in err
    assert runner_of(state2).state is RunnerState.READY and "mfm-m1-01-demo-1" in fake.vms()


def test_ip_timeout_is_reported_and_cleaned_up(fake, tmp_path, monkeypatch, capsys):
    from mfm import cli as cli_mod

    state = tmp_path / "s.json"
    monkeypatch.setenv("FAKE_TART_SLEEP_IP", "5")
    monkeypatch.setattr(cli_mod, "Tart", lambda binary="tart", **kw: Tart(binary, ip_margin=0, **kw))
    code, _, err = acquire(monkeypatch, capsys, state, "--boot-timeout", "1")
    assert code == 2 and "timed out after 1s" in err
    assert runner_of(state).state is RunnerState.READY and fake.vms() == []


def test_missing_tart_is_one_clear_message_exit_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PATH", "/nonexistent")
    monkeypatch.delenv("MFM_TART", raising=False)
    state = tmp_path / "s.json"
    code, out, err = acquire(monkeypatch, capsys, state)
    assert code == 2 and out == ""
    assert err.strip() == "mfm: tart not found on PATH. Install it with: brew install cirruslabs/cli/tart"
    assert not state.exists()


def test_dry_run_prints_commands_and_changes_nothing(fake, tmp_path, monkeypatch, capsys):
    state = tmp_path / "s.json"
    code, out, _ = acquire(monkeypatch, capsys, state, "--dry-run", "--pull", "--boot-timeout", "60")
    assert code == 0 and not state.exists() and fake.calls() == []
    lines = out.splitlines()
    assert lines[:4] == [
        "tart pull macos-15-xcode-16",
        "tart clone macos-15-xcode-16 mfm-m1-01-demo-1",
        "tart run mfm-m1-01-demo-1 --no-graphics",
        "tart ip mfm-m1-01-demo-1 --wait 60",
    ]


def test_dry_run_works_without_tart_installed(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PATH", "/nonexistent")
    code, out, _ = acquire(monkeypatch, capsys, tmp_path / "s.json", "--dry-run")
    assert code == 0 and "tart clone" in out


def test_release_dry_run_prints_stop_and_delete(fake, tmp_path, monkeypatch, capsys):
    state = tmp_path / "s.json"
    acquire(monkeypatch, capsys, state)
    before = state.read_text()
    code, out, _ = cli(monkeypatch, capsys, state, "lease", "release", "--runner", "m1-01",
                       "--job", "demo-1", "--result", "success", "--dry-run")
    assert code == 0 and state.read_text() == before
    assert out.splitlines()[:2] == ["tart stop mfm-m1-01-demo-1", "tart delete mfm-m1-01-demo-1"]


def test_dry_run_needs_the_tart_backend(tmp_path, monkeypatch, capsys):
    code, _, err = cli(monkeypatch, capsys, tmp_path / "s.json", "lease", "acquire",
                       "--runner", "m1-01", "--job", "j", "--dry-run")
    assert code == 2 and "--backend tart" in err


# The reaper path: quarantine by expiry, then destroy the VM.

def python_reaper(tmp_path):
    path = tmp_path / "py-reaper"
    path.write_text(
        f"#!{sys.executable}\n"
        "import json, sys, time\n"
        "fleet = json.load(sys.stdin)\n"
        "for r in fleet:\n"
        "    if r['state'] == 'leased' and r['lease_expires_at'] <= time.time():\n"
        "        r.update(state='quarantined', job_id=None, lease_expires_at=None)\n"
        "        print(f\"mfm-reaper: quarantined {r['runner_id']} (lease expired)\", file=sys.stderr)\n"
        "json.dump(fleet, sys.stdout)\n"
    )
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def test_reaper_tears_down_vm_of_expired_lease(fake, tmp_path, monkeypatch, capsys):
    state = tmp_path / "s.json"
    acquire(monkeypatch, capsys, state, "--ttl", "1")
    inv = Inventory.load(str(state))
    inv.get("m1-01").lease_expires_at = 1.0
    inv.save(str(state))
    assert reap_once(str(state), python_reaper(tmp_path)) == ["m1-01"]
    r = runner_of(state)
    assert r.state is RunnerState.QUARANTINED and r.vm_name is None and r.vm_ip is None
    assert fake.vms() == []
    assert [c[0] for c in fake.calls()][-2:] == ["stop", "delete"]


def test_reaper_keeps_vm_name_when_teardown_fails_then_retries(fake, tmp_path, monkeypatch, capsys):
    state = tmp_path / "s.json"
    acquire(monkeypatch, capsys, state)
    inv = Inventory.load(str(state))
    inv.get("m1-01").lease_expires_at = 1.0
    inv.save(str(state))
    reaper = python_reaper(tmp_path)
    monkeypatch.setenv("FAKE_TART_FAIL", "delete")
    reap_once(str(state), reaper)
    assert runner_of(state).vm_name == "mfm-m1-01-demo-1"
    assert "stays quarantined" in capsys.readouterr().err
    monkeypatch.setenv("FAKE_TART_FAIL", "")
    reap_once(str(state), reaper)  # next sweep retries the stuck VM
    assert runner_of(state).vm_name is None and fake.vms() == []


def test_vm_fields_survive_the_state_round_trip(tmp_path):
    inv = Inventory()
    inv.sample()
    inv.get("m1-01").vm_name = "vm"
    inv.get("m1-01").vm_ip = "1.2.3.4"
    path = str(tmp_path / "s.json")
    inv.save(path)
    again = Inventory.load(path).get("m1-01")
    assert (again.vm_name, again.vm_ip) == ("vm", "1.2.3.4")
