# GCP Deployment Guide

This guide explains how to set up and deploy the GCP Pipeline Reference Implementation to Google Cloud Platform.

## Overview

The deployment process has three phases:

| Phase | What | How | When |
|-------|------|-----|------|
| **1. Infrastructure Setup** | Create GCS buckets, BigQuery datasets, Pub/Sub topics, Terraform state | `gcloud` CLI (manual) | Once per environment |
| **2. Pipeline Deployment** | Deploy Dataflow templates, dbt models, Airflow DAGs | GitHub Actions (on push to `main`) | On each relevant commit |
| **3. Testing** | Upload test files, trigger pipeline, verify results | Test scripts (manual) | As needed |

---

## Prerequisites

### Required Tools

```bash
# Google Cloud SDK
brew install google-cloud-sdk   # macOS
# or: https://cloud.google.com/sdk/docs/install

# GitHub CLI
brew install gh                  # macOS
# or: https://cli.github.com/

# Terraform (optional, for local infrastructure development)
brew install terraform           # macOS
```

### Authentication

```bash
# Login to GCP
gcloud auth login

# Set project
gcloud config set project <YOUR_PROJECT_ID>

# Verify
gcloud config get-value project
```

---

## Phase 1: Infrastructure Setup (One-time per Environment)

Run these commands once to create the required GCP infrastructure for a given environment (e.g., `dev`, `staging`, `prod`).

### Step 1.1: Enable Required Services

```bash
./scripts/gcp/01_enable_services.sh
```

Or manually:

```bash
gcloud services enable \
    bigquery.googleapis.com \
    storage.googleapis.com \
    pubsub.googleapis.com \
    dataflow.googleapis.com \
    composer.googleapis.com \
    cloudkms.googleapis.com \
    monitoring.googleapis.com \
    logging.googleapis.com
```

### Step 1.2: Create Terraform State Bucket

```bash
./scripts/gcp/02_create_state_bucket.sh
```

Or manually:

```bash
PROJECT_ID=$(gcloud config get-value project)
gsutil mb -l europe-west2 -p $PROJECT_ID gs://gcp-pipeline-terraform-state
gsutil versioning set on gs://gcp-pipeline-terraform-state
```

The Terraform state bucket is shared across environments. Per-environment state is isolated using the key prefix `generic/{env}`. Override the backend bucket with `-backend-config` when initialising Terraform for a different project.

### Step 1.3: Create Infrastructure (Buckets, Datasets, Topics)

```bash
./scripts/gcp/03_create_infrastructure.sh all
```

Or manually (substituting `{ENV}` with `dev`, `staging`, or `prod`):

```bash
PROJECT_ID=$(gcloud config get-value project)
ENV="dev"
REGION="europe-west2"

# GCS buckets — env-scoped for isolation
gsutil mb -l $REGION gs://${PROJECT_ID}-generic-${ENV}-landing
gsutil mb -l $REGION gs://${PROJECT_ID}-generic-${ENV}-archive
gsutil mb -l $REGION gs://${PROJECT_ID}-generic-${ENV}-error
gsutil mb -l $REGION gs://${PROJECT_ID}-generic-${ENV}-temp

# BigQuery datasets
bq mk --location=$REGION odp_generic
bq mk --location=$REGION fdp_generic
bq mk --location=$REGION job_control

# Pub/Sub topics and subscriptions
gcloud pubsub topics create generic-file-notifications
gcloud pubsub topics create generic-pipeline-events
gcloud pubsub subscriptions create generic-file-notifications-sub \
    --topic=generic-file-notifications
gcloud pubsub subscriptions create generic-pipeline-events-sub \
    --topic=generic-pipeline-events
```

### Step 1.4: Set Up GitHub Actions Service Account

```bash
./scripts/gcp/04_setup_github_actions.sh
```

This creates:
- Service account: `github-actions-deploy@<PROJECT>.iam.gserviceaccount.com`
- IAM roles for deployment (Dataflow Admin, Composer Worker, BigQuery Admin, Storage Admin)
- Key file for GitHub secrets

Then add secrets to GitHub:

