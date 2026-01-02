# GCP Deployment Guide

Complete guide for deploying EM and LOA pipelines to Google Cloud Platform.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Infrastructure Setup](#infrastructure-setup)
3. [Pipeline Deployment](#pipeline-deployment)
4. [Environment Configuration](#environment-configuration)
5. [CI/CD Setup](#cicd-setup)
6. [Monitoring & Alerting](#monitoring--alerting)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### GCP Project Setup

1. **Create GCP Project** with billing enabled
2. **Install Cloud SDK** locally:
   ```bash
   # macOS
   brew install google-cloud-sdk
   
   # Or download from https://cloud.google.com/sdk/docs/install
   ```

3. **Authenticate:**
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```

### Required APIs

Enable the following APIs:

```bash
gcloud services enable \
  bigquery.googleapis.com \
  storage.googleapis.com \
  dataflow.googleapis.com \
  composer.googleapis.com \
  pubsub.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com \
  cloudbuild.googleapis.com
```

### Service Accounts

Create service accounts for pipeline execution:

```bash
# Dataflow Service Account
gcloud iam service-accounts create dataflow-worker \
  --display-name="Dataflow Worker"

# Grant roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:dataflow-worker@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/dataflow.worker"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:dataflow-worker@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:dataflow-worker@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"
```

### Local Development Requirements

- Python 3.10+
- Terraform 1.0+
- dbt 1.5+
- Apache Beam 2.49+

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Terraform
brew install terraform

# Install dbt
pip install dbt-bigquery
```

---

## Infrastructure Setup

### Directory Structure

```
infrastructure/
└── terraform/
    ├── em/              # EM-specific infrastructure
    │   ├── main.tf
    │   ├── variables.tf
    │   ├── outputs.tf
    │   └── env/
    │       ├── dev.tfvars
    │       ├── staging.tfvars
    │       └── prod.tfvars
    └── loa/             # LOA-specific infrastructure
        └── (same structure)
```

### Deploy with Terraform

```bash
# Set environment variables
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export ENVIRONMENT="dev"

# Navigate to infrastructure
cd infrastructure/terraform/em  # or /loa

# Initialize Terraform
terraform init

# Plan deployment
terraform plan \
  -var="project_id=${PROJECT_ID}" \
  -var="region=${REGION}" \
  -var="environment=${ENVIRONMENT}" \
  -var-file="env/${ENVIRONMENT}.tfvars"

# Apply
terraform apply \
  -var="project_id=${PROJECT_ID}" \
  -var="region=${REGION}" \
  -var="environment=${ENVIRONMENT}" \
  -var-file="env/${ENVIRONMENT}.tfvars"
```

### Resources Created

| Resource | Purpose | Naming Pattern |
|----------|---------|----------------|
| **BigQuery Datasets** | Data storage | `odp_{system}`, `fdp_{system}`, `job_control` |
| **GCS Buckets** | File storage | `{project}-{env}-landing`, `-archive`, `-error` |
| **Pub/Sub Topics** | Event notifications | `{system}-notifications` |
| **Pub/Sub Subscriptions** | Event consumption | `{system}-processing-sub` |
| **Cloud Composer** | Airflow environment | `{system}-composer-{env}` |

---

## Pipeline Deployment

### Deploy Dataflow Template

```bash
# Build container image
gcloud builds submit \
  --tag gcr.io/${PROJECT_ID}/em-pipeline:latest \
  deployments/em/pipeline/

# Create Flex Template
gcloud dataflow flex-template build \
  gs://${PROJECT_ID}-dataflow-templates/em_pipeline.json \
  --image-gcr-path gcr.io/${PROJECT_ID}/em-pipeline:latest \
  --sdk-language PYTHON \
  --flex-template-base-image PYTHON3 \
  --metadata-file deployments/em/pipeline/metadata.json
```

### Deploy Airflow DAGs

```bash
# Get Composer environment bucket
COMPOSER_BUCKET=$(gcloud composer environments describe em-composer-${ENVIRONMENT} \
  --location ${REGION} \
  --format="value(config.dagGcsPrefix)")

# Upload DAGs
gsutil -m cp -r deployments/em/orchestration/airflow/dags/* ${COMPOSER_BUCKET}/
```

### Deploy dbt Models

```bash
# Navigate to dbt project
cd deployments/em/transformations/dbt

# Install dependencies
dbt deps

# Run models
dbt run --target ${ENVIRONMENT}

# Run tests
dbt test --target ${ENVIRONMENT}
```

---

## Environment Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GCP_PROJECT_ID` | GCP Project ID | `my-project-123` |
| `GCP_REGION` | Deployment region | `us-central1` |
| `ENVIRONMENT` | Environment name | `dev`, `staging`, `prod` |
| `DATAFLOW_TEMPLATE_PATH` | Template location | `gs://bucket/template.json` |

### Airflow Variables

Set in Cloud Composer UI or via gcloud:

```bash
gcloud composer environments run em-composer-${ENVIRONMENT} \
  --location ${REGION} \
  variables set -- \
  gcp_project_id ${PROJECT_ID}

gcloud composer environments run em-composer-${ENVIRONMENT} \
  --location ${REGION} \
  variables set -- \
  landing_bucket ${PROJECT_ID}-${ENVIRONMENT}-landing
```

### dbt Profiles

Configure `profiles.yml`:

```yaml
em_profile:
  target: "{{ env_var('ENVIRONMENT', 'dev') }}"
  outputs:
    dev:
      type: bigquery
      project: "{{ env_var('GCP_PROJECT_ID') }}"
      dataset: fdp_em
      location: US
      method: oauth
    staging:
      # Same with different project
    prod:
      # Production settings
```

---

## CI/CD Setup

### GitHub Actions Workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy Pipeline

on:
  push:
    branches: [main]
    paths:
      - 'deployments/**'
      - 'infrastructure/**'

env:
  PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
  REGION: us-central1

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -e ./gdw_data_core
      
      - name: Run tests
        run: |
          PYTHONPATH=. pytest deployments/loa/tests/ -v
          PYTHONPATH=. pytest deployments/em/tests/unit/ -v \
            --ignore=deployments/em/tests/unit/orchestration/

  deploy-infrastructure:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      
      - name: Authenticate to GCP
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      
      - name: Set up Terraform
        uses: hashicorp/setup-terraform@v2
      
      - name: Terraform Apply
        run: |
          cd infrastructure/terraform/em
          terraform init
          terraform apply -auto-approve \
            -var="project_id=$PROJECT_ID" \
            -var="environment=staging"

  deploy-pipeline:
    needs: deploy-infrastructure
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Authenticate to GCP
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      
      - name: Deploy DAGs
        run: |
          ./deploy.sh dags em staging
      
      - name: Deploy dbt
        run: |
          cd deployments/em/transformations/dbt
          dbt run --target staging
```

### Required Secrets

Configure in GitHub repository settings:

| Secret | Description |
|--------|-------------|
| `GCP_PROJECT_ID` | GCP Project ID |
| `GCP_SA_KEY` | Service account JSON key |

---

## Monitoring & Alerting

### Cloud Monitoring Dashboard

Create a dashboard for:
- Dataflow job success/failure rate
- BigQuery slot usage
- GCS object counts
- Pub/Sub message latency

```bash
# Create dashboard from template
gcloud monitoring dashboards create \
  --config-from-file=infrastructure/monitoring/dashboard.json
```

### Alert Policies

```bash
# Pipeline failure alert
gcloud alpha monitoring policies create \
  --notification-channels="projects/${PROJECT_ID}/notificationChannels/YOUR_CHANNEL" \
  --display-name="Pipeline Failure Alert" \
  --condition-display-name="Dataflow Job Failed" \
  --condition-filter='resource.type="dataflow_job" AND metric.type="dataflow.googleapis.com/job/status"'
```

### Log-Based Metrics

```bash
# Create metric for validation errors
gcloud logging metrics create validation_errors \
  --description="Count of validation errors" \
  --log-filter='resource.type="dataflow_step" AND jsonPayload.error_type="VALIDATION"'
```

---

## Troubleshooting

### Common Issues

#### 1. Dataflow Job Fails

**Check worker logs:**
```bash
gcloud logging read "resource.type=dataflow_step AND resource.labels.job_id=YOUR_JOB_ID" \
  --limit=100 \
  --format="table(timestamp,jsonPayload.message)"
```

**Common causes:**
- Schema mismatch
- Invalid data format
- Permission issues

#### 2. BigQuery Load Fails

**Check job status:**
```bash
bq ls -j -a --max_results=10
bq show -j YOUR_JOB_ID
```

**Common causes:**
- Schema incompatibility
- Quota exceeded
- Table not found

#### 3. Airflow DAG Fails

**Check task logs:**
```bash
gcloud composer environments run em-composer-${ENVIRONMENT} \
  --location ${REGION} \
  tasks logs list -- YOUR_DAG_ID YOUR_TASK_ID
```

**Common causes:**
- Missing Airflow variables
- Connection issues
- Timeout

#### 4. dbt Model Fails

**Run with debug:**
```bash
dbt run --models YOUR_MODEL --debug
```

**Check compiled SQL:**
```bash
cat target/compiled/em_transformations/models/fdp/em_attributes.sql
```

### Debug Commands

```bash
# View Dataflow jobs
gcloud dataflow jobs list --region=${REGION}

# View BigQuery jobs
bq ls -j -a

# View Composer logs
gcloud composer environments run em-composer-${ENVIRONMENT} \
  --location ${REGION} \
  logs

# View Pub/Sub messages
gcloud pubsub subscriptions pull ${SYSTEM}-processing-sub --auto-ack --limit=10
```

### Health Check Script

```bash
#!/bin/bash
# health_check.sh

echo "=== GCP Pipeline Health Check ==="

# Check BigQuery datasets
echo "BigQuery Datasets:"
bq ls --datasets

# Check GCS buckets
echo "GCS Buckets:"
gsutil ls

# Check Pub/Sub topics
echo "Pub/Sub Topics:"
gcloud pubsub topics list

# Check recent Dataflow jobs
echo "Recent Dataflow Jobs:"
gcloud dataflow jobs list --region=${REGION} --limit=5

# Check Composer status
echo "Composer Environment:"
gcloud composer environments describe em-composer-${ENVIRONMENT} \
  --location ${REGION} \
  --format="value(state)"
```

---

## Quick Reference

### Deploy Commands

```bash
# Full deployment (Terraform + DAGs + dbt)
./deploy.sh all em staging

# Infrastructure only
./deploy.sh infra em staging

# DAGs only
./deploy.sh dags em staging

# dbt only
./deploy.sh dbt em staging
```

### Test Commands

```bash
# Run all tests
PYTHONPATH=. pytest deployments/ -v

# Run specific deployment
PYTHONPATH=. pytest deployments/loa/tests/ -v

# Run with coverage
PYTHONPATH=. pytest deployments/ -v --cov=deployments --cov-report=html
```

---

**Last Updated:** January 2, 2026

