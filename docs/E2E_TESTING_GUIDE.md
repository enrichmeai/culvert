# End-to-End Testing Guide

This document describes how to perform end-to-end testing of the deployed pipelines.

## Prerequisites

- GCP CLI (`gcloud`) installed and authenticated
- GitHub CLI (`gh`) installed and authenticated
- Access to GCP project with deployed infrastructure


## EM Pipeline - Complete Test Procedure

### Step 1: Deploy Infrastructure (if not done)

```bash
# Trigger deployment via GitHub Actions
gh workflow run deploy-em.yml

# Wait and check status (takes ~5-10 mins, Composer takes ~30 mins)
gh run list --limit 4
```

### Step 2: Verify Infrastructure

```bash
# Check Composer environment
gcloud composer environments list --locations=europe-west2

# Expected: em-dev-composer with state RUNNING
```

```bash
# Check BigQuery datasets
bq ls

# Expected: fdp_em, job_control, odp_em
```

```bash
# Check GCS buckets
gsutil ls | grep em

# Expected:
# gs://{project}-em-dev-archive/
# gs://{project}-em-dev-error/
# gs://{project}-em-dev-landing/
```

```bash
# Check Pub/Sub topics
gcloud pubsub topics list | grep em

# Expected: em-file-notifications
```

### Step 3: Upload Test Data

```bash
PROJECT_ID=$(gcloud config get-value project)

# Upload the test data file (uses existing sample data)
gsutil cp deployments/em/tests/data/em_customers_sample.csv \
  gs://${PROJECT_ID}-em-dev-landing/em/

# Upload the trigger file (.ok) - this triggers the pipeline
touch /tmp/em_customers_sample.ok
gsutil cp /tmp/em_customers_sample.ok \
  gs://${PROJECT_ID}-em-dev-landing/em/

# Verify files uploaded
gsutil ls gs://${PROJECT_ID}-em-dev-landing/em/
```

### Step 4: Verify Pub/Sub Notification

```bash
# Pull messages from subscription
gcloud pubsub subscriptions pull em-file-notifications-sub \
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
DAGS_BUCKET=$(gcloud composer environments describe em-dev-composer \
  --location=$REGION \
  --format='value(config.dagGcsPrefix)')

echo "DAGs bucket: $DAGS_BUCKET"

# Upload DAGs
gsutil -m cp -r deployments/em/src/em/orchestration/airflow/dags/* \
  ${DAGS_BUCKET}/em/

# Verify DAGs uploaded
gsutil ls ${DAGS_BUCKET}/em/
```

### Step 6: Access Airflow UI

```bash
# Get Composer environment URL
gcloud composer environments describe em-dev-composer \
  --location=europe-west2 \
  --format='value(config.airflowUri)'

# Open URL in browser to access Airflow UI
```

### Step 7: Query BigQuery (after pipeline runs)

```bash
PROJECT_ID=$(gcloud config get-value project)

# Check ODP table
bq query --project_id=${PROJECT_ID} \
  "SELECT * FROM odp_em.customers LIMIT 10"

# Check FDP table  
bq query --project_id=${PROJECT_ID} \
  "SELECT * FROM fdp_em.em_attributes LIMIT 10"

# Check job control
bq query --project_id=${PROJECT_ID} \
  "SELECT * FROM job_control.pipeline_jobs ORDER BY created_at DESC LIMIT 10"
```

---

## LOA Pipeline - Complete Test Procedure

### Step 1: Deploy Infrastructure

```bash
# Trigger LOA deployment
gh workflow run deploy-loa.yml

# Wait and check status
gh run list --limit 4

# Note: Composer creation takes ~30 minutes
```

### Step 2: Verify Infrastructure

```bash
# Check Composer environment
gcloud composer environments list --locations=europe-west2

# Expected: loa-dev-composer with state RUNNING
```

```bash
# Check BigQuery datasets
bq ls | grep loa

# Expected: fdp_loa, odp_loa
```

```bash
# Check GCS buckets
gsutil ls | grep loa

# Expected:
# gs://{project}-loa-dev-archive/
# gs://{project}-loa-dev-error/
# gs://{project}-loa-dev-landing/
```

### Step 3: Upload Test Data

```bash
PROJECT_ID=$(gcloud config get-value project)

# Upload the test data file
gsutil cp deployments/loa/tests/data/loa_applications_sample.csv \
  gs://${PROJECT_ID}-loa-dev-landing/loa/

# Upload the trigger file (.ok)
touch /tmp/loa_applications_sample.ok
gsutil cp /tmp/loa_applications_sample.ok \
  gs://${PROJECT_ID}-loa-dev-landing/loa/
```

### Step 4: Verify Pub/Sub Notification

```bash
gcloud pubsub subscriptions pull loa-file-notifications-sub \
  --auto-ack --limit=5
```

### Step 5: Deploy DAGs to Composer

```bash
PROJECT_ID=$(gcloud config get-value project)
REGION="europe-west2"

# Get the Composer DAGs bucket
DAGS_BUCKET=$(gcloud composer environments describe loa-dev-composer \
  --location=$REGION \
  --format='value(config.dagGcsPrefix)')

# Upload DAGs
gsutil -m cp -r deployments/loa/src/loa/orchestration/airflow/dags/* \
  ${DAGS_BUCKET}/loa/
```

---

## Cleanup Test Data

```bash
PROJECT_ID=$(gcloud config get-value project)

# Remove EM test files
gsutil rm gs://${PROJECT_ID}-em-dev-landing/em/em_customers_sample.*

# Remove LOA test files
gsutil rm gs://${PROJECT_ID}-loa-dev-landing/loa/loa_applications_sample.*
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
gsutil notification list gs://${PROJECT_ID}-em-dev-landing

# Verify topic exists
gcloud pubsub topics describe em-file-notifications
```

### Composer Environment Issues

```bash
# Check environment status
gcloud composer environments describe em-dev-composer \
  --location=europe-west2

# Check environment logs
gcloud logging read "resource.type=cloud_composer_environment" --limit=20
```

### BigQuery Access Issues

```bash
# Check dataset permissions
bq show --format=prettyjson odp_em
```

### DAGs Not Appearing in Airflow

```bash
# Check if DAGs were uploaded
DAGS_BUCKET=$(gcloud composer environments describe em-dev-composer \
  --location=europe-west2 \
  --format='value(config.dagGcsPrefix)')
gsutil ls ${DAGS_BUCKET}/

# Check for DAG parsing errors in Airflow logs
gcloud logging read "resource.type=cloud_composer_environment AND textPayload:DAG" --limit=20
```
