import json

import pytest

from mfm.cli import build_parser, main
from mfm.health import parse_health
from mfm.inventory import Inventory
from mfm.model import Runner, RunnerState


def health(**per_runner):
    return parse_health(
        {
            rid: {
                "thermalState": thermal,
                "memory": {"swapUsedBytes": swap, "swapTotalBytes": 1000},
            }
            for rid, (thermal, swap) in per_runner.items()
        }
    )


def run_cli(monkeypatch, capsys, state, *argv):
    monkeypatch.setattr("sys.argv", ["mfm", "--state", str(state), *argv])
    code = main()
    out = capsys.readouterr()
    return code, out.out, out.err


def test_lease_then_release_across_separate_invocations(tmp_path, monkeypatch, capsys):
    state = tmp_path / "state.json"
    assert run_cli(monkeypatch, capsys, state, "lease", "acquire", "--runner", "m1-01", "--job", "j1")[0] == 0
    code, out, _ = run_cli(monkeypatch, capsys, state, "lease", "release", "--runner", "m1-01",
                           "--job", "j1", "--result", "success")
    assert code == 0 and "draining m1-01" in out
    saved = {r["runner_id"]: r["state"] for r in json.loads(state.read_text())}
    assert saved["m1-01"] == "draining"


def test_inventory_list_shows_leased_runners_for_the_reaper(tmp_path, monkeypatch, capsys):
    state = tmp_path / "state.json"
    run_cli(monkeypatch, capsys, state, "lease", "acquire", "--runner", "m1-02", "--job", "j2", "--ttl", "5")
    _, out, _ = run_cli(monkeypatch, capsys, state, "inventory", "list")
    by_id = {r["runner_id"]: r for r in json.loads(out)}
    assert len(by_id) == 3
    assert by_id["m1-02"]["state"] == "leased" and by_id["m1-02"]["lease_expires_at"] is not None


def test_inventory_sample_does_not_touch_state(tmp_path, monkeypatch, capsys):
    state = tmp_path / "state.json"
    code, out, _ = run_cli(monkeypatch, capsys, state, "inventory", "sample")
    assert code == 0 and len(json.loads(out)) == 3 and not state.exists()


@pytest.mark.parametrize(
    "argv, fragment",
    [
        (["lease", "acquire", "--runner", "nope", "--job", "j"], "unknown runner: nope"),
        (["lease", "release", "--runner", "m1-01", "--job", "j", "--result", "success"], "no active lease"),
        (["lease", "acquire", "--runner", "m1-01", "--image", "x", "--job", "j"], "cannot be combined"),
    ],
)
def test_errors_exit_2_with_message_not_traceback(tmp_path, monkeypatch, capsys, argv, fragment):
    code, _, err = run_cli(monkeypatch, capsys, tmp_path / "s.json", *argv)
    assert code == 2 and fragment in err and "Traceback" not in err


def test_pick_without_telemetry_takes_first_ready():
    inv = Inventory([Runner("a", "img"), Runner("b", "img")])
    assert inv.pick().runner_id == "a"


def test_pick_skips_hot_and_swapping_hosts_and_ranks_coolest_first():
    inv = Inventory([Runner(r, "img") for r in ("hot", "swappy", "fair", "cool")])
    h = health(hot=("serious", 0), swappy=("nominal", 900), fair=("fair", 0), cool=("nominal", 100))
    assert inv.pick("img", h).runner_id == "cool"
    inv.get("cool").lease("j")
    assert inv.pick("img", h).runner_id == "fair"


def test_pick_ranks_runner_without_telemetry_last():
    inv = Inventory([Runner("blind", "img"), Runner("seen", "img")])
    assert inv.pick("img", health(seen=("fair", 0))).runner_id == "seen"


def test_pick_fails_closed_when_every_host_is_unhealthy():
    inv = Inventory([Runner("a", "img"), Runner("b", "img")])
    with pytest.raises(ValueError, match="a: thermal state critical.*b: swap 95% used"):
        inv.pick("img", health(a=("critical", 0), b=("nominal", 950)))


def test_pick_filters_by_image_and_reports_no_match():
    inv = Inventory([Runner("a", "old")])
    with pytest.raises(ValueError, match="no ready runner for image new"):
        inv.pick("new")


def test_cli_acquire_uses_health_file(tmp_path, monkeypatch, capsys):
    hf = tmp_path / "health.json"
    hf.write_text(json.dumps({
        "m1-01": {"thermalState": "critical", "memory": {}},
        "m1-02": {"thermalState": "fair", "memory": {}},
        "m1-03": {"thermalState": "nominal", "memory": {}},
    }))
    code, out, _ = run_cli(monkeypatch, capsys, tmp_path / "s.json", "lease", "acquire", "--job", "j",
                           "--health", str(hf))
    assert code == 0 and out.strip() == "leased m1-03 to j"


def test_state_roundtrip_preserves_runner_fields():
    r = Runner("x", "img", state=RunnerState.LEASED, job_id="j", lease_expires_at=12.5)
    assert Runner.from_dict(r.to_dict()) == r


def test_parser_builds():
    assert build_parser().parse_args(["inventory", "list"]).action == "list"


def test_version_flag(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["mfm", "--version"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0 and capsys.readouterr().out.startswith("mfm ")
