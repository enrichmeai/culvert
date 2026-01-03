#!/bin/bash

# setupanddeployongcp.sh - Complete GCP Setup & Deployment Script
#
# This script automates the entire setup and deployment process for the LOA Blueprint
# on Google Cloud Platform (GCP) for London (UK) staging environment.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - terraform installed (v1.5.0+)
#   - git access to repository
#
# Usage:
#   ./setupanddeployongcp.sh <GCP_PROJECT_ID>
#
# Example:
#   ./setupanddeployongcp.sh loa-staging-project-123

set -e  # Exit on first error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TERRAFORM_DIR="$PROJECT_ROOT/infrastructure/terraform"
GCP_PROJECT_ID="${1:-}"
GCP_REGION="europe-west2"
ENVIRONMENT="staging"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Validate inputs
validate_inputs() {
    log_info "Validating inputs..."

    if [ -z "$GCP_PROJECT_ID" ]; then
        log_error "GCP_PROJECT_ID is required. Usage: $0 <GCP_PROJECT_ID>"
    fi

    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI is not installed"
    fi

    if ! command -v terraform &> /dev/null; then
        log_error "terraform is not installed"
    fi

    log_success "All prerequisites validated"
}

# Setup GCP project
setup_gcp_project() {
    log_info "Setting up GCP project: $GCP_PROJECT_ID"

    # Set default project
    gcloud config set project "$GCP_PROJECT_ID"
    log_success "GCP project set to $GCP_PROJECT_ID"

    # Enable required APIs
    log_info "Enabling GCP APIs..."
    gcloud services enable \
        compute.googleapis.com \
        storage-api.googleapis.com \
        bigquery.googleapis.com \
        cloudrun.googleapis.com \
        cloudfunctions.googleapis.com \
        dataflow.googleapis.com \
        logging.googleapis.com \
        monitoring.googleapis.com \
        iam.googleapis.com \
        servicenetworking.googleapis.com \
        secretmanager.googleapis.com \
        --quiet

    log_success "All required APIs enabled"
}

# Create service account
setup_service_accounts() {
    log_info "Setting up service accounts..."

    local terraform_sa="terraform-sa@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

    # Check if service account exists
    if ! gcloud iam service-accounts describe "$terraform_sa" 2>/dev/null; then
        log_info "Creating Terraform service account..."
        gcloud iam service-accounts create terraform-sa \
            --display-name="Terraform Service Account" \
            --quiet
    else
        log_warning "Terraform service account already exists"
    fi

    # Grant required roles
    log_info "Granting IAM roles to Terraform service account..."
    gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
        --member="serviceAccount:$terraform_sa" \
        --role="roles/editor" \
        --quiet

    log_success "Service accounts configured"
    echo "$terraform_sa"
}

# Create Terraform state bucket
setup_terraform_state() {
    log_info "Setting up Terraform state storage..."

    local state_bucket="${GCP_PROJECT_ID}-terraform-state"

    # Create bucket if it doesn't exist
    if ! gsutil ls "gs://$state_bucket" 2>/dev/null; then
        log_info "Creating Terraform state bucket: $state_bucket"
        gsutil mb -l "$GCP_REGION" "gs://$state_bucket"

        # Enable versioning
        gsutil versioning set on "gs://$state_bucket"
        log_success "Terraform state bucket created with versioning enabled"
    else
        log_warning "Terraform state bucket already exists"
    fi
}

# Initialize Terraform
init_terraform() {
    log_info "Initializing Terraform..."

    cd "$TERRAFORM_DIR"

    terraform init \
        -backend-config="bucket=${GCP_PROJECT_ID}-terraform-state" \
        -backend-config="prefix=staging" \
        -upgrade

    log_success "Terraform initialized"
}

# Validate Terraform
validate_terraform() {
    log_info "Validating Terraform configuration..."

    cd "$TERRAFORM_DIR"

    terraform validate
    terraform fmt -check -recursive || true

    log_success "Terraform configuration is valid"
}

# Plan Terraform
plan_terraform() {
    log_info "Creating Terraform plan..."

    cd "$TERRAFORM_DIR"

    terraform plan \
        -var-file="env/staging.tfvars" \
        -out=tfplan \
        -no-color

    log_success "Terraform plan created"
}

# Apply Terraform
apply_terraform() {
    log_info "Applying Terraform configuration..."
    log_warning "This will create/modify GCP resources. Press ENTER to continue or Ctrl+C to cancel."
    read -r

    cd "$TERRAFORM_DIR"

    terraform apply -no-color -auto-approve tfplan

    log_success "Terraform apply completed"
}

# Verify deployment
verify_deployment() {
    log_info "Verifying deployment..."

    cd "$TERRAFORM_DIR"

    # Get outputs
    log_info "Infrastructure Endpoints:"
    terraform output deployment_summary 2>/dev/null || log_warning "Could not retrieve outputs"

    # Check GCS buckets
    log_info "Checking GCS buckets..."
    gsutil ls | grep "loa-staging-" || log_warning "Some buckets not found"

    # Check BigQuery datasets
    log_info "Checking BigQuery datasets..."
    bq ls | grep -E "raw|staging|marts" || log_warning "Some datasets not found"

    # Check Cloud Run services
    log_info "Checking Cloud Run services..."
    gcloud run services list --region="$GCP_REGION" || log_warning "No Cloud Run services found"

    log_success "Deployment verification complete"
}

# Main execution
main() {
    echo ""
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║   LOA Blueprint GCP Setup & Deployment Script           ║"
    echo "║   Region: London, UK (europe-west2)                    ║"
    echo "║   Environment: Staging                                 ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""

    validate_inputs
    setup_gcp_project
    setup_service_accounts
    setup_terraform_state
    init_terraform
    validate_terraform
    plan_terraform
    apply_terraform
    verify_deployment

    echo ""
    log_success "╔════════════════════════════════════════════════════════╗"
    log_success "║   GCP Setup & Deployment Complete!                    ║"
    log_success "║   Your LOA Blueprint is ready to use.                  ║"
    log_success "╚════════════════════════════════════════════════════════╝"
    echo ""
    log_info "Next steps:"
    log_info "  1. Run: ./testpipeline.sh"
    log_info "  2. Verify tests pass"
    log_info "  3. Deploy Cloud Functions: gcloud functions deploy ..."
    echo ""
}

# Run main function
main

