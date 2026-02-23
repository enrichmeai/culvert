#!/bin/bash
export ROOT_DIR=$(pwd)
export PYTHONPATH=$PYTHONPATH:$ROOT_DIR/gcp-pipeline-libraries/gcp-pipeline-core/src:$ROOT_DIR/gcp-pipeline-libraries/gcp-pipeline-beam/src:$ROOT_DIR/gcp-pipeline-libraries/gcp-pipeline-tester/src:$ROOT_DIR/gcp-pipeline-libraries/gcp-pipeline-orchestration/src

echo "Running application1-ingestion tests..."
cd deployments/application1-ingestion && PYTHONPATH=$PYTHONPATH:$(pwd)/src pytest tests/unit/
cd $ROOT_DIR

echo "Running application2-ingestion tests..."
cd deployments/application2-ingestion && PYTHONPATH=$PYTHONPATH:$(pwd)/src pytest tests/unit/
cd $ROOT_DIR

echo "Running application1-orchestration tests..."
cd deployments/application1-orchestration && PYTHONPATH=$PYTHONPATH:$(pwd)/src pytest tests/
cd $ROOT_DIR

echo "Running application2-orchestration tests..."
cd deployments/application2-orchestration && PYTHONPATH=$PYTHONPATH:$(pwd)/src pytest tests/
cd $ROOT_DIR