```bash
gh secret set GCP_SA_KEY < /tmp/gcp-sa-key.json
gh secret set GCP_PROJECT_ID --body '<PROJECT_ID>'
rm /tmp/gcp-sa-key.json  # Delete key after adding
```

### Step 1.5: Verify Setup

```bash
./scripts/gcp/05_verify_setup.sh
```

---

## Phase 2: Pipeline Deployment (CI/CD)

The pipeline uses a **3-unit deployment model** (Ingestion, Transformation, Orchestration) to enable independent release cycles and minimal blast radius.

### Shared Libraries (PyPI)

The shared libraries (`gcp-pipeline-core`, `gcp-pipeline-beam`, `gcp-pipeline-orchestration`, `gcp-pipeline-transform`, `gcp-pipeline-tester`) are published as Python packages to **PyPI** under the umbrella package `gcp-pipeline-framework`.

- Current version: `1.0.7`
- PyPI: https://pypi.org/project/gcp-pipeline-framework/
- Libraries must be published to PyPI before deploying application units that depend on them.
- Use the `[publish:pypi]` or `[publish:deploy]` commit keyword to trigger publishing workflows.

### Containerisation Strategy

| Deployment Unit | Requires Docker? | Reason |
| :--- | :--- | :--- |
| **Ingestion** (`original-data-to-bigqueryload`) | Yes | Dataflow Flex Templates require a custom Docker image registered in GCR. |
| **Transformation** (`bigquery-to-mapped-product`) | No | Executed as dbt code using standard dbt-bigquery runners. |
| **Orchestration** (`data-pipeline-orchestrator`) | No | Deployed as Python DAG files to the Cloud Composer GCS bucket. |

### Step 2.1: Deploy Ingestion Unit

1. Build the Dataflow Flex Template container. The Dockerfile installs `gcp-pipeline-framework` from PyPI.
2. Push the Docker image to GCR: `generic-ingestion:{version}`.
3. Publish the Flex Template JSON to GCS.

### Step 2.2: Deploy Transformation Unit

1. Validate dbt models against the target BigQuery project.
2. Publish dbt artifacts and configurations.
3. dbt macros are pulled from `gcp-pipeline-transform` via `dbt deps`.

### Step 2.3: Deploy Orchestration Unit

1. Upload Airflow DAGs to the Cloud Composer DAGs bucket (`gs://<composer-bucket>/dags/`).
2. Update Cloud Composer environment PyPI dependencies to include `gcp-pipeline-framework==1.0.7`.
3. Cloud Composer environment: `generic-{ENV}-composer`.

### Automatic Deployment

Pipelines deploy automatically when you push to `main` with changes in:

- `deployments/original-data-to-bigqueryload/**` → Triggers ingestion deployment
- `deployments/bigquery-to-mapped-product/**` → Triggers transformation deployment
- `deployments/data-pipeline-orchestrator/**` → Triggers orchestration deployment
- `gcp-pipeline-libraries/**` → Triggers relevant deployments
- `infrastructure/terraform/**` → Triggers infrastructure updates

### Manual Deployment

```bash
# Trigger the Generic deployment workflow
gh workflow run deploy-generic.yml

# Check status
gh run list --workflow=deploy-generic.yml --limit 3
```

### CI/CD Commit Keywords

| Keyword | Effect |
|---------|--------|
| *(no keyword, push to main)* | Auto-deploys path-filtered deployment units |
| `[publish:deploy]` | Publishes libraries to PyPI, then triggers full deployment |
| `[publish:pypi]` | Publishes libraries to PyPI only |

---

## Phase 3: Testing (Manual)

### Step 3.1: Upload Test Data

```bash
./scripts/gcp/06_test_pipeline.sh generic
```

Or manually:

