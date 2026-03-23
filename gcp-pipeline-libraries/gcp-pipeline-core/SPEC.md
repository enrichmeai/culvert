# Specification: gcp-pipeline-core

**Version:** 1.0
**Layer:** Foundation — used by all other libraries and all deployments
**Dependency rule:** MUST NOT import `apache_beam` or `apache_airflow`

---

## Purpose

Portable, framework-agnostic utilities for audit, error handling, job control, observability,
and schema definition. Works in any Python environment: Dataflow workers, Airflow tasks,
Cloud Functions, local scripts.

---

## Boundary Rules

| Rule | Rationale |
|------|-----------|
| MUST NOT import `apache_beam` | Keeps library usable outside Beam |
| MUST NOT import `apache_airflow` | Keeps library usable outside Airflow |
| MUST NOT use `print()` for operational output | All output must go through `logging` |
| MUST NOT contain entity-specific business logic | Library provides mechanisms, not rules |

---

## Module Contracts

### `schema` — EntitySchema & SchemaField

**Purpose:** Single source of truth for entity definitions. Drives validation, BQ schema generation, PII tracking, and dbt enrichment.

**Contract:**

| Method | Precondition | Postcondition |
|--------|-------------|---------------|
| `EntitySchema.to_bq_schema(include_audit=True)` | Valid fields list | Returns list of BQ schema dicts; includes `_run_id`, `_source_file`, `_processed_at` when `include_audit=True` |
| `EntitySchema.get_pii_fields()` | — | Returns names of all fields where `is_pii=True` |
| `EntitySchema.get_required_fields()` | — | Returns names of all fields where `required=True` |
| `EntitySchema.get_field(name)` | — | Returns `SchemaField` or `None`; never raises |
| `SchemaField` | — | `is_pii=True` fields MUST also set `pii_type` |

**Test scenarios:**
- `to_bq_schema()` maps `STRING` → `STRING`, `INTEGER` → `INT64`, `BOOLEAN` → `BOOL`
- `to_bq_schema(include_audit=True)` appends exactly 3 audit columns
- `to_bq_schema(include_audit=False)` contains no audit columns
- `get_pii_fields()` returns only fields with `is_pii=True`
- `get_field()` with unknown name returns `None`
- Unknown `field_type` defaults to `STRING` in BQ schema

---

### `audit.AuditTrail`

**Purpose:** Track pipeline executions. Record start, end, counts, and errors. Publish to external system via `AuditPublisher`.

**Contract:**

| Method | Precondition | Postcondition |
|--------|-------------|---------------|
| `record_processing_start(source_file)` | — | Sets `self.source_file`; logs via `logging`, not `print()` |
| `record_processing_end(success)` | `record_processing_start` called first | Returns `AuditRecord`; calls `publisher.publish()` if publisher set |
| `increment_counts(valid, errors)` | — | `records_processed == records_valid + records_error` always |
| `log_entry(status, message)` | — | Appends `AuditEntry`; logs via `logging.getLogger(__name__)` |
| `_generate_audit_hash()` | `record_processing_end` in progress | Returns deterministic SHA-256 hex string |

**Test scenarios:**
- After `increment_counts(valid=5, errors=2)`, `records_processed == 7`
- `record_processing_end()` returns `AuditRecord` with correct counts
- Audit hash is deterministic for same inputs
- `log_entry()` appends to `self.entries` and is retrievable via `get_entries_by_status()`
- With `publisher=None`, `record_processing_end()` completes without error
- With `publisher` set, `publisher.publish()` is called exactly once

---

### `audit.DuplicateDetector`

**Purpose:** Detect duplicate records within a pipeline run. In-memory; single-process only.

**Contract:**

| Method | Precondition | Postcondition |
|--------|-------------|---------------|
| `is_duplicate(record, key_fields)` | — | First call with given key returns `False`; subsequent identical keys return `True` |
| `find_duplicates(records, key_fields)` | — | Returns only the 2nd+ occurrence of each key; never the first |
| `mark_as_processed(record_id)` | — | Future `is_duplicate(record_id)` returns `True` |

**Test scenarios:**
- Same string record ID seen twice → second call returns `True`
- Dict record with `key_fields` → composite key built from field values
- `find_duplicates([r1, r1, r2])` → returns `[r1]` (one duplicate)
- Empty `records` list → returns empty list

---

### `audit.ReconciliationEngine`

**Purpose:** Compare source record count (from trailer) with BigQuery actual count. Pass/fail per run.

**Contract:**

| Method | Precondition | Postcondition |
|--------|-------------|---------------|
| `reconcile_counts(source, destination, error)` | All ints ≥ 0 | Returns `RECONCILED` when `source == destination + error`; `MISMATCH` otherwise |
| `reconcile_with_bigquery(expected, table)` | Valid BQ table path | Queries BQ; falls back to `ERROR` status on exception (does not raise) |
| `reconcile_from_trailer(trailer_record, table)` | `trailer_record.record_count` exists | Delegates to `reconcile_with_bigquery` |

