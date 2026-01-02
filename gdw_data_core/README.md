# GDW Data Core Library

A production-grade Python framework providing reusable components for data migration pipelines. Decouples core infrastructure (validation, error handling, audit, monitoring) from specific business implementations.

**Status**: ✅ 513/513 tests passing | Production ready

> **📖 Part of the Legacy Mainframe to GCP Migration Framework**  
> This library is the foundation for all migration pipelines. See the [Root README](../README.md) for framework objectives, architecture decisions, and how EM/LOA deployments use this library.
>
> **Reference Implementations:**
> - [EM Deployment](../deployments/em/) - Multi-entity JOIN pattern (3 → 1)
> - [LOA Deployment](../deployments/loa/) - Single-entity SPLIT pattern (1 → 2)

---

## Quick Start

### Installation

```bash
# Install in editable mode for development
pip install -e ./gdw_data_core

# Or in your requirements.txt
-e path/to/gdw_data_core
```

### Minimal Example

```python
from gdw_data_core.core.validators import validate_ssn
from gdw_data_core.core.error_handling import ErrorContext, ErrorHandler
from gdw_data_core.core.audit import AuditTrail
from gdw_data_core.core.monitoring import MetricsCollector

# Validate data
errors = validate_ssn("123-45-6789")

# Handle errors with automatic classification and retry
handler = ErrorHandler(pipeline_name="my_job", run_id="run_001")
with ErrorContext(handler):
    result = process_data()

# Track execution
audit = AuditTrail(run_id="run_001", pipeline_name="my_job", entity_type="applications")
audit.record_processing_start("gs://bucket/input.csv")
audit.increment_counts(valid=100, errors=5)
audit.record_processing_end(success=True)

# Collect metrics
metrics = MetricsCollector(pipeline_name="my_job", run_id="run_001")
metrics.increment("records_processed", 100)
stats = metrics.get_statistics()
```

---

## Architecture

The library is organized into 4 layers:

