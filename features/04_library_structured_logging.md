# Prompt: Library Enhancement - Structured JSON Logging

**STATUS: ✅ COMPLETE**

## Context
Currently, the library uses standard Python logging, which is often inconsistent across different modules. For production cloud environments like GCP, structured JSON logging is essential for effective log analysis, monitoring, and alerting in Cloud Logging.

## What Was Implemented

### 1. Core Logging Module ✅
**File:** `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/utilities/logging.py`

- `StructuredLogger` class with context injection
- `StructuredJsonFormatter` for JSON output
- `configure_structured_logging()` setup function
- `get_logger()` to retrieve existing logger
- 16 unit tests passing

### 2. EM Pipeline Integration ✅
**File:** `deployments/em/src/em/pipeline/em_pipeline.py`

```python
from gcp_pipeline_builder.utilities import configure_structured_logging, generate_run_id

def run_em_pipeline(argv=None):
    # ...
    run_id = em_opts.run_id or generate_run_id(f"em_{entity}")

    # Configure structured JSON logging
    logger = configure_structured_logging(
        run_id=run_id,
        system_id=SYSTEM_ID,
        entity_type=entity,
        logger_name="em_pipeline"
    )

    logger.info("Pipeline starting", input_pattern=..., output_table=...)
    # ... pipeline execution ...
    logger.info("Pipeline completed successfully", counts=..., rates=...)
```

### 3. LOA Pipeline Integration ✅
**File:** `deployments/loa/src/loa/pipeline/loa_pipeline.py`

Same pattern as EM - structured logging configured at pipeline start.

---

## Usage Guide

### Basic Usage (Recommended)
```python
from gcp_pipeline_builder.utilities import configure_structured_logging

# Configure at pipeline start - returns a StructuredLogger
logger = configure_structured_logging(
    run_id="em_20260105_143022_abc123",
    system_id="EM",
    entity_type="customers"
)

# Log with automatic context injection
logger.info("Processing started", records=1000)
logger.warning("Slow processing", duration_ms=5000)
logger.error("Validation failed", error_count=50)
```

### Output Format (Cloud Logging Compatible)
```json
{
  "timestamp": "2026-01-05T14:30:22.123456+00:00",
  "level": "INFO",
  "message": "Processing started",
  "logger": "em_pipeline",
  "module": "em_pipeline",
  "function": "run_em_pipeline",
  "line": 125,
  "run_id": "em_20260105_143022_abc123",
  "system_id": "EM",
  "entity_type": "customers",
  "records": 1000
}
```

### Updating Context Mid-Pipeline
```python
# Change entity type during processing
logger.set_context(entity_type="accounts")
logger.info("Switching to accounts processing")
```

### Getting Existing Logger
```python
from gcp_pipeline_builder.utilities import get_logger

# In a different module
logger = get_logger("em_pipeline")
logger.info("Message from sub-module")
```

---

## Configuration Options

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `run_id` | No | None | Pipeline run identifier |
| `system_id` | No | None | System identifier (EM, LOA) |
| `entity_type` | No | None | Entity being processed |
| `level` | No | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `logger_name` | No | "gcp_pipeline" | Name for the logger |
| `stream` | No | sys.stdout | Output stream |

---

## Cloud Logging Integration

The JSON output is automatically parsed by GCP Cloud Logging:

```
Cloud Logging → Parses JSON automatically
       ↓
Error grouping by message
       ↓
Alerting on severity
       ↓
Dashboards showing run_id, system_id, entity_type
```

### Filtering Examples in Cloud Logging
```
# Find all errors for a specific run
jsonPayload.run_id="em_20260105_143022_abc123" AND jsonPayload.level="ERROR"

# Find all EM customer processing logs
jsonPayload.system_id="EM" AND jsonPayload.entity_type="customers"

# Find slow operations
jsonPayload.duration_ms > 5000
```

---

## Test Results

```
tests/unit/utilities/test_logging.py - 16 tests passed ✅
```

---

## Files Modified

| File | Change |
|------|--------|
| `utilities/logging.py` | Created StructuredLogger, configure_structured_logging |
| `utilities/__init__.py` | Added exports |
| `em/pipeline/em_pipeline.py` | Uses structured logging |
| `loa/pipeline/loa_pipeline.py` | Uses structured logging |
