# GCP Setup Scripts

Step-by-step scripts to set up GCP infrastructure for the Legacy Migration Pipeline.

## Quick Start (One Command)

```bash
# Deploy everything
chmod +x scripts/gcp/*.sh
./scripts/gcp/deploy_all.sh all
```

## Full Reset (Start Fresh)

```bash
# Delete everything and start over
./scripts/gcp/00_full_reset.sh
./scripts/gcp/deploy_all.sh all
```

## Scripts Overview

| Script | Purpose |
|--------|---------|
| `00_full_reset.sh` | **DELETE everything** - buckets, datasets, topics, service accounts |
| `01_enable_services.sh` | Enable required GCP APIs |
| `02_create_state_bucket.sh` | Create Terraform state bucket |
| `03_create_infrastructure.sh` | Create buckets, datasets, Pub/Sub |
| `04_setup_github_actions.sh` | Create service account for CI/CD |
| `05_verify_setup.sh` | Verify all components are set up |
| `06_test_pipeline.sh` | Upload test data and trigger pipeline |
| `07_cleanup.sh` | Delete infrastructure (keeps project) |
| `deploy_all.sh` | **Run all steps** in order |
| `e2e_test_em.sh` | End-to-end test for EM pipeline |

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
│  Or manual: gh workflow run deploy-em.yml                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                       TESTING                                │
│  (Run locally with gcloud CLI)                               │
├─────────────────────────────────────────────────────────────┤
│  Step 6: Test Pipeline  → 06_test_pipeline.sh em             │
│                                                              │
│  This uploads test CSV files and publishes Pub/Sub messages  │
└─────────────────────────────────────────────────────────────┘
```

## What Gets Created

### Infrastructure (Step 3)

**EM Deployment:**
- Buckets: `{project}-em-landing`, `{project}-em-archive`, `{project}-em-error`, `{project}-em-temp`
- Datasets: `odp_em`, `fdp_em`, `job_control`
- Topics: `em-file-notifications`, `em-pipeline-events`

**LOA Deployment:**
- Buckets: `{project}-loa-landing`, `{project}-loa-archive`, `{project}-loa-error`, `{project}-loa-temp`
- Datasets: `odp_loa`, `fdp_loa`
- Topics: `loa-file-notifications`, `loa-pipeline-events`

### GitHub Secrets (Step 4)

| Secret | Description |
|--------|-------------|
| `GCP_SA_KEY` | Service account JSON key |
| `GCP_PROJECT_ID` | GCP project ID |

## Cleanup

```bash
# Delete EM only
./scripts/gcp/07_cleanup.sh em

# Delete LOA only
./scripts/gcp/07_cleanup.sh loa

# Delete everything
./scripts/gcp/07_cleanup.sh all
```

