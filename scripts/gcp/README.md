# GCP Setup Scripts

Complete scripts for setting up, testing, and managing GCP infrastructure for the Legacy Migration Pipeline.

> **Last Updated:** March 2026

## Quick Reference

| Action | Command |
|--------|---------|
| **Full Infrastructure Setup** | `./scripts/gcp/setup_gke_infrastructure.sh` |
| **Verify Infrastructure** | `./scripts/gcp/verify_infrastructure.sh` |
| **End-to-End Test** | `./scripts/gcp/e2e_automation_test.sh` |
| **Deploy to GKE** | `./scripts/gcp/deploy_to_gke.sh` |
| **Reset Everything** | `./scripts/gcp/00_full_reset.sh --force` |

## Scripts Overview

### Infrastructure Setup

| Script | Description |
|--------|-------------|
| `setup_gke_infrastructure.sh` | **MAIN SETUP** - Creates GKE, GCS, BigQuery, Pub/Sub, service accounts |
| `01_enable_services.sh` | Enable required GCP APIs only |
| `02_create_state_bucket.sh` | Create Terraform state bucket |
| `03_create_infrastructure.sh` | Create infrastructure via Terraform |

### Verification & Testing

| Script | Description |
|--------|-------------|
| `verify_infrastructure.sh` | **NEW** - Verify all resources are properly configured |
| `e2e_automation_test.sh` | **NEW** - Run end-to-end pipeline test |
| `05_verify_setup.sh` | Legacy verification script |
| `06_test_pipeline.sh` | Test specific pipeline |

### Deployment

| Script | Description |
|--------|-------------|
| `deploy_to_gke.sh` | Deploy Airflow and DAGs to GKE |
| `deploy_all.sh` | Deploy everything (legacy) |
| `quick_deploy.sh` | Quick deployment for testing |

### Cleanup

| Script | Description |
|--------|-------------|
| `00_full_reset.sh` | **DELETE EVERYTHING** - Avoid charges |
| `07_cleanup.sh` | Clean up specific resources |
| `quick_cleanup.sh` | Quick cleanup |

---

## Typical Workflow

```bash
# 1. Set project
gcloud config set project YOUR_PROJECT_ID

# 2. Setup infrastructure
./scripts/gcp/setup_gke_infrastructure.sh

# 3. Verify setup
./scripts/gcp/verify_infrastructure.sh

# 4. Build Airflow image
cd infrastructure/k8s/airflow
gcloud builds submit --tag gcr.io/$(gcloud config get-value project)/airflow-custom:latest .

# 5. Install Airflow
helm install airflow apache-airflow/airflow \
  --namespace airflow --create-namespace \
  --version 1.11.0 \
  --set images.airflow.repository=gcr.io/$(gcloud config get-value project)/airflow-custom \
  --set images.airflow.tag=latest

# 6. Deploy DAGs
gsutil -m rsync -r deployments/data-pipeline-orchestrator/dags/ gs://$(gcloud config get-value project)-airflow-dags/

# 7. Run E2E test
./scripts/gcp/e2e_automation_test.sh

# 8. Clean up (when done)
./scripts/gcp/00_full_reset.sh --force
```

---

## Architecture

```
Deployments:
├── data-pipeline-orchestrator/     # Airflow DAGs (runs on GKE)
├── original-data-to-bigqueryload/  # Beam ingestion (runs on Dataflow)
├── bigquery-to-mapped-product/     # dbt transforms (runs on BigQuery)
├── mainframe-segment-transform/    # Segment processing
└── spanner-to-bigquery-load/       # Spanner source
```

---

## Prerequisites

### 1. Install Google Cloud SDK
```bash
# macOS
brew install google-cloud-sdk

# Or download from https://cloud.google.com/sdk/docs/install
```

### 2. Install GitHub CLI
```bash
# macOS
brew install gh

# Or download from https://cli.github.com/
```

### 3. Authenticate
```bash
# Login to GCP
gcloud auth login

# Set your project
gcloud config set project <YOUR_PROJECT_ID>

# Login to GitHub
gh auth login
```

---

## Scripts Overview

### Infrastructure Setup

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `setup_gke_infrastructure.sh` | Create GKE cluster, buckets, datasets, Pub/Sub | **Start here for GKE** |
| `01_enable_services.sh` | Enable GCP APIs | First time setup |
| `02_create_state_bucket.sh` | Create Terraform state bucket | First time setup |
| `03_create_infrastructure.sh` | Create buckets, datasets, Pub/Sub (legacy) | Without GKE |
| `setup_github_actions.sh` | Create service account for CI/CD | First time setup |

