"""Execute the README quick start from a fresh clone of the current checkout.

Redirect only Git's documented HTTPS clone URL to this local checkout, so CI
validates the proposed commit before it is merged. The README shell commands
otherwise run unchanged. Temporary XDG and MFM state directories isolate user data.
"""
from pathlib import Path
import os
import subprocess
import tempfile


repo = Path(__file__).resolve().parents[1]
readme = (repo / "README.md").read_text()
section = readme.split("## Try it in 60 seconds\n", 1)[1]
commands = section.split("```bash\n", 1)[1].split("```", 1)[0]
with tempfile.TemporaryDirectory(prefix="mfm-quickstart-") as directory:
    root = Path(directory)
    env = os.environ.copy()
    env.pop("MFM_STATE", None)
    env.pop("XDG_STATE_HOME", None)
    env.pop("PYTHONPATH", None)
    env.pop("VIRTUAL_ENV", None)
    env.update({
        "XDG_STATE_HOME": str(root / "state"),
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": f"url.{repo.as_uri()}.insteadOf",
        "GIT_CONFIG_VALUE_0": "https://github.com/gerardrecinto/macos-fleet-matrix",
    })
    # Verify this commit, including local changes, rather than the remote default.
    subprocess.run(["git", "clone", "--quiet", str(repo), str(root / "snapshot")], check=True)
    snapshot = root / "snapshot"
    for path in subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=repo
    ).decode().split("\0"):
        if path and (repo / path).is_file():
            target = snapshot / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((repo / path).read_bytes())
    env["GIT_CONFIG_KEY_0"] = f"url.{snapshot.as_uri()}.insteadOf"
    subprocess.run(["git", "add", "-A"], cwd=snapshot, check=True)
    subprocess.run([
        "git", "-c", "user.name=Quickstart check", "-c", "user.email=check@localhost",
        "commit", "--quiet", "--allow-empty", "-m", "Quickstart snapshot",
    ], cwd=snapshot, check=True)
    script = commands + '''
python - <<'CHECK'
import json
from pathlib import Path
import os
state = json.loads(Path(os.environ["MFM_STATE"]).read_text())
assert len(state) == 3, state
runner = next(r for r in state if r["runner_id"] == "m1-01")
assert runner["state"] == "draining", runner
assert runner["job_id"] is None, runner
assert not (Path(os.environ["XDG_STATE_HOME"]) / "mfm/state.json").exists()
print("Quickstart verified: isolated install, three runners, released lease, untouched default state")
CHECK
'''
    subprocess.run(["bash", "-euo", "pipefail", "-c", script], cwd=root, env=env, check=True)
