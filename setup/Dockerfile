# LOA Blueprint - Production Docker Image
# Build: docker build -t loa-blueprint:latest .
# Run: docker run --rm loa-blueprint:latest

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/app

WORKDIR $APP_HOME

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Google Cloud SDK
RUN curl https://sdk.cloud.google.com | bash && \
    export PATH=/root/google-cloud-sdk/bin:$PATH

# Copy requirements files
COPY setup/requirements.txt setup/requirements-dev.txt setup/requirements-ci.txt ./

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install -r requirements-dev.txt

# Copy application code
COPY . .

# Install the blueprint package
RUN pip install -e .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser $APP_HOME

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Default command
CMD ["python", "-c", "print('LOA Blueprint container ready!')"]

# Labels
LABEL maintainer="Data Engineering Team"
LABEL version="1.0.0"
LABEL description="LOA Blueprint - Mainframe to GCP Migration"

