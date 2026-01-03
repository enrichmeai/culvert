#!/bin/bash
# Run EM pipeline tests
# Usage: ./run_tests.sh [optional pytest args]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Add src to PYTHONPATH and also add libraries
export PYTHONPATH="$SCRIPT_DIR/src:$SCRIPT_DIR/../../libraries/gcp-pipeline-builder/src:$SCRIPT_DIR/../../libraries/gcp-pipeline-tester/src:$PYTHONPATH"

echo "PYTHONPATH: $PYTHONPATH"
echo "Running EM pipeline tests..."

cd "$SCRIPT_DIR"
pytest tests/ "$@"

