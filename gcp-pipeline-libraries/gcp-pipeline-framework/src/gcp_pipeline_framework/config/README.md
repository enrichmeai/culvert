# GCP Pipeline Reference Implementation

A **reference implementation** of a mainframe-to-GCP data pipeline, demonstrating standardised "paved path" patterns for the enterprise the enterprise platform. It consolidates what were previously separate applications (Application A and Application B) into a single **Generic** reference system, proving two distinct pipeline patterns simultaneously using a shared 3-unit deployment model.

> **Last Updated:** March 2026 | **Version:** 1.0.10

---

## Quick Start

### Deploy via Push to Main

The primary deployment path is automated via GitHub Actions on push to `main`:

```bash
# 1. Set GCP project and authenticate
gcloud config set project YOUR_PROJECT_ID
gcloud auth login

# 2. Create all infrastructure (one-time per environment)
./scripts/gcp/01_enable_services.sh
./scripts/gcp/02_create_state_bucket.sh
./scripts/gcp/03_create_infrastructure.sh all

# 3. Add required GitHub secrets
gh secret set GCP_SA_KEY < /tmp/gcp-sa-key.json
gh secret set GCP_PROJECT_ID --body 'YOUR_PROJECT_ID'

# 4. Push to main — CI/CD deploys all three units automatically
git push origin main

# 5. Verify deployment
gh run list --workflow=deploy-generic.yml --limit 3

# 6. Run end-to-end test
./scripts/gcp/06_test_pipeline.sh generic
```

### Key Scripts

| Script | Purpose |
|--------|---------|
| `./scripts/gcp/01_enable_services.sh` | Enable required GCP APIs |
| `./scripts/gcp/02_create_state_bucket.sh` | Create Terraform state bucket |
| `./scripts/gcp/03_create_infrastructure.sh` | Create GCS, BigQuery, Pub/Sub resources |
| `./scripts/gcp/05_verify_setup.sh` | Verify infrastructure is ready |
| `./scripts/gcp/06_test_pipeline.sh` | Run end-to-end pipeline test |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CLOUD COMPOSER (Managed Airflow)                          │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  Airflow Scheduler + Webserver + Workers (Google-managed)              │  │
│  │  DAGs: Trigger → Validate → Load → Transform                          │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Orchestrates
                    ┌──────────────────┴──────────────────┐
                    ▼                                      ▼
