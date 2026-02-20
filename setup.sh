#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
#  DevOps Assessment — FULLY AUTOMATED DEPLOY & TEST
# ════════════════════════════════════════════════════════════════════════════
set -euo pipefail

CLUSTER_NAME="assessment"
NAMESPACE="assessment"
STRESS_TEST_FILE="stress-test/stress-test.js"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
die()     { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── 1. Cluster & Image Setup ─────────────────────────────────────────────────
if ! k3d cluster list | grep -q "^${CLUSTER_NAME}"; then
  info "Creating cluster..."
  k3d cluster create "${CLUSTER_NAME}" --port "80:80@loadbalancer" --agents 2
fi
kubectl config use-context "k3d-${CLUSTER_NAME}"

info "Building and Importing Images..."
docker build -t "assessment/app-python:latest" ./app-python/
docker build -t "assessment/worker:latest" ./worker/
k3d image import "assessment/app-python:latest" "assessment/worker:latest" --cluster "${CLUSTER_NAME}"

# ── 2. Manifest Deployment ───────────────────────────────────────────────────
info "Applying Infrastructure..."
kubectl apply -f k8s/base/namespace.yaml
kubectl delete hpa --all -n "${NAMESPACE}" --ignore-not-found=true
kubectl apply -f k8s/mongodb/
kubectl apply -f k8s/redis/
kubectl rollout status deployment/mongo -n "${NAMESPACE}" --timeout=120s
kubectl rollout status deployment/redis -n "${NAMESPACE}" --timeout=120s

info "Applying App Configuration..."
kubectl apply -f k8s/worker/
kubectl apply -f k8s/app/combined-app.yaml
kubectl scale deployment app-python -n "${NAMESPACE}" --replicas=1
kubectl rollout status deployment/app-python -n "${NAMESPACE}" --timeout=120s

# ── 3. The "Automated Bridge" ────────────────────────────────────────────────
info "Stabilizing Network (5s pause)..."
sleep 5

# Query the dynamic Pod IP
POD_IP=$(kubectl get pods -n "${NAMESPACE}" -l app=app-python -o jsonpath='{.items[0].status.podIP}')
[ -z "$POD_IP" ] && die "Could not retrieve Pod IP."

info "Detected Pod IP: ${YELLOW}${POD_IP}${NC}"

# Inject the IP into the k6 script using sed (handles macOS and Linux differences)
info "Updating ${STRESS_TEST_FILE} with new IP..."
if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' "s/const POD_IP = '[^']*'/const POD_IP = '${POD_IP}'/" "$STRESS_TEST_FILE"
else
  sed -i "s/const POD_IP = '[^']*'/const POD_IP = '${POD_IP}'/" "$STRESS_TEST_FILE"
fi

success "Configuration complete."

# ── 4. Automated Stress Test ─────────────────────────────────────────────────
echo -e "${YELLOW}🚀 Launching k6 Stress Test in 3 seconds...${NC}"
sleep 3

# Apply host tuning right before execution
sudo sysctl -w net.ipv4.tcp_tw_reuse=1 >/dev/null 2>&1 || warn "Could not set sysctl (requires sudo)"
ulimit -n 100000 || warn "Could not set ulimit."

# Start k6
k6 run "$STRESS_TEST_FILE"

# ── 5. Final Report ──────────────────────────────────────────────────────────
success "Workflow Complete! Review the k6 summary above for pass/fail criteria."
