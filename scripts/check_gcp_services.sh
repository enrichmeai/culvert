#!/bin/bash
# Check GCP Services Required for Legacy Migration Pipeline
# Run: gcloud auth login && bash scripts/check_gcp_services.sh

set -e

PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-europe-west2}"

echo "=============================================="
echo "GCP Services Check for Legacy Migration"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "=============================================="
echo ""

# Required services for the pipeline
REQUIRED_SERVICES=(
    "bigquery.googleapis.com"
    "storage.googleapis.com"
    "pubsub.googleapis.com"
    "dataflow.googleapis.com"
    "composer.googleapis.com"
    "cloudkms.googleapis.com"
    "monitoring.googleapis.com"
    "logging.googleapis.com"
)

echo "Checking required GCP services..."
echo ""

ENABLED_SERVICES=$(gcloud services list --enabled --project="$PROJECT_ID" --format="value(config.name)" 2>/dev/null)

ALL_ENABLED=true
for service in "${REQUIRED_SERVICES[@]}"; do
    if echo "$ENABLED_SERVICES" | grep -q "^${service}$"; then
        echo "✅ $service - ENABLED"
    else
        echo "❌ $service - NOT ENABLED"
        ALL_ENABLED=false
    fi
done

echo ""
echo "=============================================="
if [ "$ALL_ENABLED" = true ]; then
    echo "✅ All required services are enabled!"
else
    echo "⚠️  Some services need to be enabled."
    echo ""
    echo "To enable all required services, run:"
    echo ""
    echo "gcloud services enable \\"
    for service in "${REQUIRED_SERVICES[@]}"; do
        echo "    $service \\"
    done
    echo "    --project=$PROJECT_ID"
fi
echo "=============================================="

echo ""
echo "Additional checks:"
echo ""

# Check if BigQuery datasets exist
echo "BigQuery Datasets:"
gcloud alpha bq datasets list --project="$PROJECT_ID" 2>/dev/null | head -10 || echo "  (none or access denied)"

echo ""
echo "Cloud Storage Buckets:"
gsutil ls -p "$PROJECT_ID" 2>/dev/null | head -10 || echo "  (none or access denied)"

echo ""
echo "Pub/Sub Topics:"
gcloud pubsub topics list --project="$PROJECT_ID" --format="value(name)" 2>/dev/null | head -10 || echo "  (none or access denied)"

echo ""
echo "=============================================="
echo "Check complete!"

