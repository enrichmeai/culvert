#!/bin/bash
# Delete LOA Migration GCP Project
# This will permanently delete the project and all resources

set -e

PROJECT_ID="loa-migration-dev"

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║        ⚠️  DELETE GCP PROJECT - PERMANENT ACTION             ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "This will PERMANENTLY DELETE:"
echo "  • Project: ${PROJECT_ID}"
echo "  • All Cloud Storage buckets and data"
echo "  • All BigQuery datasets and tables"
echo "  • All Pub/Sub topics"
echo "  • Any Cloud Functions"
echo "  • All other resources in the project"
echo ""
echo "⚠️  THIS CANNOT BE UNDONE!"
echo ""
read -p "Are you ABSOLUTELY SURE you want to delete ${PROJECT_ID}? (type 'DELETE' to confirm): " CONFIRM

if [ "$CONFIRM" != "DELETE" ]; then
    echo "Deletion cancelled."
    exit 0
fi

echo ""
echo "Deleting project ${PROJECT_ID}..."
echo ""

# Delete the project
gcloud projects delete ${PROJECT_ID} --quiet

echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║              ✅ PROJECT DELETION INITIATED                    ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "The project ${PROJECT_ID} is being deleted."
echo "This may take a few minutes to complete."
echo ""
echo "The project will be scheduled for deletion and removed after 30 days."
echo "During this period, you can restore it if needed."
echo ""
echo "To check deletion status:"
echo "  gcloud projects list --filter='projectId:${PROJECT_ID}'"
echo ""
echo "To restore the project (within 30 days):"
echo "  gcloud projects undelete ${PROJECT_ID}"
echo ""

