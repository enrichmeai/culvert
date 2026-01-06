# Libraries

4-library architecture for mainframe-to-GCP data migration.

---

## Architecture

```
gcp-pipeline-core (Foundation - NO beam, NO airflow)
        ↓
   ┌────┴────┐
   ↓         ↓
gcp-pipeline-beam         gcp-pipeline-orchestration
(Ingestion)               (Control)
```

---

## Libraries

| Library | Purpose | Tests |
|---------|---------|-------|
| [gcp-pipeline-core](gcp-pipeline-core/) | Audit, monitoring, error handling, job control | 208 |
| [gcp-pipeline-beam](gcp-pipeline-beam/) | Beam pipelines, transforms, file management | 358 |
| [gcp-pipeline-orchestration](gcp-pipeline-orchestration/) | Airflow DAGs, sensors, operators | 52 |
| [gcp-pipeline-transform](gcp-pipeline-transform/) | dbt macros for audit columns | - |
| [gcp-pipeline-tester](gcp-pipeline-tester/) | Mocks, fixtures, base test classes | - |

---

## Dependency Rules

| Library | Can Import | Cannot Import |
|---------|------------|---------------|
| `gcp-pipeline-core` | Standard libs, GCP clients | beam, airflow |
| `gcp-pipeline-beam` | core, apache-beam | airflow |
| `gcp-pipeline-orchestration` | core, apache-airflow | beam |
| `gcp-pipeline-transform` | dbt | beam, airflow |

---

## Run Tests

```bash
# Core (208 tests)
cd gcp-pipeline-core
PYTHONPATH=src python -m pytest tests/unit/ -q

# Beam (358 tests)
cd ../gcp-pipeline-beam
PYTHONPATH=src:../gcp-pipeline-core/src python -m pytest tests/unit/ -q

# Orchestration (52 tests)
cd ../gcp-pipeline-orchestration
PYTHONPATH=src:../gcp-pipeline-core/src python -m pytest tests/unit/ -q
```

---

## Module Summary

### gcp-pipeline-core

| Module | Purpose |
|--------|---------|
| `audit/` | Lineage, reconciliation, audit trail |
| `monitoring/` | Metrics, OTEL/Dynatrace |
| `error_handling/` | Classification, retry, DLQ |
| `job_control/` | Pipeline status tracking |
| `clients/` | GCS, BigQuery, Pub/Sub wrappers |
| `utilities/` | Structured logging, run ID generation |

### gcp-pipeline-beam

| Module | Purpose |
|--------|---------|
| `pipelines/` | Base classes, transforms |
| `file_management/` | HDR/TRL parsing, archival |
| `validators/` | Schema, SSN, date validation |

### gcp-pipeline-orchestration

| Module | Purpose |
|--------|---------|
| `factories/` | DAG factories |
| `sensors/` | Pub/Sub Pull sensors |
| `operators/` | Custom operators |
| `callbacks/` | Error handlers |

