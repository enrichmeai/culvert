# gcp-pipeline-core

Foundation library - audit, monitoring, error handling, job control.

**NO Apache Beam or Airflow dependencies.**

---

## Modules

| Module | Purpose |
|--------|---------|
| `audit/` | Lineage tracking, reconciliation, audit trail |
| `monitoring/` | Metrics collection, OTEL/Dynatrace integration |
| `error_handling/` | Error classification, retry logic, DLQ |
| `job_control/` | Pipeline job status and metadata |
| `clients/` | GCS, BigQuery, Pub/Sub client wrappers |
| `utilities/` | Structured logging, run ID generation |
| `schema.py` | EntitySchema, SchemaField definitions |

---

## Usage

```python
from gcp_pipeline_core.audit import AuditTrail, ReconciliationEngine
from gcp_pipeline_core.monitoring import MetricsCollector
from gcp_pipeline_core.utilities import configure_structured_logging, generate_run_id
from gcp_pipeline_core.schema import EntitySchema, SchemaField
```

---

## Tests

```bash
PYTHONPATH=src python -m pytest tests/unit/ -v
# 208 passed
```

