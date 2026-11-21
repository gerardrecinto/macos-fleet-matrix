import json
import os

from mfm import doctor
from mfm.cli import main


def run_cli(monkeypatch, capsys, state, *argv):
    monkeypatch.setattr("sys.argv", ["mfm", "--state", str(state), *argv])
    code = main()
    out = capsys.readouterr()
    return code, out.out, out.err


def test_clean_host_passes_with_only_warnings(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PATH", "")
    code, out, _ = run_cli(monkeypatch, capsys, tmp_path / "s.json", "doctor")
    assert code == 0
    assert "PASS  python" in out and "WARN  tart" in out and "fix:" in out and "0 fail" in out


def test_unreadable_state_fails_and_names_the_fix(tmp_path, monkeypatch, capsys):
    bad = tmp_path / "s.json"
    bad.write_text("not json")
    code, out, _ = run_cli(monkeypatch, capsys, bad, "doctor")
    assert code == 1 and "FAIL  state file" in out and "Move it aside" in out


def test_state_summary_and_no_ready_runner_warning(tmp_path, monkeypatch, capsys):
    state = tmp_path / "s.json"
    run_cli(monkeypatch, capsys, state, "lease", "acquire", "--runner", "m1-01", "--job", "j")
    code, out, _ = run_cli(monkeypatch, capsys, state, "doctor", "--json")
    rows = {c["name"]: c for c in json.loads(out)}
    assert code == 0 and rows["state file"]["status"] == "pass" and "1 leased" in rows["state file"]["detail"]


def test_unwritable_state_directory_fails(tmp_path, monkeypatch, capsys):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        if os.access(locked, os.W_OK):  # running as root
            return
        code, out, _ = run_cli(monkeypatch, capsys, locked / "sub" / "s.json", "doctor")
        assert code == 1 and "Set MFM_STATE" in out
    finally:
        locked.chmod(0o700)


def test_old_python_is_a_failure(monkeypatch):
    class V:
        major, minor, micro = 3, 10, 0

    monkeypatch.setattr(doctor.sys, "version_info", V)
    assert doctor._python().status == doctor.FAIL


def test_rosetta_python_on_apple_silicon_is_not_flagged(monkeypatch):
    class R:
        returncode, stdout = 0, "1\n"

    monkeypatch.setattr(doctor.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(doctor.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **k: R())
    assert doctor._host().status == doctor.PASS


def test_linux_host_is_a_warning(monkeypatch):
    monkeypatch.setattr(doctor.platform, "system", lambda: "Linux")
    assert doctor._host().status == doctor.WARN