```
┌────────────────────────────────────────────────────────┐
│ Testing & Observability Layer                          │
│ (Base test classes, fixtures, mocks, assertions)       │
├────────────────────────────────────────────────────────┤
│ Pipeline Framework Layer                               │
│ (Apache Beam: base pipeline, transforms, I/O ops)      │
├────────────────────────────────────────────────────────┤
│ Core Infrastructure Layer                              │
│ (Validators, error handling, audit, monitoring)        │
├────────────────────────────────────────────────────────┤
│ Data Operations & Orchestration Layer                  │
│ (GCS/BigQuery clients, DAG factory, utilities)         │
└────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

- **Data Operations**: GCS/BigQuery clients, utilities for run ID generation, file discovery
- **Core Infrastructure**: Core business logic - validation, error classification, audit trails, metrics
- **Pipeline Framework**: Apache Beam integration - transforms, I/O operations, lifecycle management
- **Testing**: Test utilities - base classes, fixtures, mocks, assertions, and BDD (Gherkin) framework for comprehensive testing
- **BDD Framework**: Reusable step definitions (SSN, Pipeline, Data Quality) and scenario runners to bridge the gap between business requirements and technical implementation.

---

## Architecture Diagram - Detailed Component View

### Component Organization

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         APPLICATION LAYER                                       │
│                                                                                  │
│    Your Custom Pipelines  │  Your Business Logic  │  Your Custom Transforms     │
└──────────────────┬─────────────────────────────────────┬──────────────────────┘
                   │                                     │
        ┌──────────┴─────────────────────────────────────┴──────────┐
        │                                                           │
┌──────▼──────────────────────────────────────────────────────────▼──────┐
│                  TESTING & OBSERVABILITY LAYER                          │
│  ┌─────────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │  Base Classes   │  │   Fixtures   │  │ Mock Objects│  │Assertions│ │
│  │ ─────────────── │  │ ──────────── │  │ ─────────── │  │──────────│ │
│  │ BaseGDWTest     │  │ sample_*     │  │ GCSMock     │  │ assert_* │ │
│  │ BaseValidTest   │  │ test_*       │  │ BQMock      │  │ custom   │ │
│  │ BaseBeamTest    │  │ factories    │  │ PubSubMock  │  │ checks   │ │
│  └─────────────────┘  └──────────────┘  └─────────────┘  └──────────┘ │
└──────────────────────────────────────────────────────────────────────┬──┘
                                                                        │
        ┌───────────────────────────────────────────────────────────────┴────┐
        │                                                                     │
┌──────▼──────────────────────────────────────────────────────────────────┐   │
│                   PIPELINE FRAMEWORK LAYER                              │   │
│                    (Apache Beam Integration)                            │   │
│                                                                         │   │
│  ┌──────────────────────────────────────────────────────────────────┐  │   │
│  │ Base Pipeline Classes                                            │  │   │
│  │ ─────────────────────────────────────────────────────────────    │  │   │
│  │  • BasePipeline (abstract base with lifecycle)                  │  │   │
│  │  • PipelineConfig (configuration dataclass)                      │  │   │
│  │  • GDWPipelineOptions (Beam PipelineOptions extended)           │  │   │
│  └──────────────────────────────────────────────────────────────────┘  │   │
│                                                                         │   │
│  ┌─────────────────────────┐  ┌────────────────────────────────────┐  │   │
│  │ Beam Transforms (DoFn)  │  │ Beam I/O Operations                │  │   │
│  │ ──────────────────────  │  │ ───────────────────────            │  │   │
│  │ • ParseCsvLine          │  │ GCS Operations:                    │  │   │
│  │ • ValidateRecordDoFn    │  │ • ReadFromGCSDoFn                  │  │   │
│  │ • FilterRecordsDoFn     │  │ • WriteToGCSDoFn                   │  │   │
│  │ • TransformRecordDoFn   │  │ • ReadCSVFromGCSDoFn               │  │   │
│  │ • EnrichWithMetadataFn  │  │ • WriteCSVToGCSDoFn                │  │   │
│  │ • DeduplicateRecordsFn  │  │                                    │  │   │
│  │                         │  │ BigQuery Operations:               │  │   │
│  │ (all with metrics)      │  │ • WriteToBigQueryDoFn              │  │   │
│  │                         │  │ • BatchWriteToBigQueryDoFn         │  │   │
│  │                         │  │                                    │  │   │
│  │                         │  │ Pub/Sub Operations:                │  │   │
│  │                         │  │ • PublishToPubSubDoFn              │  │   │
│  │                         │  │                                    │  │   │
│  │                         │  │ Builder:                           │  │   │
│  │                         │  │ • BeamPipelineBuilder (fluent API) │  │   │
│  └─────────────────────────┘  └────────────────────────────────────┘  │   │
│                                                                         │   │
└─────────────────────────────────────────────────────────────────────┬──┘   │
                                                                      │       │
        ┌─────────────────────────────────────────────────────────────┴───────┤
        │                                                                     │
┌──────▼──────────────────────────────────────────────────────────────────────▼──┐
│                      CORE INFRASTRUCTURE LAYER                                   │
│                     (Reusable Business Logic)                                    │
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │ Validators Module (gdw_data_core.core.validators)                      │   │
│  │ ───────────────────────────────────────────────────────────────────    │   │
│  │  • validate_ssn() - SSN format & rules validation                     │   │
│  │  • validate_numeric_range() - Range validation with formatting       │   │
│  │  • validate_date() - Date format & constraint validation             │   │
│  │  • validate_branch_code() - Bank code validation                     │   │
│  │  • validate_required() - Null/empty check                            │   │
│  │  • validate_length() - String length validation                      │   │
│  │  • ValidationError - PII-masked error dataclass                      │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌──────────────────────────────────────────┐  ┌─────────────────────────────┐ │
│  │ Error Handling Module                    │  │ Audit & Reconciliation      │ │
│  │ (gdw_data_core.core.error_handling)      │  │ (gdw_data_core.core.audit)  │ │
│  │ ──────────────────────────────────────── │  │ ──────────────────────────  │ │
│  │  • ErrorContext (context manager)        │  │  • AuditTrail              │ │
│  │  • ErrorHandler (main error handler)     │  │  • DuplicateDetector       │ │
│  │  • ErrorClassifier (auto-classification) │  │  • ReconciliationEngine    │ │
│  │  • ErrorSeverity (enum)                  │  │  • DataLineage             │ │
│  │  • ErrorCategory (enum)                  │  │  • AuditEntry (dataclass)  │ │
│  │  • RetryStrategy (enum)                  │  │  • AuditRecord (dataclass) │ │
│  │  • RetryPolicy (configuration)           │  │                            │ │
│  │  • Error Storage:                        │  │ Features:                  │ │
│  │    - InMemoryErrorStorage                │  │  ✓ Execution tracking      │ │
│  │    - GCSErrorStorage                     │  │  ✓ Duplicate prevention    │ │
│  │                                          │  │  ✓ Source-dest reconcile   │ │
│  │ Features:                                │  │  ✓ Data lineage tracking   │ │
│  │  ✓ Auto classification                  │  │                            │ │
│  │  ✓ Multiple retry strategies             │  │                            │ │
│  │  ✓ Pluggable storage backends            │  │                            │ │
│  │  ✓ Error analytics                       │  │                            │ │
│  └──────────────────────────────────────────┘  └─────────────────────────────┘ │
│                                                                                  │
│  ┌──────────────────────────────────────────┐  ┌─────────────────────────────┐ │
│  │ Monitoring & Observability               │  │ Utilities                   │ │
│  │ (gdw_data_core.core.monitoring)          │  │ (gdw_data_core.core.util)   │ │
│  │ ──────────────────────────────────────── │  │ ──────────────────────────  │ │
│  │  • MetricsCollector                      │  │  • generate_run_id()        │ │
│  │    - Counters, gauges, histograms, time │  │  • validate_run_id()        │ │
│  │  • HealthChecker                         │  │  • discover_split_files()   │ │
│  │    - Processing rate, error threshold   │  │  • discover_files_by_date() │ │
│  │  • AlertManager                          │  │  • build_gcs_path()         │ │
│  │    - Multi-backend routing               │  │  • Other helpers            │ │
│  │  • TimerContext (auto-measurement)       │  │                             │ │
│  │  • HealthStatus (reporting)              │  │                             │ │
│  │                                          │  │                             │ │
│  │ Features:                                │  │ Features:                   │ │
│  │  ✓ Thread-safe collection                │  │  ✓ Run ID generation        │ │
│  │  ✓ Multiple metric types                 │  │  ✓ File discovery           │ │
│  │  ✓ Health check automation               │  │  ✓ Path building            │ │
│  │  ✓ Alert routing (Slack, etc.)           │  │  ✓ Common operations        │ │
│  │  ✓ Export to monitoring systems          │  │                             │ │
│  └──────────────────────────────────────────┘  └─────────────────────────────┘ │
│                                                                                  │
│  ┌──────────────────────────────────┐  ┌──────────────────────────────────┐   │
│  │ Data Quality Module              │  │ File Management Module           │   │
│  │ (gdw_data_core.core.data_quality)│  │ (gdw_data_core.core.file_mgmt)   │   │
│  │ ────────────────────────────────│  │ ──────────────────────────────   │   │
│  │  • DataQualityChecker            │  │  • FileArchiver                  │   │
│  │  • AnomalyDetector               │  │  • FileValidator                 │   │
│  │  • QualityScoring                │  │  • FileLifecycleManager          │   │
│  │  • Quality Reports               │  │  • FileMetadata                  │   │
│  └──────────────────────────────────┘  └──────────────────────────────────┘   │
│                                                                                  │
│  ┌──────────────────────────────────┐  ┌──────────────────────────────────┐   │
│  │ Data Deletion Framework          │  │ Clients                          │   │
│  │ (gdw_data_core.core.data_delete) │  │ (gdw_data_core.core.clients)     │   │
│  │ ────────────────────────────────│  │ ──────────────────────────────   │   │
│  │  • DeletionFramework             │  │  • GCSClient                     │   │
│  │  • QuarantineManager             │  │  • BigQueryClient                │   │
│  │  • RecoveryManager               │  │                                  │   │
│  │  • DeletionDetector              │  │ Features:                        │   │
│  │                                  │  │  ✓ Connection management         │   │
│  │                                  │  │  ✓ Retry logic                   │   │
│  │                                  │  │  ✓ Error handling                │   │
│  └──────────────────────────────────┘  └──────────────────────────────────┘   │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────┬──┘
                                                                               │
        ┌──────────────────────────────────────────────────────────────────────┴─┐
        │                                                                        │
┌──────▼──────────────────────────────────────────────────────────────────────────▼─┐
│                  DATA OPERATIONS & ORCHESTRATION LAYER                            │
│                                                                                   │
│  ┌─────────────────────────────────┐  ┌──────────────────────────────────────┐  │
│  │ Orchestration                   │  │ GCP/Cloud Integrations              │  │
│  │ (gdw_data_core.orchestration)   │  │                                      │  │
│  │ ─────────────────────────────── │  │ ──────────────────────────────────  │  │
│  │  • DAGFactory (Airflow DAG gen) │  │  • Cloud Storage (GCS) integration  │  │
│  │  • DynamicRouter (task routing) │  │  • BigQuery integration             │  │
│  │  • Workflow coordination        │  │  • Pub/Sub integration              │  │
│  │                                 │  │  • Cloud Composer integration       │  │
│  │ Features:                       │  │  • Cloud Functions trigger          │  │
│  │  ✓ Dynamic DAG creation         │  │                                      │  │
│  │  ✓ Task dependency management   │  │ Features:                           │  │
│  │  ✓ Workflow execution           │  │  ✓ Cloud-native design              │  │
│  │  ✓ State management             │  │  ✓ Serverless compatibility         │  │
│  └─────────────────────────────────┘  └──────────────────────────────────────┘  │
│                                                                                   │
│  ┌────────────────────────────────────────────────────────────────────────────┐ │
│  │ External Services & Cloud Platform                                        │ │
│  │ ──────────────────────────────────────────────────────────────────────   │ │
│  │  Google Cloud Platform:                                                  │ │
│  │   ├─ Google Cloud Storage (file operations)                              │ │
│  │   ├─ BigQuery (data warehouse)                                           │ │
│  │   ├─ Cloud Pub/Sub (messaging)                                           │ │
│  │   ├─ Cloud Composer (managed Airflow)                                    │ │
│  │   ├─ Cloud Dataflow (Apache Beam runner)                                 │ │
│  │   ├─ Cloud Functions (serverless compute)                                │ │
│  │   ├─ Cloud Monitoring (observability)                                    │ │
│  │   └─ Cloud Logging (log management)                                      │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow Within Components

```
User Pipeline
    │
    ├─→ [PipelineConfig] (settings)
    │
    ├─→ [BasePipeline.build()] 
    │       │
    │       ├─→ [Beam Pipeline Creation]
    │       │
    │       ├─→ Transform Chain:
    │       │   ├─ ParseCsvLine → ValidationError (if invalid)
    │       │   ├─ ValidateRecordDoFn → ErrorContext (handle errors)
    │       │   ├─ FilterRecordsDoFn → filtered out records
    │       │   ├─ TransformRecordDoFn → transformed records
    │       │   ├─ DeduplicateRecordsDoFn → DuplicateDetector (state check)
    │       │   ├─ EnrichWithMetadataDoFn → adds audit fields
    │       │   └─ I/O DoFn (Write to GCS/BQ/PubSub)
    │       │
    │       └─→ Error Handling:
    │           ├─ ErrorClassifier (severity + category)
    │           ├─ ErrorContext (catch + retry)
    │           ├─ RetryPolicy (strategy selection)
    │           └─ ErrorStorage (persistence)
    │
    ├─→ [MetricsCollector]
    │   ├─ Counters (record counts)
    │   ├─ Gauges (current state)
    │   ├─ Histograms (distributions)
    │   └─ Timers (durations)
    │
    ├─→ [AuditTrail]
    │   ├─ Record start/end
    │   ├─ Track counts
    │   ├─ Generate audit record
    │   └─ Store in AuditEntry
    │
    └─→ [HealthChecker]
        ├─ Check processing rate
        ├─ Check error threshold
        ├─ Monitor resources
        └─ Send AlertManager alerts
```

### Component Dependencies

```
Applications depend on:
    ↓
BasePipeline + PipelineConfig
    ↓
Beam Transforms + Beam I/O
    ↓
Core Modules (validators, error_handling, audit, monitoring, utilities)
    ↓
GCS/BigQuery Clients + Cloud Services
```

---

## Core Modules

### 1. Validators Module

**Location**: `gdw_data_core.core.validators`

Standardized validation with PII masking and structured error reporting.

#### ValidationError (Dataclass)

```python
from gdw_data_core.core.validators import ValidationError

error = ValidationError(
    field="ssn",
    value="123-45-6789",
    message="Invalid SSN format",
    error_type="VALIDATION_ERROR"
)
# String representation masks PII: field: message (value: ***-**-6789)
```

**Fields**:
- `field`: Field name being validated
- `value`: The value that failed validation
- `message`: Human-readable error message
- `error_type`: Type of error (default: "VALIDATION_ERROR")

#### Available Validators

**validate_ssn(ssn: str) -> List[ValidationError]**

Validates US Social Security Numbers. Checks format, prevents invalid area numbers (000, 666, 900-999).

```python
from gdw_data_core.core.validators import validate_ssn

# Valid SSN
errors = validate_ssn("123-45-6789")
assert errors == []

