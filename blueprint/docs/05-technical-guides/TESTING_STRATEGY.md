# 🧪 LOA Blueprint - Complete Testing Strategy

**Version:** 1.0  
**Last Updated:** December 21, 2025  
**Status:** Production Ready

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Testing Framework](#testing-framework)
3. [Test Organization](#test-organization)
4. [Unit Testing Strategy](#unit-testing-strategy)
5. [Integration Testing Strategy](#integration-testing-strategy)
6. [Functional Testing Strategy](#functional-testing-strategy)
7. [Test Data Management](#test-data-management)
8. [Mocking & Fixtures](#mocking--fixtures)
9. [Coverage Requirements](#coverage-requirements)
10. [CI/CD Integration](#cicd-integration)
11. [Test Execution](#test-execution)
12. [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

The LOA Blueprint provides comprehensive testing strategies for all components:
- **Unit Tests:** Individual function/class testing (70% of tests)
- **Integration Tests:** Component interaction testing (20% of tests)
- **Functional Tests:** End-to-end workflow testing (10% of tests)

### GDW Core Testing Standardization
To ensure consistency across platforms (Risk, Commercial, Credit), we use the standardized testing framework from `gdw_data_core.testing`. This provides:
- **Base Test Classes:** Pre-configured classes for common testing scenarios.
- **Unified Assertions:** Custom assertions for validation and data quality.
- **Beam Testing Utilities:** Standardized ways to test Dataflow/Beam pipelines.

### Goals
- ✅ Maintain 95%+ code coverage
- ✅ Catch errors before production
- ✅ Enable confident refactoring
- ✅ Document expected behavior
- ✅ Support rapid development
- ✅ **Standardize testing across all GDW platforms**

### Test Pyramid
```
        Functional Tests (10%)
           /  \
          /    \
    Integration Tests (20%)
       /        \
      /          \
   Unit Tests (70%)
```

---

## 🛠️ Testing Framework

### Standardized Base Classes
All tests should inherit from the standardized base classes in `gdw_data_core.testing`:

- **`BaseGDWTest`**: Root class for all tests. Inherits from `unittest.TestCase`.
- **`BaseValidationTest`**: Optimized for testing validators. Includes `assertValidationPassed` and `assertValidationError`.
- **`BaseBeamTest`**: Specialized for testing Apache Beam/Dataflow pipelines.

### Usage Example
```python
from gdw_data_core.testing import BaseValidationTest
from loa_common.validation import validate_ssn

class TestSsnValidation(BaseValidationTest):
    def test_valid_ssn(self):
        errors = validate_ssn("123-45-6789")
        self.assertValidationPassed(errors)
        
    def test_invalid_ssn(self):
        errors = validate_ssn("INVALID")
        self.assertValidationError(errors, "ssn", "format")
```

### Dependencies
```
pytest >= 7.0
pytest-cov >= 4.0          # Coverage reporting
pytest-mock >= 3.0         # Mocking helpers
unittest.mock              # Built-in (Python 3.3+)
faker >= 10.0             # Test data generation
gdw-data-core             # GDW Standardized Testing Framework
```

### Installation
```bash
pip install pytest pytest-cov pytest-mock faker
```

### Configuration
**pytest.ini:**
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = --cov=loa_common --cov=loa_pipelines --cov-report=html --cov-report=term-missing
minversion = 7.0
```

---

## 📂 Test Organization

### Directory Structure
```
blueprint/components/tests/
├── unit/
│   ├── test_validation.py
│   ├── test_io_utils.py
│   ├── test_error_handling.py
│   ├── test_audit.py
│   ├── test_data_quality.py
│   └── test_schema.py
│
├── integration/
│   ├── test_pipeline_end_to_end.py
│   ├── test_dataflow_local.py
│   └── test_bigquery_integration.py
│
├── functional/
│   ├── test_applications_functional.py
│   ├── test_error_handling_scenarios.py
│   └── test_reconciliation.py
│
├── fixtures/
│   ├── test_data_factory.py
│   ├── sample_data_generator.py
│   └── conftest.py
│
└── performance/
    └── test_performance_benchmarks.py
```

### File Naming Convention
- **test_*.py** - Regular test files
- **conftest.py** - Shared fixtures and configuration
- **test_*_functional.py** - Functional/E2E tests
- **test_*_integration.py** - Integration tests

---

## 🔬 Unit Testing Strategy

### What to Test
- Individual functions/methods
- Class initialization and properties
- Error conditions and edge cases
- Input validation
- Return value correctness

### Test Structure
```python
class TestComponentName:
    """Test suite for ComponentName."""
    
    @pytest.fixture
    def component(self):
        """Create component for testing."""
        return ComponentName()
    
    def test_happy_path(self, component):
        """Test success case."""
        result = component.do_something()
        assert result == expected
    
    def test_error_case(self, component):
        """Test error handling."""
        with pytest.raises(ValueError):
            component.do_something_bad()
    
    def test_edge_case(self, component):
        """Test boundary conditions."""
        result = component.do_something(0)
        assert result is not None
```

### Example: Testing FileValidator
```python
def test_validate_file_exists_success(self):
    """File exists check returns True."""
    validator = FileValidator("bucket")
    validator.gcs_client.bucket.return_value.blob.return_value.exists.return_value = True
    
    result = validator.validate_file_exists("test.csv")
    
    assert result is True
    validator.gcs_client.bucket.assert_called()
```

### Assertions
```python
# Value assertions
assert result == expected
assert result is not None
assert result in valid_values
assert 0 <= value <= 100

# Exception assertions
with pytest.raises(ValueError):
    function_that_raises()

# Collection assertions
assert len(items) == 3
assert item in items
assert all(x > 0 for x in items)
```

---

## 🔗 Integration Testing Strategy

### What to Test
- Multiple components working together
- External service integration (mocked)
- Data flow between components
- Error propagation
- State management across components

### Test Structure
```python
def test_pipeline_integration(self):
    """Test complete pipeline flow."""
    # Setup: Create mock services
    mock_gcs = MagicMock()
    mock_bq = MagicMock()
    
    # Execute: Run workflow
    validator = FileValidator(mock_gcs)
    archiver = FileArchiver(mock_gcs)
    result = validator.validate_file("test.csv")
    
    # Verify: Check interactions
    assert result is True
    mock_gcs.bucket.assert_called()
    mock_bq.insert_rows.assert_called()
```

### Example: End-to-End Pipeline
```python
def test_file_processing_pipeline(self):
    """Test complete file processing."""
    # Step 1: Validate
    is_valid, errors = validator.validate_file("app.csv")
    assert is_valid is True
    
    # Step 2: Archive
    archive_path = archiver.archive_file("app.csv")
    assert "archive" in archive_path
    
    # Step 3: Extract metadata
    size = extractor.get_file_size("app.csv")
    assert size > 0
    
    # Step 4: Verify all steps completed
    assert all([is_valid, archive_path, size])
```

---

## 🎭 Functional Testing Strategy

### What to Test
- Complete workflows from start to finish
- Real-world scenarios
- Business logic correctness
- Data accuracy in transformation
- Error recovery and retries

### Test Structure
```python
def test_application_processing_workflow(self):
    """Test processing application file end-to-end."""
    # 1. Create test data
    apps = application_factory.create_batch(100)
    
    # 2. Process through pipeline
    pipeline = LongRunningPipeline()
    result = pipeline.process_records(apps)
    
    # 3. Verify results
    assert result.total_records == 100
    assert result.successful_records == 100
    assert result.failed_records == 0
    
    # 4. Check side effects
    assert result.archive_path is not None
    assert result.metrics['completion_time'] > 0
```

### Business Process Testing
```python
def test_duplicate_detection_workflow(self):
    """Test complete duplicate detection workflow."""
    # Real scenario: Process batch with duplicates
    records = [
        {"app_id": "APP001", "name": "John"},
        {"app_id": "APP002", "name": "Jane"},
        {"app_id": "APP001", "name": "John"}  # Duplicate
    ]
    
    detector = DuplicateDetector()
    duplicates = detector.find_duplicates(records, key_fields=["app_id"])
    
    # Verify
    assert len(duplicates) > 0
    assert duplicates[0]["app_id"] == "APP001"
```

---

## 📊 Test Data Management

### Using Test Factories
```python
# Create single record
app = application_factory.create_single()

# Create batch
apps = application_factory.create_batch(100)

# Create with overrides
app = application_factory.with_ssn("999-99-9999").create_single()

# Builder pattern
app = (application_factory
       .with_loan_amount(500000)
       .with_loan_type("MORTGAGE")
       .create_single())
```

### Sample Data in Fixtures
```python
@pytest.fixture
def sample_applications(application_factory):
    """Provide 10 sample applications."""
    return application_factory.create_batch(10)

def test_batch_processing(sample_applications):
    """Test uses pre-generated sample data."""
    result = processor.process_batch(sample_applications)
    assert len(result) == 10
```

### CSV Format Validation
```python
def test_csv_format(self):
    """Verify test CSV matches FILE_FORMATS.md specs."""
    csv_content = """
    application_id,ssn,loan_amount,branch_code
    APP001,123-45-6789,250000,BRANCH001
    APP002,234-56-7890,500000,BRANCH002
    """
    
    # Validate against spec
    assert validate_csv_format(csv_content, APPLICATIONS_SPEC)
```

---

## 🎭 Mocking & Fixtures

### Mocking External Services
```python
@patch('google.cloud.storage.Client')
def test_with_mocked_gcs(mock_gcs_client):
    """Test with mocked GCS."""
    # Setup mock
    mock_blob = Mock()
    mock_blob.exists.return_value = True
    mock_gcs_client.bucket.return_value.blob.return_value = mock_blob
    
    # Test
    validator = FileValidator()
    result = validator.validate_file_exists("test.csv")
    
    # Verify
    assert result is True
    mock_gcs_client.bucket.assert_called()
```

### Using Fixtures
```python
@pytest.fixture
def gcs_mock():
    """Mock GCS client."""
    with patch('google.cloud.storage.Client') as mock:
        yield mock

def test_gcs_operation(gcs_mock):
    """Test using fixture."""
    gcs_mock.bucket.return_value.list_blobs.return_value = [Mock(), Mock()]
    # Test code here
```

### Fixture Scope
```python
@pytest.fixture(scope="function")  # New instance per test
def fresh_component():
    return Component()

@pytest.fixture(scope="class")     # Shared per test class
def shared_resource():
    return ExpensiveResource()

@pytest.fixture(scope="session")   # Shared entire session
def one_time_setup():
    return DatabaseConnection()
```

---

## 📊 Coverage Requirements

### Target Coverage
- **Overall:** 95%+ code coverage
- **Critical Path:** 100% coverage
- **Error Handling:** 95%+ coverage
- **Utilities:** 90%+ coverage

### Measuring Coverage
```bash
# Run tests with coverage
pytest --cov=loa_common --cov-report=html

# View coverage report
open htmlcov/index.html

# Check specific file
pytest --cov=loa_common.validation --cov-report=term-missing
```

### Coverage Report
```
coverage_name                 statements   missing   excluded   coverage
-----------                   ----------   -------   --------   --------
loa_common/validation.py      156         3         0          98%
loa_common/error_handling.py  189         4         0          97%
loa_common/audit.py           234         7         0          97%
-----------                   ----------   -------   --------   --------
TOTAL                         1280        21        0          98%
```

---

## 🔄 CI/CD Integration

### GitHub Actions Example
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - run: pip install -r requirements.txt
      - run: pytest --cov=loa_common
      - run: coverage report --fail-under=95
```

### Pre-commit Hook
```bash
#!/bin/bash
# .git/hooks/pre-commit
pytest --cov=loa_common
if [ $? -ne 0 ]; then
  echo "Tests failed. Commit aborted."
  exit 1
fi
```

---

## 🚀 Test Execution

### Run All Tests
```bash
pytest
```

### Run Specific Test File
```bash
pytest tests/unit/test_validation.py
```

### Run Specific Test Class
```bash
pytest tests/unit/test_validation.py::TestFileValidator
```

### Run Specific Test
```bash
pytest tests/unit/test_validation.py::TestFileValidator::test_validate_file_exists
```

### Run with Options
```bash
# Verbose output
pytest -v

# Show print statements
pytest -s

# Stop on first failure
pytest -x

# Run last failed
pytest --lf

# Run failed and passed
pytest --ff

# Show slowest 10 tests
pytest --durations=10
```

---

## 🔧 Troubleshooting

### Test Failures

**Problem:** Import errors
```python
# Solution: Add path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
```

**Problem:** Mock not working
```python
# Wrong:
@patch('module.ClassName')  # Wrong module path

# Right:
@patch('package.module.ClassName')  # Full path
```

**Problem:** Fixture not found
```python
# Make sure conftest.py is in correct directory
# tests/
#   conftest.py
#   unit/
#     test_something.py
```

### Performance Issues

**Slow Tests:**
```bash
# Find slow tests
pytest --durations=10

# Run in parallel (install pytest-xdist)
pytest -n auto
```

**Memory Issues:**
```bash
# Use session-scoped fixtures sparingly
# Clean up resources in teardown
@pytest.fixture
def resource():
    r = create_resource()
    yield r
    r.cleanup()  # Teardown
```

---

## 📚 Best Practices

### ✅ DO
- Test one thing per test
- Use descriptive test names
- Use fixtures for reusable setup
- Mock external dependencies
- Test error cases
- Keep tests fast
- Test edge cases and boundaries

### ❌ DON'T
- Test implementation details
- Use global state
- Create interdependent tests
- Write tests that sometimes fail
- Test third-party libraries
- Make external calls
- Ignore test failures

### Naming Convention
```python
# Good
def test_validate_ssn_with_valid_format():
def test_validate_ssn_with_invalid_format():
def test_validate_ssn_with_empty_string():

# Bad
def test_ssn():
def test_validation():
def test_it_works():
```

---

## 🎓 Team Guidelines

### For New Developers
1. Copy test patterns from existing tests
2. Use factories for test data
3. Mock external services
4. Aim for 95%+ coverage
5. Run tests before committing

### For New JCL Migration
1. Copy test structure from LOA tests
2. Create tests for entity-specific validation
3. Reuse common test utilities
4. Follow naming conventions
5. Update this guide with new patterns

### Code Review Checklist
- [ ] Tests written for new code
- [ ] Coverage > 95%
- [ ] All tests passing
- [ ] Mocks used for external services
- [ ] Test names are descriptive
- [ ] No flaky tests
- [ ] Documentation updated

---

## 📖 References

### Python Testing
- [pytest Documentation](https://docs.pytest.org/)
- [unittest.mock Guide](https://docs.python.org/3/library/unittest.mock.html)
- [pytest Best Practices](https://docs.pytest.org/en/latest/goodpractices.html)

### Project Testing
- See: `/blueprint/components/tests/unit/` for examples
- See: `/blueprint/components/tests/integration/` for integration examples
- See: `/blueprint/components/tests/fixtures/` for test data

---

## 📝 Summary

The LOA Blueprint provides:
- ✅ Comprehensive test organization
- ✅ Reusable test fixtures and factories
- ✅ Clear testing patterns and examples
- ✅ Mocking strategies for external services
- ✅ Coverage requirements and CI/CD integration
- ✅ Best practices and guidelines

**Teams building new JCL migrations can:**
1. Copy the test structure
2. Use the test factories
3. Reuse common test utilities
4. Follow the naming conventions
5. Achieve 95%+ coverage consistently

---

**Last Updated:** December 21, 2025  
**Status:** Production Ready  
**Maintained By:** LOA Blueprint Team  

For questions, see: `blueprint/docs/TESTING_STRATEGY.md`

