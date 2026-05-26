# End-to-End Testing Guide

How to run a full end-to-end test of the Generic pipeline after deployment.

## Prerequisites

- GCP CLI (`gcloud`) installed and authenticated
- GitHub CLI (`gh`) installed and authenticated
- Access to GCP project with deployed infrastructure

## Generic Pipeline - Complete Test Procedure

### Step 1: Deploy Infrastructure (if not already done)

```bash
# Trigger deployment via GitHub Actions
gh workflow run deploy-generic.yml

# Wait and check status (builds ~10 min, Composer ~30 min)
gh run list --limit 4
```

### Step 2: Verify Infrastructure

```bash
# Composer environment
gcloud composer environments list --locations=europe-west2
# Expected: generic-int-composer with state RUNNING

# BigQuery datasets
bq ls
# Expected: fdp_generic, job_control, odp_generic

# GCS buckets
gsutil ls | grep generic
# Expected:
#   gs://{project}-generic-int-archive/
#   gs://{project}-generic-int-error/
#   gs://{project}-generic-int-landing/

# Pub/Sub topics
gcloud pubsub topics list | grep generic
# Expected: generic-file-notifications
```

### Step 3: Deploy DAGs to Composer

```bash
PROJECT_ID=$(gcloud config get-value project)
REGION="europe-west2"

# Get the Composer DAGs bucket
DAGS_BUCKET=$(gcloud composer environments describe generic-int-composer \
  --location=$REGION \
  --format='value(config.dagGcsPrefix)')

echo "DAGs bucket: $DAGS_BUCKET"

# Upload DAGs from the orchestrator deployment
gsutil -m cp -r deployments/data-pipeline-orchestrator/dags/* \
  ${DAGS_BUCKET}/generic/

# Verify DAGs uploaded
gsutil ls ${DAGS_BUCKET}/generic/
```

### Step 4: Access Airflow UI

```bash
gcloud composer environments describe generic-int-composer \
  --location=europe-west2 \
  --format='value(config.airflowUri)'

# Open the returned URL in your browser.
```

### Step 5: Upload Test Data

Upload a CSV file followed by its `.ok` trigger file. The `.ok` file fires a
GCS notification through Pub/Sub, which the orchestrator DAG picks up.

```bash
PROJECT_ID=$(gcloud config get-value project)

# Upload sample data (customers example -- accounts and decision samples also available)
gsutil cp deployments/original-data-to-bigqueryload/tests/data/generic_customers_sample.csv \
  gs://${PROJECT_ID}-generic-int-landing/generic/

# Upload the trigger file
touch /tmp/generic_customers_sample.ok
gsutil cp /tmp/generic_customers_sample.ok \
  gs://${PROJECT_ID}-generic-int-landing/generic/

# Verify both files are present
gsutil ls gs://${PROJECT_ID}-generic-int-landing/generic/
```

### Step 6: Verify Pub/Sub Notification

```bash
gcloud pubsub subscriptions pull generic-file-notifications-sub \
  --auto-ack --limit=5

# Expected: two OBJECT_FINALIZE messages (one for .csv, one for .ok)
```

### Step 7: Query BigQuery (after pipeline completes)

```bash
PROJECT_ID=$(gcloud config get-value project)

# ODP table (written by original-data-to-bigqueryload)
bq query --project_id=${PROJECT_ID} \
  "SELECT * FROM odp_generic.customers LIMIT 10"

# FDP table (written by bigquery-to-mapped-product)
bq query --project_id=${PROJECT_ID} \
  "SELECT * FROM fdp_generic.event_transaction_excess LIMIT 10"

# Job control
bq query --project_id=${PROJECT_ID} \
  "SELECT * FROM job_control.pipeline_jobs ORDER BY created_at DESC LIMIT 10"
```

---

## Cleanup Test Data

```bash
PROJECT_ID=$(gcloud config get-value project)

gsutil rm gs://${PROJECT_ID}-generic-int-landing/generic/generic_customers_sample.*
```

---

## Full Infrastructure Cleanup

```bash
./scripts/gcp/cleanup_all.sh
```

---

## Troubleshooting

### Pub/Sub Not Receiving Messages

```bash
# Check GCS notification configuration
gsutil notification list gs://${PROJECT_ID}-generic-int-landing

# Verify topic exists
gcloud pubsub topics describe generic-file-notifications
```

### Composer Environment Issues

```bash
gcloud composer environments describe generic-int-composer \
  --location=europe-west2

gcloud logging read "resource.type=cloud_composer_environment" --limit=20
```

### BigQuery Access Issues

```bash
bq show --format=prettyjson odp_generic
```

### DAGs Not Appearing in Airflow

```bash
DAGS_BUCKET=$(gcloud composer environments describe generic-int-composer \
  --location=europe-west2 \
  --format='value(config.dagGcsPrefix)')

gsutil ls ${DAGS_BUCKET}/

gcloud logging read "resource.type=cloud_composer_environment AND textPayload:DAG" --limit=20
```
