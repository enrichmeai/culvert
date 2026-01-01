# GitHub Copilot Context & Coding Standards

## Project Overview

This is a **legacy mainframe-to-GCP data migration framework** consisting of two main components:

1. **gdw_data_core** - Reusable Python library providing infrastructure components
2. **blueprint** - LOA (Application B Application) specific implementation using the library

**Tech Stack:**
- **Runtime**: Python 3.10+
- **Data Processing**: Apache Beam 2.49.0 (Dataflow runner)
- **Orchestration**: Apache Airflow 2.5+
- **Cloud Services**: GCP (BigQuery, GCS, Pub/Sub, Dataflow)
- **Validation**: Pydantic 2.0+
- **Configuration**: YAML
- **Transformations**: dbt (SQL macros)
- **Testing**: pytest, unittest, BDD/Gherkin

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│ Blueprint Layer (LOA-specific implementations)              │
│ - Extends library base classes                              │
│ - Contains business-specific logic                          │
├─────────────────────────────────────────────────────────────┤
│ Testing & Observability Layer                               │
│ - Base test classes, fixtures, mocks, assertions            │
│ - BDD framework with reusable step definitions              │
├─────────────────────────────────────────────────────────────┤
│ Pipeline Framework Layer (Apache Beam)                      │
│ - Base pipeline classes, transforms, I/O operations         │
│ - BeamPipelineBuilder (fluent API)                          │
├─────────────────────────────────────────────────────────────┤
│ Orchestration Layer (Airflow)                               │
│ - DAG factories, routing, sensors, operators, callbacks     │
├─────────────────────────────────────────────────────────────┤
│ Core Infrastructure Layer                                   │
│ - Validators, error handling, audit, monitoring             │
│ - GCS/BigQuery/PubSub clients                               │
│ - Data quality, file management, data deletion              │
└─────────────────────────────────────────────────────────────┘
```

---

## Module Structure Standards

### Rule: Use Submodules for Multiple Classes/Functions

When a module contains **multiple related classes or functions**, organize them into a **directory (submodule)** with separate files:

#### ✅ CORRECT - Directory Structure for Multiple Components

```
gdw_data_core/core/validators/
├── __init__.py          # Re-exports all public API
├── types.py             # Shared types (ValidationError)
├── ssn.py               # validate_ssn()
├── numeric.py           # validate_numeric_range()
├── date.py              # validate_date()
├── code.py              # validate_branch_code(), validate_entity_code()
└── generic.py           # validate_required(), validate_length()
```

#### ❌ INCORRECT - Single Large File

```
gdw_data_core/core/validators.py  # 500+ lines with everything
```

### File Naming Conventions

| File Type | Naming Pattern | Example |
|-----------|---------------|---------|
| Types/Enums/Dataclasses | `types.py` | `error_handling/types.py` |
| Base/Abstract Classes | `base.py` | `pipelines/base/pipeline.py` |
| Configuration | `config.py` | `orchestration/routing/config.py` |
| Models/Dataclasses | `models.py` | `error_handling/models.py` |
| Main Implementation | Descriptive name | `handler.py`, `router.py` |
| Storage Backends | `storage.py` | `error_handling/storage.py` |
| Context Managers | `context.py` | `error_handling/context.py` |

### `__init__.py` Pattern

Each submodule's `__init__.py` must:
1. Have a module docstring explaining purpose
2. Import and re-export all public APIs
3. Define `__all__` explicitly
4. Group imports by category with comments

```python
"""
GDW Data Core - Error Handling Framework

Production-grade error handling, classification, routing, and retry logic.
Provides centralized error management for data migration pipelines.

Used by: ALL pipelines, Beam transforms, Airflow DAGs
"""

from .types import ErrorSeverity, ErrorCategory, RetryStrategy
from .errors import GDWError, GDWValidationError, GDWTransformError
from .models import PipelineError, ErrorConfig
from .handler import ErrorHandler, ErrorClassifier, RetryPolicy
from .storage import ErrorStorageBackend, InMemoryErrorStorage, GCSErrorStorage
from .context import ErrorContext, with_error_handling

