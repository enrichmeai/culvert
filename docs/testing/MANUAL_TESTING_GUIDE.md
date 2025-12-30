# 🧪 Manual Testing Guide - LOA Blueprint & GDW Core

Complete guide for manual testing using existing setup and tools, combined with automated testing.

## Overview

The project includes multiple layers of setup and testing capabilities:

1. **Setup Layer** - Automated environment setup
2. **Tools Layer** - GCP deployment, migration, and testing tools  
3. **Testing Layer** - Automated pytest suite (75+ tests)
4. **Manual Testing** - Local and staging validation

---

## Part 1: Local Environment Setup

### Option 1: Docker Setup (Recommended - Full Stack)

The Docker setup provides complete isolated environment with all services:

```bash
cd blueprint/setup

# Start all services
docker-compose up -d

# Wait for services to initialize (2-3 minutes)
docker-compose ps

# Check service health
docker-compose logs -f airflow-webserver
```

**Services Started:**
- **Airflow WebUI**: http://localhost:8080 (admin/airflow)
- **PostgreSQL**: localhost:5432 (airflow/airflow)
- **Redis**: localhost:6379
- **BigQuery Emulator**: localhost:9050/9060
- **Pub/Sub Emulator**: localhost:8085
- **Jupyter Lab**: http://localhost:8888 (optional)

**Verify Services:**
```bash
# Check all containers are running
docker-compose ps

# View Airflow UI
open http://localhost:8080

# Check PostgreSQL connection
psql -h localhost -U airflow -d airflow -c "SELECT 1"

# Test Redis
redis-cli ping

# Check BigQuery emulator
curl http://localhost:9050/
```

### Option 2: Airflow Setup (Standalone)

```bash
cd blueprint/setup

# Run setup script
./setup_airflow.sh

# This will:
# ✓ Create virtual environment (airflow-venv)
# ✓ Install Apache Airflow 2.6.0
# ✓ Install Google Cloud Provider
# ✓ Setup PostgreSQL backend
# ✓ Create admin user
# ✓ Initialize database
# ✓ Start Airflow webserver and scheduler

# After script completes:
# Access Airflow UI: http://localhost:8080
```

### Option 3: Manual Setup (Python Only)

```bash
# Install all dependencies
cd blueprint
pip install -r setup/requirements.txt
pip install -r setup/requirements-dev.txt
pip install -r setup/requirements-test.txt

# Install GDW Core library
cd ../gdw_data_core
pip install -e .

# Go back to blueprint
cd ../blueprint
pip install -e .
```

---

## Part 2: Manual Testing with Local Environment

### 1. Airflow DAG Testing

```bash
# Start Airflow (if not using Docker)
airflow webserver --port 8080 &
airflow scheduler &

# Wait for web UI to be ready
sleep 5

# Access Airflow UI
open http://localhost:8080

# In Airflow UI:
# 1. Navigate to DAGs tab
# 2. Find your DAG (e.g., loa_applications_migration)
# 3. Click on it
# 4. Verify DAG structure (tasks, dependencies)
# 5. Trigger DAG manually
# 6. Monitor execution
```

**Manual DAG Validation:**
```bash
# Parse DAG without running
airflow dags list

# Test DAG parsing
airflow dags test loa_applications_migration 2025-01-01

# Check DAG structure
airflow dags show loa_applications_migration

# Validate connections
airflow connections test gcp_default

# Check variables
airflow variables list
```

### 2. Local Pipeline Testing

```bash
# Using the local test script
python blueprint/tools/testing/test_loa_local.py

# Or run with local deployment helper
python blueprint/tools/testing/deploy_local.py

# Generate test data
python blueprint/tools/testing/generate_output.py

# This creates sample data in:
# - /tmp/loa_data_input/
# - /tmp/loa_data_output/
```

### 3. Data Validation Tests

```bash
# Test with sample data
cd blueprint

# Generate test data
python tools/testing/generate_output.py --output /tmp/test_data.csv

# Validate schema
python components/validation/schema_validator.py /tmp/test_data.csv

# Run data quality checks
python components/validation/data_quality.py /tmp/test_data.csv

# Check validation results
cat /tmp/validation_results.json
```

### 4. Jupyter Notebook Testing

Access Jupyter for interactive testing:

```bash
# If using Docker
docker-compose exec jupyter jupyter lab --ip=0.0.0.0 --allow-root

# Or if installed locally
jupyter lab

# Navigate to: http://localhost:8888

# Create new notebook and test:
# - Import components
# - Load sample data
# - Test transformations
# - Validate outputs
```

---

## Part 3: GCP Setup and Deployment Tools

### Preflight Checks

```bash
# Verify GCP readiness
cd blueprint/tools/gcp

./preflight_check.sh

# Checks:
# ✓ GCP SDK installed
# ✓ Authentication configured
# ✓ Project ID set
# ✓ Required APIs enabled
# ✓ Service accounts available
# ✓ Quotas sufficient
```

