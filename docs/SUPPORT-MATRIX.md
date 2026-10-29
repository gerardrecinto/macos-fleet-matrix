# Support matrix

This lists only what the repository states. Nothing here has been run on a real Apple Silicon fleet, so "tested" means exercised by CI or the test suite, not by a production workload.

| Item | Value | Status |
| --- | --- | --- |
| macOS image version | 15 (default of `macos_version` in `terraform/variables.tf`; sample runners use `macos-15-xcode-16`) | Label only. No image is built or booted. |
| Xcode image version | 16 (default of `xcode_version` in `terraform/variables.tf`) | Label only. No image is built or booted. |
| macOS for the Swift telemetry probe | 13 and later (`.macOS(.v13)` in `Package.swift`), Swift 5.9+ | Built and tested on `macos-14` in CI once the `macos` job in `.github/workflows/ci.yml` has run. Other macOS versions untested. |
| Hardware | Apple Silicon (arm64). The probe notes that an Intel-only thermal sysctl does not exist on M-series. | No specific chip or model is tested. Intel is untested. |
| Tart | No version is pinned anywhere in the repository. | Untested. There is no Tart adapter yet. |
| Python | 3.11 and later; CI uses 3.12 | Tested in CI on Linux, and on `macos-14` once that job has run. |
| Rust | 1.75 and later, stable channel | Tested in CI on Linux. |
| Control-plane container | Linux only, no macOS virtualization | Built and smoke-tested in CI. |

If you run this on a combination not listed as tested, please open an issue with what you used and what happened.
