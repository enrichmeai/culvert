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
│ run_id()    │    │ .start()    │    │ Logging     │
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
```

---

## Tests

```bash
PYTHONPATH=src python -m pytest tests/unit/ -v
# 208 passed
```