### Setup Dependencies

```bash
cd blueprint/tools/gcp

# Install all Python dependencies
./setup-dependencies.sh

# This installs:
# - google-cloud-storage
# - google-cloud-bigquery
# - google-cloud-dataflow
# - apache-beam[gcp]
# - airflow-providers-google
```

### GCP Project Setup

```bash
cd blueprint/tools/gcp

# Main setup script (orchestrator)
./setupanddeployongcp.sh

# Interactive prompts will ask for:
# - GCP Project ID
# - Region (us-central1, etc.)
# - Environment (dev/staging/prod)
# - Service account email
# - Dataflow template path

# This will:
# ✓ Create GCS buckets
# ✓ Create BigQuery datasets and tables
# ✓ Deploy Dataflow templates
# ✓ Create Pub/Sub topics
# ✓ Configure service accounts
# ✓ Setup IAM permissions
# ✓ Configure Airflow connections
```

### Manual GCP Testing

```bash
cd blueprint/tools/gcp

# Test individual components

# 1. Test BigQuery connection
gcloud bigquery datasets list
bq ls

# 2. Test GCS access
gsutil ls

# 3. Test Pub/Sub
gcloud pubsub topics list

# 4. Test service account permissions
gcloud projects get-iam-policy PROJECT_ID

# 5. Trigger a test pipeline
./trigger-pipeline.sh loa-test-job

# 6. Monitor Dataflow job
gcloud dataflow jobs list --region=us-central1
```

### Cloud Function Deployment

```bash
cd blueprint/tools/gcp

# Deploy Cloud Functions
./deploy-cloud-function.sh

# Deploys:
# - Event trigger function
# - Validation function
# - Error handler function
```

### Dataflow Deployment

```bash
cd blueprint/tools/gcp

# Deploy Dataflow template
./deploy-dataflow.sh

# Or deploy manually:
gcloud dataflow flex-template build gs://bucket/templates/loa-template.json \
    --image-gcr-path "gcr.io/project/loa-template" \
    --sdk-language PYTHON \
    --flex-template-base-image PYTHON3
```

---

## Part 4: Automated Testing Suite

### Quick Test Run

```bash
cd blueprint

# Install test dependencies
pip install -r setup/requirements-test.txt

# Run all local tests (no GCP required)
./run_full_tests.sh --full --coverage --report

# Expected: 75+ tests pass in 8-10 minutes
```

### Specific Test Phases

```bash
# Unit tests only
./run_full_tests.sh --unit

# Integration tests (mocked)
./run_full_tests.sh --integration

# DAG tests
pytest components/tests/unit/orchestration/test_dag_deployment.py -v

# GCP client tests
pytest components/tests/integration/test_gcp_clients.py -v
```

### Coverage Reports

```bash
# Generate coverage report
pytest components/tests/ --cov=components --cov-report=html

# View HTML report
open htmlcov/index.html
```

---

## Part 5: Staging Deployment Testing

### Setup Staging Environment

```bash
# 1. Set up GCP project
export GCP_PROJECT="staging-project"
export GCP_REGION="us-central1"

# 2. Create service account
gcloud iam service-accounts create loa-staging-sa \
    --project=$GCP_PROJECT

# 3. Grant permissions
gcloud projects add-iam-policy-binding $GCP_PROJECT \
    --member="serviceAccount:loa-staging-sa@$GCP_PROJECT.iam.gserviceaccount.com" \
    --role="roles/dataflow.admin"

# 4. Create and download key
gcloud iam service-accounts keys create staging-key.json \
    --iam-account=loa-staging-sa@$GCP_PROJECT.iam.gserviceaccount.com
```

### Run Staging Tests

```bash
cd blueprint

# Set environment
export GCP_TEST_PROJECT="staging-project"
export GCP_TEST_REGION="us-central1"
export GCP_TEST_BUCKET="staging-bucket"
export GOOGLE_APPLICATION_CREDENTIALS="./staging-key.json"

# Run staging tests
./run_full_tests.sh --staging

# Or use Python runner
python GCP_DEPLOYMENT_TESTING_GUIDE.py --phase staging
```

### Manual Pipeline Run on Staging

```bash
# 1. Upload sample data
gsutil cp tests/data/sample_applications.csv \
    gs://$GCP_TEST_BUCKET/raw/sample_

# 2. Trigger DAG in Cloud Composer
gcloud composer environments run my-composer-env \
    --location $GCP_TEST_REGION \
    dags trigger -- loa_applications_migration

# 3. Monitor execution
gcloud composer environments run my-composer-env \
    --location $GCP_TEST_REGION \
    dags list-runs -- loa_applications_migration

# 4. Check BigQuery output
bq query "SELECT COUNT(*) FROM \`$GCP_TEST_PROJECT:dataset.applications\` WHERE DATE(ingestion_timestamp) = CURRENT_DATE()"

# 5. Verify archive
gsutil ls gs://$GCP_TEST_BUCKET/archive/

# 6. Check Pub/Sub events
gcloud pubsub subscriptions pull loa-completion-subscription --auto-ack
```

