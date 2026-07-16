# Error Handling Guide

This guide describes the error handling patterns used across GCP pipeline deployments. Error handling spans three Culvert layers: schema-grounded validation in `data_pipeline_core.dataquality`, DLQ/quarantine callbacks in `data_pipeline_orchestration.callbacks`, and metrics/tracing via the `ObservabilityHook` contract (`data_pipeline_core.contracts.observability`, GCP adapter in `data-pipeline-gcp-observability`) — providing consistent error classification, retry logic, dead letter routing, and structured reporting across all three deployment units.

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
gs://myproject-generic-int-error/customers/20260101/
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

Validation is schema-grounded via `data_pipeline_core.dataquality`:

```python
from data_pipeline_core.dataquality import DataQualityTransform, InvalidRow
from data_pipeline_core.schema import EntitySchema, SchemaField

schema = EntitySchema(
    name="customers",
    fields=[
        SchemaField("customer_id", "STRING", mode="REQUIRED"),
        SchemaField("ssn", "STRING"),
    ],
)
dq = DataQualityTransform(schema=schema, row_accessor=lambda row: row)

result = dq.validate(record)
if not result.is_valid():
    assert isinstance(result, InvalidRow)
    result.violations  # [FieldViolation(field_name, violation_kind, detail), ...]
```

In the Java ingestion pipeline (`deployments/original-data-to-bigqueryload-java`),
the same `DataQualityTransform` (Java twin, `com.enrichmeai.culvert.dataquality`)
runs inline and `InvalidRow` results are routed to the dead letter table — see
`IngestionRunner` and `InvalidRowAdapter`.

### 2. Failure Callbacks for Unhandled Exceptions

Unhandled task exceptions are captured by the error-handling callbacks in
`data_pipeline_orchestration.callbacks`, which log the full context and publish
to the Dead Letter Queue:

```python
from data_pipeline_orchestration.callbacks import ErrorHandler, ErrorHandlerConfig

config = ErrorHandlerConfig(
    dlq_topic="generic-pipeline-dlq",
    quarantine_bucket="myproject-generic-int-error",
)
handler = ErrorHandler(config)

# Wire onto any Airflow task (the DagFactory does this for you)
task = PythonOperator(
    task_id="run_ingestion",
    python_callable=run_ingestion,
    on_failure_callback=handler.on_failure_callback,
)
```

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
| `original-data-to-bigqueryload-java` (Ingestion) | Parse failure | `gs://{PROJECT_ID}-generic-{ENV}-error/` |
| `original-data-to-bigqueryload-java` (Ingestion) | Validation failure | `odp_generic.{entity}_failed` |
| `bigquery-to-mapped-product` (Transformation) | dbt test failure | BigQuery error logs + job_control FAILED |
| `data-pipeline-orchestrator` (Orchestration) | DAG task failure | Airflow task log + job_control FAILED |

---

## CSV Parsing

Legacy mainframe extracts have common data quality issues (missing columns, EBCDIC artifacts, wrong delimiters, corrupted rows). CSV parsing now lives in the Java ingestion pipeline: `CsvRowParser` in
[`deployments/original-data-to-bigqueryload-java`](../deployments/original-data-to-bigqueryload-java/)
handles HDR/TRL envelope stripping and field parsing, and rows that fail to
parse are routed to the error path rather than failing the job (see
`IngestionRunner` and the `envelope/` package). There is no Python Beam CSV
parser — Beam execution is Java-only.

### CSV Error Types

| Error Type | Description |
|------------|-------------|
| `FIELD_COUNT_MISMATCH` | Wrong number of fields |
| `ENCODING_ERROR` | Cannot decode as UTF-8 |
| `WRONG_DELIMITER` | Parsing failed with all delimiters |
| `CORRUPTED_ROW` | Truncated data, null bytes, embedded newlines |
| `QUOTE_MISMATCH` | Unbalanced quotes in quoted fields |

---

## BigQuery Retry

BigQuery operations can fail with transient errors (quota exceeded, rate limits, table locks). Warehouse writes go through the `Warehouse` contract (`data_pipeline_core.contracts.warehouse` / `com.enrichmeai.culvert.contracts.Warehouse`). The Java ingestion pipeline stages rows to GCS and loads them via `BigQueryWarehouse.loadFromUri` (a batch load job, which BigQuery retries server-side), rather than per-record streaming inserts — see `data-pipeline-gcp-bigquery-java` and `IngestionRunner` in
[`deployments/original-data-to-bigqueryload-java`](../deployments/original-data-to-bigqueryload-java/).
Transient load-job failures surface as `CRITICAL` job failures and are retried at the orchestration layer (Airflow task retries).

### BigQuery Error Classification

| Error Type | Retryable | Typical Cause |
|------------|-----------|---------------|
| `QUOTA_EXCEEDED` | Yes | Project quota limits |
| `RATE_LIMIT` | Yes | Too many requests/sec |
| `TABLE_LOCK` | Yes | Concurrent writes |
| `BACKEND_ERROR` | Yes | Transient service issues |
| `TIMEOUT` | Yes | Long operations |
| `INVALID_DATA` | No | Bad data values |
| `SCHEMA_MISMATCH` | No | Wrong data types |
| `NOT_FOUND` | No | Missing table/dataset |

---

## References

- [data-pipeline-orchestration — error-handling callbacks](../data-pipeline-libraries/data-pipeline-orchestration/src/data_pipeline_orchestration/callbacks/)
- [data-pipeline-core — dataquality module](../data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/dataquality/)
- [Data Quality Guide](./DATA_QUALITY_GUIDE.md) — validation rules and Dataplex integration
- [E2E Functional Flow](./E2E_FUNCTIONAL_FLOW.md) — full pipeline flow including error states
- [GCP Deployment Guide](./GCP_DEPLOYMENT_GUIDE.md) — infrastructure setup for error buckets