# Invalid format
errors = validate_ssn("12-34-567")
assert len(errors) > 0
assert errors[0].message == "SSN must be 9 digits (format: XXX-XX-XXXX)"

# In processing loop
for record in records:
    errors = validate_ssn(record['ssn'])
    if errors:
        print(f"SSN validation failed: {errors[0]}")  # PII masked automatically
```

**validate_numeric_range(field: str, value: str, min_value: float = None, max_value: float = None) -> Tuple[Optional[float], List[ValidationError]]**

Validates numeric values within a range. Handles currency formatting ($1,234.56) and comma-separated numbers.

```python
from gdw_data_core.core.validators import validate_numeric_range

# Valid number
cleaned, errors = validate_numeric_range("loan_amount", "$1,234.56", min_value=0, max_value=100000)
assert cleaned == 1234.56
assert errors == []

# Out of range
cleaned, errors = validate_numeric_range("age", "25", min_value=18, max_value=65)
assert cleaned == 25.0
assert errors == []

# Invalid format
cleaned, errors = validate_numeric_range("amount", "invalid", min_value=0)
assert cleaned is None
assert len(errors) > 0
```

**validate_date(field: str, date_str: str, fmt: str = '%Y-%m-%d', allow_future: bool = False, max_age_years: int = None) -> Tuple[Optional[str], List[ValidationError]]**

Validates date format and constraints (future dates, age limits).

```python
from gdw_data_core.core.validators import validate_date

# Valid date
cleaned, errors = validate_date("birth_date", "1990-05-15", fmt='%Y-%m-%d', max_age_years=100)
assert errors == []

# Future date rejected (by default)
cleaned, errors = validate_date("birth_date", "2025-12-31", allow_future=False)
assert len(errors) > 0

# Age validation
cleaned, errors = validate_date("birth_date", "1990-05-15", max_age_years=80)
# Fails if person would be >80 years old
```

**validate_branch_code(code: str) -> List[ValidationError]**

Validates bank branch codes (typically 4-digit codes).

```python
from gdw_data_core.core.validators import validate_branch_code

errors = validate_branch_code("1234")
assert errors == []

errors = validate_branch_code("123")  # Too short
assert len(errors) > 0
```

**validate_required(field: str, value: Any) -> List[ValidationError]**

Ensures field is not empty/None.

```python
from gdw_data_core.core.validators import validate_required

errors = validate_required("account_id", "ACC123")
assert errors == []

errors = validate_required("email", None)
assert len(errors) > 0
```

**validate_length(field: str, value: str, min_length: int = None, max_length: int = None) -> List[ValidationError]**

Validates string length constraints.

```python
from gdw_data_core.core.validators import validate_length

errors = validate_length("account_id", "ACC123456", min_length=5, max_length=20)
assert errors == []
```

#### Custom Validators

```python
from gdw_data_core.core.validators import ValidationError
from typing import List

def validate_phone_number(phone: str) -> List[ValidationError]:
    """Custom validator for phone numbers."""
    errors = []
    
    # Remove formatting
    clean = ''.join(c for c in phone if c.isdigit())
    
    if len(clean) != 10:
        errors.append(ValidationError(
            field='phone',
            value=phone,
            message='Phone must be 10 digits'
        ))
    
    return errors

# Use in pipeline
errors = validate_phone_number("(555) 123-4567")
```

---

### 2. Error Handling Module

**Location**: `gdw_data_core.core.error_handling`

Production-grade error management with automatic classification and configurable retry strategies.

#### ErrorContext (Context Manager)

Most common pattern - wrap processing logic to automatically handle errors:

```python
from gdw_data_core.core.error_handling import ErrorContext, ErrorHandler

handler = ErrorHandler(pipeline_name="my_job", run_id="run_001")

# Simple usage
with ErrorContext(handler, operation_name="process_record"):
    result = process_record(record)
    # Errors are automatically caught, classified, logged, and retried

# Access error info after processing
stats = handler.get_statistics()
errors = handler.get_all_errors()
```

**Parameters**:
- `handler`: ErrorHandler instance
- `operation_name`: Name of the operation being executed
- `max_retries`: Override max retries for this context
- `retry_delay_seconds`: Override base delay between retries

#### ErrorHandler (Main Class)

```python
from gdw_data_core.core.error_handling import ErrorHandler, ErrorSeverity, ErrorCategory

handler = ErrorHandler(
    pipeline_name="loa_migration",
    run_id="run_20231225_001"
)

# Process records with error handling
for record in records:
    with ErrorContext(handler, operation_name="validate_record"):
        errors = validate_record(record)

# Get statistics
stats = handler.get_statistics()
print(f"Total errors: {stats['error_count']}")
print(f"Critical: {stats['severity_breakdown']['CRITICAL']}")

# Get detailed error list
all_errors = handler.get_all_errors()
for err in all_errors:
    print(f"{err.severity}: {err.message}")
```

**Methods**:
- `get_statistics() -> Dict`: Error counts by severity and category
- `get_all_errors() -> List[PipelineError]`: All captured errors
- `get_errors_by_severity(severity: ErrorSeverity) -> List[PipelineError]`: Filter by severity
- `get_errors_by_category(category: ErrorCategory) -> List[PipelineError]`: Filter by category
- `clear_errors()`: Reset error state
- `should_fail() -> bool`: Whether pipeline should fail based on error state

#### Error Classification

Errors are automatically classified by **Severity** and **Category**:

**Severity Levels**:
- `CRITICAL`: Pipeline cannot continue (authorization failures, invalid config)
- `HIGH`: Significant data loss risk (quota exceeded, service unavailable)
- `MEDIUM`: Processing issues but can retry (timeout, connection errors)
- `LOW`: Non-blocking issues (warnings, informational)
- `INFO`: Informational messages

**Categories**:
- `VALIDATION`: Data validation failures
- `INTEGRATION`: External service failures (GCS, BigQuery, Pub/Sub)
- `CONFIGURATION`: Configuration/setup issues
- `RESOURCE`: Resource exhaustion (memory, storage, compute)
- `DATA_QUALITY`: Data quality rule violations
- `INFRASTRUCTURE`: System/infrastructure issues

**ErrorClassifier**:

```python
from gdw_data_core.core.error_handling import ErrorClassifier

# Automatic classification
exception = TimeoutError("Connection timeout to BigQuery")
severity, category, retry_strategy = ErrorClassifier.classify(exception)

print(f"Severity: {severity}")        # ErrorSeverity.MEDIUM
print(f"Category: {category}")        # ErrorCategory.INTEGRATION
print(f"Retry: {retry_strategy}")     # RetryStrategy.EXPONENTIAL_BACKOFF
```

#### Retry Strategies

```python
from gdw_data_core.core.error_handling import RetryStrategy

# Built-in strategies (automatically selected based on error type):

# EXPONENTIAL_BACKOFF: Delays increase exponentially (1s, 2s, 4s, 8s...)
# - Good for: Rate limits, temporary service issues
# - Includes jitter to prevent thundering herd

# FIXED_DELAY: Consistent delay between retries (e.g., 5 seconds)
# - Good for: Scheduled retries with predictable timing

# LINEAR: Delays increase linearly (1s, 2s, 3s, 4s...)
# - Good for: Progressive backoff with gradual increase

# NO_RETRY: Don't retry (for validation errors, permission failures)
# - Good for: Errors that won't resolve on retry
```

#### Error Storage

```python
from gdw_data_core.core.error_handling import ErrorHandler, InMemoryErrorStorage, GCSErrorStorage

# Testing - in-memory storage
handler = ErrorHandler(
    pipeline_name="test_job",
    run_id="test_001",
    storage_backend=InMemoryErrorStorage()
)

# Production - store in GCS
handler = ErrorHandler(
    pipeline_name="loa_job",
    run_id="run_001",
    storage_backend=GCSErrorStorage(bucket="error-logs", prefix="loa/")
)
```

#### Complete Example

```python
from gdw_data_core.core.error_handling import ErrorContext, ErrorHandler

handler = ErrorHandler(pipeline_name="data_migration", run_id="run_001")

processed = 0
failed = 0

for record in data_source:
    with ErrorContext(handler, operation_name="process_record"):
        # Process logic here - errors are caught automatically
        validate_record(record)
        transform_record(record)
        load_to_bigquery(record)
        processed += 1

# Check results
stats = handler.get_statistics()
if stats['severity_breakdown'].get('CRITICAL', 0) > 0:
    print("Pipeline failed due to critical errors")
    handler.log_errors_to_file("errors.log")
else:
    print(f"Processed {processed} records, {stats['error_count']} non-critical errors")
```

---

### 3. Audit & Reconciliation Module

**Location**: `gdw_data_core.core.audit`

Tracks data integrity, prevents reprocessing, and enables reconciliation.

#### AuditTrail

```python
from gdw_data_core.core.audit import AuditTrail

# Initialize
audit = AuditTrail(
    run_id="run_20231225_001",
    pipeline_name="loa_applications",
    entity_type="applications"
)

