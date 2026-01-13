# Production Reference Dockerfile for Dataflow Flex Template
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Beam SDK and common dependencies
RUN pip install --no-cache-dir \
    apache-beam[gcp]==2.53.0 \
    google-cloud-storage \
    google-cloud-bigquery \
    google-cloud-pubsub

# Install shared libraries from Nexus
ARG NEXUS_USER
ARG NEXUS_PASSWORD
ARG NEXUS_URL
RUN pip install --no-cache-dir \
    --index-url https://${NEXUS_USER}:${NEXUS_PASSWORD}@${NEXUS_URL}/repository/pypi-all/simple \
    gcp-pipeline-core \
    gcp-pipeline-beam

# Copy deployment code (Assumes this Dockerfile is in the root of the deployment repo)
COPY . /app/deployments/loa-ingestion

# Install deployment as a package
RUN pip install -e /app/deployments/loa-ingestion

# Set environment variables
ENV PYTHONPATH="/app/deployments/loa-ingestion/src:/app"
ENV FLEX_TEMPLATE_PYTHON_PY_FILE="/app/deployments/loa-ingestion/src/loa_ingestion/pipeline/main.py"

# Set entrypoint for Dataflow
ENTRYPOINT ["python", "-m", "loa_ingestion.pipeline.main"]
