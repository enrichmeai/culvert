# gcp-pipeline-core

Foundation library - audit, monitoring, error handling, job control.

**NO Apache Beam or Airflow dependencies.**

---

## Architecture

```
                         GCP-PIPELINE-CORE
                         ─────────────────

  ┌─────────────────────────────────────────────────────────────────┐
  │                     FOUNDATION LAYER                             │
  │                                                                  │
  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
  │  │   Audit     │  │  Monitoring │  │   Error     │              │
  │  │   Trail     │  │   Metrics   │  │  Handling   │              │
  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
  │         │                │                │                      │
  │         ▼                ▼                ▼                      │
  │  ┌─────────────────────────────────────────────────────────┐    │
  │  │                  Utilities Layer                         │    │
  │  │  • Structured Logging (JSON)                             │    │
  │  │  • Run ID Generation                                     │    │
  │  │  • Configuration Management                              │    │
  │  └─────────────────────────────────────────────────────────┘    │
  │         │                │                │                      │
  │         ▼                ▼                ▼                      │
  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
  │  │   Clients   │  │ Job Control │  │   Schema    │              │
  │  │ GCS/BQ/PS   │  │  Repository │  │ Definitions │              │
  │  └─────────────┘  └─────────────┘  └─────────────┘              │
  │                                                                  │
  └─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
              Used by: gcp-pipeline-beam, gcp-pipeline-orchestration
```

---

## Modules

| Module | Purpose | Key Classes |
|--------|---------|-------------|
| `audit/` | Lineage tracking, reconciliation | `AuditTrail`, `ReconciliationEngine` |
| `monitoring/` | Metrics, health, alerts, OTEL tracing | `MetricsCollector`, `MigrationMetrics`, `ObservabilityManager`, `AlertManager`, `OTELConfig` |
| `finops/` | Cost tracking and labeling | `BigQueryCostTracker`, `FinOpsLabels` |
| `error_handling/` | Error classification, retry | `ErrorHandler`, `RetryPolicy` |
| `job_control/` | Pipeline status tracking | `JobControlRepository`, `PipelineJob` |
| `clients/` | GCP service wrappers | `GCSClient`, `BigQueryClient`, `PubSubClient` |
| `utilities/` | Logging, run ID | `configure_structured_logging`, `generate_run_id` |
| `data_quality/` | Quality checks, scoring, anomaly detection | `DataQualityChecker`, `QualityScore`, `AnomalyDetector` |
| `data_deletion/` | Quarantine, safe deletion, recovery | `DataDeletionFramework`, `SafeDataDeletion`, `RecoveryManager` |
| `schema.py` | Entity definitions | `EntitySchema`, `SchemaField` |

---

## Component Flow

```
Pipeline Start
      │
      ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ generate_   │───►│ AuditTrail  │───►│ Structured  │
│ run_id()    │    │ .record_processing_start()    │    │ Logging     │
└─────────────┘    └─────────────┘    └─────────────┘
      │                  │                  │
      ▼                  ▼                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ JobControl  │    │ Metrics     │    │ Error       │
│ .create()   │    │ .record()   │    │ Handler     │
└─────────────┘    └─────────────┘    └─────────────┘
      │                  │                  │
      └──────────────────┴──────────────────┘
                         │
                         ▼
                  ┌─────────────┐
                  │ Reconcile   │
                  │ & Complete  │
                  └─────────────┘
```

---

## Key Findings

### 1. Audit Trail & Lineage
- **AuditTrail**: Implements robust tracking of `run_id` across all pipeline stages.
- **DuplicateDetector**: Provides idempotency by tracking seen records and preventing double-processing.
- **Publisher**: Supports automated publishing of audit records to BigQuery for centralized monitoring.

### 2. Sophisticated Error Handling
- **ErrorClassifier**: Categorizes exceptions into:
    - **Validation**: Data errors (no retry).
    - **Integration**: Connection/API errors (retry with backoff).
    - **Resource**: Quota/Rate limit errors (exponential backoff).
- **RetryPolicy**: Configurable backoff multipliers, jitter, and maximum retry attempts.

### 3. Job Control
- **JobControlRepository**: Centralized state management for pipeline executions.
- **State Tracking**: Granular tracking of failure stages, start/end times, and record counts.

### 4. Structured Logging
- Standardized JSON logging with automated context injection (`run_id`, `system_id`).
- Optimized for Cloud Logging and BigQuery ingestion.

