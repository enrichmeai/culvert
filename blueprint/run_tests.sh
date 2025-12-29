#!/bin/bash

################################################################################
# LOA Blueprint Test Runner Script
# Purpose: Run all pytest tests with coverage reporting
# Usage: ./run_tests.sh [test_pattern] [verbose]
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Flags
VERBOSE=false
TEST_PATTERN=""
SHOW_HELP=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            SHOW_HELP=true
            shift
            ;;
        *)
            TEST_PATTERN=$1
            shift
            ;;
    esac
done

# Display help
if [ "$SHOW_HELP" = true ]; then
    cat << EOF
${BLUE}LOA Blueprint Test Runner${NC}

Usage: ./run_tests.sh [options] [test_pattern]

Options:
    -v, --verbose       Show detailed output for each test
    -h, --help          Display this help message

Examples:
    ./run_tests.sh                          # Run all tests
    ./run_tests.sh test_pipeline_router     # Run specific test file
    ./run_tests.sh -v                       # Run all tests with verbose output
    ./run_tests.sh -v test_data_factory     # Run specific test with verbose output

Test Files:
    - test_pipeline_router.py   (Pipeline routing logic)
    - test_data_factory.py       (Data generation)
    - test_audit.py              (Audit functionality)
    - test_data_quality.py       (Data quality checks)
    - test_error_handling.py     (Error handling)
    - test_io_utils.py           (I/O utilities)

EOF
    exit 0
fi

################################################################################
# Print header
################################################################################
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}           ${BLUE}LOA Blueprint Test Runner${NC}                          ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}              Running pytest tests suite                    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

################################################################################
# Check dependencies
################################################################################
echo -e "${YELLOW}📋 Checking dependencies...${NC}"

if ! command -v pytest &> /dev/null; then
    echo -e "${RED}❌ pytest not found. Installing...${NC}"
    pip install pytest pytest-cov pytest-xdist -q
fi

echo -e "${GREEN}✅ Dependencies check passed${NC}"
echo ""

################################################################################
# Run tests
################################################################################

# Build pytest command
PYTEST_ARGS=("-c" "blueprint/pytest.ini" "-v" "--cov=blueprint/components" "--cov-report=html:htmlcov" "--cov-report=term-missing")

# Set PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)/blueprint

# Add verbose output if requested
if [ "$VERBOSE" = true ]; then
    PYTEST_ARGS+=("-s")
fi

# Add test pattern if specified
if [ -n "$TEST_PATTERN" ]; then
    if [ -d "blueprint/components/tests/$TEST_PATTERN" ]; then
        PYTEST_ARGS+=("blueprint/components/tests/$TEST_PATTERN/")
    elif [ -f "blueprint/components/tests/unit/$TEST_PATTERN.py" ]; then
        PYTEST_ARGS+=("blueprint/components/tests/unit/$TEST_PATTERN.py")
    elif [ -f "blueprint/components/tests/integration/$TEST_PATTERN.py" ]; then
        PYTEST_ARGS+=("blueprint/components/tests/integration/$TEST_PATTERN.py")
    elif [ -f "blueprint/components/tests/dag/$TEST_PATTERN.py" ]; then
        PYTEST_ARGS+=("blueprint/components/tests/dag/$TEST_PATTERN.py")
    else
        echo -e "${RED}❌ Test file or directory $TEST_PATTERN not found in components/tests folders.${NC}"
        exit 1
    fi
fi

echo -e "${YELLOW}🧪 Test 1/3: Pipeline Router Tests${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f "blueprint/components/tests/unit/loa_pipelines/test_pipeline_router.py" ]; then
    pytest blueprint/components/tests/unit/loa_pipelines/test_pipeline_router.py -v --cov=blueprint/components/loa_pipelines/pipeline_router --cov-report=term-missing "${PYTEST_ARGS[@]:0:3}" 2>&1 | head -200
    TEST1_EXIT=$?
else
    echo -e "${YELLOW}⚠️  test_pipeline_router.py not found, skipping...${NC}"
    TEST1_EXIT=0
fi
echo ""

if [ $TEST1_EXIT -eq 0 ]; then
    echo -e "${GREEN}✅ Pipeline Router Tests PASSED${NC}"
else
    echo -e "${RED}❌ Pipeline Router Tests FAILED${NC}"
