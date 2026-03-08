# =============================================================================
# Dockerfile for Streaming CDC Pipeline (Dataflow Flex Template)
# =============================================================================
# Build:
#   gcloud builds submit --tag gcr.io/<PROJECT>/streaming-cdc-pipeline:latest .
#
# Create Flex Template:
#   gcloud dataflow flex-template build gs://<BUCKET>/templates/streaming-cdc.json \
#     --image gcr.io/<PROJECT>/streaming-cdc-pipeline:latest \
#     --sdk-language PYTHON \
#     --metadata-file metadata.json
# =============================================================================

FROM gcr.io/dataflow-templates-base/python311-template-launcher-base:latest

ARG WORKDIR=/template
WORKDIR ${WORKDIR}

# Copy requirements first for caching
COPY pyproject.toml .

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy source code
COPY src/ ./src/

# Set environment
ENV FLEX_TEMPLATE_PYTHON_PY_FILE="${WORKDIR}/src/streaming_pipeline/pipeline/runner.py"
ENV FLEX_TEMPLATE_PYTHON_SETUP_FILE="${WORKDIR}/pyproject.toml"

# Verify installation
RUN python -c "from streaming_pipeline.pipeline import runner; print('Pipeline module OK')"

