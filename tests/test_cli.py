import json
import time

import pytest

from mfm.cli import main, render_metrics
from mfm.inventory import Inventory


def run_cli(monkeypatch, capsys, state, *argv):
    monkeypatch.setattr("sys.argv", ["mfm", "--state", str(state), *argv])
    code = main()
    out = capsys.readouterr()
    return code, out.out, out.err


def test_readme_quick_start_sequence(tmp_path, monkeypatch, capsys):
    state = tmp_path / "state.json"
    code, out, _ = run_cli(monkeypatch, capsys, state, "inventory", "sample")
    assert code == 0 and len(json.loads(out)) == 3
    code, out, _ = run_cli(monkeypatch, capsys, state, "lease", "acquire", "--runner", "m1-01", "--job", "demo-123")
    assert code == 0 and out.strip() == "leased m1-01 to demo-123"
    code, out, _ = run_cli(monkeypatch, capsys, state, "lease", "release", "--runner", "m1-01",
                           "--job", "demo-123", "--result", "success")
    assert code == 0 and out.strip() == "draining m1-01 after success"


def test_acquire_and_release_json(tmp_path, monkeypatch, capsys):
    state = tmp_path / "state.json"
    code, out, _ = run_cli(monkeypatch, capsys, state, "lease", "acquire", "--job", "j1", "--json")
    doc = json.loads(out)
    assert code == 0 and doc["state"] == "leased" and doc["job_id"] == "j1"
    code, out, _ = run_cli(monkeypatch, capsys, state, "lease", "release", "--runner", doc["runner_id"],
                           "--job", "j1", "--result", "failure", "--json")
    assert code == 0 and json.loads(out)["state"] == "draining"


def test_unknown_runner(tmp_path, monkeypatch, capsys):
    code, _, err = run_cli(monkeypatch, capsys, tmp_path / "s.json", "lease", "acquire",
                           "--runner", "ghost", "--job", "j")
    assert code == 2 and "unknown runner: ghost" in err


@pytest.mark.parametrize("ttl", ["0", "-5", "abc"])
def test_bad_ttl_is_rejected_before_any_state_change(tmp_path, monkeypatch, capsys, ttl):
    state = tmp_path / "s.json"
    monkeypatch.setattr("sys.argv", ["mfm", "--state", str(state), "lease", "acquire", "--job", "j", "--ttl", ttl])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2 and not state.exists()


def test_release_by_wrong_job_fails_and_keeps_lease(tmp_path, monkeypatch, capsys):
    state = tmp_path / "s.json"
    run_cli(monkeypatch, capsys, state, "lease", "acquire", "--runner", "m1-01", "--job", "right")
    code, _, err = run_cli(monkeypatch, capsys, state, "lease", "release", "--runner", "m1-01",
                           "--job", "wrong", "--result", "success")
    assert code == 2 and "does not belong" in err
    assert Inventory.load(str(state)).get("m1-01").job_id == "right"


def test_release_without_lease_says_so(tmp_path, monkeypatch, capsys):
    code, _, err = run_cli(monkeypatch, capsys, tmp_path / "s.json", "lease", "release",
                           "--runner", "m1-01", "--job", "j", "--result", "success")
    assert code == 2 and "no active lease" in err


def test_expired_lease_is_visible_as_overdue(tmp_path, monkeypatch, capsys):
    state = tmp_path / "s.json"
    run_cli(monkeypatch, capsys, state, "lease", "acquire", "--runner", "m1-01", "--job", "j", "--ttl", "1")
    time.sleep(1.1)
    _, out, _ = run_cli(monkeypatch, capsys, state, "inventory", "list")
    expires = {r["runner_id"]: r["lease_expires_at"] for r in json.loads(out)}["m1-01"]
    assert expires <= time.time()


def test_metrics_output(tmp_path, monkeypatch, capsys):
    state = tmp_path / "s.json"
    run_cli(monkeypatch, capsys, state, "lease", "acquire", "--runner", "m1-01", "--job", "j", "--ttl", "600")
    with Inventory.transaction(str(state)) as inv:
        inv.get("m1-03").quarantine()
    code, out, _ = run_cli(monkeypatch, capsys, state, "metrics")
    assert code == 0
    assert 'mfm_runners{state="leased"} 1' in out
    assert 'mfm_runners{state="quarantined"} 1' in out
    assert 'mfm_runners{state="ready"} 1' in out
    line = next(ln for ln in out.splitlines() if ln.startswith('mfm_lease_seconds_until_expiry{runner="m1-01"}'))
    assert 590 <= int(line.split()[-1]) <= 600


def test_metrics_reports_negative_for_overdue_lease():
    inv = Inventory()
    inv.sample()
    inv.get("m1-01").lease("j", 10)
    text = render_metrics(inv, inv.get("m1-01").lease_expires_at + 5)
    assert 'mfm_lease_seconds_until_expiry{runner="m1-01"} -5' in text
