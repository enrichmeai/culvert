#!/bin/bash
export ROOT_DIR=$(pwd)
export PYTHONPATH=$PYTHONPATH:$ROOT_DIR/gcp-pipeline-libraries/gcp-pipeline-core/src:$ROOT_DIR/gcp-pipeline-libraries/gcp-pipeline-beam/src:$ROOT_DIR/gcp-pipeline-libraries/gcp-pipeline-tester/src:$ROOT_DIR/gcp-pipeline-libraries/gcp-pipeline-orchestration/src

echo "Running generic-ingestion tests..."
cd deployments/generic-ingestion && PYTHONPATH=$PYTHONPATH:$(pwd)/src pytest tests/unit/
cd $ROOT_DIR

echo "Running generic-ingestion tests..."
cd deployments/generic-ingestion && PYTHONPATH=$PYTHONPATH:$(pwd)/src pytest tests/unit/
cd $ROOT_DIR

echo "Running generic-orchestration tests..."
cd deployments/generic-orchestration && PYTHONPATH=$PYTHONPATH:$(pwd)/src pytest tests/
cd $ROOT_DIR

echo "Running generic-orchestration tests..."
cd deployments/generic-orchestration && PYTHONPATH=$PYTHONPATH:$(pwd)/src pytest tests/
cd $ROOT_DIR