__all__ = [
    # Types
    'ErrorSeverity',
    'ErrorCategory',
    'RetryStrategy',
    # Exceptions
    'GDWError',
    'GDWValidationError',
    'GDWTransformError',
    # Models
    'PipelineError',
    'ErrorConfig',
    # Handler
    'ErrorHandler',
    'ErrorClassifier',
    'RetryPolicy',
    # Storage
    'ErrorStorageBackend',
    'InMemoryErrorStorage',
    'GCSErrorStorage',
    # Context
    'ErrorContext',
    'with_error_handling',
]
```

---

## Coding Standards

### Python Style

- **Type Hints**: Required for all function signatures
- **Docstrings**: Google-style docstrings for all public functions/classes
- **Line Length**: 100 characters max
- **Imports**: Group by stdlib, third-party, local (with blank lines between)

```python
"""
Module docstring explaining purpose.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from google.cloud import bigquery
from google.cloud import storage

from gdw_data_core.core.error_handling import ErrorHandler
from .types import ValidationError

logger = logging.getLogger(__name__)
```

### Dataclass Pattern

Use `@dataclass` for data structures with sensible defaults:

```python
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class ComparisonResult:
    """Result of a single comparison check."""
    check_name: str
    source_value: Any
    target_value: Any
    status: str  # "PASS", "WARN", "FAIL"
    message: str
    delta_percent: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### Enum Pattern

Use `Enum` for fixed sets of values:

```python
from enum import Enum


class ErrorSeverity(Enum):
    """Error severity levels"""
    CRITICAL = "CRITICAL"  # Data loss risk, immediate action needed
    HIGH = "HIGH"          # Processing blocked, manual intervention needed
    MEDIUM = "MEDIUM"      # Partial failure, can retry
    LOW = "LOW"            # Non-blocking issue, can continue
    INFO = "INFO"          # Informational only
```

### Class Inheritance Pattern

Library classes should be **generic and configurable**. Blueprint classes **extend with defaults**:

```python
# Library (gdw_data_core) - Generic base
class BasePubSubPullSensor(PubSubPullSensor):
    """Generic sensor with configurable filtering."""
    
    def __init__(
        self,
        *args,
        filter_extension: Optional[str] = None,  # Configurable
        metadata_xcom_key: str = "file_metadata",  # Configurable
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.filter_extension = filter_extension
        self.metadata_xcom_key = metadata_xcom_key


# Blueprint (LOA-specific) - Pre-configured wrapper
class LOAPubSubPullSensor(BasePubSubPullSensor):
    """LOA-specific sensor with defaults."""
    
    def __init__(self, *args, filter_ok_files: bool = True, **kwargs):
        super().__init__(
            *args,
            filter_extension='.ok' if filter_ok_files else None,
            metadata_xcom_key='loa_metadata',  # LOA-specific default
            **kwargs
        )
```

---

## Error Handling Standards

### Use Structured Error Types

```python
from gdw_data_core.core.error_handling import (
    GDWError,
    GDWValidationError,
    ErrorSeverity,
    ErrorCategory,
)

# Raise specific error types
raise GDWValidationError(
    message="SSN format invalid",
    field_name="ssn",
    severity=ErrorSeverity.MEDIUM,
)
```

### Use Error Context Manager

```python
from gdw_data_core.core.error_handling import ErrorContext, ErrorHandler

handler = ErrorHandler(pipeline_name="my_job", run_id="run_001")

with ErrorContext(handler):
    # Errors are automatically captured and classified
    result = process_data()
```

---

## Testing Standards

### Test File Structure

```
gdw_data_core/tests/
├── unit/
│   ├── core/
│   │   ├── test_validators.py
│   │   ├── test_error_handling.py
│   │   └── file_management/
│   │       └── test_archiver.py
│   ├── orchestration/
│   │   └── test_dag_factory.py
│   └── testing/
│       └── test_dual_run_comparison.py
├── pipelines/
│   └── test_beam_pipeline.py
└── conftest.py  # Shared fixtures
```

### Test Class Pattern

```python
"""Unit tests for DualRunComparison."""

import unittest
from unittest.mock import MagicMock, patch

from gdw_data_core.testing.comparison import (
    ComparisonResult,
    ComparisonReport,
    DualRunComparison,
)


class TestComparisonResult(unittest.TestCase):
    """Test ComparisonResult dataclass."""

    def test_create_pass_result(self):
        """Test creating a passing comparison result."""
        result = ComparisonResult(
            check_name="row_count",
            source_value=1000,
            target_value=1000,
            status="PASS",
            message="Row counts match",
        )
        self.assertEqual(result.status, "PASS")
```

### Use Base Test Classes

```python
from gdw_data_core.testing import BaseGDWTest, BaseBeamTest

class TestMyPipeline(BaseBeamTest):
    """Tests for my pipeline."""
    
    def test_record_processing(self):
        # BaseBeamTest provides pipeline fixtures
        pass
```

---

## GCP Service Patterns

### GCS Client Usage

```python
from gdw_data_core.core.clients import GCSClient

client = GCSClient(project_id="my-project")
content = client.read_file("gs://bucket/path/file.csv")
client.write_file("gs://bucket/output/result.json", json_content)
```

### BigQuery Client Usage

```python
from gdw_data_core.core.clients import BigQueryClient

client = BigQueryClient(project_id="my-project")
rows = client.query("SELECT * FROM dataset.table LIMIT 100")
client.insert_rows("dataset.table", records)
```

### Pub/Sub Client Usage

```python
from gdw_data_core.core.clients import PubSubClient

client = PubSubClient(project_id="my-project")
client.publish("topic-name", {"event": "file_ready", "path": "gs://..."})
```

---

## Apache Beam Patterns

### Transform (DoFn) Pattern

```python
import apache_beam as beam
from gdw_data_core.core.validators import validate_ssn


class ValidateRecordDoFn(beam.DoFn):
    """Validate records and route to valid/invalid outputs."""
    
    def process(self, record):
        errors = validate_ssn(record.get('ssn', ''))
        
        if errors:
            yield beam.pvalue.TaggedOutput('invalid', {
                'record': record,
                'errors': [str(e) for e in errors],
            })
        else:
            yield beam.pvalue.TaggedOutput('valid', record)
```

### Pipeline Builder Pattern

```python
from gdw_data_core.pipelines.beam import BeamPipelineBuilder

pipeline = (
    BeamPipelineBuilder(options=pipeline_options)
    .read_from_gcs("gs://bucket/input/*.csv")
    .parse_csv(headers=['id', 'name', 'ssn'])
    .validate(ValidateRecordDoFn())
    .write_to_bigquery("project:dataset.table")
    .build()
)

result = pipeline.run()
```

---

## Airflow/Orchestration Patterns

### DAG Factory Pattern

```python
from gdw_data_core.orchestration import DAGFactory, DAGConfig

factory = DAGFactory()
dag = factory.create_dag_from_dict({
    'dag_id': 'loa_daily_processing',
    'schedule_interval': '@daily',
    'default_args': {
        'owner': 'data-team',
        'retries': 3,
    },
})
```

### Sensor Pattern

```python
from blueprint.components.orchestration.airflow.sensors import LOAPubSubPullSensor

sensor = LOAPubSubPullSensor(
    task_id='wait_for_file',
    project_id='my-project',
    subscription='loa-notifications-sub',
    filter_ok_files=True,  # Only trigger on .ok files
)
```

---

## dbt Macros (SQL)

### Standard Audit Columns

```sql
-- Usage in dbt model:
SELECT
    id,
    name,
    amount
    {{ add_audit_columns() }}
FROM {{ source('raw', 'transactions') }}
```

### Available Macros

| Macro | Purpose |
|-------|---------|
| `add_audit_columns()` | Adds run_id, processed_timestamp, source_file |
| `apply_audit_columns(relation)` | ALTER TABLE to add audit columns |
| `create_audit_trail(source, dest)` | Create audit trail table |
| `data_quality_check(...)` | Data quality validation |
| `pii_masking(column, type)` | Mask PII data |

---

## Key Principles

1. **Library vs Blueprint**: Generic reusable code goes in `gdw_data_core`. LOA-specific code goes in `blueprint`.

2. **Extend, Don't Duplicate**: Blueprint classes should extend library base classes, not copy code.

3. **Configuration over Code**: Use YAML configuration where possible. Make components configurable.

4. **Type Safety**: Use type hints everywhere. Use `Optional[T]` for nullable values.

5. **Structured Errors**: Use library error types. Never raise plain `Exception`.

6. **Audit Everything**: Use `AuditTrail` for all pipeline executions. Include run_id everywhere.

7. **Test Coverage**: Unit tests required for all new code. Use library test base classes.

---

## Common Import Patterns

```python
# Validators
from gdw_data_core.core.validators import validate_ssn, ValidationError

# Error Handling
from gdw_data_core.core.error_handling import ErrorHandler, ErrorContext, GDWError

# Audit
from gdw_data_core.core.audit import AuditTrail, AuditRecord

# Monitoring
from gdw_data_core.core.monitoring import MetricsCollector, HealthChecker

# Clients
from gdw_data_core.core.clients import GCSClient, BigQueryClient, PubSubClient

# Orchestration
from gdw_data_core.orchestration import DAGFactory, DAGRouter
from gdw_data_core.orchestration.sensors import BasePubSubPullSensor

# Pipelines
from gdw_data_core.pipelines.base import BasePipeline, PipelineConfig
from gdw_data_core.pipelines.beam import BeamPipelineBuilder

# Testing
from gdw_data_core.testing import BaseGDWTest, BaseBeamTest
from gdw_data_core.testing.comparison import DualRunComparison
from gdw_data_core.testing.mocks import GCSClientMock, BigQueryClientMock
```

