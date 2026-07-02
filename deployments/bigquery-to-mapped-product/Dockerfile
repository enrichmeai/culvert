# =============================================================================
# dbt Transformation Container
# =============================================================================
# Build with: docker build --build-arg LIBRARY_VERSION=1.0.5 -t generic-transformation .
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

RUN pip install --no-cache-dir dbt-bigquery

# Install the Culvert transform library from local source (nothing is on PyPI
# yet — the coordinated 0.1.0 publish is pending; switch to a pinned PyPI
# install of `culvert`/`data-pipeline-transform` after the release).
COPY data-pipeline-libraries/data-pipeline-transform /tmp/data-pipeline-transform
RUN pip install --no-cache-dir /tmp/data-pipeline-transform

# Verify installed versions
RUN echo "Installed library versions:" && \
    pip show data-pipeline-transform | grep Version

# Copy deployment code
COPY deployments/bigquery-to-mapped-product /app/deployments/bigquery-to-mapped-product
RUN pip install /app/deployments/bigquery-to-mapped-product

WORKDIR /app/deployments/bigquery-to-mapped-product/dbt

# Copy shared macros from pip-installed data-pipeline-transform into dbt project
RUN TRANSFORM_PKG=$(python -c "import data_pipeline_transform; import os; print(os.path.dirname(data_pipeline_transform.__file__))") && \
    cp -r "$TRANSFORM_PKG/dbt_shared/macros" /app/deployments/bigquery-to-mapped-product/dbt/shared_macros

# Install dbt package dependencies (e.g. dbt_utils from packages.yml)
RUN dbt deps --profiles-dir .

# Set dbt profiles dir (if needed, otherwise uses default)
ENV DBT_PROFILES_DIR=/app/deployments/bigquery-to-mapped-product/dbt

# Create version marker
RUN echo "library_version=${LIBRARY_VERSION}" > /app/VERSION

# Entrypoint for dbt
ENTRYPOINT ["dbt"]
CMD ["run"]
