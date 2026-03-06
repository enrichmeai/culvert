#!/bin/bash
# Deploy Airflow Orchestrator to GKE
#
# Architecture:
#   - Orchestration (Airflow): GKE (this script)
#   - Ingestion (Beam): Dataflow (Google managed) - triggered by DAGs
#   - Transformation (dbt): BigQuery native - triggered by DAGs
#
# Usage:
#   ./scripts/gcp/deploy_to_gke.sh [--dags-only] [--dataflow-templates]
#
# Options:
#   --dags-only           Only sync DAGs (skip k8s resources)
#   --dataflow-templates  Also deploy Dataflow Flex Templates

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="europe-west2"
CLUSTER_NAME="pipeline-cluster"
ZONE="${REGION}-a"

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEPLOYMENTS_DIR="${ROOT_DIR}/deployments"
WORKFLOWS_DIR="${ROOT_DIR}/.github/workflows"

# Parse arguments
DAGS_ONLY=false
DEPLOY_DATAFLOW=false

for arg in "$@"; do
  case $arg in
    --dags-only)
      DAGS_ONLY=true
      shift
      ;;
    --dataflow-templates)
      DEPLOY_DATAFLOW=true
      shift
      ;;
  esac
done

echo -e "${BLUE}=== GKE Orchestrator Deployment ===${NC}"
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Cluster: ${CLUSTER_NAME}"
echo ""
echo "Architecture:"
echo "  • Orchestration (Airflow): GKE"
echo "  • Ingestion (Beam): Dataflow (Google managed)"
echo "  • Transformation (dbt): BigQuery native"
echo ""

# Verify gcloud authentication
if ! gcloud auth print-identity-token &>/dev/null; then
  echo -e "${RED}Error: Not authenticated with gcloud. Run 'gcloud auth login'${NC}"
  exit 1
fi

# Get cluster credentials
echo -e "${BLUE}=== Getting cluster credentials ===${NC}"
gcloud container clusters get-credentials ${CLUSTER_NAME} --zone ${ZONE} --project ${PROJECT_ID}

# Sync DAGs to GCS
echo -e "${BLUE}=== Syncing DAGs to GCS ===${NC}"
gsutil mb -l ${REGION} gs://${PROJECT_ID}-airflow-dags 2>/dev/null || true
gsutil -m rsync -r -d ${DEPLOYMENTS_DIR}/data-pipeline-orchestrator/dags/ \
  gs://${PROJECT_ID}-airflow-dags/
echo -e "${GREEN}DAGs synced successfully${NC}"

if [ "$DAGS_ONLY" = true ]; then
  echo -e "${BLUE}=== Restarting Airflow scheduler ===${NC}"
  kubectl rollout restart deployment/airflow-scheduler -n airflow || true
  echo -e "${GREEN}Done${NC}"
  exit 0
fi

# Apply Kubernetes resources for Airflow
echo -e "${BLUE}=== Applying Kubernetes resources ===${NC}"

# Create airflow namespace
kubectl create namespace airflow 2>/dev/null || true

# Apply service account with Workload Identity
sed "s/PROJECT_ID/${PROJECT_ID}/g" ${ROOT_DIR}/infrastructure/k8s/workloads/serviceaccount.yaml | kubectl apply -f -

echo -e "${GREEN}Kubernetes resources applied${NC}"

# Deploy Dataflow Flex Templates (optional)
if [ "$DEPLOY_DATAFLOW" = true ]; then
  echo -e "${BLUE}=== Deploying Dataflow Flex Templates ===${NC}"

  # Build and push Dataflow template
  TEMPLATE_BUCKET="gs://${PROJECT_ID}-dataflow-templates"
  gsutil mb -l ${REGION} ${TEMPLATE_BUCKET} 2>/dev/null || true

  # Build ingestion template
  echo "Building Dataflow Flex Template for ingestion..."
  gcloud dataflow flex-template build \
    ${TEMPLATE_BUCKET}/templates/ingestion-pipeline.json \
    --image-gcr-path "gcr.io/${PROJECT_ID}/ingestion-pipeline:latest" \
    --sdk-language "PYTHON" \
    --flex-template-base-image "PYTHON3" \
    --metadata-file "${DEPLOYMENTS_DIR}/original-data-to-bigqueryload/metadata.json" \
    --py-path "${DEPLOYMENTS_DIR}/original-data-to-bigqueryload/src"

  echo -e "${GREEN}Dataflow templates deployed${NC}"
fi

# Check Airflow deployment
echo -e "${BLUE}=== Checking Airflow deployment ===${NC}"
if kubectl get deployment airflow-scheduler -n airflow &>/dev/null; then
  echo "Airflow is deployed. Restarting scheduler to pick up new DAGs..."
  kubectl rollout restart deployment/airflow-scheduler -n airflow
else
  echo -e "${RED}Airflow not found. Deploy using Helm:${NC}"
  echo ""
  echo "  helm repo add apache-airflow https://airflow.apache.org"
  echo "  helm repo update"
  echo "  helm install airflow apache-airflow/airflow \\"
  echo "    --namespace airflow \\"
  echo "    --values ${ROOT_DIR}/infrastructure/k8s/airflow/values.yaml"
fi

echo ""
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "Components deployed:"
echo "  ✓ DAGs synced to gs://${PROJECT_ID}-airflow-dags/"
echo "  ✓ Airflow on GKE (orchestration only)"
echo ""
echo "Native GCP services (triggered by DAGs):"
echo "  • Dataflow: Runs Beam ingestion pipelines"
echo "  • BigQuery: Runs dbt transformations"
echo ""
echo "Next steps:"
echo "  1. Verify Airflow UI: kubectl port-forward svc/airflow-webserver 8080:8080 -n airflow"
echo "  2. Check DAGs: Open http://localhost:8080"
echo "  3. Trigger a test: Upload .ok file to landing bucket"