### Deployment

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `deploy_to_gke.sh` | Deploy DAGs and k8s resources | Regular deployments |
| `deploy_to_gke.sh --dags-only` | Sync DAGs only | Quick DAG updates |
| `deploy_to_gke.sh --dataflow-templates` | Build and deploy Dataflow templates | When ingestion code changes |
| `deploy_all.sh` | Run all setup steps (legacy) | Cloud Composer setup |

### Verification & Testing

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `05_verify_setup.sh` | Verify all resources exist | After any setup step |
| `06_test_pipeline.sh` | Upload test data | Testing pipeline |

### Cleanup

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `00_full_reset.sh` | Delete ALL resources | Start fresh |
| `07_cleanup.sh` | Delete infrastructure (partial) | Cleanup specific deployment |
| `cleanup_all.sh` | Cleanup including GKE | Full cleanup |

---

## GKE Deployment (Recommended)

### One-Time Setup

```bash
# 1. Create all infrastructure (GKE, buckets, BigQuery, Pub/Sub)
./scripts/gcp/setup_gke_infrastructure.sh

# 2. Install Airflow on GKE
helm repo add apache-airflow https://airflow.apache.org
helm repo update
helm install airflow apache-airflow/airflow \
  --namespace airflow --create-namespace \
  --values infrastructure/k8s/airflow/values.yaml

# 3. Deploy DAGs
./scripts/gcp/deploy_to_gke.sh --dags-only
```

### Regular Deployments

```bash
# Deploy DAGs only (fast)
./scripts/gcp/deploy_to_gke.sh --dags-only

# Deploy everything including Dataflow templates
./scripts/gcp/deploy_to_gke.sh --dataflow-templates
```

### Access Airflow UI

```bash
kubectl port-forward svc/airflow-webserver 8080:8080 -n airflow
# Open http://localhost:8080
```

---

## Validating the 3-Unit Deployment
The deployment scripts provide a way to verify the independence of each unit:

### 1. Ingestion Testing (Unit 1)
You can test the Dataflow ingestion without Airflow:
```bash
./scripts/gcp/06_test_pipeline.sh generic
# Then manually check BigQuery ODP tables
bq query 'SELECT count(*) FROM odp_generic.customers'
```
This proves the Ingestion unit is self-contained.

### 2. Transformation Testing (Unit 2)
You can test dbt transformations without running the full ingestion:
```bash
cd deployments/generic-transformation/dbt
dbt run --select fdp.generic
```
This proves the Transformation unit is independent.

### 3. Orchestration Testing (Unit 3)
The `06_test_pipeline.sh` script simulates the entry point by uploading an `.ok` file and publishing a Pub/Sub message. You can then monitor the Airflow UI to see the sequence of **separate DAGs** being triggered:
1. `generic_pubsub_trigger_dag` detects the file.
2. `generic_odp_genericd_dag` starts the Dataflow job.
3. `generic_fdp_transform_dag` starts the dbt run.

This proves the **Micro-Orchestration** pattern where failure in one step doesn't force a full re-run of the entire pipeline.

---

## What Gets Created

### GCP Services Enabled

| Service | Purpose |
|---------|---------|
| `bigquery.googleapis.com` | Data warehouse |
| `storage.googleapis.com` | GCS buckets |
| `pubsub.googleapis.com` | Event messaging |
| `dataflow.googleapis.com` | Data processing |
| `cloudkms.googleapis.com` | Key management |
| `iam.googleapis.com` | Identity management |
| `monitoring.googleapis.com` | Monitoring |
| `logging.googleapis.com` | Logging |
| `telemetry.googleapis.com` | OTel ingestion API |
| `cloudbuild.googleapis.com` | CI/CD builds |
| `containerregistry.googleapis.com` | Docker images |
| `artifactregistry.googleapis.com` | Artifacts |
| `composer.googleapis.com` | Airflow (orchestration) |
| `compute.googleapis.com` | Compute (for Dataflow) |

### GCS Buckets

