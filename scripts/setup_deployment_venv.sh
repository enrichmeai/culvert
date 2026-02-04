#!/bin/bash
set -e

# Script to set up a local virtual environment for a deployment
# and install required libraries from the local monorepo.

if [ -z "$1" ]; then
    echo "Usage: $0 <deployment-name>"
    echo "Example: $0 loa-ingestion"
    exit 1
fi

DEPLOYMENT_NAME=$1
PROJECT_ROOT=$(pwd)
DEPLOYMENT_PATH="$PROJECT_ROOT/deployments/$DEPLOYMENT_NAME"

if [ ! -d "$DEPLOYMENT_PATH" ]; then
    echo "Error: Deployment '$DEPLOYMENT_NAME' not found in deployments/."
    exit 1
fi

echo "Setting up venv for $DEPLOYMENT_NAME..."

cd "$DEPLOYMENT_PATH"

# Remove existing venv if it exists
if [ -d "venv" ]; then
    echo "Removing existing venv..."
    rm -rf venv
fi

# Create new venv
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Determine which libraries to install based on pyproject.toml
# This is a simple heuristic: check for gcp-pipeline-* in dependencies
echo "Installing monorepo libraries..."

# List of all possible libraries in the monorepo
ALL_LIBS=("gcp-pipeline-core" "gcp-pipeline-beam" "gcp-pipeline-orchestration" "gcp-pipeline-transform" "gcp-pipeline-tester")

for lib in "${ALL_LIBS[@]}"; do
    if grep -q "$lib" pyproject.toml; then
        echo "Detected dependency: $lib. Installing from local monorepo..."
        pip install -e "$PROJECT_ROOT/gcp-pipeline-libraries/$lib"
    fi
done

# Install the deployment itself in editable mode with dev dependencies
echo "Installing $DEPLOYMENT_NAME..."
pip install -e ".[dev]"

echo "------------------------------------------------"
echo "Setup complete for $DEPLOYMENT_NAME"
echo "To activate the environment, run:"
echo "source deployments/$DEPLOYMENT_NAME/venv/bin/activate"
echo "------------------------------------------------"