# Record start
audit.record_processing_start(
    source_file="gs://bucket/loa_apps_2023.csv",
    metadata={"source_system": "mainframe", "batch_date": "2023-12-25"}
)

# Process records
audit.increment_counts(valid=1000, errors=5)

# Record completion
audit_record = audit.record_processing_end(success=True)
# Returns: AuditRecord with run_id, record_count, duration, success flag, audit_hash
```

**Methods**:
- `record_processing_start(source_file, metadata)`: Mark processing start
- `record_processing_end(success) -> AuditRecord`: Mark processing end, returns audit record
- `increment_counts(valid, errors)`: Update record counts
- `log_entry(status, message, context)`: Log specific audit entry
- `get_entries() -> List[AuditEntry]`: Get all audit entries
- `get_entries_by_status(status)`: Filter entries by status
- `get_entry_count() -> int`: Total entry count

**Audit Output**:
```
[AUDIT] Starting loa_applications for applications
[AUDIT] Run ID: run_20231225_001
[AUDIT] Source: gs://bucket/loa_apps_2023.csv
[AUDIT] Completed loa_applications
[AUDIT] Records processed: 1005
[AUDIT] Valid: 1000, Errors: 5
[AUDIT] Duration: 45.23s
```

#### DuplicateDetector

Prevents processing the same data multiple times:

```python
from gdw_data_core.core.audit import DuplicateDetector

detector = DuplicateDetector()

# Check for duplicates across runs
key_fields = ['account_id', 'date']
for record in records:
    record_key = "|".join([str(record[f]) for f in key_fields])
    
    if detector.is_duplicate(record, key_fields=key_fields):
        print(f"Skipping duplicate: {record_key}")
    else:
        process_record(record)
```

#### ReconciliationEngine

Compare source vs. destination to verify data completeness:

```python
from gdw_data_core.core.audit import ReconciliationEngine

reconciler = ReconciliationEngine()

# After loading data to BigQuery
source_count = 10000
bigquery_count = 9995

report = reconciler.reconcile(
    source_count=source_count,
    destination_count=bigquery_count,
    entity_type="applications"
)

if report['status'] == 'MISMATCH':
    print(f"Missing records: {report['difference']}")
    print(f"Error rate: {report['error_rate_percent']:.2f}%")
```

#### DataLineage

Track data flow from source to destination:

```python
from gdw_data_core.core.audit import DataLineage

lineage = DataLineage()

lineage.add_transformation(
    source="gs://bucket/raw/applications.csv",
    operation="validate_ssn",
    target_dataset="staging_dataset"
)

lineage.add_transformation(
    source="staging_dataset.applications",
    operation="enrich_with_metadata",
    target_dataset="production_dataset"
)

report = lineage.get_lineage_report()
# Shows complete data flow path
```

---

### 4. Monitoring & Observability Module

**Location**: `gdw_data_core.core.monitoring`

Metrics collection and health monitoring for pipelines.

#### MetricsCollector

```python
from gdw_data_core.core.monitoring import MetricsCollector

metrics = MetricsCollector(pipeline_name="loa_job", run_id="run_001")

# Counters - monotonically increasing
metrics.increment("records_processed", 1)
metrics.increment("validation_errors", 1)
metrics.increment("bigquery_writes", 100)  # Increment by value

# Gauges - current value
metrics.set_gauge("queue_size", 250.0)
metrics.set_gauge("memory_usage_mb", 512.0)

# Histograms - value distributions
metrics.record_histogram("record_size_bytes", 1024)
metrics.record_histogram("transformation_time_ms", 45.5)

# Timers - duration measurements
metrics.record_timer("bigquery_write_seconds", 2.3)

# Timer context - automatic duration measurement
with metrics.start_timer() as timer:
    # Do work
    results = process_data()
    # Duration automatically recorded when exiting context
```

**Accessing Metrics**:

```python
# Get all statistics
stats = metrics.get_statistics()

print(stats['counters'])  # {'records_processed': 1000, ...}
print(stats['gauges'])    # {'queue_size': 250.0, ...}
print(stats['histograms_summary'])  # {'record_size_bytes': {'min': 100, 'max': 2000, 'avg': 1050}}
print(stats['timers_summary'])      # {'bigquery_write_seconds': {'min': 0.5, 'max': 5.0, 'avg': 2.3}}
```

#### HealthChecker

```python
from gdw_data_core.core.monitoring import HealthChecker

checker = HealthChecker()

# Configure health checks
checker.add_check(
    name="processing_rate",
    check_type="rate",
    min_rate=10,  # At least 10 records/second
    window_seconds=60
)

checker.add_check(
    name="error_threshold",
    check_type="error_rate",
    max_error_rate=0.05  # Alert if >5% error rate
)

checker.add_check(
    name="memory_usage",
    check_type="resource",
    max_memory_mb=2000
)

# Run health checks
health_status = checker.check_health(metrics)
if health_status['status'] == 'UNHEALTHY':
    print(f"Alerts: {health_status['alerts']}")
```

#### AlertManager

```python
from gdw_data_core.core.monitoring import AlertManager, AlertSeverity

alert_manager = AlertManager()

# Configure alert backends
alert_manager.add_backend("slack", webhook_url="https://hooks.slack.com/...")
alert_manager.add_backend("cloud_monitoring", project_id="my-gcp-project")

# Send alerts
alert_manager.alert(
    title="High error rate detected",
    message="Error rate exceeded 5% threshold",
    severity=AlertSeverity.HIGH,
    tags={"pipeline": "loa_job", "run_id": "run_001"}
)

# Routes to all configured backends automatically
```

#### Complete Example

```python
from gdw_data_core.core.monitoring import MetricsCollector, HealthChecker

metrics = MetricsCollector("pipeline", "run_001")
checker = HealthChecker()

for record in records:
    with metrics.start_timer() as timer:
        try:
            result = process(record)
            metrics.increment("processed")
        except Exception as e:
            metrics.increment("errors")

# Check health
stats = metrics.get_statistics()
health = checker.check_health(stats)

if health['status'] == 'HEALTHY':
    print(f"Processed: {stats['counters']['processed']}")
```

---

### 5. Utilities Module

**Location**: `gdw_data_core.core.utilities`

Common utility functions for run IDs, GCS discovery, and path operations.

#### Run ID Generation

```python
from gdw_data_core.core.utilities import generate_run_id, validate_run_id

# Generate unique run ID
run_id = generate_run_id(
    job_name="loa_migration",
    timestamp=None,  # Uses current time if None
    include_uuid=True
)
# Format: loa_migration_YYYYMMDD_HHMMSS_<uuid>
print(run_id)  # loa_migration_20231225_153045_a1b2c3d4e5f6

# Validate run ID format
is_valid = validate_run_id(run_id)
assert is_valid == True
```

#### GCS File Discovery

```python
from gdw_data_core.core.utilities import discover_split_files, discover_files_by_date
from google.cloud import storage

client = storage.Client()

# Discover split files (app_1, app_2, app_3, etc.)
files = discover_split_files(
    client=client,
    bucket="my-bucket",
    prefix="input/applications/",
    pattern="app_*.csv"
)
# Returns: ['input/applications/app_1.csv', 'input/applications/app_2.csv', ...]

# Discover files by date pattern (YYYY/MM/DD)
files = discover_files_by_date(
    client=client,
    bucket="my-bucket",
    prefix="data/",
    date_pattern="2023/12/"
)
# Returns all files under data/2023/12/
```

#### GCS Path Building

```python
from gdw_data_core.core.utilities import build_gcs_path

path = build_gcs_path(
    bucket="my-bucket",
    prefix="output/processed/",
    filename="results.csv"
)
# Returns: gs://my-bucket/output/processed/results.csv
```

---

### 6. Apache Beam Transforms

**Location**: `gdw_data_core.pipelines.beam.transforms`

Reusable DoFn classes for common transformation patterns.

#### ParseCsvLine

Parse CSV lines into structured dictionaries:

```python
from gdw_data_core.pipelines.beam.transforms import ParseCsvLine
import apache_beam as beam

pipeline = beam.Pipeline()

(pipeline
    | 'Read' >> beam.io.ReadFromText('input.csv')
    | 'Parse' >> beam.ParDo(ParseCsvLine(
        field_names=['id', 'name', 'email'],
        delimiter=','
    ))
    | 'Print' >> beam.Map(print)
)

pipeline.run()
# Output: {'id': '1', 'name': 'John', 'email': 'john@example.com'}
```

#### ValidateRecordDoFn

Validate records against custom rules:

```python
from gdw_data_core.pipelines.beam.transforms import ValidateRecordDoFn
import apache_beam as beam

def validate_fn(record):
    """Custom validation function."""
    errors = []
    if not record.get('id'):
        errors.append("Missing id")
    if not record.get('email'):
        errors.append("Missing email")
    return errors