---

## Part 6: Migration Testing

The bulk migration tool allows testing data migration workflows:

```bash
cd blueprint/tools/migration

# Example migration with configuration
python bulk_migration_tool.py \
    --config migration_config_examples.yaml \
    --source bigquery \
    --target bigquery \
    --dry-run  # Test without actual migration

# Create custom config
cat > my_migration_config.yaml << EOF
source:
  type: bigquery
  project: source-project
  dataset: source_dataset
  table: source_table

target:
  type: bigquery
  project: target-project
  dataset: target_dataset
  table: target_table

transformation:
  type: full_load  # or incremental
  batch_size: 10000

validation:
  enabled: true
  check_row_count: true
  check_data_quality: true
EOF

# Run migration
python bulk_migration_tool.py --config my_migration_config.yaml
```

---

## Part 7: Testing Workflow

### Complete Testing Sequence

```bash
# Step 1: Local environment setup
cd blueprint/setup
docker-compose up -d  # or ./setup_airflow.sh

# Step 2: Verify environment
docker-compose ps
open http://localhost:8080

# Step 3: Run manual tests
cd ../
python tools/testing/test_loa_local.py

# Step 4: Run automated tests
./run_full_tests.sh --full --coverage --report

# Step 5: Setup staging (if ready)
cd tools/gcp
./preflight_check.sh
./setupanddeployongcp.sh

# Step 6: Run staging tests
cd ../../
export GCP_TEST_PROJECT="staging-project"
./run_full_tests.sh --staging

# Step 7: Verify results
open htmlcov/index.html
```

---

## Part 8: Troubleshooting

### Common Issues

**Docker Services Won't Start**
```bash
# Check logs
docker-compose logs -f

# Rebuild containers
docker-compose up -d --build

# Reset everything
docker-compose down -v
docker-compose up -d
```

**Module Import Errors**
```bash
# Install in editable mode
cd blueprint && pip install -e .
cd ../gdw_data_core && pip install -e .

# Verify Python path
python -c "import blueprint; import gdw_data_core; print('OK')"
```

**Test Collection Errors**
```bash
# Check pytest configuration
cat pytest.ini

# Run with verbose output
pytest -vv components/tests/

# Check for invalid files
find components/tests -name "*.py" -exec python -m py_compile {} \;
```

**GCP Authentication Issues**
```bash
# Verify credentials
gcloud auth list
gcloud config list

# Set project
gcloud config set project $GCP_PROJECT

# Test API access
gcloud compute zones list
```

---

## Part 9: Manual Testing Checklist

### Pre-Deployment Verification

- [ ] **Local Environment**
  - [ ] Docker/Airflow setup successful
  - [ ] All services healthy
  - [ ] Airflow UI accessible
  - [ ] Jupyter accessible (if needed)

- [ ] **Local Testing**
  - [ ] Sample data generated successfully
  - [ ] Schema validation passes
  - [ ] Data quality checks pass
  - [ ] DAG tests pass

- [ ] **Automated Testing**
  - [ ] Unit tests pass (40+)
  - [ ] Integration tests pass (20+)
  - [ ] DAG tests pass (15+)
  - [ ] Coverage 80%+

- [ ] **GCP Staging Setup**
  - [ ] Project created
  - [ ] APIs enabled
  - [ ] Service accounts configured
  - [ ] GCS/BigQuery/Dataflow ready
  - [ ] Preflight checks pass

- [ ] **Staging Testing**
  - [ ] Deployment validation passes
  - [ ] Sample pipeline runs successfully
  - [ ] Output in BigQuery verified
  - [ ] Performance acceptable

- [ ] **Production Ready**
  - [ ] All tests passing
  - [ ] Performance targets met
  - [ ] Chaos tests pass
  - [ ] Team review complete

---

## Quick Command Reference

```bash
# Start environment
docker-compose -f blueprint/setup/docker-compose.yml up -d

# Run all local tests
./blueprint/run_full_tests.sh --full --coverage --report

# Deploy to GCP
cd blueprint/tools/gcp && ./setupanddeployongcp.sh

# Monitor Airflow
open http://localhost:8080

# Check GCP deployment
gcloud dataflow jobs list --region=us-central1

# Generate test data
python blueprint/tools/testing/generate_output.py

# Run bulk migration
python blueprint/tools/migration/bulk_migration_tool.py --config config.yaml
```

---

## Additional Resources

- **Airflow Docs**: https://airflow.apache.org/docs/
- **Apache Beam**: https://beam.apache.org/documentation/
- **GCP Documentation**: https://cloud.google.com/docs
- **Docker Compose**: https://docs.docker.com/compose/
- **Pytest Documentation**: https://docs.pytest.org/

---

**Last Updated:** December 27, 2025  
**Status:** Complete and Ready for Use ✅


