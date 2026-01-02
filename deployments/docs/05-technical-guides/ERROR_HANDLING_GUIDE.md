# 🛑 LOA Blueprint - Error Handling Guide

## Overview
This guide describes the error handling patterns used in the LOA migration pipelines. Error handling is built on the GDW Data Core library, providing consistent error classification, retry logic, and structured reporting.

## Core Concepts
- **Error Classification**: Errors are categorized by severity (INFO, WARNING, CRITICAL) and category (VALIDATION, INTEGRATION, TRANSFORM, RESOURCE).
- **Retry Strategy**: Automated retries for transient errors (e.g., network issues) based on configurable policies.
- **Error Context**: Python context managers (`ErrorContext`) ensure consistent error capture and logging across pipeline steps.
- **Dead Letter Queues**: Malformed records are routed to specific error tables/buckets for manual investigation.

## Usage in Pipelines

### 1. Simple Validation Error
When a record fails validation, it is tagged with a `ValidationError` and routed to the error output.

```python
from gdw_data_core.core.validators import ValidationError

def validate_record(record):
    errors = []
    if not record.get('ssn'):
        errors.append(ValidationError("ssn", None, "SSN is required"))
    return errors
```

### 2. Wrapping Execution with ErrorContext
The `ErrorContext` manager captures any unhandled exceptions during execution.

```python
from gdw_data_core.core.error_handling import ErrorHandler, ErrorContext

handler = ErrorHandler(pipeline_name="loa-applications", run_id="run_001")

with ErrorContext(handler, operation_name="dataflow_execution"):
    # Run your pipeline logic here
    result = run_dataflow_pipeline()
```

## Error Storage
- **BigQuery Error Tables**: Detailed error logs including the raw record, error field, and message.
- **GCS Quarantine**: Files that cannot be parsed at all are moved to a quarantine bucket.

## References
- [GDW Data Core - Error Handling](../../gdw_data_core/README.md#error-handling)
- [Testing Strategy](./TESTING_STRATEGY.md)
