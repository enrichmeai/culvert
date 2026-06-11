# GCP Pipeline Reference Implementation

> The simplest production-ready GCP data pipeline framework. Composer + BigQuery + Beam + dbt, opinionated and ready to ship.

A **reference implementation** of a mainframe-to-GCP data pipeline, demonstrating standardised "Golden Path" patterns for the enterprise Credit Platform. It consolidates what were previously separate applications (Excess Management and Loan Origination) into a single **Generic** reference system, proving two distinct pipeline patterns simultaneously using a shared 3-unit deployment model.

> **Last Updated:** March 2026 | **Version:** 1.0.29 (libraries), 1.0.14 (reference packages)

---

## Quickstart

New here? Start with **[QUICKSTART.md](./QUICKSTART.md)**. It walks through the standard Composer-based deployment end-to-end in under 30 minutes. Everything you need is there. Come back to this README for the broader reference once you are up and running.

---

## Standard deployment (Composer optional)

The standard path runs three independently deployed units — ingestion, transformation, and orchestration. Cloud Composer is optional; the framework's default does not provision it. Adopt Composer only if you need Apache Airflow's full feature set; otherwise the orchestration unit runs as Cloud Functions + Cloud Run Jobs at a fraction of the cost. Terraform provisions all infrastructure; GitHub Actions deploys on push to `main`.

### One-time infrastructure setup

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
```

### Deploy

```bash
# Push to main — CI/CD deploys all three units automatically
git push origin main

# Verify deployment
gh run list --workflow=deploy-generic.yml --limit 3

