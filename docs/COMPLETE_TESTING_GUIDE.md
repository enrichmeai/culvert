# 📖 Complete Testing & Deployment Guide

Unified guide for the GDW Data Core Library and Deployments (Application1 & Application2).

**Last Updated:** January 2, 2026  
**Reference:** [E2E Functional Flow](../E2E_FUNCTIONAL_FLOW.md)

---

## Quick Navigation

| Goal | Section |
|------|---------|
| Set up environment | [Environment Setup](#environment-setup) |
| Run tests locally | [Testing Workflow](#testing-workflow) |
| Deploy to GCP | [GCP Deployment](#gcp-deployment) |
| Validate deployment | [Post-Deployment Testing](#post-deployment-testing) |
| Troubleshoot issues | [Troubleshooting](#troubleshooting) |

---

## System Overview

Per the [E2E Functional Flow](../E2E_FUNCTIONAL_FLOW.md), we have two pipeline systems:

| System | Entities | ODP Tables | FDP Tables | Pattern |
|--------|----------|------------|------------|---------|
| **Application1** (Application A) | 3 (Customers, Accounts, Decision) | 3 | 2 (`event_transaction_excess`, `portfolio_account_excess`) | MULTI-TARGET |
| **Application2** (Application B) | 1 (Applications) | 1 | 1 (`portfolio_account_facility`) | MAP |

### File Format (Both Systems)

```
HDR|{SYSTEM}|{ENTITY}|{YYYYMMDD}     ← Header record
{csv_header_row}                      ← Column names  
{data_rows...}                        ← Data records
TRL|RecordCount={n}|Checksum={hash}   ← Trailer record
```

---

## Environment Setup

### Step 1: Clone and Install

```bash
# Clone repository
git clone <repo-url>
cd legacy-migration-reference

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r deployments/setup/requirements.txt
pip install -r deployments/setup/requirements-test.txt

# Install packages in editable mode
pip install -e gcp-pipeline-libraries/gcp-pipeline-core/
pip install -e deployments/application1/
pip install -e deployments/application2/

# Verify installation
python -c "
from gcp_pipeline_beam.file_management import HDRTRLParser
from application1.config import SYSTEM_ID as Application1_ID
from application2.config import SYSTEM_ID as Application2_ID
print(f'✅ Library: OK')
print(f'✅ Application1 System ID: {Application1_ID}')
print(f'✅ Application2 System ID: {Application2_ID}')
"
```

### Step 2: Docker Setup (Optional)

```bash
cd deployments/setup
docker-compose up -d

# Access Airflow: http://localhost:8080 (admin/airflow)
```

---

## Testing Workflow

### ⚠️ Critical: Run Tests in Isolation

To avoid Python module caching conflicts, run tests for each component **separately**:

```bash
# Use the test runner script (recommended)
./run_all_tests.sh

# Or run each component separately:
./run_all_tests.sh library   # Library only (500+ tests)
./run_all_tests.sh application1        # Application1 only (400+ tests)
./run_all_tests.sh application2       # Application2 only (60+ tests)
```

### Test Categories

| Category | Location | Purpose |
|----------|----------|---------|
| **Unit** | `tests/unit/` | Test individual components |
| **Integration** | `tests/integration/` | Test with mocked GCP |
| **BDD** | `tests/bdd/` | E2E scenarios (post-deployment) |
| **Infrastructure** | `tests/unit/infrastructure/` | Terraform validation |

### Running Tests Manually

```bash
cd /path/to/legacy-migration-reference

# Core library tests (208 tests)
cd gcp-pipeline-libraries/gcp-pipeline-core
PYTHONPATH=src python -m pytest tests/unit/ -v --tb=short

# Beam library tests (358 tests)
cd ../gcp-pipeline-beam
PYTHONPATH=src:../gcp-pipeline-core/src python -m pytest tests/unit/ -v --tb=short

# Orchestration library tests (52 tests)
cd ../gcp-pipeline-orchestration
PYTHONPATH=src:../gcp-pipeline-core/src python -m pytest tests/unit/ -v --tb=short

# Application2 Ingestion tests (36 tests)
cd ../../deployments/application2-ingestion
PYTHONPATH=src:../../gcp-pipeline-libraries/gcp-pipeline-core/src:../../gcp-pipeline-libraries/gcp-pipeline-beam/src \
  python -m pytest tests/unit/ -v --tb=short

# Application1 Ingestion tests (44 tests)
cd ../application1-ingestion
PYTHONPATH=src:../../gcp-pipeline-libraries/gcp-pipeline-core/src:../../gcp-pipeline-libraries/gcp-pipeline-beam/src \
  python -m pytest tests/unit/ -v --tb=short
```

### CI/CD Pipeline

On every push/PR, GitHub Actions runs tests in isolation:

```
┌──────────────────┐
│ test-core        │ ← Runs first (foundation)
└────────┬─────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌──────────────┐
│test-   │ │test-         │
│beam    │ │orchestration │ ← Parallel after core
└────┬───┘ └──────┬───────┘
     │            │
     └─────┬──────┘
           ▼
  ┌────────────────┐
  │ test-ingestion │ ← Application1 + Application2 ingestion
  └────────────────┘
```

See [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml).

---

## GCP Deployment

### Step 1: Deploy Infrastructure

```bash
cd infrastructure/terraform

# Deploy shared security (KMS keys)
terraform init
terraform apply

# Deploy Application1
cd application1
terraform init
terraform apply -var-file=../env/staging.tfvars

# Deploy Application2
cd ../application2
terraform init  
terraform apply -var-file=../env/staging.tfvars
```

### Step 2: Verify Resources

```bash
export PROJECT_ID=$(gcloud config get-value project)

# Check buckets
gsutil ls gs://${PROJECT_ID}-application1-staging-landing
gsutil ls gs://${PROJECT_ID}-application2-staging-landing

# Check Pub/Sub
gcloud pubsub topics list

# Check BigQuery
bq ls
```

### Step 3: Deploy Airflow DAGs

```bash
# Copy to Cloud Composer
gsutil -m cp deployments/application1/src/application1/orchestration/airflow/dags/*.py gs://${COMPOSER_BUCKET}/dags/
gsutil -m cp deployments/application2/src/application2/orchestration/airflow/dags/*.py gs://${COMPOSER_BUCKET}/dags/
```

---

## Post-Deployment Testing

### Using the Deployment Test Script

```bash
# Test Application1 deployment
./test_deployment.sh application1

# Test Application2 deployment
./test_deployment.sh application2
```

**What the script does:**
1. ✅ Generates test data with HDR/TRL format
2. ✅ Uploads to GCS landing bucket
3. ✅ Creates `.ok` trigger file
4. ✅ Waits for pipeline processing
5. ✅ Checks Pub/Sub, BigQuery, and archive

### Manual Validation

```bash
export PROJECT_ID=$(gcloud config get-value project)

# 1. Upload test file + trigger
gsutil cp test_applications.csv gs://${PROJECT_ID}-application2-staging-landing/application2/
gsutil cp /dev/null gs://${PROJECT_ID}-application2-staging-landing/application2/test_applications.csv.ok

# 2. Check Pub/Sub received message
gcloud pubsub subscriptions pull application2-file-notifications-sub --auto-ack --limit=5

# 3. Wait for pipeline (30-60 seconds)
sleep 60

# 4. Query BigQuery
bq query --use_legacy_sql=false \
  "SELECT COUNT(*) FROM \`${PROJECT_ID}.odp_application2.applications\`"

# 5. Check archive
gsutil ls gs://${PROJECT_ID}-application2-staging-archive/
```

---

## Test Data Examples

### Application1 Customers File

```csv
HDR|Application1|Customers|20260102
customer_id,name,ssn,account_status,created_date
CUST001,John Doe,123-45-6789,ACTIVE,2026-01-01
CUST002,Jane Smith,987-65-4321,ACTIVE,2026-01-01
TRL|RecordCount=2|Checksum=abc123
```

### Application2 Applications File

```csv
HDR|Application2|Applications|20260102
application_id,customer_id,ssn,loan_amount,application_date,application_status
APP001,CUST001,123-45-6789,50000.00,2026-01-01,PENDING
APP002,CUST002,987-65-4321,75000.00,2026-01-01,APPROVED
TRL|RecordCount=2|Checksum=def456
```

---

## Troubleshooting

### Tests Fail When Run Together

**Solution:** Run in isolation using `./run_all_tests.sh`

```bash
./run_all_tests.sh library  # Then
./run_all_tests.sh application1       # Then
./run_all_tests.sh application2
```

### Import Errors

**Solution:** Set PYTHONPATH correctly:

```bash
export PYTHONPATH=.:./gcp_pipeline_core:./deployments
pip install -e gcp_pipeline_core/
pip install -e deployments/
```

### Pub/Sub Not Triggering

**Check:**
1. `.ok` file uploaded
2. GCS notification configured: `gsutil notification list gs://BUCKET`
3. Subscription exists: `gcloud pubsub subscriptions describe SUBSCRIPTION`

### BigQuery Table Empty

**Check:**
1. Airflow DAG status
2. Dataflow job logs
3. Error bucket: `gsutil ls gs://${PROJECT_ID}-*-error/`

---

## Architecture Reference

See [E2E Functional Flow](../E2E_FUNCTIONAL_FLOW.md) for complete architecture.

### Key Diagrams

| Diagram | Purpose |
|---------|---------|
| [pubsub_kms_secure_trigger.mmd](../../gcp_pipeline_core/docs/diagrams/pubsub_kms_secure_trigger.mmd) | Secure Pub/Sub with KMS |
| [intelligent_routing_flow.mmd](../../gcp_pipeline_core/docs/diagrams/intelligent_routing_flow.mmd) | Pipeline routing |
| [audit_framework_flow.mmd](../../gcp_pipeline_core/docs/diagrams/audit_framework_flow.mmd) | Audit trail |

---

## Quick Reference

| Task | Command |
|------|---------|
| Run all tests | `./run_all_tests.sh` |
| Run library tests | `./run_all_tests.sh library` |
| Run Application1 tests | `./run_all_tests.sh application1` |
| Run Application2 tests | `./run_all_tests.sh application2` |
| Test Application1 deployment | `./test_deployment.sh application1` |
| Test Application2 deployment | `./test_deployment.sh application2` |
| Deploy Application1 Terraform | `cd infrastructure/terraform/application1 && terraform apply` |
| Deploy Application2 Terraform | `cd infrastructure/terraform/application2 && terraform apply` |

---

<div align="center">

**Version 2.0** | **Last Updated: January 2, 2026**

</div>
