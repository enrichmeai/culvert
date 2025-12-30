# Quick Start: GCP Deployment Testing

Get started with comprehensive testing for LOA Blueprint and GDW Core library deployment to GCP, with setup, manual testing, and automated testing options.

## Environment Setup (Local Development)

### Option 1: Automated Setup with Docker (Recommended)

```bash
cd blueprint/setup

# Start all services (Airflow, PostgreSQL, Redis, Emulators, Jupyter)
docker-compose up -d

# Wait for services to be healthy (2-3 minutes)
docker-compose ps

# Access services:
# - Airflow UI: http://localhost:8080 (admin/airflow)
# - Jupyter: http://localhost:8888
# - PostgreSQL: localhost:5432
# - Redis: localhost:6379
```

### Option 2: Manual Setup with Airflow

```bash
cd blueprint/setup

# Run the Airflow setup script
./setup_airflow.sh

# This will:
# - Create virtual environment
# - Install dependencies
# - Setup Airflow home
# - Configure database
# - Create admin user
# - Start Airflow services
```

### Option 3: Python Dependencies Only

```bash
cd blueprint
pip install -r setup/requirements-test.txt
pip install -r setup/requirements-dev.txt
pip install -r setup/requirements.txt
```

## 5-Minute Quick Start - Automated Testing

### 1. Install Test Dependencies

```bash
cd blueprint
pip install -r setup/requirements-test.txt
```

### 2. Run Local Tests (No GCP Required)

```bash
# Option A: Using the test runner script
./run_full_tests.sh --unit --integration --coverage

# Option B: Using pytest directly
pytest components/tests/unit/ -v --cov=components
pytest components/tests/integration/ -v -m "not requires_gcp"

# Expected: ~75 tests pass in ~8-10 minutes
```

### 3. View Coverage Report

```bash
# HTML report will be generated in htmlcov/
open htmlcov/index.html  # macOS
# or
xdg-open htmlcov/index.html  # Linux
```

## Next Steps

### For Local Development

```bash
# Run specific test
pytest blueprint/components/tests/unit/orchestration/test_dag_deployment.py -v

# Run with verbose output
pytest blueprint/components/tests/unit/ -vv

# Watch mode (requires pytest-watch)
ptw blueprint/components/tests/unit/ -- -v
```

### For Staging Deployment

```bash
# Set up staging GCP credentials
export GCP_TEST_PROJECT="my-staging-project"
export GCP_TEST_REGION="us-central1"
export GCP_TEST_BUCKET="my-staging-bucket"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# Run staging tests
./run_full_tests.sh --staging

# Or manually
pytest blueprint/components/tests/integration/test_gcp_deployment.py -v -m requires_gcp
```

### For Performance Testing

```bash
# Run performance benchmarks
pytest blueprint/components/tests/performance/ -v --benchmark-only

# Run chaos engineering tests
pytest blueprint/components/tests/chaos/ -v
```

## Test Files Created

### Core Test Files

1. **conftest_gcp.py** - GCP service fixtures and mocks
   - BigQuery client mock
   - GCS client mock
   - Dataflow client mock
   - Pub/Sub client mock
   - Airflow context mock

2. **test_gcp_deployment.py** - GCP deployment validation
   - BigQuery schema validation
   - GCS bucket configuration
   - Dataflow template validation
   - Pub/Sub configuration
   - Service account permissions
   - Network configuration

3. **test_gcp_clients.py** - GCP client integration tests
   - BigQuery operations
   - GCS operations
   - Dataflow operations
   - Pub/Sub operations
   - Error handling
   - Client initialization

4. **test_dag_deployment.py** - DAG deployment validation
   - DAG creation and parsing
   - Task definition and configuration
   - Task dependencies
   - Retry and timeout configuration
   - Error handling
   - Parameter validation
   - Dataflow integration
   - Sensor configuration

### Test Support Files

5. **requirements-test.txt** - Test dependencies
   - pytest and plugins
   - Mocking libraries
   - GCP client libraries
   - Code quality tools
   - Performance profiling

6. **run_full_tests.sh** - Enhanced test runner
   - Local testing (unit + integration)
   - Staging deployment testing
   - Performance testing
   - HTML report generation
   - Parallel execution support

7. **gcp-deployment-tests.yml** - GitHub Actions CI/CD
   - Unit tests on every PR
   - Integration tests on every PR
   - Code quality checks
   - Security scanning
   - Staging tests on main branch
   - Nightly performance tests

8. **GCP_DEPLOYMENT_TESTING_GUIDE.py** - Python testing guide
   - Runnable test phases
   - Local, staging, and production testing
   - Performance and chaos testing