### 5. FinOps & Cost Tracking
- **Cost Estimation**: Automated cost estimation for BigQuery (Query/Load), GCS (Storage/Upload), and Pub/Sub (Publishing).
- **FinOpsLabels**: Standardized GCP resource labeling for precise cost allocation.
- **Monitoring Integration**: Seamless integration with `MigrationMetrics` for real-time cost visibility in audit logs.
- **Trackers**:
    - `BigQueryCostTracker`: Estimates costs based on bytes billed and slot usage.
    - `CloudStorageCostTracker`: Estimates storage costs and upload fees.
    - `PubSubCostTracker`: Estimates throughput costs with 1KB minimum billing awareness.
- **Decorators**: `@track_bq_cost` for automated tracking of BigQuery jobs.

### 6. Monitoring & Observability

The `monitoring/` module provides a layered observability stack — from low-level metric counters through health checks and alerts to full OpenTelemetry distributed tracing.

#### Architecture

```
ObservabilityManager (facade — combines all three)
├── MetricsCollector         Thread-safe counters, gauges, histograms, timers
│   └── MigrationMetrics     Standardized pipeline metrics + FinOps metrics
├── HealthChecker            5-check health assessment (error rate, queue depth, memory, etc.)
└── AlertManager             Multi-backend alerting
    ├── LoggingAlertBackend       Python logging (default)
    ├── SlackAlertBackend         Slack Webhooks (Block Kit)
    ├── DynatraceAlertBackend     Dynatrace Events API v2
    ├── ServiceNowAlertBackend    ServiceNow incident creation
    ├── CloudMonitoringBackend    Google Cloud Monitoring
    └── DatadogAlertBackend       Datadog (stub)
```

#### MigrationMetrics — Pipeline-Level Metrics

High-level metrics API with standardized names for all pipeline stages:

```python
from gcp_pipeline_core.monitoring import MigrationMetrics

metrics = MigrationMetrics(run_id="run_20260323", system_id="generic", entity_type="customers")

# Record processing counts
metrics.record_read(1000)
metrics.record_validated(995)
metrics.record_failed(5, error_type="schema_validation")
metrics.record_written(995)

# FinOps integration
metrics.record_cost(0.42)
metrics.record_bytes_scanned(1_073_741_824)

# Timing
with metrics.start_timer("transform"):
    transform_records()

# Summary (includes validation success rate, FinOps, timing)
summary = metrics.get_summary()
job_record = metrics.to_job_record()  # Ready for pipeline_jobs table
```

#### HealthChecker — Automated Health Assessment

```python
from gcp_pipeline_core.monitoring import HealthChecker, MetricsCollector

collector = MetricsCollector("my_pipeline", "run_001")
health = HealthChecker(collector)

results = health.run_all_checks()
# Checks: record_processing, error_rate (≤10%), queue_depth (≤1000),
#          processing_time (≤3600s), memory_usage (≤1024MB)

if not health.is_healthy():
    # Trigger alert
```

#### AlertManager — Multi-Backend Alerting

```python
from gcp_pipeline_core.monitoring import AlertManager, AlertLevel
from gcp_pipeline_core.monitoring.alerts import SlackAlertBackend, DynatraceAlertBackend, ServiceNowAlertBackend

manager = AlertManager(alert_backends=[
    SlackAlertBackend(webhook_url="https://hooks.slack.com/..."),
    DynatraceAlertBackend(environment_url="https://xyz.live.dynatrace.com", api_token="dt0c01..."),
    ServiceNowAlertBackend(instance_url="https://company.service-now.com", username="...", password="...",
                           assignment_group="Data Engineering"),
])

# Sends to all configured backends simultaneously
manager.create_alert(
    level=AlertLevel.CRITICAL,
    title="Pipeline Failure: customers",
    message="Schema validation failed for 500 records",
    source="gcp-pipeline-beam",
    metric_name="records_failed",
    threshold_value=0,
    actual_value=500,
)

# Query recent alerts
critical_alerts = manager.get_recent_alerts(minutes=60, level=AlertLevel.CRITICAL)
```

#### ObservabilityManager — Unified Facade

```python
from gcp_pipeline_core.monitoring import ObservabilityManager

obs = ObservabilityManager("my_pipeline", "run_001", alert_backends=[...])
obs.report_records_processed(1000)
obs.report_records_error(5)

# Auto-triggers WARNING alert if any health check fails
is_healthy = obs.check_health()

# Full summary: metrics + health + recent alerts
print(obs.export_metrics())
```

