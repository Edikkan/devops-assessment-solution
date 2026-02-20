#!/bin/bash
set -e

# ── 1. CONFIGURATION ──────────────────────────────────────────────────────────
NAMESPACE="assessment"
APP_IMAGE="assessment/app-python:latest"
WORKER_IMAGE="assessment/worker:latest"

echo "════════════════════════════════════════════════════════"
echo "  Deploying High-Performance Solution"
echo "════════════════════════════════════════════════════════"

# ── 2. KERNEL TUNING (HOST LEVEL) ─────────────────────────────────────────────
echo "[INFO] Tuning Host Kernel for 10k Concurrency..."
sudo sysctl -w net.ipv4.ip_local_port_range="1024 65535" > /dev/null
sudo sysctl -w net.ipv4.tcp_tw_reuse=1 > /dev/null
sudo sysctl -w net.core.somaxconn=20000 > /dev/null
ulimit -n 100000

# ── 3. NAMESPACE & INFRASTRUCTURE ─────────────────────────────────────────────
echo "[INFO] Cleaning Namespace..."
kubectl delete ns $NAMESPACE --ignore-not-found
kubectl create ns $NAMESPACE

echo "[INFO] Deploying Redis and MongoDB..."
kubectl apply -f k8s/mongodb/
kubectl apply -f k8s/redis/

echo "[WAIT] Waiting for Databases to stabilize..."
kubectl rollout status deployment/mongo -n $NAMESPACE --timeout=120s
kubectl rollout status deployment/redis -n $NAMESPACE --timeout=120s

# ── 4. BUILD & IMPORT (Only if needed) ────────────────────────────────────────
# If you've already built images, you can skip this to save time
# echo "[INFO] Building Optimized Images..."
# docker build -t $APP_IMAGE ./app-python/
# docker build -t $WORKER_IMAGE ./worker/
# k3d image import $APP_IMAGE $WORKER_IMAGE --cluster assessment

# ── 5. APPLICATION DEPLOYMENT ─────────────────────────────────────────────────
echo "[INFO] Applying High-Performance Manifests..."
kubectl apply -f k8s/app/combined-app.yaml
kubectl apply -f k8s/worker/

# NOTE: We keep replicas at 1 because hostNetwork binds to VM Port 8000.
# A single Pod with 8 workers leverages the full F8s_v2 capacity.
echo "[INFO] Scaling to Native Performance Mode (1 Replica, 8 Workers)..."
kubectl scale deployment app-python -n $NAMESPACE --replicas=1

echo "[WAIT] Waiting for App Rollout..."
kubectl rollout status deployment/app-python -n $NAMESPACE --timeout=60s

# ── 6. FINAL VERIFICATION ─────────────────────────────────────────────────────
POD_IP=$(kubectl get pods -n $NAMESPACE -l app=app-python -o jsonpath='{.items[0].status.podIP}')

echo ""
echo "════════════════════════════════════════════════════════"
echo "  STATION READY!"
echo "════════════════════════════════════════════════════════"
echo "  Target Pod IP : $POD_IP"
echo "  Health Check  : curl http://$POD_IP:8000/healthz"
echo "  Next Step     : Update stress-test.js with IP $POD_IP"
echo "                  Then run: k6 run stress-test/stress-test.js"
echo "════════════════════════════════════════════════════════"
