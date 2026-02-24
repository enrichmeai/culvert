# Production Reference Dockerfile for Dataflow Flex Template
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Beam SDK and common dependencies (Optimized for Python 3.11)
RUN pip install --no-cache-dir \
    apache-beam[gcp]==2.53.0 \
    google-cloud-storage \
    google-cloud-bigquery \
    google-cloud-pubsub \
    google-cloud-logging \
    google-cloud-monitoring \
    google-cloud-error-reporting \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp \
    cryptography \
    pandas

# Copy shared libraries and install them
COPY gcp-pipeline-libraries /app/gcp-pipeline-libraries
RUN pip install /app/gcp-pipeline-libraries/gcp-pipeline-core \
    /app/gcp-pipeline-libraries/gcp-pipeline-beam \
    /app/gcp-pipeline-libraries/gcp-pipeline-framework

# Copy deployment code
COPY deployments/original-data-to-bigqueryload /app/deployments/original-data-to-bigqueryload

# Install deployment as a package
RUN pip install -e /app/deployments/original-data-to-bigqueryload

# Set environment variables
ENV PYTHONPATH="/app/deployments/original-data-to-bigqueryload/src:/app"
ENV FLEX_TEMPLATE_PYTHON_PY_FILE="/app/deployments/original-data-to-bigqueryload/src/data_ingestion/pipeline/runner.py"

# Set entrypoint for Dataflow
ENTRYPOINT ["python", "-m", "data_ingestion.pipeline.runner"]
