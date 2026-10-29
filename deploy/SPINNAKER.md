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

## Pipelines in this repository

| File | Pipeline | What it does |
| --- | --- | --- |
| `deploy/spinnaker/control-plane-pipeline.json` | `deploy-control-plane` | Verify the signed control-plane image, deploy to staging, manual judgment, deploy to prod |
| `deploy/spinnaker/promote-macos-image-pipeline.json` | `promote-macos-image` | `build -> canary -> green -> blue/green` for a runner image digest |
| `deploy/spinnaker/rollback-macos-image-pipeline.json` | `rollback-macos-image` | Point the fleet back at the last known-good digest |

The image pipelines use `webhook` stages that POST to the `promotionApiUrl` parameter, with the action named in the payload. Spinnaker has no stage that drives Tart, and this repository ships no promotion service, so that endpoint is yours to provide. The webhook stages succeed when the endpoint returns a 2xx status, so the endpoint must answer only after the action has finished, or you add Spinnaker's webhook polling fields. The canary stage lists the six checks above in its payload and sets `failPipeline`, so any failure stops the run before `green` and `blue-green`. The Packer image build itself is not part of these pipelines.

## Validate

```bash
mfm pipeline validate deploy/spinnaker/*.json
```

It checks required fields, unique `refId`s, that every `requisiteStageRefIds` entry names a stage, that there are no cycles, that stage types are in a curated list of core Spinnaker types, that each `${parameters.x}` names a defined parameter, and that the gates above exist and sit in front of what they protect. CI runs it on every push. Exit code 1 means a file is invalid.

This is a structural check only. These pipelines have not been saved to or run on a live Spinnaker, and the webhook field names come from memory of Spinnaker's schema, not from a server that accepted them.

## Apply

Needs the `spin` CLI configured against your Spinnaker (`spin` is not installed by this repository). The application must exist first.

```bash
spin application save \
  --application-name macosfleetmatrix \
  --owner-email you@example.com \
  --cloud-providers kubernetes

spin pipeline save --file deploy/spinnaker/control-plane-pipeline.json
spin pipeline save --file deploy/spinnaker/promote-macos-image-pipeline.json
spin pipeline save --file deploy/spinnaker/rollback-macos-image-pipeline.json
```

Both commands and their flags (`--file`, `--application-name`, `--owner-email`, `--cloud-providers`) were read from the `spin` source. If Spinnaker rejects a file, fix the JSON and add the lesson to `mfm pipeline validate`.

