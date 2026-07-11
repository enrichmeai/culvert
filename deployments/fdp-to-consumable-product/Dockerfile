# =============================================================================
# dbt CDP Transformation Container
# =============================================================================
# Build with: docker build --build-arg LIBRARY_VERSION=1.0.7 -t generic-cdp-transformation .
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
# data-pipeline-core first: transform declares data-pipeline-core>=0.1.0 and
# nothing is on PyPI yet — both install from local source until the 0.1.0 publish.
COPY data-pipeline-libraries/data-pipeline-core /tmp/data-pipeline-core
RUN pip install --no-cache-dir /tmp/data-pipeline-core
COPY data-pipeline-libraries/data-pipeline-transform /tmp/data-pipeline-transform
RUN pip install --no-cache-dir /tmp/data-pipeline-transform

# Verify installed versions
RUN echo "Installed library versions:" && \
    pip show data-pipeline-transform | grep Version

# Copy deployment code
COPY deployments/fdp-to-consumable-product /app/deployments/fdp-to-consumable-product
RUN pip install /app/deployments/fdp-to-consumable-product

WORKDIR /app/deployments/fdp-to-consumable-product/dbt

# Copy shared macros from pip-installed data-pipeline-transform into dbt project
RUN TRANSFORM_PKG=$(python -c "import data_pipeline_transform; import os; print(os.path.dirname(data_pipeline_transform.__file__))") && \
    cp -r "$TRANSFORM_PKG/dbt_shared/macros" /app/deployments/fdp-to-consumable-product/dbt/shared_macros

# Install dbt package dependencies (e.g. dbt_utils from packages.yml)
RUN dbt deps --profiles-dir .

ENV DBT_PROFILES_DIR=/app/deployments/fdp-to-consumable-product/dbt

# Create version marker
RUN echo "library_version=${LIBRARY_VERSION}" > /app/VERSION

ENTRYPOINT ["dbt"]
CMD ["run"]
