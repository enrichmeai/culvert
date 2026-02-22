#!/bin/bash
# Script to run all library unit tests in the monorepo

set -e

PROJECT_ROOT=$(pwd)

echo "Running gcp-pipeline-core tests..."
cd "$PROJECT_ROOT/gcp-pipeline-libraries/gcp-pipeline-core"
python3 -m pytest tests/unit/ -v

echo "Running gcp-pipeline-beam tests..."
cd "$PROJECT_ROOT/gcp-pipeline-libraries/gcp-pipeline-beam"
python3 -m pytest tests/unit/ -v

echo "Running gcp-pipeline-orchestration tests..."
cd "$PROJECT_ROOT/gcp-pipeline-libraries/gcp-pipeline-orchestration"
python3 -m pytest tests/unit/ -v

echo "Running gcp-pipeline-transform tests..."
cd "$PROJECT_ROOT/gcp-pipeline-libraries/gcp-pipeline-transform"
python3 -m pytest tests/unit/ -v

echo "Running gcp-pipeline-tester tests..."
cd "$PROJECT_ROOT/gcp-pipeline-libraries/gcp-pipeline-tester"
python3 -m pytest tests/unit/ -v

echo "------------------------------------------------"
echo "All library tests passed! ✅"
echo "------------------------------------------------"
