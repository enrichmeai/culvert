#!/bin/bash
# Setup automatic pipeline triggering on file upload
# This creates a Cloud Function that triggers when files land in GCS

PROJECT_ID=${1:-"loa-migration-dev"}

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║     Setting Up Auto-Trigger for Pipeline                     ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

echo "⚠️  NOTE: This is OPTIONAL - only needed for automatic triggering"
echo ""
echo "What this does:"
echo "  • Creates a Cloud Function"
echo "  • Listens for file uploads to GCS input bucket"
echo "  • Automatically triggers Dataflow pipeline when files arrive"
echo ""
echo "Cost: ~$0.10-1/month (Cloud Function charges)"
echo ""

read -p "Do you want to set up auto-trigger? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Skipped. You can trigger manually with: ./trigger-pipeline-now.sh"
    exit 0
fi

echo ""
echo "📦 Deploying Cloud Function..."
echo ""

# Call the deployment script
./scripts/deploy-cloud-function.sh ${PROJECT_ID}

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║              ✅ AUTO-TRIGGER SETUP COMPLETE!                  ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "🎯 How it works:"
echo "  1. Upload CSV to: gs://${PROJECT_ID}-loa-data/input/"
echo "  2. Cloud Function automatically detects it"
echo "  3. Pipeline triggers automatically"
echo ""
echo "📊 Test it:"
echo "  gsutil cp test.csv gs://${PROJECT_ID}-loa-data/input/"
echo ""
echo "💰 Cost: ~$0.10-1/month"
echo ""

