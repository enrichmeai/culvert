#!/bin/bash
# =============================================================================
# Verify GCP Infrastructure
# =============================================================================
# Checks that all required GCP resources are properly configured.
#
# Usage: ./scripts/gcp/verify_infrastructure.sh [--fix]
#
# Options:
#   --fix    Attempt to fix any issues found
#
# Last Updated: March 2026
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

FIX_MODE="${1:-}"
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="europe-west2"
ZONE="${REGION}-a"

PASSED=0
FAILED=0
WARNINGS=0

# =============================================================================
# Helper Functions
# =============================================================================

check_pass() {
    echo -e "  ${GREEN}✅ $1${NC}"
    ((PASSED++))
}

check_fail() {
    echo -e "  ${RED}❌ $1${NC}"
    ((FAILED++))
}

check_warn() {
    echo -e "  ${YELLOW}⚠️  $1${NC}"
    ((WARNINGS++))
}

check_info() {
    echo -e "  ${BLUE}ℹ️  $1${NC}"
}

# =============================================================================
# Validation Functions
# =============================================================================

check_service_enabled() {
    local service="$1"
    if gcloud services list --enabled --project="$PROJECT_ID" --format="value(config.name)" 2>/dev/null | grep -q "^${service}$"; then
        return 0
    else
        return 1
    fi
}

fix_service() {
    local service="$1"
    if [[ "$FIX_MODE" == "--fix" ]]; then
        echo -e "    ${BLUE}Enabling ${service}...${NC}"
        gcloud services enable "$service" --project="$PROJECT_ID" --quiet 2>/dev/null && return 0 || return 1
    fi
    return 1
}

# =============================================================================
# Main Checks
# =============================================================================

echo ""
echo -e "${BLUE}=============================================="
echo "  GCP Infrastructure Verification"
echo "==============================================${NC}"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# -----------------------------------------------------------------------------
# Check 1: Required GCP Services
# -----------------------------------------------------------------------------
echo -e "${BLUE}>>> Checking GCP Services...${NC}"

REQUIRED_SERVICES=(
    "storage.googleapis.com"
    "bigquery.googleapis.com"
    "pubsub.googleapis.com"
    "container.googleapis.com"
    "dataflow.googleapis.com"
    "cloudbuild.googleapis.com"
    "containerregistry.googleapis.com"
    "monitoring.googleapis.com"
    "logging.googleapis.com"
    "iam.googleapis.com"
    "cloudresourcemanager.googleapis.com"
)

for service in "${REQUIRED_SERVICES[@]}"; do
    if check_service_enabled "$service"; then
        check_pass "$service"
    else
        check_fail "$service (not enabled)"
        fix_service "$service" && check_info "Fixed: $service enabled"
    fi
done

# -----------------------------------------------------------------------------
# Check 2: GKE Cluster
# -----------------------------------------------------------------------------
echo ""
echo -e "${BLUE}>>> Checking GKE Cluster...${NC}"

if gcloud container clusters describe pipeline-cluster --zone="$ZONE" --project="$PROJECT_ID" &>/dev/null; then
    CLUSTER_STATUS=$(gcloud container clusters describe pipeline-cluster --zone="$ZONE" --project="$PROJECT_ID" --format="value(status)" 2>/dev/null)
    if [[ "$CLUSTER_STATUS" == "RUNNING" ]]; then
        check_pass "GKE cluster 'pipeline-cluster' is RUNNING"

        # Check node count
        NODE_COUNT=$(gcloud container clusters describe pipeline-cluster --zone="$ZONE" --project="$PROJECT_ID" --format="value(currentNodeCount)" 2>/dev/null)
        check_info "Node count: $NODE_COUNT"
    else
        check_warn "GKE cluster exists but status is: $CLUSTER_STATUS"
    fi
else
    check_fail "GKE cluster 'pipeline-cluster' not found"
    check_info "Run: ./scripts/gcp/setup_gke_infrastructure.sh"
fi

# -----------------------------------------------------------------------------
# Check 3: GCS Buckets
# -----------------------------------------------------------------------------
echo ""
echo -e "${BLUE}>>> Checking GCS Buckets...${NC}"

REQUIRED_BUCKETS=(
    "${PROJECT_ID}-landing"
    "${PROJECT_ID}-archive"
    "${PROJECT_ID}-error"
    "${PROJECT_ID}-temp"
    "${PROJECT_ID}-airflow-dags"
    "${PROJECT_ID}-dataflow-templates"
)

for bucket in "${REQUIRED_BUCKETS[@]}"; do
    if gsutil ls -b "gs://${bucket}" &>/dev/null; then
        check_pass "gs://${bucket}"
    else
        check_fail "gs://${bucket} (not found)"
    fi
done

# -----------------------------------------------------------------------------
# Check 4: BigQuery Datasets
# -----------------------------------------------------------------------------
echo ""
echo -e "${BLUE}>>> Checking BigQuery Datasets...${NC}"

REQUIRED_DATASETS=(
    "odp_generic"
    "fdp_generic"
    "job_control"
    "error_tracking"
)

