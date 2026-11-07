"""Structural validation for Spinnaker pipeline-as-code JSON.

This checks the shape Spinnaker expects and the promotion gates deploy/SPINNAKER.md
describes. It does not talk to a Spinnaker server, so it cannot prove a pipeline saves
or runs there. `spin pipeline save` is the real acceptance test.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field

# Stage types this repo is willing to ship. A curated list of core Spinnaker types, not
# the full set a given installation has, so an unlisted type fails with a clear message
# and the fix is to add it here after checking it exists in your Spinnaker.
KNOWN_STAGE_TYPES = frozenset({
    "bake", "bakeManifest", "checkPreconditions", "cloneServerGroup", "createServerGroup",
    "deleteManifest", "deploy", "deployManifest", "destroyServerGroup", "disableCluster",
    "disableManifest", "enableManifest", "evaluateVariables", "findArtifactFromExecution",
    "findImage", "jenkins", "kayentaCanary", "manualJudgment", "patchManifest", "pipeline",
    "resizeServerGroup", "rollbackCluster", "runJob", "runJobManifest", "scaleManifest",
    "script", "shrinkCluster", "undoRolloutManifest", "wait", "webhook",
})

# Fields Spinnaker needs on top of refId/name/type/requisiteStageRefIds, per stage type.
TYPE_REQUIRED: dict[str, tuple[str, ...]] = {
    "webhook": ("url", "method"),
    "manualJudgment": ("failPipeline",),
    "runJobManifest": ("account", "cloudProvider", "source"),
    "deployManifest": ("account", "cloudProvider", "source"),
    "bakeManifest": ("templateRenderer",),
    "wait": ("waitTime",),
}

CANARY_CHECKS = (
    "runner boot", "runner registration", "lease acquisition",
    "representative Xcode build", "telemetry health", "clean teardown",
)

_PARAM_REF = re.compile(r"\$\{[^}]*?parameters\.([A-Za-z_][A-Za-z0-9_]*)")


@dataclass
class Pipeline:
    path: str
    doc: dict
    errors: list[str] = field(default_factory=list)

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    @property
    def stages(self) -> dict[str, dict]:
        return {s["refId"]: s for s in self.doc.get("stages", []) if isinstance(s, dict) and "refId" in s}


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    out: dict = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _strings(node: object):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _strings(value)


def ancestors(stages: dict[str, dict], ref: str) -> set[str]:
    seen: set[str] = set()
    todo = list(stages[ref].get("requisiteStageRefIds", []))
    while todo:
        cur = todo.pop()
        if cur in seen or cur not in stages:
            continue
        seen.add(cur)
        todo.extend(stages[cur].get("requisiteStageRefIds", []))
    return seen


def _check_shape(p: Pipeline) -> None:
    doc = p.doc
    for key in ("application", "name"):
        if not isinstance(doc.get(key), str) or not doc[key].strip():
            p.err(f"{key} is required and must be a non-empty string")
    stages = doc.get("stages")
    if not isinstance(stages, list) or not stages:
        p.err("stages is required and must be a non-empty list")
        return

    params: set[str] = set()
    for entry in doc.get("parameterConfig", []):
        name = entry.get("name") if isinstance(entry, dict) else None
        if not isinstance(name, str) or not name:
            p.err("parameterConfig entries need a name")
        elif name in params:
            p.err(f"duplicate parameter: {name}")
        else:
            params.add(name)

    seen: set[str] = set()
    for i, stage in enumerate(stages):
        where = f"stage #{i + 1}"
        if not isinstance(stage, dict):
            p.err(f"{where} must be an object")
            continue
        ref = stage.get("refId")
        if not isinstance(ref, str) or not ref:
            p.err(f"{where} needs a string refId")
            continue
        where = f"stage {ref}"
        if ref in seen:
            p.err(f"{where}: duplicate refId")
        seen.add(ref)
        if not isinstance(stage.get("name"), str) or not stage["name"]:
            p.err(f"{where}: name is required")
        kind = stage.get("type")
        if kind not in KNOWN_STAGE_TYPES:
            p.err(f"{where}: unknown stage type {kind!r}")
        req = stage.get("requisiteStageRefIds")
        if not isinstance(req, list) or not all(isinstance(r, str) for r in req):
            p.err(f"{where}: requisiteStageRefIds is required and must be a list of refIds")
        for key in TYPE_REQUIRED.get(kind, ()):
            if key not in stage:
                p.err(f"{where}: {kind} stages need {key}")
        for text in _strings(stage):
            for name in _PARAM_REF.findall(text):
                if name not in params:
                    p.err(f"{where}: references parameters.{name} but no such parameter is defined")

    by_ref = p.stages
    for ref, stage in by_ref.items():
        for r in stage.get("requisiteStageRefIds", []) if isinstance(stage.get("requisiteStageRefIds"), list) else []:
            if r == ref:
                p.err(f"stage {ref}: requires itself")
            elif r not in by_ref:
                p.err(f"stage {ref}: requisiteStageRefIds names {r!r}, which is not a stage")
    _check_cycles(p, by_ref)


def _check_cycles(p: Pipeline, by_ref: dict[str, dict]) -> None:
    deps = {
        ref: [r for r in s.get("requisiteStageRefIds", []) if r in by_ref and r != ref]
        for ref, s in by_ref.items()
        if isinstance(s.get("requisiteStageRefIds"), list)
    }
    indegree = {ref: len(d) for ref, d in deps.items()}
    ready = [ref for ref, n in indegree.items() if n == 0]
    done = 0
    while ready:
        cur = ready.pop()
        done += 1
        for ref, d in deps.items():
            if cur in d:
                indegree[ref] -= 1
                if indegree[ref] == 0:
                    ready.append(ref)
    if done != len(deps):
        stuck = sorted(ref for ref, n in indegree.items() if n > 0)
        p.err(f"dependency cycle among stages: {', '.join(stuck)}")


def _gate(p: Pipeline, gate: str, kind: str, protects: list[str]) -> None:
    """`gate` must be a stage of `kind` that fails the pipeline and precedes each stage in `protects`."""
    stages = p.stages
    if gate not in stages:
        p.err(f"missing gate stage {gate}")
        return
    if stages[gate].get("type") != kind:
        p.err(f"gate {gate} must be a {kind} stage")
    if stages[gate].get("failPipeline") is not True:
        p.err(f"gate {gate} must set failPipeline true so a failed gate blocks promotion")
    for target in protects:
        if target not in stages:
            p.err(f"missing stage {target} that gate {gate} should protect")
        elif gate not in ancestors(stages, target):
            p.err(f"stage {target} can run without passing gate {gate}")


def _control_plane(p: Pipeline) -> None:
    _gate(p, "approve-prod", "manualJudgment", ["bake-prod", "deploy-prod", "smoke-prod"])


def _image_promotion(p: Pipeline) -> None:
    _gate(p, "canary", "webhook", ["green", "blue-green"])
    stages = p.stages
    if all(r in stages for r in ("build", "canary", "green", "blue-green")):
        order = [("build", "canary"), ("canary", "green"), ("green", "blue-green")]
        for before, after in order:
            if before not in ancestors(stages, after):
                p.err(f"promotion order must be build -> canary -> green -> blue-green; {after} does not follow {before}")
        text = json.dumps(stages["canary"].get("payload", {}))
        for check in CANARY_CHECKS:
            if check not in text:
                p.err(f"canary payload must require the check {check!r}")


def _image_rollback(p: Pipeline) -> None:
    names = {e.get("name") for e in p.doc.get("parameterConfig", []) if isinstance(e, dict)}
    if "lastKnownGoodDigest" not in names:
        p.err("rollback needs a lastKnownGoodDigest parameter")
    stage = p.stages.get("rollback")
    if not stage:
        p.err("missing stage rollback")
    elif "parameters.lastKnownGoodDigest" not in json.dumps(stage.get("payload", {})):
        p.err("rollback must point at parameters.lastKnownGoodDigest")


# Gates are looked up by pipeline name. A pipeline with another name gets the structural
# checks only, and validate() says so.
POLICIES: dict[str, Callable[[Pipeline], None]] = {
    "deploy-control-plane": _control_plane,
    "promote-macos-image": _image_promotion,
    "rollback-macos-image": _image_rollback,
}


def validate_file(path: str) -> tuple[Pipeline | None, list[str]]:
    try:
        with open(path, encoding="utf-8") as handle:
            doc = json.load(handle, object_pairs_hook=_no_duplicate_keys)
    except (OSError, ValueError) as exc:
        return None, [f"cannot read pipeline: {exc}"]
    if not isinstance(doc, dict):
        return None, ["pipeline must be a JSON object"]
    pipeline = Pipeline(path, doc)
    _check_shape(pipeline)
    if not pipeline.errors:
        policy = POLICIES.get(doc["name"])
        if policy:
            policy(pipeline)
    return pipeline, pipeline.errors


def main(paths: list[str]) -> int:
    """Print one result per file. Returns 1 if any file is invalid."""
    if not paths:
        raise ValueError("give at least one pipeline JSON file")
    failed = False
    for path in paths:
        pipeline, errors = validate_file(path)
        if errors:
            failed = True
            print(f"INVALID {path}")
            for msg in errors:
                print(f"  - {msg}")
            continue
        assert pipeline is not None
        gated = "gates checked" if pipeline.doc["name"] in POLICIES else "structure only, no gate policy for this name"
        print(f"OK {path} ({len(pipeline.doc['stages'])} stages, {gated})")
    return 1 if failed else 0
