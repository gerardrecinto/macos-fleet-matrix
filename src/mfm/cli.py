"""CLI for exercising fleet lifecycle operations without requiring a macOS host."""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import reap
from .health import parse_health
from .inventory import Inventory


def default_state_path() -> str:
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, "mfm", "state.json")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mfm")
    p.add_argument(
        "--state",
        default=os.environ.get("MFM_STATE") or None,
        help="fleet state file shared between commands (default: $MFM_STATE, then the XDG state dir)",
    )
    sub = p.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory")
    inv_sub = inv.add_subparsers(dest="action", required=True)
    inv_sub.add_parser("sample", help="print a fresh sample fleet")
    inv_sub.add_parser("list", help="print every runner in the saved state, in any state")

    lease = sub.add_parser("lease")
    lease_sub = lease.add_subparsers(dest="action", required=True)
    acq = lease_sub.add_parser("acquire")
    acq.add_argument("--runner", help="lease this runner; omit to let the scheduler pick")
    acq.add_argument("--image", help="only consider runners with this image when picking")
    acq.add_argument(
        "--health",
        help="JSON file of {runner_id: HostHealthState} from the telemetry probe; "
        "hot or swapping hosts are skipped and the rest ranked coolest first",
    )
    acq.add_argument("--job", required=True)
    acq.add_argument("--ttl", type=int, default=1800)
    rel = lease_sub.add_parser("release")
    rel.add_argument("--runner", required=True)
    rel.add_argument("--job", required=True)
    rel.add_argument("--result", choices=("success", "failure", "cancelled"), required=True)

    reap = sub.add_parser("reap", help="run the Rust lease reaper over the saved fleet state")
    reap.add_argument("--reaper", help="path to the mfm-reaper binary (default: $MFM_REAPER, then PATH)")
    reap.add_argument("--interval", type=float, default=30, help="seconds between sweeps")
    reap.add_argument("--once", action="store_true", help="sweep once and exit")
    return p


def _dump(inventory: Inventory) -> None:
    print(json.dumps([r.to_dict() for r in inventory.all()], indent=2))


def run(args: argparse.Namespace) -> int:
    state = args.state or default_state_path()

    if args.command == "inventory":
        if args.action == "sample":
            inventory = Inventory()
            inventory.sample()
        else:
            inventory = Inventory.load(state)
        _dump(inventory)
        return 0

    if args.command == "reap":
        if args.interval <= 0:
            raise ValueError("interval must be positive")
        return reap.main_loop(state, args.reaper, args.interval, args.once)

    with Inventory.transaction(state) as inventory:
        _lease(inventory, args)
    return 0


def _lease(inventory: Inventory, args: argparse.Namespace) -> None:
    if args.action == "acquire":
        if args.runner and (args.image or args.health):
            raise ValueError("--runner cannot be combined with --image or --health")
        if args.runner:
            runner = inventory.get(args.runner)
        else:
            health = None
            if args.health:
                with open(args.health, encoding="utf-8") as handle:
                    health = parse_health(json.load(handle))
            runner = inventory.pick(args.image, health)
        runner.lease(args.job, args.ttl)
        print(f"leased {runner.runner_id} to {args.job}")
    else:
        runner = inventory.get(args.runner)
        runner.release(args.job, args.result)
        print(f"draining {runner.runner_id} after {args.result}")


def main() -> int:
    args = build_parser().parse_args()
    try:
        return run(args)
    except (ValueError, KeyError, OSError) as exc:
        message = exc.args[0] if isinstance(exc, KeyError) and exc.args else exc
        print(f"mfm: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