| Bucket | Purpose |
|--------|---------|
| `{project}-generic-landing` | Generic raw file uploads |
| `{project}-generic-archive` | Generic processed files |
| `{project}-generic-error` | Generic failed files |
| `{project}-generic-temp` | Generic temporary files |
| `{project}-generic-landing` | Generic raw file uploads |
| `{project}-generic-archive` | Generic processed files |
| `{project}-generic-error` | Generic failed files |
| `{project}-generic-temp` | Generic temporary files |
| `gdw-terraform-state` | Terraform state storage |

### BigQuery Datasets

| Dataset | Purpose |
|---------|---------|
| `odp_generic` | Generic Original Data Product (raw) |
| `fdp_generic` | Generic Foundation Data Product (transformed) |
| `odp_generic` | Generic Original Data Product (raw) |
| `fdp_generic` | Generic Foundation Data Product (transformed) |
| `job_control` | Pipeline job tracking |

### Pub/Sub Topics & Subscriptions

| Topic | Subscription | Purpose |
|-------|--------------|---------|
| `generic-file-notifications` | `generic-file-notifications-sub` | Generic file arrival events |
| `generic-pipeline-events` | `generic-pipeline-events-sub` | Generic pipeline status events |
| `generic-file-notifications` | `generic-file-notifications-sub` | Generic file arrival events |
| `generic-pipeline-events` | `generic-pipeline-events-sub` | Generic pipeline status events |

### Service Accounts

| Service Account | Purpose | Roles |
|-----------------|---------|-------|
| `github-actions-deploy` | CI/CD deployment | BigQuery Admin, Storage Admin, Pub/Sub Admin, Dataflow Admin, IAM Admin, Composer Admin |
| `generic-dataflow-sa` | Generic Dataflow jobs | Dataflow Worker, BigQuery Data Editor, Storage Object Admin |
| `generic-dbt-sa` | Generic dbt transformations | BigQuery Data Editor |
| `generic-composer-sa` | Generic Airflow orchestration | Composer Worker, Dataflow Admin |
| `generic-dataflow-sa` | Generic Dataflow jobs | Dataflow Worker, BigQuery Data Editor, Storage Object Admin |
| `generic-dbt-sa` | Generic dbt transformations | BigQuery Data Editor |

### GitHub Secrets Required

| Secret | Purpose | How to Get |
|--------|---------|------------|
| `GCP_SA_KEY` | Service account JSON key | `./scripts/gcp/setup_github_actions.sh` |
| `GCP_PROJECT_ID` | GCP project ID | Your project ID |
| `COMPOSER_BUCKET` | Composer DAGs bucket | From Composer environment |

---

## Workflows

### First Time Setup (Local)

```bash
# 1. Clone repository
git clone https://github.com/enrichmeai/legacy-migration-reference.git
cd legacy-migration-reference

# 2. Authenticate
gcloud auth login
gcloud config set project <YOUR_PROJECT_ID>

# 3. Make scripts executable
chmod +x scripts/gcp/*.sh

# 4. Deploy everything
./scripts/gcp/deploy_all.sh all

# 5. Test pipeline
./scripts/gcp/06_test_pipeline.sh generic
```

### Reset and Redeploy

```bash
# Delete everything
./scripts/gcp/00_full_reset.sh

# Redeploy
./scripts/gcp/deploy_all.sh all
```

### GitHub Actions Deployment

After local setup, push to GitHub to trigger automatic deployment:

```bash
git push origin main

# Or manually trigger
gh workflow run deploy-generic.yml
gh workflow run deploy-generic.yml

# Check status
gh run list --limit 5
```

---

## IAM Permissions Reference

### GitHub Actions Service Account Roles

The `github-actions-deploy` service account needs these roles:

| Role | Purpose |
|------|---------|
| `roles/bigquery.admin` | Create/manage BigQuery datasets |
| `roles/storage.admin` | Create/manage GCS buckets |
| `roles/pubsub.admin` | Create/manage Pub/Sub topics |
| `roles/dataflow.admin` | Create/manage Dataflow jobs |
| `roles/iam.serviceAccountUser` | Use service accounts |
| `roles/iam.serviceAccountAdmin` | Create service accounts |
| `roles/resourcemanager.projectIamAdmin` | Manage IAM policies |
| `roles/logging.admin` | Manage logging |
| `roles/monitoring.admin` | Manage monitoring |
| `roles/composer.admin` | Create Composer environments |
| `roles/cloudbuild.builds.builder` | Build container images |

---

## Troubleshooting

