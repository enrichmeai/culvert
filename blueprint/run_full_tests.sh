#!/bin/bash

#
# Enhanced Test Runner Script for Complete GCP Deployment Testing
#
# Usage:
#     ./run_full_tests.sh              # Run all tests
#     ./run_full_tests.sh --unit       # Unit tests only
#     ./run_full_tests.sh --integration # Integration tests only (mocked)
#     ./run_full_tests.sh --staging    # Staging GCP tests
#     ./run_full_tests.sh --performance # Performance & chaos tests
#     ./run_full_tests.sh --report     # Generate HTML report
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/.."
cd "$PROJECT_ROOT"

# Default values
TEST_PHASE="full"
VERBOSE=false
COVERAGE_REPORT=false
REPORT_HTML=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --unit)
            TEST_PHASE="unit"
            shift
            ;;
        --integration)
            TEST_PHASE="integration"
            shift
            ;;
        --staging)
            TEST_PHASE="staging"
            shift
            ;;
        --performance)
            TEST_PHASE="performance"
            shift
            ;;
        --full)
            TEST_PHASE="full"
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --coverage)
            COVERAGE_REPORT=true
            shift
            ;;
        --report)
            REPORT_HTML=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--unit|--integration|--staging|--performance|--full|--verbose|--coverage|--report|--help]"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Helper functions
print_header() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC} $1"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo -e "${PURPLE}→${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

# Build pytest command
build_pytest_cmd() {
    local cmd="pytest"

    # Add verbose flag
    if [ "$VERBOSE" = true ]; then
        cmd="$cmd -vv"
    else
        cmd="$cmd -v"
    fi

    # Add coverage
    if [ "$COVERAGE_REPORT" = true ]; then
        cmd="$cmd --cov=blueprint/components --cov=gdw_data_core --cov-report=term-missing"
        if [ "$REPORT_HTML" = true ]; then
            cmd="$cmd --cov-report=html"
        fi
    fi

    echo "$cmd"
}

# Run unit tests
run_unit_tests() {
    print_header "UNIT TESTS (with mocked GCP services)"

    print_step "Running blueprint unit tests..."
    local cmd=$(build_pytest_cmd)
    $cmd blueprint/components/tests/unit/ -m "not requires_gcp"
    print_success "Blueprint unit tests passed"

    print_step "Running gdw_data_core unit tests..."
    $cmd gdw_data_core/tests/unit/ -m "not requires_gcp"
    print_success "GDW Data Core unit tests passed"
}

# Run integration tests (mocked)
run_integration_tests() {
    print_header "INTEGRATION TESTS (with mocked GCP services)"

    print_step "Running GCP client integration tests..."
    local cmd=$(build_pytest_cmd)
    $cmd blueprint/components/tests/integration/test_gcp_clients.py -m "integration"
    print_success "GCP client integration tests passed"

    print_step "Running DAG validation tests..."
    $cmd blueprint/components/tests/unit/orchestration/test_dag_deployment.py
    print_success "DAG validation tests passed"
}

# Run staging deployment tests
run_staging_tests() {
    print_header "STAGING GCP DEPLOYMENT TESTS"

    # Check environment variables
    if [ -z "$GCP_TEST_PROJECT" ]; then
        print_error "GCP_TEST_PROJECT environment variable not set"
        echo "Set it with: export GCP_TEST_PROJECT=your-staging-project"
        return 1
    fi

    if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
        print_error "GOOGLE_APPLICATION_CREDENTIALS environment variable not set"
        echo "Set it with: export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json"
        return 1
    fi

    print_step "Validating GCP deployment configuration..."
    local cmd=$(build_pytest_cmd)
    $cmd blueprint/components/tests/integration/test_gcp_deployment.py -m "requires_gcp"
    print_success "GCP deployment validation passed"
}

# Run performance & chaos tests
run_performance_tests() {
    print_header "PERFORMANCE & CHAOS TESTS"

    print_step "Running performance benchmarks..."
    local cmd=$(build_pytest_cmd)
    $cmd blueprint/components/tests/performance/ --benchmark-only
    print_success "Performance benchmarks completed"

    print_step "Running chaos engineering tests..."
    $cmd blueprint/components/tests/chaos/ -v
    print_success "Chaos engineering tests passed"
}

# Generate HTML report
generate_report() {
    print_header "GENERATING HTML REPORT"

    if [ -f "htmlcov/index.html" ]; then
        print_success "Coverage report generated: htmlcov/index.html"
        if command -v open &> /dev/null; then
            open htmlcov/index.html
        elif command -v xdg-open &> /dev/null; then
            xdg-open htmlcov/index.html
        fi
    fi
}

# Main execution
print_header "LOA Blueprint & GDW Core - GCP Deployment Testing"

print_step "Python version: $(python3 --version)"
print_step "Test phase: $TEST_PHASE"

case "$TEST_PHASE" in
    "unit")
        run_unit_tests
        ;;
    "integration")
        run_integration_tests
        ;;
    "staging")
        run_staging_tests
        ;;
    "performance")
        run_performance_tests
        ;;
    "full")
        run_unit_tests
        run_integration_tests

        if [ "$COVERAGE_REPORT" = true ]; then
            generate_report
        fi

        print_header "ALL TESTS PASSED!"
        print_success "Local and integration testing complete"
        echo ""
        echo -e "${CYAN}Next Steps:${NC}"
        echo "  1. Review test results above"
        if [ "$REPORT_HTML" = true ]; then
            echo "  2. Review coverage report: htmlcov/index.html"
        fi
        echo "  3. Run staging tests: $0 --staging"
        echo "  4. Run performance tests: $0 --performance"
        echo "  5. Proceed with GCP deployment"
        ;;
    *)
        print_error "Unknown test phase: $TEST_PHASE"
        exit 1
        ;;
esac

# Generate report if requested
if [ "$REPORT_HTML" = true ]; then
    generate_report
fi

print_success "Test run completed!"
exit 0

