# Custom Airflow Docker Image with Pipeline Libraries
#
# Build:
#   docker build -t gcr.io/<PROJECT_ID>/airflow-custom:latest -f Dockerfile.airflow .
#   docker push gcr.io/<PROJECT_ID>/airflow-custom:latest
#
# Or with Cloud Build:
#   gcloud builds submit --tag gcr.io/<PROJECT_ID>/airflow-custom:latest -f Dockerfile.airflow .

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

