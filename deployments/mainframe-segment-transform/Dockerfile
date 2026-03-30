# Dataflow Flex Template for Mainframe Segment Transform
# =============================================================================
# Build with: docker build --build-arg LIBRARY_VERSION=1.0.29 -t segment-transform .
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

# Upgrade pip to avoid dependency resolution issues (ResolutionTooDeep)
RUN pip install --upgrade pip

# Install Apache Beam with GCP extras first (pulls in most GCP client libs)
RUN pip install --no-cache-dir "apache-beam[gcp]==2.56.0"

# Install remaining dependencies not already pulled in by Beam
RUN pip install --no-cache-dir \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp \
    pyyaml

# Install framework from PyPI with version pinning
RUN if [ "$LIBRARY_VERSION" = "latest" ]; then \
        pip install --no-cache-dir gcp-pipeline-framework; \
    else \
        pip install --no-cache-dir "gcp-pipeline-framework==${LIBRARY_VERSION}"; \
    fi

# Verify installed versions
RUN echo "Installed library versions:" && \
    pip show gcp-pipeline-framework | grep Version && \
    pip show gcp-pipeline-core | grep Version && \
    pip show gcp-pipeline-beam | grep Version

# Copy deployment code (includes config/ with templates and src/)
COPY deployments/mainframe-segment-transform /app/deployments/mainframe-segment-transform

# Install deployment as a package
RUN pip install -e /app/deployments/mainframe-segment-transform

# Set environment variables
ENV PYTHONPATH="/app/deployments/mainframe-segment-transform/src:/app"
ENV FLEX_TEMPLATE_PYTHON_PY_FILE="/app/deployments/mainframe-segment-transform/src/segment_transform/pipeline/runner.py"

# Create version marker
RUN echo "library_version=${LIBRARY_VERSION}" > /app/VERSION

# Set entrypoint for Dataflow
ENTRYPOINT ["python", "-m", "segment_transform.pipeline.runner"]
