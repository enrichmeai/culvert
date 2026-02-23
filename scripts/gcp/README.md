# GCP Setup Scripts

Complete scripts for setting up, testing, and managing GCP infrastructure for the Legacy Migration Pipeline.

## Quick Reference

| Action | Command |
|--------|---------|
| **Deploy Everything** | `./scripts/gcp/deploy_all.sh all` |
| **Reset Everything** | `./scripts/gcp/00_full_reset.sh` |
| **Test Application1 Pipeline** | `./scripts/gcp/06_test_pipeline.sh application1` |
| **Test Application2 Pipeline** | `./scripts/gcp/06_test_pipeline.sh application2` |

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

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `00_full_reset.sh` | Delete ALL resources | Start fresh / cleanup |
| `01_enable_services.sh` | Enable GCP APIs | First time setup |
| `02_create_state_bucket.sh` | Create Terraform state bucket | First time setup |
| `03_create_infrastructure.sh` | Create buckets, datasets, Pub/Sub | After reset or first time |
| `setup_github_actions.sh` | Create service account for CI/CD | First time setup |
| `05_verify_setup.sh` | Verify all resources exist | After any setup step |
| `06_test_pipeline.sh` | Upload test data | Testing pipeline |
| `07_cleanup.sh` | Delete infrastructure (partial) | Cleanup specific deployment |
| `deploy_all.sh` | Run all setup steps | One-command setup |
| `e2e_test_em.sh` | End-to-end Application1 test | Testing |

---

## Validating the 3-Unit Deployment
The deployment scripts provide a way to verify the independence of each unit:

### 1. Ingestion Testing (Unit 1)
You can test the Dataflow ingestion without Airflow:
```bash
./scripts/gcp/06_test_pipeline.sh application1
# Then manually check BigQuery ODP tables
bq query 'SELECT count(*) FROM odp_application1.customers'
```
This proves the Ingestion unit is self-contained.

### 2. Transformation Testing (Unit 2)
You can test dbt transformations without running the full ingestion:
```bash
cd deployments/application1-transformation/dbt
dbt run --select fdp.application1
```
This proves the Transformation unit is independent.

### 3. Orchestration Testing (Unit 3)
The `06_test_pipeline.sh` script simulates the entry point by uploading an `.ok` file and publishing a Pub/Sub message. You can then monitor the Airflow UI to see the sequence of **separate DAGs** being triggered:
1. `application2_pubsub_trigger_dag` detects the file.
2. `application2_odp_application2d_dag` starts the Dataflow job.
3. `application2_fdp_transform_dag` starts the dbt run.

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
| `cloudbuild.googleapis.com` | CI/CD builds |
| `containerregistry.googleapis.com` | Docker images |
| `artifactregistry.googleapis.com` | Artifacts |
| `composer.googleapis.com` | Airflow (orchestration) |
| `compute.googleapis.com` | Compute (for Dataflow) |

### GCS Buckets

| Bucket | Purpose |
|--------|---------|
| `{project}-application1-landing` | Application1 raw file uploads |
| `{project}-application1-archive` | Application1 processed files |
| `{project}-application1-error` | Application1 failed files |
| `{project}-application1-temp` | Application1 temporary files |
| `{project}-application2-landing` | Application2 raw file uploads |
| `{project}-application2-archive` | Application2 processed files |
| `{project}-application2-error` | Application2 failed files |
| `{project}-application2-temp` | Application2 temporary files |
| `gdw-terraform-state` | Terraform state storage |

### BigQuery Datasets

| Dataset | Purpose |
|---------|---------|
| `odp_application1` | Application1 Original Data Product (raw) |
| `fdp_application1` | Application1 Foundation Data Product (transformed) |
| `odp_application2` | Application2 Original Data Product (raw) |
| `fdp_application2` | Application2 Foundation Data Product (transformed) |
| `job_control` | Pipeline job tracking |

### Pub/Sub Topics & Subscriptions

| Topic | Subscription | Purpose |
|-------|--------------|---------|
| `application1-file-notifications` | `application1-file-notifications-sub` | Application1 file arrival events |
| `application1-pipeline-events` | `application1-pipeline-events-sub` | Application1 pipeline status events |
| `application2-file-notifications` | `application2-file-notifications-sub` | Application2 file arrival events |
| `application2-pipeline-events` | `application2-pipeline-events-sub` | Application2 pipeline status events |

### Service Accounts

| Service Account | Purpose | Roles |
|-----------------|---------|-------|
| `github-actions-deploy` | CI/CD deployment | BigQuery Admin, Storage Admin, Pub/Sub Admin, Dataflow Admin, IAM Admin, Composer Admin |
| `application1-dataflow-sa` | Application1 Dataflow jobs | Dataflow Worker, BigQuery Data Editor, Storage Object Admin |
| `application1-dbt-sa` | Application1 dbt transformations | BigQuery Data Editor |
| `application1-composer-sa` | Application1 Airflow orchestration | Composer Worker, Dataflow Admin |
| `application2-dataflow-sa` | Application2 Dataflow jobs | Dataflow Worker, BigQuery Data Editor, Storage Object Admin |
| `application2-dbt-sa` | Application2 dbt transformations | BigQuery Data Editor |

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
./scripts/gcp/06_test_pipeline.sh application1
./scripts/gcp/06_test_pipeline.sh application2
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
gh workflow run deploy-application1.yml
gh workflow run deploy-application2.yml

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
./scripts/gcp/deploy_all.sh application1   # Just Application1
./scripts/gcp/deploy_all.sh application2  # Just Application2
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

### Example Application1 Customers File
```
HDR|Application1|Customers|20260104
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
│  Or manual: gh workflow run deploy-application1.yml                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                       TESTING                                │
│  (Run locally with gcloud CLI)                               │
├─────────────────────────────────────────────────────────────┤
│  Step 6: Test Pipeline  → 06_test_pipeline.sh application1             │
│                                                              │
│  This uploads test CSV files and publishes Pub/Sub messages  │
└─────────────────────────────────────────────────────────────┘
```

## What Gets Created

### Infrastructure (Step 3)

**Application1 Deployment:**
- Buckets: `{project}-application1-landing`, `{project}-application1-archive`, `{project}-application1-error`, `{project}-application1-temp`
- Datasets: `odp_application1`, `fdp_application1`, `job_control`
- Topics: `application1-file-notifications`, `application1-pipeline-events`

**Application2 Deployment:**
- Buckets: `{project}-application2-landing`, `{project}-application2-archive`, `{project}-application2-error`, `{project}-application2-temp`
- Datasets: `odp_application2`, `fdp_application2`
- Topics: `application2-file-notifications`, `application2-pipeline-events`

### GitHub Secrets (Step 4)

| Secret | Description |
|--------|-------------|
| `GCP_SA_KEY` | Service account JSON key |
| `GCP_PROJECT_ID` | GCP project ID |

## Cleanup

```bash
# Delete Application1 only
./scripts/gcp/07_cleanup.sh application1

# Delete Application2 only
./scripts/gcp/07_cleanup.sh application2

# Delete everything
./scripts/gcp/07_cleanup.sh all
```

