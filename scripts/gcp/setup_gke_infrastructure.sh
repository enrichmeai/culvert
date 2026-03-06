#!/bin/bash
# =============================================================================
# Setup GKE Infrastructure for Data Pipeline
# =============================================================================
# Creates all required infrastructure for GKE-based pipeline deployment:
#   - GKE Cluster
#   - GCS Buckets (landing, archive, error, dags, dataflow-templates)
#   - BigQuery Datasets (ODP, FDP, job_control)
#   - Pub/Sub Topics
#   - Service Accounts with Workload Identity
#
# Usage: ./scripts/gcp/setup_gke_infrastructure.sh [--skip-cluster]
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="europe-west2"
ZONE="${REGION}-a"
CLUSTER_NAME="pipeline-cluster"
SKIP_CLUSTER=false

# Parse arguments
for arg in "$@"; do
  case $arg in
    --skip-cluster)
      SKIP_CLUSTER=true
      shift
      ;;
  esac
done

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: No GCP project set${NC}"
    echo "Run: gcloud config set project <PROJECT_ID>"
    exit 1
fi

echo "=============================================="
echo "  GKE Infrastructure Setup"
echo "=============================================="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Zone: $ZONE"
echo "Cluster: $CLUSTER_NAME"
echo "=============================================="
echo ""

# =============================================================================
# Step 1: Enable Required Services
# =============================================================================
echo -e "${BLUE}>>> Step 1: Enable GCP Services${NC}"

SERVICES=(
    "container.googleapis.com"       # GKE
    "bigquery.googleapis.com"        # BigQuery
    "storage.googleapis.com"         # GCS
    "pubsub.googleapis.com"          # Pub/Sub
    "dataflow.googleapis.com"        # Dataflow
    "cloudbuild.googleapis.com"      # Cloud Build
    "containerregistry.googleapis.com" # GCR
    "cloudkms.googleapis.com"        # KMS
    "monitoring.googleapis.com"      # Monitoring
    "logging.googleapis.com"         # Logging
)

for service in "${SERVICES[@]}"; do
    echo -n "  Enabling $service... "
    gcloud services enable "$service" --project="$PROJECT_ID" --quiet && echo -e "${GREEN}✅${NC}"
done
echo ""

# =============================================================================
# Step 2: Create GKE Cluster
# =============================================================================
if [ "$SKIP_CLUSTER" = false ]; then
    echo -e "${BLUE}>>> Step 2: Create GKE Cluster${NC}"

    if gcloud container clusters describe "$CLUSTER_NAME" --zone="$ZONE" --project="$PROJECT_ID" &>/dev/null; then
        echo -e "  ${YELLOW}Cluster already exists:${NC} $CLUSTER_NAME"
    else
        echo "  Creating cluster: $CLUSTER_NAME (this takes ~5 minutes)..."
        gcloud container clusters create "$CLUSTER_NAME" \
            --zone "$ZONE" \
            --project "$PROJECT_ID" \
            --num-nodes 2 \
            --machine-type e2-standard-2 \
            --enable-autoscaling \
            --min-nodes 1 \
            --max-nodes 5 \
            --workload-pool="${PROJECT_ID}.svc.id.goog" \
            --enable-ip-alias \
            --quiet
        echo -e "  ${GREEN}Cluster created ✅${NC}"
    fi

    # Get credentials
    echo "  Getting cluster credentials..."
    gcloud container clusters get-credentials "$CLUSTER_NAME" --zone "$ZONE" --project "$PROJECT_ID"
    echo ""
else
    echo -e "${YELLOW}>>> Step 2: Skipping GKE Cluster (--skip-cluster)${NC}"
    echo ""
fi

# =============================================================================
# Step 3: Create GCS Buckets
# =============================================================================
echo -e "${BLUE}>>> Step 3: Create GCS Buckets${NC}"

