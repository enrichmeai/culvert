# GCP Deployment Guide

This guide explains how to set up and deploy the Legacy Migration Pipeline to GCP.

## Overview

The deployment process has 3 phases:

| Phase | What | How | When |
|-------|------|-----|------|
| **1. Infrastructure Setup** | Create GCS buckets, BigQuery datasets, Pub/Sub topics, Terraform state | `gcloud` CLI (manual) | Once per environment |
| **2. Pipeline Deployment** | Deploy Dataflow templates, DAGs | GitHub Actions (on commit) | On each commit |
| **3. Testing** | Upload test files, trigger pipeline | Test scripts (manual) | As needed |

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

# Terraform (optional, for local development)
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

## Phase 1: Infrastructure Setup (One-time)

Run these commands **once** to create the required GCP infrastructure.

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
    cloudkms.googleapis.com \
    monitoring.googleapis.com \
    logging.googleapis.com \
    telemetry.googleapis.com
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

### Step 1.3: Create Infrastructure (Buckets, Datasets, Topics)
```bash
./scripts/gcp/03_create_infrastructure.sh all
```

Or manually:
```bash
PROJECT_ID=$(gcloud config get-value project)
REGION="europe-west2"

# Generic Buckets
gsutil mb -l $REGION gs://${PROJECT_ID}-generic-landing
gsutil mb -l $REGION gs://${PROJECT_ID}-generic-archive
gsutil mb -l $REGION gs://${PROJECT_ID}-generic-error
gsutil mb -l $REGION gs://${PROJECT_ID}-generic-temp

# Generic BigQuery Datasets
bq mk --location=$REGION odp_generic
bq mk --location=$REGION fdp_generic
bq mk --location=$REGION job_control

# Generic Pub/Sub Topics
gcloud pubsub topics create generic-file-notifications
gcloud pubsub topics create generic-pipeline-events
gcloud pubsub subscriptions create generic-file-notifications-sub --topic=generic-file-notifications
gcloud pubsub subscriptions create generic-pipeline-events-sub --topic=generic-pipeline-events

# Generic Buckets
gsutil mb -l $REGION gs://${PROJECT_ID}-generic-landing
gsutil mb -l $REGION gs://${PROJECT_ID}-generic-archive
gsutil mb -l $REGION gs://${PROJECT_ID}-generic-error
gsutil mb -l $REGION gs://${PROJECT_ID}-generic-temp

# Generic BigQuery Datasets
bq mk --location=$REGION odp_generic
bq mk --location=$REGION fdp_generic

# Generic Pub/Sub Topics
gcloud pubsub topics create generic-file-notifications
gcloud pubsub topics create generic-pipeline-events
gcloud pubsub subscriptions create generic-file-notifications-sub --topic=generic-file-notifications
gcloud pubsub subscriptions create generic-pipeline-events-sub --topic=generic-pipeline-events
```

### Step 1.4: Setup GitHub Actions Service Account
```bash
./scripts/gcp/04_setup_github_actions.sh
```

This creates:
- Service account: `github-actions-deploy@<PROJECT>.iam.gserviceaccount.com`
- IAM roles for deployment
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

The pipeline follows a **3-unit deployment model** (Ingestion, Transformation, Orchestration) to enable independent release cycles and minimal environment overhead.

### Shared Libraries (Nexus Packages)
The shared libraries (`gcp-pipeline-core`, `gcp-pipeline-beam`, etc.) are managed as Python packages in **Nexus**. 
- They must be published to Nexus before deploying the application units.
- Use the automated workflows to automate the publishing.
- The pipeline handles authentication and URLs automatically.

### Containerization Strategy
| Deployment Unit | Requires Docker? | Reason |
| :--- | :--- | :--- |
| **Ingestion** (`*-ingestion`) | **Yes** | Dataflow Flex Templates require a custom Docker image to be registered in GCR/GAR. |
| **Transformation** (`*-transformation`) | **No** | Executed as dbt code; uses standard dbt-bigquery runners. |
| **Orchestration** (`*-orchestration`) | **No** | Deployed as Python DAG files to Cloud Composer (GCS bucket). |

