# Error Handling Guide

This guide describes the error handling patterns used across GCP pipeline deployments. Error handling is built on the `gcp-pipeline-core` library, providing consistent error classification, retry logic, dead letter routing, and structured reporting across all three deployment units.

---

## Error Classification

All pipeline errors are classified on two dimensions:

### Severity

| Severity | Description | Action |
|----------|-------------|--------|
| `INFO` | Informational — record skipped by design (e.g., duplicate) | Log only |
| `WARNING` | Recoverable — record routed to dead letter queue for review | Log + DLQ |
| `CRITICAL` | Pipeline failure — job marked FAILED in `job_control` | Alert + halt |

### Category

| Category | Examples | Retry? |
|----------|---------|--------|
| `VALIDATION` | Missing required field, invalid data type, failed schema check | No |
| `TRANSFORM` | dbt model failure, NULL join key, assertion failure | No |
| `INTEGRATION` | BigQuery write timeout, Dataflow worker OOM, GCS permission denied | Yes (transient) |
| `RESOURCE` | Pub/Sub subscription not found, missing GCS bucket | No — infra fix required |

---

## Storage Destinations

### GCS Error Bucket

Files that fail to parse at intake (e.g., malformed CSV, missing HDR record) are quarantined to the GCS error bucket:

```
gs://{PROJECT_ID}-generic-{ENV}-error/{entity}/{extract_date}/
```

Example:
```
gs://myproject-generic-dev-error/customers/20260101/
  customers_20260101_PARSE_FAILED.csv
  customers_20260101_PARSE_FAILED.meta.json
```

### BigQuery Dead Letter Tables

Individual records that fail validation or transformation are written to dead letter tables:

```
{PROJECT_ID}.odp_generic.{entity}_failed
```

Example schema:

| Column | Type | Description |
|--------|------|-------------|
| `_run_id` | STRING | Pipeline run identifier |
| `_error_timestamp` | TIMESTAMP | When the error occurred |
| `_error_category` | STRING | `VALIDATION`, `TRANSFORM`, `INTEGRATION` |
| `_error_severity` | STRING | `INFO`, `WARNING`, `CRITICAL` |
| `_error_field` | STRING | Field that caused the error (if applicable) |
| `_error_message` | STRING | Human-readable error description |
| `_raw_record` | JSON | Original record as received |

---

## Usage in Pipelines

### 1. Validation Errors (Ingestion Unit)

```python
from gcp_pipeline_core.data_quality.validators import ValidationError

def validate_record(record):
    errors = []
    if not record.get('customer_id'):
        errors.append(ValidationError(
            field="customer_id",
            value=None,
            message="customer_id is required"
        ))
    if record.get('ssn') and len(record['ssn']) != 9:
        errors.append(ValidationError(
            field="ssn",
            value=record['ssn'],
            message="SSN must be exactly 9 digits"
        ))
    return errors
```

Records with validation errors are tagged and routed to the dead letter output via Beam's `TaggedOutput`:

```python
# In your DoFn
yield pvalue.TaggedOutput('errors', {
    '_error_category': 'VALIDATION',
    '_error_severity': 'WARNING',
    '_error_field': error.field,
    '_error_message': error.message,
    '_raw_record': json.dumps(record),
})
```

### 2. ErrorContext for Unhandled Exceptions

Wrap any step that could raise an unexpected exception:

```python
from gcp_pipeline_core.error_handling import ErrorHandler, ErrorContext

handler = ErrorHandler(
    pipeline_name="{system_id}-ingestion",
    run_id=run_id,
)

with ErrorContext(handler, operation_name="dataflow_execution"):
    result = run_dataflow_pipeline()
```

If an exception escapes, `ErrorContext` logs it with full context (operation, run_id, timestamp) before re-raising, ensuring it is captured in Cloud Logging.

### 3. Job Control Integration

The orchestration DAG updates `job_control` status on success or failure:

```python
# In the ODP Load DAG — failure callback
def on_pipeline_failure(context):
    repo = JobControlRepository(project_id=PROJECT_ID)
    repo.update_status(
        run_id=context['ti'].xcom_pull(key='run_id'),
        status='FAILED',
        error_message=str(context.get('exception', 'Unknown error')),
    )
```

---

## Retry Policy

| Error Type | Retry Strategy | Max Retries | Backoff |
|------------|---------------|-------------|---------|
| BigQuery write timeout | Exponential | 3 | 30s, 60s, 120s |
| GCS read permission denied | None (permanent) | 0 | — |
| Pub/Sub message delivery | Pub/Sub built-in | Unlimited | Cloud-managed |
| Dataflow worker failure | Dataflow built-in | 4 | Cloud-managed |
| dbt model failure | Airflow retry | 1 | 5 min |

Transient integration errors are retried automatically by Dataflow and Airflow. Validation and transform errors are **never retried** — they are routed to the dead letter queue for manual investigation.

---

## Monitoring and Alerting

### Cloud Logging — Find Errors

```bash
# All CRITICAL errors for a specific run
gcloud logging read \
  'resource.type="dataflow_step" AND jsonPayload.severity="CRITICAL" AND jsonPayload.run_id="{run_id}"' \
  --project={PROJECT_ID} \
  --format="json" \
  --limit=50
```

### BigQuery — Inspect Dead Letter Records

```sql
-- Recent validation failures for customers entity
SELECT
    _run_id,
    _error_timestamp,
    _error_field,
    _error_message,
    JSON_VALUE(_raw_record, '$.customer_id') AS customer_id
FROM `{PROJECT_ID}.odp_generic.customers_failed`
WHERE DATE(_error_timestamp) = CURRENT_DATE()
ORDER BY _error_timestamp DESC
LIMIT 100;
```

### Airflow — Failed DAG Runs

In the Airflow UI, failed runs appear in red. The `error_handling_dag` monitors the `job_control` table and can trigger alerts or retry flows for recoverable failures.

---

## Error Handling in Each Deployment Unit

| Unit | Error Type | Destination |
|------|-----------|------------|
| `original-data-to-bigqueryload` (Ingestion) | Parse failure | `gs://{PROJECT_ID}-generic-{ENV}-error/` |
| `original-data-to-bigqueryload` (Ingestion) | Validation failure | `odp_generic.{entity}_failed` |
| `bigquery-to-mapped-product` (Transformation) | dbt test failure | BigQuery error logs + job_control FAILED |
| `data-pipeline-orchestrator` (Orchestration) | DAG task failure | Airflow task log + job_control FAILED |

---

## References

- [gcp-pipeline-core — Error Handling module](../gcp-pipeline-libraries/gcp-pipeline-core/README.md#error-handling)
- [Complete Testing Guide](./COMPLETE_TESTING_GUIDE.md) — how to test error paths
- [E2E Functional Flow](./E2E_FUNCTIONAL_FLOW.md) — full pipeline flow including error states
- [GCP Deployment Guide](./GCP_DEPLOYMENT_GUIDE.md) — infrastructure setup for error buckets
