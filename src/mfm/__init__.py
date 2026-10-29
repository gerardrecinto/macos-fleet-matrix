"""macOS Fleet Matrix reference control plane."""

from importlib.metadata import PackageNotFoundError, version

from .inventory import Inventory
from .model import Runner, RunnerState

try:
    __version__ = version("macos-fleet-matrix")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = ["Inventory", "Runner", "RunnerState", "__version__"]
