#!/bin/bash
# Example usage of the Local Airflow DAG Test Script
# This file shows various ways to run test_airflow_locally.py

set -e

# Colors for output
GREEN='\033[92m'
BLUE='\033[94m'
CYAN='\033[96m'
BOLD='\033[1m'
END='\033[0m'

echo -e "${BLUE}${BOLD}════════════════════════════════════════════════════════════════${END}"
echo -e "${BLUE}${BOLD}Local Airflow DAG Test Examples${END}"
echo -e "${BLUE}${BOLD}════════════════════════════════════════════════════════════════${END}"
echo ""

# Function to print example header
print_example() {
    echo -e "${CYAN}${BOLD}Example $1: $2${END}"
    echo ""
}

# Check if we're in the right directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
if [ ! -f "$SCRIPT_DIR/test_airflow_locally.py" ]; then
    echo "❌ Error: test_airflow_locally.py not found"
    echo "Expected location: $SCRIPT_DIR/test_airflow_locally.py"
    exit 1
fi

# Example 1: Basic validation
print_example "1" "Basic DAG Validation"
echo -e "${CYAN}Command:${END} python $SCRIPT_DIR/test_airflow_locally.py"
echo ""
python "$SCRIPT_DIR/test_airflow_locally.py"
echo ""

# Example 2: Verbose output
print_example "2" "Verbose Output (with detailed info)"
echo -e "${CYAN}Command:${END} python $SCRIPT_DIR/test_airflow_locally.py --verbose"
echo ""
python "$SCRIPT_DIR/test_airflow_locally.py" --verbose 2>&1 | head -20
echo "... (output truncated for brevity)"
echo ""

# Example 3: JSON output
print_example "3" "JSON Output (for automation/CI-CD)"
echo -e "${CYAN}Command:${END} python $SCRIPT_DIR/test_airflow_locally.py --output json"
echo ""
python "$SCRIPT_DIR/test_airflow_locally.py" --output json 2>&1 | head -30
echo "... (output truncated for brevity)"
echo ""

# Example 4: Silent validation
print_example "4" "Silent Validation (check only)"
echo -e "${CYAN}Command:${END} python $SCRIPT_DIR/test_airflow_locally.py --validate-only"
echo ""
if python "$SCRIPT_DIR/test_airflow_locally.py" --validate-only 2>/dev/null; then
    echo -e "${GREEN}✅ DAG validation passed${END}"
else
    echo -e "❌ DAG validation failed"
fi
echo ""

# Example 5: Check exit code
print_example "5" "Check Exit Code"
echo -e "${CYAN}Command:${END} python $SCRIPT_DIR/test_airflow_locally.py && echo 'Success' || echo 'Failed'"
echo ""
if python "$SCRIPT_DIR/test_airflow_locally.py" > /dev/null 2>&1; then
    echo -e "${GREEN}Exit code: 0 (Success)${END}"
else
    EXIT_CODE=$?
    echo -e "Exit code: $EXIT_CODE (Failed)"
fi
echo ""

# Example 6: Save JSON report
print_example "6" "Save JSON Report (for documentation)"
echo -e "${CYAN}Command:${END} python $SCRIPT_DIR/test_airflow_locally.py --output json > dag_report.json"
echo ""
python "$SCRIPT_DIR/test_airflow_locally.py" --output json > /tmp/dag_report.json 2>/dev/null
echo -e "${GREEN}✅ Report saved to /tmp/dag_report.json${END}"
echo "Report size: $(wc -c < /tmp/dag_report.json) bytes"
echo ""

# Example 7: Combine with other checks
print_example "7" "Combined with other validation"
echo -e "${CYAN}Script snippet:${END}"
echo "#!/bin/bash"
echo "# Pre-deployment validation"
echo "python $SCRIPT_DIR/test_airflow_locally.py --validate-only || exit 1"
echo "pytest components/tests/unit/ -v || exit 1"
echo "echo 'All checks passed!'"
echo ""

# Summary
echo -e "${BLUE}${BOLD}════════════════════════════════════════════════════════════════${END}"
echo -e "${GREEN}${BOLD}Summary${END}"
echo -e "${BLUE}${BOLD}════════════════════════════════════════════════════════════════${END}"
echo ""
echo "The test_airflow_locally.py script provides:"
echo ""
echo "  ✅ Fast validation (no Airflow services needed)"
echo "  ✅ Multiple output formats (text, JSON)"
echo "  ✅ CI/CD integration (proper exit codes)"
echo "  ✅ Detailed error messages"
echo "  ✅ Task structure validation"
echo "  ✅ Dependency validation"
echo ""
echo "Common use cases:"
echo ""
echo "  1. Pre-deployment check:"
echo "     python $SCRIPT_DIR/test_airflow_locally.py"
echo ""
echo "  2. CI/CD pipeline:"
echo "     python $SCRIPT_DIR/test_airflow_locally.py --validate-only"
echo ""
echo "  3. Generate report:"
echo "     python $SCRIPT_DIR/test_airflow_locally.py --output json > report.json"
echo ""
echo "  4. Debugging:"
echo "     python $SCRIPT_DIR/test_airflow_locally.py --verbose"
echo ""
echo -e "${GREEN}${BOLD}✅ Examples completed!${END}"
echo ""

