#!/bin/bash

################################################################################
# Deployment Validation Script
#
# Validates infrastructure, GitHub workflow, and test harness readiness
# Usage: ./validate_deployment.sh
################################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
PASSED=0
FAILED=0

# Helper functions
print_header() {
    echo -e "\n${BLUE}════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════${NC}\n"
}

print_check() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED++))
}

print_error() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED++))
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# ============================================================================
# Section 1: Terraform Validation
# ============================================================================

print_header "TERRAFORM INFRASTRUCTURE VALIDATION"

# Check main.tf exists
if [ -f "infrastructure/terraform/main.tf" ]; then
    print_check "main.tf exists"
else
    print_error "main.tf not found"
fi

# Check variables.tf exists
if [ -f "infrastructure/terraform/variables.tf" ]; then
    print_check "variables.tf exists"
else
    print_error "variables.tf not found"
fi

# Check outputs.tf exists
if [ -f "infrastructure/terraform/outputs.tf" ]; then
    print_check "outputs.tf exists"
else
    print_error "outputs.tf not found"
fi

# Validate Terraform syntax (if terraform installed)
if command -v terraform &> /dev/null; then
    cd infrastructure/terraform
    if terraform validate &> /dev/null; then
        print_check "Terraform syntax valid"
    else
        print_error "Terraform syntax invalid"
    fi
    cd ../../
else
    print_warning "Terraform CLI not installed - skipping syntax check"
fi

# Check for required providers in main.tf
if grep -q "terraform {" infrastructure/terraform/main.tf; then
    print_check "Terraform block configured"
else
    print_error "Terraform block not found"
fi

if grep -q 'required_providers' infrastructure/terraform/main.tf; then
    print_check "Providers configured"
else
    print_error "Providers not configured"
fi

# Check GCP configuration
if grep -q 'provider "google"' infrastructure/terraform/main.tf; then
    print_check "Google provider configured"
else
    print_error "Google provider not configured"
fi

# ============================================================================
# Section 2: GitHub Workflow Validation
# ============================================================================

print_header "GITHUB ACTIONS WORKFLOW VALIDATION"

WORKFLOW_FILE=".github/workflows/gcp-deployment-tests.yml"

# Check workflow file exists
if [ -f "$WORKFLOW_FILE" ]; then
    print_check "Workflow file exists"
else
    print_error "Workflow file not found"
fi

# Check workflow has required jobs
if grep -q "unit-tests:" "$WORKFLOW_FILE"; then
    print_check "Unit tests job configured"
else
    print_error "Unit tests job not found"
fi

if grep -q "integration-tests:" "$WORKFLOW_FILE"; then
    print_check "Integration tests job configured"
else
    print_error "Integration tests job not found"
fi

if grep -q "dag-tests:" "$WORKFLOW_FILE"; then
    print_check "DAG tests job configured"
else
    print_error "DAG tests job not found"
fi

if grep -q "code-quality:" "$WORKFLOW_FILE"; then
    print_check "Code quality job configured"
else
    print_error "Code quality job not found"
fi

if grep -q "security-scan:" "$WORKFLOW_FILE"; then
    print_check "Security scan job configured"
else
    print_error "Security scan job not found"
fi

# Check trigger events
if grep -q "on:" "$WORKFLOW_FILE"; then
    print_check "Trigger events configured"
else
    print_error "Trigger events not configured"
fi

# Check for scheduled run
if grep -q "schedule:" "$WORKFLOW_FILE"; then
    print_check "Scheduled runs configured"
else
    print_error "Scheduled runs not configured"
fi

# Check Python version
if grep -q "PYTHON_VERSION" "$WORKFLOW_FILE"; then
    print_check "Python version configured"
else
    print_error "Python version not configured"
fi

# ============================================================================
# Section 3: Test Harness Validation
# ============================================================================

print_header "TEST HARNESS VALIDATION"

# Check pytest.ini exists
if [ -f "blueprint/pytest.ini" ]; then
    print_check "pytest.ini exists"
else
    print_error "pytest.ini not found"
fi

# Check test directories exist
if [ -d "blueprint/components/tests/unit" ]; then
    print_check "Unit tests directory exists"
else
    print_error "Unit tests directory not found"
fi

if [ -d "blueprint/components/tests/integration" ]; then
    print_check "Integration tests directory exists"
else
    print_error "Integration tests directory not found"
fi

# Check test files exist
if [ -f "blueprint/components/tests/unit/orchestration/test_dag_deployment.py" ]; then
    print_check "DAG deployment test file exists"