# Run end-to-end test
./scripts/gcp/06_test_pipeline.sh generic
```

Changes in each deployment unit are detected automatically:

- `deployments/original-data-to-bigqueryload/**` → rebuilds and deploys the Dataflow Flex Template
- `deployments/bigquery-to-mapped-product/**` → deploys dbt models to BigQuery
- `deployments/data-pipeline-orchestrator/**` → uploads DAGs to Cloud Composer
- `infrastructure/terraform/**` → applies Terraform changes

### Key scripts

| Script | Purpose |
|--------|---------|
| `./scripts/gcp/01_enable_services.sh` | Enable required GCP APIs |
| `./scripts/gcp/02_create_state_bucket.sh` | Create Terraform state bucket |
| `./scripts/gcp/03_create_infrastructure.sh` | Create GCS, BigQuery, Pub/Sub resources |
| `./scripts/gcp/05_verify_setup.sh` | Verify infrastructure is ready |
| `./scripts/gcp/06_test_pipeline.sh` | Run single-entity pipeline test |
| `./scripts/gcp/e2e_pipeline_test.sh` | Full E2E test (all entities, ODP + FDP verification) |

### Manual trigger

```bash
# Trigger full Generic deployment manually
gh workflow run deploy-generic.yml

# Check workflow status
gh run list --workflow=deploy-generic.yml --limit 3
```

### Library publishing

```bash
# Publish libraries to PyPI AND deploy in one step (canonical trigger per CLAUDE.md)
git commit -m "chore: update version [publish:deploy]"
git push

# Alternatively, publish libraries to PyPI only (no deploy), then deploy separately
git commit -m "chore: update version [publish:pypi]"
gh workflow run deploy-generic.yml
```

> **Note:** The canonical CI trigger for publishing libraries then deploying is `[publish:deploy]` (see CLAUDE.md). Use `[publish:pypi]` only when you want to publish libraries to PyPI without triggering a deployment.

---

## CI (GitHub Actions)

### Workflow: `.github/workflows/ci.yml`

Introduced in T15.1 (#77). Triggers on `push` and `pull_request` to `sprint-15` and `main`.

#### Jobs

| Job | What it does |
|-----|-------------|
| `verify-module-list` | Diffs the workflow's explicit module list against `data-pipeline-libraries-java/pom.xml`. Fails if a module is missing — a gap is a visible red, not a silent pass. |
| `java-build` | Matrix over all 13 Java reactor modules. Sets up JDK 21 (Temurin), caches `~/.m2`, runs `mvn --batch-mode -pl <module> -am test`. Integration tests (`*IT.java`) are excluded by surefire default; those come in T15.2. |
| `python-tests` | Matrix over the three GCP adapter modules (`data-pipeline-gcp-bigquery`, `data-pipeline-gcp-gcs`, `data-pipeline-gcp-pubsub`). Installs `data-pipeline-core` from local source first (it is not on PyPI yet), then the adapter. Caches pip. |
| `ci-gate` | Required-status-check entry point. Fails if either `java-build` or `python-tests` fail. |

#### Java reactor modules (all 13 enumerated)

```
data-pipeline-core-java
data-pipeline-gcp-secrets-java
data-pipeline-gcp-bigquery-java
data-pipeline-gcp-gcs-java
data-pipeline-gcp-pubsub-java
data-pipeline-gcp-observability-java
data-pipeline-gcp-dataflow-java
data-pipeline-tester-java
data-pipeline-it-support-java
data-pipeline-contract-tests-java
data-pipeline-aws-s3-java
data-pipeline-azure-blob-java
data-pipeline-orchestration-java
```

#### Adding a new Java module

1. Add the module directory under `data-pipeline-libraries-java/`.
2. Add a `<module>` entry to `data-pipeline-libraries-java/pom.xml`.
3. Add the module name to the `matrix.module` list in `.github/workflows/ci.yml`.
   The `verify-module-list` job will fail on the next CI run if you forget step 3.

#### Known exclusions

- `data-pipeline-orchestration` (Python) is excluded from CI pending tech-debt #88: `tests/unit/test_create_dags.py` references `airflow.providers.standard.operators.empty`, an Airflow-3.x-only import path that does not exist under the pinned Airflow 2.9.x. The file already carries a module-level `pytest.skip()` guard but the module is still unreliable to collect on a clean runner. Fix tracked in #88.
- Emulator / Testcontainers integration tests — tracked in T15.2.
- E2E / cloud-credential steps — tracked in T15.3.

#### Re-enabling CI

The workflow file is committed but the workflow is **disabled at the GitHub level** (intentional since Sprint 0 to avoid billable Actions minutes during development sprints). To enable:

```bash
gh workflow enable ci.yml
```

This is an **engineer trigger** — do not enable from an agent session.

---

## Alternative deployments (advanced)

These escape hatches exist for teams with specific constraints. They are not the default path.

- **Self-managed Airflow on GKE (Helm)** — for teams that cannot use Composer due to regulatory, hybrid-estate, or extreme-scale requirements. See [GKE Deployment Guide](./docs/GKE_DEPLOYMENT_GUIDE.md) and Chapter 14 of the book.
- **Cloud Run / Workflows** — for teams running lightweight, event-driven workloads without a standing orchestrator. Not covered inline here; raise it as a discussion if you think you need it.

If you are not sure which path applies, use Composer. The operational overhead of self-managing Kubernetes or Workflows is significant; Composer pays for itself quickly.

---

## Install from PyPI and Reconstruct the Project

All libraries, reference implementations, documentation, infrastructure-as-code, and CI/CD workflows are published to PyPI. You can reconstruct the entire project from packages — no access to the source repo required.

### Option 1: Quick Reconstruction with `reconstruct.py`

Download [`reconstruct.py`](./reconstruct.py) and run it — it creates a temp venv, installs everything from PyPI, and exports the full project layout:

```bash
# From public PyPI (latest version)
python reconstruct.py

# Specific version
python reconstruct.py --version 1.0.29

# From a private index (Nexus, Artifactory, etc.)
python reconstruct.py --index-url https://nexus.internal/repository/pypi/simple/

# Custom destination
python reconstruct.py --dest /path/to/my-pipeline-project
```

This produces a ready-to-use project directory:
```
culvert/
├── docs/                      # 34 documentation guides
├── infrastructure/
│   ├── terraform/             # All Terraform modules and tfvars
│   └── k8s/                   # Helm charts for alternative self-managed deployment (advanced)
├── .github/workflows/         # 11 CI/CD workflow definitions
├── deployments/               # Dockerfiles, cloudbuild.yaml, pyproject.toml per deployment
│   ├── original-data-to-bigqueryload/
│   ├── bigquery-to-mapped-product/
│   ├── data-pipeline-orchestrator/
│   └── ...
├── gcp-pipeline-libraries/    # Full library source code
├── .gitignore, pyproject.toml, README.md
```

Push it to your internal repo:
```bash
cd culvert
git init && git add -A && git commit -m "Import GCP Pipeline Reference from PyPI"
git remote add origin <your-internal-repo-url>
git push -u origin main
```

### Option 2: CLI Export (docs + infrastructure only)

If you already have `gcp-pipeline-framework` installed:

```bash
pip install gcp-pipeline-framework

# List all bundled docs
gcp-pipeline-docs list

# View a specific guide
gcp-pipeline-docs show DEVELOPER_TESTING_GUIDE.md

# Export just the docs
gcp-pipeline-docs export-docs --dest docs

# Export the full project structure (docs + infra + workflows + deployment configs)
gcp-pipeline-docs export-project --dest my-project
```

### Option 3: Python API

```python
from gcp_pipeline_framework import list_docs, get_docs_path, export_project

# List all documentation
for doc in list_docs():
    print(doc)

# Read a specific guide
content = (get_docs_path() / "DEVELOPER_TESTING_GUIDE.md").read_text()

# Export everything to a directory
export_project("my-project")
```

### What's Published to PyPI

| Package | Contents |
|---------|----------|
| `gcp-pipeline-framework` | Umbrella + all docs, Terraform, Helm charts, workflows, deployment configs |
| `gcp-pipeline-core` | Foundation library (audit, monitoring, error handling, job control) |
| `gcp-pipeline-beam` | Apache Beam ingestion library |
| `gcp-pipeline-orchestration` | Airflow operators and DAG utilities |
| `gcp-pipeline-transform` | Shared dbt macros |
| `gcp-pipeline-tester` | Test mocks, fixtures, base classes |
| `gcp-pipeline-ref-ingestion` | Reference: GCS → BigQuery ODP ingestion source |
| `gcp-pipeline-ref-transform` | Reference: ODP → FDP dbt models |
| `gcp-pipeline-ref-orchestration` | Reference: Airflow DAGs for Cloud Composer |
| `gcp-pipeline-ref-cdp` | Reference: FDP → CDP dbt models |
| `gcp-pipeline-ref-segment-transform` | Reference: CDP → mainframe segment files |

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

- **JOIN pattern** (from Excess Management): 3 source entities (Customers, Accounts, Decision) → 3 ODP tables → 2 FDP tables. All 3 entities must complete before transformation triggers.
- **MAP pattern** (from Loan Origination): 1 source entity (Applications) → 1 ODP table → 1 FDP table. Transformation triggers immediately on ODP load.

### 3. Reliability and Visibility

- **Job Tracking:** Every run has a unique `run_id`, providing end-to-end lineage from source file to FDP row.
- **FinOps & Cost Visibility:** Built-in cost estimation for BigQuery, GCS, and Pub/Sub, with automated labelling for precise cost allocation.
- **Automatic Error Handling:** Exponential backoff at task level; failed files routed to error bucket with structured error report.
- **Structured Logs:** Standardised JSON logging searchable in Cloud Logging.

### Deployment Footprint

By consolidating Excess Management and Loan Origination into three unified deployment units, the reference implementation reduces infrastructure overhead significantly:

| Unit | Entities Covered | Benefit |
|------|-----------------|---------|
| **Ingestion** (`original-data-to-bigqueryload`) | Customers, Accounts, Decision, Applications | Single Dataflow Flex Template image |
| **Transformation** (`bigquery-to-mapped-product`) | All FDP models | Unified dbt project |
| **Orchestration** (`data-pipeline-orchestrator`) | Full pipeline coordination | Single DAG set via Cloud Composer |

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
python -m data_ingestion.pipeline.runner \
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

Pipeline events (status, errors) are published to the `generic-pipeline-events` Pub/Sub topic.

---

## Architecture

### Library Stack (6 packages) (Published as `gcp-pipeline-framework`)

Libraries are consumed from PyPI (`pip install gcp-pipeline-framework>=1.0.29`) and are **not embedded** in this repository.

```
gcp-pipeline-core (Foundation — no Beam, no Airflow)
        |
   ┌────┼────────────┐
   ↓    ↓            ↓
gcp-pipeline-beam    gcp-pipeline-orchestration    gcp-pipeline-transform
(Ingestion — Beam)   (Control — Airflow)           (SQL — dbt macros)
```

Supplementary packages:
- `gcp-pipeline-tester` — Testing utilities (mocks, fixtures, base classes)
- `gcp-pipeline-framework` — Umbrella package that installs all libraries

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
- **CDP:** [`fdp-to-consumable-product`](./deployments/fdp-to-consumable-product/) (code-complete)
- **Mainframe Segment:** [`mainframe-segment-transform`](./deployments/mainframe-segment-transform/) (code-complete)
- **Spanner:** [`spanner-to-bigquery-load`](./deployments/spanner-to-bigquery-load/) (reference)
- **Postgres CDC:** [`postgres-cdc-streaming`](./deployments/postgres-cdc-streaming/) (reference)

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

### JOIN Pattern (from Excess Management)

| Aspect | Value |
|--------|-------|
| Source Entities | 3 (Customers, Accounts, Decision) |
| ODP Tables | 3 (`odp_generic.customers`, `odp_generic.accounts`, `odp_generic.decision`) |
| FDP Tables | 2 (`fdp_generic.event_transaction_excess`, `fdp_generic.portfolio_account_excess`) |
| Dependency | All 3 JOIN entities must reach SUCCESS before FDP transformation triggers |

### MAP Pattern (from Loan Origination)

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
├── gcp-pipeline-tester/                                   # Testing utilities
└── gcp-pipeline-framework/                                # Umbrella package

deployments/
├── original-data-to-bigqueryload/                         # Generic Ingestion (Dataflow Flex Template)
├── bigquery-to-mapped-product/                            # Generic Transformation (dbt)
├── data-pipeline-orchestrator/                            # Generic Orchestration (Cloud Composer)
├── fdp-to-consumable-product/                             # CDP Transformation (dbt, code-complete)
├── mainframe-segment-transform/                           # Mainframe Segment (Beam, code-complete)
├── postgres-cdc-streaming/                                # Postgres CDC (Beam streaming, reference)
├── spanner-to-bigquery-load/                              # Spanner Federated (dbt, reference)

infrastructure/terraform/
└── systems/generic/
    ├── ingestion/                                         # GCS, Pub/Sub, BQ ODP
    ├── transformation/                                    # BigQuery FDP
    └── orchestration/                                     # Service accounts, IAM, Composer
```

---

## Run All Tests

```bash
# Library tests (763 tests)
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
| [Golden Path Proposal](./docs/GOLDEN_PATH_PROPOSAL.md) | Enterprise Golden Path proposal for the Credit Platform |
| [GCP Deployment Guide](./docs/GCP_DEPLOYMENT_GUIDE.md) | Terraform and deployment guide |
| [Production Release Guide](./docs/PRODUCTION_RELEASE_GUIDE.md) | Senior developer handover and release checklist |
| [GKE Deployment Guide](./docs/GKE_DEPLOYMENT_GUIDE.md) | Advanced escape hatch: self-hosted Airflow on GKE (see "Alternative deployments" above) |
| [Audit Integration](./docs/AUDIT_INTEGRATION_GUIDE.md) | Audit trail and reconciliation |
| [Pub/Sub & KMS](./docs/PUBSUB_KMS_GUIDE.md) | Event-driven triggers with encryption |
| [Error Handling](./docs/ERROR_HANDLING_GUIDE.md) | Error classification, retry, DLQ |
| [Data Quality](./docs/DATA_QUALITY_GUIDE.md) | Validation and quality scoring |
| [Creating New Deployment](./docs/CREATING_NEW_DEPLOYMENT_GUIDE.md) | How to add a new system migration |
| [Standard Migration Tasks](./docs/STANDARD_MIGRATION_TASKS.md) | Ticket templates for new systems |

**Wire contract:** See [`docs/CONTRACT.md`](docs/CONTRACT.md) for the language-neutral specification of `audit_events`, `finops_usage`, `reconciliation_record`, and `EntitySchema`. Any team writing a non-Python emitter should implement to this spec.

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
