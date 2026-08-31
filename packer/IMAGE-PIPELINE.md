# Image pipeline contract

Packer does not magically provision macOS on every host. The real build must run on a supported Apple Silicon build host and use an approved macOS base artifact.

The pipeline should:

1. Verify the pinned macOS and Xcode versions.
2. Create a temporary VM from the approved base image.
3. Install Xcode and command-line tools with checksums or vendor provenance.
4. Install only the runner dependencies required by the fleet.
5. Run smoke tests: `xcodebuild -version`, `swift --version`, network policy checks, and telemetry startup.
6. Remove temporary credentials and caches that must not persist.
7. Shut down and seal the image.
8. Produce a content-addressed image manifest.

This file is a contract rather than a fake Packer builder. Provider-specific Packer builders should be added only after the exact Tart/macOS build environment is selected and validated.
