#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="assessment"
NAMESPACE="assessment"

# ── 1. Cluster Setup (1 Server + 3 Agents) ──────────────────────────────────
if k3d cluster list | grep -q "^${CLUSTER_NAME}"; then
  k3d cluster delete "${CLUSTER_NAME}"
fi

# Mapping VM port 8000 to Kubernetes NodePort 30000
k3d cluster create "${CLUSTER_NAME}" \
  --agents 3 \
  --port "8000:30000@agent:0" \
  --port "80:80@loadbalancer"

kubectl config use-context "k3d-${CLUSTER_NAME}"

# ── 2. Build & Import ────────────────────────────────────────────────────────
docker build -t "assessment/app-python:latest" ./app-python/
docker build -t "assessment/worker:latest" ./worker/
k3d image import "assessment/app-python:latest" "assessment/worker:latest" --cluster "${CLUSTER_NAME}"

# ── 3. Apply Manifests ───────────────────────────────────────────────────────
kubectl apply -f k8s/base/namespace.yaml
kubectl apply -f k8s/mongodb/
kubectl apply -f k8s/redis/
kubectl rollout status deployment/mongo -n "${NAMESPACE}" --timeout=120s

kubectl apply -f k8s/worker/
kubectl apply -f k8s/app/combined-app.yaml
kubectl rollout status deployment/app-python -n "${NAMESPACE}" --timeout=120s

echo "Multi-node cluster is ready. Testing via NodePort 8000..."
