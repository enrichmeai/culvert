# Legacy Mainframe to GCP Data Migration Framework

A **library-first framework** for migrating legacy mainframe batch systems to Google Cloud Platform. Shared libraries provide reusable patterns; deployments configure them per system.

---

## Architecture

### 4-Library Model

```
gcp-pipeline-core (Foundation - NO beam, NO airflow)
        ↓
   ┌────┴────┐
   ↓         ↓
gcp-pipeline-beam         gcp-pipeline-orchestration
(Ingestion - beam)        (Control - airflow)
```

| Library | Purpose | Tests |
|---------|---------|-------|
| `gcp-pipeline-core` | Audit, monitoring, error handling, job control | 208 |
| `gcp-pipeline-beam` | Beam pipelines, transforms, file management | 358 |
| `gcp-pipeline-orchestration` | Airflow DAGs, sensors, operators | 52 |
| `gcp-pipeline-transform` | dbt macros for audit columns, PII masking | - |
| `gcp-pipeline-tester` | Mocks, fixtures, base test classes | - |

### 3-Unit Deployment Model

Each system is split into 3 independent units:

| Unit | Purpose | Dependencies |
|------|---------|--------------|
| `*-ingestion` | Beam pipeline (GCS → ODP) | core, beam (NO airflow) |
| `*-transformation` | dbt models (ODP → FDP) | transform |
| `*-orchestration` | Airflow DAGs | core, orchestration (NO beam) |

---

## Project Structure

```
libraries/
├── gcp-pipeline-core/           # 208 tests
├── gcp-pipeline-beam/           # 358 tests  
├── gcp-pipeline-orchestration/  # 52 tests
├── gcp-pipeline-transform/      # dbt macros
└── gcp-pipeline-tester/         # Testing utilities

deployments/
├── em-ingestion/                # 44 tests (JOIN: 3→1)
├── em-transformation/           # dbt
├── em-orchestration/            # DAGs
├── loa-ingestion/               # 36 tests (SPLIT: 1→2)
├── loa-transformation/          # dbt
└── loa-orchestration/           # DAGs
```

---

## 🚀 The Minimalist Advantage

### Why 3 Independent Deployments?
1.  **Decoupled Scaling**: Scale Dataflow (Ingestion) for high-volume bursts without over-provisioning Airflow (Orchestration).
2.  **Failure Isolation**: A dbt syntax error (Transformation) won't stop the file from being safely landed and audited in ODP (Ingestion).
3.  **Clean Dependencies**: Airflow stays "light" (no Beam/Java dependencies), reducing environment conflicts and start-up times.
4.  **Polyglot Fit**: Use the best tool for the job—Python/Beam for complex parsing, SQL/dbt for business logic.
5.  **Simpler E2E Testing**: Each unit (Ingestion, Transformation, Orchestration) can be tested in isolation with mocked inputs, significantly shortening feedback loops and simplifying CI/CD.

### Resiliency Patterns
*   **Integrity (Reconciliation)**: Automated TRL record count vs. BigQuery row count verification.
*   **Recoverability (Idempotency)**: Every run is uniquely identified (`run_id`), allowing safe re-execution and data overwrites.
*   **Observability (Audit Trail)**: Single correlation ID links GCS files, Beam logs, and dbt transformations.
*   **Durability (DLQ)**: Invalid records are isolated to side-tables, preserving the pipeline's "Green" status for valid data.
*   **Security (Metadata-Masking)**: PII masking is defined in the schema and enforced during both Ingestion and Transformation.

---

### EM (Application A) - JOIN Pattern

- **Source**: 3 entities (Customers, Accounts, Decision)
- **ODP**: 3 tables
- **FDP**: 1 table (`em_attributes`)
- **Dependency**: Wait for all 3 entities before FDP transformation

### LOA (Application B) - SPLIT Pattern

- **Source**: 1 entity (Applications)
- **ODP**: 1 table
- **FDP**: 2 tables (`event_transaction_excess`, `portfolio_account_excess`)
- **Dependency**: Immediate trigger after ODP load

---

## Key Concepts

| Term | Definition |
|------|------------|
| **ODP** | Original Data Product - Raw 1:1 copy of mainframe data |
| **FDP** | Foundation Data Product - Transformed, business-ready |
| **HDR/TRL** | Header/Trailer records for file validation |
| **.ok file** | Signal file indicating transfer complete |

---

## Library Features

| Feature | Module |
|---------|--------|
| HDR/TRL Parsing | `gcp-pipeline-beam.file_management` |
| Schema Validation | `gcp-pipeline-beam.validators` |
| Audit Trail | `gcp-pipeline-core.audit` |
| Reconciliation | `gcp-pipeline-core.audit.reconciliation` |
| Structured Logging | `gcp-pipeline-core.utilities` |
| Metrics & OTEL | `gcp-pipeline-core.monitoring` |
| Error Handling | `gcp-pipeline-core.error_handling` |
| Job Control | `gcp-pipeline-core.job_control` |
| DAG Factory | `gcp-pipeline-orchestration.factories` |
| Pub/Sub Sensor | `gcp-pipeline-orchestration.sensors` |

---

## Quick Start

### Run Library Tests

```bash
cd libraries/gcp-pipeline-core
PYTHONPATH=src python -m pytest tests/unit/ -q

cd ../gcp-pipeline-beam
PYTHONPATH=src:../gcp-pipeline-core/src python -m pytest tests/unit/ -q

cd ../gcp-pipeline-orchestration
PYTHONPATH=src:../gcp-pipeline-core/src python -m pytest tests/unit/ -q
```

### Run Deployment Tests

```bash
cd deployments/loa-ingestion
PYTHONPATH=src:../../libraries/gcp-pipeline-core/src:../../libraries/gcp-pipeline-beam/src \
  python -m pytest tests/unit/ -q

cd ../em-ingestion
PYTHONPATH=src:../../libraries/gcp-pipeline-core/src:../../libraries/gcp-pipeline-beam/src \
  python -m pytest tests/unit/ -q
```

---

## Test Summary

| Component | Tests |
|-----------|-------|
| gcp-pipeline-core | 208 |
| gcp-pipeline-beam | 358 |
| gcp-pipeline-orchestration | 52 |
| loa-ingestion | 36 |
| em-ingestion | 44 |
| **Total** | **698** |

---

## Documentation

| Guide | Description |
|-------|-------------|
| [E2E Flow](docs/E2E_FUNCTIONAL_FLOW.md) | End-to-end functional flow |
| [Audit Integration](docs/AUDIT_INTEGRATION_GUIDE.md) | Audit trail implementation |
| [Pub/Sub & KMS](docs/PUBSUB_KMS_GUIDE.md) | Event-driven triggers |
| [Error Handling](docs/ERROR_HANDLING_GUIDE.md) | Error classification and DLQ |
| [Data Quality](docs/DATA_QUALITY_GUIDE.md) | Validation and quality scoring |
| [GCP Deployment](docs/GCP_DEPLOYMENT_GUIDE.md) | Terraform and deployment |

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Storage | GCS |
| Messaging | Pub/Sub with KMS |
| Processing | Apache Beam on Dataflow |
| Orchestration | Apache Airflow (Cloud Composer) |
| Transformation | dbt |
| Data Warehouse | BigQuery |
| Infrastructure | Terraform |

