# GitHub Copilot Context & Coding Standards

## Project Overview

This is a **legacy mainframe-to-GCP data migration framework** consisting of two main components:

1. **gcp-pipeline-builder** - Reusable Python library providing infrastructure components
2. **blueprint** - Implementation of two data pipelines (EM and LOA) using the library

**Tech Stack:**
- **Runtime**: Python 3.11+
- **Data Processing**: Apache Beam 2.49.0 (Dataflow runner)
- **Orchestration**: Apache Airflow 2.5+
- **Cloud Services**: GCP (BigQuery, GCS, Pub/Sub, Dataflow)
- **Validation**: Pydantic 2.0+
- **Configuration**: YAML
- **Transformations**: dbt (SQL macros)
- **Testing**: pytest, unittest, BDD/Gherkin

---

## Pipeline Systems

The blueprint implements two data migration pipelines:

### EM (Application A) Pipeline
| Attribute | Value |
|-----------|-------|
| **Source Entities** | 3 (Customers, Accounts, Decision) |
| **ODP Tables** | 3 (`odp_em.customers`, `odp_em.accounts`, `odp_em.decision`) |
| **FDP Tables** | 1 (`fdp_em.em_attributes`) |
| **Transformation** | JOIN 3 sources → 1 target |
| **Dependency** | Wait for all 3 entities before FDP transformation |

### LOA (Application B Application) Pipeline
| Attribute | Value |
|-----------|-------|
| **Source Entities** | 1 (Applications) |
| **ODP Tables** | 1 (`odp_loa.applications`) |
| **FDP Tables** | 2 (`fdp_loa.event_transaction_excess`, `fdp_loa.portfolio_account_excess`) |
| **Transformation** | SPLIT 1 source → 2 targets |
| **Dependency** | No wait - immediate trigger after ODP load |

### File Format (Both Systems)
```
HDR|{SYSTEM}|{ENTITY}|{YYYYMMDD}     ← Header record
{csv_header_row}                      ← Column names
{data_row_1}                          ← Data records
...
TRL|RecordCount={n}|Checksum={hash}   ← Trailer record
```

### Key Library Components
```python
# File Management
from gcp_pipeline_core.file_management import HDRTRLParser, validate_record_count, validate_checksum

# Job Control
from gcp_pipeline_core.job_control import JobControlRepository, JobStatus, PipelineJob

# Entity Dependency
from gcp_pipeline_orchestration import EntityDependencyChecker

# Data Quality
from gcp_pipeline_core.data_quality import validate_row_types, check_duplicate_keys
```

### Library Design: Generic with Pipeline Configuration

| Component | Library Provides | Pipeline Provides |
|-----------|------------------|-------------------|
| `HDRTRLParser` | Parsing mechanism | Patterns, prefixes (or use defaults) |
| `EntityDependencyChecker` | Dependency checking | system_id, required_entities |
| `ParseCsvLine` | CSV parsing DoFn | headers, hdr/trl prefixes |
| `validate_row_types` | Validation logic | hdr_prefix, trl_prefix |
| `JobControlRepository` | CRUD operations | project_id, dataset, table |

**Default patterns for CSV extracts:**
```python
DEFAULT_HDR_PATTERN = r'^HDR\|([^|]+)\|([^|]+)\|(\d{8})$'
DEFAULT_TRL_PATTERN = r'^TRL\|RecordCount=(\d+)\|Checksum=([^|]+)$'
```

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│ Blueprint Layer (EM and LOA implementations)                │
│ - Extends library base classes                              │
│ - Contains system-specific logic                            │
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

**When to create a submodule (directory with `__init__.py`):**
- Module has **more than 1 class**
- Module has **more than 3 related functions**
- File would exceed **200 lines**
- Components have distinct responsibilities

Organize them into a **directory (submodule)** with separate files:

#### ✅ CORRECT - Directory Structure for Multiple Components

```
gcp_pipeline_core/core/validators/
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
gcp_pipeline_core/core/validators.py  # 500+ lines with everything
```

### Test Structure Must Mirror Source Structure

Tests MUST mirror the source module structure exactly. No backward compatibility files needed.

