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

RUN pip install dbt-bigquery

# Install shared libraries from PyPI with version pinning
RUN if [ "$LIBRARY_VERSION" = "latest" ]; then \
        pip install --no-cache-dir gcp-pipeline-core gcp-pipeline-transform; \
    else \
        pip install --no-cache-dir \
            "gcp-pipeline-core==${LIBRARY_VERSION}" \
            "gcp-pipeline-transform==${LIBRARY_VERSION}"; \
    fi

# Verify installed versions
RUN echo "Installed library versions:" && \
    pip show gcp-pipeline-core | grep Version

# Copy deployment code
COPY deployments/bigquery-to-mapped-product /app/deployments/bigquery-to-mapped-product
RUN pip install /app/deployments/bigquery-to-mapped-product

WORKDIR /app/deployments/bigquery-to-mapped-product/dbt

# Set dbt profiles dir (if needed, otherwise uses default)
ENV DBT_PROFILES_DIR=/app/deployments/bigquery-to-mapped-product/dbt

# Create version marker
RUN echo "library_version=${LIBRARY_VERSION}" > /app/VERSION

# Entrypoint for dbt
ENTRYPOINT ["dbt"]
CMD ["run"]
