# =============================================================================
# DAG Validation Container (NOT the Airflow runtime)
# =============================================================================
# This Dockerfile is for LOCAL TESTING and CI validation of DAGs only.
# It does NOT run Airflow - it just validates DAG syntax and imports.
#
# For the actual Airflow runtime, use the Helm chart in ./helm (official
# Apache Airflow chart + culvert[orchestration])
#
# Usage:
#   docker build --build-arg LIBRARY_VERSION=0.1.1 -t dag-validator .
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

# Upgrade pip to avoid dependency resolution issues
RUN pip install --upgrade pip

# Install Airflow then providers separately to avoid resolver loops
# Version should match Cloud Composer: composer-2.16.1-airflow-2.10.5
RUN pip install --no-cache-dir "apache-airflow==2.10.5"
RUN pip install --no-cache-dir "apache-airflow-providers-google>=10.0.0"

# Install Culvert from PyPI with version pinning (core contracts + Airflow-side
# orchestration; import names are data_pipeline_*)
RUN if [ "$LIBRARY_VERSION" = "latest" ]; then \
        pip install --no-cache-dir "culvert[orchestration]"; \
    else \
        pip install --no-cache-dir "culvert[orchestration]==${LIBRARY_VERSION}"; \
    fi

# Verify installed versions
RUN echo "Installed library versions:" && \
    pip show culvert | grep Version && \
    python -c "import data_pipeline_orchestration; print('data_pipeline_orchestration OK')" 

# Copy DAGs
COPY dags /app/dags

# Create version marker
RUN echo "library_version=${LIBRARY_VERSION}" > /app/VERSION

# Validate DAGs can be parsed
CMD ["python", "-c", "import sys; sys.path.insert(0, '/app'); from dags import *; print('All DAGs validated successfully')"]
