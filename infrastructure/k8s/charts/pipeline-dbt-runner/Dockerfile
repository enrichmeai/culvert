# =============================================================================
# pipeline-dbt-runner — dbt + BigQuery runner image
# =============================================================================
# Versions baked into the tag (1.7.14-1.0.29):
#   dbt-core / dbt-bigquery : 1.7.14
#   gcp-pipeline-transform  : 1.0.29  (dbt macro package)
#   gcp-pipeline-core       : 1.0.29  (structured logging / audit emission)
#
# Build:
#   docker build \
#     --build-arg DBT_VERSION=1.7.14 \
#     --build-arg PIPELINE_LIB_VERSION=1.0.29 \
#     -t my-registry/pipeline-dbt-runner:1.7.14-1.0.29 .
#
# Override pip index (private registry):
#   docker build --build-arg PIP_INDEX_URL=https://pypi.example.com/simple/ ...
# =============================================================================

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ARG DBT_VERSION=1.7.14
ARG PIPELINE_LIB_VERSION=1.0.29
ARG PIP_INDEX_URL=https://pypi.org/simple/

ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# Build dependencies for packages that compile C extensions (e.g. grpcio)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

# Install dbt + BigQuery adapter
RUN pip install --prefix=/install \
    "dbt-core==${DBT_VERSION}" \
    "dbt-bigquery==${DBT_VERSION}"

# Install pipeline libraries (index-url override lets teams point at a private registry)
RUN pip install --prefix=/install \
    --index-url "${PIP_INDEX_URL}" \
    "gcp-pipeline-transform==${PIPELINE_LIB_VERSION}" \
    "gcp-pipeline-core==${PIPELINE_LIB_VERSION}"

# Pin transitive GCP client libs to known-good versions
RUN pip install --prefix=/install \
    "google-cloud-bigquery>=3.11.0,<4.0.0" \
    "google-cloud-storage>=2.10.0,<3.0.0"

# Security audit — non-blocking; surfaced in build logs only
RUN pip install pip-audit && \
    pip-audit --path /install/lib/python3.11/site-packages || true

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ARG DBT_VERSION=1.7.14
ARG PIPELINE_LIB_VERSION=1.0.29

LABEL org.opencontainers.image.title="pipeline-dbt-runner" \
      org.opencontainers.image.description="dbt BigQuery runner with gcp-pipeline-transform macros" \
      org.opencontainers.image.version="${DBT_VERSION}-${PIPELINE_LIB_VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Default dbt env vars — all overridable at pod/container level
    DBT_PROJECT=bigquery-to-mapped-product \
    DBT_TARGET=prod \
    DBT_PROFILES_DIR=/app/profiles \
    PATH="/app/bin:${PATH}"

# Minimal runtime OS deps (libpq needed by google-cloud-bigquery's grpc transport)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -g 1000 dbtuser && \
    useradd -u 1000 -g dbtuser -m -s /bin/bash dbtuser

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Application directories
#   /app/projects/  — volume mount point for dbt project(s)
#   /app/profiles/  — volume mount point for profiles.yml
#   /app/bin/       — entrypoint and helper scripts
RUN mkdir -p /app/projects /app/profiles /app/bin && \
    chown -R dbtuser:dbtuser /app

# Entrypoint script
COPY --chown=dbtuser:dbtuser bin/entrypoint.sh /app/bin/entrypoint.sh
RUN chmod +x /app/bin/entrypoint.sh

# Smoke-test: dbt binary is on PATH
RUN dbt --version

USER dbtuser

# /app/projects/<DBT_PROJECT> is expected to be mounted at runtime
VOLUME ["/app/projects", "/app/profiles"]

WORKDIR /app

ENTRYPOINT ["/app/bin/entrypoint.sh"]
CMD ["run"]
