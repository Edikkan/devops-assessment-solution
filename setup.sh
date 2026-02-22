#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
#  DevOps Assessment — MULTI-NODE 10,000 VU CAPABLE AUTOMATED DEPLOY
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

# ── 0. Host Kernel Hardening ────────────────────────────────────────────────
info "Hardening Host Kernel for high concurrency..."
sudo sysctl -w net.core.somaxconn=32768 >/dev/null
sudo sysctl -w net.ipv4.tcp_max_syn_backlog=32768 >/dev/null
sudo sysctl -w net.ipv4.tcp_tw_reuse=1 >/dev/null
sudo sysctl -w net.ipv4.ip_local_port_range="1024 65535" >/dev/null
sudo sysctl -w net.ipv4.tcp_fin_timeout=15 >/dev/null
ulimit -n 100000 || warn "Could not set ulimit manually."

# ── 1. Cluster Setup (Multi-Node Transition) ────────────────────────────────
# We recreate the cluster to ensure the new 3-agent geometry is applied
if k3d cluster list | grep -q "^${CLUSTER_NAME}"; then
  info "Recreating cluster for Multi-Node geometry..."
  k3d cluster delete "${CLUSTER_NAME}"
fi

# Create cluster with 1 Server and 3 Agents
# Map VM port 8000 to NodePort 30000 on the agents
info "Creating 3-Agent Cluster..."
k3d cluster create "${CLUSTER_NAME}" \
  --agents 3 \
  --port "8000:30000@agent:0" \
  --port "80:80@loadbalancer"

kubectl config use-context "k3d-${CLUSTER_NAME}"

info "Building and Importing Images..."
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
# Note: Ensure your combined-app.yaml has replicas: 3 for this run
kubectl apply -f k8s/app/combined-app.yaml
kubectl rollout status deployment/app-python -n "${NAMESPACE}" --timeout=120s

# ── 3. Automated Bridge ──────────────────────────────────────────────────────
info "Stabilizing Network (10s pause)..."
sleep 10

# Direct targeting via NodePort on localhost
TARGET_URL="http://localhost:8000"

info "Targeting Multi-Node Entrypoint: ${YELLOW}${TARGET_URL}${NC}"

# Update k6 script to hit the NodePort entrypoint
if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' "s|http://[0-9.]*:[0-9]*|${TARGET_URL}|" "$STRESS_TEST_FILE"
else
  sed -i "s|http://[0-9.]*:[0-9]*|${TARGET_URL}|" "$STRESS_TEST_FILE"
fi

success "Multi-node system (3 Agents) is primed."

# ── 4. Execution ─────────────────────────────────────────────────────────────
echo -e "${YELLOW}🚀 Launching k6 Spike Test...${NC}"
k6 run "$STRESS_TEST_FILE"