### Step 2.1: Deploy Ingestion Unit (`*-ingestion`)
1. Build the Dataflow Flex Template container.
   - The Dockerfile pulls the shared libraries from **Nexus**.
   - Credentials and URLs are provided by the **Nexus Connector**.
2. Publish the template JSON to GCS and the image to GCR/GAR.

### Step 2.2: Deploy Transformation Unit (`*-transformation`)
1. Validate dbt models.
2. Publish dbt artifacts and configurations.
3. Consumes shared dbt macros from the library repository or local references.

### Step 2.3: Deploy Orchestration Unit (`*-orchestration`)
1. Upload Airflow DAGs to the Cloud Composer DAGs bucket (`gs://<composer-bucket>/dags/`).
2. Update Composer environment dependencies (PyPI packages) to point to the shared libraries in Nexus.
3. Note: Orchestration does **not** require `apache-beam` as it only triggers jobs.

### Automatic Deployment
Pipelines deploy automatically when you push to `main` branch with changes in:
- `deployments/*-ingestion/**` → Triggers ingestion deployment
- `deployments/*-transformation/**` → Triggers transformation deployment
- `deployments/*-orchestration/**` → Triggers orchestration deployment
- `gcp-pipeline-libraries/**` → Triggers relevant deployments
- `infrastructure/terraform/**` → Triggers infrastructure updates

### Manual Deployment
```bash
# Trigger Generic deployment
gh workflow run deploy-generic.yml

# Trigger Generic deployment
gh workflow run deploy-generic.yml

# Check status
gh run list --workflow=deploy-generic.yml --limit 3
```

---

## Phase 3: Testing (Manual)

### Step 3.1: Upload Test Data
```bash
./scripts/gcp/06_test_pipeline.sh generic
```

Or manually:
```bash
PROJECT_ID=$(gcloud config get-value project)
DATE=$(date +%Y%m%d)

# Create test file
cat > /tmp/generic_customers.csv << 'EOF'
HDR|Generic|Customers|20260104
customer_id,name,email,status
CUST001,John Doe,john@example.com,ACTIVE
CUST002,Jane Smith,jane@example.com,ACTIVE
TRL|RecordCount=2|Checksum=abc123
EOF

# Upload to landing bucket
gsutil cp /tmp/generic_customers.csv gs://${PROJECT_ID}-generic-landing/

# Create trigger file (.ok)
touch /tmp/generic_customers.csv.ok
gsutil cp /tmp/generic_customers.csv.ok gs://${PROJECT_ID}-generic-landing/

# Publish notification
gcloud pubsub topics publish generic-file-notifications \
    --message='{"file": "generic_customers.csv", "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}'
```

### Step 3.2: Monitor Pipeline
```bash
# Check Pub/Sub messages
gcloud pubsub subscriptions pull generic-pipeline-events-sub --auto-ack

# Check BigQuery for loaded data
bq query --use_legacy_sql=false 'SELECT * FROM odp_generic.customers LIMIT 10'

# Check Dataflow jobs
gcloud dataflow jobs list --status=active
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

### "Bucket doesn't exist" error
```bash
# Create the Terraform state bucket
gsutil mb -l europe-west2 gs://gcp-pipeline-terraform-state
```

### "Permission denied" error
```bash
# Check service account roles
gcloud projects get-iam-policy $(gcloud config get-value project) \
    --flatten="bindings[].members" \
    --filter="bindings.members:github-actions-deploy"
```

### GitHub secrets not set
```bash
# Verify secrets
gh secret list

# Re-add if missing
./scripts/gcp/04_setup_github_actions.sh
```

---

## Quick Reference

| Resource | Generic | Generic |
|----------|-----|-----|
| Landing Bucket | `{project}-generic-landing` | `{project}-generic-landing` |
| Archive Bucket | `{project}-generic-archive` | `{project}-generic-archive` |
| Error Bucket | `{project}-generic-error` | `{project}-generic-error` |
| ODP Dataset | `odp_generic` | `odp_generic` |
| FDP Dataset | `fdp_generic` | `fdp_generic` |
| Notification Topic | `generic-file-notifications` | `generic-file-notifications` |
| Events Topic | `generic-pipeline-events` | `generic-pipeline-events` |

