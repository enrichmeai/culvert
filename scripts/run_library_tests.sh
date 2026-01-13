#!/bin/bash
# Script to run all library unit tests in the monorepo

set -e

PROJECT_ROOT=$(pwd)

echo "Running gcp-pipeline-core tests..."
cd "$PROJECT_ROOT/gcp-pipeline-libraries/gcp-pipeline-core"
PYTHONPATH=src python3 -m pytest tests/unit/ -q

echo "Running gcp-pipeline-beam tests..."
cd "$PROJECT_ROOT/gcp-pipeline-libraries/gcp-pipeline-beam"
PYTHONPATH=src:../gcp-pipeline-core/src python3 -m pytest tests/unit/ -q

echo "Running gcp-pipeline-orchestration tests..."
cd "$PROJECT_ROOT/gcp-pipeline-libraries/gcp-pipeline-orchestration"
PYTHONPATH=src:../gcp-pipeline-core/src python3 -m pytest tests/unit/ -q

echo "Running gcp-pipeline-tester tests..."
cd "$PROJECT_ROOT/gcp-pipeline-libraries/gcp-pipeline-tester"
PYTHONPATH=src python3 -m pytest tests/unit/ -q

echo "------------------------------------------------"
echo "All library tests passed! ✅"
echo "------------------------------------------------"
