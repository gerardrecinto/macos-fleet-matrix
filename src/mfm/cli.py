"""CLI for exercising fleet lifecycle operations without requiring a macOS host."""
from __future__ import annotations

import argparse
import json

from .inventory import Inventory


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mfm")
    sub = p.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory")
    inv_sub = inv.add_subparsers(dest="action", required=True)
    inv_sub.add_parser("sample")

    lease = sub.add_parser("lease")
    lease_sub = lease.add_subparsers(dest="action", required=True)
    acq = lease_sub.add_parser("acquire")
    acq.add_argument("--runner", required=True)
    acq.add_argument("--job", required=True)
    acq.add_argument("--ttl", type=int, default=1800)
    rel = lease_sub.add_parser("release")
    rel.add_argument("--runner", required=True)
    rel.add_argument("--job", required=True)
    rel.add_argument("--result", choices=("success", "failure", "cancelled"), required=True)
    return p


def main() -> int:
    args = build_parser().parse_args()
    inventory = Inventory()
    inventory.sample()

    if args.command == "inventory":
        print(json.dumps([r.__dict__ | {"state": r.state.value} for r in inventory.ready()], default=str, indent=2))
        return 0

    runner = inventory.get(args.runner)
    if args.action == "acquire":
        runner.lease(args.job, args.ttl)
        print(f"leased {runner.runner_id} to {args.job}")
    else:
        runner.release(args.job, args.result)
        print(f"draining {runner.runner_id} after {args.result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
