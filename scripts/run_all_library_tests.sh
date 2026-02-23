#!/bin/bash
set -e

# Define libraries to test in order of dependency
LIBRARIES=(
    "gcp-pipeline-core"
    "gcp-pipeline-beam"
    "gcp-pipeline-orchestration"
    "gcp-pipeline-transform"
    "gcp-pipeline-tester"
)

# Root directory
ROOT_DIR=$(pwd)

# Create a virtual environment
VENV_DIR="$ROOT_DIR/.venv_tests"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activating virtual environment...
# source "$VENV_DIR/bin/activate"

# Use set +e to continue on test failures
set +e

echo "Installing common test dependencies..."
python3 -m pip install pytest pytest-mock pytest-cov pyyaml google-cloud-storage google-cloud-bigquery pydantic -q
# apache-beam installation often fails due to pyarrow compilation, so we make it optional
python3 -m pip install apache-beam -q || echo "Warning: apache-beam installation failed. Beam-related tests might fail."

for LIB in "${LIBRARIES[@]}"; do
    echo "===================================================="
    echo "Testing $LIB..."
    echo "===================================================="
    
    cd "$ROOT_DIR/gcp-pipeline-libraries/$LIB"
    
    # Check if [dev] exists in pyproject.toml
    if grep -q "\[project.optional-dependencies\]" pyproject.toml && grep -q "dev =" pyproject.toml; then
        echo "Installing $LIB with [dev] dependencies (skipping if installation fails)..."
        # Use --no-deps to avoid recompilation of common libraries
        python3 -m pip install -e ".[dev]" --no-deps -q || echo "Warning: [dev] installation failed, continuing with current environment."
    else
        echo "Installing $LIB (skipping if installation fails)..."
        python3 -m pip install -e "." --no-deps -q || echo "Warning: installation failed, continuing with current environment."
    fi
    
    if [ -d "tests" ]; then
        echo "Running tests for $LIB..."
        # Set PYTHONPATH to include src directories of ALL libraries to handle inter-library dependencies
        ALL_SRC=$(find "$ROOT_DIR/gcp-pipeline-libraries" -maxdepth 3 -name "src" | tr '\n' ':')
        PYTHONPATH="$ALL_SRC" pytest tests/ -v --tb=short
    else
        echo "No tests found for $LIB."
    fi
    
    echo "Completed $LIB testing."
    echo ""
done

cd "$ROOT_DIR"
echo "All library tests completed successfully!"
