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
    logging.googleapis.com
```

### Step 1.2: Create Terraform State Bucket
```bash
./scripts/gcp/02_create_state_bucket.sh
```

Or manually:
```bash
PROJECT_ID=$(gcloud config get-value project)
gsutil mb -l europe-west2 -p $PROJECT_ID gs://gdw-terraform-state
gsutil versioning set on gs://gdw-terraform-state
```

### Step 1.3: Create Infrastructure (Buckets, Datasets, Topics)
```bash
./scripts/gcp/03_create_infrastructure.sh all
```

Or manually:
```bash
PROJECT_ID=$(gcloud config get-value project)
REGION="europe-west2"

# EM Buckets
gsutil mb -l $REGION gs://${PROJECT_ID}-em-landing
gsutil mb -l $REGION gs://${PROJECT_ID}-em-archive
gsutil mb -l $REGION gs://${PROJECT_ID}-em-error
gsutil mb -l $REGION gs://${PROJECT_ID}-em-temp

# EM BigQuery Datasets
bq mk --location=$REGION odp_em
bq mk --location=$REGION fdp_em
bq mk --location=$REGION job_control

# EM Pub/Sub Topics
gcloud pubsub topics create em-file-notifications
gcloud pubsub topics create em-pipeline-events
gcloud pubsub subscriptions create em-file-notifications-sub --topic=em-file-notifications
gcloud pubsub subscriptions create em-pipeline-events-sub --topic=em-pipeline-events

# LOA Buckets
gsutil mb -l $REGION gs://${PROJECT_ID}-loa-landing
gsutil mb -l $REGION gs://${PROJECT_ID}-loa-archive
gsutil mb -l $REGION gs://${PROJECT_ID}-loa-error
gsutil mb -l $REGION gs://${PROJECT_ID}-loa-temp

# LOA BigQuery Datasets
bq mk --location=$REGION odp_loa
bq mk --location=$REGION fdp_loa

# LOA Pub/Sub Topics
gcloud pubsub topics create loa-file-notifications
gcloud pubsub topics create loa-pipeline-events
gcloud pubsub subscriptions create loa-file-notifications-sub --topic=loa-file-notifications
gcloud pubsub subscriptions create loa-pipeline-events-sub --topic=loa-pipeline-events
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

## Phase 2: Pipeline Deployment (GitHub Actions)

### Automatic Deployment
Pipelines deploy automatically when you push to `main` branch with changes in:
- `deployments/em/**` → Triggers EM deployment
- `deployments/loa/**` → Triggers LOA deployment
- `libraries/**` → Triggers both deployments
- `infrastructure/terraform/**` → Triggers infrastructure updates

### Manual Deployment
```bash
# Trigger EM deployment
gh workflow run deploy-em.yml

# Trigger LOA deployment
gh workflow run deploy-loa.yml

# Check status
gh run list --workflow=deploy-em.yml --limit 3
```

---

## Phase 3: Testing (Manual)

### Step 3.1: Upload Test Data
```bash
./scripts/gcp/06_test_pipeline.sh em
```

Or manually:
```bash
PROJECT_ID=$(gcloud config get-value project)
DATE=$(date +%Y%m%d)

# Create test file
cat > /tmp/em_customers.csv << 'EOF'
HDR|EM|Customers|20260104
customer_id,name,email,status
CUST001,John Doe,john@example.com,ACTIVE
CUST002,Jane Smith,jane@example.com,ACTIVE
TRL|RecordCount=2|Checksum=abc123
EOF

# Upload to landing bucket
gsutil cp /tmp/em_customers.csv gs://${PROJECT_ID}-em-landing/

# Create trigger file (.ok)
touch /tmp/em_customers.csv.ok
gsutil cp /tmp/em_customers.csv.ok gs://${PROJECT_ID}-em-landing/

# Publish notification
gcloud pubsub topics publish em-file-notifications \
    --message='{"file": "em_customers.csv", "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}'
```

### Step 3.2: Monitor Pipeline
```bash
# Check Pub/Sub messages
gcloud pubsub subscriptions pull em-pipeline-events-sub --auto-ack

# Check BigQuery for loaded data
bq query --use_legacy_sql=false 'SELECT * FROM odp_em.customers LIMIT 10'

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
gsutil mb -l europe-west2 gs://gdw-terraform-state
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

| Resource | EM | LOA |
|----------|-----|-----|
| Landing Bucket | `{project}-em-landing` | `{project}-loa-landing` |
| Archive Bucket | `{project}-em-archive` | `{project}-loa-archive` |
| Error Bucket | `{project}-em-error` | `{project}-loa-error` |
| ODP Dataset | `odp_em` | `odp_loa` |
| FDP Dataset | `fdp_em` | `fdp_loa` |
| Notification Topic | `em-file-notifications` | `loa-file-notifications` |
| Events Topic | `em-pipeline-events` | `loa-pipeline-events` |

