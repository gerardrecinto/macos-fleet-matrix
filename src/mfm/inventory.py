"""In-memory inventory used by the reference control plane and tests."""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager

from .health import NO_TELEMETRY_RANK, HostHealth
from .model import Runner, RunnerState


class Inventory:
    def __init__(self, runners: list[Runner] | None = None) -> None:
        self._runners = {r.runner_id: r for r in (runners or [])}

    def add(self, runner: Runner) -> None:
        if runner.runner_id in self._runners:
            raise ValueError(f"runner {runner.runner_id} already exists")
        self._runners[runner.runner_id] = runner

    def get(self, runner_id: str) -> Runner:
        try:
            return self._runners[runner_id]
        except KeyError as exc:
            raise KeyError(f"unknown runner: {runner_id}") from exc

    def ready(self, image: str | None = None) -> list[Runner]:
        return [
            r for r in self._runners.values()
            if r.state is RunnerState.READY and (image is None or r.image == image)
        ]

    def all(self) -> list[Runner]:
        return list(self._runners.values())

    def pick(
        self, image: str | None = None, health: dict[str, HostHealth] | None = None
    ) -> Runner:
        """Best READY runner for a job.

        Without telemetry this is the first ready runner. With it, hosts that are hot
        (serious/critical) or already swapping are refused, and the rest are ranked
        coolest and least-swapped first. A runner missing from the telemetry ranks last.
        """
        candidates = self.ready(image)
        if not candidates:
            raise ValueError(f"no ready runner{f' for image {image}' if image else ''}")
        if health is None:
            return candidates[0]
        refused = {}
        fit = []
        for runner in candidates:
            host = health.get(runner.runner_id)
            reason = host.refusal() if host else None
            if reason:
                refused[runner.runner_id] = reason
            else:
                fit.append(runner)
        if not fit:
            detail = ", ".join(f"{rid}: {why}" for rid, why in refused.items())
            raise ValueError(f"every ready runner is unhealthy ({detail})")

        def rank(runner: Runner) -> tuple[int, int]:
            host = health.get(runner.runner_id)
            return host.sort_key() if host else (NO_TELEMETRY_RANK, 0)

        return min(fit, key=rank)

    def to_json(self) -> str:
        return json.dumps([r.to_dict() for r in self._runners.values()], indent=2)

    @classmethod
    def from_json(cls, raw: str) -> Inventory:
        return cls([Runner.from_dict(doc) for doc in json.loads(raw)])

    @classmethod
    def load(cls, path: str) -> Inventory:
        """Load saved state, or seed the sample fleet when the file does not exist yet."""
        try:
            with open(path, encoding="utf-8") as handle:
                return cls.from_json(handle.read())
        except FileNotFoundError:
            inventory = cls()
            inventory.sample()
            return inventory

    @classmethod
    @contextmanager
    def transaction(cls, path: str) -> Iterator[Inventory]:
        """Load state under an exclusive lock, yield it, and save it on a clean exit.

        The lock is what lets the lease CLI and the reaper loop share one state file
        without one overwriting the other's change.
        """
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path + ".lock", "w", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            inventory = cls.load(path)
            yield inventory
            inventory.save(path)

    def replace_with(self, other: Inventory) -> None:
        self._runners = dict(other._runners)

    def save(self, path: str) -> None:
        """Write atomically so a crash mid-write never leaves a torn state file."""
        directory = os.path.dirname(os.path.abspath(path))
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".mfm-state-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(self.to_json())
            os.replace(tmp, path)
        except BaseException:
            os.unlink(tmp)
            raise

    def sample(self) -> None:
        for runner_id in ("m1-01", "m1-02", "m1-03"):
            self.add(Runner(runner_id=runner_id, image="macos-15-xcode-16"))
