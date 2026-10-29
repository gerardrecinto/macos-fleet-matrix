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
        if not isinstance(doc, dict):
            raise ValueError("host health must be a JSON object")
        thermal = doc.get("thermalState", "unknown")
        if not isinstance(thermal, str) or thermal.lower() not in {
            *_THERMAL_RANK, *_REFUSED_THERMAL,
        }:
            raise ValueError("thermalState must be nominal, fair, serious, critical, or unknown")
        memory = doc.get("memory", {})
        if not isinstance(memory, dict):
            raise ValueError("memory must be a JSON object")
        counters = {}
        for name in ("swapUsedBytes", "swapTotalBytes"):
            value = memory.get(name, 0)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
            counters[name] = value
        if counters["swapUsedBytes"] > counters["swapTotalBytes"]:
            raise ValueError("swapUsedBytes cannot exceed swapTotalBytes")
        return cls(
            thermal_state=thermal.lower(),
            swap_used_bytes=counters["swapUsedBytes"],
            swap_total_bytes=counters["swapTotalBytes"],
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