(pipeline
    | 'Validate' >> beam.ParDo(ValidateRecordDoFn(validate_fn))
)
# Emits metrics: 'validation_passed', 'validation_failed'
# Failed records sent to error output
```

#### FilterRecordsDoFn

Filter records based on predicates:

```python
from gdw_data_core.pipelines.beam.transforms import FilterRecordsDoFn

def filter_fn(record):
    """Keep only active records."""
    return record.get('status') == 'ACTIVE'

(pipeline
    | 'Filter' >> beam.ParDo(FilterRecordsDoFn(filter_fn))
)
# Emits metric: 'filtered_count'
```

#### TransformRecordDoFn

Transform record fields:

```python
from gdw_data_core.pipelines.beam.transforms import TransformRecordDoFn

def transform_fn(record):
    """Normalize and clean data."""
    record['name'] = record['name'].upper()
    record['email'] = record['email'].lower()
    return record

(pipeline
    | 'Transform' >> beam.ParDo(TransformRecordDoFn(transform_fn))
)
```

#### EnrichWithMetadataDoFn

Add audit metadata fields:

```python
from gdw_data_core.pipelines.beam.transforms import EnrichWithMetadataDoFn

(pipeline
    | 'Enrich' >> beam.ParDo(EnrichWithMetadataDoFn(
        run_id='run_001',
        pipeline_name='loa_migration'
    ))
)
# Adds: run_id, pipeline_name, processed_at timestamp
```

#### DeduplicateRecordsDoFn

Remove duplicate records:

```python
from gdw_data_core.pipelines.beam.transforms import DeduplicateRecordsDoFn

def key_fn(record):
    """Create composite key for deduplication."""
    return f"{record['account_id']}|{record['date']}"

(pipeline
    | 'Deduplicate' >> beam.ParDo(DeduplicateRecordsDoFn(key_fn))
)
# Emits metric: 'deduplicated_count'
# Maintains state across records to detect duplicates
```

#### Chaining Transforms

```python
(pipeline
    | 'Read' >> beam.io.ReadFromText('input.csv')
    | 'Parse' >> beam.ParDo(ParseCsvLine(['id', 'name', 'email']))
    | 'Validate' >> beam.ParDo(ValidateRecordDoFn(validate_fn))
    | 'Filter' >> beam.ParDo(FilterRecordsDoFn(filter_fn))
    | 'Transform' >> beam.ParDo(TransformRecordDoFn(transform_fn))
    | 'Deduplicate' >> beam.ParDo(DeduplicateRecordsDoFn(key_fn))
    | 'Enrich' >> beam.ParDo(EnrichWithMetadataDoFn('run_001', 'my_pipeline'))
    | 'Write' >> beam.io.WriteToBigQuery('dataset.table')
)
```

---

### 7. Apache Beam I/O Operations

**Location**: `gdw_data_core.pipelines.beam.io`

Cloud I/O operations for GCS, BigQuery, and Pub/Sub.

#### GCS Operations

**ReadFromGCSDoFn**:

```python
from gdw_data_core.pipelines.beam.io import ReadFromGCSDoFn

(pipeline
    | 'Read from GCS' >> beam.ParDo(ReadFromGCSDoFn(
        bucket='my-bucket',
        prefix='input/data/',
        encoding='utf-8'
    ))
)
# Reads all files matching gs://my-bucket/input/data/*
```

**WriteToGCSDoFn**:

```python
from gdw_data_core.pipelines.beam.io import WriteToGCSDoFn

(pipeline
    | 'Write to GCS' >> beam.ParDo(WriteToGCSDoFn(
        bucket='my-bucket',
        prefix='output/processed/',
        extension='csv'
    ))
)
# Writes records to gs://my-bucket/output/processed/
```

#### CSV I/O

**ReadCSVFromGCSDoFn**:

```python
from gdw_data_core.pipelines.beam.io import ReadCSVFromGCSDoFn

(pipeline
    | 'Read CSV' >> beam.ParDo(ReadCSVFromGCSDoFn(
        bucket='my-bucket',
        prefix='input/',
        delimiter=',',
        skip_header=True
    ))
)
# Automatically parses CSV into dictionaries
```

**WriteCSVToGCSDoFn**:

```python
from gdw_data_core.pipelines.beam.io import WriteCSVToGCSDoFn

(pipeline
    | 'Write CSV' >> beam.ParDo(WriteCSVToGCSDoFn(
        bucket='my-bucket',
        filename='output.csv',
        fieldnames=['id', 'name', 'email']
    ))
)
```

#### BigQuery Operations

**WriteToBigQueryDoFn**:

```python
from gdw_data_core.pipelines.beam.io import WriteToBigQueryDoFn

(pipeline
    | 'Write to BigQuery' >> beam.ParDo(WriteToBigQueryDoFn(
        project='my-gcp-project',
        dataset='my_dataset',
        table='records'
    ))
)
# Streams records to BigQuery table
```

**BatchWriteToBigQueryDoFn**:

```python
from gdw_data_core.pipelines.beam.io import BatchWriteToBigQueryDoFn

(pipeline
    | 'Batch Write to BigQuery' >> beam.ParDo(BatchWriteToBigQueryDoFn(
        project='my-gcp-project',
        dataset='my_dataset',
        table='records',
        batch_size=1000
    ))
)
# Batches records for efficient loading
```

#### Pub/Sub Operations

**PublishToPubSubDoFn**:

```python
from gdw_data_core.pipelines.beam.pubsub import PublishToPubSubDoFn

(pipeline
    | 'Publish Events' >> beam.ParDo(PublishToPubSubDoFn(
        project='my-gcp-project',
        topic='my-topic'
    ))
)
# Publishes records as events to Pub/Sub topic
```

---

### 8. Pipeline Base Classes

**Location**: `gdw_data_core.pipelines.base`

Foundation for Apache Beam pipelines.

#### PipelineConfig

```python
from gdw_data_core.pipelines.base import PipelineConfig

config = PipelineConfig(
    run_id='run_20231225_001',
    pipeline_name='loa_applications',
    entity_type='applications',
    source_file='gs://bucket/applications.csv',
    gcp_project_id='my-gcp-project',
    bigquery_dataset='migration_dataset'
)

# Validate configuration
config.validate()

# Access values
run_id = config.run_id
value = config.get('key', default='default_value')  # Dict-like access
config_dict = config.to_dict()
```

#### GDWPipelineOptions

```python
from gdw_data_core.pipelines.base import GDWPipelineOptions

options = GDWPipelineOptions(
    input_pattern='gs://bucket/input/*.csv',
    output_table='dataset.records',
    error_table='dataset.errors',
    run_id='run_001',
    project='my-gcp-project',
    num_workers=10,
    autoscaling_algorithm='THROUGHPUT_BASED'
)

# Use with Beam pipeline
beam_pipeline = beam.Pipeline(options=options)
```

#### BasePipeline

```python
from gdw_data_core.pipelines.base import BasePipeline
import apache_beam as beam

class MyPipeline(BasePipeline):
    """Custom migration pipeline."""
    
    def build(self, pipeline: beam.Pipeline):
        """Build the pipeline logic."""
        (pipeline
            | 'Read' >> beam.io.ReadFromText(self.config.source_file)
            | 'Process' >> beam.ParDo(self.process_fn)
            | 'Write' >> beam.io.WriteToBigQuery(self.config.bigquery_dataset)
        )
    
    def process_fn(self, element):
        """Custom processing logic."""
        return element.upper()

# Run pipeline
config = PipelineConfig(run_id='run_001', ...)
pipeline = MyPipeline(config=config)
result = pipeline.run()

# Access results
audit = pipeline.get_audit_record()
metrics = pipeline.get_metrics_summary()
errors = pipeline.get_error_count()
```

**BasePipeline Lifecycle**:

```python
class MyPipeline(BasePipeline):
    def on_start(self):
        """Called when pipeline starts."""
        print("Pipeline starting...")
    
    def on_success(self):
        """Called on successful completion."""
        print("Pipeline completed successfully")
    
    def on_failure(self, exception: Exception):
        """Called on failure."""
        print(f"Pipeline failed: {exception}")
```

---

### 9. Testing Framework

**Location**: `gdw_data_core.testing`

Comprehensive testing utilities for unit and integration tests.

#### Base Test Classes

**BaseGDWTest**:

```python
from gdw_data_core.testing.base import BaseGDWTest

class TestMyModule(BaseGDWTest):
    def test_field_exists(self):
        """Test that field exists in record."""
        record = {'id': '123', 'name': 'John'}
        self.assert_field_exists(record, 'id')
        
    def test_field_value(self):
        """Test field value."""
        record = {'status': 'ACTIVE'}
        self.assert_field_value(record, 'status', 'ACTIVE')
