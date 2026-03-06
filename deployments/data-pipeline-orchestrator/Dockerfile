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
#   docker build -t dag-validator .
#   docker run dag-validator python -c "from dags import *; print('DAGs OK')"
# =============================================================================

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Airflow (for DAG parsing) and our libraries
RUN pip install --no-cache-dir \
    apache-airflow==2.8.1 \
    gcp-pipeline-core \
    gcp-pipeline-orchestration \
    apache-airflow-providers-google>=10.0.0

# Copy DAGs
COPY dags /app/dags

# Validate DAGs can be parsed
CMD ["python", "-c", "import sys; sys.path.insert(0, '/app'); from dags import *; print('All DAGs validated successfully')"]
