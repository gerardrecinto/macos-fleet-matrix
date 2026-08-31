# Spinnaker promotion contract

The image pipeline should publish a versioned image manifest containing:

- image name and content digest
- macOS version
- Xcode version
- runner bootstrap version
- SBOM/provenance reference
- smoke-test results

Spinnaker should promote the manifest through:

`build -> canary -> green -> blue/green`

A canary gate should require successful runner boot, registration, lease acquisition, a representative Xcode build, telemetry health, and clean teardown. Promotion is blocked on any failed gate. Rollback points to the last known-good immutable digest.
