# Pipeline Observability & Monitoring Spec

## 1. Purpose

Wire the full monitoring, alerting, auditing, and observability capabilities from the core library (`gcp-pipeline-core`) into the orchestration layer (generated DAGs). The core library already provides all the building blocks — this spec defines how each is connected to the pipeline DAGs.

## 2. Current State

### What the Core Library Provides (complete, tested)

| # | Capability | Module | Key Classes |
|---|-----------|--------|-------------|
| 1 | **Slack alerts** | `monitoring.alerts` | `SlackAlertBackend`, `AlertManager` |
| 2 | **Cloud Monitoring alerts** | `monitoring.alerts` | `CloudMonitoringBackend` |
| 3 | **Datadog alerts** | `monitoring.alerts` | `DatadogAlertBackend` |
| 4 | **Health checks** | `monitoring.health` | `HealthChecker` (error rate, queue depth, memory, processing time) |
| 5 | **Unified observability** | `monitoring.observability` | `ObservabilityManager` (metrics + health + alerts) |
| 6 | **Metrics collection** | `monitoring.metrics` | `MetricsCollector`, `MigrationMetrics` |
| 7 | **OpenTelemetry tracing** | `monitoring.otel.*` | `OTELProvider`, `OTELContext`, `OTELMetricsBridge` |
| 8 | **Audit trail** | `audit.trail` | `AuditTrail`, `DuplicateDetector` |
| 9 | **Audit publishing** | `audit.publisher` | `AuditPublisher` → Pub/Sub |
| 10 | **Data lineage** | `audit.lineage` | `DataLineageTracker` |
| 11 | **Reconciliation** | `audit.reconciliation` | `ReconciliationEngine` |
| 12 | **FinOps cost tracking** | `finops.tracker` | `BigQueryCostTracker`, `CloudStorageCostTracker`, `PubSubCostTracker` |
| 13 | **Error handling callbacks** | `orchestration.callbacks` | `ErrorHandler`, DLQ publishing, file quarantine |

### What's Wired into DAGs Today

| Capability | Trigger DAG | Ingestion DAG | Transformation DAG | Status DAG |
|-----------|-------------|---------------|-------------------|------------|
| AuditTrail | Yes (parse/validate) | Yes (via callback) | No | No |
| JobControlRepository | No | Yes (create/update/fail) | Yes (create/update/fail) | Yes (query) |
| ReconciliationEngine | No | Yes (ODP count) | Yes (FDP count) | No |
| ErrorHandler/GCSErrorStorage | File → error bucket | Yes (on_failure_callback) | Yes (on_failure_callback) | No |
| Email alerts | Yes (default_args) | Yes (default_args) | Yes (default_args) | Yes (default_args) |
| **Dynatrace alerts** | **No** | **No** | **No** | **No** |
| **ServiceNow incidents** | **No** | **No** | **No** | **No** |
| **AuditPublisher** | **No** | **No** | **No** | **No** |
| **DataLineageTracker** | **No** | **No** | **No** | **No** |
| **FinOps cost tracking** | **No** | **No** | **No** | **No** |
| **HealthChecker** | **No** | **No** | **No** | **No** |
| **ObservabilityManager** | **No** | **No** | **No** | **No** |
| **OpenTelemetry** | **No** | **No** | **No** | **No** |
| **Cloud Monitoring** | **No** | **No** | **No** | **No** |

### What the Original Hardcoded DAGs Had (commit a526ecd, before factory)

The original 4 DAGs had basic auditing but **no** Slack, no AuditPublisher, no lineage, no FinOps, no health checks, no OTEL. The `error_handling_dag.py` was the most advanced — it had error categorization (CRITICAL/VALIDATION/INTEGRATION), automatic retry routing, and manual review queues. That error routing logic was **not** carried forward into the factory pattern.

---

## 3. Deliverables — Phased

### Phase 1: Immediate (this PR) — Items 1–3