### "Permission denied" errors
```bash
# Re-run setup to grant all permissions
./scripts/gcp/deploy_all.sh all
```

### "Resource already exists" errors
```bash
# Reset everything and start fresh
./scripts/gcp/00_full_reset.sh
./scripts/gcp/deploy_all.sh all
```

### "API not enabled" errors
```bash
# Re-enable all services
./scripts/gcp/01_enable_services.sh
```

### Check what exists
```bash
# Verify all resources
./scripts/gcp/05_verify_setup.sh
```

---

## Cost Considerations

| Resource | Cost Impact | Notes |
|----------|-------------|-------|
| GCS Buckets | Low | Pay per storage used |
| BigQuery Datasets | Low | Pay per query/storage |
| Pub/Sub | Low | Pay per message |
| Dataflow | Medium | Pay per worker-hour |
| **Cloud Composer** | **High** | ~$300-500/month minimum |

### To Minimize Costs
```bash
# Delete everything when not testing
./scripts/gcp/00_full_reset.sh

# Only deploy what you need
./scripts/gcp/deploy_all.sh generic   # Just Generic
./scripts/gcp/deploy_all.sh generic  # Just Generic
```

---

## File Format Reference

### Test Data Format (HDR/TRL)
```
HDR|{SYSTEM}|{ENTITY}|{YYYYMMDD}     ← Header record
{csv_header_row}                      ← Column names
{data_row_1}                          ← Data records
{data_row_2}
TRL|RecordCount={n}|Checksum={hash}   ← Trailer record
```

### Example Generic Customers File
```
HDR|Generic|Customers|20260104
customer_id,name,email,status,created_date
CUST001,John Doe,john@example.com,ACTIVE,2025-01-15
CUST002,Jane Smith,jane@example.com,ACTIVE,2025-01-14
TRL|RecordCount=2|Checksum=abc123
```

## Prerequisites

1. **Google Cloud SDK** installed and authenticated:
   ```bash
   gcloud auth login
   gcloud config set project <PROJECT_ID>
   ```

2. **GitHub CLI** installed and authenticated:
   ```bash
   gh auth login
   ```

## Deployment Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    ONE-TIME SETUP                           │
│  (Run locally with gcloud CLI)                              │
├─────────────────────────────────────────────────────────────┤
│  Step 1: Enable Services       → 01_enable_services.sh      │
│  Step 2: Create State Bucket   → 02_create_state_bucket.sh  │
│  Step 3: Create Infrastructure → 03_create_infrastructure.sh│
│  Step 4: Setup GitHub Actions  → 04_setup_github_actions.sh │
│  Step 5: Verify Setup          → 05_verify_setup.sh         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   PIPELINE DEPLOYMENT                        │
│  (Automatic via GitHub Actions on push)                      │
├─────────────────────────────────────────────────────────────┤
│  git push  →  GitHub Actions  →  Deploy to GCP              │
│                                                              │
│  Or manual: gh workflow run deploy-generic.yml                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                       TESTING                                │
│  (Run locally with gcloud CLI)                               │
├─────────────────────────────────────────────────────────────┤
│  Step 6: Test Pipeline  → 06_test_pipeline.sh generic             │
│                                                              │
│  This uploads test CSV files and publishes Pub/Sub messages  │
└─────────────────────────────────────────────────────────────┘
```

## What Gets Created

### Infrastructure (Step 3)

**Generic Deployment:**
- Buckets: `{project}-generic-landing`, `{project}-generic-archive`, `{project}-generic-error`, `{project}-generic-temp`
- Datasets: `odp_generic`, `fdp_generic`, `job_control`
- Topics: `generic-file-notifications`, `generic-pipeline-events`

**Generic Deployment:**
- Buckets: `{project}-generic-landing`, `{project}-generic-archive`, `{project}-generic-error`, `{project}-generic-temp`
- Datasets: `odp_generic`, `fdp_generic`
- Topics: `generic-file-notifications`, `generic-pipeline-events`

### GitHub Secrets (Step 4)

| Secret | Description |
|--------|-------------|
| `GCP_SA_KEY` | Service account JSON key |
| `GCP_PROJECT_ID` | GCP project ID |

## Cleanup

```bash
# Delete Generic only
./scripts/gcp/07_cleanup.sh generic

# Delete Generic only
./scripts/gcp/07_cleanup.sh generic

# Delete everything
./scripts/gcp/07_cleanup.sh all
```