fi
echo ""

echo -e "${YELLOW}🧪 Test 2/3: Dataflow Tests${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f "blueprint/components/tests/unit/test_dataflow_flow.py" ]; then
    pytest blueprint/components/tests/unit/test_dataflow_flow.py -v -s --cov=credit.examples 2>&1 | head -200
    TEST2_EXIT=$?
    if [ $TEST2_EXIT -eq 0 ]; then
        echo -e "${GREEN}✅ Dataflow Tests PASSED${NC}"
    else
        echo -e "${RED}❌ Dataflow Tests FAILED or NOT FOUND${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  test_dataflow_flow.py not found, skipping...${NC}"
    TEST2_EXIT=0
fi
echo ""

echo -e "${YELLOW}🧪 Test 3/3: DAG Structure Tests${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ -f "blueprint/components/tests/unit/test_dag_structure.py" ]; then
    pytest blueprint/components/tests/unit/test_dag_structure.py -v --cov=blueprint/components/loa_pipelines/dag_template 2>&1 | head -200
    TEST3_EXIT=$?
    if [ $TEST3_EXIT -eq 0 ]; then
        echo -e "${GREEN}✅ DAG Structure Tests PASSED${NC}"
    else
        echo -e "${RED}❌ DAG Structure Tests FAILED or NOT FOUND${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  test_dag_structure.py not found, skipping...${NC}"
    TEST3_EXIT=0
fi
echo ""

################################################################################
# Run all tests together for comprehensive coverage
################################################################################
echo -e "${YELLOW}📊 Running all tests for coverage report...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -n "$TEST_PATTERN" ]; then
    pytest "blueprint/components/tests/unit/$TEST_PATTERN.py" -v --cov=blueprint/components --cov-report=term-missing --cov-report=html:htmlcov
    ALL_EXIT=$?
else
    pytest blueprint/components/tests/unit/ -v --cov=blueprint/components --cov-report=term-missing --cov-report=html:htmlcov
    ALL_EXIT=$?
fi

echo ""

################################################################################
# Print summary
################################################################################
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                    ${YELLOW}TEST EXECUTION SUMMARY${NC}                       ${BLUE}║${NC}"
echo -e "${BLUE}╠════════════════════════════════════════════════════════════════╣${NC}"

if [ $TEST1_EXIT -eq 0 ]; then
    echo -e "${BLUE}║${NC} ${GREEN}✅ Pipeline Router Tests${NC}                              ${BLUE}║${NC}"
else
    echo -e "${BLUE}║${NC} ${RED}❌ Pipeline Router Tests${NC}                              ${BLUE}║${NC}"
fi

if [ $TEST2_EXIT -eq 0 ]; then
    echo -e "${BLUE}║${NC} ${GREEN}✅ Dataflow Tests${NC}                                    ${BLUE}║${NC}"
else
    echo -e "${BLUE}║${NC} ${RED}❌ Dataflow Tests${NC}                                    ${BLUE}║${NC}"
fi

if [ $TEST3_EXIT -eq 0 ]; then
    echo -e "${BLUE}║${NC} ${GREEN}✅ DAG Structure Tests${NC}                               ${BLUE}║${NC}"
else
    echo -e "${BLUE}║${NC} ${RED}❌ DAG Structure Tests${NC}                               ${BLUE}║${NC}"
fi

echo -e "${BLUE}╠════════════════════════════════════════════════════════════════╣${NC}"

if [ -f "htmlcov/index.html" ]; then
    echo -e "${BLUE}║${NC} ${GREEN}📊 Coverage report generated${NC}                          ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}    File: htmlcov/index.html                         ${BLUE}║${NC}"
else
    echo -e "${BLUE}║${NC} ${YELLOW}⚠️  Coverage report not found${NC}                        ${BLUE}║${NC}"
fi

echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

################################################################################
# Determine exit code
################################################################################
if [ $TEST1_EXIT -eq 0 ] && [ $TEST2_EXIT -eq 0 ] && [ $TEST3_EXIT -eq 0 ] && [ $ALL_EXIT -eq 0 ]; then
    echo -e "${GREEN}✅ All tests PASSED!${NC}"
    echo ""
    exit 0
else
    echo -e "${RED}❌ Some tests FAILED!${NC}"
    echo ""
    exit 1
fi

