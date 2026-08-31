"""In-memory inventory used by the reference control plane and tests."""
from __future__ import annotations

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

    def sample(self) -> None:
        for runner_id in ("m1-01", "m1-02", "m1-03"):
            self.add(Runner(runner_id=runner_id, image="macos-15-xcode-16"))
