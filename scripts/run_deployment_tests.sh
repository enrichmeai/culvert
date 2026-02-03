#!/bin/bash
export ROOT_DIR=$(pwd)
export PYTHONPATH=$PYTHONPATH:$ROOT_DIR/gcp-pipeline-libraries/gcp-pipeline-core/src:$ROOT_DIR/gcp-pipeline-libraries/gcp-pipeline-beam/src:$ROOT_DIR/gcp-pipeline-libraries/gcp-pipeline-tester/src:$ROOT_DIR/gcp-pipeline-libraries/gcp-pipeline-orchestration/src

echo "Running em-ingestion tests..."
cd deployments_embedded/em-ingestion && PYTHONPATH=$PYTHONPATH:$(pwd)/src pytest tests/unit/
cd $ROOT_DIR

echo "Running loa-ingestion tests..."
cd deployments_embedded/loa-ingestion && PYTHONPATH=$PYTHONPATH:$(pwd)/src pytest tests/unit/
cd $ROOT_DIR

echo "Running em-orchestration tests..."
cd deployments_embedded/em-orchestration && PYTHONPATH=$PYTHONPATH:$(pwd)/src pytest tests/
cd $ROOT_DIR

echo "Running loa-orchestration tests..."
cd deployments_embedded/loa-orchestration && PYTHONPATH=$PYTHONPATH:$(pwd)/src pytest tests/
cd $ROOT_DIR
