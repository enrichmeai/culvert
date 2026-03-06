# =============================================================================
# Custom Airflow Docker Image for GKE Deployment
# =============================================================================
# This is THE Airflow runtime image used by the Helm chart on GKE.
# It includes gcp-pipeline-core and gcp-pipeline-orchestration libraries
# that the DAGs depend on.
#
# Build locally:
#   docker build -t gcr.io/<PROJECT_ID>/airflow-custom:latest .
#   docker push gcr.io/<PROJECT_ID>/airflow-custom:latest
#
# Build with Cloud Build:
#   cd infrastructure/k8s/airflow
#   gcloud builds submit --tag gcr.io/<PROJECT_ID>/airflow-custom:latest .
#
# Note: DAGs are NOT baked into this image. They are synced from GCS at runtime.
# =============================================================================

FROM apache/airflow:2.8.1-python3.11

USER airflow

# Install required packages for DAGs
RUN pip install --no-cache-dir \
    gcp-pipeline-core \
    gcp-pipeline-orchestration \
    apache-airflow-providers-google>=10.0.0 \
    apache-airflow-providers-cncf-kubernetes>=7.0.0

# Verify installation
RUN python -c "import gcp_pipeline_core; print('gcp-pipeline-core installed')" && \
    python -c "import gcp_pipeline_orchestration; print('gcp-pipeline-orchestration installed')"