| # | Item | Where | What |
|---|------|-------|------|
| **1** | **Dynatrace + ServiceNow alerts on failure** | All 4 generated DAGs | `DynatraceAlertBackend` → sends events to Dynatrace Events API v2 (appears in Problems feed, triggers Davis AI). `ServiceNowAlertBackend` → creates incidents via Table API with severity mapping. Graceful no-op if not configured. |
| **2** | **Reconciliation verification** | Ingestion + Transformation DAGs | Already wired — verify generated code matches factory. No new work needed if generator output is correct. |
| **3** | **Audit publishing to Pub/Sub** | Ingestion + Transformation DAGs | After each successful job, publish `AuditRecord` to `generic-pipeline-events` topic via `AuditPublisher`. Includes run_id, entity, record counts, duration, success/fail, audit hash. |

### Phase 2: Medium Term — Items 4–5

| # | Item | Where | What |
|---|------|-------|------|
| **4** | **FinOps cost tracking** | Ingestion DAG (post-Dataflow), Transformation DAG (post-dbt) | After each Dataflow/dbt run, call `BigQueryCostTracker.estimate_query_cost()` or `estimate_load_cost()`. Store cost metrics in `job_control.pipeline_jobs` metadata column. |
| **5** | **Health check in status DAG** | Pipeline Status DAG | Replace simple pass/fail with `HealthChecker` — check error rate across the day's runs, flag DEGRADED if >10% entities failed. Use `ObservabilityManager` for unified reporting. |

### Phase 3: Longer Term — Items 6–8

| # | Item | Where | What |
|---|------|-------|------|
| **6** | **Data lineage** | Ingestion + Transformation DAGs | After successful load, call `DataLineageTracker.generate_data_lineage()` and publish to Pub/Sub audit topic. Enables downstream lineage consumers (Data Catalog, compliance). |
| **7** | **OpenTelemetry tracing** | All DAGs | Initialize `OTELProvider` at DAG parse time. Wrap each task callable in `OTELContext.span()`. Export to GCP Cloud Trace or Dynatrace via `OTELConfig.for_gcp()` / `OTELConfig.for_dynatrace()`. |
| **8** | **Cloud Monitoring custom metrics** | All DAGs | Push `MigrationMetrics` (records processed, duration, error rate, cost) to Cloud Monitoring via `CloudMonitoringBackend`. Enables Grafana/Cloud Monitoring dashboards and alerting policies. |

---

## 4. Phase 1 — Detailed Design

### 4.1 Dynatrace + ServiceNow Alerts on Failure

**Approach:** Add a `_send_failure_alert()` helper to each generated DAG that routes to Dynatrace Events API v2 and ServiceNow Table API. Wire it into the existing `on_failure_callback` chain.

**Airflow Variables (all optional — graceful no-op if not configured):**

| Variable | Purpose |
|----------|---------|
| `dynatrace_environment_url` | Dynatrace SaaS URL (e.g., `https://xyz.live.dynatrace.com`) |
| `dynatrace_api_token` | API token with `events.ingest` scope |
| `servicenow_instance_url` | ServiceNow instance (e.g., `https://mycompany.service-now.com`) |
| `servicenow_username` | ServiceNow API user |
| `servicenow_password` | ServiceNow API password |
| `servicenow_assignment_group` | Assignment group for created incidents |

**Dynatrace event payload:**
- `eventType`: `ERROR_EVENT` (CRITICAL), `CUSTOM_ALERT` (WARNING), `CUSTOM_INFO` (INFO)
- `title`: Pipeline failure summary (200 char max)
- `properties`: alert_id, source, level, run_id, entity, failure_stage

**ServiceNow incident payload:**
- `impact`/`urgency`: 1 (CRITICAL), 2 (WARNING), 3 (INFO)
- `category`: "Data Pipeline"
- `subcategory`: DAG ID
- `short_description`: Pipeline failure summary
- `description`: Full error details + metadata

**Implementation in generated DAGs:**

