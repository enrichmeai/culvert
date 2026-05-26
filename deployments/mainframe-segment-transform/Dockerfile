# Dataflow Flex Template for Mainframe Segment Transform
# =============================================================================
# Uses the official Dataflow Flex Template launcher base image.
# =============================================================================
FROM gcr.io/dataflow-templates-base/python311-template-launcher-base:latest

# Build arguments for version pinning
ARG LIBRARY_VERSION=latest
ENV LIBRARY_VERSION=${LIBRARY_VERSION}

# Set working directory
WORKDIR /template

# Upgrade pip to avoid dependency resolution issues (ResolutionTooDeep)
RUN pip install --upgrade pip

# Install Apache Beam with GCP extras first
RUN pip install --no-cache-dir "apache-beam[gcp]==2.56.0"

# Install remaining dependencies
RUN pip install --no-cache-dir \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp \
    pyyaml

# Install framework from PyPI with version pinning
RUN if [ "$LIBRARY_VERSION" = "latest" ]; then \
        pip install --no-cache-dir data-pipeline-framework; \
    else \
        pip install --no-cache-dir "data-pipeline-framework==${LIBRARY_VERSION}"; \
    fi

# Copy deployment code (includes config/ with templates and src/)
COPY deployments/mainframe-segment-transform /template/deployments/mainframe-segment-transform

# Install deployment as a package
RUN pip install -e /template/deployments/mainframe-segment-transform

# Set environment variables for Flex Template launcher
ENV PYTHONPATH="/template/deployments/mainframe-segment-transform/src:/template"
ENV FLEX_TEMPLATE_PYTHON_PY_FILE="/template/deployments/mainframe-segment-transform/src/launch.py"
ENV FLEX_TEMPLATE_PYTHON_SETUP_FILE="/template/deployments/mainframe-segment-transform/setup.py"

# Version marker
RUN echo "library_version=${LIBRARY_VERSION}" > /template/VERSION