#### OpenTelemetry Integration (Optional)

Full distributed tracing with graceful degradation — if OTEL SDK is not installed, all tracing calls become no-ops (zero overhead).

```python
from gcp_pipeline_core.monitoring import configure_otel, OTELConfig, trace_function, OTELContext

# Configure for GCP Cloud Trace
config = OTELConfig.for_gcp_otlp(service_name="generic-ingestion", project_id="my-project")
configure_otel(config)

# Or Dynatrace
config = OTELConfig.for_dynatrace(
    service_name="generic-ingestion",
    dynatrace_url="https://xyz.live.dynatrace.com/api/v2/otlp",
    dynatrace_token="dt0c01...",
)

# Decorator: auto-creates spans per function call
@trace_function(span_name="validate_records", attributes={"entity": "customers"})
def validate_records(records):
    ...

# Context manager: pipeline-level + child spans
with OTELContext(run_id="run_001", system_id="generic", entity_type="customers") as ctx:
    with ctx.span("parse_csv"):
        parse_csv_files()
    with ctx.span("validate"):
        validate_records()

# Bridge: export existing MetricsCollector data to OTEL backends
from gcp_pipeline_core.monitoring import OTELMetricsBridge
bridge = OTELMetricsBridge(collector, meter_name="pipeline_metrics")
bridge.increment("records_processed", 100)  # Forwards to BOTH collector AND OTEL
```

**Supported OTEL exporters:**

| Exporter | Config Factory | Endpoint |
|---|---|---|
| GCP Native OTel | `OTELConfig.for_gcp_otlp()` | `telemetry.googleapis.com:443` |
| Google Cloud Trace | `OTELConfig.for_gcp()` | Cloud Trace API |
| Dynatrace | `OTELConfig.for_dynatrace()` | OTLP/HTTP with `Api-Token` header |
| Any OTLP (Jaeger, etc.) | `OTELConfig(exporter_type=OTLP, otlp_endpoint="...")` | gRPC OTLP |
| Console (debug) | `OTELConfig.for_console()` | stdout |
| Disabled | `OTELConfig.disabled()` | No-op |

### 7. Data Quality

Six-dimension quality scoring with anomaly detection:

- **Completeness** (95% threshold), **Validity** (90%), **Accuracy** (exact match), **Uniqueness** (100%), **Timeliness** (80%)
- **`DataQualityChecker`**: orchestrates all dimensions with `get_quality_report()`
- **`ScoreCalculator`**: letter grades (A-F) from weighted dimension scores
- **`AnomalyDetector`**: IQR-based outlier detection on numeric fields

### 8. Data Deletion & Recovery

Safe, auditable data deletion with approval workflows:

- **`MalformationDetector`**: detects malformed records with 10 categorized reasons
- **`QuarantineManager`**: 4-level quarantine (REVIEW, HOLD, DELETE, ARCHIVE)
- **`SafeDataDeletion`**: approval-gated deletion with configurable batch sizes
- **`RecoveryManager`** / **`GCSRecoveryManager`**: checkpoint-based recovery (in-memory or GCS-persisted)

---

## Governance & Compliance

- **Zero-Bleed Policy**: This library **MUST NOT** import `apache_beam` or `airflow`.
- **Portability**: Must remain compatible with any Python environment (Cloud Functions, Cloud Run, local scripts, etc.).
- **Testing**: All new features require unit tests in `tests/unit/`.

---

## Usage

```python
from gcp_pipeline_core.audit import AuditTrail, ReconciliationEngine
from gcp_pipeline_core.monitoring import MetricsCollector, MigrationMetrics, ObservabilityManager
from gcp_pipeline_core.monitoring import AlertManager, AlertLevel, OTELConfig, configure_otel
from gcp_pipeline_core.monitoring.alerts import SlackAlertBackend, DynatraceAlertBackend
from gcp_pipeline_core.utilities import configure_structured_logging, generate_run_id
from gcp_pipeline_core.schema import EntitySchema, SchemaField
from gcp_pipeline_core.job_control import JobControlRepository, JobStatus, PipelineJob
from gcp_pipeline_core.error_handling import ErrorHandler, RetryPolicy
from gcp_pipeline_core.finops import BigQueryCostTracker, FinOpsLabels, track_bq_cost
from gcp_pipeline_core.data_quality import DataQualityChecker
from gcp_pipeline_core.data_deletion import DataDeletionFramework
```

---

## Tests

```bash
python3.11 -m pytest tests/ -v
# 256 passed
```