```python
from gcp_pipeline_core.monitoring.alerts import (
    AlertManager, DynatraceAlertBackend, ServiceNowAlertBackend, LoggingAlertBackend,
)
from gcp_pipeline_core.monitoring.types import AlertLevel

def _get_alert_manager() -> AlertManager:
    """Create AlertManager with Dynatrace and ServiceNow backends if configured."""
    backends = [LoggingAlertBackend()]
    try:
        dt_url = Variable.get("dynatrace_environment_url")
        dt_token = Variable.get("dynatrace_api_token")
        if dt_url and dt_token:
            backends.append(DynatraceAlertBackend(
                environment_url=dt_url, api_token=dt_token,
            ))
    except Exception:
        pass
    try:
        snow_url = Variable.get("servicenow_instance_url")
        snow_user = Variable.get("servicenow_username")
        snow_pass = Variable.get("servicenow_password")
        if snow_url and snow_user:
            backends.append(ServiceNowAlertBackend(
                instance_url=snow_url, username=snow_user, password=snow_pass,
                assignment_group=Variable.get("servicenow_assignment_group", default_var=""),
            ))
    except Exception:
        pass
    return AlertManager(alert_backends=backends)
```

**Where applied:**
- Ingestion DAG: `mark_job_failed()` callback
- Transformation DAG: `mark_fdp_job_failed()` callback
- Trigger DAG: `move_to_error_bucket()` task (file validation failures)
- Status DAG: `check_pipeline_status()` (pipeline incomplete at end of day)

### 4.2 Reconciliation Verification

**Current state:** The factory (`dag_factory.py`) already has `ReconciliationEngine` in both:
- `reconcile_odp_load()` — compares HDR/TRL record_count vs BigQuery ODP table
- `reconcile_fdp_model_output()` — compares ODP source tables vs FDP output table

**Verification:** Confirm that `generate_dags.py` produces code that matches the factory's reconciliation logic 1:1. The generated ingestion and transformation DAGs must contain the same reconciliation tasks.

**Acceptance criteria:**
- `generic_ingestion_dag.py` contains `reconcile_odp_load` task with `ReconciliationEngine`
- `generic_transformation_dag.py` contains `reconcile_fdp_model` task with `ReconciliationEngine`
- Both raise `Exception` on mismatch (fail the DAG run)

### 4.3 Audit Publishing to Pub/Sub

**Approach:** After each successful pipeline run, publish an `AuditRecord` to the `generic-pipeline-events` Pub/Sub topic.

**Airflow Variable:** `audit_pubsub_topic` (default: `generic-pipeline-events`)

**Implementation in generated DAGs:**

```python
from gcp_pipeline_core.audit.publisher import AuditPublisher
from gcp_pipeline_core.audit.records import AuditRecord
from gcp_pipeline_core.audit.lineage import DataLineageTracker

def _publish_audit_record(run_id, pipeline_name, entity, source_file,
                          record_count, duration_seconds, success, error_count, metadata=None):
    """Publish audit record to Pub/Sub for downstream consumers."""
    project_id = _get_project_id()
    topic = Variable.get("audit_pubsub_topic", default_var="generic-pipeline-events")
    try:
        record = AuditRecord(
            run_id=run_id,
            pipeline_name=pipeline_name,
            entity_type=entity,
            source_file=source_file,
            record_count=record_count,
            processed_timestamp=datetime.now(tz=timezone.utc),
            processing_duration_seconds=duration_seconds,
            success=success,
            error_count=error_count,
            audit_hash="",  # computed by publisher
            metadata=metadata or {},
        )
        publisher = AuditPublisher(project_id=project_id, topic_name=topic)
        msg_id = publisher.publish(record)
        logger.info(f"Published audit record to {topic}: {msg_id}")
    except Exception as e:
        logger.warning(f"Audit publishing failed (non-fatal): {e}")
```

**Where applied:**
- Ingestion DAG: `update_job_success()` — publish after marking SUCCESS
- Transformation DAG: `update_fdp_job_success()` — publish after marking SUCCESS
- Both: `mark_*_failed()` callbacks — publish on failure too (success=False)

