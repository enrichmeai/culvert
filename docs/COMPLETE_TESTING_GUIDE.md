# 📖 Complete Testing & Deployment Guide

Unified guide for the GDW Data Core Library and Deployments (EM & LOA).

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
| **EM** (Application A) | 3 (Customers, Accounts, Decision) | 3 | 1 (`em_attributes`) | JOIN 3→1 |
| **LOA** (Application B) | 1 (Applications) | 1 | 2 (`event_transaction_excess`, `portfolio_account_excess`) | SPLIT 1→2 |

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
pip install -e libraries/gcp-pipeline-builder/
pip install -e deployments/em/
pip install -e deployments/loa/

# Verify installation
python -c "
from gcp_pipeline_builder.file_management import HDRTRLParser
from em.config import SYSTEM_ID as EM_ID
from loa.config import SYSTEM_ID as LOA_ID
print(f'✅ Library: OK')
print(f'✅ EM System ID: {EM_ID}')
print(f'✅ LOA System ID: {LOA_ID}')
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
./run_all_tests.sh em        # EM only (400+ tests)
./run_all_tests.sh loa       # LOA only (60+ tests)
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

# Library tests
PYTHONPATH=libraries/gcp-pipeline-builder/src pytest libraries/gcp-pipeline-builder/tests -v --tb=short

# EM tests
PYTHONPATH=libraries/gcp-pipeline-builder/src:deployments/em/src pytest deployments/em/tests -v --tb=short

# LOA tests
PYTHONPATH=libraries/gcp-pipeline-builder/src:deployments/loa/src pytest deployments/loa/tests -v --tb=short
```

### CI/CD Pipeline

On every push/PR, GitHub Actions runs tests in isolation:

```
┌──────────────┐
│ test-library │ ← Runs first
└──────┬───────┘
       │
  ┌────┴────┐
  ▼         ▼
┌────────┐ ┌────────┐
│test-em │ │test-loa│ ← Parallel after library
└────────┘ └────────┘
       │         │
       └────┬────┘
            ▼
   ┌─────────────────┐
   │ all-tests-pass  │
   └─────────────────┘
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

# Deploy EM
cd em
terraform init
terraform apply -var-file=../env/staging.tfvars

# Deploy LOA
cd ../loa
terraform init  
terraform apply -var-file=../env/staging.tfvars
```

### Step 2: Verify Resources

```bash
export PROJECT_ID=$(gcloud config get-value project)

# Check buckets
gsutil ls gs://${PROJECT_ID}-em-staging-landing
gsutil ls gs://${PROJECT_ID}-loa-staging-landing

# Check Pub/Sub
gcloud pubsub topics list

# Check BigQuery
bq ls
```

### Step 3: Deploy Airflow DAGs

```bash
# Copy to Cloud Composer
gsutil -m cp deployments/em/src/em/orchestration/airflow/dags/*.py gs://${COMPOSER_BUCKET}/dags/
gsutil -m cp deployments/loa/src/loa/orchestration/airflow/dags/*.py gs://${COMPOSER_BUCKET}/dags/
```

---

## Post-Deployment Testing

### Using the Deployment Test Script

```bash
# Test EM deployment
./test_deployment.sh em

# Test LOA deployment
./test_deployment.sh loa
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
gsutil cp test_applications.csv gs://${PROJECT_ID}-loa-staging-landing/loa/
gsutil cp /dev/null gs://${PROJECT_ID}-loa-staging-landing/loa/test_applications.csv.ok

# 2. Check Pub/Sub received message
gcloud pubsub subscriptions pull loa-file-notifications-sub --auto-ack --limit=5

# 3. Wait for pipeline (30-60 seconds)
sleep 60

# 4. Query BigQuery
bq query --use_legacy_sql=false \
  "SELECT COUNT(*) FROM \`${PROJECT_ID}.odp_loa.applications\`"

# 5. Check archive
gsutil ls gs://${PROJECT_ID}-loa-staging-archive/
```

---

## Test Data Examples

### EM Customers File

```csv
HDR|EM|Customers|20260102
customer_id,name,ssn,account_status,created_date
CUST001,John Doe,123-45-6789,ACTIVE,2026-01-01
CUST002,Jane Smith,987-65-4321,ACTIVE,2026-01-01
TRL|RecordCount=2|Checksum=abc123
```

### LOA Applications File

```csv
HDR|LOA|Applications|20260102
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
./run_all_tests.sh em       # Then
./run_all_tests.sh loa
```

### Import Errors

**Solution:** Set PYTHONPATH correctly:

```bash
export PYTHONPATH=.:./gcp_pipeline_builder:./deployments
pip install -e gcp_pipeline_builder/
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
| [pubsub_kms_secure_trigger.mmd](../../gcp_pipeline_builder/docs/diagrams/pubsub_kms_secure_trigger.mmd) | Secure Pub/Sub with KMS |
| [intelligent_routing_flow.mmd](../../gcp_pipeline_builder/docs/diagrams/intelligent_routing_flow.mmd) | Pipeline routing |
| [audit_framework_flow.mmd](../../gcp_pipeline_builder/docs/diagrams/audit_framework_flow.mmd) | Audit trail |

---

## Quick Reference

| Task | Command |
|------|---------|
| Run all tests | `./run_all_tests.sh` |
| Run library tests | `./run_all_tests.sh library` |
| Run EM tests | `./run_all_tests.sh em` |
| Run LOA tests | `./run_all_tests.sh loa` |
| Test EM deployment | `./test_deployment.sh em` |
| Test LOA deployment | `./test_deployment.sh loa` |
| Deploy EM Terraform | `cd infrastructure/terraform/em && terraform apply` |
| Deploy LOA Terraform | `cd infrastructure/terraform/loa && terraform apply` |

---

<div align="center">

**Version 2.0** | **Last Updated: January 2, 2026**

</div>
