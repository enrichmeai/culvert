# Prompt: Library Enhancement - Standardized Monitoring Metrics

**STATUS: ✅ COMPLETE**

## Context
While Dataflow provides some built-in metrics, there is no standardized way for the migration framework to report business-level metrics (e.g., "records processed per second", "validation failure rate by entity type") consistently across all systems.

## What Was Implemented

### 1. Core Metrics Module ✅
**File:** `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/monitoring/metrics.py`

- Created `MigrationMetrics` class with standard metrics:
  - `records_read` - Total records read from source
  - `records_parsed` - Records successfully parsed  
  - `records_validated` - Records that passed validation
  - `records_failed` - Records that failed validation
  - `records_written` - Records written to destination
  - `processing_duration_ms` - Processing time histogram
  - `validation_errors` - Count by error type
- All metrics tagged with `run_id`, `system_id`, `entity_type`
- `get_summary()` returns counts and rates
- `to_job_record()` for pipeline_jobs table update

### 2. Structured JSON Logging ✅
**File:** `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/utilities/logging.py`

- `StructuredLogger` class with context injection
- `configure_structured_logging()` setup function
- JSON output format for Cloud Logging
- Automatic inclusion of run_id, system_id, entity_type

### 3. EM Pipeline Integration ✅
**File:** `deployments/em/src/em/pipeline/em_pipeline.py`

```python
# Configure structured JSON logging
logger = configure_structured_logging(
    run_id=run_id,
    system_id=SYSTEM_ID,
    entity_type=entity,
    logger_name="em_pipeline"
)

# Initialize migration metrics
metrics = MigrationMetrics(
    run_id=run_id,
    system_id=SYSTEM_ID,
    entity_type=entity
)

logger.info("Pipeline starting", input_pattern=..., output_table=...)
# ... pipeline execution ...
logger.info("Pipeline completed successfully", counts=summary['counts'], rates=summary['rates'])
```

### 4. LOA Pipeline Integration ✅
**File:** `deployments/loa/src/loa/pipeline/loa_pipeline.py`

Same pattern as EM - structured logging and metrics integrated.

## Test Results

```
=== LIBRARY ===  559 passed ✅
=== EM ===       199 passed ✅
=== LOA ===       55 passed ✅
─────────────────────────
TOTAL:           813 tests
```

## Usage Example

```python
from gcp_pipeline_builder.utilities import configure_structured_logging
from gcp_pipeline_builder.monitoring import MigrationMetrics

# Setup
logger = configure_structured_logging(run_id="em_123", system_id="EM", entity_type="customers")
metrics = MigrationMetrics(run_id="em_123", system_id="EM", entity_type="customers")

# During processing
metrics.record_read(1000)
metrics.record_validated(950)
metrics.record_failed(50)

# Log with context (JSON output)
logger.info("Processing complete", records=1000, validation_rate=95.0)

# Get summary for job control
summary = metrics.get_summary()
# {'counts': {'read': 1000, 'validated': 950, 'failed': 50}, 'rates': {'validation_success_rate': 95.0}}

job_record = metrics.to_job_record()
# Ready for pipeline_jobs table update
```

## Output Format (Cloud Logging Compatible)

```json
{
  "timestamp": "2026-01-05T22:30:00.123Z",
  "level": "INFO",
  "message": "Pipeline starting",
  "run_id": "em_customers_20260105_223000_abc123",
  "system_id": "EM",
  "entity_type": "customers",
  "input_pattern": "gs://bucket/em/customers/*.csv",
  "output_table": "odp_em.customers"
}
```