#### ✅ CORRECT - Tests Mirror Source (1:1 mapping)

```
# Source structure
gcp_pipeline_core/core/job_control/
├── __init__.py
├── types.py
├── models.py
└── repository.py

# Test structure mirrors source EXACTLY
gcp_pipeline_core/tests/unit/core/job_control/
├── __init__.py
├── test_types.py          # Tests for types.py
├── test_models.py         # Tests for models.py
└── test_repository.py     # Tests for repository.py
```

#### ❌ INCORRECT - Single Test File or Backward Compat Files

```
gcp_pipeline_core/tests/unit/core/test_job_control.py  # All tests in one file - WRONG
gcp_pipeline_core/tests/unit/core/test_job_control.py  # Backward compat file - NOT NEEDED
```

### When Refactoring to Submodules

When splitting a large file into a submodule:
1. Create the submodule directory with properly split files
2. **DELETE** the original single file (no backward compatibility needed)
3. Update `__init__.py` to re-export public API
4. Move/split tests to mirror new structure
5. **DELETE** old single test file

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

from gcp_pipeline_core.error_handling import ErrorHandler
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
# Library (gcp-pipeline-builder) - Generic base
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
from gcp_pipeline_core.error_handling import (
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
from gcp_pipeline_core.error_handling import ErrorContext, ErrorHandler

handler = ErrorHandler(pipeline_name="my_job", run_id="run_001")

with ErrorContext(handler):
    # Errors are automatically captured and classified
    result = process_data()
```

---

## Testing Standards

### Test File Structure

```
gcp_pipeline_core/tests/
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

from gcp_pipeline_core.testing import (
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
from gcp_pipeline_core.testing import BaseGDWTest, BaseBeamTest

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
from gcp_pipeline_core.clients import GCSClient

client = GCSClient(project_id="my-project")
content = client.read_file("gs://bucket/path/file.csv")
client.write_file("gs://bucket/output/result.json", json_content)
```

### BigQuery Client Usage

```python
from gcp_pipeline_core.clients import BigQueryClient

client = BigQueryClient(project_id="my-project")
rows = client.query("SELECT * FROM dataset.table LIMIT 100")
client.insert_rows("dataset.table", records)
```

### Pub/Sub Client Usage

```python
from gcp_pipeline_core.clients import PubSubClient

client = PubSubClient(project_id="my-project")
client.publish("topic-name", {"event": "file_ready", "path": "gs://..."})
```

---

## Apache Beam Patterns

### Transform (DoFn) Pattern

```python
import apache_beam as beam
from gcp_pipeline_core.validators import validate_ssn


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
from gcp_pipeline_beam.pipelines.beam import BeamPipelineBuilder

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
from gcp_pipeline_orchestration import DAGFactory, DAGConfig

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
from blueprint.em.components.orchestration.airflow.sensors import LOAPubSubPullSensor

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

1. **Library vs Blueprint**: Generic reusable code goes in `gcp-pipeline-builder`. System-specific code (EM, LOA) goes in `blueprint`.

2. **Extend, Don't Duplicate**: Blueprint classes should extend library base classes, not copy code.

3. **Configuration over Code**: Use YAML configuration where possible. Make components configurable.

4. **Type Safety**: Use type hints everywhere. Use `Optional[T]` for nullable values.

5. **Structured Errors**: Use library error types. Never raise plain `Exception`.

6. **Audit Everything**: Use `AuditTrail` for all pipeline executions. Include run_id everywhere.

7. **Test Coverage**: Unit tests required for all new code. Use library test base classes.

8. **EM vs LOA Patterns**: EM uses dependency wait (3 entities → 1 FDP), LOA uses immediate trigger (1 entity → 2 FDP).

9. **HDR/TRL Validation**: Always validate header/trailer records before processing data.

10. **Job Control**: Always create job record before processing, update status on completion/failure.

---

## Implementation Workflow (MANDATORY)

**Never make ad-hoc changes. Always follow this workflow:**

### Step 1: Analyse
- Review existing code and documentation
- Identify what exists vs what needs to change
- Reference E2E documentation for requirements

### Step 2: Create/Update Prompt
- Document all changes in a prompt file (e.g., `LIBRARY_FIX_PROMPT.md`)
- Include: current state, required changes, implementation details
- Track changes against the prompt

### Step 3: Request Approval
- Present the prompt to user for review
- Wait for explicit approval before implementing
- Address any feedback

### Step 4: Implement
- Follow the approved prompt exactly
- Make changes as documented
- Run tests to validate

### Step 5: Verify
- Check implementation matches prompt
- Update prompt status to "Completed"
- Document any deviations

### Key Prompt Files
| Prompt | Purpose | Status |
|--------|---------|--------|
| `docs/LIBRARY_FIX_PROMPT.md` | Library gap fixes | Ready |
| `docs/BLUEPRINT_IMPLEMENTATION_PROMPT.md` | EM/LOA implementation | Ready |
| `docs/E2E_FUNCTIONAL_FLOW.md` | Requirements reference | Complete |

10. **Job Control**: Always create job record before processing, update status on completion/failure.

---

## Key Terms (Reference)

| Term | Definition |
|------|------------|
| **ODP** | Original Data Product - Raw 1:1 copy of mainframe data in BigQuery |
| **FDP** | Foundation Data Product - Transformed, business-ready data |
| **HDR** | Header record: `HDR|{SYSTEM}|{ENTITY}|{YYYYMMDD}` |
| **TRL** | Trailer record: `TRL|RecordCount={n}|Checksum={hash}` |
| **.ok file** | Signal file indicating transfer completion (triggers pipeline) |

---

## Error Codes (Reference)

| Error Code | Stage | Description |
|------------|-------|-------------|
| `FILE_NOT_FOUND` | File Discovery | Expected data files not found |
| `HDR_INVALID` | File Validation | Invalid or missing header record |
| `TRL_INVALID` | File Validation | Invalid or missing trailer record |
| `RECORD_COUNT_MISMATCH` | File Validation | Trailer count doesn't match actual |
| `CHECKSUM_MISMATCH` | File Validation | Checksum validation failed |
| `DQ_ROW_TYPE` | Data Quality | Row type validation failed |
| `DQ_DATA_TYPE` | Data Quality | Data type validation failed |
| `DQ_MANDATORY_FIELD` | Data Quality | Mandatory field missing |
| `DQ_DUPLICATE_PK` | Data Quality | Duplicate primary keys found |
| `DATAFLOW_FAILED` | ODP Load | Dataflow pipeline failed |
| `BQ_LOAD_FAILED` | ODP Load | BigQuery load failed |

---

## Job Status Values (Reference)

| Status | Description |
|--------|-------------|
| `PENDING` | Job created, waiting to start |
| `RUNNING` | Pipeline currently executing |
| `SUCCESS` | Pipeline completed successfully |
| `FAILED` | Pipeline failed (see error_code) |
| `RETRYING` | Automatic retry in progress |
| `QUARANTINED` | Manual intervention required |

---

## Audit Columns (Added to All Tables)

| Column | Type | Description |
|--------|------|-------------|
| `_run_id` | STRING | Unique pipeline execution ID |
| `_source_file` | STRING | Source file name |
| `_processed_ts` | TIMESTAMP | When record was loaded |
| `_extract_date` | DATE | Extract date from HDR record |
| `_transformed_ts` | TIMESTAMP | When record was transformed (FDP only) |

---

## BigQuery Datasets

| Dataset | Purpose | Tables |
|---------|---------|--------|
| `odp_em` | EM Original Data Product | customers, accounts, decision |
| `fdp_em` | EM Foundation Data Product | em_attributes |
| `odp_loa` | LOA Original Data Product | applications |
| `fdp_loa` | LOA Foundation Data Product | event_transaction_excess, portfolio_account_excess |
| `job_control` | Pipeline job tracking | pipeline_jobs |

---

## Common Import Patterns

```python
# Validators
from gcp_pipeline_core.validators import validate_ssn, ValidationError

# Error Handling
from gcp_pipeline_core.error_handling import ErrorHandler, ErrorContext, GDWError

# Audit
from gcp_pipeline_core.audit import AuditTrail, AuditRecord

# Monitoring
from gcp_pipeline_core.monitoring import MetricsCollector, HealthChecker

# Clients
from gcp_pipeline_core.clients import GCSClient, BigQueryClient, PubSubClient

# Orchestration
from gcp_pipeline_orchestration import DAGFactory, DAGRouter
from gcp_pipeline_orchestration.sensors import BasePubSubPullSensor

# Pipelines
from gcp_pipeline_beam.pipelines.base import BasePipeline, PipelineConfig
from gcp_pipeline_beam.pipelines.beam import BeamPipelineBuilder

# Testing
from gcp_pipeline_core.testing import BaseGDWTest, BaseBeamTest
from gcp_pipeline_core.testing import DualRunComparison
from gcp_pipeline_core.testing import GCSClientMock, BigQueryClientMock

# File Management
from gcp_pipeline_core.file_management import (
    HDRTRLParser,
    validate_record_count,
    validate_checksum,
)

# Data Quality
from gcp_pipeline_core.data_quality import validate_row_types, check_duplicate_keys

# Job Control
from gcp_pipeline_core.job_control import JobControlRepository, JobStatus, PipelineJob

# Entity Dependencies
from gcp_pipeline_orchestration.dependency import EntityDependencyChecker
```

---

## 🚀 IMPLEMENTING NEW PIPELINES (CRITICAL)

### Golden Rule: NEVER Duplicate Library Code

The library (`gcp-pipeline-builder`) provides all infrastructure. New pipelines:
1. **IMPORT** library components
2. **CONFIGURE** with system-specific values
3. **EXTEND** base classes only when adding new behavior
4. **NEVER** copy/paste library code into pipeline

### Pipeline Directory Structure

Each new pipeline system should follow this structure:

```
blueprint/components/{system_name}/
├── __init__.py           # Exports all public API
├── config.py             # System-specific configuration constants
├── schema.py             # Entity schemas (extend library base if available)
├── validation.py         # Validator using library components
├── transforms.py         # System-specific Beam DoFns
├── pipeline.py           # Main pipeline class
└── dags/
    └── {system}_daily.py # Airflow DAG

blueprint/tests/{system_name}/
├── __init__.py
├── test_validation.py
├── test_transforms.py
└── test_pipeline.py
```

### Step-by-Step: Creating a New Pipeline

#### Step 1: Create Configuration (`config.py`)

Define system-specific constants. **Library is generic, pipeline provides config.**

```python
"""
{SYSTEM} Pipeline Configuration.

System-specific configuration for the library components.
"""

# System identification
SYSTEM_ID = "NEW_SYSTEM"

# Entity dependencies (for EntityDependencyChecker)
REQUIRED_ENTITIES = ["entity_a", "entity_b"]

# GCS paths
LANDING_BUCKET = "gs://landing-{env}/{system}"
ARCHIVE_BUCKET = "gs://archive-{env}/{system}"

# BigQuery datasets
ODP_DATASET = "odp_{system}"
FDP_DATASET = "fdp_{system}"

# Job control
JOB_CONTROL_DATASET = "job_control"
JOB_CONTROL_TABLE = "pipeline_jobs"
```

#### Step 2: Create Validation (`validation.py`)

**Use library components, don't reimplement.**

```python
"""
{SYSTEM} Entity Validation.

Uses gcp-pipeline-builder library components - NO DUPLICATION.
"""

from typing import Dict, List, Optional
from datetime import date
from dataclasses import dataclass

# IMPORT library components
from gcp_pipeline_core.validators import (
    validate_ssn,
    validate_required,
    ValidationError,
)
from gcp_pipeline_core.data_quality import validate_row_types, check_duplicate_keys
from gcp_pipeline_core.file_management import (
    HDRTRLParser,
    validate_record_count,
    validate_checksum,
)

# Import system-specific schema
from .schema import MY_SCHEMAS
from .config import SYSTEM_ID, REQUIRED_ENTITIES


@dataclass
class ValidationResult:
    """Result of validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    record_count: int = 0


class MySystemValidator:
    """
    Validator for {SYSTEM} entities.

    Uses library validators internally.
    """

    # System-specific config provided to library
    SYSTEM_ID = SYSTEM_ID
    REQUIRED_ENTITIES = REQUIRED_ENTITIES

    def __init__(self):
        # Use library parser with defaults (works for CSV extracts)
        self.hdr_trl_parser = HDRTRLParser()

    def validate_file(
        self,
        file_lines: List[str],
        entity_name: str,
        expected_extract_date: Optional[date] = None
    ) -> ValidationResult:
        """
        Validate an entity file.

        Uses library functions - NOT reimplemented here.
        """
        errors = []
        warnings = []

        # Step 1: Use LIBRARY function for row type validation
        is_valid, msg = validate_row_types(file_lines)
        if not is_valid:
            errors.append(f"Row type validation failed: {msg}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Step 2: Use LIBRARY parser for HDR/TRL
        try:
            metadata = self.hdr_trl_parser.parse_file_lines(file_lines)
        except ValueError as e:
            errors.append(f"HDR/TRL parsing failed: {str(e)}")
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Step 3: System-specific validation (header content)
        if metadata.header.system_id != self.SYSTEM_ID:
            errors.append(f"System ID mismatch: expected {self.SYSTEM_ID}")

        # Step 4: Use LIBRARY function for record count
        is_valid, msg = validate_record_count(
            file_lines,
            expected_count=metadata.trailer.record_count,
            has_csv_header=True
        )
        if not is_valid:
            errors.append(f"Record count: {msg}")

        # Step 5: Use LIBRARY function for checksum
        data_lines = file_lines[metadata.data_start_line:metadata.data_end_line + 1]
        is_valid, msg = validate_checksum(data_lines, metadata.trailer.checksum)
        if not is_valid:
            errors.append(f"Checksum: {msg}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            record_count=len(data_lines) - 1,
        )

    def check_duplicates(self, records: List[Dict], entity_name: str):
        """Use LIBRARY function for duplicate detection."""
        schema = MY_SCHEMAS.get(entity_name)
        # Library function - NOT reimplemented
        return check_duplicate_keys(records, schema.primary_key)
```

#### Step 3: Entity Dependency (For Multi-Entity Systems)

**Configure library checker, don't create your own.**

```python
"""
{SYSTEM} Entity Dependency Checking.

Uses library EntityDependencyChecker with system config.
"""

from datetime import date
from gcp_pipeline_orchestration.dependency import EntityDependencyChecker
from .config import SYSTEM_ID, REQUIRED_ENTITIES, PROJECT_ID


def create_dependency_checker(project_id: str = None) -> EntityDependencyChecker:
    """
    Create dependency checker for this system.

    Library provides the mechanism, we provide the config.
    """
    return EntityDependencyChecker(
        project_id=project_id or PROJECT_ID,
        system_id=SYSTEM_ID,
        required_entities=REQUIRED_ENTITIES,
    )


def all_entities_ready(extract_date: date, project_id: str = None) -> bool:
    """Check if all required entities are loaded."""
    checker = create_dependency_checker(project_id)
    return checker.all_entities_loaded(extract_date)
```

#### Step 4: Beam Transforms

**Extend library DoFns, add system-specific validation.**

```python
"""
{SYSTEM} Beam Transforms.

Extends library transforms with system-specific logic.
"""

import apache_beam as beam
from typing import Dict, Iterator

from gcp_pipeline_core.validators import validate_ssn
from gcp_pipeline_beam.pipelines.beam.transforms import ParseCsvLine

from .schema import MY_ENTITY_HEADERS
from .validation import MySystemValidator


class ValidateMyEntityDoFn(beam.DoFn):
    """
    Validate {SYSTEM} entity records.

    Uses library validators internally.
    """

    def __init__(self, entity_name: str):
        super().__init__()
        self.entity_name = entity_name
        self.validator = MySystemValidator()

    def process(self, record: Dict) -> Iterator[Dict]:
        # Use system validator (which uses library functions)
        errors = self.validator._validate_record(record, self.entity_name)

        if errors:
            yield beam.pvalue.TaggedOutput('invalid', {
                'record': record,
                'errors': errors,
            })
        else:
            yield beam.pvalue.TaggedOutput('valid', record)
```

### ❌ ANTI-PATTERNS (DO NOT DO)

#### Don't Reimplement Library Functions

```python
# ❌ WRONG - Reimplementing what library provides
def my_validate_row_types(file_lines):
    if not file_lines[0].startswith("HDR|"):
        return False, "No header"
    # ... reimplementing library logic

# ✅ CORRECT - Use library function
from gcp_pipeline_core.data_quality import validate_row_types
is_valid, msg = validate_row_types(file_lines)
```

#### Don't Copy Library Classes

```python
# ❌ WRONG - Copying HDRTRLParser class into pipeline
class MyHDRTRLParser:
    def __init__(self):
        self.hdr_pattern = ...  # Copy-pasted from library

# ✅ CORRECT - Import and use library class
from gcp_pipeline_core.file_management import HDRTRLParser
parser = HDRTRLParser()  # Use defaults for CSV extracts
```

#### Don't Hardcode What Should Be Configured

```python
# ❌ WRONG - Hardcoding in library
# In gcp_pipeline_core/orchestration/dependency.py
SYSTEM_DEPENDENCIES = {
    "em": {"entities": ["customers", "accounts"]},  # NO!
}

# ✅ CORRECT - Pipeline provides config to library
# In blueprint/components/em/config.py
REQUIRED_ENTITIES = ["customers", "accounts", "decision"]

# In blueprint/components/em/dependency.py
checker = EntityDependencyChecker(
    project_id=PROJECT_ID,
    system_id="em",
    required_entities=REQUIRED_ENTITIES,  # Config provided
)
```

### Reference Implementation: EM Validator

See `blueprint/components/em/validation.py` for the correct pattern:

```python
# CORRECT PATTERN - EM uses library components

from gcp_pipeline_core.validators import validate_ssn, ValidationError
from gcp_pipeline_core.data_quality import validate_row_types, check_duplicate_keys
from gcp_pipeline_core.file_management import (
    HDRTRLParser,
    validate_record_count,
    validate_checksum,
)

class EMValidator:
    SYSTEM_ID = "EM"  # System-specific
    REQUIRED_ENTITIES = ["customers", "accounts", "decision"]  # System-specific

    def __init__(self):
        self.hdr_trl_parser = HDRTRLParser()  # Library component

    def validate_file(self, file_lines, entity_name, ...):
        # Uses library: validate_row_types()
        # Uses library: self.hdr_trl_parser.parse_file_lines()
        # Uses library: validate_record_count()
        # Uses library: validate_checksum()
        # System-specific: header.system_id == self.SYSTEM_ID check
```

### Checklist: New Pipeline Implementation

- [ ] Created `config.py` with system-specific constants
- [ ] Created `schema.py` with entity definitions
- [ ] Created `validation.py` that **imports** library components
- [ ] **NO** library functions reimplemented in pipeline code
- [ ] Used `EntityDependencyChecker` with system config (not hardcoded)
- [ ] Used `HDRTRLParser` from library (not reimplemented)
- [ ] Used `validate_row_types`, `validate_record_count`, `validate_checksum` from library
- [ ] Used `check_duplicate_keys` from library
- [ ] Extended library base classes, didn't copy them
- [ ] Tests use library test base classes and mocks

---

## EM Implementation Completion Checklist

**Status: ✅ COMPLETE**  
**Last Updated: January 2, 2026**

### 📋 FILES TO DELETE (LOA remnants in EM deployment) - ✅ DONE

All LOA files have been removed from the EM deployment.

### ✅ COMPLETED Components

#### Source Files
- [x] `deployments/em/config/__init__.py` - Exports SCORE_MIN, SCORE_MAX
- [x] `deployments/em/config/constants.py` - EM constants defined
- [x] `deployments/em/config/settings.py` - SYSTEM_ID="EM"
- [x] `deployments/em/domain/schema.py` - EM schemas (customers, accounts, decision)
- [x] `deployments/em/domain/__init__.py` - Exports EM schemas
- [x] `deployments/em/pipeline/em_pipeline.py` - EM pipeline created
- [x] `deployments/em/pipeline/__init__.py` - Exports EM pipeline components
- [x] `deployments/em/validation/*` - Already EM-specific

#### Test Files (Mirrored Structure)
- [x] `deployments/em/tests/conftest.py` - EM fixtures
- [x] `deployments/em/tests/unit/config/test_config.py`
- [x] `deployments/em/tests/unit/domain/test_schema.py`
- [x] `deployments/em/tests/unit/pipeline/test_em_pipeline.py`
- [x] `deployments/em/tests/unit/validation/test_validator.py`

#### Test Data
- [x] `deployments/em/tests/data/em_customers_sample.csv`
- [x] `deployments/em/tests/data/em_accounts_sample.csv`
- [x] `deployments/em/tests/data/em_decision_sample.csv`

#### dbt Transformations
- [x] `deployments/em/transformations/dbt/dbt_project.yml` - Updated for EM
- [x] `deployments/em/transformations/dbt/models/staging/em/_em_sources.yml`
- [x] `deployments/em/transformations/dbt/models/staging/em/stg_em_*.sql`
- [x] `deployments/em/transformations/dbt/models/fdp/em_attributes.sql`
- [x] `deployments/em/transformations/dbt/models/fdp/_fdp_em_models.yml`

#### GitHub Workflows
- [x] `.github/workflows/gcp-deployment-tests.yml` - Updated for deployments/ paths
- [x] `.github/workflows/deploy.yml` - Updated for EM

### 🧪 Verification Commands

```bash
# Run EM unit tests
cd /path/to/legacy-migration-reference
PYTHONPATH=. pytest deployments/em/tests/unit/ -v

# Validate imports
python -c "
from deployments.em.config import SYSTEM_ID, SCORE_MIN, SCORE_MAX
from deployments.em.domain.schema import EM_SCHEMAS, get_schema
from deployments.em.pipeline.em_pipeline import EM_ENTITY_CONFIG
from deployments.em.validation import EMValidator
print('✅ All EM imports OK')
"
```

---

## LOA Implementation Checklist

**Status: Ready for Implementation**  
**Prompt:** `docs/LOA_IMPLEMENTATION_PROMPT.md`  
**Last Updated: January 2, 2026**

### 📊 LOA Overview

| Attribute | Value |
|-----------|-------|
| **System ID** | `LOA` |
| **Source Entities** | 1 (Applications) |
| **ODP Tables** | 1 (`odp_loa.applications`) |
| **FDP Tables** | 2 (`fdp_loa.event_transaction_excess`, `fdp_loa.portfolio_account_excess`) |
| **Transformation** | SPLIT 1 source → 2 targets |
| **Dependency** | No wait - immediate trigger after ODP load |

### Key Difference from EM

| Aspect | EM | LOA |
|--------|-----|-----|
| Entities | 3 (Customers, Accounts, Decision) | 1 (Applications) |
| FDP Transformation | JOIN (3→1) | SPLIT (1→2) |
| Dependency Wait | Yes (all 3 entities) | No (immediate) |
| FDP Tables | 1 | 2 |

### 📁 Directory Structure

```
deployments/loa/
├── config/           # SYSTEM_ID="LOA", constants
├── schema/           # LOAApplicationsSchema
├── domain/           # BigQuery schemas (1 ODP + 2 FDP)
├── validation/       # LOAValidator
├── pipeline/         # loa_pipeline.py, dag_template.py
├── orchestration/    # Airflow DAGs
├── transformations/  # dbt models (SPLIT to 2 FDP)
└── tests/            # Unit tests (mirror structure)
```

### ✅ Implementation Tasks

See `docs/LOA_IMPLEMENTATION_PROMPT.md` for complete implementation details.

- [ ] Config module (SYSTEM_ID, constants)
- [ ] Schema module (LOAApplicationsSchema)
- [ ] Domain module (BigQuery schemas)
- [ ] Validation module (LOAValidator)
- [ ] Pipeline module (loa_pipeline.py)
- [ ] Orchestration (Airflow DAGs)
- [ ] dbt transformations (staging + 2 FDP)
- [ ] Tests (unit + integration)
- [ ] Root files (__init__.py, README.md)