**Test scenarios:**
- `reconcile_counts(1000, 998, 2)` → `RECONCILED`, `match_percentage == 100.0`
- `reconcile_counts(1000, 950, 2)` → `MISMATCH`, `difference == 48`
- `reconcile_counts(0, 0, 0)` → `RECONCILED`
- BQ query exception → `ERROR` status, no exception propagated
- `get_reconciliation_report()` before any reconciliation → returns informative string

---

### `error_handling.ErrorClassifier`

**Purpose:** Classify any exception into severity, category, and retry strategy. Stateless.

**Contract:**

| Classification | Trigger | Retry strategy |
|---------------|---------|---------------|
| `VALIDATION / NO_RETRY` | `ValueError`, `TypeError`, CSV errors | No retry |
| `INTEGRATION / EXPONENTIAL_BACKOFF` | Connection errors, timeout | Retry with backoff |
| `RESOURCE / EXPONENTIAL_BACKOFF` | Quota exceeded, rate limit | Retry with backoff |
| `CONFIGURATION / MANUAL_ONLY` | Permission denied, unauthorized | No automatic retry |
| `UNKNOWN / MANUAL_ONLY` | Unrecognised exception | No automatic retry |

**Test scenarios:**
- `ValueError` → `VALIDATION`, `NO_RETRY`
- `ConnectionError` → `INTEGRATION`, `EXPONENTIAL_BACKOFF`
- Exception with "quota" in message → `RESOURCE`, `EXPONENTIAL_BACKOFF`
- Exception with "permission denied" in message → `CONFIGURATION`, `MANUAL_ONLY`
- Unrecognised exception type → `UNKNOWN`, `MANUAL_ONLY`

---

### `error_handling.RetryPolicy`

**Contract:**

| Method | Postcondition |
|--------|--------------|
| `should_retry(error)` | `False` when `retry_count >= max_retries` or strategy is `NO_RETRY`/`MANUAL_ONLY` |
| `calculate_backoff(error)` | Returns `int` seconds; respects `max_retry_delay_seconds`; adds jitter when `jitter_enabled=True` |
| `schedule_retry(error)` | Returns `datetime` in the future; or `None` if not retryable |

**Test scenarios:**
- Exponential backoff: delay doubles each retry
- Delay never exceeds `max_retry_delay_seconds`
- `NO_RETRY` strategy → `calculate_backoff` returns `None`
- `IMMEDIATE` strategy → `calculate_backoff` returns `0`

---

### `error_handling.ErrorHandler`

**Contract:**

| Method | Postcondition |
|--------|--------------|
| `handle_exception(exc)` | Creates `PipelineError`; appends to `self.errors`; logs at appropriate level; stores if backend configured; triggers alert for `CRITICAL` |
| `prepare_retry(error)` | Increments `retry_count`; sets `next_retry_timestamp`; returns `True` if retry scheduled |
| `mark_resolved(error_id)` | Sets `error.resolved = True` |
| `export_errors()` | Returns valid JSON string |

**Test scenarios:**
- Error ID is unique per call (no collisions across concurrent calls)
- `get_critical_errors()` returns only `CRITICAL` severity errors
- `export_errors()` produces valid JSON
- `mark_resolved()` with unknown ID logs warning, does not raise

---

### `job_control.JobControlRepository`

**Purpose:** CRUD for `job_control.pipeline_jobs` in BigQuery.

**Contract:**
- All SQL queries use `@parameter` binding — no string interpolation of user data
- `create_job()` sets initial status to `PENDING`
- `update_status(RUNNING)` sets `started_at`; `update_status(SUCCESS)` sets `completed_at`
- `mark_failed()` records `error_code`, `error_message`, `failure_stage`

**Test scenarios (use mock BQ client):**
- `create_job()` inserts exactly one row
- `update_status(SUCCESS, total_records=1000)` updates `total_records`
- `get_job(unknown_run_id)` returns `None`
- `get_pending_jobs()` returns only PENDING status jobs

---

### `utilities.logging` — StructuredLogger

**Purpose:** JSON-formatted logging for Cloud Logging. Auto-injects `run_id`, `system_id`, `entity_type`.

**Contract:**
- All output is valid JSON
- `run_id`, `system_id`, `entity_type` appear in every log entry when set
- Extra kwargs passed to `info()`, `warning()` etc. appear as top-level JSON fields
- `configure_structured_logging()` removes duplicate handlers on re-call

**Test scenarios:**
- Log entry parses as valid JSON
- `logger.info("msg", records=100)` → JSON contains `"records": 100`
- Context set via `set_context()` appears in subsequent log entries

---

### `utilities.run_id` — generate_run_id

**Contract:**
- Format: `{job_name}_{YYYYMMDD}_{HHMMSS}_{uuid8}` (with UUID) or `{job_name}_{YYYYMMDD}_{HHMMSS}` (without)
- Empty `job_name` raises `ValueError`
- `validate_run_id()` returns `True` for correctly formatted IDs; `False` otherwise