for dataset in "${REQUIRED_DATASETS[@]}"; do
    if bq show --project_id="$PROJECT_ID" "$dataset" &>/dev/null; then
        check_pass "Dataset: $dataset"
    else
        check_fail "Dataset: $dataset (not found)"
    fi
done

# -----------------------------------------------------------------------------
# Check 5: Pub/Sub Topics and Subscriptions
# -----------------------------------------------------------------------------
echo ""
echo -e "${BLUE}>>> Checking Pub/Sub...${NC}"

REQUIRED_TOPICS=(
    "file-notifications"
    "pipeline-events"
)

for topic in "${REQUIRED_TOPICS[@]}"; do
    if gcloud pubsub topics describe "$topic" --project="$PROJECT_ID" &>/dev/null; then
        check_pass "Topic: $topic"

        # Check subscription
        if gcloud pubsub subscriptions describe "${topic}-sub" --project="$PROJECT_ID" &>/dev/null; then
            check_pass "Subscription: ${topic}-sub"
        else
            check_fail "Subscription: ${topic}-sub (not found)"
        fi
    else
        check_fail "Topic: $topic (not found)"
    fi
done

# -----------------------------------------------------------------------------
# Check 6: Service Accounts
# -----------------------------------------------------------------------------
echo ""
echo -e "${BLUE}>>> Checking Service Accounts...${NC}"

REQUIRED_SAS=(
    "airflow-sa"
)

for sa in "${REQUIRED_SAS[@]}"; do
    if gcloud iam service-accounts describe "${sa}@${PROJECT_ID}.iam.gserviceaccount.com" --project="$PROJECT_ID" &>/dev/null; then
        check_pass "Service Account: $sa"
    else
        check_fail "Service Account: $sa (not found)"
    fi
done

# -----------------------------------------------------------------------------
# Check 7: Container Images (GCR)
# -----------------------------------------------------------------------------
echo ""
echo -e "${BLUE}>>> Checking Container Images...${NC}"

REQUIRED_IMAGES=(
    "airflow-custom"
)

for image in "${REQUIRED_IMAGES[@]}"; do
    if gcloud container images describe "gcr.io/${PROJECT_ID}/${image}:latest" &>/dev/null 2>&1; then
        check_pass "Image: gcr.io/${PROJECT_ID}/${image}:latest"
    else
        check_warn "Image: ${image} (not built yet)"
        check_info "Build with: gcloud builds submit --tag gcr.io/${PROJECT_ID}/${image}:latest infrastructure/k8s/airflow/"
    fi
done

# -----------------------------------------------------------------------------
# Check 8: Helm/Airflow (if GKE exists)
# -----------------------------------------------------------------------------
echo ""
echo -e "${BLUE}>>> Checking Airflow Installation...${NC}"

if kubectl get namespace airflow &>/dev/null 2>&1; then
    check_pass "Airflow namespace exists"

    # Check pods
    READY_PODS=$(kubectl get pods -n airflow --no-headers 2>/dev/null | grep -c "Running" || echo "0")
    TOTAL_PODS=$(kubectl get pods -n airflow --no-headers 2>/dev/null | wc -l | tr -d ' ' || echo "0")

    if [[ "$READY_PODS" -gt 0 ]]; then
        check_pass "Airflow pods: ${READY_PODS}/${TOTAL_PODS} running"
    else
        check_warn "Airflow pods: ${READY_PODS}/${TOTAL_PODS} running"
    fi
else
    check_warn "Airflow namespace not found (not deployed)"
    check_info "Deploy with: helm install airflow apache-airflow/airflow -n airflow --create-namespace"
fi

# -----------------------------------------------------------------------------
# Check 9: GCS Notifications
# -----------------------------------------------------------------------------
echo ""
echo -e "${BLUE}>>> Checking GCS Notifications...${NC}"

NOTIFICATIONS=$(gsutil notification list "gs://${PROJECT_ID}-landing" 2>/dev/null | grep -c "projects/" || echo "0")
if [[ "$NOTIFICATIONS" -gt 0 ]]; then
    check_pass "GCS notification configured on landing bucket"
else
    check_warn "No GCS notification on landing bucket"
    check_info "Set up with: gsutil notification create -t file-notifications -f json gs://${PROJECT_ID}-landing"
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
echo -e "${BLUE}=============================================="
echo "  Verification Summary"
echo "==============================================${NC}"
echo ""
echo -e "  ${GREEN}Passed:${NC}   $PASSED"
echo -e "  ${RED}Failed:${NC}   $FAILED"
echo -e "  ${YELLOW}Warnings:${NC} $WARNINGS"
echo ""

if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}✅ All checks passed! Infrastructure is ready.${NC}"
    exit 0
elif [[ $FAILED -le 3 ]]; then
    echo -e "${YELLOW}⚠️  Some checks failed. Run with --fix to attempt auto-fix.${NC}"
    echo "   ./scripts/gcp/verify_infrastructure.sh --fix"
    exit 1
else
    echo -e "${RED}❌ Multiple checks failed. Run setup script:${NC}"
    echo "   ./scripts/gcp/setup_gke_infrastructure.sh"
    exit 1
fi

