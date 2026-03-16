# Deployment Operations Guide

> **Last Updated:** March 2026
> **Version:** 1.0
> **Audience:** Developers building ingestion, transformation, or orchestration pipelines

This guide documents the **resources**, **permissions**, **testing**, and **environment externalization** for each of the three active deployments. Use this as a single reference when onboarding, debugging, or adapting the Generic pipeline for a new system.

**Related docs:**
- [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md) — system design and data layer hierarchy
- [CREATING_NEW_DEPLOYMENT_GUIDE.md](CREATING_NEW_DEPLOYMENT_GUIDE.md) — building a new deployment from scratch
- [E2E_FUNCTIONAL_FLOW.md](E2E_FUNCTIONAL_FLOW.md) — end-to-end data flow walkthrough
- [INFRASTRUCTURE_REQUIREMENTS.md](INFRASTRUCTURE_REQUIREMENTS.md) — full GCP service list and cost estimates
- [GCP_DEPLOYMENT_GUIDE.md](GCP_DEPLOYMENT_GUIDE.md) — GCP project setup, deployment phases, and infrastructure

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Deployment 1: original-data-to-bigqueryload (Ingestion)](#2-deployment-1-original-data-to-bigqueryload-ingestion)
3. [Deployment 2: bigquery-to-mapped-product (Transformation)](#3-deployment-2-bigquery-to-mapped-product-transformation)
4. [Deployment 3: data-pipeline-orchestrator (Orchestration)](#4-deployment-3-data-pipeline-orchestrator-orchestration)
5. [Environment Externalization Summary](#5-environment-externalization-summary)
6. [Local Development Setup](#6-local-development-setup)
7. [GCP Independent Testing](#7-gcp-independent-testing)
8. [Terraform Modules](#8-terraform-modules)

---

## 1. Architecture Overview

```
Mainframe CSV files → GCS landing bucket
                           ↓ (.ok trigger file → GCS notification → Pub/Sub)
                  data-pipeline-orchestrator (Airflow DAG on Cloud Composer)
                           ↓ (triggers Dataflow job per entity)
            original-data-to-bigqueryload (Dataflow Flex Template)
                           ↓ (loads into ODP tables)
                 BigQuery ODP (odp_generic.customers/accounts/decision/applications)
                           ↓
            bigquery-to-mapped-product (dbt transformation)
                           ↓ (combines ODP → FDP)
                 BigQuery FDP (fdp_generic.event_transaction_excess /
                               portfolio_account_excess / portfolio_account_facility)
```

**Three active deployments:**

| # | Deployment | Runtime | Docker Image | Terraform |
|---|-----------|---------|--------------|-----------|
| 1 | `original-data-to-bigqueryload` | Cloud Dataflow (Flex Template) | `generic-ingestion` | Unified root module |
| 2 | `bigquery-to-mapped-product` | BigQuery (dbt) | `generic-transformation` | Unified root module |
| 3 | `data-pipeline-orchestrator` | Cloud Composer (Airflow) | `generic-dag-validator` | Unified root module |

---

## 2. Deployment 1: original-data-to-bigqueryload (Ingestion)

**Purpose:** Reads CSV files from GCS, validates rows, loads into BigQuery ODP tables.

### 2.1 GCP Resources Required

| Resource | Name Pattern | Created By |
|----------|-------------|------------|
| **GCS Bucket** (landing) | `{PROJECT_ID}-generic-{ENV}-landing` | Terraform (unified root module) |
| **GCS Bucket** (archive) | `{PROJECT_ID}-generic-{ENV}-archive` | Terraform (unified root module) |
| **GCS Bucket** (error) | `{PROJECT_ID}-generic-{ENV}-error` | Terraform (unified root module) |
| **GCS Bucket** (temp/templates) | `{PROJECT_ID}-generic-{ENV}-temp` | Terraform (unified root module) |
| **BigQuery Dataset** | `odp_generic` | Terraform (unified root module) |
| **BigQuery Dataset** | `job_control` | Terraform (unified root module) |
| **BigQuery Tables** | `customers`, `accounts`, `decision`, `applications` | Application (not managed by Terraform) |
| **BigQuery Error Tables** | `customers_errors`, `accounts_errors`, `decision_errors`, `applications_errors` | Application (not managed by Terraform) |
| **BigQuery Tables** | `pipeline_jobs`, `audit_trail` | Application (not managed by Terraform) |
| **Pub/Sub Topic** | `generic-file-notifications` | Terraform (unified root module) |
| **Pub/Sub Subscription** | `generic-file-notifications-sub` | Terraform (unified root module) |
| **Pub/Sub Dead Letter** | `generic-file-notifications-dead-letter` | Terraform (unified root module) |
| **GCS Notification** | On landing bucket → Pub/Sub topic | Deploy workflow (not Terraform) |
| **Flex Template** | `gs://{PROJECT_ID}-generic-{ENV}-temp/templates/generic_ingestion_v{VERSION}.json` | Deploy workflow |
| **Container Image** | `gcr.io/{PROJECT_ID}/generic-ingestion:{VERSION}` | Deploy workflow (Cloud Build) |

### 2.2 IAM Permissions

**Service Account:** `generic-{ENV}-dataflow@{PROJECT_ID}.iam.gserviceaccount.com`

| Role | Scope | Why |
|------|-------|-----|
| `roles/dataflow.worker` | Project | Dataflow worker operations |
| `roles/storage.objectAdmin` | Landing, archive, error, temp buckets | Read source CSV, write archives/errors, read template |
| `roles/bigquery.dataEditor` | `odp_generic`, `job_control` datasets | Insert rows into ODP and job_control tables |
| `roles/pubsub.subscriber` | `generic-file-notifications-sub` | Acknowledge processed messages |

**Additional IAM (system-level):**

| Role | Principal | Why |
|------|-----------|-----|
| `roles/pubsub.publisher` | GCS service account | GCS notification → Pub/Sub |

### 2.3 Pipeline Parameters (Flex Template)

These are the runtime parameters passed when launching a Dataflow job. Defined in `metadata.json`:

| Parameter | Required | Example | Externalize? |
|-----------|----------|---------|-------------|
| `entity` | Yes | `customers` | No (per-job) |
| `source_file` | Yes | `gs://{PROJECT}-generic-int-landing/generic/customers/file.csv` | Yes (bucket name) |
| `output_table` | Yes | `{PROJECT}:odp_generic.customers` | Yes (project, dataset) |
| `error_table` | Yes | `{PROJECT}:odp_generic.customers_errors` | Yes (project, dataset) |
| `extract_date` | Yes | `20260315` | No (per-job) |
| `run_id` | Yes | `run-20260315-001` | No (per-job) |
| `gcp_project` | No | `joseph-antony-aruja` | Yes |

### 2.4 Testing Locally

```bash
cd deployments/original-data-to-bigqueryload

# Install dependencies (dev extras include pytest, mock libraries)
pip install -e ".[dev]"

# Run unit tests (no GCP credentials needed)
PYTHONPATH=src pytest tests/unit -v --tb=short

# Run a specific test file
PYTHONPATH=src pytest tests/unit/pipeline/test_runner.py -v

# Run with markers
PYTHONPATH=src pytest tests/ -m "not requires_gcp" -v
```

**What unit tests cover:**
- CSV parsing and validation (header/trailer, field types, allowed values)
- Entity schema mapping (customers, accounts, decision, applications)
- Error handling (malformed rows, missing fields, type coercion)
- Pipeline options parsing
- Job control record creation

**Test fixtures available** (in `tests/conftest.py`):
- `generic_customer_record`, `generic_account_record`, `generic_decision_record` — sample dicts
- `generic_customers_file_lines`, `generic_accounts_file_lines` — full CSV with HDR/TRL
- `mock_bigquery_client`, `mock_gcs_client` — pre-configured mocks
- `temp_csv_file` — creates real temp files for file-based tests
- `faker_instance` — reproducible fake data generation

### 2.5 Testing on GCP (Independent)

```bash
PROJECT_ID=$(gcloud config get-value project)
ENV="int"

# 1. Build and push the Docker image
cd deployments/original-data-to-bigqueryload
gcloud builds submit --config=cloudbuild.yaml \
  --substitutions=_LIBRARY_VERSION=1.0.11 \
  ../..

# 2. Register Flex Template
gcloud dataflow flex-template build \
  gs://${PROJECT_ID}-generic-${ENV}-temp/templates/generic_ingestion_test.json \
  --image gcr.io/${PROJECT_ID}/generic-ingestion:1.0.11 \
  --sdk-language PYTHON \
  --metadata-file metadata.json

# 3. Upload a test CSV file
cat > /tmp/test_customers.csv << 'EOF'
HDR|Generic|CUSTOMERS|20260315
customer_id,first_name,last_name,ssn,dob,status,created_date
C001,John,Doe,123-45-6789,1985-06-15,A,2025-01-15
C002,Jane,Smith,987-65-4321,1990-03-22,A,2025-02-20
TRL|RecordCount=2|Checksum=abc123
EOF
gsutil cp /tmp/test_customers.csv \
  gs://${PROJECT_ID}-generic-${ENV}-landing/generic/customers/

# 4. Launch Dataflow job directly (bypasses orchestration)
gcloud dataflow flex-template run "test-customers-$(date +%s)" \
  --template-file-gcs-location=gs://${PROJECT_ID}-generic-${ENV}-temp/templates/generic_ingestion_test.json \
  --region=europe-west2 \
  --parameters entity=customers \
  --parameters source_file=gs://${PROJECT_ID}-generic-${ENV}-landing/generic/customers/test_customers.csv \
  --parameters output_table=${PROJECT_ID}:odp_generic.customers \
  --parameters error_table=${PROJECT_ID}:odp_generic.customers_errors \
  --parameters extract_date=20260315 \
  --parameters run_id=test-manual-001 \
  --parameters gcp_project=${PROJECT_ID} \
  --service-account-email=generic-${ENV}-dataflow@${PROJECT_ID}.iam.gserviceaccount.com

# 5. Verify results
bq query --use_legacy_sql=false \
  "SELECT COUNT(*) as row_count FROM \`${PROJECT_ID}.odp_generic.customers\`"

bq query --use_legacy_sql=false \
  "SELECT * FROM \`${PROJECT_ID}.job_control.pipeline_jobs\` ORDER BY created_at DESC LIMIT 5"
```

### 2.6 Environment Externalization

| Item | Where Defined | What to Change Per Environment |
|------|--------------|-------------------------------|
| GCS bucket names | Terraform `main.tf` | `gcp_project_id` + `environment` variables |
| BigQuery dataset location | Terraform `variables.tf` | `bq_location` (default: `EU`) |
| Bucket lifecycle rules | Terraform `main.tf` | Landing: 90d→COLDLINE, Archive: 365d→COLDLINE→5y→ARCHIVE, Error: 90d→DELETE |
| Force destroy flag | Terraform `variables.tf` | `force_destroy` — `true` for dev/int, `false` for prod |
| Versioning | Terraform `variables.tf` | `enable_versioning` — `true` recommended for all envs |
| Terraform backend prefix | `deploy-generic.yml` | `-backend-config="prefix=generic/ingestion"` |
| Docker image tag | `deploy-generic.yml` | Framework version from PyPI |
| Template GCS path | `deploy-generic.yml` | Bucket name includes project + env |

---

## 3. Deployment 2: bigquery-to-mapped-product (Transformation)

**Purpose:** dbt models that transform ODP tables into FDP (Foundation Data Products).

### 3.1 GCP Resources Required

| Resource | Name Pattern | Created By |
|----------|-------------|------------|
| **BigQuery Dataset** | `fdp_generic` | Terraform (unified root module) |
| **BigQuery Tables** | `event_transaction_excess`, `portfolio_account_excess`, `portfolio_account_facility` | dbt (incremental models) |
| **BigQuery Dataset** | `stg_generic` | dbt (created on first run for staging views) |
| **Container Image** | `gcr.io/{PROJECT_ID}/generic-transformation:{VERSION}` | Deploy workflow (Cloud Build) |

**Reads from (created by ingestion module):**
- `odp_generic.customers`, `odp_generic.accounts`, `odp_generic.decision`, `odp_generic.applications`

### 3.2 IAM Permissions

**Service Account:** `generic-{ENV}-dbt@{PROJECT_ID}.iam.gserviceaccount.com`

| Role | Scope | Why |
|------|-------|-----|
| `roles/bigquery.dataViewer` | `odp_generic` dataset | Read ODP source tables |
| `roles/bigquery.dataEditor` | `fdp_generic` dataset | Create/update FDP tables |
| `roles/bigquery.dataViewer` | `job_control` dataset | Read pipeline status for dependency checks |
| `roles/bigquery.jobUser` | Project | Run BigQuery jobs |

### 3.3 dbt Configuration

**`dbt_project.yml` variables:**

| Variable | Default | Purpose | Externalize? |
|----------|---------|---------|-------------|
| `gcp_project_id` | `env_var('GCP_PROJECT_ID')` | BigQuery project | Yes |
| `source_dataset` | `odp_generic` | ODP dataset name | Yes (if different per system) |
| `staging_dataset` | `stg_generic` | Staging views dataset | Yes (if different per system) |
| `fdp_dataset` | `fdp_generic` | FDP target dataset | Yes (if different per system) |
| `extract_date` | `null` | Filter for incremental runs | No (runtime) |
| `all_entities` | `['customers', 'accounts', 'decision', 'applications']` | Entity list | No (system-specific) |

**`profiles.yml` (connection config):**

```yaml
mapped_product_profile:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: service-account
      project: "{{ env_var('GCP_PROJECT_ID') }}"
      dataset: fdp_generic
      location: EU
      threads: 4
      timeout_seconds: 300
```

### 3.4 Transformation Patterns

| Pattern | Source Tables | Target Table | Logic |
|---------|-------------|--------------|-------|
| **JOIN** | customers + accounts | `event_transaction_excess` | JOIN on `customer_id`, map PII fields |
| **JOIN** | customers + decision | `portfolio_account_excess` | JOIN on `customer_id`, map decision fields |
| **MAP** | applications | `portfolio_account_facility` | 1:1 mapping with field renaming |

### 3.5 Testing Locally

```bash
cd deployments/bigquery-to-mapped-product

# Install dependencies
pip install -e ".[dev]"

# Run unit tests (validates SQL compilation, macro logic)
pytest tests/ -v --tb=short

# Validate dbt project compiles (no GCP needed for compile)
cd dbt
dbt compile --profiles-dir . --target dev
```

**What tests cover:**
- dbt model compilation (SQL syntax validation)
- Macro output correctness
- Schema test definitions (uniqueness, not_null, relationships)
- Source freshness configuration

### 3.6 Testing on GCP (Independent)

```bash
PROJECT_ID=$(gcloud config get-value project)

# 1. Build the dbt Docker image
cd deployments/bigquery-to-mapped-product
gcloud builds submit --config=cloudbuild.yaml \
  --substitutions=_LIBRARY_VERSION=1.0.11 \
  ../..

# 2. Run dbt directly (requires ODP tables to have data)
docker run --rm \
  -e GCP_PROJECT_ID=${PROJECT_ID} \
  -v ~/.config/gcloud:/root/.config/gcloud \
  gcr.io/${PROJECT_ID}/generic-transformation:1.0.11 \
  dbt run --profiles-dir /app/deployments/bigquery-to-mapped-product/dbt --target dev

# 3. Or run dbt natively (if dbt-bigquery is installed)
cd dbt
export GCP_PROJECT_ID=${PROJECT_ID}
dbt run --profiles-dir . --target dev

# 4. Verify FDP tables
bq query --use_legacy_sql=false \
  "SELECT COUNT(*) FROM \`${PROJECT_ID}.fdp_generic.event_transaction_excess\`"
bq query --use_legacy_sql=false \
  "SELECT COUNT(*) FROM \`${PROJECT_ID}.fdp_generic.portfolio_account_excess\`"
bq query --use_legacy_sql=false \
  "SELECT COUNT(*) FROM \`${PROJECT_ID}.fdp_generic.portfolio_account_facility\`"

# 5. Run dbt tests (schema tests, data tests)
dbt test --profiles-dir . --target dev
```

### 3.7 Environment Externalization

| Item | Where Defined | What to Change Per Environment |
|------|--------------|-------------------------------|
| BigQuery project | `dbt_project.yml` → `env_var('GCP_PROJECT_ID')` | Set `GCP_PROJECT_ID` env var |
| BigQuery location | `profiles.yml` → `location` | `EU` for all (or override) |
| Target profile | `profiles.yml` → `target` | `dev` / `int` / `prod` |
| Thread count | `profiles.yml` → `threads` | `4` for dev, higher for prod |
| FDP dataset name | `dbt_project.yml` → `fdp_dataset` | Change if per-env naming needed |
| Terraform backend | `deploy-generic.yml` | `-backend-config="prefix=generic/transformation"` |

---

## 4. Deployment 3: data-pipeline-orchestrator (Orchestration)

**Purpose:** Airflow DAGs that coordinate the full pipeline: listen for files, trigger Dataflow, run dbt.

### 4.1 GCP Resources Required

| Resource | Name Pattern | Created By |
|----------|-------------|------------|
| **Cloud Composer** | `generic-{ENV}-composer` | Terraform (unified root module) |
| **Service Account** | `generic-composer-sa@{PROJECT_ID}.iam.gserviceaccount.com` | Terraform (unified root module) |
| **Container Image** | `gcr.io/{PROJECT_ID}/generic-dag-validator:{VERSION}` | Deploy workflow (Cloud Build) |

**Composer Configuration (from Terraform):**
- Image version: `composer-2.10.2-airflow-2.10.5`
- Environment size: `ENVIRONMENT_SIZE_SMALL`
- Scheduler: 0.5 CPU, 2 GB RAM
- Web server: 0.5 CPU, 2 GB RAM
- Workers: 1-3 instances, 1 CPU, 4 GB RAM each

**Reads/writes to (created by ingestion + transformation modules):**
- GCS buckets (landing, archive, error)
- BigQuery datasets (odp_generic, fdp_generic, job_control)
- Pub/Sub subscription (generic-file-notifications-sub)
- Dataflow Flex Template (to launch jobs)

### 4.2 IAM Permissions

**Service Account:** `generic-composer-sa@{PROJECT_ID}.iam.gserviceaccount.com`

| Role | Scope | Why |
|------|-------|-----|
| `roles/composer.worker` | Project | Airflow worker operations |
| `roles/dataflow.admin` | Project | Launch and monitor Dataflow jobs |
| `roles/bigquery.admin` | Project | Query tables, check job_control status |
| `roles/storage.admin` | Project | Move files between buckets (landing → archive/error) |
| `roles/pubsub.subscriber` | Project | Pull messages from notification subscription |

### 4.3 Airflow DAGs

| DAG | Trigger | What It Does |
|-----|---------|--------------|
| `pubsub_trigger_dag.py` | Scheduled (polls Pub/Sub) | Detects `.ok` files, records arrival, triggers ingestion DAG |
| `data_ingestion_dag.py` | Triggered by pubsub DAG | Launches Dataflow Flex Template per entity |
| `transformation_dag.py` | Triggered after all JOIN entities loaded | Runs dbt models (ODP → FDP) |
| `error_handling_dag.py` | Triggered on failure | Moves files to error bucket, updates job_control |

### 4.4 Airflow Variables (Environment Variables in Composer)

Set by Terraform in the Composer environment config:

| Variable | Value | Externalize? |
|----------|-------|-------------|
| `GCP_PROJECT_ID` | `{project_id}` | Yes |
| `EM_LANDING_BUCKET` | `{project_id}-generic-{env}-landing` | Yes |
| `EM_ARCHIVE_BUCKET` | `{project_id}-generic-{env}-archive` | Yes |
| `EM_ERROR_BUCKET` | `{project_id}-generic-{env}-error` | Yes |
| `ODP_DATASET` | `odp_generic` | Yes (if per-system naming) |
| `FDP_DATASET` | `fdp_generic` | Yes (if per-system naming) |
| `JOB_CONTROL_TABLE` | `job_control.pipeline_jobs` | Yes (if per-system naming) |

**DAG-level variables** (accessed via `Variable.get()` with env var fallbacks):

| Variable Key | Default | Used By |
|-------------|---------|---------|
| `gcp_project_id` | `os.environ['GCP_PROJECT_ID']` | All DAGs |
| `gcp_region` | `europe-west2` | Dataflow launch region |
| `generic_pubsub_subscription` | `generic-file-notifications-sub` | pubsub_trigger_dag |
| `generic_landing_bucket` | `{PROJECT_ID}-generic-int-landing` | pubsub_trigger_dag |
| `generic_error_bucket` | `{PROJECT_ID}-generic-int-error` | error_handling_dag |
| `dataflow_templates_bucket` | `{PROJECT_ID}-generic-int-temp` | data_ingestion_dag |
| `dbt_project_path` | `/home/airflow/gcs/dags/dbt` | transformation_dag |

### 4.5 Testing Locally

```bash
cd deployments/data-pipeline-orchestrator

# Install dependencies
pip install -e ".[dev]"

# Run DAG structure tests (validates DAG definitions, no Airflow needed)
pytest tests/ -v --tb=short

# Run with GCP_PROJECT_ID set (DAGs reference it at import time)
GCP_PROJECT_ID=test-project pytest tests/ -v
```

**What tests cover:**
- DAG definition validity (no import errors)
- Task structure and dependencies
- DAG IDs and schedule intervals
- Mocked Airflow Variable access

**conftest.py setup:**
- Adds `libs/` to Python path (for framework packages)
- Patches `os.environ` with test project ID

### 4.6 Testing on GCP (Independent)

```bash
PROJECT_ID=$(gcloud config get-value project)
ENV="int"
REGION="europe-west2"

# 1. Verify Composer is running
gcloud composer environments describe generic-${ENV}-composer \
  --location=${REGION} --format='value(state)'
# Expected: RUNNING

# 2. Get Composer DAGs bucket
DAGS_BUCKET=$(gcloud composer environments describe generic-${ENV}-composer \
  --location=${REGION} --format='value(config.dagGcsPrefix)')
echo "DAGs bucket: ${DAGS_BUCKET}"

# 3. Upload DAGs manually (for testing outside CI/CD)
gsutil -m cp deployments/data-pipeline-orchestrator/dags/*.py ${DAGS_BUCKET}/

# 4. Check DAGs are visible in Airflow
gcloud composer environments run generic-${ENV}-composer \
  --location=${REGION} dags list

# 5. Trigger a DAG manually
gcloud composer environments run generic-${ENV}-composer \
  --location=${REGION} dags trigger -- generic_pubsub_trigger

# 6. Check DAG run status
gcloud composer environments run generic-${ENV}-composer \
  --location=${REGION} dags list-runs -- -d generic_pubsub_trigger --limit 5
```

### 4.7 Environment Externalization

| Item | Where Defined | What to Change Per Environment |
|------|--------------|-------------------------------|
| Composer environment name | Terraform `main.tf` | `generic-{ENV}-composer` |
| Composer image version | Terraform `main.tf` | `composer-2.10.2-airflow-2.10.5` |
| Composer size/scaling | Terraform `main.tf` | Worker min/max, CPU, memory |
| Airflow env variables | Terraform `main.tf` | Bucket names, dataset names, project ID |
| DAG schedule intervals | DAG Python files | Currently hardcoded; externalize via Airflow Variables for prod |
| Terraform backend prefix | `deploy-generic.yml` | `-backend-config="prefix=generic/orchestration"` |

---

## 5. Environment Externalization Summary

### 5.1 Things That MUST Change Per Environment

| Category | Item | Dev/Int | Prod |
|----------|------|---------|------|
| **Terraform** | `gcp_project_id` | `joseph-antony-aruja` | Production project ID |
| **Terraform** | `environment` | `int` | `prod` |
| **Terraform** | `force_destroy` | `true` | `false` |
| **Terraform** | Terraform backend bucket | `gcp-pipeline-terraform-state` | Separate per env |
| **Terraform** | Terraform backend prefix | `generic/ingestion` | `generic-prod/ingestion` |
| **GCS** | Bucket names | `{PROJECT}-generic-int-*` | `{PROJECT}-generic-prod-*` |
| **BigQuery** | Dataset location | `EU` | Per compliance requirements |
| **Composer** | Environment size | `SMALL` | `MEDIUM` or `LARGE` |
| **Composer** | Worker scaling | 1-3 workers | 3-10+ workers |
| **Docker** | Image tag | `1.0.11` | Pinned release version |
| **GitHub** | `GCP_SA_KEY` secret | Int SA key | Prod SA key |
| **GitHub** | `GCP_PROJECT_ID` secret | Int project | Prod project |

### 5.2 Things That Are Constant Across Environments

| Category | Item | Value |
|----------|------|-------|
| **Region** | GCP region | `europe-west2` (London) |
| **BigQuery** | Dataset names | `odp_generic`, `fdp_generic`, `job_control` |
| **Entities** | Entity list | `customers`, `accounts`, `decision`, `applications` |
| **Pub/Sub** | Topic name | `generic-file-notifications` |
| **Pipeline** | Parameter name | `source_file` (not `input_file`) |
| **dbt** | Model names | `event_transaction_excess`, `portfolio_account_excess`, `portfolio_account_facility` |

### 5.3 GitHub Actions Secrets Required

| Secret | Purpose | Where Used |
|--------|---------|-----------|
| `GCP_SA_KEY` | Service account JSON key for deployment | All deploy jobs (auth) |
| `GCP_PROJECT_ID` | Target GCP project | Terraform vars, gcloud commands, Docker tags |

### 5.4 Recommended Per-Environment Terraform Configuration

Create `terraform.tfvars` files per environment:

**`int.tfvars`:**
```hcl
gcp_project_id   = "joseph-antony-aruja"
environment      = "int"
gcp_region       = "europe-west2"
bq_location      = "EU"
force_destroy    = true
enable_versioning = true
log_retention_days = 30
```

**`prod.tfvars`:**
```hcl
gcp_project_id    = "your-prod-project"
environment       = "prod"
gcp_region        = "europe-west2"
bq_location       = "EU"
force_destroy     = false
enable_versioning = true
log_retention_days = 90
```

Apply with: `terraform apply -var-file=prod.tfvars`

> **Note:** The current Terraform variables have a validation constraint `var.environment == "int"`. Remove this constraint when adding multi-environment support.

---

## 6. Local Development Setup

### 6.1 Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | `brew install python@3.11` |
| gcloud CLI | Latest | `brew install google-cloud-sdk` |
| Terraform | >= 1.7 | `brew install terraform` |
| dbt-bigquery | Latest | `pip install dbt-bigquery` |
| Docker | Latest | Docker Desktop |

### 6.2 Clone and Setup

```bash
git clone https://github.com/enrichmeai/gcp-pipeline-reference.git
cd gcp-pipeline-reference

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install framework
pip install gcp-pipeline-framework>=1.0.11

# Install each deployment for local development
pip install -e "deployments/original-data-to-bigqueryload[dev]"
pip install -e "deployments/bigquery-to-mapped-product[dev]"
pip install -e "deployments/data-pipeline-orchestrator[dev]"
```

### 6.3 Running All Tests Locally

```bash
# Ingestion tests (26 tests)
cd deployments/original-data-to-bigqueryload
PYTHONPATH=src pytest tests/unit -v --tb=short

# Transformation tests
cd ../bigquery-to-mapped-product
pytest tests/ -v --tb=short

# Orchestration tests
cd ../data-pipeline-orchestrator
GCP_PROJECT_ID=test-project pytest tests/ -v --tb=short
```

### 6.4 Local Pipeline Execution (DirectRunner)

For ingestion, you can run the pipeline locally using Beam's DirectRunner:

```bash
cd deployments/original-data-to-bigqueryload

python -m data_ingestion.pipeline.runner \
  --entity=customers \
  --source_file=/tmp/test_customers.csv \
  --output_table=local_output \
  --error_table=local_errors \
  --extract_date=20260315 \
  --run_id=local-test-001 \
  --runner=DirectRunner
```

> **Note:** DirectRunner writes to local files, not BigQuery. Use for validation of parsing and transformation logic only.

---

## 7. GCP Independent Testing

### 7.1 Test Ingestion Only (No Orchestration)

See [Section 2.5](#25-testing-on-gcp-independent) — launch Dataflow directly with `gcloud dataflow flex-template run`.

### 7.2 Test Transformation Only (No Ingestion)

See [Section 3.6](#36-testing-on-gcp-independent) — run dbt directly against BigQuery with existing ODP data.

### 7.3 Test Orchestration Only (No Data)

See [Section 4.6](#46-testing-on-gcp-independent) — upload DAGs to Composer and trigger manually.

### 7.4 Full E2E Test (All Three Together)

```bash
PROJECT_ID=$(gcloud config get-value project)
ENV="int"

# Upload test data + .ok trigger files to landing bucket
# This triggers: GCS notification → Pub/Sub → Airflow DAG → Dataflow → BQ ODP → dbt → BQ FDP

# Customers
gsutil cp /tmp/test_customers.csv gs://${PROJECT_ID}-generic-${ENV}-landing/generic/customers/
touch /tmp/customers.csv.ok
gsutil cp /tmp/customers.csv.ok gs://${PROJECT_ID}-generic-${ENV}-landing/generic/customers/

# Accounts
gsutil cp /tmp/test_accounts.csv gs://${PROJECT_ID}-generic-${ENV}-landing/generic/accounts/
touch /tmp/accounts.csv.ok
gsutil cp /tmp/accounts.csv.ok gs://${PROJECT_ID}-generic-${ENV}-landing/generic/accounts/

# Decision
gsutil cp /tmp/test_decision.csv gs://${PROJECT_ID}-generic-${ENV}-landing/generic/decision/
touch /tmp/decision.csv.ok
gsutil cp /tmp/decision.csv.ok gs://${PROJECT_ID}-generic-${ENV}-landing/generic/decision/

# Applications (MAP entity - triggers independently)
gsutil cp /tmp/test_applications.csv gs://${PROJECT_ID}-generic-${ENV}-landing/generic/applications/
touch /tmp/applications.csv.ok
gsutil cp /tmp/applications.csv.ok gs://${PROJECT_ID}-generic-${ENV}-landing/generic/applications/

# Verify end-to-end (wait 10-15 minutes for full pipeline)
bq query --use_legacy_sql=false "SELECT * FROM \`${PROJECT_ID}.job_control.pipeline_jobs\` ORDER BY created_at DESC LIMIT 10"
bq query --use_legacy_sql=false "SELECT COUNT(*) FROM \`${PROJECT_ID}.odp_generic.customers\`"
bq query --use_legacy_sql=false "SELECT COUNT(*) FROM \`${PROJECT_ID}.fdp_generic.event_transaction_excess\`"
```

Also see: `scripts/gcp/test_e2e_flow.sh` for an automated E2E test script.

---

## 8. Terraform Modules

### 8.1 Module Structure

```
infrastructure/terraform/systems/generic/
├── ingestion/          # GCS, Pub/Sub, BQ ODP, job_control, Dataflow SA
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── transformation/     # BQ FDP, dbt SA
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
└── orchestration/      # Cloud Composer, Composer SA, IAM
    ├── main.tf
    ├── variables.tf
    └── outputs.tf
```

### 8.2 Shared Variables (All Modules)

| Variable | Type | Default | Required |
|----------|------|---------|----------|
| `gcp_project_id` | string | — | Yes |
| `gcp_region` | string | `europe-west2` | No |
| `bq_location` | string | `EU` | No |
| `environment` | string | `int` | No |
| `force_destroy` | bool | `false` | No |
| `enable_versioning` | bool | `true` | No |
| `generic_entities` | list(string) | `["customers", "accounts", "decision", "applications"]` | No |
| `log_retention_days` | number | `30` | No |

### 8.3 Applying Terraform

```bash
# From deploy-generic.yml workflow:
cd infrastructure/terraform/systems/generic/ingestion
terraform init \
  -backend-config="bucket=gcp-pipeline-terraform-state" \
  -backend-config="prefix=generic/ingestion"
terraform apply -auto-approve \
  -var="gcp_project_id=${PROJECT_ID}" \
  -var="environment=int"

# Repeat for transformation/ and orchestration/
```

### 8.4 Terraform State

| Module | State Bucket | Prefix |
|--------|-------------|--------|
| Ingestion | `gcp-pipeline-terraform-state` | `generic/ingestion` |
| Transformation | `gcp-pipeline-terraform-state` | `generic/transformation` |
| Orchestration | `gcp-pipeline-terraform-state` | `generic/orchestration` |

---

*This document is maintained alongside the codebase. For architectural decisions, see [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md). For creating new deployments, see [CREATING_NEW_DEPLOYMENT_GUIDE.md](CREATING_NEW_DEPLOYMENT_GUIDE.md).*