else
    print_error "DAG deployment test file not found"
fi

if [ -f "blueprint/components/tests/integration/test_gcp_clients.py" ]; then
    print_check "GCP clients test file exists"
else
    print_error "GCP clients test file not found"
fi

if [ -f "blueprint/components/tests/integration/conftest.py" ]; then
    print_check "Integration conftest.py exists"
else
    print_error "Integration conftest.py not found"
fi

# Check pytest markers configured
if grep -q "markers =" blueprint/pytest.ini; then
    print_check "pytest markers configured"
else
    print_error "pytest markers not configured"
fi

# ============================================================================
# Section 4: Dependencies Validation
# ============================================================================

print_header "DEPENDENCIES VALIDATION"

# Check requirements files exist
if [ -f "blueprint/setup/requirements.txt" ]; then
    print_check "requirements.txt exists"
else
    print_error "requirements.txt not found"
fi

if [ -f "blueprint/setup/requirements-test.txt" ]; then
    print_check "requirements-test.txt exists"
else
    print_error "requirements-test.txt not found"
fi

# Check key test dependencies in requirements
if grep -q "pytest" blueprint/setup/requirements-test.txt; then
    print_check "pytest in requirements-test.txt"
else
    print_error "pytest not in requirements-test.txt"
fi

if grep -q "google-cloud" blueprint/setup/requirements-test.txt; then
    print_check "google-cloud libraries in requirements"
else
    print_error "google-cloud libraries not in requirements"
fi

# ============================================================================
# Section 5: Documentation Validation
# ============================================================================

print_header "DOCUMENTATION VALIDATION"

# Check key documentation exists
if [ -f "docs/testing/INFRASTRUCTURE_VALIDATION_REPORT.md" ]; then
    print_check "Infrastructure validation report exists"
else
    print_error "Infrastructure validation report not found"
fi

if [ -f "docs/testing/COMPLETE_TESTING_GUIDE.md" ]; then
    print_check "GCP deployment guide exists"
else
    print_error "GCP deployment guide not found"
fi

if [ -f "README.md" ]; then
    print_check "README.md exists"
else
    print_warning "README.md not found (optional)"
fi

# ============================================================================
# Section 6: Test Execution (if pytest available)
# ============================================================================

print_header "TEST EXECUTION VALIDATION"

if command -v pytest &> /dev/null; then
    echo "Running test validation..."

    # Try to collect tests
    cd blueprint
    TEST_COUNT=$(pytest --collect-only -q components/tests/unit/orchestration/test_dag_deployment.py 2>/dev/null | wc -l)

    if [ "$TEST_COUNT" -gt 0 ]; then
        print_check "Tests collectable: $TEST_COUNT tests found"
    else
        print_error "No tests collected"
    fi

    cd ..
else
    print_warning "pytest not installed - skipping test execution check"
fi

# ============================================================================
# Section 7: Security Validation
# ============================================================================

print_header "SECURITY VALIDATION"

# Check for hardcoded secrets
if ! grep -r "AKIA" . 2>/dev/null | grep -v ".git" | grep -v ".venv" > /dev/null 2>&1; then
    print_check "No hardcoded AWS keys found"
else
    print_error "Potential hardcoded credentials found"
fi

if ! grep -r "ghp_" . 2>/dev/null | grep -v ".git" | grep -v ".venv" > /dev/null 2>&1; then
    print_check "No hardcoded GitHub tokens found"
else
    print_error "Potential hardcoded GitHub tokens found"
fi

# Check .gitignore exists
if [ -f ".gitignore" ]; then
    print_check ".gitignore exists"
else
    print_warning ".gitignore not found (recommended)"
fi

# ============================================================================
# Summary
# ============================================================================

print_header "VALIDATION SUMMARY"

TOTAL=$((PASSED + FAILED))

echo "Passed: ${GREEN}$PASSED${NC}"
echo "Failed: ${RED}$FAILED${NC}"
echo "Total:  $TOTAL"

if [ $FAILED -eq 0 ]; then
    echo -e "\n${GREEN}✓ ALL VALIDATION CHECKS PASSED${NC}"
    echo -e "${GREEN}Status: READY FOR DEPLOYMENT${NC}\n"
    exit 0
else
    echo -e "\n${RED}✗ VALIDATION FAILED${NC}"
    echo -e "${RED}Please fix the above issues before deployment${NC}\n"
    exit 1
fi

