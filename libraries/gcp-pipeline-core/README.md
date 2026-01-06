 w# gcp-pipeline-core

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