┌───────────────────────────────┐  ┌───────────────────────────────┐
│         DATAFLOW              │  │         BIGQUERY              │
│   (Google Managed)            │  │    (Google Managed)           │
│  ┌─────────────────────────┐  │  │  ┌─────────────────────────┐  │
│  │  Beam Ingestion Jobs    │  │  │  │  dbt Transformations    │  │
│  │  GCS → ODP              │  │  │  │  ODP → FDP              │  │
│  └─────────────────────────┘  │  │  └─────────────────────────┘  │
└───────────────────────────────┘  └───────────────────────────────┘
```

---

## Why Use This Reference Implementation?

### 1. Standards-Based, Production-Ready Patterns

The framework abstracts enterprise-grade cross-cutting concerns into versioned, reusable libraries available on PyPI:

- **Audit Trail:** Centralised tracking via `gcp-pipeline-core`.
- **Ingestion Patterns:** Standardised Beam pipelines in `gcp-pipeline-beam`.
- **Orchestration:** Reusable Airflow operators and DAG factories in `gcp-pipeline-orchestration`.
- **Transformation Macros:** Shared dbt macros in `gcp-pipeline-transform`.
- **Testing Utilities:** Base classes and mocks in `gcp-pipeline-tester`.

Detailed information: [Technical Architecture Document](./docs/TECHNICAL_ARCHITECTURE.md).

### 2. Two Proven Patterns in One Reference System

The Generic system simultaneously demonstrates:

- **JOIN pattern** (from Application A): 3 source entities (Customers, Accounts, Decision) → 3 ODP tables → 2 FDP tables. All 3 entities must complete before transformation triggers.
- **MAP pattern** (from Application B): 1 source entity (Applications) → 1 ODP table → 1 FDP table. Transformation triggers immediately on ODP load.

### 3. Reliability and Visibility

- **Job Tracking:** Every run has a unique `run_id`, providing end-to-end lineage from source file to FDP row.
- **FinOps & Cost Visibility:** Built-in cost estimation for BigQuery, GCS, and Pub/Sub, with automated labelling for precise cost allocation.
- **Automatic Error Handling:** Exponential backoff at task level; failed files routed to error bucket with structured error report.
- **Structured Logs:** Standardised JSON logging searchable in Cloud Logging.

### Deployment Footprint

By consolidating Application A and Application B into three unified deployment units, the reference implementation reduces infrastructure overhead significantly:

| Unit | Entities Covered | Benefit |
|------|-----------------|---------|
| **Ingestion** (`original-data-to-bigqueryload`) | Customers, Accounts, Decision, Applications | Single Dataflow Flex Template image |
| **Transformation** (`bigquery-to-mapped-product`) | All FDP models | Unified dbt project |
| **Orchestration** (`data-pipeline-orchestrator`) | Full pipeline coordination | Single DAG set via Cloud Composer |

---

## Deployment Workflow

### Automatic Deployment (Recommended)

Push to `main` triggers `deploy-generic.yml` automatically for changes in:
- `deployments/original-data-to-bigqueryload/**` → Rebuilds and deploys Dataflow Flex Template
- `deployments/bigquery-to-mapped-product/**` → Deploys dbt models
- `deployments/data-pipeline-orchestrator/**` → Uploads DAGs to Cloud Composer
- `infrastructure/terraform/**` → Updates GCP infrastructure

### Manual Trigger

```bash
# Trigger full Generic deployment
gh workflow run deploy-generic.yml

# Check workflow status
gh run list --workflow=deploy-generic.yml --limit 3
```

### Library Publishing

```bash
# Publish libraries to PyPI AND trigger deployment
git commit -m "release: description [publish:deploy]"

# Publish libraries to PyPI only
git commit -m "chore: update version [publish:pypi]"
```

---

## Getting Started

### Local Environment Setup

```bash
# Set up the root venv for IDE resolution
./scripts/setup_ide_context.sh
source venv/bin/activate
```

- **PyCharm/IntelliJ:** Set project interpreter to `./venv`.
- **VS Code:** The Python extension will usually auto-detect `./venv`.

| Resource | Description |
| :--- | :--- |
| **[Creating New Deployment](./docs/CREATING_NEW_DEPLOYMENT_GUIDE.md)** | Step-by-step guide to adding a new system |
| **[GCP Deployment Guide](./docs/GCP_DEPLOYMENT_GUIDE.md)** | Infrastructure setup and CI/CD reference |
| **[Technical Architecture](./docs/TECHNICAL_ARCHITECTURE.md)** | Deep-dive into deployments, DAGs, and integration patterns |
| **[Production Release Guide](./docs/PRODUCTION_RELEASE_GUIDE.md)** | Senior developer handover and release checklist |

---

## Execution Guide

### 1. Local Environment Setup

Each deployment has its own isolated environment:

```bash
# Set up the ingestion deployment environment
./scripts/setup_deployment_venv.sh original-data-to-bigqueryload
source deployments/original-data-to-bigqueryload/venv/bin/activate
```

### 2. Running Tests

#### Library Tests

```bash
./scripts/run_library_tests.sh
```

#### Deployment Tests

```bash
cd deployments/original-data-to-bigqueryload
python -m pytest tests/unit/

cd deployments/bigquery-to-mapped-product
python -m pytest tests/unit/

cd deployments/data-pipeline-orchestrator
python -m pytest tests/unit/
```

### 3. Local Execution

#### Running Ingestion Locally

```bash
cd deployments/original-data-to-bigqueryload
python -m data_ingestion.pipeline.main \
    --source_file=path/to/local/file.csv \
    --output_table=project:dataset.table \
    --runner=DirectRunner \
    --temp_location=/tmp/beam-temp
```

#### Running Transformation Locally

```bash
cd deployments/bigquery-to-mapped-product/dbt
dbt run --profiles-dir . --target dev
```

### 4. Cloud Validation

```bash
# Simulate a file arrival for the generic ingestion pipeline
./scripts/gcp/06_test_pipeline.sh generic
```

This script:
1. Generates sample CSV data with valid HDR/TRL records.
2. Uploads data files to the landing bucket.
3. Uploads the `.ok` trigger file.
4. Publishes a message to the `generic-file-notifications` Pub/Sub topic.

---

## Architecture

### 5-Library Model (Published as `gcp-pipeline-framework`)

Libraries are consumed from PyPI (`pip install gcp-pipeline-framework>=1.0.10`) and are **not embedded** in this repository.

```
gcp-pipeline-core (Foundation — no Beam, no Airflow)
        ↓
   ┌────┴────┐
   ↓         ↓
gcp-pipeline-beam         gcp-pipeline-orchestration
(Ingestion — Beam)        (Control — Airflow)
        ↓                          ↓
gcp-pipeline-transform    gcp-pipeline-tester
(dbt macros)              (Test utilities)
```

| Library | Purpose | Tests |
|---------|---------|-------|
| [`gcp-pipeline-framework`](https://pypi.org/project/gcp-pipeline-framework/) | Umbrella package — installs all libraries below | - |
| `gcp-pipeline-core` | Audit, monitoring, FinOps, error handling, job control | 219 |
| `gcp-pipeline-beam` | Beam pipelines, transforms, HDR/TRL parsing, file management | 359 |
| `gcp-pipeline-orchestration` | Airflow DAGs, sensors, operators, DAG factory | 58 |
| `gcp-pipeline-transform` | dbt macros for audit columns and PII masking | - |
| `gcp-pipeline-tester` | Mocks, fixtures, base test classes | 101 |

### 3-Unit Deployment Model

| Unit | Deployment Folder | Covers |
| :--- | :--- | :--- |
| **Ingestion** | [`original-data-to-bigqueryload`](./deployments/original-data-to-bigqueryload/) | Dataflow Flex Template; reads HDR/TRL CSV files from GCS, loads to ODP |
| **Transformation** | [`bigquery-to-mapped-product`](./deployments/bigquery-to-mapped-product/) | dbt models transforming ODP to FDP |
| **Orchestration** | [`data-pipeline-orchestrator`](./deployments/data-pipeline-orchestrator/) | Airflow DAGs on Cloud Composer; Pub/Sub sensing, validation, coordination |

Specialised patterns maintained in separate deployments (not part of the active Generic CI/CD):
- **Spanner:** [`spanner-to-bigquery-load`](./deployments/spanner-to-bigquery-load/)
- **Mainframe Segment:** [`mainframe-segment-transform`](./deployments/mainframe-segment-transform/)

---

## End-to-End Flow

```
MAINFRAME           GCS LANDING         CLOUD COMPOSER       DATAFLOW            dbt
─────────           ───────────         ──────────────       ────────            ───

Extract     ───────►  .csv files   ──┐
CSV files             + .ok file     │ OBJECT_FINALIZE
(HDR/TRL)                            ▼ notification
                                ┌─────────────┐
                                │ Pub/Sub     │ generic-file-notifications
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
HDR|Generic|CUSTOMERS|20260101           ← Header: System, Entity, Date
customer_id,name,ssn,status              ← CSV column headers
1001,John Doe,123-45-6789,ACTIVE         ← Data rows
1002,Jane Smith,987-65-4321,ACTIVE
TRL|RecordCount=2|Checksum=a1b2c3d4      ← Trailer: Count, Checksum
```

### Split File Handling

Files > 25MB are split by the mainframe using the naming convention `customers_1.csv`, `customers_2.csv`. A single `.ok` file signals all splits are complete:

```
gs://{PROJECT_ID}-generic-{ENV}-landing/generic/customers/
├── customers_1.csv
├── customers_2.csv
└── customers.csv.ok    ← Triggers processing of ALL splits
```

---

## Reference Implementations

### JOIN Pattern (from Application A)

| Aspect | Value |
|--------|-------|
| Source Entities | 3 (Customers, Accounts, Decision) |
| ODP Tables | 3 (`odp_generic.customers`, `odp_generic.accounts`, `odp_generic.decision`) |
| FDP Tables | 2 (`fdp_generic.event_transaction_excess`, `fdp_generic.portfolio_account_excess`) |
| Dependency | All 3 JOIN entities must reach SUCCESS before FDP transformation triggers |

### MAP Pattern (from Application B)

| Aspect | Value |
|--------|-------|
| Source Entities | 1 (Applications) |
| ODP Tables | 1 (`odp_generic.applications`) |
| FDP Tables | 1 (`fdp_generic.portfolio_account_facility`) |
| Dependency | Transformation triggers immediately after ODP load |

### Spanner Transformation — FEDERATED Pattern

| Aspect | Value |
|--------|-------|
| Source System | Cloud Spanner |
| ODP Tables | 0 (bypassed) |
| FDP Tables | 1 (`spanner_customer_summary`) |
| Technology | dbt + `EXTERNAL_QUERY` |
| Pattern | Low-friction federated transformation |

---

## Project Structure

```
gcp-pipeline-libraries/                                    # Library source (published to PyPI)
├── gcp-pipeline-core/                                     # Foundation
├── gcp-pipeline-beam/                                     # Ingestion
├── gcp-pipeline-orchestration/                            # Control
├── gcp-pipeline-transform/                                # dbt macros
└── gcp-pipeline-tester/                                   # Testing utilities

deployments/
├── original-data-to-bigqueryload/                         # Generic Ingestion (Dataflow Flex Template)
├── bigquery-to-mapped-product/                            # Generic Transformation (dbt)
├── data-pipeline-orchestrator/                            # Generic Orchestration (Cloud Composer)
├── spanner-to-bigquery-load/                              # Spanner Federated (specialist)
└── mainframe-segment-transform/                           # Mainframe Segment (specialist)

infrastructure/terraform/
└── systems/generic/
    ├── ingestion/                                         # GCS, Pub/Sub, BQ ODP
    ├── transformation/                                    # BigQuery FDP
    └── orchestration/                                     # Service accounts, IAM, Composer
```

---

## Run All Tests

```bash
# Library tests (737 tests)
cd gcp-pipeline-libraries/gcp-pipeline-core && PYTHONPATH=src python -m pytest tests/unit/ -q
cd ../gcp-pipeline-beam && PYTHONPATH=src:../gcp-pipeline-core/src python -m pytest tests/unit/ -q
cd ../gcp-pipeline-orchestration && PYTHONPATH=src:../gcp-pipeline-core/src python -m pytest tests/unit/ -q
cd ../gcp-pipeline-tester && PYTHONPATH=src python -m pytest tests/unit/ -q

# Deployment tests
cd ../../deployments/original-data-to-bigqueryload && python -m pytest tests/unit/ -q
cd ../bigquery-to-mapped-product && python -m pytest tests/unit/ -q
cd ../data-pipeline-orchestrator && python -m pytest tests/unit/ -q
```

---

## Test Summary

| Component | Tests |
|-----------|-------|
| gcp-pipeline-core | 219 |
| gcp-pipeline-beam | 359 |
| gcp-pipeline-orchestration | 58 |
| gcp-pipeline-tester | 101 |
| original-data-to-bigqueryload | 26 |
| **Total** | **763** |

---

## Key Concepts

| Term | Definition |
|------|------------|
| **ODP** | Original Data Product — raw 1:1 copy of mainframe data in BigQuery |
| **FDP** | Foundation Data Product — transformed, business-ready data |
| **HDR/TRL** | Header/Trailer records for file envelope validation |
| **.ok file** | Signal file indicating all data file transfers are complete |
| **Split Files** | Files > 25MB split by the mainframe; a single `.ok` covers all splits |
| **JOIN pattern** | Multi-entity pipeline requiring all entities to load before FDP transform |
| **MAP pattern** | Single-entity pipeline with immediate FDP trigger |
| **run_id** | Unique correlation ID propagated across all layers for end-to-end lineage |

---

## Documentation

| Guide | Description |
|-------|-------------|
| [E2E Functional Flow](./docs/E2E_FUNCTIONAL_FLOW.md) | Complete end-to-end requirements and data flow |
| [Technical Architecture](./docs/TECHNICAL_ARCHITECTURE.md) | Technical deep-dive into deployments, DAGs, and integration patterns |
| [paved path Proposal](./docs/PAVED_PATH_PROPOSAL.md) | Enterprise paved path proposal for the the enterprise platform |
| [GCP Deployment Guide](./docs/GCP_DEPLOYMENT_GUIDE.md) | Terraform and deployment guide |
| [Production Release Guide](./docs/PRODUCTION_RELEASE_GUIDE.md) | Senior developer handover and release checklist |
| [GKE Deployment Guide](./docs/GKE_DEPLOYMENT_GUIDE.md) | Alternative: self-hosted Airflow on GKE |
| [Audit Integration](./docs/AUDIT_INTEGRATION_GUIDE.md) | Audit trail and reconciliation |
| [Pub/Sub & KMS](./docs/PUBSUB_KMS_GUIDE.md) | Event-driven triggers with encryption |
| [Error Handling](./docs/ERROR_HANDLING_GUIDE.md) | Error classification, retry, DLQ |
| [Data Quality](./docs/DATA_QUALITY_GUIDE.md) | Validation and quality scoring |
| [Creating New Deployment](./docs/CREATING_NEW_DEPLOYMENT_GUIDE.md) | How to add a new system migration |
| [Standard Migration Tasks](./docs/STANDARD_MIGRATION_TASKS.md) | Ticket templates for new systems |

---

## Technology Stack

| Layer | Technology | Documentation |
|-------|------------|---------------|
| **Storage** | [Google Cloud Storage (GCS)](https://cloud.google.com/storage) | [GCS Docs](https://cloud.google.com/storage/docs) |
| **Messaging** | [Cloud Pub/Sub](https://cloud.google.com/pubsub) | [Pub/Sub Docs](https://cloud.google.com/pubsub/docs) |
| **Security** | [Cloud KMS](https://cloud.google.com/kms) | [KMS Docs](https://cloud.google.com/kms/docs) |
| **Processing** | [Apache Beam](https://beam.apache.org/) on [Cloud Dataflow](https://cloud.google.com/dataflow) | [Beam Docs](https://beam.apache.org/documentation/) |
| **Orchestration** | [Apache Airflow](https://airflow.apache.org/) on [Cloud Composer](https://cloud.google.com/composer) | [Composer Docs](https://cloud.google.com/composer/docs) |
| **Transformation** | [dbt (Data Build Tool)](https://www.getdbt.com/) | [dbt Docs](https://docs.getdbt.com/docs/introduction) |
| **Data Warehouse** | [BigQuery](https://cloud.google.com/bigquery) | [BigQuery Docs](https://cloud.google.com/bigquery/docs) |
| **Monitoring** | [Cloud Monitoring](https://cloud.google.com/monitoring) | [Operations Suite Docs](https://cloud.google.com/stackdriver/docs) |
| **Infrastructure** | [Terraform](https://www.terraform.io/) | [Terraform GCP Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs) |
