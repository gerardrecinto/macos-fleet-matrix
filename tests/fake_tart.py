"""A stand-in `tart` for tests. Not shipped, not a Tart emulator.

It accepts only the argument shapes the adapter is supposed to send, records every call
as one JSON line in $FAKE_TART_LOG, and keeps a tiny VM table under $FAKE_TART_HOME.
$FAKE_TART_FAIL is a comma list of subcommands that exit 1. $FAKE_TART_SLEEP_IP delays
`ip`. `ip --wait` polls for the VM like the real one. Like real Tart, deleting a running VM fails.
"""
import json
import os
import sys
import time

home = os.environ["FAKE_TART_HOME"]
fail = os.environ.get("FAKE_TART_FAIL", "").split(",")
argv = sys.argv[1:]
with open(os.environ["FAKE_TART_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(argv) + "\n")


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def vm(name):
    return os.path.join(home, "vms", name)


def running(name):
    return os.path.join(home, "running", name)


for sub in ("vms", "running"):
    os.makedirs(os.path.join(home, sub), exist_ok=True)

cmd = argv[0] if argv else ""
if cmd in fail:
    die(f"fake tart: {cmd} failed on purpose")

if cmd == "list":
    if argv[1:] != ["--source", "local", "--quiet"]:
        die(f"unexpected list args: {argv[1:]}", 64)
    print("\n".join(sorted(os.listdir(os.path.join(home, "vms")))))
elif cmd == "pull":
    if len(argv) != 2:
        die("usage: tart pull <image>", 64)
elif cmd == "clone":
    if len(argv) != 3:
        die("usage: tart clone <image> <name>", 64)
    if os.path.exists(vm(argv[2])):
        die(f"VM {argv[2]} already exists")
    open(vm(argv[2]), "w").write(argv[1])
elif cmd == "run":
    if argv[2:] != ["--no-graphics"] or not os.path.exists(vm(argv[1])):
        die("bad run", 64)
    open(running(argv[1]), "w").close()
elif cmd == "ip":
    if argv[2] != "--wait" or not argv[3].isdigit():
        die("bad ip args", 64)
    time.sleep(float(os.environ.get("FAKE_TART_SLEEP_IP", "0")))
    # Like `tart ip --wait`: a VM that is still booting gets up to N seconds to appear.
    deadline = time.time() + min(int(argv[3]), 5)
    while not os.path.exists(running(argv[1])) and time.time() < deadline:
        time.sleep(0.05)
    if not os.path.exists(running(argv[1])):
        die("no IP address found, is your VM running?")
    print("192.168.64.7")
elif cmd == "stop":
    if len(argv) != 2 or not os.path.exists(running(argv[1])):
        die("VM is not running")
    os.unlink(running(argv[1]))
elif cmd == "delete":
    if len(argv) != 2 or not os.path.exists(vm(argv[1])):
        die("no such VM")
    if os.path.exists(running(argv[1])):
        die("VM is running")
    os.unlink(vm(argv[1]))
else:
    die(f"unknown command {cmd}", 64)
