# Contributing

## Dev setup

Requires Python 3.11+. Rust (stable) and Swift 5.9+ on macOS are needed only for those parts.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## Tests

```bash
ruff check .
pytest
mfm pipeline validate deploy/spinnaker/*.json
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

1. Run `tests/test_tart_e2e.py` on a Mac with real Tart (`MFM_TART_E2E=1`) and report what happens.
2. A launchd unit (and a systemd unit) that runs `mfm reap` on a host.
3. A collector that runs the Swift probe on each host and writes the `--health` file.
4. Serve `mfm metrics` over HTTP, or add the host probe values to it.
5. A real Packer template for the image contract in `packer/IMAGE-PIPELINE.md`.
6. Save the pipelines in `deploy/spinnaker/` to a real Spinnaker with `spin pipeline save` and report what it rejects.