create_bucket() {
    local name="$1"
    local full="gs://${PROJECT_ID}-${name}"
    if gsutil ls "$full" &>/dev/null 2>&1; then
        echo -e "  ${YELLOW}Exists:${NC} $full"
    else
        echo -n "  Creating: $full... "
        gsutil mb -l "$REGION" -p "$PROJECT_ID" "$full" && echo -e "${GREEN}✅${NC}"
    fi
}

# Pipeline buckets
create_bucket "landing"
create_bucket "archive"
create_bucket "error"
create_bucket "temp"

# Airflow DAGs bucket
create_bucket "airflow-dags"

# Dataflow templates bucket
create_bucket "dataflow-templates"

echo ""

# =============================================================================
# Step 4: Create BigQuery Datasets
# =============================================================================
echo -e "${BLUE}>>> Step 4: Create BigQuery Datasets${NC}"

create_dataset() {
    local name="$1"
    if bq show --project_id="$PROJECT_ID" "$name" &>/dev/null 2>&1; then
        echo -e "  ${YELLOW}Exists:${NC} $name"
    else
        echo -n "  Creating: $name... "
        bq mk --project_id="$PROJECT_ID" --location="$REGION" "$name" && echo -e "${GREEN}✅${NC}"
    fi
}

# ODP datasets
create_dataset "odp_generic"

# FDP datasets
create_dataset "fdp_generic"

# Job control
create_dataset "job_control"

# Error tracking
create_dataset "error_tracking"

echo ""

# =============================================================================
# Step 5: Create Pub/Sub Topics and Subscriptions
# =============================================================================
echo -e "${BLUE}>>> Step 5: Create Pub/Sub Topics${NC}"

create_topic() {
    local name="$1"
    if gcloud pubsub topics describe "$name" --project="$PROJECT_ID" &>/dev/null 2>&1; then
        echo -e "  ${YELLOW}Exists:${NC} $name"
    else
        echo -n "  Creating topic: $name... "
        gcloud pubsub topics create "$name" --project="$PROJECT_ID" --quiet && echo -e "${GREEN}✅${NC}"
    fi
}

create_subscription() {
    local name="$1"
    local topic="$2"
    if gcloud pubsub subscriptions describe "$name" --project="$PROJECT_ID" &>/dev/null 2>&1; then
        echo -e "  ${YELLOW}Exists:${NC} $name"
    else
        echo -n "  Creating subscription: $name... "
        gcloud pubsub subscriptions create "$name" --topic="$topic" --project="$PROJECT_ID" --quiet && echo -e "${GREEN}✅${NC}"
    fi
}

create_topic "file-notifications"
create_topic "pipeline-events"
create_subscription "file-notifications-sub" "file-notifications"
create_subscription "pipeline-events-sub" "pipeline-events"

echo ""

# =============================================================================
# Step 6: Create Service Accounts for Workload Identity
# =============================================================================
echo -e "${BLUE}>>> Step 6: Create Service Accounts${NC}"

# Airflow service account
AIRFLOW_SA="airflow-sa"
AIRFLOW_SA_EMAIL="${AIRFLOW_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

if gcloud iam service-accounts describe "$AIRFLOW_SA_EMAIL" --project="$PROJECT_ID" &>/dev/null 2>&1; then
    echo -e "  ${YELLOW}Exists:${NC} $AIRFLOW_SA_EMAIL"
else
    echo -n "  Creating: $AIRFLOW_SA... "
    gcloud iam service-accounts create "$AIRFLOW_SA" \
        --display-name="Airflow Service Account" \
        --project="$PROJECT_ID" --quiet && echo -e "${GREEN}✅${NC}"
fi

# Grant roles to Airflow SA
echo "  Granting roles to Airflow SA..."
AIRFLOW_ROLES=(
    "roles/dataflow.developer"
    "roles/bigquery.jobUser"
    "roles/bigquery.dataEditor"
    "roles/storage.objectAdmin"
    "roles/pubsub.subscriber"
    "roles/pubsub.publisher"
)

for role in "${AIRFLOW_ROLES[@]}"; do
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:${AIRFLOW_SA_EMAIL}" \
        --role="$role" \
        --quiet 2>/dev/null || true
