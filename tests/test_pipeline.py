import copy
import glob
import json
import os

import pytest

from mfm.cli import main
from mfm.pipeline import validate_file

ROOT = os.path.dirname(os.path.dirname(__file__))
SHIPPED = sorted(glob.glob(os.path.join(ROOT, "deploy", "spinnaker", "*.json")))


def load(name):
    with open(os.path.join(ROOT, "deploy", "spinnaker", name), encoding="utf-8") as handle:
        return json.load(handle)


def check(tmp_path, doc):
    path = tmp_path / "p.json"
    path.write_text(json.dumps(doc))
    return validate_file(str(path))[1]


def stage(doc, ref):
    return next(s for s in doc["stages"] if s["refId"] == ref)


def test_there_are_three_shipped_pipelines():
    names = {os.path.basename(p) for p in SHIPPED}
    assert names == {
        "control-plane-pipeline.json",
        "promote-macos-image-pipeline.json",
        "rollback-macos-image-pipeline.json",
    }


@pytest.mark.parametrize("path", SHIPPED, ids=os.path.basename)
def test_shipped_pipelines_are_valid(path):
    assert validate_file(path)[1] == []


@pytest.fixture
def promo():
    return load("promote-macos-image-pipeline.json")


def test_duplicate_ref_id(tmp_path, promo):
    promo["stages"][1]["refId"] = "build"
    assert any("duplicate refId" in e for e in check(tmp_path, promo))


def test_requisite_naming_a_missing_stage(tmp_path, promo):
    stage(promo, "green")["requisiteStageRefIds"] = ["nope"]
    assert any("'nope', which is not a stage" in e for e in check(tmp_path, promo))


def test_cycle(tmp_path, promo):
    stage(promo, "build")["requisiteStageRefIds"] = ["blue-green"]
    assert any("dependency cycle" in e for e in check(tmp_path, promo))


def test_self_reference(tmp_path, promo):
    stage(promo, "build")["requisiteStageRefIds"] = ["build"]
    assert any("requires itself" in e for e in check(tmp_path, promo))


def test_unknown_stage_type(tmp_path, promo):
    stage(promo, "green")["type"] = "teleportFleet"
    assert any("unknown stage type 'teleportFleet'" in e for e in check(tmp_path, promo))


def test_missing_required_fields(tmp_path, promo):
    del stage(promo, "green")["url"]
    del promo["application"]
    errors = check(tmp_path, promo)
    assert any("application is required" in e for e in errors)
    assert any("webhook stages need url" in e for e in errors)


def test_missing_requisite_list(tmp_path, promo):
    del stage(promo, "green")["requisiteStageRefIds"]
    assert any("requisiteStageRefIds is required" in e for e in check(tmp_path, promo))


def test_undefined_parameter_reference(tmp_path, promo):
    stage(promo, "green")["payload"]["imageDigest"] = "${parameters.imageDigset}"
    assert any("parameters.imageDigset" in e for e in check(tmp_path, promo))


def test_canary_must_fail_the_pipeline(tmp_path, promo):
    stage(promo, "canary")["failPipeline"] = False
    assert any("failPipeline true" in e for e in check(tmp_path, promo))


def test_stage_that_skips_the_canary_gate(tmp_path, promo):
    stage(promo, "green")["requisiteStageRefIds"] = ["build"]
    errors = check(tmp_path, promo)
    assert any("green can run without passing gate canary" in e for e in errors)
    assert any("promotion order" in e for e in errors)


def test_canary_must_require_every_documented_check(tmp_path, promo):
    checks = stage(promo, "canary")["payload"]["requiredChecks"]
    checks.remove("clean teardown")
    assert any("'clean teardown'" in e for e in check(tmp_path, promo))


def test_missing_canary_stage(tmp_path, promo):
    promo["stages"] = [s for s in promo["stages"] if s["refId"] != "canary"]
    stage(promo, "green")["requisiteStageRefIds"] = ["build"]
    assert any("missing gate stage canary" in e for e in check(tmp_path, promo))


def test_control_plane_needs_its_manual_judgment_before_prod(tmp_path):
    doc = load("control-plane-pipeline.json")
    stage(doc, "bake-prod")["requisiteStageRefIds"] = ["smoke-staging"]
    assert any("deploy-prod can run without passing gate approve-prod" in e for e in check(tmp_path, doc))
    doc = load("control-plane-pipeline.json")
    stage(doc, "approve-prod")["failPipeline"] = False
    assert any("failPipeline true" in e for e in check(tmp_path, doc))


def test_rollback_must_use_the_known_good_digest(tmp_path):
    doc = load("rollback-macos-image-pipeline.json")
    stage(doc, "rollback")["payload"]["imageDigest"] = "${parameters.promotionApiUrl}"
    assert any("lastKnownGoodDigest" in e for e in check(tmp_path, doc))


def test_other_names_get_structure_checks_only(tmp_path, promo, capsys):
    promo["name"] = "something-else"
    stage(promo, "green")["requisiteStageRefIds"] = ["build"]
    assert check(tmp_path, promo) == []


def test_bad_json_and_duplicate_keys(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert "cannot read pipeline" in validate_file(str(bad))[1][0]
    dup = tmp_path / "dup.json"
    dup.write_text('{"a": 1, "a": 2}')
    assert "duplicate JSON key: a" in validate_file(str(dup))[1][0]
    assert "cannot read pipeline" in validate_file(str(tmp_path / "missing.json"))[1][0]


def run_cli(monkeypatch, capsys, *argv):
    monkeypatch.setattr("sys.argv", ["mfm", *argv])
    code = main()
    return code, capsys.readouterr().out


def test_cli_exit_codes(tmp_path, monkeypatch, capsys):
    code, out = run_cli(monkeypatch, capsys, "pipeline", "validate", *SHIPPED)
    assert code == 0 and out.count("OK ") == 3
    broken = copy.deepcopy(load("promote-macos-image-pipeline.json"))
    broken["stages"][0]["type"] = "nope"
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(broken))
    code, out = run_cli(monkeypatch, capsys, "pipeline", "validate", SHIPPED[0], str(path))
    assert code == 1 and "INVALID" in out and "OK " in out
