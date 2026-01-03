# GCP Pipeline Tester

A comprehensive testing framework for GCP data pipelines, providing mocks, fixtures, builders, and assertions for testing BigQuery, GCS, Pub/Sub, and Dataflow pipelines.

> **📖 Part of the Legacy Mainframe to GCP Migration Framework**  
> This library provides testing utilities for pipelines built with `gcp-pipeline-builder`.

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Base Test Classes](#base-test-classes)
- [Mocks](#mocks)
- [Builders](#builders)
- [Fixtures](#fixtures)
- [Assertions](#assertions)
- [Dual-Run Comparison](#dual-run-comparison)
- [BDD Testing](#bdd-testing)
- [Running Tests](#running-tests)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)

---

## Features

- **Base Test Classes**: `BaseGDWTest`, `BaseBeamTest`, `BaseValidationTest` - foundational test classes with common assertions
- **Mocks**: Mock implementations for GCS, BigQuery, Pub/Sub - test without real GCP connectivity
- **Fixtures**: Ready-to-use pytest fixtures for sample data and GCP services
- **Builders**: Fluent builders for constructing test records and configurations
- **Assertions**: Domain-specific assertion functions for pipeline testing
- **Comparison**: Dual-run comparison utilities for migration validation
- **BDD**: Behavior-driven development support with Gherkin step definitions

---

## Installation

```bash
# Install from source
cd libraries/gcp-pipeline-tester
pip install -e .

# Or with dev dependencies
pip install -e ".[dev]"
```

---

## Quick Start

### Basic Test with Base Class

```python
from gcp_pipeline_tester import BaseGDWTest

class TestMyPipeline(BaseGDWTest):
    def test_record_has_required_fields(self):
        record = {"id": "1", "name": "John", "email": "john@example.com"}
        
        self.assertFieldExists(record, "id")
        self.assertFieldValue(record, "name", "John")
        self.assertRecordStructure(record, ["id", "name", "email"])
```

### Validation Testing

```python
from gcp_pipeline_tester import BaseValidationTest

class TestMyValidator(BaseValidationTest):
    def test_validation_passes(self):
        errors = my_validator.validate({"id": "1", "name": "John"})
        self.assertValidationPassed(errors)
    
    def test_validation_fails_for_missing_field(self):
        errors = my_validator.validate({})
        self.assertValidationFailed(errors)
        self.assertValidationError(errors, "id", "required")
```

### Using Mocks

```python
from gcp_pipeline_tester.mocks import GCSClientMock, BigQueryClientMock

class TestWithMocks(BaseGDWTest):
    def test_gcs_operations(self):
        gcs_mock = GCSClientMock()
        gcs_mock.write_file("gs://bucket/input.csv", "id,name\n1,John")
        
        content = gcs_mock.read_file("gs://bucket/input.csv")
        self.assertEqual(content, "id,name\n1,John")
    
    def test_bigquery_operations(self):
        bq_mock = BigQueryClientMock()
        
        errors = bq_mock.insert_rows_json(
            "project.dataset.table",
            [{"id": "1", "name": "John"}]
        )
        
        self.assertEqual(errors, [])
        self.assertEqual(len(bq_mock.get_inserted_rows()), 1)
```

---

## Base Test Classes

### BaseGDWTest

Root test class with record assertions.

```python
from gcp_pipeline_tester import BaseGDWTest

class TestMyModule(BaseGDWTest):
    def test_field_exists(self):
        record = {'id': '123', 'name': 'John'}
        self.assertFieldExists(record, 'id')
        self.assertFieldValue(record, 'name', 'John')
        self.assertRecordStructure(record, ['id', 'name'])
```

**Available Assertions:**
- `assertFieldExists(record, field)` - Assert field exists in record
- `assertFieldValue(record, field, expected)` - Assert field has expected value
- `assertRecordStructure(record, expected_fields)` - Assert record has all expected fields

### BaseValidationTest

Test class for validation logic.

```python
from gcp_pipeline_tester import BaseValidationTest

class TestValidators(BaseValidationTest):
    def test_valid_ssn(self):
        errors = validate_ssn("123-45-6789")
        self.assertValidationPassed(errors)
    
    def test_invalid_ssn(self):
        errors = validate_ssn("invalid")
        self.assertValidationFailed(errors)
        self.assertValidationError(errors, "ssn")
```

**Available Assertions:**
- `assertValidationPassed(errors)` - Assert no validation errors
- `assertValidationFailed(errors)` - Assert validation failed
- `assertValidationError(errors, field, message=None)` - Assert specific validation error

### BaseBeamTest

Test class for Apache Beam pipelines.

```python
from gcp_pipeline_tester import BaseBeamTest
import apache_beam as beam

class TestBeamTransforms(BaseBeamTest):
    def test_parse_csv(self):
        pipeline = self.create_test_pipeline()
        
        result = (pipeline
            | beam.Create(['"id","name"\n"1","John"'])
            | beam.ParDo(ParseCsvLine(['id', 'name']))
        )
        
        self.assert_pcollection_contains(result, {'id': '1', 'name': 'John'})
```

---

## Mocks

### GCSClientMock

Mock GCS client for file operations without real GCP connectivity.

```python
from gcp_pipeline_tester.mocks import GCSClientMock

def test_gcs_operations():
    mock = GCSClientMock()
    
    # Write file
    mock.write_file("gs://bucket/file.csv", "id,name\n1,John")
    
    # Read file
    content = mock.read_file("gs://bucket/file.csv")
    assert content == "id,name\n1,John"
    
    # List files
    files = mock.list_files("gs://bucket/")
    assert "file.csv" in files
    
    # Check file exists
    assert mock.file_exists("gs://bucket/file.csv")
    
    # Delete file
    mock.delete_file("gs://bucket/file.csv")
```

### BigQueryClientMock

Mock BigQuery client for table operations.

```python
from gcp_pipeline_tester.mocks import BigQueryClientMock

def test_bigquery_operations():
    mock = BigQueryClientMock()
    
    # Insert rows
    errors = mock.insert_rows_json(
        "project.dataset.table",
        [{"id": "1", "name": "John"}, {"id": "2", "name": "Jane"}]
    )
    assert errors == []
    
    # Get inserted rows
    rows = mock.get_inserted_rows()
    assert len(rows) == 2
    
    # Query (returns inserted rows)
    results = mock.query("SELECT * FROM dataset.table")
```

### PubSubMock

Mock Pub/Sub client for messaging.

```python
from gcp_pipeline_tester.mocks import PubSubMock

def test_pubsub_operations():
    mock = PubSubMock()
    
    # Publish message
    mock.publish("projects/proj/topics/topic", {"event": "file_ready"})
    
    # Get published messages
    messages = mock.get_published_messages()
    assert len(messages) == 1
    
    # Pull messages
    pulled = mock.pull("projects/proj/subscriptions/sub")
```

---

## Builders

### RecordBuilder

Fluent builder for test records.

```python
from gcp_pipeline_tester.builders import RecordBuilder

record = (RecordBuilder()
    .with_field("id", "123")
    .with_field("name", "John")
    .with_field("email", "john@example.com")
    .with_field("amount", 45.67)
    .build())

assert record == {"id": "123", "name": "John", "email": "john@example.com", "amount": 45.67}
```

### CSVRecordBuilder

Builder for CSV records (all values converted to strings).

```python
from gcp_pipeline_tester.builders import CSVRecordBuilder

record = (CSVRecordBuilder(["id", "name", "amount"])
    .with_field("id", 123)
    .with_field("name", "John")
    .with_field("amount", 45.67)
    .build())

# All values are strings for CSV
assert record == {"id": "123", "name": "John", "amount": "45.67"}
```

### PipelineConfigBuilder

Builder for pipeline configurations.

```python
from gcp_pipeline_tester.builders import PipelineConfigBuilder

config = (PipelineConfigBuilder()
    .with_pipeline_name("test_pipeline")
    .with_run_id("run_001")
    .with_source_file("gs://bucket/input.csv")
    .build())
```

---

## Fixtures

Ready-to-use pytest fixtures for common testing scenarios.

```python
import pytest
from gcp_pipeline_tester.fixtures import sample_records, sample_config

def test_with_sample_records(sample_records):
    """Use pre-generated sample records."""
    assert len(sample_records) > 0
    assert 'id' in sample_records[0]

def test_with_config(sample_config):
    """Use sample pipeline config."""
    assert sample_config.pipeline_name == 'test_pipeline'
```

### Available Fixtures

| Fixture | Description |
|---------|-------------|
| `sample_records` | List of sample record dictionaries |
| `sample_config` | Sample PipelineConfig |
| `gcs_mock` | GCSClientMock instance |
| `bigquery_mock` | BigQueryClientMock instance |
| `pubsub_mock` | PubSubMock instance |
| `test_pipeline` | Beam test pipeline |

---

## Assertions

Domain-specific assertion functions.

```python
from gcp_pipeline_tester.assertions import (
    assert_field_exists,
    assert_records_equal,
    assert_record_count
)

# Field assertions
assert_field_exists(record, "id")

# Record comparison
assert_records_equal(actual_records, expected_records)

# Count assertions
assert_record_count(records, expected_count=100)
```

---

## Dual-Run Comparison

Compare source (mainframe CSV) with target (BigQuery) for migration validation.

```python
from gcp_pipeline_tester.comparison import DualRunComparison

comparison = DualRunComparison(
    project_id="my-project",
    source_file="mainframe_output.csv",
    target_table="project:dataset.table",
    job_name="customer_migration",
    tolerance_percent=1.0,  # Allow 1% difference
)

# Run comparison
report = comparison.compare()

# Check results
print(report.summary())
assert report.overall_status == "PASS"
```

### Comparison Checks

| Check | Description |
|-------|-------------|
| `row_count` | Compare record counts |
| `column_match` | Verify all columns present |
| `data_hash` | Compare data checksums |
| `sample_validation` | Validate sample records |

---

## BDD Testing

Behavior-driven development support with Gherkin step definitions.

### Writing Feature Files

```gherkin
# features/validation.feature
Feature: SSN Validation
  
  Scenario: Valid SSN passes validation
    Given I have a record with SSN "123-45-6789"
    When I validate the SSN
    Then validation should pass
  
  Scenario: Invalid SSN fails validation
    Given I have a record with SSN "invalid"
    When I validate the SSN
    Then validation should fail with error "Invalid SSN format"
```

### Implementing Steps

```python
from gcp_pipeline_tester.bdd import GDWScenarioTest
from pytest_bdd import given, when, then, scenario

class TestSSNValidation(GDWScenarioTest):
    
    @scenario('features/validation.feature', 'Valid SSN passes validation')
    def test_valid_ssn(self):
        pass
    
    @given('I have a record with SSN "<ssn>"')
    def given_ssn(self, ssn):
        self.context['ssn'] = ssn
    
    @when('I validate the SSN')
    def when_validate(self):
        self.context['errors'] = validate_ssn(self.context['ssn'])
    
    @then('validation should pass')
    def then_pass(self):
        assert len(self.context['errors']) == 0
```

---

## Running Tests

```bash
# Run all tests
./run_tests.sh

# Or manually
PYTHONPATH=src pytest tests/unit -v

# With coverage
PYTHONPATH=src pytest tests/unit -v --cov=src/gcp_pipeline_tester --cov-report=html
```

---

## Project Structure

```
gcp-pipeline-tester/
├── README.md                    # This file
├── pyproject.toml               # Package configuration
├── pytest.ini                   # Test configuration
├── run_tests.sh                 # Test runner script
├── src/
│   └── gcp_pipeline_tester/
│       ├── __init__.py          # Main exports
│       ├── base/                # Base test classes
│       │   ├── gdw_test.py      # BaseGDWTest
│       │   ├── beam_test.py     # BaseBeamTest
│       │   ├── validation_test.py
│       │   └── result.py        # TestResult dataclass
│       ├── mocks/               # GCP service mocks
│       │   ├── gcs_mock.py
│       │   ├── bigquery_mock.py
│       │   └── pubsub_mock.py
│       ├── fixtures/            # Pytest fixtures
│       │   ├── common.py
│       │   ├── gcs.py
│       │   ├── bigquery.py
│       │   └── beam.py
│       ├── builders/            # Test data builders
│       │   ├── record_builder.py
│       │   ├── csv_builder.py
│       │   └── config_builder.py
│       ├── comparison/          # Dual-run comparison
│       │   └── dual_run.py
│       ├── assertions/          # Custom assertions
│       └── bdd/                 # BDD step definitions
└── tests/
    └── unit/                    # Unit tests
```

---

## API Reference

### Base Classes

| Class | Description |
|-------|-------------|
| `BaseGDWTest` | Root test class with record assertions |
| `BaseValidationTest` | Test class for validation logic |
| `BaseBeamTest` | Test class for Apache Beam pipelines |
| `TestResult` | Standardized test result dataclass |

### Mocks

| Mock | Description |
|------|-------------|
| `GCSClientMock` | Mock GCS client for file operations |
| `GCSBucketMock` | Mock GCS bucket |
| `BigQueryClientMock` | Mock BigQuery client |
| `BigQueryTableMock` | Mock BigQuery table |
| `PubSubMock` | Mock Pub/Sub client |

### Builders

| Builder | Description |
|---------|-------------|
| `RecordBuilder` | Fluent builder for test records |
| `CSVRecordBuilder` | Builder for CSV records (converts to strings) |
| `PipelineConfigBuilder` | Builder for pipeline configurations |

### Comparison

| Class | Description |
|-------|-------------|
| `DualRunComparison` | Compare source vs target for migration validation |
| `ComparisonResult` | Single comparison check result |
| `ComparisonReport` | Complete comparison report |

---

## Dependencies

- Python 3.10+
- pytest >= 7.0.0
- google-cloud-bigquery >= 3.0.0
- google-cloud-storage >= 2.0.0
- google-cloud-pubsub >= 2.0.0

---

## Related Libraries

- **[gcp-pipeline-builder](../gcp-pipeline-builder/README.md)**: Core pipeline building library

---

## License

This library is part of the Legacy Migration Reference project.

