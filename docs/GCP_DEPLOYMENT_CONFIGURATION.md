# GCP Deployment & Configuration Guide

This document provides complete instructions for deploying the legacy-migration-reference framework to Google Cloud Platform.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [GCP Project Setup](#gcp-project-setup)
3. [Required APIs & Services](#required-apis--services)
4. [IAM Roles & Permissions](#iam-roles--permissions)
5. [Service Accounts](#service-accounts)
6. [Infrastructure Components](#infrastructure-components)
7. [Deployment Methods](#deployment-methods)
8. [GitHub Actions Workflow Configuration](#github-actions-workflow-configuration)
9. [Post-Deployment Verification](#post-deployment-verification)
10. [Testing the Pipeline](#testing-the-pipeline)
11. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Tools

| Tool | Version | Purpose |
|------|---------|---------|
| gcloud CLI | Latest | GCP resource management |
| Terraform | >= 1.0 | Infrastructure provisioning |
| Python | 3.11+ | Pipeline code |
| GitHub CLI (gh) | Latest | CI/CD workflow triggers |

### Account Requirements

- GCP account with billing enabled
- GitHub account with repository access
- Owner or Editor role on GCP project

---

## GCP Project Setup

### 1. Create or Select Project

```bash
# Set your project ID
export PROJECT_ID="your-project-id"
export REGION="europe-west2"

# Create new project (optional)
gcloud projects create $PROJECT_ID --name="Legacy Migration Reference"

# Set as default project
gcloud config set project $PROJECT_ID
```

### 2. Enable Billing

```bash
# Link billing account
gcloud billing accounts list
gcloud billing projects link $PROJECT_ID --billing-account=YOUR_BILLING_ACCOUNT_ID
```

---

## Required APIs & Services

The following GCP APIs must be enabled:

| API | Purpose |
|-----|---------|
| `bigquery.googleapis.com` | Data warehouse |
| `storage.googleapis.com` | Cloud Storage buckets |
| `pubsub.googleapis.com` | Event messaging |
| `dataflow.googleapis.com` | Data processing pipelines |
| `cloudkms.googleapis.com` | Key management (optional) |
| `iam.googleapis.com` | Identity and access management |
| `monitoring.googleapis.com` | Monitoring and alerting |
| `logging.googleapis.com` | Cloud logging |
| `cloudbuild.googleapis.com` | Build automation |
| `composer.googleapis.com` | Apache Airflow (orchestration) |
| `compute.googleapis.com` | Compute Engine (for Composer) |
| `artifactregistry.googleapis.com` | Container registry |

### Enable All Services

```bash
gcloud services enable \
    bigquery.googleapis.com \
    storage.googleapis.com \
    pubsub.googleapis.com \
    dataflow.googleapis.com \
    cloudkms.googleapis.com \
    iam.googleapis.com \
    monitoring.googleapis.com \
    logging.googleapis.com \
    cloudbuild.googleapis.com \
    composer.googleapis.com \
    compute.googleapis.com \
    artifactregistry.googleapis.com \
    containerregistry.googleapis.com
```

---

## IAM Roles & Permissions

### GitHub Actions Service Account

For automated deployments, create a service account with these roles:

| Role | Purpose |
|------|---------|
| `roles/bigquery.admin` | Create/manage BigQuery datasets and tables |
| `roles/storage.admin` | Create/manage GCS buckets |
| `roles/pubsub.admin` | Create/manage Pub/Sub topics and subscriptions |
| `roles/dataflow.admin` | Manage Dataflow jobs |
| `roles/iam.serviceAccountAdmin` | Create service accounts |
| `roles/iam.serviceAccountUser` | Use service accounts |
| `roles/resourcemanager.projectIamAdmin` | Manage IAM policies |
| `roles/logging.admin` | Access logs |
| `roles/monitoring.admin` | Access metrics |
| `roles/composer.admin` | Manage Cloud Composer environments |
| `roles/cloudbuild.builds.builder` | Build containers |

### Create GitHub Actions Service Account

```bash
# Create service account
gcloud iam service-accounts create github-actions-deploy \
    --display-name="GitHub Actions Deployment"

SA_EMAIL="github-actions-deploy@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant roles
for role in \
    "roles/bigquery.admin" \
    "roles/storage.admin" \
    "roles/pubsub.admin" \
    "roles/dataflow.admin" \
    "roles/iam.serviceAccountAdmin" \
    "roles/iam.serviceAccountUser" \
    "roles/resourcemanager.projectIamAdmin" \
    "roles/logging.admin" \
    "roles/monitoring.admin" \
    "roles/composer.admin" \
    "roles/cloudbuild.builds.builder"; do
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="$role" \
        --quiet
done
```

### Composer Service Agent Role (Required for Composer v2)

```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:service-${PROJECT_NUMBER}@cloudcomposer-accounts.iam.gserviceaccount.com" \
    --role="roles/composer.ServiceAgentV2Ext" \
    --quiet
```

---

## Service Accounts

### Per-Deployment Service Accounts

Each deployment creates dedicated service accounts. For example:

#### Application1 Deployment

| Service Account | Purpose | Key Roles |
|-----------------|---------|-----------|
| `application1-dev-dataflow` | Dataflow pipeline execution | `dataflow.worker`, `storage.objectAdmin`, `bigquery.dataEditor` |
| `application1-dev-dbt` | dbt transformations | `bigquery.dataViewer`, `bigquery.dataEditor` |
| `application1-composer-sa` | Airflow orchestration | `composer.worker`, `dataflow.admin`, `bigquery.admin`, `storage.admin` |

#### Application2 Deployment

| Service Account | Purpose | Key Roles |
|-----------------|---------|-----------|
| `application2-pipeline-sa` | Pipeline execution | `dataflow.worker`, `storage.objectAdmin`, `bigquery.dataEditor` |
| `application2-composer-sa` | Airflow orchestration | `composer.worker`, `dataflow.admin`, `bigquery.admin`, `storage.admin` |

---

## Infrastructure Components

### Per Deployment

Each deployment provisions:

#### GCS Buckets

| Bucket | Naming Pattern | Purpose |
|--------|----------------|---------|
| Landing | `{project}-{system}-{env}-landing` | Incoming data files |
| Archive | `{project}-{system}-{env}-archive` | Processed files |
| Error | `{project}-{system}-{env}-error` | Failed files |
| Temp | `{project}-{system}-{env}-temp` | Dataflow temp storage |

#### BigQuery Datasets

| Dataset | Purpose |
|---------|---------|
| `odp_{system}` | Original Data Product (raw data) |
| `fdp_{system}` | Foundation Data Product (transformed) |
| `job_control` | Pipeline job tracking (shared) |

#### Pub/Sub

| Resource | Purpose |
|----------|---------|
| `{system}-file-notifications` | Topic for file arrival events |
| `{system}-file-notifications-sub` | Subscription for pipeline trigger |
| `{system}-file-notifications-dead-letter` | Dead letter topic for failed messages |

#### Cloud Composer

| Resource | Purpose |
|----------|---------|
| `{system}-{env}-composer` | Apache Airflow environment |

---

## Deployment Methods

### Method 1: Automated (Recommended)

Use the provided scripts for end-to-end deployment:

```bash
cd legacy-migration-reference

# Full deployment (Application1 + Application2)
./scripts/gcp/deploy_all.sh all

# Or deploy individually
./scripts/gcp/deploy_all.sh application1
./scripts/gcp/deploy_all.sh application2
```

### Method 2: Step-by-Step Manual

```bash
# Step 1: Enable GCP services
./scripts/gcp/01_enable_services.sh

# Step 2: Create Terraform state bucket
./scripts/gcp/02_create_state_bucket.sh

# Step 3: Trigger GitHub Actions deployments
gh workflow run deploy-application1.yml
gh workflow run deploy-application2.yml

# Step 4: Verify deployment
./scripts/gcp/05_verify_setup.sh

# Step 5: Test pipeline
./scripts/gcp/06_test_pipeline.sh application1
```

### Method 3: Direct Terraform

```bash
cd infrastructure/terraform/application1

# Initialize
terraform init

# Plan
terraform plan -var="gcp_project_id=${PROJECT_ID}" -var="gcp_region=${REGION}"

# Apply
terraform apply -var="gcp_project_id=${PROJECT_ID}" -var="gcp_region=${REGION}"
```

---

## GitHub Actions Workflow Configuration

### Required Secrets

Configure these secrets in your GitHub repository:

| Secret | Value | Description |
|--------|-------|-------------|
| `GCP_PROJECT_ID` | Your GCP project ID | Target project |
| `GCP_SA_KEY` | Service account JSON key | Authentication |
| `GCP_REGION` | `europe-west2` | Deployment region |

### Create and Upload Service Account Key

```bash
# Create key
gcloud iam service-accounts keys create github-sa-key.json \
    --iam-account="github-actions-deploy@${PROJECT_ID}.iam.gserviceaccount.com"

# Add to GitHub (via CLI)
gh secret set GCP_PROJECT_ID --body="${PROJECT_ID}"
gh secret set GCP_SA_KEY < github-sa-key.json
gh secret set GCP_REGION --body="europe-west2"

# Clean up local key
rm github-sa-key.json
```

---

## Post-Deployment Verification

### Verify GCS Buckets

```bash
gsutil ls -p $PROJECT_ID | grep -E "(application1|application2)"
```

Expected output:
```
gs://{project}-application1-dev-landing/
gs://{project}-application1-dev-archive/
gs://{project}-application1-dev-error/
gs://{project}-application2-dev-landing/
gs://{project}-application2-dev-archive/
gs://{project}-application2-dev-error/
```

### Verify BigQuery Datasets

```bash
bq ls --project_id=$PROJECT_ID
```

Expected output:
```
  datasetId  
 ----------- 
  fdp_application1     
  fdp_application2    
  job_control
  odp_application1     
  odp_application2    
```

### Verify Pub/Sub Topics

```bash
gcloud pubsub topics list --project=$PROJECT_ID
```

Expected output:
```
name: projects/{project}/topics/application1-file-notifications
name: projects/{project}/topics/application1-file-notifications-dead-letter
name: projects/{project}/topics/application2-file-notifications
name: projects/{project}/topics/application2-file-notifications-dead-letter
```

### Verify Cloud Composer

```bash
gcloud composer environments list --locations=$REGION --project=$PROJECT_ID
```

---

## Testing the Pipeline

### 1. Upload Test Data

```bash
# Create test file with HDR/TRL format
cat > /tmp/application1_customers_20260104.csv << 'EOF'
HDR|Application1|CUSTOMERS|20260104
customer_id,name,ssn,account_type,score
CUST001,John Doe,123-45-6789,CHECKING,750
CUST002,Jane Smith,987-65-4321,SAVINGS,680
TRL|RecordCount=2|Checksum=abc123
EOF

# Upload to landing bucket
gsutil cp /tmp/application1_customers_20260104.csv gs://${PROJECT_ID}-application1-dev-landing/application1/

# Create trigger file
touch /tmp/application1_customers_20260104.ok
gsutil cp /tmp/application1_customers_20260104.ok gs://${PROJECT_ID}-application1-dev-landing/application1/
```

### 2. Verify Pub/Sub Message

```bash
# Pull messages (will show file notification)
gcloud pubsub subscriptions pull application1-file-notifications-sub \
    --project=$PROJECT_ID \
    --auto-ack \
    --limit=5
```

### 3. Check Airflow DAG (if Composer is ready)

```bash
# Get Composer environment details
gcloud composer environments describe application1-dev-composer \
    --location=$REGION \
    --project=$PROJECT_ID
```

### 4. Query BigQuery

```bash
# Check ODP table (after pipeline runs)
bq query --project_id=$PROJECT_ID \
    "SELECT * FROM odp_application1.customers LIMIT 10"
```

---

## Troubleshooting

### Common Issues

#### 1. Composer Creation Fails: Service Agent Role Missing

**Error:**
```
Cloud Composer Service Agent is missing required permissions
```

**Fix:**
```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:service-${PROJECT_NUMBER}@cloudcomposer-accounts.iam.gserviceaccount.com" \
    --role="roles/composer.ServiceAgentV2Ext"
```

#### 2. Terraform State Bucket Access Denied

**Error:**
```
Error acquiring the state lock
```

**Fix:**
```bash
gsutil iam ch "serviceAccount:github-actions-deploy@${PROJECT_ID}.iam.gserviceaccount.com:objectAdmin" gs://gdw-terraform-state
gsutil iam ch "serviceAccount:github-actions-deploy@${PROJECT_ID}.iam.gserviceaccount.com:legacyBucketWriter" gs://gdw-terraform-state
```

#### 3. Composer Version Unsupported

**Error:**
```
Unsupported image version for new environment
```

**Fix:** Update `image_version` in Terraform to a supported version:
```hcl
image_version = "composer-2.16.1-airflow-2.10.5"
```

#### 4. PyPI Package Installation Fails

**Error:**
```
Failed to install Python packages
```

**Fix:** Remove or update unsupported packages from Terraform:
```hcl
# Remove this if package doesn't exist on PyPI
pypi_packages = {}
```

### Reset and Redeploy

To completely reset and redeploy:

```bash
# Full reset
./scripts/gcp/00_full_reset.sh

# Redeploy
./scripts/gcp/deploy_all.sh all
```

---

## Cost Considerations

### Estimated Monthly Costs

| Component | Application1 | Application2 | Notes |
|-----------|-----|-----|-------|
| Cloud Composer | ~$300 | ~$300 | Smallest environment |
| BigQuery | Variable | Variable | Based on data volume |
| GCS | ~$5 | ~$5 | Based on storage |
| Pub/Sub | ~$1 | ~$1 | Based on messages |
| Dataflow | Variable | Variable | Based on job runtime |

**Total Estimate:** ~$600-800/month for both deployments

### Cost Optimization

1. **Use Composer only when needed** - Can be deleted and recreated
2. **Set lifecycle policies** - Auto-delete old files
3. **Use on-demand Dataflow** - Don't run continuously
4. **Schedule pipelines during off-peak** - Lower compute costs

---

## Security Best Practices

1. **Least Privilege:** Each service account has minimal required roles
2. **Uniform Bucket Access:** ACLs disabled, IAM-only access
3. **Dead Letter Topics:** Failed messages captured for analysis
4. **Audit Logging:** All operations logged to Cloud Logging
5. **KMS Encryption (Optional):** Can enable CMEK for data at rest

---

## Next Steps

After successful deployment:

1. **Configure Monitoring:** Set up Cloud Monitoring dashboards
2. **Create Alerts:** Configure alerting for pipeline failures
3. **Schedule DAGs:** Configure Airflow DAG schedules
4. **Integrate dbt:** Deploy dbt transformations
5. **Production Hardening:** Enable KMS, VPC-SC, etc.

---

## Support

For issues:
1. Check [Troubleshooting](#troubleshooting) section
2. Review Cloud Logging for errors
3. Open GitHub issue with error details

