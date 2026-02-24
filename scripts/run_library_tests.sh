#!/bin/bash
# Script to run all library unit tests in the monorepo

set -e

PROJECT_ROOT=$(pwd)

echo "Running gcp-pipeline-core tests..."
cd "$PROJECT_ROOT/gcp-pipeline-libraries/gcp-pipeline-core"
PYTHONPATH=src python3 -m pytest tests/unit/ -v

echo "Running gcp-pipeline-beam tests..."
cd "$PROJECT_ROOT/gcp-pipeline-libraries/gcp-pipeline-beam"
PYTHONPATH=src:../gcp-pipeline-core/src python3 -m pytest tests/unit/ -v

echo "Running gcp-pipeline-orchestration tests..."
cd "$PROJECT_ROOT/gcp-pipeline-libraries/gcp-pipeline-orchestration"
PYTHONPATH=src:../gcp-pipeline-core/src python3 -m pytest tests/unit/ -v

echo "Running gcp-pipeline-transform tests..."
cd "$PROJECT_ROOT/gcp-pipeline-libraries/gcp-pipeline-transform"
PYTHONPATH=src:../gcp-pipeline-core/src python3 -m pytest tests/unit/ -v

echo "Running gcp-pipeline-tester tests..."
cd "$PROJECT_ROOT/gcp-pipeline-libraries/gcp-pipeline-tester"
PYTHONPATH=src:../gcp-pipeline-core/src python3 -m pytest tests/unit/ -v

echo "------------------------------------------------"
echo "All library tests passed! ✅"
echo "------------------------------------------------"
