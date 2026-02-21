#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
#  DevOps Assessment — 10,000 VU CAPABLE AUTOMATED DEPLOY
# ════════════════════════════════════════════════════════════════════════════
set -euo pipefail

CLUSTER_NAME="assessment"
NAMESPACE="assessment"
STRESS_TEST_FILE="spike-test.js"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
die()     { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── 0. Host Kernel Hardening (Crucial for 10k VUs) ───────────────────────────
info "Hardening Host Kernel for high concurrency..."
# Opening the "Waiting Room" for TCP connections
sudo sysctl -w net.core.somaxconn=20000 >/dev/null
sudo sysctl -w net.ipv4.tcp_max_syn_backlog=20000 >/dev/null
# Faster socket recycling
sudo sysctl -w net.ipv4.tcp_tw_reuse=1 >/dev/null
# Increasing file descriptors for 10k simultaneous sockets
ulimit -n 100000 || warn "Could not set ulimit automatically. Ensure /etc/security/limits.conf is updated."

# ── 1. Cluster & Image Setup ─────────────────────────────────────────────────
if ! k3d cluster list | grep -q "^${CLUSTER_NAME}"; then
  info "Creating cluster..."
  k3d cluster create "${CLUSTER_NAME}" --port "80:80@loadbalancer" --agents 2
fi
kubectl config use-context "k3d-${CLUSTER_NAME}"

info "Building and Importing Images (App + Worker)..."
docker build -t "assessment/app-python:latest" ./app-python/
docker build -t "assessment/worker:latest" ./worker/
k3d image import "assessment/app-python:latest" "assessment/worker:latest" --cluster "${CLUSTER_NAME}"

# ── 2. Manifest Deployment ───────────────────────────────────────────────────
info "Applying Infrastructure (Mongo + Redis)..."
kubectl apply -f k8s/base/namespace.yaml
kubectl apply -f k8s/mongodb/
kubectl apply -f k8s/redis/
kubectl rollout status deployment/mongo -n "${NAMESPACE}" --timeout=120s
kubectl rollout status deployment/redis -n "${NAMESPACE}" --timeout=120s

info "Applying App + Worker Configuration..."
kubectl apply -f k8s/worker/
kubectl apply -f k8s/app/combined-app.yaml
kubectl rollout status deployment/app-python -n "${NAMESPACE}" --timeout=120s

# ── 3. Automated Bridge ──────────────────────────────────────────────────────
info "Stabilizing Network (5s pause)..."
sleep 5

POD_IP=$(kubectl get pods -n "${NAMESPACE}" -l app=app-python -o jsonpath='{.items[0].status.podIP}')
[ -z "$POD_IP" ] && die "Could not retrieve Pod IP."

info "Detected Pod IP: ${YELLOW}${POD_IP}${NC}"

# Inject the IP into the k6 script
if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' "s/http:\/\/172.18.[0-9.]*:[0-9]*/http:\/\/${POD_IP}:8000/" "$STRESS_TEST_FILE"
else
  sed -i "s/http:\/\/172.18.[0-9.]*:[0-9]*/http:\/\/${POD_IP}:8000/" "$STRESS_TEST_FILE"
fi

success "System is primed for 10,000 VUs."

# ── 4. Execution ─────────────────────────────────────────────────────────────
echo -e "${YELLOW}🚀 Launching k6 Spike Test...${NC}"
k6 run "$STRESS_TEST_FILE"
