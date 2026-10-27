"""Host-health gating for runner selection.

Reads the JSON the Swift telemetry probe emits (`HostHealthState`) and turns it into an
eligibility decision and a sort key, so the scheduler can skip hot or swapping hosts.
"""
from __future__ import annotations

from dataclasses import dataclass

# Lower is better. A host with no telemetry ranks after every host that reported one.
_THERMAL_RANK = {"nominal": 0, "fair": 1, "unknown": 2}
_REFUSED_THERMAL = {"serious", "critical"}
NO_TELEMETRY_RANK = 3

# Swap in use above this share of the swap file means the host is already paging.
MAX_SWAP_USED_RATIO = 0.5


@dataclass(frozen=True)
class HostHealth:
    thermal_state: str
    swap_used_bytes: int
    swap_total_bytes: int

    @classmethod
    def from_probe(cls, doc: dict) -> HostHealth:
        thermal = str(doc.get("thermalState", "unknown")).lower()
        memory = doc.get("memory") or {}
        return cls(
            thermal_state=thermal,
            swap_used_bytes=int(memory.get("swapUsedBytes", 0)),
            swap_total_bytes=int(memory.get("swapTotalBytes", 0)),
        )

    def refusal(self) -> str | None:
        """Why this host should not take a new job, or None if it is fit."""
        if self.thermal_state in _REFUSED_THERMAL:
            return f"thermal state {self.thermal_state}"
        if self.swap_total_bytes and self.swap_used_bytes / self.swap_total_bytes > MAX_SWAP_USED_RATIO:
            pct = 100 * self.swap_used_bytes // self.swap_total_bytes
            return f"swap {pct}% used"
        return None

    def sort_key(self) -> tuple[int, int]:
        return (_THERMAL_RANK.get(self.thermal_state, 2), self.swap_used_bytes)


def parse_health(doc: dict) -> dict[str, HostHealth]:
    """`{runner_id: HostHealthState JSON}` -> `{runner_id: HostHealth}`."""
    if not isinstance(doc, dict):
        raise ValueError("health file must be a JSON object keyed by runner id")
    return {runner_id: HostHealth.from_probe(entry) for runner_id, entry in doc.items()}