```bash
PROJECT_ID=$(gcloud config get-value project)
ENV="dev"

# Create test file with HDR/TRL envelope
cat > /tmp/generic_customers.csv << 'EOF'
HDR|Generic|CUSTOMERS|20260301
customer_id,name,email,status
CUST001,John Doe,john@example.com,ACTIVE
CUST002,Jane Smith,jane@example.com,ACTIVE
TRL|RecordCount=2|Checksum=abc123
EOF

# Upload to landing bucket
gsutil cp /tmp/generic_customers.csv \
    gs://${PROJECT_ID}-generic-${ENV}-landing/generic/customers/

# Create and upload trigger file (.ok)
touch /tmp/generic_customers.csv.ok
gsutil cp /tmp/generic_customers.csv.ok \
    gs://${PROJECT_ID}-generic-${ENV}-landing/generic/customers/

# GCS OBJECT_FINALIZE on the .ok file automatically notifies Pub/Sub
# To trigger manually if GCS notification is not configured:
gcloud pubsub topics publish generic-file-notifications \
    --message='{"bucket": "'${PROJECT_ID}'-generic-'${ENV}'-landing", "name": "generic/customers/generic_customers.csv.ok", "eventType": "OBJECT_FINALIZE"}'
```

### Step 3.2: Monitor Pipeline

```bash
# Monitor Pub/Sub messages
gcloud pubsub subscriptions pull generic-pipeline-events-sub --auto-ack

# Check BigQuery for loaded data
bq query --use_legacy_sql=false \
    'SELECT * FROM odp_generic.customers LIMIT 10'

# Check job control table
bq query --use_legacy_sql=false \
    'SELECT run_id, system_id, entity_type, status, started_at
     FROM job_control.pipeline_jobs
     ORDER BY started_at DESC
     LIMIT 10'

# Check Dataflow jobs
gcloud dataflow jobs list --status=active

# Check Cloud Composer DAG runs
gcloud composer environments run generic-dev-composer \
    --location europe-west2 \
    dags list
```

---

## Cleanup

### Delete Infrastructure (Keep Project)

```bash
./scripts/gcp/cleanup_infrastructure.sh all
```

### Delete Entire Project

```bash
./scripts/gcp/delete_project.sh
```

---

## Troubleshooting

### "Bucket doesn't exist" Terraform backend error

```bash
# Create the Terraform state bucket manually
gsutil mb -l europe-west2 gs://gcp-pipeline-terraform-state
gsutil versioning set on gs://gcp-pipeline-terraform-state
```

### "Permission denied" error

```bash
# Check service account IAM roles
gcloud projects get-iam-policy $(gcloud config get-value project) \
    --flatten="bindings[].members" \
    --filter="bindings.members:github-actions-deploy"
```

### GitHub secrets not set

```bash
# Verify secrets exist
gh secret list

# Re-add if missing
./scripts/gcp/04_setup_github_actions.sh
```

### Cloud Composer DAG not appearing

```bash
# Verify DAG file was uploaded to the correct bucket
gcloud composer environments describe generic-dev-composer \
    --location europe-west2 \
    --format="value(config.dagGcsPrefix)"

# List DAG files
gsutil ls gs://<composer-dag-bucket>/dags/
```

---

## Quick Reference

### GCP Resources per Environment

| Resource | Name Pattern |
|----------|-------------|
| Landing Bucket | `{PROJECT_ID}-generic-{ENV}-landing` |
| Archive Bucket | `{PROJECT_ID}-generic-{ENV}-archive` |
| Error Bucket | `{PROJECT_ID}-generic-{ENV}-error` |
| Temp Bucket | `{PROJECT_ID}-generic-{ENV}-temp` |
| ODP Dataset | `odp_generic` |
| FDP Dataset | `fdp_generic` |
| Job Control Dataset | `job_control` |
| File Notifications Topic | `generic-file-notifications` |
| Pipeline Events Topic | `generic-pipeline-events` |
| Cloud Composer Environment | `generic-{ENV}-composer` |
| Terraform State Bucket | `gcp-pipeline-terraform-state` |
| Terraform State Prefix | `generic/{env}` |

### Docker Images in GCR

| Image | Purpose |
|-------|---------|
| `generic-ingestion:{version}` | Dataflow Flex Template for ODP load |
| `generic-transformation:{version}` | dbt runner for FDP transformation |
| `generic-dag-validator:{version}` | CI validation of Airflow DAGs |
