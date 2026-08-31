# Threat model

## Assets

- Apple Silicon host control plane
- macOS runner images
- CI workload credentials
- signing material
- source code and build artifacts
- fleet inventory and audit events

## Primary threats

| Threat | Control |
| --- | --- |
| Public PR executes malicious code | isolated ephemeral guest, least privilege, no host secrets |
| Runner persistence | one-job lease followed by destroy/rebuild |
| Image tampering | provenance verification and immutable digests |
| Credential exfiltration | short-lived identities, OIDC, no persistent secrets |
| Host compromise | network segmentation, host hardening, restricted management plane |
| Control-plane abuse | authenticated API, scoped identities, audit logs |
| Supply-chain compromise | pinned versions, checksums, SBOM/provenance, canary promotion |

## Trust boundaries

CI workload code is untrusted. The runner broker is trusted infrastructure. The host operating system and image-builder pipeline are higher-trust domains. No workload should cross those boundaries merely because it is running inside a macOS VM.

## Residual risk

macOS virtualization and CI signing workflows have platform-specific constraints. Production deployment must validate Apple virtualization entitlements, network isolation, code-signing requirements, and the exact Tart image lifecycle on the selected hardware.
