# 📖 Complete Testing & Deployment Guide

Unified guide for LOA Blueprint & GDW Core Library - combining automated testing, manual testing, and GCP deployment.

## Quick Navigation

- **Getting Started?** → [Environment Setup](#environment-setup)
- **Ready to Test?** → [Testing Workflow](#testing-workflow)
- **Setting up GCP?** → [GCP Deployment](#gcp-deployment-with-tools)
- **Issues?** → [Troubleshooting](#troubleshooting)

---

## Environment Setup

### Step 1: Choose Your Setup Method

#### Option A: Docker (Recommended - Full Stack)

```bash
cd blueprint/setup
docker-compose up -d

# Wait for services (2-3 minutes)
docker-compose ps

# Access services:
# - Airflow: http://localhost:8080 (admin/airflow)
# - Jupyter: http://localhost:8888
# - PostgreSQL: localhost:5432
# - BigQuery Emulator: localhost:9050
```

#### Option B: Airflow Setup Script

```bash
cd blueprint/setup
./setup_airflow.sh

# Automatically handles:
# ✓ Virtual environment
# ✓ Dependencies
# ✓ Database setup
# ✓ Admin user creation
# ✓ Service startup
```

#### Option C: Manual Python Installation

```bash
# Create environment
python3 -m venv venv
source venv/bin/activate

# Install all packages
pip install -r blueprint/setup/requirements.txt
pip install -r blueprint/setup/requirements-dev.txt
pip install -r blueprint/setup/requirements-test.txt
pip install -e blueprint
pip install -e gdw_data_core

# Verify
python -c "import blueprint; import gdw_data_core; print('✓ OK')"
```

---

## Testing Workflow

### Phase 1: Unit & Integration Tests (8-10 minutes)

```bash
cd blueprint

# Run all local tests (no external dependencies)
./run_full_tests.sh --full --coverage --report

# Or specific phases:
./run_full_tests.sh --unit              # Unit tests only
./run_full_tests.sh --integration       # Integration tests (mocked)
./run_full_tests.sh --coverage --report # With coverage report

# Expected: 75+ tests pass ✅
```

**What's Tested:**
- DAG creation and parsing
- GCP client mocks (BigQuery, GCS, Dataflow, Pub/Sub)
- Error handling
- Configuration validation
- Retry and timeout settings

**View Results:**
```bash
open htmlcov/index.html
```

---

### Phase 2: Manual Pipeline Testing (15-30 minutes)

#### 2a: Airflow DAG Testing

```bash
# Access Airflow UI
open http://localhost:8080

# In the UI:
# 1. Navigate to DAGs tab
# 2. Find loa_applications_migration
# 3. Click to view structure
# 4. Trigger DAG manually
# 5. Monitor execution
```

**Command-line DAG Validation:**
```bash
# List DAGs
airflow dags list

# Parse DAG
airflow dags test loa_applications_migration 2025-01-01

# Show structure
airflow dags show loa_applications_migration

# Validate connections
airflow connections test gcp_default
```

#### 2b: Local Pipeline Testing

```bash
cd blueprint

# Run local pipeline test
python tools/testing/test_loa_local.py

# Deploy locally
python tools/testing/deploy_local.py

# Generate test data
python tools/testing/generate_output.py

# Validate schema
python components/validation/schema_validator.py /tmp/test_data.csv

# Data quality checks
python components/validation/data_quality.py /tmp/test_data.csv
```

#### 2c: Interactive Testing

```bash
# Start Jupyter
jupyter lab

# Create test notebook:
# - Import components
# - Load sample data
# - Test transformations
# - Validate outputs
```

---

### Phase 3: Staging GCP Deployment (20-30 minutes)

#### 3a: Automated Setup with Tools

```bash
cd blueprint/tools/gcp

# 1. Preflight checks
./preflight_check.sh

# 2. Install dependencies
./setup-dependencies.sh

# 3. Run main setup (interactive)
./setupanddeployongcp.sh

# This configures:
# ✓ GCS buckets
# ✓ BigQuery datasets
# ✓ Dataflow templates
# ✓ Pub/Sub topics
# ✓ Service accounts
# ✓ IAM permissions
# ✓ Airflow connections
```

#### 3b: Manual GCP Setup

```bash
export GCP_PROJECT="staging-project"
export GCP_REGION="us-central1"

# Create GCS bucket
gsutil mb -l $GCP_REGION gs://staging-bucket

# Create BigQuery dataset
bq mk --location=US loa_staging

# Create Pub/Sub topics
gcloud pubsub topics create loa-events --project=$GCP_PROJECT

# Setup service account
gcloud iam service-accounts create loa-tester --project=$GCP_PROJECT

# Grant permissions
gcloud projects add-iam-policy-binding $GCP_PROJECT \
  --member="serviceAccount:loa-tester@$GCP_PROJECT.iam.gserviceaccount.com" \
  --role="roles/dataflow.admin"
```

#### 3c: Run Staging Tests

```bash
export GCP_TEST_PROJECT="staging-project"
export GCP_TEST_REGION="us-central1"
export GCP_TEST_BUCKET="staging-bucket"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# Run staging tests
cd blueprint
./run_full_tests.sh --staging

# Or Python runner
python GCP_DEPLOYMENT_TESTING_GUIDE.py --phase staging
```

---

### Phase 4: Manual Staging Pipeline (10-15 minutes)

```bash
# 1. Upload sample data
gsutil cp tests/data/sample_*.csv gs://staging-bucket/raw/

# 2. Trigger DAG
gcloud composer environments run my-env \
  --location=us-central1 \
  dags trigger -- loa_applications_migration

# 3. Monitor
gcloud composer environments run my-env \
  --location=us-central1 \
  dags list-runs -- loa_applications_migration

# 4. Validate output in BigQuery
bq query "SELECT COUNT(*) FROM \`project:dataset.applications\`"

# 5. Check archive
gsutil ls gs://staging-bucket/archive/

# 6. Check Pub/Sub events
gcloud pubsub subscriptions pull loa-subscription --auto-ack
```

---

### Phase 5: Performance Testing (Optional - 10-15 minutes)

```bash
cd blueprint

# Run performance benchmarks
./run_full_tests.sh --performance

# Or Python runner
python GCP_DEPLOYMENT_TESTING_GUIDE.py --phase performance

# Metrics Checked:
# ✓ Throughput >1000 rec/s
# ✓ Latency <5 min (10K records)
# ✓ Cost <$0.01 per record
```

---

## Complete Testing Sequence

**Recommended order for full deployment validation:**

```bash
# 1. Setup (5 minutes)
cd blueprint/setup
docker-compose up -d
sleep 180

# 2. Unit & Integration (10 minutes)
cd ../
./run_full_tests.sh --full --coverage --report

# 3. Manual DAG Tests (15 minutes)
open http://localhost:8080
# Manually trigger and monitor DAG

# 4. Local Pipeline (10 minutes)
python tools/testing/test_loa_local.py

# 5. Setup GCP Staging (20 minutes)
cd tools/gcp
./preflight_check.sh
./setupanddeployongcp.sh

# 6. Staging Tests (15 minutes)
export GCP_TEST_PROJECT="staging-project"
cd ../../
./run_full_tests.sh --staging

# 7. Manual Staging Pipeline (15 minutes)
gsutil cp tests/data/sample_*.csv gs://staging-bucket/raw/
# Trigger, monitor, validate

# 8. Performance Testing (15 minutes)
./run_full_tests.sh --performance

# Total: ~2 hours for complete validation
```

---

## Key Commands Reference

### Environment Management

```bash
# Start services
cd blueprint/setup && docker-compose up -d

# Check services
docker-compose ps

# View logs
docker-compose logs -f airflow-webserver

# Stop services
docker-compose down

# Reset everything
docker-compose down -v && docker-compose up -d
```

### Testing

```bash
# Run all tests
./blueprint/run_full_tests.sh --full --coverage --report

# Specific test files
pytest blueprint/components/tests/unit/orchestration/test_dag_deployment.py -v
pytest blueprint/components/tests/integration/test_gcp_clients.py -v

# With output
pytest -vv blueprint/components/tests/

# Stop on first failure
pytest -x blueprint/components/tests/
```

### GCP Management

```bash
# Check GCP setup
cd blueprint/tools/gcp && ./preflight_check.sh

# Deploy to GCP
./setupanddeployongcp.sh

# List resources
gcloud compute instances list
gsutil ls
bq ls

# Monitor jobs
gcloud dataflow jobs list --region=us-central1
gcloud composer environments list
```

### Data & Validation

```bash
# Generate test data
python blueprint/tools/testing/generate_output.py

# Validate schema
python blueprint/components/validation/schema_validator.py

# Run data quality
python blueprint/components/validation/data_quality.py

# Bulk migration
python blueprint/tools/migration/bulk_migration_tool.py --config config.yaml
```

---

## Troubleshooting

### Docker Issues

```bash
# Docker services won't start
docker-compose logs -f
docker-compose down -v
docker-compose up -d --build

# Specific service logs
docker-compose logs airflow-webserver
docker-compose logs airflow-db
```

### Module Import Errors

```bash
# Install packages in editable mode
pip install -e blueprint
pip install -e gdw_data_core

# Verify imports
python -c "import blueprint; import gdw_data_core"

# Check Python path
python -c "import sys; print(sys.path)"
```

### Test Failures

```bash
# Run with verbose output
pytest -vv blueprint/components/tests/

# Show print statements
pytest -s blueprint/components/tests/

# Stop on first failure
pytest -x blueprint/components/tests/

# Run specific test
pytest blueprint/components/tests/unit/orchestration/test_dag_deployment.py::TestDAGCreationAndParsing::test_dag_creation_succeeds -v
```

### GCP Authentication

```bash
# Check credentials
gcloud auth list
gcloud config list

# Re-authenticate
gcloud auth application-default login

# Set project
gcloud config set project my-project-id

# Test access
gcloud compute zones list
bq ls
gsutil ls
```

---

## Pre-Deployment Checklist

Before deploying to production:

- [ ] **Environment**
  - [ ] Docker/Airflow setup successful
  - [ ] All services healthy
  - [ ] Python packages installed

- [ ] **Automated Tests**
  - [ ] Unit tests pass (40+)
  - [ ] Integration tests pass (20+)
  - [ ] DAG tests pass (15+)
  - [ ] Coverage ≥80%

- [ ] **Manual Tests**
  - [ ] DAG triggering works
  - [ ] Data flows end-to-end
  - [ ] Schema validation passes
  - [ ] Data quality passes

- [ ] **GCP Staging**
  - [ ] Preflight checks pass
  - [ ] Resources created
  - [ ] Permissions configured
  - [ ] Connections validated

- [ ] **Staging Pipeline**
  - [ ] Sample pipeline runs
  - [ ] Output in BigQuery
  - [ ] Archive verified
  - [ ] Pub/Sub events received

- [ ] **Performance**
  - [ ] Throughput >1000 rec/s
  - [ ] Latency <5 min
  - [ ] Cost <$0.01/rec

---

## Documentation Map

| Need | File |
|------|------|
| **Getting Started** | `QUICK_START_TESTING.md` |
| **Complete Reference** | `COMPLETE_TESTING_GUIDE.md` |
| **Manual Testing Details** | `MANUAL_TESTING_GUIDE.md` |
| **Architecture** | `TESTING_ARCHITECTURE.md` |
| **Implementation** | `TESTING_IMPLEMENTATION_SUMMARY.md` |
| **Checklist** | `TESTING_IMPLEMENTATION_CHECKLIST.md` |
| **File Index** | `FILE_INDEX.md` |

---

## Support

- **Setup Issues**: See `MANUAL_TESTING_GUIDE.md` → Setup section
- **Test Failures**: See `COMPLETE_TESTING_GUIDE.md` → Troubleshooting
- **GCP Problems**: Check GCP documentation and IAM permissions
- **Questions**: Review relevant guide, then contact data engineering team

---

**Last Updated:** December 27, 2025  
**Status:** Complete & Ready ✅

