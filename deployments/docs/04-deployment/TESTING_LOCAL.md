# 🧪 TESTING_LOCAL.md - Complete Local Testing Guide

**Purpose:** Comprehensive guide for running all tests locally without GCP  
**Created:** December 21, 2025  
**Updated:** January 2025  
**Status:** ✅ PRODUCTION-READY  

---

## 📋 TABLE OF CONTENTS

1. [Prerequisites](#-prerequisites)
2. [Test File Organization](#-test-file-organization)
3. [Running Each Test Type](#-running-each-test-type)
4. [Expected Output](#-expected-output)
5. [Complete Workflow](#-complete-workflow)
6. [Troubleshooting](#-troubleshooting)
7. [Next Steps](#-next-steps)

---

## 📂 TEST FILE ORGANIZATION

### Complete Test File Map

Your project has **16+ test files** organized strategically:

| Category | Location | Files | Purpose |
|----------|----------|-------|---------|
| **DAG Validation** | `/blueprint/` | test_airflow_locally.py | Validate Airflow DAG structure |
| **Local Testing** | `components/LOCAL_INTEGRATION/` | test_loa_local.py | Quick local tests (5 min) |
| **Local E2E Tests** | `components/tests/local/` | test_local_pipeline.py | Comprehensive local tests |
| **Unit Tests** | `components/tests/unit/` | 6 files, 95+ tests | Component-level tests |
| **Integration Tests** | `components/tests/integration/` | test_pipeline_end_to_end.py | Full pipeline tests |
| **Performance Tests** | `components/tests/performance/` | test_performance_benchmarks.py | Performance benchmarks |
| **Chaos Tests** | `components/tests/chaos/` | test_chaos_engineering.py | Resilience testing |
| **Fixtures** | `components/tests/` | conftest.py | Shared test fixtures |

### Test Organization Hierarchy

```
Fastest/Isolated ──────────────────── Most Complete/Integrated

Local Tests (5 min)                    E2E Tests (15 min)
└─ test_loa_local.py         └─ test_pipeline_end_to_end.py
└─ test_local_pipeline.py     └─ Docker compose setup
└─ No GCP, mocked services    └─ Full pipeline validation

Unit Tests (10-15 min)                Performance Tests
└─ components/tests/unit/     └─ test_performance_benchmarks.py
└─ 95+ tests                  └─ Stress testing
└─ Component isolation        └─ Chaos engineering

DAG Validation (1 min)
└─ test_airflow_locally.py
└─ No Airflow services needed
└─ Structure validation only
```

### When to Use Each Test

| Situation | Test File(s) | Time | Command |
|-----------|-------------|------|---------|
| **Quick development test** | LOCAL_INTEGRATION/test_loa_local.py | 5 min | `python3 components/LOCAL_INTEGRATION/test_loa_local.py` |
| **Validate DAG structure** | test_airflow_locally.py | 1 min | `python blueprint/testing/test_airflow_locally.py` |
| **Comprehensive local test** | tests/local/test_local_pipeline.py | 10 min | `pytest components/tests/local/ -v` |
| **All unit tests** | tests/unit/*.py | 10-15 min | `pytest components/tests/unit/ -v` |
| **Full integration test** | tests/integration/test_pipeline_end_to_end.py | 15-20 min | `pytest components/tests/integration/ -v` |
| **Run everything locally** | All tests | 30-45 min | `pytest components/tests/ -v` |
| **With coverage report** | All tests | 40-50 min | `pytest components/tests/ --cov` |

---

## ✅ PREREQUISITES

### 1. System Requirements

**Operating System:**
- macOS 10.15+
- Ubuntu 20.04+
- Windows 10+ (with WSL2)

**Processor & Memory:**
- CPU: 2+ cores recommended
- RAM: 8GB minimum, 16GB recommended
- Disk: 5GB available space

**Network:**
- Internet connection (for initial setup)
- No GCP credentials required for local testing

### 2. Python Version

**Required:** Python 3.9 or higher

**Check your version:**
```bash
python3 --version
# Expected: Python 3.9.x, 3.10.x, 3.11.x, or 3.12.x
```

**Install Python:**
```bash
# macOS (using Homebrew)
brew install python@3.11

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3.11 python3.11-venv

# Windows (download from python.org)
# https://www.python.org/downloads/
```

### 3. Virtual Environment Setup

**Create virtual environment:**
```bash
cd /path/to/blueprint
python3 -m venv venv
```

**Activate virtual environment:**
```bash
# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

**Verify activation:**
```bash
which python     # macOS/Linux
where python     # Windows

# Expected: /path/to/blueprint/venv/bin/python
```

### 4. Required Packages Installation

**Install all dependencies:**
```bash
# Core dependencies
pip install -r requirements.txt

# Development dependencies (testing, coverage, linting)
pip install -r requirements-dev.txt

# Verify installation
pip list | grep -E "pytest|apache-beam|google-cloud"
```

**Expected packages:**
```
apache-beam          2.49.0
google-cloud-bigquery 3.12.0
google-cloud-storage  2.10.0
google-cloud-pubsub   2.18.0
pytest                7.4.0
pytest-cov            4.1.0
pytest-mock           3.11.1
pandas                2.0.0
```

### 5. Docker Setup (Optional but Recommended)

Docker provides isolated local services (PostgreSQL, Redis).

**Install Docker:**
```bash
# macOS
brew install docker

# Ubuntu/Debian
sudo apt-get install docker.io docker-compose

# Windows
# Download Docker Desktop from https://www.docker.com/products/docker-desktop
```

**Verify Docker installation:**
```bash
docker --version
docker-compose --version

# Expected
# Docker version 24.0.0+
# Docker Compose version 2.0.0+
```

**Start Docker daemon:**
```bash
# macOS (already running in background)

# Ubuntu/Linux
sudo systemctl start docker

# Windows
# Docker Desktop starts automatically
```


---

## 🚀 RUNNING EACH TEST TYPE

### Test Type 1: Direct Python Tests (5 minutes)

**Purpose:** Test individual Python modules without pytest framework

**When to use:** Quick validation of single functions

**Command:**
```bash
cd blueprint

# Test a single module
python3 -c "from components.loa_common.validation import validate_ssn; print(validate_ssn('123-45-6789'))"

# Expected output
# []  # Empty list means valid (no errors)
```

**Test SSN Validation:**
```bash
python3 << 'EOF'
from components.loa_common.validation import validate_ssn

# Test valid SSN
valid_result = validate_ssn("123-45-6789")
print(f"Valid SSN result: {valid_result}")
assert len(valid_result) == 0, "Should have no errors"

# Test invalid SSN
invalid_result = validate_ssn("000-00-0000")
print(f"Invalid SSN result: {invalid_result}")
assert len(invalid_result) > 0, "Should have errors"

print("✅ All validation tests passed!")
EOF
```

**Expected Output:**
```
Valid SSN result: []
Invalid SSN result: [ValidationError(...)]
✅ All validation tests passed!
```

**Common Issues:**
```
Error: ModuleNotFoundError: No module named 'loa_common'
Fix: Make sure you're in the blueprint directory and venv is activated
```

### Test Type 2: Unit Tests with Pytest (10-15 minutes)

**Purpose:** Run unit tests for validation, data quality, error handling

**Command - Run all unit tests:**
```bash
cd blueprint
pytest components/tests/unit/ -v
```

**Output (first 5 lines):**
```
components/tests/unit/test_validation.py::TestValidateSsn::test_valid_ssn_with_hyphens PASSED
components/tests/unit/test_validation.py::TestValidateSsn::test_valid_ssn_without_hyphens PASSED
components/tests/unit/test_validation.py::TestValidateSsn::test_empty_ssn FAILED
...
```

**Command - Run specific test file:**
```bash
pytest components/tests/unit/test_validation.py -v
```

**Command - Run with coverage:**
```bash
pytest components/tests/unit/ -v --cov=components.loa_common --cov-report=html
```

**Output with coverage:**
```
components/tests/unit/test_validation.py::TestValidateSsn::test_valid_ssn_with_hyphens PASSED [50%]
components/tests/unit/test_validation.py::TestValidateSsn::test_empty_ssn FAILED [100%]

FAILED components/tests/unit/test_validation.py::TestValidateSsn::test_empty_ssn - assert...
===================== 1 failed, 9 passed in 0.34s ======================

Coverage report generated: ./htmlcov/index.html
```

**View coverage report:**
```bash
# Open in browser
open htmlcov/index.html          # macOS
xdg-open htmlcov/index.html      # Linux
start htmlcov/index.html         # Windows
```

**Command - Run quick subset (no output capture):**
```bash
pytest components/tests/unit/test_validation.py -v -s
```

**Expected Success Output:**
```
test_valid_ssn_with_hyphens PASSED
test_valid_ssn_without_hyphens PASSED
test_ssn_all_zeros PASSED
test_invalid_ssn_format PASSED

===================== 4 passed in 0.12s ======================
```

**Time Estimates:**
- test_validation.py: ~1-2 seconds
- test_data_factory.py: ~3-5 seconds
- test_audit.py: ~2-3 seconds
- All unit tests: ~10-15 seconds

### Test Type 3: DirectRunner Dataflow Tests (15-30 minutes)

**Purpose:** Test Apache Beam pipeline logic using DirectRunner (local execution)

**Prerequisites:**
```bash
# Ensure Dataflow is installed
pip install apache-beam[gcp]==2.49.0
```

**Command - Run with DirectRunner:**
```bash
cd blueprint

# Test file location
python3 components/loa_pipelines/test_pipeline.py \
    --runner DirectRunner \
    --input_file components/tests/data/applications_sample.csv \
    --output_prefix /tmp/pipeline_output
```

**Expected Output:**
```
INFO:root:Starting pipeline with DirectRunner
INFO:root:Reading input file: components/tests/data/applications_sample.csv
INFO:root:Processing records...
INFO:root:100% Complete
INFO:root:Pipeline finished successfully
```

**Output files created:**
```
/tmp/pipeline_output-valid.json       # Valid records
/tmp/pipeline_output-invalid.json     # Invalid records
/tmp/pipeline_output-processed.json   # Processed records
```

**Verify output:**
```bash
# Check what was created
ls -lh /tmp/pipeline_output*

# View a sample record
head -n 5 /tmp/pipeline_output-valid.json | python3 -m json.tool
```

**Time Estimate:** 15-30 seconds depending on data size

**Common Issues:**

**Issue 1: Memory error**
```
Error: Java heap space
Fix: This is DirectRunner working locally - normal for large datasets
```

**Issue 2: FileNotFoundError**
```
Error: applications_sample.csv not found
Fix: Use absolute path or ensure you're in blueprint directory
```

### Test Type 4: Local Airflow Setup (30-45 minutes)

**Purpose:** Test Airflow DAGs and scheduling logic locally

**Step 1: Start Local Airflow with Docker**
```bash
cd blueprint/setup

# Start services (PostgreSQL for Airflow, Redis for caching)
docker-compose up -d

# Verify services started
docker-compose ps
# Expected output:
# CONTAINER ID  IMAGE          STATUS
# xxxxx         loa-postgres   Up 2 minutes
# yyyyy         loa-redis      Up 2 minutes
```

**Step 2: Initialize Airflow**
```bash
# Set Airflow home
export AIRFLOW_HOME=$(pwd)/airflow

# Create directory
mkdir -p $AIRFLOW_HOME/dags $AIRFLOW_HOME/logs $AIRFLOW_HOME/plugins

# Initialize database
airflow db init

# Create admin user
airflow users create \
    --username admin \
    --password admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com
```

**Expected Output:**
```
Initialize database ... done
User created successfully
```

**Step 3: Copy DAGs to Airflow**
```bash
# Copy DAG files to Airflow
cp components/orchestration/airflow/dags/*.py $AIRFLOW_HOME/dags/

# Verify DAGs
ls -la $AIRFLOW_HOME/dags/
# Expected:
# loa_daily_pipeline_dag.py
# loa_ondemand_pipeline_dag.py
# dynamic_pipeline_dag.py
```

**Step 4: Start Airflow Services**
```bash
# Terminal 1: Start scheduler
airflow scheduler

# Terminal 2: Start webserver
airflow webserver

# Terminal 3: Monitor logs
tail -f $AIRFLOW_HOME/logs/scheduler/latest
```

**Access Airflow UI:**
```
URL: http://localhost:8080
Username: admin
Password: admin
```

**Step 5: Test DAG**
```bash
# List DAGs
airflow dags list

# Expected output:
# dag_id                     | filepath
# loa_daily_pipeline_dag     | loa_daily_pipeline_dag.py
# loa_ondemand_pipeline_dag  | loa_ondemand_pipeline_dag.py
# dynamic_pipeline_dag       | dynamic_pipeline_dag.py

# Test DAG parsing
airflow dags test loa_daily_pipeline_dag 2025-01-01

# Expected output:
# [2025-01-01 10:30:00] ...Successfully parsed DAG
```

**Step 6: Trigger DAG Run**
```bash
# Via command line
airflow dags trigger loa_daily_pipeline_dag

# Via UI
# 1. Go to http://localhost:8080
# 2. Click on "loa_daily_pipeline_dag"
# 3. Click play button to trigger
```

**Monitor Execution:**
```bash
# Watch logs in real time
tail -f $AIRFLOW_HOME/logs/dags/loa_daily_pipeline_dag/*.log

# Check DAG status
airflow dag-runs list --dag-id loa_daily_pipeline_dag

# Expected output:
# dag_id    run_id                 start_date           state
# loa_...   manual__2025-01-01...  2025-01-01 10:30:00  running
```

**Stop Airflow Services:**
```bash
# Stop from Terminal 1, 2, 3 (Ctrl+C)

# Stop Docker services
docker-compose down

# Clean up
rm -rf $AIRFLOW_HOME
```

**Time Estimate:** 30-45 minutes (most time is setup)

---

## 📊 EXPECTED OUTPUT FOR EACH TEST

### Unit Tests - Success

**Full Success:**
```bash
$ pytest components/tests/unit/ -v

components/tests/unit/test_validation.py::TestValidateSsn::test_valid_ssn_with_hyphens PASSED      [  3%]
components/tests/unit/test_validation.py::TestValidateSsn::test_valid_ssn_without_hyphens PASSED   [  6%]
components/tests/unit/test_data_factory.py::TestApplicationFactory::test_create_single PASSED      [ 12%]
components/tests/unit/test_audit.py::TestAuditTrail::test_record_creation PASSED                  [ 21%]
...more tests...

===================== 112 passed in 3.45s ======================
```

**Key Indicators of Success:**
- ✅ All tests show "PASSED"
- ✅ Time less than 10 seconds
- ✅ No warnings or errors
- ✅ Final line shows "X passed"

### Unit Tests - Failure

**Sample Failure:**
```bash
components/tests/unit/test_validation.py::TestValidateSsn::test_empty_ssn FAILED    [ 23%]

_____________________ TestValidateSsn::test_empty_ssn _____________________

def test_empty_ssn(self):
    errors = validate_ssn("")
>   assert len(errors) == 1
E   AssertionError: assert 0 == 1

components/tests/unit/test_validation.py:45: AssertionError

===================== 1 failed, 111 passed in 3.52s ======================
```

**What to Do:**
1. Read the assertion error
2. Check the test code (line shown)
3. Run with `-v -s` for more details
4. See "Troubleshooting" section below

### Coverage Report - Success

**HTML Coverage Report:**
```
Name                           Stmts   Miss  Cover
──────────────────────────────────────────────
components/loa_common/         450     18   96%
├─ validation.py               120      2   98%
├─ audit.py                     95      3   97%
├─ data_quality.py             115      8   93%
└─ error_handling.py           120      5   96%
──────────────────────────────────────────────
TOTAL                          450     18   96%
```

**Interpretation:**
- Coverage > 95%: ✅ Excellent
- Coverage 80-95%: ✅ Good
- Coverage < 80%: ⚠️ Needs improvement

### Dataflow (DirectRunner) - Success

**Sample Output:**
```
INFO:root:Started running pipeline with DirectRunner
INFO:root:Reading 100 application records from CSV
INFO:root:Validating records...
INFO:root:  Valid: 95 records
INFO:root:  Invalid: 5 records
INFO:root:Processing valid records...
INFO:root:Writing output...
INFO:root:Pipeline completed successfully

Output files:
- /tmp/output-valid.json (95 records)
- /tmp/output-invalid.json (5 records)
```

**Success Criteria:**
- ✅ Process starts without errors
- ✅ All records processed
- ✅ Output files created
- ✅ No exceptions thrown

### Airflow DAG - Success

**DAG Parse Success:**
```
[2025-01-01 10:30:00] __main__ INFO: Successfully parsed DAG: loa_daily_pipeline_dag
[2025-01-01 10:30:00] __main__ INFO: DAG has 8 tasks
[2025-01-01 10:30:00] __main__ INFO: Task dependencies valid
```

**DAG Run Success:**
```
DAG Run Status: running → success
Tasks Completed:
  ✅ wait_for_input (2s)
  ✅ validate_input (5s)
  ✅ run_dataflow_pipeline (15s)
  ✅ validate_output (3s)
  ✅ archive_files (2s)
  ✅ send_notification (1s)

Total Runtime: 28 seconds
Status: SUCCESS
```

---

## 🔄 COMPLETE WORKFLOW

### Day-by-Day Testing Schedule

#### **Day 1: Setup & Quick Test (30 minutes)**

**Morning:**
```bash
# 1. Set up environment (10 min)
cd blueprint
python3 -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 2. Run quick validation (5 min)
python3 -c "from components.loa_common.validation import validate_ssn; print(validate_ssn('123-45-6789'))"

# 3. Run unit tests (10 min)
pytest components/tests/unit/test_validation.py -v

# Expected: All tests pass, setup complete ✅
```

**Afternoon:**
```bash
# 4. Install Docker (5 min - if needed)
brew install docker  # or: apt-get install docker.io
```

#### **Day 2: Unit Tests & Coverage (1-2 hours)**

**Morning:**
```bash
# 1. Run all unit tests (5 min)
pytest components/tests/unit/ -v

# 2. Generate coverage report (5 min)
pytest components/tests/unit/ --cov=components.loa_common --cov-report=html

# 3. Review coverage (10 min)
open htmlcov/index.html

# Expected: 96%+ coverage ✅
```

**Afternoon:**
```bash
# 4. Run specific test categories (30 min)
pytest components/tests/unit/ -v -k "validation"    # Validation tests
pytest components/tests/unit/ -v -k "audit"         # Audit tests
pytest components/tests/unit/ -v -k "data_quality"  # Quality tests
```

#### **Day 3: Integration Tests (1-2 hours)**

**Morning:**
```bash
# 1. Start Docker services (5 min)
docker-compose up -d

# 2. Run integration tests (10 min)
pytest components/tests/integration/ -v

# 3. Check service health (5 min)
docker-compose ps
```

**Afternoon:**
```bash
# 4. Test with real files (30 min)
pytest components/tests/local/ -v

# 5. Check logs (15 min)
docker-compose logs -f
```

#### **Day 4: Dataflow Tests (1-2 hours)**

**Morning:**
```bash
# 1. Test DirectRunner pipeline (15 min)
python3 components/loa_pipelines/test_pipeline.py \
    --runner DirectRunner \
    --input_file components/tests/data/applications_sample.csv \
    --output_prefix /tmp/output

# 2. Verify output (10 min)
ls -lh /tmp/output*
head -n 2 /tmp/output-valid.json
```

**Afternoon:**
```bash
# 3. Performance testing (30 min)
pytest components/tests/performance/ -v

# 4. Chaos testing (30 min)
pytest components/tests/chaos/ -v
```

#### **Day 5: Airflow & End-to-End (2-3 hours)**

**Morning:**
```bash
# 1. Set up Airflow (15 min)
export AIRFLOW_HOME=$(pwd)/airflow
mkdir -p $AIRFLOW_HOME/{dags,logs,plugins}
airflow db init
airflow users create --username admin --password admin --role Admin --email admin@example.com

# 2. Copy DAGs (5 min)
cp components/orchestration/airflow/dags/*.py $AIRFLOW_HOME/dags/

# 3. Start services (5 min)
airflow scheduler &
airflow webserver &
```

**Afternoon:**
```bash
# 4. Test DAGs (30 min)
airflow dags list
airflow dags test loa_daily_pipeline_dag 2025-01-01

# 5. Monitor execution (30 min)
# Open http://localhost:8080 and trigger DAG run

# 6. Verify success (15 min)
docker-compose logs
tail -f $AIRFLOW_HOME/logs/scheduler/latest
```

### Total Time Breakdown

| Activity | Time | Cumulative |
|----------|------|------------|
| Setup & Environment | 30 min | 30 min |
| Unit Tests | 1 hour | 1.5 hours |
| Integration Tests | 1 hour | 2.5 hours |
| Dataflow Tests | 1.5 hours | 4 hours |
| Airflow Setup & Tests | 2.5 hours | 6.5 hours |
| **TOTAL** | **7 hours** | **Over 5 days** |

**Fast Path (Core Testing Only):**
- Day 1: Setup (30 min)
- Day 2: Unit Tests (1 hour)
- Day 3: Integration Tests (1 hour)
- **Total: 2.5 hours**

### Cost Breakdown (Local Testing)

**Zero GCP Costs** ✅
- All testing is local
- No cloud resources needed
- Only costs: Local compute

**Infrastructure Requirements:**
```
CPU:    2+ cores
RAM:    8GB (used: ~4GB for all services)
Disk:   2-3GB (test data + images + artifacts)
```

**Cost Calculation:**
```
Local Testing Cost:        $0
Docker Images (first-time): Free (open source)
Maintenance:               Free
─────────────────────────
TOTAL MONTHLY COST:        $0
```

---

## 🐛 TROUBLESHOOTING

### Issue 1: "ModuleNotFoundError: No module named 'loa_common'"

**Cause:** Python path not set correctly

**Solution:**
```bash
# Ensure you're in blueprint directory
cd /path/to/project/blueprint

# Add to Python path (temporary)
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Or activate venv
source venv/bin/activate

# Or install as package
pip install -e .
```

### Issue 2: "pytest: command not found"

**Cause:** pytest not installed

**Solution:**
```bash
pip install pytest pytest-cov pytest-mock

# Verify
pytest --version
# Expected: pytest 7.4.0
```

### Issue 3: "Port 5432 already in use"

**Cause:** PostgreSQL already running or port conflict

**Solution:**
```bash
# Option 1: Stop existing service
docker-compose down

# Option 2: Use different port
# Edit setup/docker-compose.yml
#   ports:
#     - "5433:5432"  # Changed from 5432 to 5433

# Option 3: Find and stop process
lsof -i :5432    # Find process
kill -9 <PID>    # Kill process
```

### Issue 4: "Test timeout or hangs"

**Cause:** Long-running test, infinite loop, or resource issue

**Solution:**
```bash
# Run with timeout (30 seconds)
pytest components/tests/unit/ --timeout=30

# Run with verbose output to see what's happening
pytest components/tests/unit/ -v -s

# Run single test
pytest components/tests/unit/test_validation.py::TestValidateSsn::test_valid_ssn_with_hyphens -v -s
```

### Issue 5: "Memory error: java.lang.OutOfMemoryError"

**Cause:** Dataflow needs more memory

**Solution:**
```bash
# Increase Java heap size
export JAVA_OPTS="-Xmx4g"

# Run pipeline again
python3 components/loa_pipelines/test_pipeline.py --runner DirectRunner ...
```

### Issue 6: "Docker daemon not running"

**Cause:** Docker service stopped

**Solution:**
```bash
# macOS
brew services restart docker

# Linux
sudo systemctl restart docker

# Windows
# Restart Docker Desktop application

# Verify
docker ps
```

### Issue 7: "Connection refused: PostgreSQL"

**Cause:** PostgreSQL not running or not ready

**Solution:**
```bash
# Check status
docker-compose ps

# Restart services
docker-compose down
docker-compose up -d --wait

# Wait for health check
docker-compose logs postgres
# Look for: "database system is ready to accept connections"
```

### Issue 8: "Airflow: DAG import error"

**Cause:** Invalid DAG syntax or missing imports

**Solution:**
```bash
# Check DAG syntax
python3 $AIRFLOW_HOME/dags/loa_daily_pipeline_dag.py
# Should print: <DAG: loa_daily_pipeline_dag>

# Check imports
python3 -c "from orchestration.airflow.dags.loa_daily_pipeline_dag import loa_daily_pipeline_dag"

# View logs
tail -f $AIRFLOW_HOME/logs/dag_parser_process/latest
```

### Finding Logs

**Test Logs:**
```bash
# Pytest output (live)
pytest components/tests/unit/ -v -s --log-cli-level=DEBUG

# Saved to file
pytest components/tests/unit/ -v --log-file=test.log
cat test.log
```

**Docker Logs:**
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f postgres
docker-compose logs -f redis

# Last 100 lines
docker-compose logs --tail=100
```

**Airflow Logs:**
```bash
# Scheduler
tail -f $AIRFLOW_HOME/logs/scheduler/latest

# DAG parsing
tail -f $AIRFLOW_HOME/logs/dag_parser_process/latest

# Task execution
tail -f $AIRFLOW_HOME/logs/dags/loa_daily_pipeline_dag/*/latest
```

### How to Debug

**Step 1: Isolate the problem**
```bash
# Run single test
pytest components/tests/unit/test_validation.py::TestValidateSsn::test_valid_ssn_with_hyphens -v -s
```

**Step 2: Add debug output**
```bash
# Create test file for debugging
cat > test_debug.py << 'EOF'
from components.loa_common.validation import validate_ssn

# Test
result = validate_ssn("000-00-0000")
print(f"Result: {result}")
print(f"Type: {type(result)}")
print(f"Length: {len(result)}")

if result:
    for error in result:
        print(f"Error: {error}")
EOF

python3 test_debug.py
```

**Step 3: Check dependencies**
```bash
pip list | grep -E "pytest|apache-beam|google-cloud"
```

**Step 4: Review test code**
```bash
# Look at what test expects
cat components/tests/unit/test_validation.py | grep -A 10 "test_valid_ssn_with_hyphens"
```

**Step 5: Run with increased verbosity**
```bash
pytest components/tests/unit/ -vv --tb=long -s --log-cli-level=DEBUG
```

---

## ✅ NEXT STEPS

### When to Deploy to GCP

**Prerequisites Checklist:**
- ✅ All unit tests pass (>350 tests)
- ✅ Code coverage > 95%
- ✅ Integration tests pass
- ✅ Dataflow tests successful
- ✅ Airflow DAGs parse correctly
- ✅ No critical issues in logs

**Success Criteria:**

```bash
# All these should complete successfully
pytest components/tests/ -v --cov=components.loa_common --cov-report=term-report:96%+
```

### Ready for GCP Deployment?

**Check these:**
1. ✅ No failing tests
2. ✅ Coverage > 95%
3. ✅ All 350+ tests pass
4. ✅ No performance issues
5. ✅ Documentation complete
6. ✅ Terraform validated

**Then proceed:**
```bash
# Follow this guide for GCP deployment
cat GCP_DEPLOYMENT_GUIDE.md

# Or one-command deployment
./tools/setupanddeployongcp.sh your-project-id
```

### What Happens Next

**1. Infrastructure Setup (30-40 minutes)**
- Creates 25+ GCP resources
- Sets up BigQuery datasets
- Configures Cloud Storage
- Creates service accounts

**2. Initial Data Load**
- Loads sample data to GCS
- Triggers first pipeline run
- Validates end-to-end

**3. Monitoring & Testing**
- Enables Cloud Monitoring
- Sets up alerting
- Runs E2E tests

**4. Production Handoff**
- Document customizations
- Train team on patterns
- Transfer ownership

---

## 📞 QUICK REFERENCE

### Most Common Commands

```bash
# Setup (one time)
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
docker-compose up -d

# Run tests (daily)
pytest components/tests/unit/ -v                    # Unit tests
pytest components/tests/ --cov                      # With coverage
docker-compose down                                  # Cleanup

# Debug specific test
pytest components/tests/unit/test_validation.py -v -s

# View results
open htmlcov/index.html                             # Coverage
```

### File Locations

**Test Files:**
- Unit tests: `components/tests/unit/`
- Integration tests: `components/tests/integration/`
- Airflow DAGs: `components/orchestration/airflow/dags/`
- Sample data: `components/tests/data/`

**Configuration:**
- pytest config: `testing/pytest.ini`
- Docker config: `setup/docker-compose.yml`
- Requirements: `setup/requirements.txt`, `setup/requirements-dev.txt`

**Output:**
- Coverage report: `htmlcov/index.html`
- Test logs: `test.log` (if created)
- Airflow logs: `$AIRFLOW_HOME/logs/`

---

**Status:** ✅ Complete and Ready  
**Last Updated:** December 21, 2025  
**Audience:** All developers, QA, data engineers  

For issues or questions, see the Troubleshooting section above.

