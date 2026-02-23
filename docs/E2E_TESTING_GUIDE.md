# End-to-End Testing Guide

This document describes how to perform end-to-end testing of the deployed pipelines.

## Prerequisites

- GCP CLI (`gcloud`) installed and authenticated
- GitHub CLI (`gh`) installed and authenticated
- Access to GCP project with deployed infrastructure


## Application1 Pipeline - Complete Test Procedure

### Step 1: Deploy Infrastructure (if not done)

```bash
# Trigger deployment via GitHub Actions
gh workflow run deploy-application1.yml

# Wait and check status (takes ~5-10 mins, Composer takes ~30 mins)
gh run list --limit 4
```

### Step 2: Verify Infrastructure

```bash
# Check Composer environment
gcloud composer environments list --locations=europe-west2

# Expected: application1-dev-composer with state RUNNING
```

```bash
# Check BigQuery datasets
bq ls

# Expected: fdp_application1, job_control, odp_application1
```

```bash
# Check GCS buckets
gsutil ls | grep application1

# Expected:
# gs://{project}-application1-dev-archive/
# gs://{project}-application1-dev-error/
# gs://{project}-application1-dev-landing/
```

```bash
# Check Pub/Sub topics
gcloud pubsub topics list | grep application1

# Expected: application1-file-notifications
```

### Step 3: Upload Test Data

```bash
PROJECT_ID=$(gcloud config get-value project)

# Upload the test data file (uses existing sample data)
gsutil cp deployments/application1/tests/data/application1_customers_sample.csv \
  gs://${PROJECT_ID}-application1-dev-landing/application1/

# Upload the trigger file (.ok) - this triggers the pipeline
touch /tmp/application1_customers_sample.ok
gsutil cp /tmp/application1_customers_sample.ok \
  gs://${PROJECT_ID}-application1-dev-landing/application1/

# Verify files uploaded
gsutil ls gs://${PROJECT_ID}-application1-dev-landing/application1/
```

### Step 4: Verify Pub/Sub Notification

```bash
# Pull messages from subscription
gcloud pubsub subscriptions pull application1-file-notifications-sub \
  --auto-ack --limit=5

# Expected: Two messages with eventType=OBJECT_FINALIZE
# - One for .csv file
# - One for .ok file
```

### Step 5: Deploy DAGs to Composer

```bash
PROJECT_ID=$(gcloud config get-value project)
REGION="europe-west2"

# Get the Composer DAGs bucket
DAGS_BUCKET=$(gcloud composer environments describe application1-dev-composer \
  --location=$REGION \
  --format='value(config.dagGcsPrefix)')

echo "DAGs bucket: $DAGS_BUCKET"

# Upload DAGs
gsutil -m cp -r deployments/application1/src/application1/orchestration/airflow/dags/* \
  ${DAGS_BUCKET}/application1/

# Verify DAGs uploaded
gsutil ls ${DAGS_BUCKET}/application1/
```

### Step 6: Access Airflow UI

```bash
# Get Composer environment URL
gcloud composer environments describe application1-dev-composer \
  --location=europe-west2 \
  --format='value(config.airflowUri)'

# Open URL in browser to access Airflow UI
```

### Step 7: Query BigQuery (after pipeline runs)

```bash
PROJECT_ID=$(gcloud config get-value project)

# Check ODP table
bq query --project_id=${PROJECT_ID} \
  "SELECT * FROM odp_application1.customers LIMIT 10"

# Check FDP table  
bq query --project_id=${PROJECT_ID} \
  "SELECT * FROM fdp_application1.event_transaction_excess LIMIT 10"

# Check job control
bq query --project_id=${PROJECT_ID} \
  "SELECT * FROM job_control.pipeline_jobs ORDER BY created_at DESC LIMIT 10"
```

---

## Application2 Pipeline - Complete Test Procedure

### Step 1: Deploy Infrastructure

```bash
# Trigger Application2 deployment
gh workflow run deploy-application2.yml

# Wait and check status
gh run list --limit 4

# Note: Composer creation takes ~30 minutes
```

### Step 2: Verify Infrastructure

```bash
# Check Composer environment
gcloud composer environments list --locations=europe-west2

# Expected: application2-dev-composer with state RUNNING
```

```bash
# Check BigQuery datasets
bq ls | grep application2

# Expected: fdp_application2, odp_application2
```

```bash
# Check GCS buckets
gsutil ls | grep application2

# Expected:
# gs://{project}-application2-dev-archive/
# gs://{project}-application2-dev-error/
# gs://{project}-application2-dev-landing/
```

### Step 3: Upload Test Data

```bash
PROJECT_ID=$(gcloud config get-value project)

# Upload the test data file
gsutil cp deployments/application2/tests/data/application2_applications_sample.csv \
  gs://${PROJECT_ID}-application2-dev-landing/application2/

# Upload the trigger file (.ok)
touch /tmp/application2_applications_sample.ok
gsutil cp /tmp/application2_applications_sample.ok \
  gs://${PROJECT_ID}-application2-dev-landing/application2/
```

### Step 4: Verify Pub/Sub Notification

```bash
gcloud pubsub subscriptions pull application2-file-notifications-sub \
  --auto-ack --limit=5
```

### Step 5: Deploy DAGs to Composer

```bash
PROJECT_ID=$(gcloud config get-value project)
REGION="europe-west2"

# Get the Composer DAGs bucket
DAGS_BUCKET=$(gcloud composer environments describe application2-dev-composer \
  --location=$REGION \
  --format='value(config.dagGcsPrefix)')

# Upload DAGs
gsutil -m cp -r deployments/application2/src/application2/orchestration/airflow/dags/* \
  ${DAGS_BUCKET}/application2/
```

---

## Cleanup Test Data

```bash
PROJECT_ID=$(gcloud config get-value project)

# Remove Application1 test files
gsutil rm gs://${PROJECT_ID}-application1-dev-landing/application1/application1_customers_sample.*

# Remove Application2 test files
gsutil rm gs://${PROJECT_ID}-application2-dev-landing/application2/application2_applications_sample.*
```

---

## Full Infrastructure Cleanup

To completely remove all resources:

```bash
./scripts/gcp/cleanup_all.sh
```

---

## Troubleshooting

### Pub/Sub Not Receiving Messages

```bash
# Check GCS notification configuration
gsutil notification list gs://${PROJECT_ID}-application1-dev-landing

# Verify topic exists
gcloud pubsub topics describe application1-file-notifications
```

### Composer Environment Issues

```bash
# Check environment status
gcloud composer environments describe application1-dev-composer \
  --location=europe-west2

# Check environment logs
gcloud logging read "resource.type=cloud_composer_environment" --limit=20
```

### BigQuery Access Issues

```bash
# Check dataset permissions
bq show --format=prettyjson odp_application1
```

### DAGs Not Appearing in Airflow

```bash
# Check if DAGs were uploaded
DAGS_BUCKET=$(gcloud composer environments describe application1-dev-composer \
  --location=europe-west2 \
  --format='value(config.dagGcsPrefix)')
gsutil ls ${DAGS_BUCKET}/

# Check for DAG parsing errors in Airflow logs
gcloud logging read "resource.type=cloud_composer_environment AND textPayload:DAG" --limit=20
```
