# Pipeline Deployments

> **Last Updated:** March 2026

This directory contains **5 deployment units (3 active, 2 reference)** that demonstrate different data pipeline patterns for mainframe-to-GCP migration using the shared library architecture.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Deployment Summary](#deployment-summary)
3. [Detailed Deployment Explanations](#detailed-deployment-explanations)
4. [Patterns Demonstrated](#patterns-demonstrated)
5. [How They Work Together](#how-they-work-together)
6. [Running the Deployments](#running-the-deployments)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DEPLOYMENT ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────┐   │
│  │   ORCHESTRATION     │   │     INGESTION       │   │  TRANSFORMATION │   │
│  │   (Airflow/GKE)     │──▶│   (Beam/Dataflow)   │──▶│   (dbt/BigQuery)│   │
│  │                     │   │                     │   │                 │   │
│  │ data-pipeline-      │   │ original-data-to-   │   │ bigquery-to-    │   │
│  │ orchestrator        │   │ bigqueryload        │   │ mapped-product  │   │
│  └─────────────────────┘   └─────────────────────┘   └─────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     SPECIALIZED PIPELINES                            │   │
│  ├─────────────────────┬───────────────────────────────────────────────┤   │
│  │ mainframe-segment-  │ CDP pipeline: FDP → Segmented GCS exports     │   │
│  │ transform           │ (Apache Beam)                                 │   │
│  ├─────────────────────┼───────────────────────────────────────────────┤   │
│  │ spanner-to-bigquery │ Federated: Spanner → BigQuery FDP             │   │
│  │ -load               │ (dbt with External Queries)                   │   │
│  └─────────────────────┴───────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Deployment Summary

| # | Deployment | Purpose | Runtime | Pattern Demonstrated |
|---|------------|---------|---------|---------------------|
| 1 | **data-pipeline-orchestrator** | Airflow DAGs for workflow coordination | Cloud Composer (Google-managed) | Event-driven orchestration, entity dependencies |
| 2 | **original-data-to-bigqueryload** | Beam pipeline for CSV → BigQuery ingestion | Dataflow (Google-managed) | HDR/TRL parsing, schema validation, audit trail |
| 3 | **bigquery-to-mapped-product** | dbt models for ODP → FDP transformation | BigQuery (native SQL) | JOIN patterns, PII masking, audit columns |
| 4 | **mainframe-segment-transform** | Beam pipeline for FDP → GCS segmented exports | Dataflow (Google-managed) | Parallel reads, segmented writes, CDP pattern |
| 5 | **spanner-to-bigquery-load** | dbt models with Spanner federated queries | BigQuery (federated) | External queries, cross-service integration |

---

## Detailed Deployment Explanations

### 1. data-pipeline-orchestrator (Orchestration)

**What it is:** Apache Airflow DAGs that coordinate the entire pipeline workflow.

**What it does:**
- Listens for file arrival events via Pub/Sub
- Triggers Dataflow ingestion jobs
- Waits for all required entities to be loaded
- Triggers dbt transformations
- Handles errors and retries

**What it demonstrates:**
- **Event-driven architecture:** DAGs triggered by Pub/Sub messages when `.ok` files arrive
- **Entity dependency management:** Waits for all 3 JOIN entities (customers, accounts, decision) + handles applications MAP trigger
- **Decoupled orchestration:** DAGs don't contain business logic—they only coordinate

**Key files:**
```
dags/
├── pubsub_trigger_dag.py    # Listens for file arrival events
├── data_ingestion_dag.py    # Triggers Dataflow ingestion jobs
├── transformation_dag.py    # Triggers dbt transformation
└── error_handling_dag.py    # Monitors and handles failures
```

**Flow:**
```
Pub/Sub Event → Sensor DAG → Ingestion DAG → [Wait for all entities] → Transform DAG
```

---

### 2. original-data-to-bigqueryload (Ingestion)

**What it is:** Apache Beam pipeline that reads mainframe CSV extracts and loads them into BigQuery ODP tables.

**What it does:**
- Reads CSV files from GCS landing bucket
- Parses HDR (header) and TRL (trailer) records for validation
- Validates record counts match trailer
- Applies schema validation
- Adds audit columns (run_id, processed_at)
- Writes to BigQuery ODP tables
- Archives processed files

**What it demonstrates:**
- **Mainframe file format handling:** HDR/TRL parsing pattern common in mainframe extracts
- **Schema-driven validation:** Uses `EntitySchema` for type checking and PII detection
- **Audit trail:** Every record gets `_run_id` for end-to-end traceability
- **Error handling:** Bad records go to error bucket, not BigQuery

**Key files:**
```
src/data_ingestion/
├── pipeline/
│   ├── runner.py           # Main Beam pipeline entry point
│   └── transforms.py       # Custom DoFn transforms
├── schema/
│   ├── customers.py        # Customer entity schema
│   ├── accounts.py         # Account entity schema
│   ├── decision.py         # Decision entity schema
│   └── applications.py     # Applications entity schema
└── validation/
    └── file_validator.py   # HDR/TRL validation logic
```

**Flow:**
```
GCS (CSV) → Parse HDR/TRL → Validate Schema → Add Audit → BigQuery ODP → Archive
```

**Example mainframe file format:**
```
HDR|GENERIC|Customers|20260307
customer_id,name,email,ssn,status
C001,John Doe,john@test.com,123-45-6789,ACTIVE
C002,Jane Smith,jane@test.com,987-65-4321,ACTIVE
TRL|RecordCount=2|Checksum=abc123
```

---

### 3. bigquery-to-mapped-product (Transformation)

**What it is:** dbt models that transform raw ODP data into business-ready FDP tables.

**What it does:**
- Reads from ODP tables (raw data)
- Applies business logic (JOINs, filtering, aggregation)
- Masks PII fields (SSN, email) based on environment
- Adds audit columns for lineage
- Writes to FDP tables (clean, business-ready data)

**What it demonstrates:**
- **ODP → FDP pattern:** Raw data (ODP) transformed into consumable data products (FDP)
- **JOIN pattern:** 3 source tables → 2 target tables (multi-to-multi)
- **Environment-aware PII masking:** Full masking in prod, partial in staging
- **Audit lineage:** `run_id` carried through from ingestion

**Key files:**
```
dbt/
├── models/
│   ├── staging/
│   │   ├── stg_customers.sql     # Clean customer data
│   │   ├── stg_accounts.sql      # Clean account data
│   │   ├── stg_decision.sql      # Clean decision data
│   │   └── stg_applications.sql  # Clean applications data
│   └── fdp/
│       ├── event_transaction_excess.sql    # JOIN: customers + accounts
│       ├── portfolio_account_excess.sql    # MAP: decision only
│       └── portfolio_account_facility.sql  # MAP: applications only
└── macros/
    ├── add_audit_columns.sql     # Inject run_id, source_file
    └── mask_pii.sql              # Environment-aware masking
```

**Flow:**
```
BigQuery ODP → Staging Models → FDP Models → BigQuery FDP
     │              │               │
     │         (clean data)    (JOINs + masking)
     │              │               │
     └──────────────┴───────────────┘
              Audit columns preserved
```

---

### 4. mainframe-segment-transform (CDP/Segmentation)

**What it is:** Apache Beam pipeline that reads FDP tables and exports segmented files to GCS.

**What it does:**
- Reads multiple FDP tables in parallel from BigQuery
- Applies segmentation logic (e.g., by region, customer type)
- Normalizes data for downstream consumption
- Writes segmented JSONL files to GCS
- Handles large datasets without memory issues

**What it demonstrates:**
- **Consumable Data Product (CDP) pattern:** FDP → external-facing exports
- **Parallel BigQuery reads:** Multiple tables read simultaneously
- **Segmented writes:** Data split into manageable chunks for consumers
- **Fluent API usage:** Clean pipeline definition using `BeamPipelineBuilder`

**Key files:**
```
src/cdp_example/
└── main.py    # Main pipeline with parallel reads and segmented writes
```

**Flow:**
```
BigQuery FDP (multiple tables) → Parallel Reads → Segment → GCS (JSONL files)
```

**Use case:**
- Export customer segments for marketing systems
- Generate regional data files for compliance
- Create data feeds for external partners

---

### 5. spanner-to-bigquery-load (Federated)

**What it is:** dbt models that query Cloud Spanner directly using BigQuery federated queries.

**What it does:**
- Connects to Cloud Spanner via BigQuery External Connection
- Queries live Spanner data using `EXTERNAL_QUERY()`
- Transforms and persists results to BigQuery FDP tables
- No ETL required—data queried in real-time

**What it demonstrates:**
- **Federated query pattern:** Direct Spanner → BigQuery without data movement
- **Real-time data access:** Query live operational data
- **Cross-service integration:** BigQuery + Spanner working together
- **dbt with external sources:** Using dbt for federated transformations

**Key files:**
```
dbt/
├── models/
│   └── fdp_spanner/
│       └── spanner_customer_summary.sql    # Federated query model
└── dbt_project.yml                          # Connection configuration
```

**Flow:**
```
Cloud Spanner → BigQuery External Query → dbt Model → BigQuery FDP
                    (no data copy)
```

**Use case:**
- Real-time reporting on operational data
- Avoiding data duplication
- Hybrid transactional/analytical queries

---

## Patterns Demonstrated

| Pattern | Deployment | Description |
|---------|------------|-------------|
| **Event-Driven** | orchestrator | Pub/Sub triggers DAGs on file arrival |
| **Entity Dependency** | orchestrator | Wait for multiple entities before proceeding |
| **HDR/TRL Parsing** | ingestion | Mainframe file format validation |
| **Schema Validation** | ingestion | Type checking and PII detection |
| **Audit Trail** | ingestion, transform | run_id for E2E traceability |
| **ODP → FDP** | transform | Raw to business-ready data |
| **JOIN (3→2)** | transform | Multiple sources to targets |
| **PII Masking** | transform | Environment-aware data protection |
| **CDP Export** | segment | FDP to external-facing files |
| **Segmented Writes** | segment | Large dataset handling |
| **Federated Query** | spanner | Cross-service data access |

---

## How They Work Together

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           END-TO-END FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. MAINFRAME EXTRACT                                                       │
│     ┌──────────┐                                                            │
│     │ CSV File │ → uploaded to GCS landing bucket                          │
│     │ .ok File │ → triggers Pub/Sub notification                           │
│     └──────────┘                                                            │
│           │                                                                 │
│           ▼                                                                 │
│  2. ORCHESTRATION (data-pipeline-orchestrator)                              │
│     ┌──────────────────┐                                                    │
│     │ Pub/Sub Sensor   │ → detects .ok file                                │
│     │ Trigger Dataflow │ → starts ingestion job                            │
│     │ Wait for Entities│ → checks job_control table                        │
│     │ Trigger dbt      │ → starts transformation                           │
│     └──────────────────┘                                                    │
│           │                                                                 │
│           ▼                                                                 │
│  3. INGESTION (original-data-to-bigqueryload)                               │
│     ┌──────────────────┐                                                    │
│     │ Read CSV         │                                                    │
│     │ Parse HDR/TRL    │ → validate file structure                         │
│     │ Validate Schema  │ → check data types                                │
│     │ Add Audit Cols   │ → inject run_id                                   │
│     │ Write to ODP     │ → BigQuery raw tables                             │
│     │ Archive File     │ → move to archive bucket                          │
│     └──────────────────┘                                                    │
│           │                                                                 │
│           ▼                                                                 │
│  4. TRANSFORMATION (bigquery-to-mapped-product)                             │
│     ┌──────────────────┐                                                    │
│     │ Stage ODP data   │ → clean and type-cast                             │
│     │ Apply JOINs      │ → business logic                                  │
│     │ Mask PII         │ → protect sensitive data                          │
│     │ Write to FDP     │ → BigQuery business tables                        │
│     └──────────────────┘                                                    │
│           │                                                                 │
│           ▼                                                                 │
│  5. OPTIONAL: CDP EXPORT (mainframe-segment-transform)                      │
│     ┌──────────────────┐                                                    │
│     │ Read FDP tables  │ → parallel BigQuery reads                         │
│     │ Apply Segments   │ → group by region/type                            │
│     │ Export to GCS    │ → JSONL files for consumers                       │
│     └──────────────────┘                                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Running the Deployments

### Prerequisites
```bash
# Set GCP project
gcloud config set project YOUR_PROJECT_ID

# Create infrastructure
./scripts/gcp/setup_gke_infrastructure.sh
```

### Run Each Deployment

| Deployment | How to Run |
|------------|------------|
| **orchestrator** | Deploy to GKE with Helm, DAGs sync from GCS |
| **ingestion** | Triggered by Airflow or run directly via Dataflow |
| **transform** | Triggered by Airflow or run `dbt run` directly |
| **segment** | Run via Dataflow with custom parameters |
| **spanner** | Run `dbt run` with Spanner connection configured |

### Quick Test
```bash
# Run E2E test (simulates full flow)
./scripts/gcp/e2e_automation_test.sh
```

---

## Library Dependencies

Each deployment uses the shared libraries from `gcp-pipeline-libraries/`:

| Deployment | Libraries Used |
|------------|----------------|
| orchestrator | `gcp-pipeline-core`, `gcp-pipeline-orchestration` |
| ingestion | `gcp-pipeline-core`, `gcp-pipeline-beam` |
| transform | `gcp-pipeline-transform` (dbt macros) |
| segment | `gcp-pipeline-core`, `gcp-pipeline-beam` |
| spanner | `gcp-pipeline-transform` (dbt macros) |

**Zero-Bleed Policy:** No library imports code from another layer (e.g., `gcp-pipeline-orchestration` never imports `apache_beam`).

Note: The `PYTHONPATH` overrides below are only necessary while using the embedded library source code. Once transitioned to Nexus packages, standard `pytest` commands will work.

```bash
# Generic Ingestion
cd original-data-to-bigqueryload
python -m pytest tests/unit/ -v

# Generic Transformation
cd ../bigquery-to-mapped-product
# dbt tests
cd dbt
dbt test
```

---

## Test Summary

| Unit | Tests |
|------|-------|
| original-data-to-bigqueryload | 26 |
| bigquery-to-mapped-product | 26 |
| **Total** | **52** |