---

## 5. Airflow Variables Required

| Variable | Default | Required | Purpose |
|----------|---------|----------|---------|
| `dynatrace_environment_url` | (none) | No | Dynatrace SaaS URL for Events API |
| `dynatrace_api_token` | (none) | No | Dynatrace API token (`events.ingest` scope) |
| `servicenow_instance_url` | (none) | No | ServiceNow instance URL |
| `servicenow_username` | (none) | No | ServiceNow API user |
| `servicenow_password` | (none) | No | ServiceNow API password |
| `servicenow_assignment_group` | (none) | No | ServiceNow assignment group |
| `audit_pubsub_topic` | `generic-pipeline-events` | No | Pub/Sub topic for audit records |
| `gcp_project_id` | `$GCP_PROJECT_ID` env var | Yes | GCP project (already exists) |

---

## 6. Infrastructure Required

### Phase 1
- Dynatrace environment with API token (stored as Airflow Variable or Secret Manager)
- ServiceNow instance with API user (stored as Airflow Variable or Secret Manager)
- `generic-pipeline-events` Pub/Sub topic (already exists per MEMORY.md)

### Phase 2
- `pipeline_jobs.metadata` column in job_control (for cost metrics storage)

### Phase 3
- Cloud Trace API enabled
- Cloud Monitoring custom metric descriptors
- Optional: Dynatrace environment + API token

---

## 7. Testing

### Phase 1 Tests

```
tests/
├── test_generate_dags.py          # Generator produces valid Python
├── test_alerting.py               # Mock Dynatrace/ServiceNow backends, verify alert created on failure
├── test_audit_publishing.py       # Mock AuditPublisher, verify record published on success/failure
└── test_reconciliation_wiring.py  # Verify generated DAGs contain reconciliation tasks
```

**Generator test:**
```python
def test_generated_dags_are_valid_python():
    """Each generated DAG file must be valid Python (compile check)."""
    config = load_config(Path("config/system.yaml"))
    for suffix, gen_fn in DAG_GENERATORS.items():
        code = gen_fn(config)
        compile(code, f"<generated_{suffix}>", "exec")  # raises SyntaxError if invalid
```

**Alerting test:**
```python
def test_dynatrace_alert_sent_on_failure(mock_variable, mock_dynatrace):
    """Verify Dynatrace event fires when task fails."""
    mock_variable.side_effect = lambda key, **kw: {
        "dynatrace_environment_url": "https://xyz.live.dynatrace.com",
        "dynatrace_api_token": "dt0c01.test",
    }.get(key, kw.get("default_var", ""))
    # simulate failure callback context
    # assert mock_dynatrace.send_alert called with CRITICAL → ERROR_EVENT

def test_servicenow_incident_created_on_failure(mock_variable, mock_snow):
    """Verify ServiceNow incident created when task fails."""
    # assert mock_snow.send_alert called with impact=1 for CRITICAL
```

---

## 8. Acceptance Criteria

### Phase 1
- [x] `generate_dags.py` produces 4 DAG files with full observability stack
- [x] Dynatrace events + ServiceNow incidents fire on any task failure (graceful no-op if not configured)
- [x] Audit records published to Pub/Sub on success and failure
- [x] Reconciliation tasks present in ingestion and transformation DAGs
- [x] All generated DAGs pass `compile()` check
- [ ] Existing unit tests still pass

### Phase 2
- [x] FinOps cost metrics stored in job_control via `update_cost_metrics()` after each successful run
- [x] Status DAG uses `ObservabilityManager` with error rate tracking and health checks

### Phase 3
- [x] OTEL initialized at DAG parse time via `_init_otel()` → Dynatrace (primary) or GCP Cloud Trace (fallback)
- [x] Cloud Monitoring custom metrics pushed on success/failure: `odp_load_success/failure`, `fdp_transform_success/failure`
- [x] Data lineage published to Pub/Sub via `DataLineageTracker` after each successful load