**Test scenarios:**
- `generate_run_id("my_job")` returns string matching expected format
- `generate_run_id("my_job", include_uuid=False)` returns string without UUID suffix
- `generate_run_id("")` raises `ValueError`
- `validate_run_id("job_20260101_120000_ab12cd34")` → `True`
- `validate_run_id("invalid")` → `False`

---

### `monitoring.MetricsCollector`

**Purpose:** Thread-safe metric collection. Stores counters, gauges, histograms, and timers in memory.

**Contract:**

| Method | Precondition | Postcondition |
|--------|-------------|---------------|
| `increment(name, value=1)` | `value ≥ 0` | Counter increases by `value`; `MetricValue` appended to history |
| `set_gauge(name, value)` | — | Gauge set to exact `value` |
| `record_histogram(name, value)` | — | Value added to distribution; retrievable in `get_statistics()` |
| `start_timer()` | — | Returns `TimerContext`; on `__exit__`, records duration |
| `get_statistics()` | — | Returns dict with all counters, gauges, histogram summaries (min/max/avg/count) |

**Test scenarios:**
- `increment("x", 5)` three times → counter value is 15
- `get_statistics()` returns histogram with correct min/max/avg
- Thread-safe: concurrent increments do not lose counts

---

### `monitoring.MigrationMetrics`

**Purpose:** Standardized metric names for pipeline stages. Wraps `MetricsCollector` with convenience methods.

**Contract:**

| Method | Metric Name | Type |
|--------|------------|------|
| `record_read(count)` | `records_read` | counter |
| `record_validated(count)` | `records_validated` | counter |
| `record_failed(count, error_type)` | `records_failed` | counter |
| `record_written(count)` | `records_written` | counter |
| `record_cost(cost_usd)` | `finops_estimated_cost_usd` | gauge |
| `get_summary()` | — | Returns dict with `counts`, `rates`, `finops`, `duration` |
| `to_job_record()` | — | Returns dict suitable for `pipeline_jobs` table update |

---

### `monitoring.HealthChecker`

**Purpose:** Assess pipeline health from MetricsCollector data.

**Contract:**

| Check | Threshold | Returns `True` when |
|-------|-----------|-------------------|
| `check_record_processing()` | — | `records_processed > 0` |
| `check_error_rate(threshold=0.1)` | 10% default | `error_count / processed_count ≤ threshold` |
| `check_queue_depth(max=1000)` | 1000 default | `queue_depth gauge ≤ max` |
| `check_processing_time(max=3600)` | 1 hour default | `uptime_seconds ≤ max` |
| `check_memory_usage(max=1024)` | 1GB default | `memory_usage_mb gauge ≤ max` |

- `run_all_checks()` runs all 5; stores results
- `is_healthy()` returns `True` only if ALL checks passed

---

### `monitoring.AlertManager`

**Purpose:** Create and dispatch alerts to pluggable backends.

**Contract:**

| Method | Postcondition |
|--------|--------------|
| `create_alert(level, title, message, source, ...)` | Alert created with unique ID; sent to all backends; appended to history |
| `get_recent_alerts(minutes=60, level=None)` | Returns alerts from last N minutes; optionally filtered by level |

**Backend contract** (`AlertBackend` ABC):
- `send_alert(alert) → bool` — returns `True` on success, `False` on failure (MUST NOT raise)

**Implemented backends:**

| Backend | Status | External Service |
|---------|--------|-----------------|
| `LoggingAlertBackend` | Production | Python logging |
| `SlackAlertBackend` | Production | Slack Webhooks (Block Kit) |
| `DynatraceAlertBackend` | Production | Events API v2 |
| `ServiceNowAlertBackend` | Production | Table API (incident creation) |
| `CloudMonitoringBackend` | Partial | Google Cloud Monitoring |
| `DatadogAlertBackend` | Stub | Datadog API |

---

### `monitoring.otel` — OpenTelemetry Integration

**Purpose:** Distributed tracing and metrics export. Optional — all calls degrade to no-ops when OTEL SDK is not installed.

**Contract:**

| Function/Class | Postcondition |
|---------------|--------------|
| `configure_otel(config)` | Initializes global `OTELProvider`; returns `True` on success |
| `get_tracer(name)` | Returns OTEL Tracer or `_NoOpTracer` if unavailable |
| `get_meter(name)` | Returns OTEL Meter or `_NoOpMeter` if unavailable |
| `@trace_function(span_name)` | Creates span per function call; records exception on error |
| `@trace_beam_dofn` | Wraps DoFn `process()` method; creates span per element |
| `OTELContext(run_id, system_id)` | Context manager; creates root span; `span()` creates children |
| `OTELMetricsBridge(collector)` | Forwards all metric ops to BOTH `MetricsCollector` AND OTEL |

**Graceful degradation guarantee:**
- If `opentelemetry` package is not installed, `is_otel_available()` returns `False`
- All tracing/metrics calls become zero-cost no-ops
- No `ImportError` or runtime exception
