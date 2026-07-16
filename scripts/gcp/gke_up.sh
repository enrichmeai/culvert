#!/usr/bin/env bash
# =============================================================================
# gke_up.sh — Spin up ephemeral GKE cluster + Airflow for E2E testing
#
# Creates a spot e2-small cluster (~£0.006/hr), installs Airflow via Helm,
# and syncs DAGs. Total spin-up: ~10 minutes. Cost per session: ~£0.01-0.25
#
# Usage: ./scripts/gcp/gke_up.sh [--skip-data]
#   --skip-data  Skip creating GCS/BQ/PubSub (they already exist from first run)
# =============================================================================
set -euo pipefail

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="europe-west2"
ZONE="${REGION}-a"
CLUSTER_NAME="pipeline-cluster"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

SKIP_DATA=false
[[ "${1:-}" == "--skip-data" ]] && SKIP_DATA=true

echo -e "${CYAN}=== Ephemeral GKE Spin-Up ===${NC}"
echo "Project: $PROJECT_ID"
echo "Cluster: $CLUSTER_NAME (spot e2-small, ~£0.006/hr)"
echo ""

# ── 1. Check if cluster already exists ──
if gcloud container clusters describe "$CLUSTER_NAME" --zone="$ZONE" --project="$PROJECT_ID" &>/dev/null; then
    echo -e "${YELLOW}Cluster already exists — getting credentials${NC}"
    gcloud container clusters get-credentials "$CLUSTER_NAME" --zone "$ZONE" --project "$PROJECT_ID"
else
    echo -e "${GREEN}Creating spot GKE cluster (~5 min)...${NC}"
    gcloud container clusters create "$CLUSTER_NAME" \
        --zone "$ZONE" \
        --project "$PROJECT_ID" \
        --num-nodes 1 \
        --machine-type e2-small \
        --spot \
        --enable-autoscaling \
        --min-nodes 0 \
        --max-nodes 2 \
        --workload-pool="${PROJECT_ID}.svc.id.goog" \
        --enable-ip-alias \
        --quiet

    gcloud container clusters get-credentials "$CLUSTER_NAME" --zone "$ZONE" --project "$PROJECT_ID"
    echo -e "${GREEN}Cluster created${NC}"
fi
echo ""

# ── 2. Create data resources if needed ──
if ! $SKIP_DATA; then
    echo -e "${CYAN}Creating data resources (idempotent)...${NC}"

    # GCS buckets
    for suffix in landing archive error temp airflow-dags dataflow-templates; do
        BUCKET="gs://${PROJECT_ID}-${suffix}"
        gsutil ls "$BUCKET" &>/dev/null 2>&1 || gsutil mb -l "$REGION" -p "$PROJECT_ID" "$BUCKET" 2>/dev/null || true
    done

    # BigQuery datasets
    for ds in odp_generic fdp_generic job_control; do
        bq show --project_id="$PROJECT_ID" "$ds" &>/dev/null 2>&1 || \
            bq mk --project_id="$PROJECT_ID" --location="$REGION" "$ds" 2>/dev/null || true
    done

    # Pub/Sub
    gcloud pubsub topics describe "file-notifications" --project="$PROJECT_ID" &>/dev/null 2>&1 || \
        gcloud pubsub topics create "file-notifications" --project="$PROJECT_ID" --quiet 2>/dev/null || true
    gcloud pubsub subscriptions describe "file-notifications-sub" --project="$PROJECT_ID" &>/dev/null 2>&1 || \
        gcloud pubsub subscriptions create "file-notifications-sub" --topic="file-notifications" --project="$PROJECT_ID" --quiet 2>/dev/null || true

    echo -e "${GREEN}Data resources ready${NC}"
    echo ""
fi

# ── 3. Setup Workload Identity ──
echo -e "${CYAN}Setting up Workload Identity...${NC}"
AIRFLOW_SA="airflow-sa@${PROJECT_ID}.iam.gserviceaccount.com"

# Create SA if missing
gcloud iam service-accounts describe "$AIRFLOW_SA" --project="$PROJECT_ID" &>/dev/null 2>&1 || \
    gcloud iam service-accounts create "airflow-sa" --display-name="Airflow Service Account" --project="$PROJECT_ID" --quiet 2>/dev/null || true

# Bind Workload Identity
gcloud iam service-accounts add-iam-policy-binding "$AIRFLOW_SA" \
    --role="roles/iam.workloadIdentityUser" \
    --member="serviceAccount:${PROJECT_ID}.svc.id.goog[airflow/airflow-worker]" \
    --project="$PROJECT_ID" --quiet 2>/dev/null || true
echo ""

# ── 4. Install Airflow via Helm ──
echo -e "${CYAN}Installing Airflow via Helm (~3 min)...${NC}"

helm repo add apache-airflow https://airflow.apache.org 2>/dev/null || true
helm repo update --fail-on-repo-update-fail=false 2>/dev/null || true

# Check if already installed
if helm status airflow -n airflow &>/dev/null 2>&1; then
    echo -e "${YELLOW}Airflow already installed — upgrading${NC}"
    helm dependency build deployments/data-pipeline-orchestrator/helm
    helm upgrade airflow deployments/data-pipeline-orchestrator/helm \
        --namespace airflow \
        --wait --timeout 5m
else
    helm dependency build deployments/data-pipeline-orchestrator/helm
    helm install airflow deployments/data-pipeline-orchestrator/helm \
        --namespace airflow --create-namespace \
        --wait --timeout 5m
fi
echo -e "${GREEN}Airflow installed${NC}"
echo ""

# ── 5. Wait for pods ──
echo -e "${CYAN}Waiting for pods to be ready...${NC}"
kubectl wait --for=condition=ready pod -l component=scheduler -n airflow --timeout=120s 2>/dev/null || true
kubectl wait --for=condition=ready pod -l component=webserver -n airflow --timeout=120s 2>/dev/null || true
echo ""

# ── 6. Summary ──
echo -e "${GREEN}=============================================="
echo "  GKE + Airflow Ready"
echo "==============================================${NC}"
echo ""
echo "  Cluster:  $CLUSTER_NAME (spot e2-small)"
echo "  Cost:     ~£0.006/hour (~£0.01/session)"
echo ""
echo "  Access Airflow UI:"
echo "    kubectl port-forward svc/airflow-webserver 8080:8080 -n airflow"
echo "    Open: http://localhost:8080 (admin/admin)"
echo ""
echo "  Deploy DAGs:"
echo "    ./scripts/gcp/deploy_to_gke.sh --dags-only"
echo ""
echo "  Run E2E test:"
echo "    ./scripts/gcp/e2e_pipeline_test.sh"
echo ""
echo -e "  ${RED}IMPORTANT: When done, tear down to stop costs:${NC}"
echo "    ./scripts/gcp/gke_down.sh"
echo ""
