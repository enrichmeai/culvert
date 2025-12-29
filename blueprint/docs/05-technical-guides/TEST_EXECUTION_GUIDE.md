# Test Execution & Coverage Reporting - Quick Reference

**Components:** pytest.ini, run_tests.sh  
**Status:** ✅ Configured and Ready  
**Last Updated:** December 21, 2025

---

## Quick Start

### Run Tests
```bash
cd /path/to/project/blueprint
./blueprint/testing/run_tests.sh
```

### View Help
```bash
./blueprint/testing/run_tests.sh -h
```

### Run with Verbose Output
```bash
./blueprint/testing/run_tests.sh -v
```

### Run Specific Test Suite
```bash
./blueprint/testing/run_tests.sh test_pipeline_router
```

---

## Test Suite Details

### Test 1: Pipeline Router (test_pipeline_router.py)
- **Purpose:** Validate dynamic routing logic for LOA pipelines
- **Command:** `pytest components/tests/unit/test_pipeline_router.py -v --cov=loa_common.pipeline_router`
- **Coverage Module:** loa_common.pipeline_router
- **Expected Tests:** 35 tests
- **Expected Coverage:** 96%+

### Test 2: Dataflow (test_dataflow_flow.py)
- **Purpose:** Validate Apache Beam dataflow implementations
- **Command:** `pytest components/tests/unit/test_dataflow_flow.py -v -s --cov=credit.examples`
- **Coverage Module:** credit.examples
- **Output Mode:** Stream output (-s flag)
- **Expected Tests:** Varies
- **Expected Coverage:** 95%+

### Test 3: DAG Structure (test_dag_structure.py)
- **Purpose:** Validate Airflow DAG configurations
- **Command:** `pytest components/tests/unit/test_dag_structure.py -v --cov=loa_pipelines.dag_template`
- **Coverage Module:** loa_pipelines.dag_template
- **Expected Tests:** Varies
- **Expected Coverage:** 96%+

---

## Pytest Configuration (pytest.ini)

### Test Discovery
```ini
testpaths = components/tests
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*
```

### Output Options
```ini
addopts =
    -v                  # Verbose output
    --strict-markers    # Enforce marker definitions
    --tb=short          # Short traceback format
    --disable-warnings  # Clean output
    -ra                 # Report all test outcomes
```

### Available Test Markers
```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Performance tests only
pytest -m performance

# Chaos engineering tests only
pytest -m chaos

# Slow tests only
pytest -m slow

# Skip slow tests
pytest -m "not slow"

# Tests requiring GCP
pytest -m requires_gcp

# Tests requiring Airflow
pytest -m requires_airflow
```

---

## Coverage Reports

### Terminal Output
- **Format:** Summary with missing lines
- **Command:** Run ./blueprint/testing/run_tests.sh (included by default)
- **Output:** Console display showing % coverage per module

### HTML Report
- **Location:** `htmlcov/index.html`
- **Generated:** Automatically after test run
- **Format:** Interactive HTML with drill-down capability
- **Usage:** Open in browser to view detailed coverage

---

## Output Example

```
╔════════════════════════════════════════════════════════════════╗
║           LOA Blueprint Test Runner                            ║
║              Running pytest tests suite                        ║
╚════════════════════════════════════════════════════════════════╝

📋 Checking dependencies...
✅ Dependencies check passed

🧪 Test 1/3: Pipeline Router Tests
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
tests/unit/test_pipeline_router.py::TestPipelineRouter::test_router_initialization PASSED
...
✅ Pipeline Router Tests PASSED

🧪 Test 2/3: Dataflow Tests
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Dataflow Tests PASSED

🧪 Test 3/3: DAG Structure Tests
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ DAG Structure Tests PASSED

📊 Running all tests for coverage report...

╔════════════════════════════════════════════════════════════════╗
║                    TEST EXECUTION SUMMARY                      ║
╠════════════════════════════════════════════════════════════════╣
║ ✅ Pipeline Router Tests                              ║
║ ✅ Dataflow Tests                                    ║
║ ✅ DAG Structure Tests                               ║
╠════════════════════════════════════════════════════════════════╣
║ 📊 Coverage report generated                          ║
║    File: htmlcov/index.html                         ║
╚════════════════════════════════════════════════════════════════╝

✅ All tests PASSED!
```

---

## Exit Codes

| Exit Code | Meaning |
|-----------|---------|
| 0 | All tests passed ✅ |
| 1 | One or more tests failed ❌ |

### CI/CD Integration
The script returns proper exit codes for use in:
- GitHub Actions workflows
- GitLab CI/CD pipelines
- Jenkins jobs
- Other CI/CD systems

---

## Dependencies

**Automatically Installed by Script:**
- pytest
- pytest-cov
- pytest-xdist (optional, for parallel execution)

**Manual Installation (Optional):**
```bash
pip install pytest pytest-cov pytest-xdist
```

---

## Common Commands

### Run all tests in components/tests
```bash
pytest components/tests/ -v
```

### Run only unit tests
```bash
pytest components/tests/ -v -m unit
```

### Run with coverage for specific module
```bash
pytest components/tests/ -v --cov=loa_common --cov-report=html
```

### Run specific test file
```bash
pytest components/tests/unit/test_pipeline_router.py -v
```

### Run with output capture disabled (see print statements)
```bash
pytest components/tests/unit/ -v -s
```

### Run with strict markers and short traceback
```bash
pytest components/tests/unit/ -v --strict-markers --tb=short
```

---

## Troubleshooting

### Issue: Script not executable
```bash
chmod +x run_tests.sh
```

### Issue: pytest not found
```bash
pip install pytest pytest-cov
```

### Issue: Tests not discovered
- Check that test files follow `test_*.py` pattern
- Check that test classes inherit from `TestCase` or start with `Test`
- Check that test methods start with `test_`
- Verify `testpaths = components/tests` in pytest.ini

### Issue: Coverage report not generated
- Verify pytest-cov is installed: `pip install pytest-cov`
- Check --cov flag in command
- Verify write permissions in project directory

---

## Performance Tips

### Run tests in parallel (if installed)
```bash
pytest components/tests/ -v -n auto
```

### Run only failed tests from last run
```bash
pytest components/tests/ -v --lf
```

### Run tests until first failure
```bash
pytest components/tests/ -v -x
```

### Run with early exit on failures
```bash
pytest components/tests/ -v -x --maxfail=3
```

---

## Integration with Development Workflow

### Pre-commit Hook
Add to `.git/hooks/pre-commit`:
```bash
#!/bin/bash
./blueprint/testing/run_tests.sh || exit 1
```

### GitHub Actions
```yaml
- name: Run tests
  run: ./blueprint/testing/run_tests.sh
```

### Watch Mode (requires pytest-watch)
```bash
ptw components/tests/
```

---

**Status:** All test infrastructure ready for project testing! ✅

