# Legacy Mainframe to GCP Data Migration Framework

A **library-first framework** for migrating legacy mainframe batch systems to Google Cloud Platform. Shared libraries provide reusable patterns; deployments configure them per system.

---

## Why This Framework?

### Reusable Patterns

| Pattern | Description | Library |
|---------|-------------|---------|
| **File Validation** | HDR/TRL parsing, checksum verification, record count reconciliation | `gcp-pipeline-beam` |
| **Split File Handling** | Reassemble files split at 25MB threshold | `gcp-pipeline-beam` |
| **Schema Validation** | Automatic validation against entity schemas | `gcp-pipeline-beam` |
| **Data Quality** | Row type, data type, duplicate detection | `gcp-pipeline-beam` |
| **Audit Trail** | Run tracking, lineage, source-to-target reconciliation | `gcp-pipeline-core` |
| **Structured Logging** | JSON logging with run_id, system_id context | `gcp-pipeline-core` |
| **Metrics & OTEL** | Cloud Monitoring, Dynatrace integration | `gcp-pipeline-core` |
| **Error Handling** | Classification, retry logic, dead-letter queues | `gcp-pipeline-core` |
| **Job Control** | Pipeline status tracking and metadata | `gcp-pipeline-core` |
| **DAG Factory** | Standardized Airflow DAG generation | `gcp-pipeline-orchestration` |
| **Pub/Sub Sensor** | Event-driven file detection with .ok triggers | `gcp-pipeline-orchestration` |
| **Entity Dependency** | Wait for all entities before transformation | `gcp-pipeline-orchestration` |

### Cloud Cost Benefits

The **3-Unit Deployment Model** reduces cloud costs:

| Benefit | Description |
|---------|-------------|
| **Smaller Airflow Environment** | Orchestration unit has NO Apache Beam dependency → faster builds, less memory |
| **Smaller Dataflow Images** | Ingestion unit has NO Airflow dependency → smaller container images |
| **Independent Scaling** | Scale ingestion workers without affecting orchestration |
| **Faster Deployments** | Smaller units = faster CI/CD pipelines |

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
| `*-transformation` | dbt models (ODP → FDP) | transform (dbt only) |
| `*-orchestration` | Airflow DAGs | core, orchestration (NO beam) |

---

## End-to-End Flow

```
MAINFRAME           GCS LANDING         AIRFLOW              DATAFLOW            dbt
─────────           ───────────         ───────              ────────            ───

Extract     ───────►  .csv files   ──┐
CSV files             + .ok file     │
(HDR/TRL)                            ▼
                                ┌─────────────┐
                                │ Pub/Sub     │
                                │ Sensor      │
                                └──────┬──────┘
                                       │
                                       ▼
                                ┌─────────────┐
                                │ Validate    │
                                │ HDR/TRL     │
                                │ DQ Checks   │
                                └──────┬──────┘
                                       │
                                       ▼
                                ┌─────────────┐     ┌─────────────┐
                                │ Trigger     │────►│ Beam        │────► ODP Tables
                                │ Dataflow    │     │ Pipeline    │      (BigQuery)
                                └─────────────┘     └─────────────┘
                                       │
                                       ▼
                                ┌─────────────┐     ┌─────────────┐
                                │ Trigger     │────►│ dbt run     │────► FDP Tables
                                │ dbt         │     │ Transform   │      (BigQuery)
                                └─────────────┘     └─────────────┘
```

### File Format

```
HDR|EM|CUSTOMERS|20260101           ← Header: System, Entity, Date
customer_id,name,ssn,status         ← CSV headers
1001,John Doe,123-45-6789,ACTIVE    ← Data rows
1002,Jane Smith,987-65-4321,ACTIVE
TRL|RecordCount=2|Checksum=a1b2c3d4 ← Trailer: Count, Checksum
```

### Split File Handling

Files > 25MB are split by mainframe with naming: `customers_1.csv`, `customers_2.csv`

Single `.ok` file signals all splits are complete:
```
gs://landing/em/customers/
├── customers_1.csv
├── customers_2.csv
└── customers.csv.ok    ← Triggers processing of ALL splits
```

