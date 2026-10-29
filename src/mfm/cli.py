"""CLI for exercising fleet lifecycle operations without requiring a macOS host."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from . import __version__, pipeline, reap
from .health import parse_health
from .inventory import Inventory
from .model import Runner, RunnerState
from .tart import (
    DEFAULT_BOOT_WAIT,
    Tart,
    TartCleanupError,
    TartError,
    find_tart,
    log_dir_for,
    vm_name_for,
)


def default_state_path() -> str:
    base = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return os.path.join(base, "mfm", "state.json")


def _positive_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {raw}") from None
    if value <= 0:
        raise argparse.ArgumentTypeError("ttl must be positive")
    return value


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mfm")
    p.add_argument("--version", action="version", version=f"mfm {__version__}")
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
    acq.add_argument("--ttl", type=_positive_int, default=1800)
    acq.add_argument(
        "--backend",
        choices=("simulation", "tart"),
        default="simulation",
        help="simulation only records state (default); tart clones, boots and waits for a real VM",
    )
    acq.add_argument("--dry-run", action="store_true",
                     help="with --backend tart: print the tart commands and change nothing")
    acq.add_argument("--pull", action="store_true",
                     help="with --backend tart: run `tart pull` on the runner image first")
    acq.add_argument("--boot-timeout", type=_positive_int, default=DEFAULT_BOOT_WAIT,
                     help="with --backend tart: seconds to wait for the VM to get an IP")
    acq.add_argument("--json", action="store_true", help="print the leased runner as JSON")
    rel = lease_sub.add_parser("release")
    rel.add_argument("--runner", required=True)
    rel.add_argument("--job", required=True)
    rel.add_argument("--result", choices=("success", "failure", "cancelled"), required=True)
    rel.add_argument("--dry-run", action="store_true",
                     help="print the tart stop and delete commands for the runner's VM and change nothing")
    rel.add_argument("--json", action="store_true", help="print the released runner as JSON")

    pipe = sub.add_parser("pipeline", help="check Spinnaker pipeline JSON without a Spinnaker server")
    pipe_sub = pipe.add_subparsers(dest="action", required=True)
    val = pipe_sub.add_parser("validate", help="structure, stage types, gates; exits 1 if any file is invalid")
    val.add_argument("files", nargs="+", metavar="FILE")

    sub.add_parser("metrics", help="print fleet metrics in Prometheus text format")

    reap = sub.add_parser("reap", help="run the Rust lease reaper over the saved fleet state")
    reap.add_argument("--reaper", help="path to the mfm-reaper binary (default: $MFM_REAPER, then PATH)")
    reap.add_argument("--interval", type=float, default=30, help="seconds between sweeps")
    reap.add_argument("--once", action="store_true", help="sweep once and exit")
    return p


def _dump(inventory: Inventory) -> None:
    print(json.dumps([r.to_dict() for r in inventory.all()], indent=2))


def render_metrics(inventory: Inventory, now: float) -> str:
    runners = inventory.all()
    lines = [
        "# HELP mfm_runners Runners in the saved fleet state, by lifecycle state.",
        "# TYPE mfm_runners gauge",
    ]
    for state in RunnerState:
        count = sum(1 for r in runners if r.state is state)
        lines.append(f'mfm_runners{{state="{state.value}"}} {count}')
    lines += [
        "# HELP mfm_lease_seconds_until_expiry Seconds until a leased runner's lease expires; negative once overdue.",
        "# TYPE mfm_lease_seconds_until_expiry gauge",
    ]
    for r in runners:
        if r.state is RunnerState.LEASED and r.lease_expires_at is not None:
            lines.append(
                f'mfm_lease_seconds_until_expiry{{runner="{r.runner_id}"}} {r.lease_expires_at - now:.0f}'
            )
    return "\n".join(lines) + "\n"


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

    if args.command == "pipeline":
        return pipeline.main(args.files)

    if args.command == "metrics":
        print(render_metrics(Inventory.load(state), time.time()), end="")
        return 0

    if args.command == "reap":
        if args.interval <= 0:
            raise ValueError("interval must be positive")
        return reap.main_loop(state, args.reaper, args.interval, args.once)

    if getattr(args, "dry_run", False):
        # Read-only: load without taking the write path, then print the plan.
        _lease_dry_run(Inventory.load(state), args)
        return 0

    with Inventory.transaction(state) as inventory:
        # A failed VM operation is reported after the transaction saves, so the
        # quarantine and the recorded VM name are not lost.
        return _lease(inventory, args, state)


def _pick(inventory: Inventory, args: argparse.Namespace) -> Runner:
    if args.runner and (args.image or args.health):
        raise ValueError("--runner cannot be combined with --image or --health")
    if args.runner:
        return inventory.get(args.runner)
    health = None
    if args.health:
        with open(args.health, encoding="utf-8") as handle:
            health = parse_health(json.load(handle))
    return inventory.pick(args.image, health)


def _lease_dry_run(inventory: Inventory, args: argparse.Namespace) -> None:
    tart = Tart()
    if args.action == "acquire":
        if args.backend != "tart":
            raise ValueError("--dry-run needs --backend tart")
        runner = _pick(inventory, args)
        name = vm_name_for(runner.runner_id, args.job)
        plan = tart.plan_acquire(runner.image, name, args.boot_timeout, args.pull)
    else:
        runner = inventory.get(args.runner)
        if not runner.vm_name:
            print(f"dry run: {runner.runner_id} has no recorded tart VM, nothing to run")
            return
        plan = tart.plan_release(runner.vm_name)
    for argv in plan:
        print(tart.render(argv))
    print("dry run: nothing was executed and no state was changed")


def _lease(inventory: Inventory, args: argparse.Namespace, state: str) -> int:
    if args.action == "acquire":
        if args.backend != "tart" and (args.pull or args.boot_timeout != DEFAULT_BOOT_WAIT):
            raise ValueError("--pull and --boot-timeout need --backend tart")
        tart = Tart(find_tart(), log_dir=log_dir_for(state)) if args.backend == "tart" else None
        runner = _pick(inventory, args)
        runner.lease(args.job, args.ttl)
        if tart:
            name = vm_name_for(runner.runner_id, args.job)
            try:
                runner.vm_ip = tart.acquire(runner.image, name, args.boot_timeout, args.pull)
                runner.vm_name = name
            except TartCleanupError as exc:
                runner.quarantine()
                runner.vm_name = name
                print(f"mfm: {runner.runner_id} quarantined, VM {name} may remain: {exc}", file=sys.stderr)
                return 2
            except TartError as exc:
                runner.abort_lease()
                print(f"mfm: {exc}", file=sys.stderr)
                return 2
        if args.json:
            print(json.dumps(runner.to_dict(), indent=2))
        elif runner.vm_name:
            print(f"leased {runner.runner_id} to {args.job} (vm {runner.vm_name}, ip {runner.vm_ip})")
        else:
            print(f"leased {runner.runner_id} to {args.job}")
    else:
        runner = inventory.get(args.runner)
        runner.release(args.job, args.result)
        if runner.vm_name:
            try:
                Tart(find_tart(), log_dir=log_dir_for(state)).teardown(runner.vm_name)
            except TartError as exc:
                runner.quarantine()
                print(f"mfm: {runner.runner_id} quarantined, VM {runner.vm_name} not removed: {exc}",
                      file=sys.stderr)
                return 2
            runner.vm_name = None
            runner.vm_ip = None
        if args.json:
            print(json.dumps(runner.to_dict(), indent=2))
        else:
            print(f"draining {runner.runner_id} after {args.result}")
    return 0


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
