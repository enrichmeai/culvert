# GCP Pipeline Tester

A comprehensive testing framework for GCP data pipelines, providing mocks, fixtures, builders, and assertions for testing BigQuery, GCS, Pub/Sub, and Dataflow pipelines.

> **📖 Part of the GCP Pipeline Framework**
> This library provides testing utilities for pipelines built with `gcp-pipeline-core and gcp-pipeline-beam`.

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
  - [Record Assertions](#record-assertions)
  - [Beam Assertions](#beam-assertions)
  - [Pipeline Assertions](#pipeline-assertions)
- [Dual-Run Comparison](#dual-run-comparison)
- [BDD Testing](#bdd-testing)
  - [Data Quality Steps](#data-quality-steps)
  - [Pipeline Steps](#pipeline-steps)
- [Running Tests](#running-tests)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)

---

## Features

- **Base Test Classes**: `BasePipelineTest`, `BaseBeamTest`, `BaseValidationTest` - foundational test classes with common assertions
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
cd gcp-pipeline-libraries/gcp-pipeline-tester
pip install -e .

# Or with dev dependencies
pip install -e ".[dev]"
```

---

## Quick Start

### Basic Test with Base Class

```python
from gcp_pipeline_tester import BasePipelineTest

class TestMyPipeline(BasePipelineTest):
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

class TestWithMocks(BasePipelineTest):
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

### BasePipelineTest

Root test class with record assertions.

```python
from gcp_pipeline_tester import BasePipelineTest

class TestMyModule(BasePipelineTest):
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
            | beam.ParDo(RobustCsvParseDoFn(['id', 'name']))
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

### PubSubClientMock

Mock Pub/Sub client for messaging.

```python
from gcp_pipeline_tester.mocks import PubSubClientMock

def test_pubsub_operations():
    mock = PubSubClientMock()
    
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
from gcp_pipeline_tester.fixtures import sample_records, sample_config_dict

def test_with_sample_records(sample_records):
    """Use pre-generated sample records."""
    assert len(sample_records) > 0
    assert 'id' in sample_records[0]

def test_with_config(sample_config_dict):
    """Use sample pipeline config dictionary."""
    assert sample_config_dict['pipeline_name'] == 'test_pipeline'
```

### Available Fixtures

| Fixture | Description |
|---------|-------------|
| `sample_records` | List of sample record dictionaries |
| `sample_config_dict` | Sample PipelineConfig dictionary |
| `gcs_client_mock` | GCSClientMock instance |
| `bq_client_mock` | BigQueryClientMock instance |
| `test_pipeline` | Beam test pipeline |

---

## Assertions

Domain-specific assertion functions for various testing levels.

### Record Assertions

**Location**: `gcp_pipeline_tester.assertions.record_assertions`

Assertions for validating individual record dictionaries.

| Assertion | Description |
|-----------|-------------|
| `assert_field_exists(record, field)` | Ensure field is present |
| `assert_field_value(record, field, value)` | Check specific field value |
| `assert_record_structure(record, fields)` | Validate all required fields |

### Beam Assertions

**Location**: `gcp_pipeline_tester.assertions.beam_assertions`

Assertions for validating Apache Beam `PCollection` contents.

```python
from gcp_pipeline_tester.assertions import assert_pcollection_count, assert_pcollection_contains

# Verify record count in PCollection
assert_pcollection_count(pcollection, expected_count=10)

# Verify specific record exists in PCollection
assert_pcollection_contains(pcollection, expected_record)
```

### Pipeline Assertions

**Location**: `gcp_pipeline_tester.assertions.pipeline_assertions`

Assertions for high-level pipeline execution status.

| Assertion | Description |
|-----------|-------------|
| `assert_pipeline_success(audit_record)` | Verify `success` flag in audit |
| `assert_no_errors(error_handler)` | Ensure no errors were recorded |
| `assert_metrics_recorded(metrics)` | Verify metrics were emitted |
| `assert_audit_trail_complete(audit)` | Check for required audit fields |

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

### Data Quality Steps

**Location**: `gcp_pipeline_tester.bdd.steps.dq_steps`

Pre-built steps for testing data quality rules.

```gherkin
Given a record with ssn value "123-45-6789"
When I run the data quality validation
Then the record should be marked as valid
```

### Pipeline Steps

**Location**: `gcp_pipeline_tester.bdd.steps.pipeline_steps`

Steps for testing end-to-end pipeline execution.

```gherkin
Given a pipeline for entity "customers"
And a source file "gs://bucket/customers.csv"
When I execute the pipeline
Then the pipeline should complete successfully
And the target table should contain 100 records
```

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
from gcp_pipeline_tester.bdd import PipelineScenarioTest
from pytest_bdd import given, when, then, scenario

class TestSSNValidation(PipelineScenarioTest):
    
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

## Key Findings

### 1. Robust Mocking Infrastructure
- **Comprehensive Mocks**: Provides high-fidelity mock implementations for GCS, BigQuery, and Pub/Sub.
- **Stateless Testing**: Ensures that unit tests across the entire monorepo can run in isolated CI environments without requiring live GCP credentials or connectivity.

### 2. Standardized Base Classes
- **Foundational Support**: Includes `BasePipelineTest`, `BaseBeamTest`, and `BaseValidationTest` to enforce consistent testing patterns and provide common assertions.

### 3. BDD-Style Integration Testing
- **Complex Scenarios**: Supports Behavior-Driven Development (BDD) using Gherkin-style steps.
- **End-to-End Validation**: Facilitates testing of multi-stage pipelines (e.g., Discovery -> Ingestion -> Transformation) in a single scenario.

### 4. Dual-Run Comparison
- **Migration Verification**: Specialized utilities to compare outputs from legacy systems against GCP-processed results, ensuring parity.

---

## Governance & Compliance

- **Unified Strategy**: Integrated for a unified release and tagging strategy (`libs-1.0.x`).
- **Standardized Mocking**: Developers MUST use `tester` mocks instead of custom `unittest.mock.Mock` objects for GCP services to ensure consistency.
- **BDD Expansion**: Encouraged use of BDD scenarios for any new multi-stage orchestration or processing logic.

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
│       │   ├── pipeline_test.py # BasePipelineTest
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
| `BasePipelineTest` | Root test class with record assertions |
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
| `PubSubClientMock` | Mock Pub/Sub client |

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

- Python 3.9+
- pytest >= 7.0.0
- google-cloud-bigquery >= 3.0.0
- google-cloud-storage >= 2.0.0
- google-cloud-pubsub >= 2.0.0

---

## Related Libraries

- **[gcp-pipeline-core](../../gcp-pipeline-libraries/gcp-pipeline-core/README.md)** and **[gcp-pipeline-beam](../../gcp-pipeline-libraries/gcp-pipeline-beam/README.md)**: Core pipeline building libraries

---

## License

This library is part of the Legacy Migration Reference project.