9. **COMPLETE_TESTING_GUIDE.md** - Complete documentation
   - Testing strategy overview
   - Setup instructions
   - Test execution guide
   - Troubleshooting
   - Best practices

## Test Coverage

### Unit Tests (Local)
- ✅ DAG creation and parsing (6 tests)
- ✅ Task definition and configuration (3 tests)
- ✅ Task dependencies (4 tests)
- ✅ Retry and timeout configuration (4 tests)
- ✅ Error handling (2 tests)
- ✅ Parameter validation (5 tests)
- ✅ Dataflow integration (3 tests)
- ✅ Sensor configuration (2 tests)

### Integration Tests (Mocked GCP)
- ✅ BigQuery client operations (5 tests)
- ✅ GCS client operations (6 tests)
- ✅ Dataflow client operations (4 tests)
- ✅ Pub/Sub client operations (3 tests)
- ✅ Error handling (5 tests)
- ✅ Client initialization (5 tests)

### Deployment Tests (Real GCP - Staging)
- ✅ BigQuery deployment validation (4 tests)
- ✅ GCS deployment validation (5 tests)
- ✅ Dataflow deployment validation (3 tests)
- ✅ Pub/Sub deployment validation (2 tests)
- ✅ Service account configuration (2 tests)
- ✅ Network configuration (3 tests)
- ✅ Health checks (3 tests)

**Total: 75+ tests**

## Common Commands

### Run All Tests
```bash
./run_full_tests.sh --full --coverage --report
```

### Run Specific Test Type
```bash
# Unit tests only
pytest blueprint/components/tests/unit/ -v

# Integration tests only
pytest blueprint/components/tests/integration/ -v -m "not requires_gcp"

# DAG tests only
pytest blueprint/components/tests/unit/orchestration/test_dag_deployment.py -v
```

### Generate Reports
```bash
# Coverage report
pytest --cov=blueprint/components --cov-report=html

# Open HTML report
open htmlcov/index.html
```

### Debug Tests
```bash
# Verbose output
pytest -vv blueprint/components/tests/unit/

# Show print statements
pytest -s blueprint/components/tests/unit/

# Stop on first failure
pytest -x blueprint/components/tests/unit/

# Drop into debugger on failure
pytest --pdb blueprint/components/tests/unit/
```

## Expected Test Execution Times

| Test Type | Count | Time | Notes |
|-----------|-------|------|-------|
| Unit Tests | 40+ | 1-2 min | No external dependencies |
| Integration (Mocked) | 20+ | 2-3 min | Mocked GCP services |
| DAG Tests | 15+ | 1 min | Airflow DAG validation |
| Code Quality | - | 2-3 min | Linting, formatting, typing |
| **Local Total** | **75+** | **8-10 min** | **Fast feedback** |
| Staging Tests | 10+ | 5-10 min | Real GCP services |
| Performance Tests | 5+ | 5-10 min | Benchmarks |
| **Full Suite** | **90+** | **30-40 min** | **Complete validation** |

## Continuous Integration

Tests run automatically on:
- ✅ Every pull request (unit + integration + code quality)
- ✅ Every push to main (+ staging deployment tests)
- ✅ Nightly schedule (+ performance tests)
- ✅ On-demand (via commit message: `[performance]`)

## Troubleshooting

### Tests fail with "No module named 'google.cloud'"

```bash
# Reinstall test dependencies
pip install -r blueprint/setup/requirements-test.txt --force-reinstall
```

### Tests timeout

```bash
# Increase timeout
pytest --timeout=300 blueprint/components/tests/
```

### Permission denied errors

```bash
# Verify GCP credentials
gcloud auth application-default print-access-token > /dev/null && \
  echo "✅ Credentials OK" || echo "❌ Credentials failed"
```

## Next Steps

1. **Read the complete guide:**
   ```bash
   cat COMPLETE_TESTING_GUIDE.md
   ```

2. **Set up staging deployment:**
   Follow instructions in [Staging Deployment Testing](#for-staging-deployment) section

3. **Configure CI/CD:**
   Add `GCP_STAGING_CREDENTIALS` secret to GitHub

4. **Deploy to production:**
   Follow deployment checklist in main documentation

## Support

For issues or questions:
1. Check [COMPLETE_TESTING_GUIDE.md](COMPLETE_TESTING_GUIDE.md) troubleshooting section
2. Review test output and error messages
3. Run tests with `-vv` flag for detailed output
4. Check pytest documentation: https://docs.pytest.org/


