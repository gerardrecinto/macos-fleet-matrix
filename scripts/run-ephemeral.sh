#!/usr/bin/env bash
set -euo pipefail

# Run on an Apple Silicon host. The script is deliberately explicit so a
# production deployment can add the exact Tart image lifecycle it approves.
command -v tart >/dev/null || { echo 'tart is required'; exit 1; }

IMAGE="${MFM_IMAGE:-macos-15-xcode-16}"
RUNNER="${MFM_RUNNER_ID:?set MFM_RUNNER_ID}"

echo "Starting ephemeral runner ${RUNNER} from ${IMAGE}"
tart run "${IMAGE}" --no-graphics --dir "${RUNNER}" &
vm_pid=$!
trap 'kill "${vm_pid}" 2>/dev/null || true' EXIT
wait "${vm_pid}"
