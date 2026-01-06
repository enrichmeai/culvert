"""
GDW Data Core Tests Documentation

This document describes the test organization and structure.

## Test Structure

```
gcp-pipeline-builder/tests/
├── __init__.py
├── conftest.py                      # Shared fixtures and configuration
├── unit/                            # Unit tests
│   ├── __init__.py
│   ├── core/                        # Core module unit tests
│   │   ├── __init__.py
│   │   ├── test_validators.py
│   │   ├── test_error_handling.py
│   │   ├── test_monitoring.py
│   │   ├── test_audit.py
│   │   ├── test_io_utils.py
│   │   └── test_bigquery_client.py
│   ├── orchestration/               # Orchestration module unit tests
│   │   ├── __init__.py
│   │   ├── test_dag_factory.py
│   │   └── test_router.py
│   └── pipelines/                   # Pipelines module unit tests
│       ├── __init__.py
│       └── test_base_pipeline.py
└── README.md                        # This file
```

## Test Organization

Tests are organized by module following the project structure:

- **unit/core/** - Tests for core utilities (validators, error handling, monitoring, audit, I/O, database)
- **unit/orchestration/** - Tests for DAG factory and routing
- **unit/pipelines/** - Tests for pipeline base classes and Beam helpers

## Running Tests

### Run all tests
```bash
pytest gcp-pipeline-builder/tests/ -v
```

### Run specific test module
```bash
pytest gcp-pipeline-builder/tests/unit/core/ -v
pytest gcp-pipeline-builder/tests/unit/orchestration/ -v
pytest gcp-pipeline-builder/tests/unit/pipelines/ -v
```

### Run specific test class
```bash
pytest gcp-pipeline-builder/tests/unit/orchestration/test_dag_factory.py::TestDAGFactory -v
```

### Run specific test
```bash
pytest gcp-pipeline-builder/tests/unit/orchestration/test_dag_factory.py::TestDAGFactory::test_create_dag_basic -v
```

### Run with coverage
```bash
pytest gcp-pipeline-builder/tests/ --cov=gcp-pipeline-builder --cov-report=html
```

### Run with markers
```bash
pytest gcp-pipeline-builder/tests/ -m "not slow" -v
```

## Shared Fixtures

Shared fixtures are defined in `conftest.py`:

- `cleanup_dag_factory` - Cleanup fixture for DAGFactory state
- `sample_dag_config` - Sample DAG configuration dictionary
- `sample_pipeline_config` - Sample pipeline configuration object

## Test Naming Conventions

- Test files: `test_*.py`
- Test classes: `Test*`
- Test methods: `test_*`

Example:
```python
class TestDAGFactory:
    def test_create_dag_basic(self):
        ...
```

## Adding New Tests

When adding new tests:

1. Create test file in appropriate subdirectory (unit/core/, unit/orchestration/, etc.)
2. Follow naming conventions (test_*.py, TestClassName, test_method_name)
3. Use shared fixtures when possible
4. Add docstrings to test methods
5. Use descriptive assertion messages

Example:
```python
# In gcp-pipeline-builder/tests/unit/orchestration/test_my_module.py
import pytest
from gcp-pipeline-builder.orchestration import MyClass

class TestMyClass:
    def test_my_feature(self):
        \"\"\"Test that my feature works correctly.\"\"\"
        obj = MyClass()
        result = obj.my_method()
        assert result == expected_value, "Description of what failed"
```

## Continuous Integration

Tests are run automatically on:
- Pre-commit (local)
- Pull requests
- Merge to main branch

## Test Coverage Goals

- Minimum 80% code coverage
- All public APIs covered
- Edge cases and error conditions tested
- Integration between modules tested

## Troubleshooting

### Import errors in tests
Make sure the package is installed in editable mode:
```bash
cd gcp-pipeline-builder
pip install -e .
```

### Tests not discovered
Check that:
- Test files are named `test_*.py`
- Test classes are named `Test*`
- Test methods are named `test_*`
- `__init__.py` files exist in all test directories

### Fixture not found errors
Check that fixtures are defined in `conftest.py` and properly exported.
"""
