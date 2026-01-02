# 🚀 Local Airflow DAG Test Script Guide

**File:** `blueprint/testing/test_airflow_locally.py`  
**Purpose:** Validate Airflow DAG structure without running Airflow services  
**Status:** ✅ Ready to use  
**Created:** December 21, 2025

---

## 📋 TABLE OF CONTENTS

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Command Reference](#command-reference)
4. [Output Examples](#output-examples)
5. [Troubleshooting](#troubleshooting)
6. [Integration with Testing](#integration-with-testing)

---

## 📖 OVERVIEW

### What It Does

The `blueprint/testing/test_airflow_locally.py` script:
- ✅ Imports your DAG from `components/loa_pipelines/dag_template.py`
- ✅ Creates a test DAG instance
- ✅ Validates DAG structure and configuration
- ✅ Validates all tasks are properly defined
- ✅ Validates task dependencies
- ✅ Prints results in user-friendly format
- ✅ Returns proper exit codes for CI/CD integration
- ✅ Supports JSON output for automation

### Why Use It

**Before Deployment:**
- Catch DAG errors early (before pushing to production)
- No need to run Airflow scheduler/webserver
- Fast validation (< 1 second)
- Zero cost (local only)

**During Development:**
- Quick feedback on DAG changes
- Verify task structure
- Check dependencies

**In CI/CD:**
- Automated validation on every commit
- JSON output for programmatic processing
- Proper exit codes for pipeline integration

### What It Doesn't Do

- ❌ Execute tasks or DAGs
- ❌ Connect to GCP/BigQuery
- ❌ Require Airflow services running
- ❌ Require database connections
- ❌ Need GCP credentials

---

## 🚀 QUICK START

### Basic Usage

**Run with default options:**
```bash
cd blueprint
python blueprint/testing/test_airflow_locally.py
```

**Output:**
```
======================================================================
DAG Validation Summary
======================================================================
✅ All validations passed!

DAG Information:
  DAG ID:           loa_test_applications_migration
  Owner:            data-engineering
  Description:      LOA migration pipeline for test_applications
  Start Date:       2025-01-01 00:00:00
  Schedule:         0 6 * * *
  Tags:             loa, migration, test_applications
  Total Tasks:      6

Tasks (6):
  • wait_for_input_files
    Type: GCSObjectExistenceSensor
    Retries: 1
    Trigger Rule: all_success
    Downstream: validate_input_files
  
  • validate_input_files
    Type: PythonOperator
    Retries: 1
    Trigger Rule: all_success
    Downstream: run_dataflow_pipeline
  
  ... (more tasks)

Task Dependencies:
  wait_for_input_files → validate_input_files
  validate_input_files → run_dataflow_pipeline
  run_dataflow_pipeline → data_quality_check
  data_quality_check → archive_processed_files
  archive_processed_files → send_completion_notification

✅ Validation completed successfully
```

### Verbose Output

**Show detailed information:**
```bash
python blueprint/testing/test_airflow_locally.py --verbose
```

**Output:**
```
ℹ️  Attempting to import DAG from loa_pipelines.dag_template...
✅ DAG import successful
ℹ️  Validating DAG structure...
✅ DAG structure validation passed
ℹ️  Validating tasks...
✅ Task validation passed (6 tasks)
ℹ️  Validating task dependencies...
✅ Dependency validation passed (5 dependencies)

... (full summary)
```

### JSON Output

**Get results as JSON for automation:**
```bash
python blueprint/testing/test_airflow_locally.py --output json
```

**Output:**
```json
{
  "timestamp": "2025-01-21T10:30:45.123456",
  "import_success": true,
  "validation_success": true,
  "dag_info": {
    "dag_id": "loa_test_applications_migration",
    "owner": "data-engineering",
    "description": "LOA migration pipeline for test_applications",
    "start_date": "2025-01-01 00:00:00",
    "schedule_interval": "0 6 * * *",
    "tags": ["loa", "migration", "test_applications"],
    "task_count": 6
  },
  "tasks": [
    {
      "task_id": "wait_for_input_files",
      "task_type": "GCSObjectExistenceSensor",
      "retries": 1,
      "pool": "default_pool",
      "trigger_rule": "all_success",
      "downstream_tasks": "[<Task(PythonOperator): validate_input_files>]"
    },
    ...
  ],
  "dependencies": [
    {"upstream": "wait_for_input_files", "downstream": "validate_input_files"},
    ...
  ],
  "errors": [],
  "warnings": []
}
```

---

## 🎯 COMMAND REFERENCE

### Basic Commands

**Show help:**
```bash
python blueprint/testing/test_airflow_locally.py --help
```

**Run with default output:**
```bash
python blueprint/testing/test_airflow_locally.py
```

**Run silently (only check, don't print):**
```bash
python blueprint/testing/test_airflow_locally.py --validate-only
```

### Options

| Option | Short | Purpose | Example |
|--------|-------|---------|---------|
| `--verbose` | `-v` | Show detailed output | `python blueprint/testing/test_airflow_locally.py -v` |
| `--output` | N/A | Output format (text/json) | `python blueprint/testing/test_airflow_locally.py --output json` |
| `--validate-only` | N/A | Validate without printing summary | `python blueprint/testing/test_airflow_locally.py --validate-only` |
| `--help` | `-h` | Show help message | `python blueprint/testing/test_airflow_locally.py -h` |

### Exit Codes

| Code | Meaning | When | Action |
|------|---------|------|--------|
| 0 | ✅ Success | DAG validated successfully | Continue |
| 1 | ❌ Import Error | Failed to import DAG | Check import path |
| 2 | ❌ Validation Error | DAG structure invalid | Fix DAG definition |
| 3+ | ⚠️ Other Error | Unexpected error | Check logs |

---

## 📊 OUTPUT EXAMPLES

### Example 1: Successful Validation (Default Output)

```
======================================================================
DAG Validation Summary
======================================================================
✅ All validations passed!

DAG Information:
  DAG ID:           loa_test_applications_migration
  Owner:            data-engineering
  Description:      LOA migration pipeline for test_applications
  Start Date:       2025-01-01 00:00:00
  Schedule:         0 6 * * *
  Tags:             loa, migration, test_applications
  Total Tasks:      6

Tasks (6):
  • wait_for_input_files
    Type: GCSObjectExistenceSensor
    Retries: 1
    Trigger Rule: all_success
    Downstream: validate_input_files
  
  • validate_input_files
    Type: PythonOperator
    Retries: 1
    Trigger Rule: all_success
    Downstream: run_dataflow_pipeline
  
  • run_dataflow_pipeline
    Type: DataflowTemplatedJobOperator
    Retries: 1
    Trigger Rule: all_success
    Downstream: data_quality_check
  
  • data_quality_check
    Type: PythonOperator
    Retries: 1
    Trigger Rule: all_success
    Downstream: archive_processed_files
  
  • archive_processed_files
    Type: PythonOperator
    Retries: 1
    Trigger Rule: all_success
    Downstream: send_completion_notification
  
  • send_completion_notification
    Type: PythonOperator
    Retries: 1
    Trigger Rule: all_success

Task Dependencies:
  wait_for_input_files → validate_input_files
  validate_input_files → run_dataflow_pipeline
  run_dataflow_pipeline → data_quality_check
  data_quality_check → archive_processed_files
  archive_processed_files → send_completion_notification

✅ Validation completed successfully
```

### Example 2: With Warnings

```
...DAG Information...

Warnings (1):
  ⚠️  Missing expected tasks: data_quality_check

...
```

### Example 3: Failed Validation

```
======================================================================
DAG Validation Summary
======================================================================
❌ Validation failed - see details below

Errors (1):
  ❌ DAG import failed: ModuleNotFoundError: No module named 'loa_pipelines'

...
```

### Example 4: Verbose Output

```
ℹ️  Attempting to import DAG from loa_pipelines.dag_template...
✅ DAG import successful
ℹ️  Validating DAG structure...
✅ DAG structure validation passed
ℹ️  Validating tasks...
✅ Task validation passed (6 tasks)
ℹ️  Validating task dependencies...
✅ Dependency validation passed (5 dependencies)

======================================================================
DAG Validation Summary
======================================================================
✅ All validations passed!

... (full summary)
```

---

## 🐛 TROUBLESHOOTING

### Issue 1: ModuleNotFoundError: No module named 'loa_pipelines'

**Cause:** Not running from the blueprint directory or Python path not set

**Solution:**
```bash
# Navigate to blueprint directory
cd blueprint

# Ensure you're in the right directory
pwd
# Expected: /path/to/blueprint

# Run the script
python blueprint/testing/test_airflow_locally.py
```

### Issue 2: ModuleNotFoundError: No module named 'airflow'

**Cause:** Airflow package not installed

**Solution:**
```bash
# Install Airflow (from requirements.txt or requirements-dev.txt)
pip install apache-airflow

# Or install development dependencies
pip install -r requirements-dev.txt

# Then run the script
python blueprint/testing/test_airflow_locally.py
```

### Issue 3: ImportError: No module named 'google.cloud'

**Cause:** Google Cloud packages not installed

**Solution:**
```bash
# Install Google Cloud packages
pip install -r requirements.txt

# Then run the script
python blueprint/testing/test_airflow_locally.py
```

### Issue 4: DAG validation shows warnings

**Cause:** DAG structure doesn't match expected tasks

**Solution:**
1. Check the DAG definition in `dag_template.py`
2. Review warning messages
3. Compare actual tasks to expected tasks
4. This is usually not a blocker - warnings don't fail validation

### Issue 5: Script produces no output

**Cause:** Python process completed but no output shown

**Solution:**
```bash
# Run with verbose flag to see progress
python blueprint/testing/test_airflow_locally.py --verbose

# Or check exit code
python blueprint/testing/test_airflow_locally.py
echo $?  # Shows exit code
```

---

## 🔄 INTEGRATION WITH TESTING

### Running in Test Suite

**Add to your test suite:**
```bash
# In run_tests.sh or your test script
echo "Testing DAG structure..."
python blueprint/testing/test_airflow_locally.py || exit 1
```

### CI/CD Integration

**In GitHub Actions:**
```yaml
- name: Validate Airflow DAG
  run: |
    cd blueprint
    python blueprint/testing/test_airflow_locally.py
    if [ $? -ne 0 ]; then
      echo "DAG validation failed"
      exit 1
    fi
```

**In GitLab CI:**
```yaml
test_dag:
  script:
    - cd blueprint
    - python blueprint/testing/test_airflow_locally.py --validate-only
  allow_failure: false
```

### Generating Reports

**Create a JSON report:**
```bash
python blueprint/testing/test_airflow_locally.py --output json > dag_report.json
```

**Process the report:**
```bash
# Check if validation passed
cat dag_report.json | python -m json.tool | grep validation_success
```

---

## 📝 VALIDATION CHECKLIST

The script validates:

### DAG Structure
- ✅ DAG has valid dag_id
- ✅ DAG has owner
- ✅ DAG has proper attributes
- ✅ DAG ID doesn't contain spaces

### Tasks
- ✅ DAG has tasks (not empty)
- ✅ Each task has task_id
- ✅ Each task is associated with DAG
- ✅ Task types are correct
- ✅ Expected tasks are present
- ✅ No critical missing tasks

### Dependencies
- ✅ Dependency chain is correct
- ✅ Upstream/downstream relationships valid
- ✅ No circular dependencies (implicit)
- ✅ All expected edges exist

### Configuration
- ✅ Retry settings valid
- ✅ Trigger rules valid
- ✅ Pool assignments valid
- ✅ Timeouts configured

---

## 🎓 EXAMPLES

### Example 1: Quick Validation Before Commit

```bash
# Before committing DAG changes
python blueprint/testing/test_airflow_locally.py

# If it passes (exit code 0), safe to commit
# If it fails (exit code != 0), fix the DAG first
```

### Example 2: Validate Multiple DAGs

```bash
# Create a loop to test multiple DAG configurations
for job_name in applications customers accounts branches; do
    echo "Testing $job_name..."
    python blueprint/testing/test_airflow_locally.py --job-name $job_name
    if [ $? -ne 0 ]; then
        echo "Failed for $job_name"
        exit 1
    fi
done

echo "All DAGs validated successfully"
```

### Example 3: Generate Report for Documentation

```bash
# Create a JSON report
python blueprint/testing/test_airflow_locally.py --output json > airflow_dag_report.json

# Use in documentation or deployment process
echo "DAG Report saved to airflow_dag_report.json"
```

### Example 4: Pre-Deployment Validation

```bash
#!/bin/bash
# Pre-deployment validation script

echo "Pre-deployment checks..."

# 1. Validate DAG structure
echo "1. Validating DAG structure..."
python blueprint/testing/test_airflow_locally.py --validate-only
if [ $? -ne 0 ]; then
    echo "❌ DAG validation failed"
    exit 1
fi
echo "✅ DAG validation passed"

# 2. Run unit tests
echo "2. Running unit tests..."
pytest components/tests/unit/ -v
if [ $? -ne 0 ]; then
    echo "❌ Unit tests failed"
    exit 1
fi
echo "✅ Unit tests passed"

# 3. Generate documentation
echo "3. Generating DAG documentation..."
python blueprint/testing/test_airflow_locally.py --output json > docs/dag_structure.json
echo "✅ Documentation generated"

echo ""
echo "✅ All pre-deployment checks passed!"
echo "Ready to deploy to GCP"
```

---

## 🔗 RELATED FILES

- **DAG Template:** `components/loa_pipelines/dag_template.py`
- **Test Guide:** `TESTING_LOCAL.md`
- **Airflow Docs:** `components/orchestration/airflow/dags/`

---

## 📞 QUICK REFERENCE

```bash
# Most common commands
python blueprint/testing/test_airflow_locally.py                    # Run validation
python blueprint/testing/test_airflow_locally.py --verbose          # With details
python blueprint/testing/test_airflow_locally.py --output json      # As JSON
python blueprint/testing/test_airflow_locally.py --validate-only    # Silent check
python blueprint/testing/test_airflow_locally.py --help             # Show help

# Check exit code
python blueprint/testing/test_airflow_locally.py && echo "Success" || echo "Failed"
```

---

**Status:** ✅ Ready for Production  
**Last Updated:** December 21, 2025  
**Audience:** All developers, QA, CI/CD engineers

