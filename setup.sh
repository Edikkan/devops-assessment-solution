#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════════
#  DevOps Assessment — Cluster Bootstrap Script (STAGED ROLLOUT VERSION)
# ════════════════════════════════════════════════════════════════════════════
set -euo pipefail

CLUSTER_NAME="assessment"
REGISTRY_NAME="registry.localhost"
REGISTRY_PORT="5000"
NAMESPACE="assessment"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
die()     { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Pre-flight checks ─────────────────────────────────────────────────────────
command -v k3d     >/dev/null 2>&1 || die "k3d not found."
command -v kubectl >/dev/null 2>&1 || die "kubectl not found."
command -v docker  >/dev/null 2>&1 || die "docker not found."

info "All prerequisites found."

# ── Create k3d cluster ────────────────────────────────────────────────────────
if k3d cluster list | grep -q "^${CLUSTER_NAME}"; then
  warn "Cluster '${CLUSTER_NAME}' already exists — skipping creation."
else
  info "Creating k3d cluster '${CLUSTER_NAME}'..."
  k3d cluster create "${CLUSTER_NAME}" \
    --port "80:80@loadbalancer" \
    --port "443:443@loadbalancer" \
    --agents 2 \
    --registry-create "${REGISTRY_NAME}:${REGISTRY_PORT}"
  success "Cluster created."
fi

kubectl config use-context "k3d-${CLUSTER_NAME}"

# ── Build & push Docker images ────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

info "Building Python app image..."
docker build -t "assessment/app-python:latest" "${SCRIPT_DIR}/app-python/"
k3d image import "assessment/app-python:latest" --cluster "${CLUSTER_NAME}"

info "Building Worker image..."
docker build -t "assessment/worker:latest" "${SCRIPT_DIR}/worker/"
k3d image import "assessment/worker:latest" --cluster "${CLUSTER_NAME}"

# ── Apply manifests ───────────────────────────────────────────────────────────
info "Applying Namespace and Databases..."
kubectl apply -f "${SCRIPT_DIR}/k8s/base/namespace.yaml"
# Ensure HPA is gone so it doesn't fight our manual scaling
kubectl delete hpa --all -n "${NAMESPACE}" --ignore-not-found=true

kubectl apply -f "${SCRIPT_DIR}/k8s/mongodb/"
kubectl apply -f "${SCRIPT_DIR}/k8s/redis/"

info "Waiting for Databases to stabilize..."
kubectl rollout status deployment/mongo -n "${NAMESPACE}" --timeout=180s
kubectl rollout status deployment/redis -n "${NAMESPACE}" --timeout=120s

# Give MongoDB a 10s "Grace Period" to initialize internal engines
info "Warming up Database engines..."
sleep 10

info "Applying Worker and App (Staged Rollout)..."
kubectl apply -f "${SCRIPT_DIR}/k8s/worker/"
kubectl apply -f "${SCRIPT_DIR}/k8s/app/"

# Step 1: Scale to 1 replica to establish initial connections safely
info "Scaling Python app to 1 (Canary phase)..."
kubectl scale deployment app-python -n "${NAMESPACE}" --replicas=1
kubectl rollout status deployment/app-python -n "${NAMESPACE}" --timeout=120s

# Step 2: Scale to full capacity (15 replicas) now that Mongo is ready for the herd
info "Scaling Python app to 15 (Full capacity)..."
kubectl scale deployment app-python -n "${NAMESPACE}" --replicas=15
kubectl rollout status deployment/app-python -n "${NAMESPACE}" --timeout=300s

success "All deployments are ready!"

# ── Print access instructions ─────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Assessment Environment Ready!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Endpoints:"
echo "    API      : http://assessment.local/api/data"
echo "    Stats    : http://assessment.local/api/stats"
echo ""
echo "  To run the stress test:"
echo "    k6 run stress-test/stress-test.js"
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════${NC}"
