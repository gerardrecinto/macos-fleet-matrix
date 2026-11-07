"""Tart adapter: boot and destroy ephemeral macOS VMs behind the lease commands.

Every Tart call goes through an injectable runner, so the logic is testable without Tart.
The subcommands and flags used here were checked against the Tart quick start and the
Tart source (Commands/IP.swift, Stop.swift, List.swift, Run.swift, Delete.swift):

    tart list --source local --quiet
    tart pull <image>
    tart clone <image> <name>
    tart run <name> --no-graphics        (blocks while the VM runs, so it is spawned)
    tart ip <name> --wait <seconds>
    tart stop <name>                     (graceful, then forced after its own timeout)
    tart delete <name>

Apple's macOS license limits how many macOS VMs may run at once on Apple-branded
hardware. This adapter does not enforce or check that limit. Check Apple's software
license agreement before sizing a fleet.
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from collections.abc import Callable

INSTALL_HINT = "brew install cirruslabs/cli/tart"

DEFAULT_BOOT_WAIT = 120
CLONE_TIMEOUT = 1800  # an image that is not local is pulled first and can be large
STOP_TIMEOUT = 120
DELETE_TIMEOUT = 120
LIST_TIMEOUT = 30
IP_MARGIN = 15  # extra seconds past `tart ip --wait` before we give up on the process

Runner = Callable[[list[str], float], "subprocess.CompletedProcess[str]"]
Spawner = Callable[[list[str], str | None], "subprocess.Popen[bytes]"]


class TartError(ValueError):
    """A Tart operation failed. ValueError so the CLI reports it and exits 2."""


class TartMissing(TartError):
    def __init__(self) -> None:
        super().__init__(f"tart not found on PATH. Install it with: {INSTALL_HINT}")


class TartCleanupError(TartError):
    """The VM could not be torn down and may still exist on the host."""


def vm_name_for(runner_id: str, job_id: str) -> str:
    """A VM name that is unique per runner and job and safe as a path component."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{runner_id}-{job_id}").strip("-.")
    return f"mfm-{safe}"[:80]


def default_runner(argv: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)


def default_spawner(argv: list[str], log_path: str | None) -> subprocess.Popen[bytes]:
    """Start a long-running command detached, so it outlives the CLI process."""
    log = open(log_path, "ab") if log_path else subprocess.DEVNULL
    try:
        return subprocess.Popen(
            argv, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True
        )
    finally:
        if log_path:
            log.close()


def log_dir_for(state_path: str) -> str:
    """Where `tart run` output goes, next to the fleet state file."""
    return os.path.join(os.path.dirname(os.path.abspath(state_path)), "tart-logs")


def find_tart(explicit: str | None = None) -> str:
    candidate = explicit or os.environ.get("MFM_TART") or "tart"
    found = shutil.which(candidate)
    if not found:
        raise TartMissing()
    return found


