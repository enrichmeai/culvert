FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install dbt-bigquery

# Install shared libraries from PyPI
RUN pip install --no-cache-dir \
    gcp-pipeline-framework[core,transform]>=1.0.5

# Copy deployment code
COPY deployments/bigquery-to-mapped-product /app/deployments/bigquery-to-mapped-product
RUN pip install /app/deployments/bigquery-to-mapped-product

WORKDIR /app/deployments/bigquery-to-mapped-product/dbt

# Set dbt profiles dir (if needed, otherwise uses default)
ENV DBT_PROFILES_DIR=/app/deployments/bigquery-to-mapped-product/dbt

# Entrypoint for dbt
ENTRYPOINT ["dbt"]
CMD ["run"]
