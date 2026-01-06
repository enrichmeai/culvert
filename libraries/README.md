# Libraries

4-library architecture for mainframe-to-GCP data migration.

---

## Architecture

```
                         LIBRARY ARCHITECTURE
                         ────────────────────

                    ┌─────────────────────────────┐
                    │      gcp-pipeline-core      │
                    │         (Foundation)        │
                    │                             │
                    │  • Audit & Reconciliation   │
                    │  • Monitoring & Metrics     │
                    │  • Error Handling           │
                    │  • Job Control              │
                    │  • Structured Logging       │
                    │                             │
                    │  NO beam, NO airflow        │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    │                    ▼
┌─────────────────────────┐        │        ┌─────────────────────────┐
│    gcp-pipeline-beam    │        │        │ gcp-pipeline-orchestr.  │
│      (Ingestion)        │        │        │      (Control)          │
│                         │        │        │                         │
│  • HDR/TRL Parser       │        │        │  • Pub/Sub Sensors      │
│  • Split File Handler   │        │        │  • DAG Factory          │
│  • Schema Validator     │        │        │  • Entity Dependency    │
│  • Beam Transforms      │        │        │  • Error Callbacks      │
│                         │        │        │                         │
│  beam, NO airflow       │        │        │  airflow, NO beam       │
└─────────────────────────┘        │        └─────────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │    gcp-pipeline-transform   │
                    │          (SQL)              │
                    │                             │
                    │  • dbt Audit Macros         │
                    │  • PII Masking              │
                    │  • SQL Templates            │
                    │                             │
                    │  dbt only                   │
                    └─────────────────────────────┘
```

---

## Libraries

| Library | Purpose | Tests | README |
|---------|---------|-------|--------|
| [gcp-pipeline-core](gcp-pipeline-core/) | Audit, monitoring, error handling, job control | 208 | ✅ |
| [gcp-pipeline-beam](gcp-pipeline-beam/) | Beam pipelines, transforms, file management | 358 | ✅ |
| [gcp-pipeline-orchestration](gcp-pipeline-orchestration/) | Airflow DAGs, sensors, operators | 52 | ✅ |
| [gcp-pipeline-transform](gcp-pipeline-transform/) | dbt macros for audit columns | - | ✅ |
| [gcp-pipeline-tester](gcp-pipeline-tester/) | Mocks, fixtures, base test classes | - | ✅ |

---

## Dependency Rules

```
                    CAN IMPORT              CANNOT IMPORT
                    ──────────              ─────────────

gcp-pipeline-core   Standard libs,          beam, airflow
                    GCP clients

gcp-pipeline-beam   core, apache-beam       airflow

gcp-pipeline-orch   core, apache-airflow    beam

gcp-pipeline-trans  dbt                     beam, airflow
```

---

## Key Features

### gcp-pipeline-core
- **Audit Trail**: Track every pipeline execution with `_run_id`
- **Reconciliation**: Compare source counts with target counts
- **Structured Logging**: JSON logs with context (run_id, system_id)
- **Metrics**: Cloud Monitoring, OTEL/Dynatrace integration
- **Error Handling**: Classification, retry, dead-letter queues

### gcp-pipeline-beam
- **HDR/TRL Parsing**: Validate mainframe file headers and trailers
- **Split File Handling**: Reassemble files split at 25MB threshold
- **Schema Validation**: Validate records against EntitySchema
- **Beam Transforms**: ParseCsvLine, ValidateRecordDoFn, AddAuditColumns

### gcp-pipeline-orchestration
- **Pub/Sub Sensor**: Event-driven detection of .ok files
- **Entity Dependency**: Wait for all entities before transformation (EM)
- **DAG Factory**: Generate DAGs from configuration
- **Error Callbacks**: DLQ publishing on failure

### gcp-pipeline-transform
- **Audit Macros**: `add_audit_columns()` for every FDP table
- **PII Masking**: `mask_ssn()`, `mask_dob()` for compliance
- **SQL Templates**: Staging and FDP model templates

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

## Total: 618 tests passing ✅

