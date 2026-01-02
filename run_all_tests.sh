#!/bin/bash
# run_all_tests.sh - Runs library, EM, and LOA tests in isolation
#
# Usage:
#   ./run_all_tests.sh           # Run all tests
#   ./run_all_tests.sh library   # Run only library tests
#   ./run_all_tests.sh em        # Run only EM tests
#   ./run_all_tests.sh loa       # Run only LOA tests
#
# Why run separately?
#   Python caches imported modules. Running tests in separate pytest
#   invocations ensures clean module state and proper mock behavior.

set -e
cd "$(dirname "$0")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color


run_library_tests() {
    echo ""
    echo -e "${YELLOW}==========================================${NC}"
    echo -e "${YELLOW}Running Library Tests (gdw_data_core)${NC}"
    echo -e "${YELLOW}==========================================${NC}"
    echo ""

    PYTHONPATH=.:./gdw_data_core pytest gdw_data_core/tests -v --tb=short

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Library tests passed${NC}"
    else
        echo -e "${RED}❌ Library tests failed${NC}"
        exit 1
    fi
}

run_em_tests() {
    echo ""
    echo -e "${YELLOW}==========================================${NC}"
    echo -e "${YELLOW}Running EM Deployment Tests${NC}"
    echo -e "${YELLOW}==========================================${NC}"
    echo ""

    PYTHONPATH=.:./gdw_data_core:./deployments pytest deployments/em/tests -v --tb=short

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ EM tests passed${NC}"
    else
        echo -e "${RED}❌ EM tests failed${NC}"
        exit 1
    fi
}

run_loa_tests() {
    echo ""
    echo -e "${YELLOW}==========================================${NC}"
    echo -e "${YELLOW}Running LOA Deployment Tests${NC}"
    echo -e "${YELLOW}==========================================${NC}"
    echo ""

    PYTHONPATH=.:./gdw_data_core:./deployments pytest deployments/loa/tests -v --tb=short

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ LOA tests passed${NC}"
    else
        echo -e "${RED}❌ LOA tests failed${NC}"
        exit 1
    fi
}

# Main execution
case "${1:-all}" in
    library)
        run_library_tests
        ;;
    em)
        run_em_tests
        ;;
    loa)
        run_loa_tests
        ;;
    all)
        run_library_tests
        run_em_tests
        run_loa_tests

        echo ""
        echo -e "${GREEN}==========================================${NC}"
        echo -e "${GREEN}✅ All tests passed!${NC}"
        echo -e "${GREEN}==========================================${NC}"
        echo ""
        echo "Test Summary:"
        echo "  - Library (gdw_data_core): ✅"
        echo "  - EM Deployment:           ✅"
        echo "  - LOA Deployment:          ✅"
        ;;
    *)
        echo "Usage: $0 [library|em|loa|all]"
        echo ""
        echo "Options:"
        echo "  library  - Run only gdw_data_core library tests"
        echo "  em       - Run only EM deployment tests"
        echo "  loa      - Run only LOA deployment tests"
        echo "  all      - Run all tests (default)"
        exit 1
        ;;
esac

