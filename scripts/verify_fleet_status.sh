#!/usr/bin/env bash
# Deploys services/fleet-status to a throwaway kind cluster and checks it, including a bad rollout.
# Needs docker, kind and kubectl. Takes about three minutes the first time. Deletes the cluster at the end.
set -euo pipefail
cd "$(dirname "$0")/.."
IMG=ghcr.io/gerardrecinto/fleet-status:0.1.0
cleanup() { pkill -f "port-forward svc/fleet-status" 2>/dev/null || true; kind delete cluster --name fleet-verify >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker build -q -t "$IMG" services/fleet-status >/dev/null
kind create cluster --name fleet-verify >/dev/null 2>&1
kind load docker-image "$IMG" --name fleet-verify >/dev/null
kubectl apply -k deploy/k8s/fleet-status/base >/dev/null
kubectl -n fleet-status rollout status deploy/fleet-status --timeout=180s
kubectl -n fleet-status port-forward svc/fleet-status 18080:80 >/dev/null 2>&1 &
sleep 4
echo "summary: $(curl -fs localhost:18080/api/summary)"

kubectl -n fleet-status set image deploy/fleet-status fleet-status="${IMG%:*}:does-not-exist" >/dev/null
sleep 25
echo "pods during bad rollout:"; kubectl -n fleet-status get pods --no-headers | awk '{print "  "$1,$2,$3}'
code=$(curl -s -o /dev/null -w '%{http_code}' localhost:18080/api/summary)
echo "api during bad rollout: HTTP $code"
[ "$code" = 200 ]
kubectl -n fleet-status rollout undo deploy/fleet-status >/dev/null
kubectl -n fleet-status rollout status deploy/fleet-status --timeout=120s
echo "OK"