```

**BaseValidationTest**:

```python
from gdw_data_core.testing.base import BaseValidationTest
from gdw_data_core.core.validators import validate_ssn

class TestValidators(BaseValidationTest):
    def test_valid_ssn(self):
        """Test SSN validation."""
        errors = validate_ssn("123-45-6789")
        self.assert_validation_passed(errors)
    
    def test_invalid_ssn(self):
        """Test invalid SSN."""
        errors = validate_ssn("invalid")
        self.assert_validation_error(errors, "ssn")
```

**BaseBeamTest**:

```python
from gdw_data_core.testing.base import BaseBeamTest
import apache_beam as beam

class TestBeamTransforms(BaseBeamTest):
    def test_parse_csv(self):
        """Test CSV parsing."""
        pipeline = self.create_test_pipeline()
        
        result = (pipeline
            | beam.Create(['"id","name"\n"1","John"'])
            | beam.ParDo(ParseCsvLine(['id', 'name']))
        )
        
        self.assert_pcollection_equal(result, [
            {'id': '1', 'name': 'John'}
        ])
```

#### Pytest Fixtures

```python
import pytest
from gdw_data_core.testing.fixtures import *

# Common fixtures
def test_with_sample_records(sample_records):
    """Use pre-generated sample records."""
    assert len(sample_records) > 0

def test_with_config(sample_config):
    """Use sample pipeline config."""
    assert sample_config.pipeline_name == 'test_pipeline'

# Beam fixtures
def test_beam_pipeline(test_pipeline):
    """Use Beam test pipeline."""
    result = (test_pipeline
        | beam.Create(['a', 'b', 'c'])
    )

# GCS fixtures
def test_gcs_operations(gcs_client, gcs_bucket):
    """Use mocked GCS client."""
    gcs_client.write_file(gcs_bucket, 'file.txt', 'content')

# BigQuery fixtures
def test_bigquery_operations(bq_client, sample_schema):
    """Use mocked BigQuery client."""
    bq_client.create_table(sample_schema)
```

#### Mock Objects

```python
from gdw_data_core.testing.mocks import (
    GCSClientMock,
    BigQueryClientMock,
    PubSubClientMock
)

def test_with_mocks():
    gcs_mock = GCSClientMock()
    bq_mock = BigQueryClientMock()
    
    # Use mocks instead of real GCP services
    gcs_mock.write_file('bucket', 'file.txt', 'data')
    assert gcs_mock.read_file('bucket', 'file.txt') == 'data'
```

#### Test Builders

```python
from gdw_data_core.testing.builders import (
    RecordBuilder,
    ConfigBuilder,
    PipelineConfigBuilder
)

# Fluent record construction
record = (RecordBuilder()
    .with_id('123')
    .with_name('John')
    .with_email('john@example.com')
    .build()
)

# Fluent config construction
config = (ConfigBuilder()
    .with_pipeline_name('test_job')
    .with_entity_type('applications')
    .build()
)
```

#### Custom Assertions

```python
from gdw_data_core.testing.assertions import (
    assert_field_exists,
    assert_pcollection_equal,
    assert_pipeline_success
)

def test_assertions():
    record = {'id': '123', 'name': 'John'}
    
    assert_field_exists(record, 'id')
    assert_field_exists(record, 'name')
    
    # Record value assertions
    assert record['id'] == '123'
```

---

## Common Patterns

### Pattern 1: CSV to BigQuery Pipeline

```python
from gdw_data_core.pipelines.base import BasePipeline, PipelineConfig
from gdw_data_core.pipelines.beam.transforms import ParseCsvLine, EnrichWithMetadataDoFn
from gdw_data_core.pipelines.beam.io import WriteToBigQueryDoFn
from gdw_data_core.core.error_handling import ErrorContext, ErrorHandler
import apache_beam as beam

class CSVToBigQueryPipeline(BasePipeline):
    def build(self, pipeline: beam.Pipeline):
        (pipeline
            | 'Read CSV' >> beam.io.ReadFromText(self.config.source_file)
            | 'Parse' >> beam.ParDo(ParseCsvLine(['id', 'name', 'email']))
            | 'Enrich' >> beam.ParDo(EnrichWithMetadataDoFn(
                run_id=self.config.run_id,
                pipeline_name=self.config.pipeline_name
            ))
            | 'Write BQ' >> beam.ParDo(WriteToBigQueryDoFn(
                project=self.config.gcp_project_id,
                dataset=self.config.bigquery_dataset,
                table='records'
            ))
        )

# Run it
config = PipelineConfig(
    run_id='run_001',
    pipeline_name='csv_migration',
    entity_type='records',
    source_file='gs://bucket/data.csv',
    gcp_project_id='my-project',
    bigquery_dataset='my_dataset'
)

pipeline = CSVToBigQueryPipeline(config=config)
result = pipeline.run()
```

### Pattern 2: Data Validation Pipeline

```python
class ValidationPipeline(BasePipeline):
    def build(self, pipeline: beam.Pipeline):
        (pipeline
            | 'Read' >> beam.io.ReadFromText(self.config.source_file)
            | 'Parse' >> beam.ParDo(ParseCsvLine(['ssn', 'amount']))
            | 'Validate SSN' >> beam.ParDo(ValidateRecordDoFn(
                lambda r: validate_ssn(r['ssn'])
            ))
            | 'Validate Amount' >> beam.ParDo(ValidateRecordDoFn(
                lambda r: validate_numeric_range('amount', r['amount'], 0, 100000)
            ))
            | 'Write Valid' >> beam.ParDo(WriteToBigQueryDoFn(
                project=self.config.gcp_project_id,
                dataset=self.config.bigquery_dataset,
                table='valid_records'
            ))
        )
```

### Pattern 3: Error Handling in Processing Loop

```python
from gdw_data_core.core.error_handling import ErrorContext, ErrorHandler

def process_all_records(records):
    handler = ErrorHandler(pipeline_name="batch_job", run_id="run_001")
    
    processed = 0
    for record in records:
        with ErrorContext(handler, operation_name="process_record"):
            # Your processing logic - errors are caught automatically
            validate_record(record)
            enrich_record(record)
            load_to_database(record)
            processed += 1
    
    # Report results
    stats = handler.get_statistics()
    print(f"Processed {processed} records")
    print(f"Errors: {stats['error_count']}")
```

### Pattern 4: Full Pipeline with Audit & Monitoring

```python
from gdw_data_core.core.audit import AuditTrail
from gdw_data_core.core.monitoring import MetricsCollector
from gdw_data_core.core.error_handling import ErrorHandler, ErrorContext

def migrate_data(source_file, config):
    # Initialize services
    run_id = 'run_20231225_001'
    audit = AuditTrail(run_id=run_id, pipeline_name='loa_migration', entity_type='applications')
    metrics = MetricsCollector(pipeline_name='loa_migration', run_id=run_id)
    error_handler = ErrorHandler(pipeline_name='loa_migration', run_id=run_id)
    
    # Start processing
    audit.record_processing_start(source_file)
    
    try:
        for record in read_source(source_file):
            with ErrorContext(error_handler):
                metrics.increment('records_read')
                
                # Validate
                errors = validate_record(record)
                if errors:
                    metrics.increment('validation_errors')
                    continue
                
                # Transform
                transformed = transform_record(record)
                metrics.increment('records_transformed')
                
                # Load
                load_to_bigquery(transformed)
                metrics.increment('records_loaded')
        
        audit.increment_counts(valid=metrics.counters['records_loaded'])
        audit.record_processing_end(success=True)
        
    except Exception as e:
        audit.increment_counts(errors=metrics.counters.get('validation_errors', 0))
        audit.record_processing_end(success=False)
        raise
    
    # Report
    print(metrics.get_statistics())
```

---

## Configuration Examples

### Pipeline Configuration

```python
from gdw_data_core.pipelines.base import PipelineConfig

# Minimal config
config = PipelineConfig(
    run_id='run_001',
    pipeline_name='my_job'
)

# Full config
config = PipelineConfig(
    run_id='run_20231225_001',
    pipeline_name='loa_applications',
    entity_type='applications',
    source_file='gs://bucket/input/loa_apps.csv',
    gcp_project_id='my-gcp-project',
    bigquery_dataset='loa_dataset',
    additional_config={
        'batch_size': 1000,
        'max_retries': 3,
        'timeout_seconds': 300
    }
)
```

### Error Handler Configuration

```python
from gdw_data_core.core.error_handling import (
    ErrorHandler,
    InMemoryErrorStorage,
    GCSErrorStorage,
    ErrorConfig
)

