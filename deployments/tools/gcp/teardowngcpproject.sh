#!/bin/bash

# teardowngcpproject.sh - Complete GCP Project Teardown Script
#
# This script safely removes all LOA Blueprint resources from GCP and optionally
# deletes the entire GCP project.
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - terraform installed (v1.5.0+)
#   - Must be run from project root directory
#
# Usage:
#   ./teardowngcpproject.sh <GCP_PROJECT_ID> [--delete-project]
#
# Examples:
#   ./teardowngcpproject.sh loa-staging-project-123              # Destroy resources only
#   ./teardowngcpproject.sh loa-staging-project-123 --delete-project  # Destroy + delete project

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Script configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TERRAFORM_DIR="$PROJECT_ROOT/infrastructure/terraform"
GCP_PROJECT_ID="${1:-}"
DELETE_PROJECT="${2:-}"

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

# Confirm destructive action
confirm_action() {
    local prompt="$1"
    local response

    echo ""
    log_warning "⚠️  DESTRUCTIVE ACTION ⚠️"
    echo -e "${RED}$prompt${NC}"
    echo "Type 'yes' to confirm, anything else to cancel:"
    read -r response

    if [ "$response" != "yes" ]; then
        log_info "Teardown cancelled"
        exit 0
    fi
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

# Stop running services
stop_services() {
    log_info "Stopping running services..."

    # Set GCP project
    gcloud config set project "$GCP_PROJECT_ID"

    # Stop Cloud Run services
    log_info "Stopping Cloud Run services..."
    gcloud run services list --region=europe-west2 --format="value(name)" 2>/dev/null | while read -r service; do
        log_warning "Deleting Cloud Run service: $service"
        gcloud run services delete "$service" --region=europe-west2 --quiet 2>/dev/null || true
    done

    # Stop Cloud Functions
    log_info "Deleting Cloud Functions..."
    gcloud functions list --format="value(name)" 2>/dev/null | while read -r function; do
        log_warning "Deleting Cloud Function: $function"
        gcloud functions delete "$function" --quiet 2>/dev/null || true
    done

    log_success "Services stopped"
}

# Destroy Terraform resources
destroy_terraform() {
    log_info "Destroying Terraform-managed resources..."

    cd "$TERRAFORM_DIR"

    # Initialize Terraform (in case state is missing)
    terraform init \
        -backend-config="bucket=${GCP_PROJECT_ID}-terraform-state" \
        -backend-config="prefix=staging" \
        -upgrade \
        -reconfigure 2>/dev/null || true

    # Destroy resources
    terraform destroy \
        -var-file="env/staging.tfvars" \
        -no-color \
        -auto-approve

    log_success "Terraform resources destroyed"
}

# Delete GCP project
delete_project() {
    if [ "$DELETE_PROJECT" != "--delete-project" ]; then
        return 0
    fi

    log_warning "Project deletion requested"
    confirm_action "This will DELETE the entire GCP project: $GCP_PROJECT_ID"

    log_info "Disabling billing for project..."
    local billing_account=$(gcloud billing projects describe "$GCP_PROJECT_ID" --format='value(billingAccountName)' 2>/dev/null || echo "")

    if [ -n "$billing_account" ]; then
        gcloud billing projects unlink "$GCP_PROJECT_ID" --quiet 2>/dev/null || true
    fi

    log_warning "Deleting GCP project: $GCP_PROJECT_ID"
    gcloud projects delete "$GCP_PROJECT_ID" --quiet

    log_success "GCP project deleted"
}

# Clean up local terraform state
cleanup_local_state() {
    log_info "Cleaning up local Terraform state..."

    cd "$TERRAFORM_DIR"

    rm -f tfplan
    rm -f .terraform.lock.hcl
    rm -rf .terraform/

    log_success "Local Terraform state cleaned"
}

# Main execution
main() {
    echo ""
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║   LOA Blueprint GCP Teardown Script                    ║"
    echo "║   ⚠️  DESTRUCTIVE OPERATION ⚠️                         ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""

    validate_inputs

    confirm_action "This will DESTROY all LOA Blueprint resources in project: $GCP_PROJECT_ID"

    stop_services
    destroy_terraform
    delete_project
    cleanup_local_state

    echo ""
    log_success "╔════════════════════════════════════════════════════════╗"
    log_success "║   GCP Project Teardown Complete!                       ║"
    log_success "║   All resources have been removed.                     ║"
    log_success "╚════════════════════════════════════════════════════════╝"
    echo ""
}

# Run main function
main

