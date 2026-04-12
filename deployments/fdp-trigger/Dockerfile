FROM python:3.11-slim

WORKDIR /app

# Install system deps and upgrade pip first to avoid resolution issues
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip

# Install Python dependencies
COPY deployments/fdp-trigger/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY deployments/fdp-trigger/src/fdp_trigger/ ./fdp_trigger/

ENV PORT=8080
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# Cloud Run uses gunicorn for production
CMD exec gunicorn --bind :$PORT --workers 1 --threads 4 --timeout 120 fdp_trigger.main:app
