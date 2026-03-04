FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install shared libraries from PyPI
RUN pip install --no-cache-dir \
    gcp-pipeline-framework[core,orchestration]>=1.0.5

# Copy deployment code
COPY deployments/data-pipeline-orchestrator /app/deployments/data-pipeline-orchestrator
RUN pip install /app/deployments/data-pipeline-orchestrator

# Command to list DAGs (as a simple validation)
CMD ["ls", "-R", "/app/deployments/data-pipeline-orchestrator/dags"]
