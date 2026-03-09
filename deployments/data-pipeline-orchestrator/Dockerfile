# =============================================================================
# DAG Validation Container (NOT the Airflow runtime)
# =============================================================================
# This Dockerfile is for LOCAL TESTING and CI validation of DAGs only.
# It does NOT run Airflow - it just validates DAG syntax and imports.
#
# For the actual Airflow runtime image, use:
#   infrastructure/k8s/airflow/Dockerfile
#
# Usage:
#   docker build --build-arg LIBRARY_VERSION=1.0.5 -t dag-validator .
#   docker run dag-validator python -c "from dags import *; print('DAGs OK')"
# =============================================================================

FROM python:3.11-slim

# Build arguments for version pinning
ARG LIBRARY_VERSION=latest
ENV LIBRARY_VERSION=${LIBRARY_VERSION}

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Airflow (for DAG parsing) and our libraries with version pinning
RUN pip install --no-cache-dir \
    apache-airflow==2.8.1 \
    apache-airflow-providers-google>=10.0.0

# Install framework from PyPI with version pinning (includes core, beam, orchestration, transform, tester)
RUN if [ "$LIBRARY_VERSION" = "latest" ]; then \
        pip install --no-cache-dir gcp-pipeline-framework; \
    else \
        pip install --no-cache-dir "gcp-pipeline-framework==${LIBRARY_VERSION}"; \
    fi

# Verify installed versions
RUN echo "Installed library versions:" && \
    pip show gcp-pipeline-framework | grep Version && \
    pip show gcp-pipeline-core | grep Version && \
    pip show gcp-pipeline-orchestration | grep Version

# Copy DAGs
COPY dags /app/dags

# Create version marker
RUN echo "library_version=${LIBRARY_VERSION}" > /app/VERSION

# Validate DAGs can be parsed
CMD ["python", "-c", "import sys; sys.path.insert(0, '/app'); from dags import *; print('All DAGs validated successfully')"]
