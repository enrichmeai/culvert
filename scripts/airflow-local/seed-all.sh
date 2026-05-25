#!/usr/bin/env bash
#
# seed-all.sh — Populate the local stack with a realistic day's fixtures.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "== seed GCS =="
"$SCRIPT_DIR/seed-gcs.sh"

echo ""
echo "== seed Pub/Sub =="
"$SCRIPT_DIR/seed-pubsub.sh"

echo ""
echo "== seed BigQuery =="
"$SCRIPT_DIR/seed-bq.sh"

echo ""
echo "✅ Local stack fully seeded. Airflow will pick up DAGs automatically."
