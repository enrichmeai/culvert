# Production Reference Dockerfile for Dataflow Flex Template
# =============================================================================
# Build with: docker build --build-arg LIBRARY_VERSION=1.0.5 -t generic-ingestion .
# =============================================================================
FROM python:3.11-slim

# Build arguments for version pinning
ARG LIBRARY_VERSION=latest
ENV LIBRARY_VERSION=${LIBRARY_VERSION}

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Beam SDK and common dependencies (Optimized for Python 3.11)
RUN pip install --no-cache-dir \
    apache-beam[gcp]==2.56.0 \
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

# Install shared libraries from PyPI with version pinning
RUN if [ "$LIBRARY_VERSION" = "latest" ]; then \
        pip install --no-cache-dir gcp-pipeline-core gcp-pipeline-beam; \
    else \
        pip install --no-cache-dir \
            "gcp-pipeline-core==${LIBRARY_VERSION}" \
            "gcp-pipeline-beam==${LIBRARY_VERSION}"; \
    fi

# Verify installed versions
RUN echo "Installed library versions:" && \
    pip show gcp-pipeline-core | grep Version && \
    pip show gcp-pipeline-beam | grep Version

# Copy deployment code
COPY deployments/original-data-to-bigqueryload /app/deployments/original-data-to-bigqueryload

# Install deployment as a package
RUN pip install -e /app/deployments/original-data-to-bigqueryload

# Set environment variables
ENV PYTHONPATH="/app/deployments/original-data-to-bigqueryload/src:/app"
ENV FLEX_TEMPLATE_PYTHON_PY_FILE="/app/deployments/original-data-to-bigqueryload/src/data_ingestion/pipeline/runner.py"

# Create version marker
RUN echo "library_version=${LIBRARY_VERSION}" > /app/VERSION

# Set entrypoint for Dataflow
ENTRYPOINT ["python", "-m", "data_ingestion.pipeline.runner"]