# Production configuration
handler = ErrorHandler(
    pipeline_name='loa_migration',
    run_id='run_001',
    storage_backend=GCSErrorStorage(bucket='error-logs'),
    max_retries=3,
    base_retry_delay_seconds=1
)
```

---

### BDD Testing Framework

The library provides a standard way to implement BDD tests using `pytest-bdd`.

**Key Features:**
- `GDWScenarioTest`: Base class for BDD scenarios with automatic feature file resolution.
- Reusable steps: `common_steps`, `pipeline_steps`, `dq_steps`.
- Standardized markers for test categorization.

**Example Usage:**

```python
from gdw_data_core.testing.bdd import GDWScenarioTest
from gdw_data_core.testing.bdd.steps import common_steps, dq_steps

class TestMyDataQuality(GDWScenarioTest):
    # This automatically links to 'features/my_dq.feature'
    pass
```

---

## Testing

### Run All Tests

```bash
# All tests with coverage
pytest gdw_data_core/tests/ -v --cov=gdw_data_core

# Generate HTML coverage report
pytest gdw_data_core/tests/ --cov=gdw_data_core --cov-report=html
open htmlcov/index.html
```

### Run Specific Tests

```bash
# Single test file
pytest gdw_data_core/tests/test_validators.py -v

# Single test
pytest gdw_data_core/tests/test_validators.py::TestValidators::test_ssn_validation -v

# Tests matching pattern
pytest -k "validator" -v

# Tests excluding slow
pytest -m "not slow" -v
```

### Test Structure

```
gdw_data_core/tests/
├── test_validators.py
├── test_error_handling.py
├── test_audit.py
├── test_monitoring.py
├── beam/
│   ├── test_transforms.py
│   ├── test_io.py
│   └── test_pipelines.py
└── integration/
    └── test_full_pipeline.py
```

---

## Installation & Development

### Install for Development

```bash
# Clone repository
git clone <repo-url>
cd gdw_data_core

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install in editable mode
pip install -e ".[dev]"

# Install test dependencies
pip install pytest pytest-cov pytest-mock
```

### Project Structure

```
gdw_data_core/
├── core/                          # Core infrastructure modules
│   ├── validators/                # Validation logic
│   ├── error_handling/            # Error management
│   ├── audit/                     # Audit & reconciliation
│   ├── monitoring/                # Metrics & health
│   ├── utilities/                 # Common utilities
│   ├── data_quality/              # Quality checks
│   ├── file_management/           # File operations
│   │   └── hdr_trl/               # HDR/TRL parser submodule
│   ├── data_deletion/             # Data deletion framework
│   ├── job_control/               # Pipeline job tracking
│   └── clients/                   # GCS/BigQuery clients
├── orchestration/                 # Airflow orchestration
│   ├── callbacks/                 # Error handlers, DLQ
│   ├── factories/                 # DAG factories
│   ├── routing/                   # Task routing
│   ├── sensors/                   # Custom sensors
│   └── operators/                 # Custom operators
├── pipelines/                     # Pipeline framework
│   ├── base/                      # Base pipeline classes
│   ├── beam/                      # Apache Beam integration
│   │   ├── transforms/            # Beam DoFn transforms
│   │   ├── io/                    # I/O operations
│   │   ├── pubsub/                # Pub/Sub operations
│   │   └── builder.py             # Pipeline builder
│   └── orchestration/             # DAG generation
├── testing/                       # Testing utilities
│   ├── base/                      # Base test classes
│   ├── fixtures/                  # Pytest fixtures
│   ├── mocks/                     # Mock objects
│   ├── builders/                  # Test builders
│   └── assertions/                # Custom assertions
├── tests/                         # Test suite
│   ├── unit/                      # Unit tests (mirrors source structure)
│   └── integration/               # Integration tests
├── transformations/               # dbt transformations
│   └── dbt_shared/                # Shared dbt macros
├── README.md                      # This file
├── setup.py                       # Package setup
└── pyproject.toml                 # Project config
```

### Module Structure Rules

The library follows strict module organization rules:

#### When to Create a Submodule (Directory)

Create a submodule when:
- Module has **more than 1 class**
- Module has **more than 3 related functions**
- File would exceed **200 lines**

#### File Naming Conventions

| File Type | Naming Pattern | Example |
|-----------|---------------|---------|
| Types/Enums | `types.py` | `error_handling/types.py` |
| Constants | `constants.py` | `hdr_trl/constants.py` |
| Models/Dataclasses | `models.py` | `job_control/models.py` |
| Main Implementation | Descriptive name | `handler.py`, `parser.py` |

#### Test Structure

Tests MUST mirror source structure exactly:

```
# Source
core/file_management/hdr_trl/
├── types.py
├── constants.py
└── parser.py

# Tests (1:1 mapping)
tests/unit/core/file_management/hdr_trl/
├── test_types.py
├── test_constants.py
└── test_parser.py
```

---

## Extension Points

### Create Custom Validator

```python
from gdw_data_core.core.validators import ValidationError
from typing import List

def validate_custom(value: str) -> List[ValidationError]:
    """Custom validator for domain logic."""
    errors = []
    
    if len(value) < 5:
        errors.append(ValidationError(
            field='custom_field',
            value=value,
            message='Must be at least 5 characters'
        ))
    
    return errors
```

### Create Custom Error Handler

```python
from gdw_data_core.core.error_handling import ErrorHandler, ErrorClassifier

class CustomErrorHandler(ErrorHandler):
    def classify_error(self, exception: Exception):
        """Override error classification logic."""
        if isinstance(exception, CustomDomainException):
            return ('HIGH', 'BUSINESS_LOGIC', 'NO_RETRY')
        return super().classify_error(exception)
```

### Create Custom Beam Transform

```python
import apache_beam as beam

class CustomTransformDoFn(beam.DoFn):
    def process(self, element):
        # Your custom logic
        yield transformed_element
```

### Create Custom Pipeline

```python
from gdw_data_core.pipelines.base import BasePipeline
import apache_beam as beam

class CustomPipeline(BasePipeline):
    def build(self, pipeline: beam.Pipeline):
        # Your custom pipeline logic
        pass
```

---

## Pipeline Components (For Implementing New Pipelines)

The library provides **generic, configurable** components that pipelines use. Pipelines provide their own configuration.

### HDR/TRL File Parsing

Parse header and trailer records from mainframe extract files:

```python
from gdw_data_core.core.file_management import (
    HDRTRLParser,
    validate_record_count,
    validate_checksum,
)

# Default patterns (for CSV extracts)
# HDR|{SYSTEM}|{ENTITY}|{YYYYMMDD}
# TRL|RecordCount={n}|Checksum={hash}

parser = HDRTRLParser()  # Uses defaults

# Parse file
metadata = parser.parse_file_lines(lines)
print(f"System: {metadata.header.system_id}")
print(f"Entity: {metadata.header.entity_type}")
print(f"Records: {metadata.trailer.record_count}")

# Custom patterns for different file formats
parser = HDRTRLParser(
    hdr_pattern=r'^HEADER:(.+):(.+):(\d{8})$',
    trl_pattern=r'^FOOTER:COUNT=(\d+):HASH=(.+)$',
    hdr_prefix="HEADER:",
    trl_prefix="FOOTER:"
)
```

### File Validation

```python
from gdw_data_core.core.file_management import validate_record_count, validate_checksum
from gdw_data_core.core.data_quality import validate_row_types

# Validate row types (HDR first, TRL last)
is_valid, msg = validate_row_types(file_lines)  # Default prefixes
is_valid, msg = validate_row_types(file_lines, hdr_prefix="HEADER:", trl_prefix="FOOTER:")

# Validate record count
is_valid, msg = validate_record_count(lines, expected_count=5000, has_csv_header=True)

# Validate checksum
is_valid, msg = validate_checksum(data_lines, expected_checksum="a1b2c3d4")
```

### Entity Dependency Checking

For multi-entity pipelines that need to wait for all entities before transformation:

```python
from gdw_data_core.orchestration import EntityDependencyChecker

# Pipeline provides configuration - library is GENERIC
checker = EntityDependencyChecker(
    project_id="my-project",
    system_id="em",  # Pipeline provides
    required_entities=["customers", "accounts", "decision"]  # Pipeline provides
)

# Check if all entities are loaded for an extract date
if checker.all_entities_loaded(extract_date):
    trigger_transformation()

# Get missing entities
missing = checker.get_missing_entities(extract_date)
print(f"Waiting for: {missing}")
```

### Duplicate Key Detection

```python
from gdw_data_core.core.data_quality import check_duplicate_keys

records = [
    {"id": "1", "name": "John"},
    {"id": "1", "name": "Jane"},  # Duplicate
    {"id": "2", "name": "Bob"},
]

has_duplicates, duplicates = check_duplicate_keys(records, ["id"])
# has_duplicates = True
# duplicates = [{"key": {"id": "1"}, "count": 2}]
```

### Job Control

Track pipeline job status:

```python
from gdw_data_core.core.job_control import JobControlRepository, JobStatus, PipelineJob
from datetime import date

repo = JobControlRepository(project_id="my-project")

