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
| `monitoring/` | Metrics, OTEL/Dynatrace | `MetricsCollector`, `OTELExporter` |
| `finops/` | Cost tracking and labeling | `BigQueryCostTracker`, `FinOpsLabels` |
| `error_handling/` | Error classification, retry | `ErrorHandler`, `RetryPolicy` |
| `job_control/` | Pipeline status tracking | `JobControlRepository`, `PipelineJob` |
| `clients/` | GCP service wrappers | `GCSClient`, `BigQueryClient`, `PubSubClient` |
| `utilities/` | Logging, run ID | `configure_structured_logging`, `generate_run_id` |
| `data_quality/` | Quality checks | `validate_row_types`, `check_duplicate_keys` |
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

---

## Governance & Compliance

- **Zero-Bleed Policy**: This library **MUST NOT** import `apache_beam` or `airflow`.
- **Portability**: Must remain compatible with any Python environment (Cloud Functions, Cloud Run, local scripts, etc.).
- **Testing**: All new features require unit tests in `tests/unit/`.

---

## Usage

```python
from gcp_pipeline_core.audit import AuditTrail, ReconciliationEngine
from gcp_pipeline_core.monitoring import MetricsCollector
from gcp_pipeline_core.utilities import configure_structured_logging, generate_run_id
from gcp_pipeline_core.schema import EntitySchema, SchemaField
from gcp_pipeline_core.job_control import JobControlRepository
from gcp_pipeline_core.error_handling import ErrorHandler
from gcp_pipeline_core.finops import BigQueryCostTracker, FinOpsLabels, track_bq_cost
```

---

## Tests

```bash
python3.11 -m pytest tests/ -v
# 256 passed
```

