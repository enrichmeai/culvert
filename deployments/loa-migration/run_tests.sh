#!/bin/bash
# Run LOA pipeline tests
# Usage: ./run_tests.sh [optional pytest args]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Add src to PYTHONPATH and also add libraries
export PYTHONPATH="$SCRIPT_DIR/src:$SCRIPT_DIR/../../libraries/gcp-pipeline-builder/src:$SCRIPT_DIR/../../libraries/gcp-pipeline-tester/src:$PYTHONPATH"

echo "Running LOA pipeline tests..."
echo "PYTHONPATH: $PYTHONPATH"

pytest tests/ "$@"