# Create job record
job = PipelineJob(
    run_id="run_20260101_001",
    system_id="em",
    entity_type="customers",
    extract_date=date(2026, 1, 1),
    source_files=["customers.csv"]
)
repo.create_job(job)

# Update status
repo.update_status(run_id, JobStatus.SUCCESS, total_records=5000)

# Mark failed
repo.mark_failed(
    run_id,
    error_code="HDR_INVALID",
    error_message="Header record missing",
    failure_stage=FailureStage.FILE_VALIDATION
)
```

### Common Import Patterns for Pipelines

```python
# File Management
from gdw_data_core.core.file_management import (
    HDRTRLParser,
    validate_record_count,
    validate_checksum,
)

# Data Quality
from gdw_data_core.core.data_quality import (
    validate_row_types,
    check_duplicate_keys,
)

# Job Control
from gdw_data_core.core.job_control import (
    JobControlRepository,
    JobStatus,
    PipelineJob,
)

# Entity Dependencies
from gdw_data_core.orchestration import EntityDependencyChecker

# Validators
from gdw_data_core.core.validators import (
    validate_ssn,
    validate_required,
    validate_length,
    ValidationError,
)
```

---

## Pub/Sub Integration (Event-Driven Triggers)

The library provides components for event-driven pipeline triggering using Google Cloud Pub/Sub with a **pull-based strategy**.

### Why Pull Strategy?

| Aspect | Pull (Library Choice) | Push |
|--------|----------------------|------|
| **Backpressure** | ✅ Consumer controls pace | ❌ Can overwhelm consumer |
| **Retry Control** | ✅ Consumer decides when | ❌ Limited control |
| **Ordering** | ✅ Guaranteed in subscription | ❌ Harder to maintain |
| **Reliability** | ✅ Retained until acknowledged | ❌ Fire and forget |

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EVENT-DRIVEN PIPELINE TRIGGER                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. FILE LANDS IN GCS                                                       │
│  ┌───────────────────┐                                                      │
│  │ gs://bucket/      │                                                      │
│  │   data.csv        │                                                      │
│  │   data.csv.ok ◄───┼── Signal file triggers notification                 │
│  └───────────────────┘                                                      │
│           │                                                                 │
│           ▼                                                                 │
│  2. GCS OBJECT NOTIFICATION                                                 │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │ Pub/Sub Topic                                                          │ │
│  │ • CMEK encrypted with Cloud KMS (infrastructure provides key)          │ │
│  │ • 90-day automatic key rotation                                        │ │
│  │ • 7-day message retention                                              │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│           │                                                                 │
│           ▼                                                                 │
│  3. PULL SUBSCRIPTION                                                       │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │ • Consumer (Airflow sensor) pulls messages                             │ │
│  │ • Acknowledges only after successful processing                        │ │
│  │ • Unacknowledged messages remain for retry                             │ │
│  │ • After max retries → Dead Letter Queue                                │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│           │                                                                 │
│           ▼                                                                 │
│  4. LIBRARY SENSOR (BasePubSubPullSensor)                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │ from gdw_data_core.orchestration.sensors import BasePubSubPullSensor   │ │
│  │                                                                         │ │
│  │ • Filters for .ok files only (configurable)                            │ │
│  │ • Extracts metadata (system, entity, date) to XCom                     │ │
│  │ • Triggers DAG execution on successful pull                            │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Using BasePubSubPullSensor

```python
from gdw_data_core.orchestration.sensors import BasePubSubPullSensor

# In your Airflow DAG
class MySystemPubSubSensor(BasePubSubPullSensor):
    """System-specific sensor extending library base."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            filter_extension='.ok',        # Filter for .ok files
            metadata_xcom_key='file_info',  # Store metadata in XCom
            **kwargs
        )

# Usage in DAG
sensor = MySystemPubSubSensor(
    task_id='wait_for_file',
    project_id='my-project',
    subscription='my-subscription',
)
```

### KMS Encryption Integration

The library is designed to work with CMEK-encrypted Pub/Sub topics:

```python
# Infrastructure (Terraform) provides the encrypted topic
# Library components work transparently with encrypted messages

# No special code needed - KMS decryption happens automatically
# when the service account has roles/cloudkms.cryptoKeyDecrypter
```

**Infrastructure Requirements (Terraform):**
- Create KMS keyring and crypto key
- Grant Pub/Sub service agent `roles/cloudkms.cryptoKeyEncrypterDecrypter`
- Configure topic with `kms_key_name`

See [GCP Deployment Guide](../docs/GCP_DEPLOYMENT_GUIDE.md) for Terraform examples.

---

## Dead Letter Queue (DLQ) Management

The library provides integrated dead letter queue support for handling failed messages.

### DLQ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DEAD LETTER QUEUE FLOW                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  MESSAGE PROCESSING                                                         │
│  ┌───────────────────┐                                                      │
│  │ Pull message      │                                                      │
│  │ from subscription │                                                      │
│  └─────────┬─────────┘                                                      │
│            │                                                                 │
│            ▼                                                                 │
│  ┌───────────────────┐     SUCCESS     ┌───────────────────┐               │
│  │ Process message   │ ───────────────► │ Acknowledge       │               │
│  │                   │                  │ Message removed   │               │
│  └─────────┬─────────┘                  └───────────────────┘               │
│            │                                                                 │
│            │ FAILURE                                                         │
│            ▼                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │ RETRY POLICY (Library ErrorHandler)                                    │ │
│  │                                                                         │ │
│  │ Attempt 1: Process → Fail → Wait 1 min                                 │ │
│  │ Attempt 2: Process → Fail → Wait 2 min (exponential backoff)           │ │
│  │ Attempt 3: Process → Fail → Wait 4 min                                 │ │
│  │ Attempt 4: Process → Fail → Wait 8 min                                 │ │
│  │ Attempt 5: Process → Fail → GIVE UP                                    │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│            │                                                                 │
│            │ AFTER MAX RETRIES                                              │
│            ▼                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │ DEAD LETTER QUEUE                                                       │ │
│  │                                                                         │ │
│  │ • Separate Pub/Sub topic for failed messages                           │ │
│  │ • 7-day retention for investigation                                    │ │
│  │ • Alerting integration (optional)                                      │ │
│  │ • Manual replay capability                                             │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Using DLQ with Error Callbacks

```python
from gdw_data_core.orchestration.callbacks import (
    on_failure_callback,
    publish_to_dlq,
    ErrorType,
)

# Configure DLQ in your DAG
default_args = {
    'on_failure_callback': on_failure_callback,  # Library callback
}

# Or manually publish to DLQ
def handle_permanent_failure(context, error_message, file_path):
    publish_to_dlq(
        project_id='my-project',
        topic='my-system-dead-letter',
        error_type=ErrorType.VALIDATION_FAILURE,
        error_message=error_message,
        file_path=file_path,
        context=context,
    )
```

### DLQ Error Types

| Error Type | Description | Typical Cause |
|------------|-------------|---------------|
| `VALIDATION_FAILURE` | File validation failed | Bad HDR/TRL, checksum mismatch |
| `SCHEMA_MISMATCH` | Schema doesn't match expected | Column changes, type errors |
| `DATA_QUALITY` | Data quality checks failed | Invalid values, duplicates |
| `PROCESSING_ERROR` | Pipeline processing failed | Dataflow errors, timeouts |
| `ROUTING_FAILURE` | Could not route to correct handler | Unknown entity, bad metadata |

### Monitoring DLQ

```python
from gdw_data_core.orchestration.callbacks import create_dlq_alert

# Create alert for DLQ messages (integrates with Cloud Monitoring)
create_dlq_alert(
    project_id='my-project',
    topic='my-system-dead-letter',
    notification_channel='my-slack-channel',
    threshold=1,  # Alert on any message
)
```

---

## Best Practices

### Error Handling

Always use `ErrorContext` for error handling:

```python
with ErrorContext(handler, operation_name="important_operation"):
    result = do_work()
    # Errors are automatically caught, classified, and retried
```

### Logging

Use structured logging:

```python
import logging

logger = logging.getLogger(__name__)

logger.info("Pipeline started", extra={
    'run_id': run_id,
    'entity_type': entity_type,
    'source_file': source_file
})
```

### Metrics

Collect meaningful metrics:

```python
metrics.increment("records_processed")
metrics.increment("records_valid")
metrics.increment("records_error")
metrics.set_gauge("queue_size", current_size)
```

### Type Hints

Use complete type hints:

```python
def process_records(records: List[Dict[str, Any]]) -> Tuple[int, int]:
    """Process records and return (success, error) counts."""
    processed = 0
    failed = 0
    # ...
    return processed, failed
```

### Testing

Write tests for all functionality:

```python
def test_my_function():
    result = my_function(input_data)
    assert result == expected_output
```

---

## License

This library is part of the LOA Blueprint project.

## Support

For issues, questions, or contributions, refer to the project documentation or contact the development team.

