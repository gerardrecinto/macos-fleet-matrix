# Security policy

## Reporting a vulnerability

Email gerardrecinto@gmail.com with the details and, if you can, steps to reproduce. Please do not open a public issue for a vulnerability.

You should get a reply within a week. This is a reference project maintained by one person, so there is no bug bounty and no fixed fix timeline, but reports are read and taken seriously.

## Scope

This repository holds no credentials, signing keys or production endpoints. The assumptions the design makes about untrusted pull requests, runner identity and the management network are in [`docs/THREAT-MODEL.md`](docs/THREAT-MODEL.md). Reports that the Terraform, Kubernetes manifests, container image or release workflow weaken those assumptions are in scope.

## Supported versions

Only the latest release and `main`.
