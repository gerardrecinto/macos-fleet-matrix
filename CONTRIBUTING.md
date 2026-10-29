# Contributing

## Dev setup

Requires Python 3.11+. Rust (stable) and Swift 5.9+ on macOS are needed only for those parts.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## Tests

```bash
ruff check .
pytest
cd src/mfm/Reaper && cargo fmt -- --check && cargo clippy --all-targets -- -D warnings && cargo test
swift test   # macOS only
```

To run the Python test that feeds real `mfm` state into the Rust reaper, build `mfm-reaper` and point `MFM_REAPER` at it:

```bash
cargo build --release --manifest-path src/mfm/Reaper/Cargo.toml
MFM_REAPER="$PWD/src/mfm/Reaper/target/release/mfm-reaper" pytest tests/test_reap.py
```

`make ci` runs the full local set, including the Terraform, Kubernetes and Trivy checks, so it needs those tools installed.

Keep the README honest: if something is design only, say so in the status table.

## Starter ideas

These come from the README roadmap.

1. A Tart adapter that boots and destroys a real VM behind the existing lease commands.
2. A launchd unit (and a systemd unit) that runs `mfm reap` on a host.
3. A collector that runs the Swift probe on each host and writes the `--health` file.
4. Serve `mfm metrics` over HTTP, or add the host probe values to it.
5. A real Packer template for the image contract in `packer/IMAGE-PIPELINE.md`.

The `quickstart` CI jobs execute the README quick start in an isolated clone and virtual environment on Linux and macOS. Run the same check locally with `python3 scripts/check_quickstart.py`.

## Site behavior checks

The site loads Python only after an explicit demo start. These browser tests use the real pinned Pyodide CDN runtime, not a substitute lease engine, so the activation cases need an internet connection.

```bash
npm ci --ignore-scripts
npx playwright install chromium firefox webkit
npm run test:site
SITE_BROWSER=firefox npm run test:site
SITE_BROWSER=webkit npm run test:site
```

CI runs all three engines. It checks desktop/mobile navigation without Python downloads, keyboard activation, real acquire/release and duplicate-lease rejection, blocked-network retry, and the JavaScript-disabled local fallback.
