# Developer Testing Guide

How to test each deployment unit locally and on GCP before pushing to `main`.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [GCP Resource Reference](#gcp-resource-reference)
3. [IAM Permissions Reference](#iam-permissions-reference)
4. [Unit 1: Ingestion (Apache Beam)](#unit-1-ingestion-apache-beam)
5. [Unit 2: Transformation (dbt)](#unit-2-transformation-dbt)
6. [Unit 3: Orchestration (Airflow)](#unit-3-orchestration-airflow)
7. [CDP Layer (dbt)](#cdp-layer-dbt)
8. [Segment Export (Apache Beam)](#segment-export-apache-beam)
9. [Library Tests](#library-tests)
10. [Testing Checklist](#testing-checklist)
11. [Generic Test Specifications](#generic-test-specifications)
12. [New Deployment Checklist](#new-deployment-checklist)
13. [References](#references)

---

## Prerequisites

### Tools

```bash
# Google Cloud SDK
gcloud auth login
gcloud config set project {PROJECT_ID}

# Python 3.9+
python --version

# dbt (for transformation/CDP units)
pip install dbt-bigquery>=1.5.0

# Install the shared framework (all 5 libraries)
pip install gcp-pipeline-framework>=1.0.6

# Or install from local source for development
pip install -e gcp-pipeline-libraries/gcp-pipeline-core/
pip install -e gcp-pipeline-libraries/gcp-pipeline-beam/
pip install -e gcp-pipeline-libraries/gcp-pipeline-orchestration/
pip install -e gcp-pipeline-libraries/gcp-pipeline-transform/
pip install -e gcp-pipeline-libraries/gcp-pipeline-tester/
```

### GCP Authentication for Local Testing

```bash
# Application Default Credentials (for local runs that hit GCP)
gcloud auth application-default login

# Verify project
gcloud config get-value project
```

---

## GCP Resource Reference

All resources follow the naming pattern `{PROJECT_ID}-generic-{ENV}-{purpose}`. Replace `{ENV}` with `int`, `staging`, or `prod`.

### GCS Buckets

| Bucket | Purpose | Used By |
|--------|---------|---------|
| `{PROJECT_ID}-generic-{ENV}-landing` | Incoming CSV files from mainframe | Ingestion, Orchestration |
| `{PROJECT_ID}-generic-{ENV}-archive` | Processed files moved after successful load | Ingestion |
| `{PROJECT_ID}-generic-{ENV}-error` | Quarantined files that failed parsing | Ingestion |
| `{PROJECT_ID}-generic-{ENV}-temp` | Dataflow temp files and Flex Template staging | Ingestion, Segment Export |
| `{PROJECT_ID}-generic-{ENV}-segments` | Outbound fixed-width mainframe segment files | Segment Export |

### BigQuery Datasets and Tables

| Dataset | Tables | Purpose | Used By |
|---------|--------|---------|---------|
| `odp_generic` | `customers`, `accounts`, `decision`, `applications` | Raw ODP (Original Data Product) | Ingestion (write), Transformation (read) |
| `odp_generic` | `customers_failed`, `accounts_failed`, etc. | Dead letter / validation failures | Ingestion (write) |
| `fdp_generic` | `event_transaction_excess`, `portfolio_account_excess`, `portfolio_account_facility` | Curated FDP (Foundation Data Product) | Transformation (write), CDP (read) |
| `cdp_generic` | `customer_risk_profile` | Consumable Data Product (JOIN of 3 FDPs) | CDP (write), Segment Export (read) |
| `job_control` | `pipeline_jobs`, `audit_trail` | Pipeline state tracking and audit | All deployments |

### Pub/Sub

| Resource | Name | Purpose |
|----------|------|---------|
| Topic | `generic-file-notifications` | GCS OBJECT_FINALIZE events from landing bucket |
| Subscription | `generic-file-notifications-sub` | Airflow sensor polls this |
| Topic | `generic-pipeline-events` | Audit record streaming |
| Subscription | `generic-pipeline-events-sub` | Monitoring consumers |

### Cloud Composer

| Resource | Name |
|----------|------|
| Environment | `generic-{ENV}-composer` |
| Region | `europe-west2` |
| DAGs Bucket | Auto-assigned by Composer (retrieve with `gcloud composer environments describe`) |

### Docker Images (GCR)

| Image | Purpose |
|-------|---------|
| `gcr.io/{PROJECT_ID}/generic-ingestion:{version}` | Dataflow Flex Template for ODP load |
| `gcr.io/{PROJECT_ID}/generic-transformation:{version}` | dbt runner for FDP transformation |
| `gcr.io/{PROJECT_ID}/generic-dag-validator:{version}` | CI validation of Airflow DAGs |

---

## IAM Permissions Reference

### Developer Testing (Your User Account)

For local testing that hits GCP resources, your user account (or Application Default Credentials) needs:

| Role | Purpose | Required For |
|------|---------|-------------|
| `roles/bigquery.jobUser` | Run BigQuery queries | Transformation, CDP, verifying Ingestion results |
| `roles/bigquery.dataEditor` | Read/write BigQuery tables | All units that touch BQ |
| `roles/storage.objectAdmin` | Read/write GCS objects | Ingestion (DirectRunner writing to GCS), Segment Export |
| `roles/dataflow.developer` | Submit Dataflow jobs | Ingestion (DataflowRunner), Segment Export (DataflowRunner) |
| `roles/dataflow.worker` | Dataflow worker permissions | Required on service account used by Dataflow workers |
| `roles/pubsub.publisher` | Publish to Pub/Sub topics | Orchestration testing |
| `roles/pubsub.subscriber` | Pull from Pub/Sub subscriptions | Orchestration testing, verifying notifications |
| `roles/composer.user` | Trigger DAGs, view Composer | Orchestration (Cloud Composer) |

### Service Accounts (CI/CD and Runtime)

| Service Account | Roles | Used By |
|----------------|-------|---------|
| `github-actions-deploy@{PROJECT_ID}.iam.gserviceaccount.com` | Dataflow Admin, Composer Worker, BigQuery Admin, Storage Admin | CI/CD deployments |
| `airflow-sa@{PROJECT_ID}.iam.gserviceaccount.com` | `dataflow.developer`, `bigquery.jobUser`, `bigquery.dataEditor`, `storage.objectAdmin`, `pubsub.publisher`, `pubsub.subscriber` | Orchestration runtime (Cloud Composer) |
| `dbt-sa@{PROJECT_ID}.iam.gserviceaccount.com` | `bigquery.jobUser`, `bigquery.dataEditor` | Transformation and CDP runtime |

### Grant Roles for Local Testing

```bash
PROJECT_ID=$(gcloud config get-value project)
USER_EMAIL=$(gcloud config get-value account)

# Minimum roles for testing all units locally
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:$USER_EMAIL" \
    --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:$USER_EMAIL" \
    --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:$USER_EMAIL" \
    --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="user:$USER_EMAIL" \
    --role="roles/dataflow.developer"
```

---

## Unit 1: Ingestion (Apache Beam)

**Deployment:** `original-data-to-bigqueryload`

### GCP Resources Used

| Resource | Name |
|----------|------|
| GCS (input) | `gs://{PROJECT_ID}-generic-{ENV}-landing/generic/{entity}/` |
| GCS (archive) | `gs://{PROJECT_ID}-generic-{ENV}-archive/generic/{entity}/` |
| GCS (errors) | `gs://{PROJECT_ID}-generic-{ENV}-error/{entity}/{extract_date}/` |
| GCS (temp) | `gs://{PROJECT_ID}-generic-{ENV}-temp/dataflow-temp` |
| BigQuery (output) | `{PROJECT_ID}:odp_generic.{entity}` (e.g., `customers`, `accounts`) |
| BigQuery (dead letter) | `{PROJECT_ID}:odp_generic.{entity}_failed` |
| BigQuery (job control) | `{PROJECT_ID}:job_control.pipeline_jobs` |

### IAM Required

| Role | Why |
|------|-----|
| `roles/storage.objectAdmin` | Read landing files, write archive/error |
| `roles/bigquery.dataEditor` | Write to ODP tables and dead letter tables |
| `roles/bigquery.jobUser` | Execute BigQuery load jobs |
| `roles/dataflow.developer` | Submit Dataflow jobs (DataflowRunner only) |
| `roles/dataflow.worker` | On the Dataflow worker SA (DataflowRunner only) |

### Setup

```bash
./scripts/setup_deployment_venv.sh original-data-to-bigqueryload
source deployments/original-data-to-bigqueryload/venv/bin/activate
```

### Unit Tests (No GCP Access Needed)

```bash
python -m pytest tests/unit/ -v --tb=short
```

Tests cover: HDR/TRL parsing, schema validation, CSV error handling, audit column injection, dead letter routing.

### Local Beam Execution (DirectRunner)

Run the full pipeline locally against a sample file without deploying to Dataflow:

```bash
PROJECT_ID=$(gcloud config get-value project)

python -m data_ingestion.pipeline.runner \
    --entity=customers \
    --source_file=tests/data/generic_customers_sample.csv \
    --extract_date=20260101 \
    --output_table=${PROJECT_ID}:odp_generic.customers \
    --error_table=${PROJECT_ID}:odp_generic.customers_failed \
    --run_id=local_test_001 \
    --runner=DirectRunner \
    --temp_location=/tmp/beam-temp
```

DirectRunner still writes to BigQuery via streaming inserts, so GCP credentials and a valid project are required even for local runs.

Required arguments: `--entity`, `--source_file`, `--extract_date` (from `GenericPipelineOptions`), `--output_table`, `--error_table`, `--run_id` (from `GCPPipelineOptions`).

DirectRunner executes the entire Beam DAG in-process. Use this to verify:
- HDR/TRL envelope parsing
- CSV field validation and error routing
- Schema mapping to BigQuery types
- Audit column injection (`_run_id`, `_source_file`, `_extract_date`)

### Cloud Execution (DataflowRunner)

For integration testing against a live GCP environment:

```bash
PROJECT_ID=$(gcloud config get-value project)

python -m data_ingestion.pipeline.runner \
    --entity=customers \
    --source_file=gs://${PROJECT_ID}-generic-int-landing/generic/customers/generic_customers_sample.csv \
    --extract_date=20260101 \
    --output_table=${PROJECT_ID}:odp_generic.customers \
    --error_table=${PROJECT_ID}:odp_generic.customers_failed \
    --run_id=test_$(date +%Y%m%d_%H%M%S) \
    --gcp_project=${PROJECT_ID} \
    --runner=DataflowRunner \
    --project=${PROJECT_ID} \
    --region=europe-west2 \
    --temp_location=gs://${PROJECT_ID}-generic-int-temp/dataflow-temp
```

### Production-Equivalent Execution (Flex Template)

In production, Dataflow runs via a Flex Template (not `python -m` directly). To test the same way:

```bash
PROJECT_ID=$(gcloud config get-value project)
ENV="int"
VERSION="1.0.11"

# Step 1: Build the Flex Template image (if not already built by CI)
gcloud builds submit . \
    --config deployments/original-data-to-bigqueryload/cloudbuild.yaml \
    --substitutions _LIBRARY_VERSION=${VERSION} \
    --project ${PROJECT_ID} \
    --timeout=3300s

# Step 2: Create the Flex Template spec
gcloud dataflow flex-template build \
    gs://${PROJECT_ID}-generic-${ENV}-temp/templates/generic_ingestion_v${VERSION}.json \
    --image gcr.io/${PROJECT_ID}/generic-ingestion:${VERSION} \
    --sdk-language PYTHON \
    --metadata-file deployments/original-data-to-bigqueryload/metadata.json \
    --project ${PROJECT_ID}

# Step 3: Launch via Flex Template (exactly as the Airflow DAG does)
gcloud dataflow flex-template run "generic-odp-load-test-$(date +%Y%m%d-%H%M%S)" \
    --template-file-gcs-location=gs://${PROJECT_ID}-generic-${ENV}-temp/templates/generic_ingestion_v${VERSION}.json \
    --region=europe-west2 \
    --parameters entity=customers \
    --parameters source_file=gs://${PROJECT_ID}-generic-${ENV}-landing/generic/customers/generic_customers_sample.csv \
    --parameters extract_date=20260101 \
    --parameters output_table=${PROJECT_ID}:odp_generic.customers \
    --parameters error_table=${PROJECT_ID}:odp_generic.customers_failed \
    --parameters run_id=flex_test_$(date +%Y%m%d_%H%M%S) \
    --parameters gcp_project=${PROJECT_ID}
```

Monitor the Dataflow job:

```bash
# List active jobs
gcloud dataflow jobs list --region=europe-west2 --status=active

# Get job details
gcloud dataflow jobs describe {JOB_ID} --region=europe-west2

# Stream worker logs
gcloud logging read "resource.type=dataflow_step AND resource.labels.job_id={JOB_ID}" \
    --project=${PROJECT_ID} --limit=50 --format="table(timestamp,textPayload)"
```

### Verify via GCP Console UI

1. **Dataflow**: Go to `console.cloud.google.com` > **Dataflow** > **Jobs**. Filter by region `europe-west2`. Click the job to see the pipeline graph, worker logs, and metrics.
2. **BigQuery**: Go to **BigQuery** > **SQL Workspace**. In the Explorer panel, expand your project > `odp_generic` > click `customers`. Use the **Preview** tab to spot-check loaded rows, or run queries in the query editor.
3. **Cloud Storage**: Go to **Cloud Storage** > **Buckets**. Open `{PROJECT_ID}-generic-int-archive` to confirm files were moved. Open `{PROJECT_ID}-generic-int-error` to check for quarantined files.
4. **Cloud Logging**: Go to **Logging** > **Logs Explorer**. Filter by `resource.type="dataflow_step"` and `jsonPayload.run_id="{run_id}"` to see pipeline logs.

### Verify via CLI

| Check | Command |
|-------|---------|
| Dataflow job succeeded | `gcloud dataflow jobs list --region=europe-west2 --status=all --limit=5` |
| Records loaded | `bq query 'SELECT COUNT(*) FROM odp_generic.customers WHERE _run_id = "{run_id}"'` |
| Audit columns present | `bq query 'SELECT _run_id, _source_file, _extract_date FROM odp_generic.customers LIMIT 5'` |
| Dead letter records | `bq query 'SELECT * FROM odp_generic.customers_failed WHERE _run_id = "{run_id}"'` |
| File archived | `gsutil ls gs://${PROJECT_ID}-generic-int-archive/` |
| Job control updated | `bq query 'SELECT * FROM job_control.pipeline_jobs WHERE run_id = "{run_id}"'` |

---

## Unit 2: Transformation (dbt)

**Deployment:** `bigquery-to-mapped-product`

### GCP Resources Used

| Resource | Name |
|----------|------|
| BigQuery (source) | `odp_generic.customers`, `odp_generic.accounts`, `odp_generic.decision`, `odp_generic.applications` |
| BigQuery (target) | `fdp_generic.event_transaction_excess`, `fdp_generic.portfolio_account_excess`, `fdp_generic.portfolio_account_facility` |
| BigQuery (job control) | `job_control.pipeline_jobs` |

### IAM Required

| Role | Why |
|------|-----|
| `roles/bigquery.jobUser` | Run dbt SQL queries |
| `roles/bigquery.dataEditor` | Read ODP tables, write FDP tables |

### Setup

```bash
./scripts/setup_deployment_venv.sh bigquery-to-mapped-product
source deployments/bigquery-to-mapped-product/venv/bin/activate
cd deployments/bigquery-to-mapped-product/dbt

# Populate shared macros from pip-installed gcp-pipeline-transform
python -c "
import gcp_pipeline_transform, shutil, os
src = os.path.join(os.path.dirname(gcp_pipeline_transform.__file__), 'dbt_shared', 'macros')
shutil.copytree(src, 'shared_macros', dirs_exist_ok=True)
"

dbt deps  # Install dbt_utils and other dependencies from packages.yml
```

### Compile Check (No GCP Access Needed)

Verify SQL compiles without errors:

```bash
dbt compile
```

### dbt Profile Setup

The dbt project uses profile `mapped_product_profile` (defined in `dbt_project.yml`). Create a matching profile in `~/.dbt/profiles.yml`:

```yaml
mapped_product_profile:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: oauth
      project: {PROJECT_ID}
      dataset: fdp_generic
      location: europe-west2
      threads: 4
    int:
      type: bigquery
      method: oauth
      project: {PROJECT_ID}
      dataset: fdp_generic
      location: europe-west2
      threads: 4
```

### Local dbt Run (Requires BQ Access)

Run models against the development BigQuery dataset:

```bash
dbt run --target dev
```

### Cloud dbt Run (Against Integration/Staging)

To test against the integration environment with real ODP data:

```bash
dbt run --target int

# Run specific model only
dbt run --target int --select event_transaction_excess
```

### Production-Equivalent Execution (Staged dbt Run)

In production, the Airflow `transformation_dag` runs dbt in stages. To test the same way:

```bash
# Stage 1: Staging models (views over ODP tables)
dbt run --target int --select staging --vars '{"extract_date": "20260101"}'

# Stage 2: FDP models (incremental merge into FDP tables)
dbt run --target int --select fdp --vars '{"extract_date": "20260101"}'

# Stage 3: Data quality tests (FDP only)
dbt test --target int --select fdp
```

This matches the exact sequence the `transformation_dag` BashOperators execute in Cloud Composer.

### Data Quality Tests

```bash
dbt test --target dev
```

Tests cover: unique keys, not-null constraints, accepted values, referential integrity between ODP and FDP tables.

### PII Masking Verification

```sql
-- Verify PII columns are masked in FDP output
SELECT ssn_masked FROM fdp_generic.event_transaction_excess LIMIT 5;
-- Should show hashed/masked values, never raw SSNs
```

### Verify via GCP Console UI

1. **BigQuery**: Go to **BigQuery** > **SQL Workspace**. Expand `fdp_generic` in the Explorer panel. Click each FDP table (`event_transaction_excess`, `portfolio_account_excess`, `portfolio_account_facility`) and use the **Preview** tab to check data. Use the **Schema** tab to verify audit columns exist.
2. **BigQuery Query History**: Go to **BigQuery** > **Job History** to see the SQL queries dbt executed, their duration, and bytes processed.

### Verify via CLI

| Check | Command |
|-------|---------|
| Models compiled | `dbt compile` exits 0 |
| FDP tables populated | `bq query 'SELECT COUNT(*) FROM fdp_generic.event_transaction_excess'` |
| Audit columns propagated | `bq query 'SELECT _run_id, _transformed_at FROM fdp_generic.event_transaction_excess LIMIT 5'` |
| PII masked | `bq query 'SELECT ssn_masked FROM fdp_generic.event_transaction_excess LIMIT 5'` |
| dbt tests pass | `dbt test` exits 0 |

---

## Unit 3: Orchestration (Airflow)

**Deployment:** `data-pipeline-orchestrator`

### GCP Resources Used

| Resource | Name |
|----------|------|
| Cloud Composer | `generic-{ENV}-composer` (region: `europe-west2`) |
| Pub/Sub Topic | `generic-file-notifications` |
| Pub/Sub Subscription | `generic-file-notifications-sub` |
| Pub/Sub Topic | `generic-pipeline-events` |
| GCS (landing) | `{PROJECT_ID}-generic-{ENV}-landing` (trigger file detection) |
| BigQuery | `job_control.pipeline_jobs` (status tracking) |

### IAM Required

| Role | Why |
|------|-----|
| `roles/composer.user` | Access Composer UI, trigger DAGs |
| `roles/pubsub.publisher` | Publish test messages |
| `roles/pubsub.subscriber` | Pull messages for verification |
| `roles/storage.objectAdmin` | Upload DAGs to Composer bucket, upload test trigger files |
| `roles/bigquery.dataEditor` | Read/write job_control tables |

### Setup

```bash
./scripts/setup_deployment_venv.sh data-pipeline-orchestrator
source deployments/data-pipeline-orchestrator/venv/bin/activate
```

### DAG Syntax Validation (No Airflow Needed)

Parse each DAG file to verify no import or syntax errors:

```bash
python deployments/data-pipeline-orchestrator/dags/pubsub_trigger_dag.py
python deployments/data-pipeline-orchestrator/dags/data_ingestion_dag.py
python deployments/data-pipeline-orchestrator/dags/transformation_dag.py
python deployments/data-pipeline-orchestrator/dags/error_handling_dag.py
```

No output = no errors. The `gcp-pipeline-orchestration` library provides `AIRFLOW_AVAILABLE` stubbing so DAGs can be parsed without a live Airflow environment.

### Unit Tests (No GCP Access Needed)

```bash
python -m pytest tests/unit/ -v --tb=short
```

Tests cover: DAG structure, task dependencies, sensor configuration, XCom metadata extraction.

### Airflow Variables (Required in Composer)

The DAGs read configuration from Airflow Variables. Set these in Cloud Composer before triggering any DAG:

| Variable | Value | Used By |
|----------|-------|---------|
| `gcp_project_id` | `{PROJECT_ID}` | All DAGs |
| `gcp_region` | `europe-west2` | Dataflow job launches |
| `dataflow_templates_bucket` | `{PROJECT_ID}-generic-{ENV}-temp` | `data_ingestion_dag` |
| `generic_pubsub_subscription` | `generic-file-notifications-sub` | `pubsub_trigger_dag` |
| `generic_landing_bucket` | `{PROJECT_ID}-generic-{ENV}-landing` | File validation |
| `generic_error_bucket` | `{PROJECT_ID}-generic-{ENV}-error` | Error routing |
| `dbt_project_path` | `/home/airflow/gcs/dags/dbt` | `transformation_dag` |

Set via CLI:

```bash
gcloud composer environments run generic-int-composer \
    --location=europe-west2 \
    variables set -- gcp_project_id ${PROJECT_ID}

gcloud composer environments run generic-int-composer \
    --location=europe-west2 \
    variables set -- gcp_region europe-west2

gcloud composer environments run generic-int-composer \
    --location=europe-west2 \
    variables set -- dataflow_templates_bucket ${PROJECT_ID}-generic-int-temp
```

Or set via the Airflow UI: **Admin** > **Variables** > **+** (add each key-value pair).

### Deploy DAGs to Cloud Composer

```bash
PROJECT_ID=$(gcloud config get-value project)
REGION="europe-west2"

# Get the Composer DAGs bucket
DAGS_BUCKET=$(gcloud composer environments describe generic-int-composer \
  --location=$REGION \
  --format='value(config.dagGcsPrefix)')

echo "DAGs bucket: $DAGS_BUCKET"

# Upload DAGs
gsutil -m cp -r deployments/data-pipeline-orchestrator/dags/* \
  ${DAGS_BUCKET}/generic/

# Verify DAGs uploaded
gsutil ls ${DAGS_BUCKET}/generic/
```

### Access Airflow UI

```bash
gcloud composer environments describe generic-int-composer \
  --location=europe-west2 \
  --format='value(config.airflowUri)'

# Open the returned URL in your browser
```

### Manual Trigger via Airflow UI

In Cloud Composer, trigger a DAG with this configuration JSON:

```json
{
  "file_metadata": {
    "data_file": "gs://{PROJECT_ID}-generic-int-landing/generic/customers/test_customers_20260101.csv",
    "trigger_file": "gs://{PROJECT_ID}-generic-int-landing/generic/customers/customers.csv.ok",
    "entity": "customers",
    "extract_date": "20260101"
  }
}
```

### Trigger via Pub/Sub (Simulating GCS Notification)

```bash
PROJECT_ID=$(gcloud config get-value project)

# Publish a mock file notification
gcloud pubsub topics publish generic-file-notifications \
    --message='{"bucket": "'${PROJECT_ID}'-generic-int-landing", "name": "generic/customers/generic_customers.csv.ok", "eventType": "OBJECT_FINALIZE"}'

# Verify message was received
gcloud pubsub subscriptions pull generic-file-notifications-sub \
    --auto-ack --limit=5
```

### Production-Equivalent Execution (Full DAG Chain)

In production, the DAGs execute in this chain:

1. **pubsub_trigger_dag** -- PubSubPullSensor waits for `.ok` file notification, validates file, triggers `data_ingestion_dag`
2. **data_ingestion_dag** -- Launches Dataflow Flex Template, updates job_control, checks if all 4 entities are loaded, triggers `transformation_dag`
3. **transformation_dag** -- Runs dbt staging, then FDP, then tests, updates job_control
4. **error_handling_dag** -- Runs every 30 minutes, queries `job_control` for failed jobs, routes to retry or manual review

To test the full chain on GCP, upload a real file with its trigger:

```bash
PROJECT_ID=$(gcloud config get-value project)

# Upload test data file
gsutil cp deployments/original-data-to-bigqueryload/tests/data/generic_customers_sample.csv \
    gs://${PROJECT_ID}-generic-int-landing/generic/customers/

# Upload trigger file (this fires the GCS notification → Pub/Sub → pubsub_trigger_dag)
touch /tmp/generic_customers_sample.csv.ok
gsutil cp /tmp/generic_customers_sample.csv.ok \
    gs://${PROJECT_ID}-generic-int-landing/generic/customers/

# Monitor the chain in Airflow UI or via CLI:
gcloud composer environments run generic-int-composer \
    --location=europe-west2 \
    dags list-runs -- -d pubsub_trigger_dag
```

### Local Airflow (Docker Compose)

For full local testing with Airflow, see [DOCKER_COMPOSE_GUIDE.md](./DOCKER_COMPOSE_GUIDE.md) for Docker Compose setup with Airflow, Pub/Sub emulator, and BigQuery emulator.

### Verify via GCP Console UI

1. **Cloud Composer**: Go to `console.cloud.google.com` > **Composer**. Click `generic-int-composer` > **Open Airflow UI**. This opens the Airflow web interface where you can:
   - View all DAGs and their status (green = success, red = failed)
   - Click a DAG name to see run history and task-level logs
   - Click **Trigger DAG** (play button) and paste the configuration JSON above
   - Click a failed task > **Log** to see the error details
2. **Pub/Sub**: Go to **Pub/Sub** > **Topics** > `generic-file-notifications`. Click **Publish Message** to manually send a test notification. Go to **Subscriptions** > `generic-file-notifications-sub` > **Pull** to see received messages.
3. **Cloud Storage**: Go to **Cloud Storage** > `{PROJECT_ID}-generic-int-landing`. Upload the test CSV and `.ok` trigger file directly through the UI using the **Upload Files** button.
4. **Cloud Logging**: Go to **Logging** > **Logs Explorer**. Filter by `resource.type="cloud_composer_environment"` to see DAG execution logs.

### Verify via CLI

| Check | Command |
|-------|---------|
| DAGs visible in Composer | `gcloud composer environments run generic-int-composer --location=europe-west2 dags list` |
| Pub/Sub sensor triggers | Upload `.ok` file, then check: `gcloud pubsub subscriptions pull generic-file-notifications-sub --auto-ack --limit=5` |
| Dataflow job triggered | `gcloud dataflow jobs list --region=europe-west2` |
| Job control updated | `bq query 'SELECT * FROM job_control.pipeline_jobs ORDER BY created_at DESC LIMIT 5'` |

---

## CDP Layer (dbt)

**Deployment:** `fdp-to-consumable-product`

### GCP Resources Used

| Resource | Name |
|----------|------|
| BigQuery (source) | `fdp_generic.event_transaction_excess`, `fdp_generic.portfolio_account_excess`, `fdp_generic.portfolio_account_facility` |
| BigQuery (target) | `cdp_generic.customer_risk_profile` (partitioned by `_extract_date`, clustered by `customer_id`) |
| BigQuery (job control) | `job_control.pipeline_jobs` |

### IAM Required

| Role | Where | Why |
|------|-------|-----|
| `roles/bigquery.jobUser` | Your project | Run dbt SQL queries |
| `roles/bigquery.dataEditor` | Your project | Read your FDP tables, write CDP tables |
| `roles/bigquery.dataViewer` | Other platform team's project | Read their FDP tables used as CDP sources |

**Cross-team FDP access:** Your service account (`dbt-sa@{PROJECT_ID}.iam.gserviceaccount.com`) needs `roles/bigquery.dataViewer` granted on each external FDP dataset your CDP reads from. The owning platform team must grant this — you cannot self-serve. Raise a request with the owning team and include your service account email.

```bash
# The other platform team runs this on their project:
gcloud projects add-iam-policy-binding {OTHER_TEAM_PROJECT_ID} \
    --member="serviceAccount:dbt-sa@{YOUR_PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataViewer" \
    --condition='expression=resource.name.startsWith("projects/{OTHER_TEAM_PROJECT_ID}/datasets/fdp_"),title=fdp-datasets-only'
```

Or grant at the dataset level (more restrictive, preferred):

```bash
# The other platform team runs this:
bq update --source /dev/stdin {OTHER_TEAM_PROJECT_ID}:fdp_payments <<EOF
{
  "access": [
    {"role": "READER", "userByEmail": "dbt-sa@{YOUR_PROJECT_ID}.iam.gserviceaccount.com"}
  ]
}
EOF
```

### Setup

```bash
./scripts/setup_deployment_venv.sh fdp-to-consumable-product
source deployments/fdp-to-consumable-product/venv/bin/activate
cd deployments/fdp-to-consumable-product/dbt

# Populate shared macros from pip-installed gcp-pipeline-transform
python -c "
import gcp_pipeline_transform, shutil, os
src = os.path.join(os.path.dirname(gcp_pipeline_transform.__file__), 'dbt_shared', 'macros')
shutil.copytree(src, 'shared_macros', dirs_exist_ok=True)
"

dbt deps
```

### dbt Profile Setup

The CDP dbt project uses profile `cdp_profile` (defined in `dbt_project.yml`). Create a matching profile in `~/.dbt/profiles.yml`:

```yaml
cdp_profile:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: oauth
      project: {PROJECT_ID}
      dataset: cdp_generic
      location: europe-west2
      threads: 4
    int:
      type: bigquery
      method: oauth
      project: {PROJECT_ID}
      dataset: cdp_generic
      location: europe-west2
      threads: 4
```

### Compile Check (No GCP Access Needed)

```bash
dbt compile
```

### Run CDP Models (Requires BQ Access)

```bash
# Development target
dbt run --target dev
dbt test

# Integration target (real FDP data)
dbt run --target int
dbt test --target int
```

### Verify via GCP Console UI

1. **BigQuery**: Go to **BigQuery** > **SQL Workspace**. Expand `cdp_generic` > click `customer_risk_profile`. Use the **Preview** tab to check data. Run this query in the editor to verify segment distribution:
   ```sql
   SELECT cdp_segment, COUNT(*) as cnt
   FROM cdp_generic.customer_risk_profile
   GROUP BY 1
   ORDER BY 2 DESC
   ```
2. **BigQuery Schema**: Click the **Schema** tab on `customer_risk_profile` to verify partitioning (`_extract_date`) and clustering (`customer_id`) are configured.

### Verify via CLI

| Check | Command |
|-------|---------|
| Models compiled | `dbt compile` exits 0 |
| CDP table populated | `bq query 'SELECT COUNT(*) FROM cdp_generic.customer_risk_profile'` |
| Segment classification | `bq query 'SELECT cdp_segment, COUNT(*) FROM cdp_generic.customer_risk_profile GROUP BY 1'` |
| All 3 FDP sources joined | Verify non-null values from each FDP source |
| dbt tests pass | `dbt test` exits 0 |

---

## Segment Export (Apache Beam)

**Deployment:** `mainframe-segment-transform`

### GCP Resources Used

| Resource | Name |
|----------|------|
| BigQuery (source) | `cdp_generic.customer_risk_profile` |
| GCS (output) | `gs://{PROJECT_ID}-generic-{ENV}-segments/segments/{run_id}/{SEGMENT_CATEGORY}/segment-*.txt` |
| GCS (temp) | `gs://{PROJECT_ID}-generic-{ENV}-temp/dataflow-temp` |
| BigQuery (job control) | `job_control.pipeline_jobs` |

Segment categories: `ACTIVE_APPROVED`, `DECLINED`, `REFERRED`, `PENDING`.

### IAM Required

| Role | Why |
|------|-----|
| `roles/bigquery.jobUser` | Read from CDP table |
| `roles/bigquery.dataEditor` | Read CDP, write job_control |
| `roles/storage.objectAdmin` | Write segment files to GCS |
| `roles/dataflow.developer` | Submit Dataflow jobs (DataflowRunner only) |

### Setup

```bash
./scripts/setup_deployment_venv.sh mainframe-segment-transform
source deployments/mainframe-segment-transform/venv/bin/activate
```

### Local Beam Execution (DirectRunner)

```bash
PROJECT_ID=$(gcloud config get-value project)

python deployments/mainframe-segment-transform/src/cdp_example/main.py \
    --project $PROJECT_ID \
    --cdp_dataset cdp_generic \
    --cdp_table customer_risk_profile \
    --output_bucket ${PROJECT_ID}-generic-int-segments \
    --run_id test_$(date +%Y%m%d_%H%M%S) \
    --runner DirectRunner
```

### Cloud Execution (DataflowRunner)

```bash
PROJECT_ID=$(gcloud config get-value project)

python deployments/mainframe-segment-transform/src/cdp_example/main.py \
    --project $PROJECT_ID \
    --cdp_dataset cdp_generic \
    --cdp_table customer_risk_profile \
    --output_bucket ${PROJECT_ID}-generic-int-segments \
    --run_id export_$(date +%Y%m%d_%H%M%S) \
    --runner DataflowRunner \
    --region europe-west2 \
    --temp_location gs://${PROJECT_ID}-generic-int-temp/dataflow-temp
```

### Verify via GCP Console UI

1. **Dataflow**: Go to **Dataflow** > **Jobs**. Click the segment export job to see the pipeline graph (ReadFromBigQuery > SegmentByCategory > WriteToText). Check worker logs for errors.
2. **Cloud Storage**: Go to **Cloud Storage** > `{PROJECT_ID}-generic-int-segments` > navigate to `segments/{run_id}/`. Verify each segment category folder exists (`ACTIVE_APPROVED/`, `DECLINED/`, `REFERRED/`, `PENDING/`). Click a segment file to preview the fixed-width content.
3. **BigQuery**: Go to **BigQuery** > `job_control.pipeline_jobs`. Query for the `run_id` to verify the job was logged.

### Verify via CLI

| Check | Command |
|-------|---------|
| Dataflow job succeeded | `gcloud dataflow jobs list --region=europe-west2 --status=all --limit=5` |
| Segment files created | `gsutil ls gs://${PROJECT_ID}-generic-int-segments/segments/{run_id}/` |
| Fixed-width format (200 chars) | `gsutil cat gs://{bucket}/segments/{run_id}/ACTIVE_APPROVED/segment-00-of-01.txt \| head -1 \| wc -c` |
| All segment categories present | `gsutil ls gs://${PROJECT_ID}-generic-int-segments/segments/{run_id}/` |
| Job control updated | `bq query 'SELECT * FROM job_control.pipeline_jobs WHERE run_id = "{run_id}"'` |

---

## Library Tests

Run the full library test suite before modifying any shared code:

```bash
# All libraries (recommended)
./scripts/run_library_tests.sh

# Individual libraries
cd gcp-pipeline-libraries/gcp-pipeline-core && PYTHONPATH=src python -m pytest tests/unit/ -v
cd gcp-pipeline-libraries/gcp-pipeline-beam && PYTHONPATH=src python -m pytest tests/unit/ -v
cd gcp-pipeline-libraries/gcp-pipeline-orchestration && PYTHONPATH=src python -m pytest tests/unit/ -v
```

Run tests for each component **separately** to avoid Python module caching conflicts between libraries.

---

## Testing Checklist

### Pre-Push (Local -- No GCP Required)

| Unit | Test | Command |
|------|------|---------|
| Libraries | Unit tests | `./scripts/run_library_tests.sh` |
| Ingestion | Unit tests | `cd deployments/original-data-to-bigqueryload && pytest tests/unit/ -v` |
| Ingestion | DirectRunner | `python -m data_ingestion.pipeline.runner --runner=DirectRunner ...` |
| Transformation | Compile | `cd deployments/bigquery-to-mapped-product/dbt && dbt compile` |
| Orchestration | DAG parse | `python dags/pubsub_trigger_dag.py` |
| Orchestration | Unit tests | `cd deployments/data-pipeline-orchestrator && pytest tests/unit/ -v` |
| CDP | Compile | `cd deployments/fdp-to-consumable-product/dbt && dbt compile` |

### Integration (Requires GCP Access)

| Unit | Test | Command |
|------|------|---------|
| Ingestion | DataflowRunner | `python -m data_ingestion.pipeline.runner --runner=DataflowRunner ...` |
| Transformation | dbt run | `dbt run --target int` |
| Transformation | dbt test | `dbt test --target int` |
| Orchestration | Deploy DAGs | `gsutil cp dags/* ${DAGS_BUCKET}/generic/` |
| Orchestration | Trigger DAG | Upload `.ok` file to landing bucket or use Airflow UI |
| CDP | dbt run | `dbt run --target int` |
| Segment Export | DataflowRunner | `python src/cdp_example/main.py --runner=DataflowRunner ...` |
| All | Job control | `SELECT * FROM job_control.pipeline_jobs ORDER BY created_at DESC LIMIT 10` |

---

## Generic Test Specifications

These test specs define what to validate at each data layer. Use them as acceptance criteria when building or onboarding any new system — not just the `generic` reference implementation.

### ODP Loading Test Spec

**Purpose:** Verify that source data lands correctly in the Original Data Product layer with full audit trail.

| Test ID | Test Name | Validation | Expected Result |
|---------|-----------|-----------|-----------------|
| ODP-01 | Record count match | Compare HDR/TRL record count with `SELECT COUNT(*) FROM odp_{system}.{entity} WHERE _run_id = '{run_id}'` | Counts match exactly |
| ODP-02 | Audit columns populated | `SELECT _run_id, _source_file, _extract_date, _processed_at FROM odp_{system}.{entity} WHERE _run_id = '{run_id}' LIMIT 5` | All four columns are non-null |
| ODP-03 | Source file tracking | `SELECT DISTINCT _source_file FROM odp_{system}.{entity} WHERE _run_id = '{run_id}'` | Matches the uploaded file name |
| ODP-04 | Extract date correct | `SELECT DISTINCT _extract_date FROM odp_{system}.{entity} WHERE _run_id = '{run_id}'` | Matches the date from the HDR record |
| ODP-05 | Dead letter routing | Introduce a record with a missing required field. Check `odp_{system}.{entity}_failed WHERE _run_id = '{run_id}'` | Bad record appears in dead letter table with `_error_category = 'VALIDATION'` |
| ODP-06 | No data loss | `SELECT COUNT(*) FROM odp_{system}.{entity} WHERE _run_id = '{run_id}'` + `SELECT COUNT(*) FROM odp_{system}.{entity}_failed WHERE _run_id = '{run_id}'` | Sum equals total data records in source file (excluding HDR/TRL) |
| ODP-07 | File archived | `gsutil ls gs://{PROJECT_ID}-{system}-{ENV}-archive/{entity}/` | Source file present in archive bucket |
| ODP-08 | File removed from landing | `gsutil ls gs://{PROJECT_ID}-{system}-{ENV}-landing/{entity}/` | Source file no longer in landing bucket |
| ODP-09 | Job control status | `SELECT status FROM job_control.pipeline_jobs WHERE run_id = '{run_id}'` | Status is `SUCCESS` |
| ODP-10 | Idempotency | Re-run same file with same `run_id` | No duplicate records; same count as first run |
| ODP-11 | Schema enforcement | Upload file with extra/missing columns | Extra columns ignored; missing columns routed to dead letter or padded per config |
| ODP-12 | Partitioning | `SELECT DISTINCT _PARTITIONDATE FROM odp_{system}.{entity} WHERE _run_id = '{run_id}'` | Data is partitioned by `_extract_date` |

### ODP → FDP Transformation Test Spec

This section covers the full path from ODP load through FDP output, including error scenarios. Treat these as the **minimum acceptance criteria** for any new ODP→FDP transformation.

#### Happy Path Tests

**Purpose:** Verify that ODP data is correctly transformed, business rules applied, PII masked, and loaded into the Foundation Data Product layer.

| Test ID | Test Name | Validation Query | Expected Result |
|---------|-----------|-----------------|-----------------|
| FDP-01 | Source-to-target row count (MAP) | `SELECT COUNT(*) FROM odp_{system}.{entity}` vs `SELECT COUNT(*) FROM fdp_{system}.{fdp_table} WHERE _extract_date = '{date}'` | Counts match (MAP = 1:1) |
| FDP-02 | Source-to-target row count (JOIN) | `SELECT COUNT(DISTINCT {join_key}) FROM fdp_{system}.{fdp_table}` vs expected cardinality from ODP join | Counts align with join logic (N:1 = deduplicated) |
| FDP-03 | Audit column propagation | `SELECT _run_id, _extract_date, _transformed_at FROM fdp_{system}.{fdp_table} WHERE _extract_date = '{date}' LIMIT 5` | `_run_id` matches the ODP run; `_transformed_at` is non-null |
| FDP-04 | `_run_id` lineage | `SELECT DISTINCT _run_id FROM fdp_{system}.{fdp_table} WHERE _extract_date = '{date}'` then look up in `job_control.pipeline_jobs` | `_run_id` traces back to the originating ODP load |
| FDP-05 | Column mapping — code translation | `SELECT status_code, status_description FROM fdp_{system}.{fdp_table} WHERE status_code = 'A' LIMIT 1` | `status_description = 'Active'` (staging macro applied) |
| FDP-06 | Column mapping — field rename | `SELECT {target_column} FROM fdp_{system}.{fdp_table} LIMIT 1` | Column name matches FDP spec; source name absent |
| FDP-07 | JOIN correctness | `SELECT f.*, c.name FROM fdp_{system}.{fdp_table} f LEFT JOIN odp_{system}.customers c ON f.customer_id = c.customer_id WHERE c.customer_id IS NULL LIMIT 5` | Zero rows — no unmatched join keys |
| FDP-08 | PII masking applied | `SELECT {pii_column} FROM fdp_{system}.{fdp_table} LIMIT 5` | Values are hashed (FULL/PARTIAL per environment); raw value absent |
| FDP-09 | No raw PII column in output | Check schema: `bq show --schema {PROJECT_ID}:fdp_{system}.{fdp_table}` | Raw PII fields (`ssn`, `dob`, etc.) not present in FDP schema |
| FDP-10 | Surrogate key uniqueness | `SELECT {surrogate_key}, COUNT(*) FROM fdp_{system}.{fdp_table} GROUP BY 1 HAVING COUNT(*) > 1` | Zero rows |
| FDP-11 | Partitioning and clustering | Check table metadata in BQ Console > Schema tab | Partitioned by `_extract_date`, clustered by surrogate/primary key |
| FDP-12 | Incremental merge — no duplicates | Run dbt twice with identical ODP data | `SELECT COUNT(*) FROM fdp_{system}.{fdp_table}` unchanged on second run |
| FDP-13 | Incremental merge — updated records | Load new ODP data with same key but changed value; re-run dbt | Existing row updated; `_transformed_at` is later than first run |
| FDP-14 | dbt built-in tests pass | `dbt test --target {env} --select {fdp_model}` | All schema tests pass: `unique`, `not_null`, `accepted_values`, `relationships` |
| FDP-15 | dbt staging layer correctness | `SELECT * FROM fdp_{system}.stg_{entity} WHERE _extract_date = '{date}' LIMIT 5` | Staging view returns cleaned, code-translated rows (not raw ODP values) |

---

#### Error Scenario Tests

These tests verify that the transformation layer handles failures gracefully and produces actionable diagnostics.

| Test ID | Error Scenario | How to Trigger | Expected Behaviour |
|---------|---------------|----------------|-------------------|
| FDP-ERR-01 | ODP source table empty | Run dbt before ODP load completes | dbt run exits cleanly with 0 rows processed; no FDP rows written for that `_extract_date`; no failure in job_control |
| FDP-ERR-02 | ODP source table missing | Drop or rename the ODP table, run dbt | dbt fails with a clear compilation or runtime error; error surfaced in Airflow task log with table name |
| FDP-ERR-03 | JOIN produces zero rows | Load customers with no matching accounts; run FDP dbt | FDP table contains 0 rows for that run; `dbt test` `not_null` tests fail if key field is required — alert fires |
| FDP-ERR-04 | Unexpected NULL in required column | Load ODP data with NULLs in a field that maps to a `not_null` FDP column | `dbt test` fails; Airflow transformation_dag marks task FAILED; error visible in Cloud Logging |
| FDP-ERR-05 | Schema drift — ODP column renamed | Rename a column in ODP (simulate upstream schema change) | dbt compile fails with a column reference error; CI/CD pipeline blocked before deploying |
| FDP-ERR-06 | Schema drift — new ODP column | Add an unmapped column to ODP | dbt ignores unmapped columns; no failure; new column absent from FDP (expected behaviour) |
| FDP-ERR-07 | Invalid accepted value | Load ODP data with an `accepted_values` violation (e.g., `status = 'X'`) | `dbt test` fails; row is flagged in test results; does NOT prevent FDP write (test-only failure) |
| FDP-ERR-08 | Duplicate surrogate keys in source | Load ODP with duplicate primary keys | FDP incremental MERGE deduplicates on latest `_processed_at`; `dbt test unique` passes after run |
| FDP-ERR-09 | PII masking misconfiguration | Disable masking macro in dev (set `mask_pii` to passthrough) | Raw PII is visible in dev FDP — **confirm this is expected for dev only**; prod must always mask |
| FDP-ERR-10 | Stale ODP data (re-run old extract date) | Re-run dbt with `_extract_date = '{past_date}'` | Incremental model skips rows already merged for that key; existing FDP rows unchanged |
| FDP-ERR-11 | Partial ODP load (only 1 of 3 JOIN entities) | Load `customers` but not `accounts` or `decision`; run FDP dbt | JOIN FDP produces 0 rows (INNER JOIN); MAP FDP (applications) proceeds independently; Airflow FDP-dependency check blocks JOIN transformation until all entities ready |
| FDP-ERR-12 | dbt compilation error | Introduce Jinja syntax error in a dbt model SQL | `dbt compile` fails immediately; no models run; error message includes file path and line number |
| FDP-ERR-13 | BigQuery write permission denied | Revoke `bigquery.dataEditor` from the dbt service account | dbt run fails with `Access Denied`; Airflow task retries up to configured limit then marks FAILED |
| FDP-ERR-14 | Transformation DAG triggered before ODP complete | Manually trigger `transformation_dag` before ingestion finishes | FDP-dependency check in `data_ingestion_dag` gates the trigger; transformation DAG not triggered until all required entities reach SUCCESS |

---

#### Unit Test Patterns (Python)

These are the patterns to follow when writing dbt model unit tests using `gcp-pipeline-tester`.

**Pattern 1 — MAP transformation (1:1, column rename + code translate)**

```python
from gcp_pipeline_tester.dbt import DbtModelTestCase

class TestApplicationsFdpModel(DbtModelTestCase):
    model = "fdp_portfolio_account_facility"
    source_fixture = "tests/fixtures/odp_applications_sample.csv"

    def test_column_mapping(self):
        result = self.run_model()
        row = result[result["application_id"] == "APP-001"].iloc[0]
        self.assertEqual(row["product_type"], "Personal Loan")  # code A → label
        self.assertEqual(row["application_status"], "Approved")  # code 1 → label

    def test_pii_masked(self):
        result = self.run_model()
        # Raw SSN must never appear in FDP
        self.assertNotIn("123-45-6789", result["applicant_ssn_masked"].values)

    def test_audit_columns_present(self):
        result = self.run_model()
        for col in ["_run_id", "_extract_date", "_transformed_at"]:
            self.assertIn(col, result.columns)
            self.assertTrue(result[col].notna().all(), f"{col} must be non-null")
```

**Pattern 2 — JOIN transformation (N ODP tables → 1 FDP table)**

```python
class TestEventTransactionExcessModel(DbtModelTestCase):
    model = "fdp_event_transaction_excess"
    source_fixtures = {
        "odp_generic.customers": "tests/fixtures/odp_customers_sample.csv",
        "odp_generic.accounts":  "tests/fixtures/odp_accounts_sample.csv",
        "odp_generic.decision":  "tests/fixtures/odp_decision_sample.csv",
    }

    def test_join_produces_expected_rows(self):
        result = self.run_model()
        # 3 customers × 2 accounts each = 6 matched rows
        self.assertEqual(len(result), 6)

    def test_no_orphaned_join_keys(self):
        result = self.run_model()
        self.assertTrue(result["customer_id"].notna().all())
        self.assertTrue(result["account_id"].notna().all())

    def test_surrogate_key_unique(self):
        result = self.run_model()
        self.assertEqual(result["event_transaction_key"].nunique(), len(result))
```

**Pattern 3 — Error scenario: empty ODP source**

```python
class TestFdpHandlesEmptyOdp(DbtModelTestCase):
    model = "fdp_portfolio_account_facility"
    source_fixtures = {
        "odp_generic.applications": "tests/fixtures/empty.csv",  # zero data rows
    }

    def test_empty_source_produces_no_output(self):
        result = self.run_model()
        self.assertEqual(len(result), 0)

    def test_empty_source_does_not_raise(self):
        # dbt must exit 0 — no exception, no Airflow FAILED state
        self.assertRunSucceeds()
```

**Pattern 4 — Incremental merge idempotency**

```python
class TestFdpIncrementalMerge(DbtModelTestCase):
    model = "fdp_portfolio_account_facility"
    source_fixture = "tests/fixtures/odp_applications_sample.csv"

    def test_second_run_does_not_duplicate(self):
        self.run_model()  # first run
        count_after_first = self.row_count()
        self.run_model()  # second run with same data
        count_after_second = self.row_count()
        self.assertEqual(count_after_first, count_after_second)

    def test_updated_record_is_merged_not_duplicated(self):
        self.run_model()
        self.update_fixture_field("APP-001", "status_code", "D")  # D = Declined
        self.run_model()
        rows = self.fetch_by_key("application_id", "APP-001")
        self.assertEqual(len(rows), 1)  # still 1 row, not 2
        self.assertEqual(rows.iloc[0]["application_status"], "Declined")
```

---

#### SQL Validation Queries (run after dbt in GCP)

```sql
-- FDP-01: Row count vs ODP source (MAP pattern)
SELECT
  (SELECT COUNT(*) FROM `{PROJECT_ID}.odp_{system}.applications`
   WHERE _extract_date = '{date}') AS odp_count,
  (SELECT COUNT(*) FROM `{PROJECT_ID}.fdp_{system}.portfolio_account_facility`
   WHERE _extract_date = '{date}') AS fdp_count;

-- FDP-02: JOIN completeness — no unmatched keys
SELECT COUNT(*) AS orphaned_rows
FROM `{PROJECT_ID}.fdp_{system}.event_transaction_excess` f
LEFT JOIN `{PROJECT_ID}.odp_{system}.customers` c USING (customer_id)
WHERE c.customer_id IS NULL
  AND f._extract_date = '{date}';

-- FDP-03: Surrogate key uniqueness
SELECT surrogate_key, COUNT(*) AS occurrences
FROM `{PROJECT_ID}.fdp_{system}.{fdp_table}`
WHERE _extract_date = '{date}'
GROUP BY 1
HAVING COUNT(*) > 1;

-- FDP-04: Audit column completeness
SELECT
  COUNTIF(_run_id IS NULL) AS missing_run_id,
  COUNTIF(_extract_date IS NULL) AS missing_extract_date,
  COUNTIF(_transformed_at IS NULL) AS missing_transformed_at
FROM `{PROJECT_ID}.fdp_{system}.{fdp_table}`
WHERE _extract_date = '{date}';

-- FDP-05: Run ID traces to ODP load
SELECT j.run_id, j.status, j.entity, j.stage
FROM `{PROJECT_ID}.job_control.pipeline_jobs` j
WHERE j.run_id IN (
  SELECT DISTINCT _run_id
  FROM `{PROJECT_ID}.fdp_{system}.{fdp_table}`
  WHERE _extract_date = '{date}'
);

-- FDP-06: Confirm no raw PII value appears in FDP (spot-check SSN)
-- Expected: zero rows
SELECT COUNT(*) AS raw_pii_rows
FROM `{PROJECT_ID}.fdp_{system}.{fdp_table}`
WHERE REGEXP_CONTAINS(TO_JSON_STRING({fdp_table}), r'\d{3}-\d{2}-\d{4}');

-- FDP-ERR-03: Detect partial JOIN (only some entities loaded today)
SELECT entity, COUNT(*) AS loaded_count
FROM `{PROJECT_ID}.job_control.pipeline_jobs`
WHERE DATE(created_at) = '{date}'
  AND system = '{system}'
  AND status = 'SUCCESS'
GROUP BY entity;
-- If not all required entities appear → JOIN FDP should not have been triggered
```

### CDP Test Spec

**Purpose:** Verify that CDP tables correctly combine FDP sources (own and external) into consumable data products with correct segment classification.

| Test ID | Test Name | Validation | Expected Result |
|---------|-----------|-----------|-----------------|
| CDP-01 | All FDP sources joined | For each source FDP table, verify non-null columns in CDP output | No unexpected nulls from any FDP source |
| CDP-02 | Source FDP availability | Before running CDP dbt, check that all source FDP tables exist and have data | `SELECT COUNT(*) FROM fdp_{system}.{table}` returns > 0 for each source |
| CDP-03 | External FDP sources | If CDP joins FDPs from other teams/apps: verify cross-dataset access | `SELECT COUNT(*) FROM {other_project}.fdp_{other_system}.{table}` succeeds |
| CDP-04 | External FDP freshness | Check that external FDP data is recent enough | `SELECT MAX(_transformed_at) FROM {other_project}.fdp_{other_system}.{table}` is within acceptable window |
| CDP-05 | Segment classification | `SELECT cdp_segment, COUNT(*) FROM cdp_{system}.{cdp_table} GROUP BY 1` | All expected segments present; no `NULL` segments |
| CDP-06 | Segment business rules | Spot-check classification logic against known test records | Records assigned to correct segments based on business rules |
| CDP-07 | Record completeness | `SELECT COUNT(*) FROM cdp_{system}.{cdp_table} WHERE {key_field} IS NULL` | Zero null keys |
| CDP-08 | Cross-project IAM | If reading external FDPs: verify service account has `bigquery.dataViewer` on the external dataset | Query succeeds without permission errors |
| CDP-09 | Incremental merge | Run CDP dbt twice with same source data | No duplicates; `_transformed_at` updated |
| CDP-10 | dbt tests pass | `dbt test --target {env}` | All tests pass |
| CDP-11 | Partitioning | Check CDP table metadata | Partitioned by `_extract_date`, clustered by primary key (e.g., `customer_id`) |
| CDP-12 | Lineage traceability | `SELECT _run_id FROM cdp_{system}.{cdp_table} LIMIT 5` | `_run_id` traces back to original ODP load |

### CDP with FDP Sources from Other Platform Teams

A CDP table often joins FDPs produced by your own pipeline **and** FDPs produced by other platform teams within the organisation. These cross-team FDPs live in different GCP projects or different BigQuery datasets but are within the same GCP organisation.

**Example:** Your CDP `customer_risk_profile` joins:
- `fdp_generic.event_transaction_excess` (your team's FDP)
- `fdp_generic.portfolio_account_excess` (your team's FDP)
- `payments-platform-prod.fdp_payments.payment_history` (Payments team's FDP)

**Additional Setup Required:**

| Step | Action | Details |
|------|--------|---------|
| 1 | Cross-project dataset access | The other platform team grants `roles/bigquery.dataViewer` on their FDP dataset to your CDP service account (`dbt-sa@{PROJECT_ID}.iam.gserviceaccount.com`) |
| 2 | dbt source definition | Add the other team's FDP as a `source` in `dbt/models/sources.yml` with their project ID and dataset name |
| 3 | Freshness check | Add `freshness` block to the dbt source definition to alert if the other team's data is stale |
| 4 | Schema contract | Agree on the expected schema, update frequency, and SLA with the owning platform team. Document in a shared location |
| 5 | Network/VPC | If the other team's project is in a different VPC, ensure BigQuery cross-project queries are not blocked by VPC Service Controls |

**Example dbt source for another platform team's FDP:**

```yaml
# dbt/models/sources.yml
sources:
  - name: payments_fdp
    database: payments-platform-prod       # Other team's GCP project
    schema: fdp_payments                   # Other team's FDP dataset
    tables:
      - name: payment_history
        description: "Payment history FDP owned by the Payments platform team"
        freshness:
          warn_after: {count: 24, period: hour}
          error_after: {count: 48, period: hour}
        loaded_at_field: _transformed_at
```

**Testing cross-team FDP access:**

```bash
PROJECT_ID=$(gcloud config get-value project)

# Verify your SA can read the other team's FDP
bq query --project_id=${PROJECT_ID} \
  'SELECT COUNT(*) FROM `payments-platform-prod.fdp_payments.payment_history`'

# Check freshness
bq query --project_id=${PROJECT_ID} \
  'SELECT MAX(_transformed_at) FROM `payments-platform-prod.fdp_payments.payment_history`'
```

---

## New Deployment Checklist

Use this checklist when creating a new deployment of any type. It ensures no resources, APIs, or permissions are missed.

### GCP APIs to Enable

These must be enabled on the project before any deployment can function. Run `./scripts/gcp/01_enable_services.sh` or enable manually:

| API | Required For |
|-----|-------------|
| `bigquery.googleapis.com` | All deployments (ODP, FDP, CDP, job_control) |
| `storage.googleapis.com` | All deployments (landing, archive, error, temp, segments) |
| `pubsub.googleapis.com` | Orchestration (file notifications, pipeline events) |
| `dataflow.googleapis.com` | Ingestion, Segment Export |
| `composer.googleapis.com` | Orchestration (Cloud Composer) |
| `cloudbuild.googleapis.com` | Docker image builds (Ingestion, Transformation) |
| `containerregistry.googleapis.com` | Docker image storage |
| `iam.googleapis.com` | Service account management |
| `monitoring.googleapis.com` | Metrics and dashboards |
| `logging.googleapis.com` | Centralized logs |
| `secretmanager.googleapis.com` | Secrets (API keys, connection strings) |
| `cloudkms.googleapis.com` | Encryption keys (if Pub/Sub CMEK is used) |

### New Ingestion Deployment (Beam/Dataflow)

When creating a new `source-to-bigqueryload` deployment:

| Step | Resource/Action | Command/Details |
|------|----------------|-----------------|
| 1 | GCS landing bucket | `gsutil mb -l europe-west2 gs://${PROJECT_ID}-{system}-{ENV}-landing` |
| 2 | GCS archive bucket | `gsutil mb -l europe-west2 gs://${PROJECT_ID}-{system}-{ENV}-archive` |
| 3 | GCS error bucket | `gsutil mb -l europe-west2 gs://${PROJECT_ID}-{system}-{ENV}-error` |
| 4 | GCS temp bucket | `gsutil mb -l europe-west2 gs://${PROJECT_ID}-{system}-{ENV}-temp` |
| 5 | GCS notification | `gsutil notification create -t {system}-file-notifications -f json gs://${PROJECT_ID}-{system}-{ENV}-landing` |
| 6 | BigQuery ODP dataset | `bq mk --location=europe-west2 odp_{system}` |
| 7 | BigQuery ODP tables | Create entity tables with audit columns (`_run_id`, `_source_file`, `_extract_date`, `_processed_at`) |
| 8 | BigQuery dead letter tables | Create `{entity}_failed` tables with error columns (`_error_category`, `_error_severity`, `_error_message`, `_raw_record`) |
| 9 | BigQuery job_control | Ensure `job_control.pipeline_jobs` and `job_control.audit_trail` exist (shared across systems) |
| 10 | Service account | Create or reuse SA with: `dataflow.developer`, `dataflow.worker`, `storage.objectAdmin`, `bigquery.dataEditor`, `bigquery.jobUser` |
| 11 | Dataflow API | Ensure `dataflow.googleapis.com` is enabled |
| 12 | Docker image | Build and push to GCR: `gcr.io/${PROJECT_ID}/{system}-ingestion:{version}` |
| 13 | Flex Template | Publish template JSON to `gs://${PROJECT_ID}-{system}-{ENV}-temp/templates/` |
| 14 | Unit tests | `pytest tests/unit/ -v` |
| 15 | DirectRunner test | `python -m {module}.pipeline.runner --runner=DirectRunner ...` |
| 16 | DataflowRunner test | `python -m {module}.pipeline.runner --runner=DataflowRunner ...` |

### New Transformation Deployment (dbt/BigQuery)

When creating a new `source-to-mapped-product` deployment:

| Step | Resource/Action | Command/Details |
|------|----------------|-----------------|
| 1 | BigQuery source dataset | Ensure ODP dataset exists (e.g., `odp_{system}`) with populated tables |
| 2 | BigQuery target dataset | `bq mk --location=europe-west2 fdp_{system}` |
| 3 | dbt profiles.yml | Configure `dev`, `int`, `prod` targets pointing to the correct project and datasets |
| 4 | dbt macro-paths | Set `macro-paths: ["macros", "shared_macros"]` in `dbt_project.yml`. Dockerfile copies macros from pip-installed `gcp-pipeline-transform`. Add `dbt_utils` to `packages.yml` |
| 5 | Service account | Create or reuse SA with: `bigquery.jobUser`, `bigquery.dataEditor` |
| 6 | Compile check | `dbt compile` (no GCP access needed) |
| 7 | Dev run | `dbt run --target dev && dbt test --target dev` |
| 8 | Int run | `dbt run --target int && dbt test --target int` |

### New Orchestration Deployment (Airflow/Composer)

When creating a new orchestration deployment:

| Step | Resource/Action | Command/Details |
|------|----------------|-----------------|
| 1 | Cloud Composer environment | `gcloud composer environments create {system}-{ENV}-composer --location=europe-west2 --image-version=composer-2.x.x-airflow-2.x.x` |
| 2 | Composer PyPI packages | Add `gcp-pipeline-framework>=1.0.6` to Composer environment PyPI dependencies |
| 3 | Pub/Sub file notification topic | `gcloud pubsub topics create {system}-file-notifications` |
| 4 | Pub/Sub file notification subscription | `gcloud pubsub subscriptions create {system}-file-notifications-sub --topic={system}-file-notifications` |
| 5 | Pub/Sub pipeline events topic | `gcloud pubsub topics create {system}-pipeline-events` |
| 6 | Pub/Sub pipeline events subscription | `gcloud pubsub subscriptions create {system}-pipeline-events-sub --topic={system}-pipeline-events` |
| 7 | GCS notification on landing bucket | `gsutil notification create -t {system}-file-notifications -f json gs://${PROJECT_ID}-{system}-{ENV}-landing` |
| 8 | BigQuery job_control | Ensure `job_control.pipeline_jobs` and `job_control.audit_trail` exist |
| 9 | Composer SA roles | `composer.worker`, `dataflow.developer`, `bigquery.jobUser`, `bigquery.dataEditor`, `storage.objectAdmin`, `pubsub.publisher`, `pubsub.subscriber` |
| 10 | DAG syntax validation | `python dags/pubsub_trigger_dag.py && python dags/data_ingestion_dag.py && python dags/transformation_dag.py && python dags/error_handling_dag.py` (no output = no errors) |
| 11 | Unit tests | `pytest tests/unit/ -v` |
| 12 | Deploy DAGs | `gsutil cp dags/* ${DAGS_BUCKET}/{system}/` |
| 13 | Verify in Airflow UI | DAGs appear without import errors |

### New CDP Deployment (dbt/BigQuery)

When creating a new `fdp-to-consumable-product` deployment:

| Step | Resource/Action | Command/Details |
|------|----------------|-----------------|
| 1 | BigQuery source dataset | Ensure FDP dataset exists (e.g., `fdp_{system}`) with populated tables |
| 2 | BigQuery target dataset | `bq mk --location=europe-west2 cdp_{system}` |
| 3 | dbt profiles.yml | Configure targets pointing to source and target datasets |
| 4 | Service account | Reuse dbt SA with: `bigquery.jobUser`, `bigquery.dataEditor` |
| 5 | Compile and run | `dbt compile && dbt run --target dev && dbt test` |

### New Segment Export Deployment (Beam/Dataflow)

When creating a new mainframe segment export deployment:

| Step | Resource/Action | Command/Details |
|------|----------------|-----------------|
| 1 | BigQuery source | Ensure CDP dataset and table exist (e.g., `cdp_{system}.{table}`) |
| 2 | GCS segments bucket | `gsutil mb -l europe-west2 gs://${PROJECT_ID}-{system}-{ENV}-segments` |
| 3 | GCS temp bucket | Reuse `gs://${PROJECT_ID}-{system}-{ENV}-temp` |
| 4 | Service account | Create or reuse SA with: `bigquery.jobUser`, `bigquery.dataEditor`, `storage.objectAdmin`, `dataflow.developer`, `dataflow.worker` |
| 5 | DirectRunner test | `python src/{module}/main.py --runner=DirectRunner ...` |
| 6 | DataflowRunner test | `python src/{module}/main.py --runner=DataflowRunner ...` |
| 7 | Verify segment files | `gsutil ls gs://{bucket}/segments/{run_id}/` |

---

## References

- [E2E Testing Guide](./E2E_TESTING_GUIDE.md) -- full GCP end-to-end test procedure
- [Docker Compose Guide](./DOCKER_COMPOSE_GUIDE.md) -- local Airflow + emulators
- [Beam File Processing Guide](./BEAM_FILE_PROCESSING_GUIDE.md) -- file size limits, memory, Docker config
- [DAG Development Guide](./DAG_DEVELOPMENT_GUIDE.md) -- DAG naming, patterns, templates
- [Error Handling Guide](./ERROR_HANDLING_GUIDE.md) -- error classification, DLQ, retry logic
- [Infrastructure Requirements](./INFRASTRUCTURE_REQUIREMENTS.md) -- full resource specs and Terraform config
- [GCP Deployment Guide](./GCP_DEPLOYMENT_GUIDE.md) -- CI/CD pipeline and deployment phases
