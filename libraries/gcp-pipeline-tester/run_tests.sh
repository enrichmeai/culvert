#!/bin/bash
# Run all tests for gcp-pipeline-tester

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "GCP Pipeline Tester - Running Tests"
echo "=========================================="

# Run unit tests
echo ""
echo "Running unit tests..."
PYTHONPATH=src pytest tests/unit -v --tb=short

echo ""
echo "=========================================="
echo "✅ All tests passed!"
echo "=========================================="

