# GCP Setup Scripts

Step-by-step scripts to set up GCP infrastructure for the Legacy Migration Pipeline.

## Quick Start

```bash
# Make all scripts executable
chmod +x scripts/gcp/*.sh

# Run steps 1-5 in order
./scripts/gcp/01_enable_services.sh
./scripts/gcp/02_create_state_bucket.sh
./scripts/gcp/03_create_infrastructure.sh all
./scripts/gcp/04_setup_github_actions.sh
./scripts/gcp/05_verify_setup.sh

# Then push to deploy pipelines via GitHub Actions
git push

# Test with sample data
./scripts/gcp/06_test_pipeline.sh em
```

## Scripts Overview

| Script | Purpose |
|--------|---------|
| `01_enable_services.sh` | Enable required GCP APIs |
| `02_create_state_bucket.sh` | Create Terraform state bucket |
| `03_create_infrastructure.sh` | Create buckets, datasets, Pub/Sub |
| `04_setup_github_actions.sh` | Create service account for CI/CD |
| `05_verify_setup.sh` | Verify all components are set up |
| `06_test_pipeline.sh` | Upload test data and trigger pipeline |
| `07_cleanup.sh` | Delete infrastructure (keeps project) |

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

