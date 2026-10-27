import json
import os
import stat
import time

import pytest

from mfm.cli import main
from mfm.inventory import Inventory
from mfm.reap import find_reaper, reap_once

REAL_REAPER = os.environ.get("MFM_REAPER")


def cli(monkeypatch, capsys, state, *argv):
    monkeypatch.setattr("sys.argv", ["mfm", "--state", str(state), *argv])
    code = main()
    out = capsys.readouterr()
    return code, out.out, out.err


def fake_reaper(tmp_path, body):
    path = tmp_path / "fake-reaper"
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def test_missing_reaper_binary_fails_closed(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("MFM_REAPER", raising=False)
    code, _, err = cli(monkeypatch, capsys, tmp_path / "s.json", "reap", "--once", "--reaper", "nope-reaper")
    assert code == 2 and "reaper binary not found" in err


def test_reaper_failure_leaves_state_untouched(tmp_path):
    state = str(tmp_path / "s.json")
    Inventory.load(state).save(state)
    before = open(state).read()
    bad = fake_reaper(tmp_path, "echo 'bad inventory' >&2; exit 1")
    with pytest.raises(ValueError, match="reaper failed"):
        reap_once(state, bad)
    assert open(state).read() == before


def test_reap_once_writes_back_what_the_reaper_changed(tmp_path):
    state = str(tmp_path / "s.json")
    with Inventory.transaction(state) as inv:
        inv.get("m1-01").lease("j1")
    script = fake_reaper(
        tmp_path,
        "python3 -c \"import json,sys;f=json.load(sys.stdin);"
        "f[0].update(state='quarantined',job_id=None,lease_expires_at=None);"
        "print(json.dumps(f))\"; echo 'mfm-reaper: quarantined m1-01 (lease expired)' >&2",
    )
    assert reap_once(state, script) == ["m1-01"]
    saved = {r["runner_id"]: r["state"] for r in json.loads(open(state).read())}
    assert saved["m1-01"] == "quarantined"


@pytest.mark.skipif(not REAL_REAPER, reason="set MFM_REAPER to the built mfm-reaper binary")
def test_real_reaper_quarantines_only_the_expired_lease(tmp_path, monkeypatch, capsys):
    state = tmp_path / "s.json"
    cli(monkeypatch, capsys, state, "lease", "acquire", "--runner", "m1-01", "--job", "short", "--ttl", "1")
    cli(monkeypatch, capsys, state, "lease", "acquire", "--runner", "m1-02", "--job", "long", "--ttl", "600")
    time.sleep(1.2)
    code, out, _ = cli(monkeypatch, capsys, state, "reap", "--once", "--reaper", REAL_REAPER)
    assert code == 0 and "quarantined m1-01" in out
    _, listing, _ = cli(monkeypatch, capsys, state, "inventory", "list")
    by_id = {r["runner_id"]: r["state"] for r in json.loads(listing)}
    assert by_id == {"m1-01": "quarantined", "m1-02": "leased", "m1-03": "ready"}


def test_find_reaper_prefers_explicit_path(tmp_path):
    script = fake_reaper(tmp_path, "true")
    assert find_reaper(script) == script