---

## Reference Implementations

### EM (Application A) - JOIN Pattern

| Aspect | Value |
|--------|-------|
| Source Entities | 3 (Customers, Accounts, Decision) |
| ODP Tables | 3 |
| FDP Tables | 1 (`em_attributes`) |
| Dependency | Wait for all 3 entities before FDP transformation |

### LOA (Application B) - SPLIT Pattern

| Aspect | Value |
|--------|-------|
| Source Entities | 1 (Applications) |
| ODP Tables | 1 |
| FDP Tables | 2 (`event_transaction_excess`, `portfolio_account_excess`) |
| Dependency | Immediate trigger after ODP load |

---

## Project Structure

```
libraries/
├── gcp-pipeline-core/           # 208 tests - Foundation
├── gcp-pipeline-beam/           # 358 tests - Ingestion
├── gcp-pipeline-orchestration/  # 52 tests - Control
├── gcp-pipeline-transform/      # dbt macros
└── gcp-pipeline-tester/         # Testing utilities

deployments/
├── em-ingestion/                # 44 tests (JOIN: 3→1)
├── em-transformation/           # dbt models
├── em-orchestration/            # Airflow DAGs
├── loa-ingestion/               # 36 tests (SPLIT: 1→2)
├── loa-transformation/          # dbt models
└── loa-orchestration/           # Airflow DAGs

infrastructure/terraform/
├── systems/em/                  # EM infrastructure
│   ├── ingestion/               # GCS, Pub/Sub
│   ├── transformation/          # BigQuery datasets
│   └── orchestration/           # Service accounts, IAM
└── systems/loa/                 # LOA infrastructure
    ├── ingestion/
    ├── transformation/
    └── orchestration/
```

---

## Key Concepts

| Term | Definition |
|------|------------|
| **ODP** | Original Data Product - Raw 1:1 copy of mainframe data |
| **FDP** | Foundation Data Product - Transformed, business-ready |
| **HDR/TRL** | Header/Trailer records for file validation |
| **.ok file** | Signal file indicating transfer complete |
| **Split Files** | Large files (>25MB) split by mainframe |

---

## Quick Start

### Run All Tests

```bash
# Libraries (618 tests)
cd libraries/gcp-pipeline-core && PYTHONPATH=src python -m pytest tests/unit/ -q
cd ../gcp-pipeline-beam && PYTHONPATH=src:../gcp-pipeline-core/src python -m pytest tests/unit/ -q
cd ../gcp-pipeline-orchestration && PYTHONPATH=src:../gcp-pipeline-core/src python -m pytest tests/unit/ -q

# Deployments (80 tests)
cd ../../deployments/loa-ingestion && \
  PYTHONPATH=src:../../libraries/gcp-pipeline-core/src:../../libraries/gcp-pipeline-beam/src \
  python -m pytest tests/unit/ -q

cd ../em-ingestion && \
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
| [E2E Functional Flow](docs/E2E_FUNCTIONAL_FLOW.md) | Complete end-to-end requirements and data flow |
| [Audit Integration](docs/AUDIT_INTEGRATION_GUIDE.md) | Audit trail and reconciliation |
| [Pub/Sub & KMS](docs/PUBSUB_KMS_GUIDE.md) | Event-driven triggers with encryption |
| [Error Handling](docs/ERROR_HANDLING_GUIDE.md) | Error classification, retry, DLQ |
| [Data Quality](docs/DATA_QUALITY_GUIDE.md) | Validation and quality scoring |
| [GCP Deployment](docs/GCP_DEPLOYMENT_GUIDE.md) | Terraform and deployment guide |

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Storage | GCS |
| Messaging | Pub/Sub with KMS encryption |
| Processing | Apache Beam on Dataflow |
| Orchestration | Apache Airflow (Cloud Composer) |
| Transformation | dbt |
| Data Warehouse | BigQuery |
| Monitoring | Cloud Monitoring, OTEL, Dynatrace |
| Infrastructure | Terraform |