done
echo -e "  ${GREEN}Roles granted ✅${NC}"

# Setup Workload Identity binding
if [ "$SKIP_CLUSTER" = false ]; then
    echo "  Setting up Workload Identity..."
    gcloud iam service-accounts add-iam-policy-binding "$AIRFLOW_SA_EMAIL" \
        --role="roles/iam.workloadIdentityUser" \
        --member="serviceAccount:${PROJECT_ID}.svc.id.goog[airflow/airflow-worker]" \
        --project="$PROJECT_ID" --quiet 2>/dev/null || true
    echo -e "  ${GREEN}Workload Identity configured ✅${NC}"
fi

echo ""

# =============================================================================
# Step 7: Setup GCS Notifications for Pub/Sub
# =============================================================================
echo -e "${BLUE}>>> Step 7: Setup GCS Notifications${NC}"

LANDING_BUCKET="gs://${PROJECT_ID}-landing"
TOPIC="projects/${PROJECT_ID}/topics/file-notifications"

# Check if notification exists
existing=$(gsutil notification list "$LANDING_BUCKET" 2>/dev/null | grep -c "file-notifications" || echo "0")
if [ "$existing" -gt 0 ]; then
    echo -e "  ${YELLOW}Notification already exists${NC}"
else
    echo -n "  Creating GCS notification... "
    gsutil notification create \
        -t "$TOPIC" \
        -f json \
        -e OBJECT_FINALIZE \
        "$LANDING_BUCKET" && echo -e "${GREEN}✅${NC}"
fi

echo ""

# =============================================================================
# Step 8: Create Job Control Table
# =============================================================================
echo -e "${BLUE}>>> Step 8: Create Job Control Table${NC}"

TABLE_EXISTS=$(bq show --project_id="$PROJECT_ID" "job_control.pipeline_jobs" 2>/dev/null && echo "yes" || echo "no")

if [ "$TABLE_EXISTS" = "yes" ]; then
    echo -e "  ${YELLOW}Table already exists:${NC} job_control.pipeline_jobs"
else
    echo -n "  Creating job_control.pipeline_jobs table... "
    bq mk --table \
        --project_id="$PROJECT_ID" \
        --schema='run_id:STRING,system_id:STRING,entity_type:STRING,extract_date:DATE,status:STRING,source_files:STRING,record_count:INTEGER,started_at:TIMESTAMP,completed_at:TIMESTAMP,error_message:STRING,created_at:TIMESTAMP,updated_at:TIMESTAMP' \
        "job_control.pipeline_jobs" && echo -e "${GREEN}✅${NC}"
fi

echo ""

# =============================================================================
# Summary
# =============================================================================
echo -e "${GREEN}=============================================="
echo "✅ GKE Infrastructure Setup Complete!"
echo "==============================================${NC}"
echo ""
echo "Created Resources:"
echo "  • GKE Cluster: $CLUSTER_NAME"
echo "  • GCS Buckets: landing, archive, error, temp, airflow-dags, dataflow-templates"
echo "  • BigQuery: odp_generic, fdp_generic, job_control, error_tracking"
echo "  • Pub/Sub: file-notifications, pipeline-events"
echo "  • Service Account: $AIRFLOW_SA_EMAIL"
echo ""
echo "Next Steps:"
echo ""
echo "  1. Install Airflow on GKE:"
echo "     helm repo add apache-airflow https://airflow.apache.org"
echo "     helm repo update"
echo "     helm install airflow apache-airflow/airflow \\"
echo "       --namespace airflow --create-namespace \\"
echo "       --values infrastructure/k8s/airflow/values.yaml"
echo ""
echo "  2. Deploy DAGs:"
echo "     ./scripts/gcp/deploy_to_gke.sh --dags-only"
echo ""
echo "  3. Verify:"
echo "     kubectl get pods -n airflow"
echo "     kubectl port-forward svc/airflow-webserver 8080:8080 -n airflow"
echo ""

