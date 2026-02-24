FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy shared libraries and install them
COPY gcp-pipeline-libraries /app/gcp-pipeline-libraries
RUN pip install /app/gcp-pipeline-libraries/gcp-pipeline-core \
    /app/gcp-pipeline-libraries/gcp-pipeline-orchestration \
    /app/gcp-pipeline-libraries/gcp-pipeline-framework

# Copy deployment code
COPY deployments/data-pipeline-orchestrator /app/deployments/data-pipeline-orchestrator
RUN pip install /app/deployments/data-pipeline-orchestrator

# Command to list DAGs (as a simple validation)
CMD ["ls", "-R", "/app/deployments/data-pipeline-orchestrator/dags"]