class Tart:
    def __init__(
        self,
        binary: str = "tart",
        runner: Runner = default_runner,
        spawner: Spawner = default_spawner,
        log_dir: str | None = None,
        ip_margin: float = IP_MARGIN,
    ) -> None:
        self.binary = binary
        self._run = runner
        self._spawn = spawner
        self.log_dir = log_dir
        self.ip_margin = ip_margin

    # Command construction. Pure, shared by the real path and --dry-run.

    def cmd_list(self) -> list[str]:
        return [self.binary, "list", "--source", "local", "--quiet"]

    def cmd_pull(self, image: str) -> list[str]:
        return [self.binary, "pull", image]

    def cmd_clone(self, image: str, name: str) -> list[str]:
        return [self.binary, "clone", image, name]

    def cmd_run(self, name: str) -> list[str]:
        return [self.binary, "run", name, "--no-graphics"]

    def cmd_ip(self, name: str, wait: int) -> list[str]:
        return [self.binary, "ip", name, "--wait", str(wait)]

    def cmd_stop(self, name: str) -> list[str]:
        return [self.binary, "stop", name]

    def cmd_delete(self, name: str) -> list[str]:
        return [self.binary, "delete", name]

    def plan_acquire(self, image: str, name: str, wait: int, pull: bool) -> list[list[str]]:
        plan = [self.cmd_pull(image)] if pull else []
        return plan + [self.cmd_clone(image, name), self.cmd_run(name), self.cmd_ip(name, wait)]

    def plan_release(self, name: str) -> list[list[str]]:
        return [self.cmd_stop(name), self.cmd_delete(name)]

    @staticmethod
    def render(argv: list[str]) -> str:
        return shlex.join(argv)

    # Execution.

    def _exec(self, argv: list[str], timeout: float) -> str:
        label = f"tart {argv[1]}"
        try:
            proc = self._run(argv, timeout)
        except subprocess.TimeoutExpired:
            raise TartError(f"{label} timed out after {timeout:.0f}s") from None
        except FileNotFoundError:
            raise TartMissing() from None
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise TartError(f"{label} failed ({proc.returncode}): {detail or 'no output'}")
        return proc.stdout

    def list_names(self) -> list[str]:
        return [n for n in self._exec(self.cmd_list(), LIST_TIMEOUT).splitlines() if n.strip()]

    def exists(self, name: str) -> bool:
        return name in (n.strip() for n in self.list_names())

    def pull(self, image: str) -> None:
        self._exec(self.cmd_pull(image), CLONE_TIMEOUT)

    def _log_path(self, name: str) -> str | None:
        if not self.log_dir:
            return None
        os.makedirs(self.log_dir, exist_ok=True)
        return os.path.join(self.log_dir, f"{name}.log")

    def _log_tail(self, path: str | None) -> str:
        if not path or not os.path.exists(path):
            return ""
        with open(path, encoding="utf-8", errors="replace") as handle:
            lines = handle.read().strip().splitlines()
        return " | ".join(lines[-3:])

    def acquire(self, image: str, name: str, wait: int = DEFAULT_BOOT_WAIT, pull: bool = False) -> str:
        """Clone, boot headless and wait for an IP. Returns the IP.

        On any failure after the clone is attempted, the half-started VM is stopped and
        deleted. If that cleanup also fails, TartCleanupError says the VM may remain.
        """
        if self.exists(name):
            raise TartError(f"a tart VM named {name} already exists; delete it or use another job id")
        if pull:
            self.pull(image)
        log_path = self._log_path(name)
        try:
            self._exec(self.cmd_clone(image, name), CLONE_TIMEOUT)
            self._spawn(self.cmd_run(name), log_path)
            ip = self._exec(self.cmd_ip(name, wait), wait + self.ip_margin).strip()
            if not ip:
                raise TartError(f"tart ip returned no address for {name}")
            return ip
        except TartError as exc:
            tail = self._log_tail(log_path)
            try:
                self._cleanup(name)
            except TartError as cleanup_exc:
                raise TartCleanupError(f"{exc}; cleanup also failed: {cleanup_exc}") from exc
            raise TartError(f"{exc}{f' (tart run log: {tail})' if tail else ''}") from exc

    def _cleanup(self, name: str) -> None:
        if self.exists(name):
            self.teardown(name)
        self._remove_log(name)

    def teardown(self, name: str) -> None:
        """Stop then delete. A failed stop is tolerated only if the delete then succeeds,
        since a VM that already exited cannot be stopped but still has to be deleted."""
        stop_error: TartError | None = None
        try:
            self._exec(self.cmd_stop(name), STOP_TIMEOUT)
        except TartMissing:
            raise
        except TartError as exc:
            stop_error = exc
        try:
            self._exec(self.cmd_delete(name), DELETE_TIMEOUT)
        except TartMissing:
            raise
        except TartError as exc:
            if not self.exists(name):
                self._remove_log(name)
                return
            detail = f"{stop_error}; {exc}" if stop_error else str(exc)
            raise TartError(f"could not tear down {name}: {detail}") from exc
        self._remove_log(name)

    def _remove_log(self, name: str) -> None:
        if self.log_dir:
            try:
                os.unlink(os.path.join(self.log_dir, f"{name}.log"))
            except FileNotFoundError:
                pass
