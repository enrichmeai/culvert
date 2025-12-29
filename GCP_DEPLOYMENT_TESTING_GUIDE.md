# GCP Deployment Testing Guide

Complete testing strategy for deploying the LOA Blueprint and GDW Data Core library to Google Cloud Platform, including setup, manual testing, and automated validation.

## Table of Contents

1. [Overview](#overview)
2. [Environment Setup](#environment-setup)
3. [Manual Testing](#manual-testing)
4. [Automated Testing](#automated-testing)
5. [Staging Deployment](#staging-deployment)
6. [Production Validation](#production-validation)
7. [CI/CD Pipeline](#cicd-pipeline)
8. [Troubleshooting](#troubleshooting)
9. [Best Practices](#best-practices)

## Overview

The testing strategy is organized into phases:

| Phase | Duration | Scope | Environment |
|-------|----------|-------|-------------|
| **Environment Setup** | 5-10 min | Infrastructure provisioning | Local/GCP |
| **Local Unit Tests** | 2 min | Core logic with mocked GCP | Local machine |
| **Local Integration Tests** | 5 min | Component integration with mocks | Local machine |
| **Manual Pipeline Tests** | 15-30 min | End-to-end validation | Local/Staging |
| **Staging Deployment Tests** | 15 min | GCP service validation | GCP staging project |
| **Performance Tests** | 10 min | Throughput, latency, cost | GCP staging project |
| **Production Health Checks** | 5 min | Read-only validation | GCP production project |

### Test Pyramid

```
         Production Validation (Read-Only)
        ┌──────────────────────────────┐
        │                              │
        │  5 tests (Health checks)     │
        └──────────────────────────────┘
              Performance Tests
        ┌──────────────────────────────┐
        │                              │
        │  20 tests (Benchmarks)       │
        └──────────────────────────────┘
       Staging Deployment Tests
    ┌──────────────────────────────┐
    │                              │
    │  30 tests (GCP integration)  │
    └──────────────────────────────┘
    Manual Testing (DAGs, Pipelines)
  ┌────────────────────────────────┐
  │                                │
  │  Airflow DAGs, Data Flow       │
  └────────────────────────────────┘
    Integration Tests (Mocked)
  ┌────────────────────────────────┐
  │                                │
  │  40 tests (Mocked services)    │
  └────────────────────────────────┘
         Unit Tests
    ┌────────────────────┐
    │                    │
    │  100+ tests        │
    └────────────────────┘
```

## Environment Setup

### Prerequisites

```bash
# Install Python 3.9+
python3 --version  # >= 3.9

# Install Docker & Docker Compose (for full stack)
docker --version
docker-compose --version

# For GCP testing
gcloud --version
```

### Option 1: Docker Setup (Recommended - Full Stack)

Start complete isolated environment with all services:

```bash
cd blueprint/setup

# Start all services
docker-compose up -d

# Wait for services (2-3 minutes)
docker-compose ps

# Verify services are healthy
docker-compose logs -f airflow-webserver
```

**Services Available:**
- Airflow WebUI: http://localhost:8080 (admin/airflow)
- PostgreSQL: localhost:5432 (metadata database)
- Redis: localhost:6379 (caching)
- BigQuery Emulator: localhost:9050/9060
- Pub/Sub Emulator: localhost:8085
- Jupyter Lab: http://localhost:8888

### Option 2: Automated Airflow Setup

```bash
cd blueprint/setup

# Run Airflow setup script (handles all configuration)
./setup_airflow.sh

# Script will:
# - Create virtual environment
# - Install dependencies
# - Setup PostgreSQL backend
# - Initialize Airflow database
# - Create admin user
# - Start webserver and scheduler
```

### Option 3: Manual Python Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r blueprint/setup/requirements.txt
pip install -r blueprint/setup/requirements-dev.txt
pip install -r blueprint/setup/requirements-test.txt

# Install local packages
pip install -e blueprint
pip install -e gdw_data_core

# Verify installation
python -c "import blueprint; import gdw_data_core; print('✓ Installation successful')"
```

## Local Testing

### Prerequisites

```bash
# Install Python 3.9+
python3 --version  # >= 3.9

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install test dependencies
pip install -r blueprint/setup/requirements-test.txt
```

### Unit Tests

Test core logic and DAG definitions with mocked GCP services.

```bash
# Run all unit tests
pytest blueprint/components/tests/unit/ -v --cov=blueprint/components

# Run specific test file
pytest blueprint/components/tests/unit/orchestration/test_dag_deployment.py -v

# Run with detailed output
pytest blueprint/components/tests/unit/ -vv --tb=long

# Run specific test
pytest blueprint/components/tests/unit/orchestration/test_dag_deployment.py::TestDAGCreationAndParsing::test_dag_creation_succeeds -v

# Run with coverage report
pytest blueprint/components/tests/unit/ \
  --cov=blueprint/components \
  --cov-report=html \
  --cov-report=term-missing
```

**Coverage Targets:**
- Core logic: 80%+
- Error handling: 90%+
- DAG definitions: 95%+

### Integration Tests (Mocked)

Test component interactions without external resources.

```bash
# Run all integration tests with mocked services
pytest blueprint/components/tests/integration/ -v -m "not requires_gcp"

# Run GCP client integration tests
pytest blueprint/components/tests/integration/test_gcp_clients.py -v

# Run DAG validation tests
pytest blueprint/components/tests/unit/orchestration/test_dag_deployment.py -v
```

### Quick Local Test Run

```bash
# Run all local tests (unit + integration with mocks)
python blueprint/GCP_DEPLOYMENT_TESTING_GUIDE.py --phase local

# Or use the shell script
chmod +x blueprint/run_full_tests.sh
./blueprint/run_full_tests.sh --unit --integration --coverage --report
```

Expected output:
```
✅ Local unit tests passed!
✅ Local integration tests passed!
✅ DAG tests passed!

Coverage report: htmlcov/index.html
```

## Manual Testing

### Airflow DAG Testing

After setting up your environment (Docker or Airflow setup), test DAGs manually:

```bash
# Access Airflow UI
open http://localhost:8080

# In the UI:
# 1. Navigate to DAGs tab
# 2. Find your DAG (e.g., loa_applications_migration)
# 3. Click to view DAG structure
# 4. Verify tasks and dependencies are correct
# 5. Trigger DAG with: "Trigger DAG" button
# 6. Monitor execution in real-time
```

**Command-line DAG Validation:**

```bash
# List all DAGs
airflow dags list

# Test DAG parsing
airflow dags test loa_applications_migration 2025-01-01

# Show DAG structure
airflow dags show loa_applications_migration

# Validate connections
airflow connections test gcp_default

# Check variables
airflow variables list

# Check configuration
airflow config list
```

### Local Pipeline Testing

Use the provided tools for testing:

```bash
cd blueprint

# Run local pipeline test
python tools/testing/test_loa_local.py

# Deploy locally for testing
python tools/testing/deploy_local.py

# Generate test data
python tools/testing/generate_output.py --output /tmp/test_data.csv
```

### Data Quality Validation

```bash
# Validate schema against sample data
python components/validation/schema_validator.py /tmp/test_data.csv

# Run data quality checks
python components/validation/data_quality.py /tmp/test_data.csv

# View validation results
cat /tmp/validation_results.json
```

### Interactive Testing with Jupyter

```bash
# Start Jupyter
jupyter lab  # or access at http://localhost:8888 if using Docker

# Create a test notebook:
# - Import components
# - Load sample data
# - Test transformations
# - Validate outputs
```

## Staging Deployment Testing

### Setup Staging Environment

1. Create GCP staging project
2. Set up GCS bucket, BigQuery dataset, Dataflow templates
3. Create service account with appropriate permissions

### Configuration

```bash
# Set environment variables
export GCP_TEST_PROJECT="my-staging-project"
export GCP_TEST_REGION="us-central1"
export GCP_TEST_BUCKET="my-staging-bucket"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# Verify configuration
gcloud config set project $GCP_TEST_PROJECT
gcloud auth application-default print-access-token > /dev/null && \
  echo "✅ GCP authentication successful" || \
  echo "❌ GCP authentication failed"
```

### Run Staging Tests

```bash
# Validate GCP deployment configuration
pytest blueprint/components/tests/integration/test_gcp_deployment.py -v -m requires_gcp

# Test GCP client integration
pytest blueprint/components/tests/integration/test_gcp_clients.py -v -m integration

# Or run all staging tests
python blueprint/GCP_DEPLOYMENT_TESTING_GUIDE.py --phase staging
```

### Manual Pipeline Run

1. **Upload sample data:**
   ```bash
   gsutil cp tests/data/sample_applications.csv gs://$GCP_TEST_BUCKET/raw/sample_
   ```

2. **Trigger DAG:**
   ```bash
   gcloud composer environments run my-composer-env \
     --location us-central1 \
     dags trigger -- loa_applications_migration
   ```

3. **Monitor execution:**
   ```bash
   gcloud composer environments run my-composer-env \
     --location us-central1 \
     dags list-runs -- loa_applications_migration
   ```

4. **Validate output:**
   ```bash
   # Check BigQuery
   bq query "SELECT COUNT(*) FROM \`project:dataset.applications\` WHERE DATE(ingestion_timestamp) = CURRENT_DATE()"
   
   # Check archive
   gsutil ls gs://$GCP_TEST_BUCKET/archive/
   
   # Check Pub/Sub
   gcloud pubsub subscriptions pull loa-completion-subscription --auto-ack
   ```

## Production Validation

### Read-Only Health Checks

```bash
# Check BigQuery dataset
bq ls -a

# Check table schemas
bq show project:dataset.applications

# Query recent data
bq query --use_legacy_sql=false "SELECT COUNT(*) FROM \`project:dataset.applications\` LIMIT 1"

# Check GCS bucket
gsutil ls -h gs://production-bucket/

# Check Dataflow templates
gcloud dataflow templates list --region=$GCP_REGION

# Check Pub/Sub topics
gcloud pubsub topics list

# Check recent logs
gcloud logging read "resource.type=cloud_composer_environment" --limit 50 --format=json
```

### Performance Benchmarks

```bash
# Run performance tests
pytest blueprint/components/tests/performance/ -v --benchmark-only

# Performance targets:
# - Throughput: >1000 records/second
# - Latency: <5 minutes for 10K records
# - Cost: <$0.01 per record
```

### Chaos Engineering Tests

```bash
# Run chaos tests to validate error handling
pytest blueprint/components/tests/chaos/ -v

# Scenarios tested:
# - Network failures
# - Service timeouts
# - Quota exceeded
# - Malformed data
# - Out of memory
```

## CI/CD Pipeline

### GitHub Actions Workflow

The `.github/workflows/gcp-deployment-tests.yml` file defines automated testing:

1. **Unit Tests** - Run on every push/PR (2 min)
2. **Integration Tests** - Run on every push/PR (5 min)
3. **DAG Tests** - Run on every push/PR (2 min)
4. **Code Quality** - Run on every push/PR (5 min)
5. **Security Scan** - Run on every push/PR (5 min)
6. **Performance Tests** - Run nightly + on-demand (15 min)
7. **Staging Tests** - Run on main branch push (20 min)

### Triggering Tests

```bash
# Run unit tests on PR
git push origin feature-branch

# Run performance tests
git commit --allow-empty -m "[performance] Run performance tests"

# Run staging tests (on main branch)
git push origin main
```

### Required Secrets (GitHub)

For staging deployment tests to work, add these secrets to your GitHub repository:

```
GCP_STAGING_PROJECT     = your-staging-project
GCP_STAGING_BUCKET      = your-staging-bucket
GCP_STAGING_CREDENTIALS = {service-account-json-content}
```

## Test Files Reference

### Unit Tests

| File | Tests | Coverage |
|------|-------|----------|
| `test_dag_deployment.py` | DAG creation, task dependencies, configuration | 95% |
| `test_validation.py` | Input validation, error handling | 90% |
| `test_data_quality.py` | Data quality checks | 85% |

### Integration Tests

| File | Tests | Scope |
|------|-------|-------|
| `test_gcp_clients.py` | BigQuery, GCS, Dataflow, Pub/Sub clients | Mocked services |
| `test_gcp_deployment.py` | GCP resource validation | Real GCP services |
| `conftest_gcp.py` | GCP fixtures and mocks | Fixtures |

### Performance Tests

| File | Benchmarks | Targets |
|------|-----------|---------|
| `test_performance_benchmarks.py` | Throughput, latency, memory | >1000 rec/s, <5 min, <$0.01 |

## Troubleshooting

### Common Issues

#### 1. "No such file or directory: requirements-test.txt"

**Solution:**
```bash
cd blueprint
pip install -r setup/requirements-test.txt
```

#### 2. "GCP_TEST_PROJECT environment variable not set"

**Solution:**
```bash
export GCP_TEST_PROJECT="your-staging-project"
```

#### 3. "GOOGLE_APPLICATION_CREDENTIALS file not found"

**Solution:**
```bash
# Create service account in GCP
gcloud iam service-accounts create test-runner --display-name="Test Runner"
gcloud iam service-accounts keys create service-account.json \
  --iam-account=test-runner@$GCP_TEST_PROJECT.iam.gserviceaccount.com

export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

#### 4. "Permission denied" errors

**Solution:**
Grant required permissions to service account:
```bash
gcloud projects add-iam-policy-binding $GCP_TEST_PROJECT \
  --member="serviceAccount:test-runner@$GCP_TEST_PROJECT.iam.gserviceaccount.com" \
  --role="roles/dataflow.admin"

gcloud projects add-iam-policy-binding $GCP_TEST_PROJECT \
  --member="serviceAccount:test-runner@$GCP_TEST_PROJECT.iam.gserviceaccount.com" \
  --role="roles/bigquery.admin"

gcloud projects add-iam-policy-binding $GCP_TEST_PROJECT \
  --member="serviceAccount:test-runner@$GCP_TEST_PROJECT.iam.gserviceaccount.com" \
  --role="roles/storage.admin"
```

#### 5. "Tests timing out"

**Solution:**
Increase timeout or check for service issues:
```bash
# Increase timeout for specific test
pytest --timeout=300 blueprint/components/tests/integration/

# Check GCP service health
gcloud services list --enabled
```

## Best Practices

### 1. Local Development

```bash
# Always run unit tests before committing
pytest blueprint/components/tests/unit/ -v

# Use pytest watch for continuous testing
pytest-watch blueprint/components/tests/unit/ -- -v

# Check coverage regularly
pytest --cov=blueprint/components --cov-report=html
```

### 2. Testing with GCP Services

```bash
# Always use staging project for GCP tests
export GCP_TEST_PROJECT="staging-only-project"

# Never run tests against production
unset GCP_TEST_PROJECT  # Disable GCP tests to be safe

# Clean up test resources
gsutil -m rm -r gs://staging-bucket/test-runs/
```

### 3. CI/CD

```bash
# Keep test stages fast
# Unit tests: < 5 min
# Integration tests: < 10 min
# Staging tests: < 20 min

# Run tests in parallel where possible
pytest -n auto  # Parallel execution with pytest-xdist

# Generate reports for analysis
pytest --cov --cov-report=html --cov-report=term-missing
```

### 4. Test Data

```python
# Use synthetic data for testing
from faker import Faker
faker = Faker()

# Never use production data in tests
# Always use staging/test GCP projects
# Clean up test data after tests
```

### 5. Monitoring

```bash
# Check test execution time
pytest --durations=10

# Monitor GCP resource usage during tests
watch -n 1 'gcloud compute instances list'

# Review logs after tests
gcloud logging read --limit=50 --format=json | jq
```

## Performance Targets

### Throughput
- **Target:** > 1,000 records/second
- **Validation:** `test_performance_benchmarks.py`

### Latency
- **Target:** < 5 minutes for 10,000 records
- **Validation:** Dataflow job monitoring

### Cost
- **Target:** < $0.01 per record
- **Validation:** GCP billing API

### Error Rate
- **Target:** < 0.1%
- **Validation:** Application logs

## Deployment Checklist

Before deploying to production:

- [ ] All unit tests pass (100%)
- [ ] All integration tests pass (100%)
- [ ] All DAG tests pass (100%)
- [ ] Code quality checks pass
- [ ] Security scan passes (no critical issues)
- [ ] Performance benchmarks meet targets
- [ ] Chaos tests pass (resilience validated)
- [ ] Staging deployment tests pass (100%)
- [ ] Sample pipeline runs successfully
- [ ] Production health checks pass
- [ ] Team review and approval

## Additional Resources

- [Apache Beam Testing Guide](https://beam.apache.org/documentation/runners/dataflow/)
- [Airflow Testing Guide](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html)
- [Google Cloud Testing Best Practices](https://cloud.google.com/docs/authentication/best-practices)
- [pytest Documentation](https://docs.pytest.org/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)


