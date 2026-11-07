"""Domain model for the runner lifecycle."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from time import time


class RunnerState(StrEnum):
    READY = "ready"
    LEASED = "leased"
    DRAINING = "draining"
    QUARANTINED = "quarantined"
    DESTROYED = "destroyed"


@dataclass
class Runner:
    runner_id: str
    image: str
    arch: str = "arm64"
    state: RunnerState = RunnerState.READY
    job_id: str | None = None
    lease_expires_at: float | None = None
    # Set only when a real VM backs the runner (Tart backend); None in simulation.
    vm_name: str | None = None
    vm_ip: str | None = None

    def lease(self, job_id: str, ttl_seconds: int = 1800) -> None:
        if self.state is not RunnerState.READY:
            raise ValueError(f"runner {self.runner_id} is not ready")
        if not job_id:
            raise ValueError("job_id is required")
        if ttl_seconds <= 0:
            raise ValueError("ttl must be positive")
        self.state = RunnerState.LEASED
        self.job_id = job_id
        self.lease_expires_at = time() + ttl_seconds

    def abort_lease(self) -> None:
        """Undo a lease whose VM never came up, so the runner can take another job."""
        self.state = RunnerState.READY
        self.job_id = None
        self.lease_expires_at = None

    def release(self, job_id: str, result: str) -> None:
        if self.state is not RunnerState.LEASED:
            raise ValueError(f"runner {self.runner_id} has no active lease")
        if self.job_id != job_id:
            raise ValueError("lease does not belong to job")
        if result not in {"success", "failure", "cancelled"}:
            raise ValueError("invalid job result")
        self.state = RunnerState.DRAINING
        self.job_id = None
        self.lease_expires_at = None

    @classmethod
    def from_dict(cls, doc: dict) -> Runner:
        return cls(
            runner_id=doc["runner_id"],
            image=doc["image"],
            arch=doc.get("arch", "arm64"),
            state=RunnerState(doc.get("state", "ready")),
            job_id=doc.get("job_id"),
            lease_expires_at=doc.get("lease_expires_at"),
            vm_name=doc.get("vm_name"),
            vm_ip=doc.get("vm_ip"),
        )

    def to_dict(self) -> dict:
        return {
            "runner_id": self.runner_id,
            "image": self.image,
            "arch": self.arch,
            "state": self.state.value,
            "job_id": self.job_id,
            "lease_expires_at": self.lease_expires_at,
            "vm_name": self.vm_name,
            "vm_ip": self.vm_ip,
        }

    def quarantine(self) -> None:
        self.state = RunnerState.QUARANTINED
        self.job_id = None
        self.lease_expires_at = None
