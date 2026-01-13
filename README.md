# Legacy Mainframe to GCP Data Migration Framework

A **standardized framework** for moving data from legacy mainframe systems to Google Cloud Platform. It uses shared libraries to handle common tasks like audit, security, and error handling, while allowing each system to have its own specific configuration.

---

## Why Use This Framework?

### 1. Shared Library Foundation
Instead of rebuilding common features for every system, the framework provides five core libraries (`core`, `beam`, `orchestration`, `transform`, `tester`). This ensures that every migration follows the same high standards for data integrity and security. Detailed information can be found in our [Technical Architecture Document](./docs/TECHNICAL_ARCHITECTURE.md).

### 2. Flexible and Extensible
The architecture is designed to work with different tools. While we provide ready-to-use patterns for **Apache Beam** (ingestion) and **dbt** (transformation), you can plug in your own tools if needed. 

**Community Driven Standards:** Anyone can contribute a new standardized pattern (called a "paved path") as long as it follows our [Core Governance Rules](./docs/TECHNICAL_ARCHITECTURE.md#106-governance-for-custom-paved-paths). This model is supported by multiple teams across the **the enterprise platform**, encouraging shared ownership and consistent quality.

### 3. Reliability and Visibility
The framework makes it easy to track and fix issues:
*   **Job Tracking:** Every run has a unique ID, making it easy to see exactly what happened to a specific file.
*   **FinOps & Cost Visibility:** Built-in cost estimation for BigQuery, GCS, and Pub/Sub, with automated labeling for precise cost allocation and budget management.
*   **Automatic Error Handling:** Built-in systems to retry failed tasks and move bad data to a "Dead Letter Queue" for investigation.
*   **Clear Logs:** Standardized logging that is easy to search in the Google Cloud console.

### Cloud Cost Savings

By splitting each system into three independent parts (Ingestion, Transformation, and Orchestration), we reduce infrastructure costs:

| Benefit | How it saves money |
|---------|-------------|
| **Smaller Orchestration** | The scheduler (Airflow) doesn't need heavy data processing tools installed. |
| **Efficient Ingestion** | Ingestion jobs (Dataflow) only use the resources they need for a specific task. |
| **Independent Scaling** | You can scale up ingestion for a large file without affecting the rest of the system. |
| **Faster Builds** | Smaller, focused components are faster to test and deploy. |

---

### Deployment Workflow

In a production environment (using tools like **Harness**), libraries are installed from a central repository. The libraries are managed independently to ensure stability across all systems using them.

---

## 🚀 Getting Started

The framework is designed to be simple to use. You can set up a new migration by following our guides and using our pre-built templates.

| Resource | Description |
| :--- | :--- |
| **[Creating New Deployment](./docs/CREATING_NEW_DEPLOYMENT_GUIDE.md)** | **Start Here!** Step-by-step guide to adding a new system. |
| **[Execution Guide](#-execution-guide)** | How to run tests and pipelines. |
| **[DAG Templates](./templates/dags/)** | Pre-built templates for scheduling your jobs. |
| **[Library Features](./libraries/README.md)** | Overview of built-in features like Audit, FinOps, PII Masking, and Data Quality. |
| **[FinOps Guide](./libraries/gcp-pipeline-core/README.md#5-finops--cost-tracking)** | Detailed guide for cost tracking and labeling. |

---

## 🛠 Execution Guide

The framework supports local testing and cloud-based validation.

### 1. Local Environment Setup

Each part of a system has its own isolated environment. Use the setup script to get started:

```bash
# Example: Setup the ingestion part for the EM system
./scripts/setup_deployment_venv.sh em-ingestion

# Activate the environment
source deployments/em-ingestion/venv/bin/activate
```

This script sets up everything you need to develop and test locally.

### 2. Running Tests

#### Library Tests
To run all shared library tests (700+ tests):
```bash
./scripts/run_library_tests.sh
```

#### System-Specific Tests
To run tests for a specific system component:
```bash
cd deployments/em-ingestion
PYTHONPATH=src:../../libraries/gcp-pipeline-core/src:../../libraries/gcp-pipeline-beam/src \
  python -m pytest tests/unit/
```

### 3. Local Execution

#### Running Ingestion Locally
You can test ingestion on your own machine without using Google Cloud. This is great for checking if your file parsing and data rules are working correctly.

```bash
# Activate the ingestion environment
cd deployments/em-ingestion
python -m em_ingestion.pipeline.main \
    --input_file=path/to/local/file.csv \
    --output_table=project:dataset.table \
    --runner=DirectRunner \
    --temp_location=/tmp/beam-temp
```

#### Running Transformation Locally
You can also run your data transformation rules (dbt) locally:

```bash
cd deployments/em-transformation/dbt
dbt run --profiles-dir . --target dev
```

### 4. Cloud Validation

To test the full flow on Google Cloud, use the simulation script. This mimics a file arriving from a mainframe:

```bash
# Simulates a file arrival for the EM system
./scripts/gcp/06_test_pipeline.sh em

# Simulates LOA file arrival
./scripts/gcp/06_test_pipeline.sh loa
```

This script performs the following actions:
1.  Generates sample CSV data with valid HDR/TRL records.
2.  Uploads the data files to the Landing Bucket.
3.  Uploads the `.ok` trigger file.
4.  Publishes a message to the Pub/Sub topic to trigger the Airflow DAG.

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
| [`gcp-pipeline-core`](./libraries/gcp-pipeline-core/) | Audit, monitoring, FinOps, error handling, job control | 208 |
| [`gcp-pipeline-beam`](./libraries/gcp-pipeline-beam/) | Beam pipelines, transforms, file management | 358 |
| [`gcp-pipeline-orchestration`](./libraries/gcp-pipeline-orchestration/) | Airflow DAGs, sensors, operators | 52 |
| [`gcp-pipeline-transform`](./libraries/gcp-pipeline-transform/) | dbt macros for audit columns, PII masking | - |
| [`gcp-pipeline-tester`](./libraries/gcp-pipeline-tester/) | Mocks, fixtures, base test classes | - |

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

### EM (Application A) - MULTI-TARGET Pattern

| Aspect | Value |
|--------|-------|
| Source Entities | 3 (Customers, Accounts, Decision) |
| ODP Tables | 3 |
| FDP Tables | 2 (`event_transaction_excess`, `portfolio_account_excess`) |
| Dependency | Wait for all 3 entities before FDP transformation |

### LOA (Application B) - MAP Pattern

| Aspect | Value |
|--------|-------|
| Source Entities | 1 (Applications) |
| ODP Tables | 1 |
| FDP Tables | 1 (`portfolio_account_facility`) |
| Dependency | Immediate trigger after ODP load |

---

## Project Structure

```
libraries/
├── [`gcp-pipeline-core/`](./libraries/gcp-pipeline-core/)           # 208 tests - Foundation
├── [`gcp-pipeline-beam/`](./libraries/gcp-pipeline-beam/)           # 358 tests - Ingestion
├── [`gcp-pipeline-orchestration/`](./libraries/gcp-pipeline-orchestration/)  # 52 tests - Control
├── [`gcp-pipeline-transform/`](./libraries/gcp-pipeline-transform/)      # dbt macros
└── [`gcp-pipeline-tester/`](./libraries/gcp-pipeline-tester/)         # Testing utilities

deployments/
├── [`em-ingestion/`](./deployments/em-ingestion/)                # 44 tests (3 sources)
├── [`em-transformation/`](./deployments/em-transformation/)           # dbt models (2 targets)
├── [`em-orchestration/`](./deployments/em-orchestration/)            # Airflow DAGs
├── [`loa-ingestion/`](./deployments/loa-ingestion/)               # 36 tests (1 source)
├── [`loa-transformation/`](./deployments/loa-transformation/)          # dbt models (1 target)
└── [`loa-orchestration/`](./deployments/loa-orchestration/)           # Airflow DAGs

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
| [E2E Functional Flow](./docs/E2E_FUNCTIONAL_FLOW.md) | Complete end-to-end requirements and data flow |
| [Technical Architecture](./docs/TECHNICAL_ARCHITECTURE.md) | Technical deep-dive into deployments, DAGs, and Hybrid Integration |
| [Standard Migration Tasks](./docs/STANDARD_MIGRATION_TASKS.md) | Major tasks and ticket templates for new systems |
| [Audit Integration](./docs/AUDIT_INTEGRATION_GUIDE.md) | Audit trail and reconciliation |
| [Pub/Sub & KMS](./docs/PUBSUB_KMS_GUIDE.md) | Event-driven triggers with encryption |
| [Error Handling](./docs/ERROR_HANDLING_GUIDE.md) | Error classification, retry, DLQ |
| [Data Quality](./docs/DATA_QUALITY_GUIDE.md) | Validation and quality scoring |
| [GCP Deployment](./docs/GCP_DEPLOYMENT_GUIDE.md) | Terraform and deployment guide |
| [GCP Deployment Config](./docs/GCP_DEPLOYMENT_CONFIGURATION.md) | Environment configuration |
| [GCP Deployment Testing](./docs/GCP_DEPLOYMENT_TESTING_GUIDE.md) | Testing deployed infrastructure |
| [Complete Testing](./docs/COMPLETE_TESTING_GUIDE.md) | Full testing guide |
| [BDD Testing](./docs/BDD_TESTING_GUIDE.md) | Behavior-driven development tests |
| [E2E Testing](./docs/E2E_TESTING_GUIDE.md) | End-to-end testing |
| [Docker Compose](./docs/DOCKER_COMPOSE_GUIDE.md) | Local development with Docker |
| [Creating New Deployment](./docs/CREATING_NEW_DEPLOYMENT_GUIDE.md) | How to add new system migration |
| [Production Release](./docs/PRODUCTION_RELEASE_GUIDE.md) | Senior dev handover and release guide |

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

