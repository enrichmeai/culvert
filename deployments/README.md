# Pipeline Deployments

> **Last Updated:** March 2026

This directory contains **7 deployment units (3 active, 2 code-complete, 2 reference)** that demonstrate different data pipeline patterns for mainframe-to-GCP migration using the shared library architecture.

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
│  └─────────────────────┘   └─────────────────────┘   └────────┬────────┘   │
│                                                                │            │
│  ┌─────────────────────────────────────────────────────────────┘            │
│  │                                                                          │
│  ▼                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     CDP & SPECIALIZED PIPELINES                      │   │
│  ├─────────────────────┬───────────────────────────────────────────────┤   │
│  │ fdp-to-consumable-  │ CDP pipeline: FDP → CDP consumable products   │   │
│  │ product             │ (dbt, code-complete)                          │   │
│  ├─────────────────────┼───────────────────────────────────────────────┤   │
│  │ mainframe-segment-  │ Segment pipeline: CDP → Segmented GCS exports │   │
│  │ transform           │ (Apache Beam, code-complete)                  │   │
│  ├─────────────────────┼───────────────────────────────────────────────┤   │
│  │ spanner-to-bigquery │ Federated: Spanner → BigQuery FDP             │   │
│  │ -load               │ (dbt with External Queries, reference)        │   │
│  ├─────────────────────┼───────────────────────────────────────────────┤   │
│  │ postgres-cdc-       │ Streaming: Postgres → Kafka → Beam → BigQuery │   │
│  │ streaming           │ (Beam streaming, reference/planned)           │   │
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
| 3 | **bigquery-to-mapped-product** | dbt models for ODP → FDP transformation | BigQuery (native SQL) | JOIN/MAP patterns, schema routing, audit columns |
| 4 | **mainframe-segment-transform** | Beam pipeline for CDP → GCS segmented exports | Dataflow (Google-managed) | Parallel reads, segmented writes, CDP pattern |
| 5 | **spanner-to-bigquery-load** | dbt models with Spanner federated queries | BigQuery (federated) | External queries, cross-service integration |
| 6 | **fdp-to-consumable-product** | dbt models for FDP → CDP transformation | BigQuery (native SQL) | 3-table JOIN, incremental model, code-complete |
| 7 | **postgres-cdc-streaming** | Streaming pipeline: Postgres → Kafka → Beam → BigQuery | Dataflow (streaming) | CDC, real-time ingestion, reference/planned |

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
├── generic_pubsub_trigger_dag.py    # Listens for file arrival events
├── generic_ingestion_dag.py         # Triggers Dataflow ingestion jobs
├── generic_transformation_dag.py    # Triggers dbt transformation
├── generic_error_handling_dag.py    # Monitors and handles failures
└── generic_pipeline_status_dag.py   # Pipeline status monitoring
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
- Adds audit columns for lineage (`_run_id`, `_extract_date`, `_transformed_at`)
- Writes to FDP tables (clean, business-ready data)

**What it demonstrates:**
- **ODP → FDP pattern:** Raw data (ODP) transformed into consumable data products (FDP)
- **JOIN pattern:** 2 source tables → 1 target table (customers + accounts → event_transaction_excess)
- **MAP pattern:** 1 source table → 1 target table (decision → portfolio_account_excess, applications → portfolio_account_facility)
- **Schema routing:** Custom `generate_schema_name` macro maps logical schemas to Terraform-managed datasets
- **Audit lineage:** `_run_id` and `_extract_date` carried through from ingestion

**Key files:**
```
dbt/
├── models/
│   ├── staging/
│   │   └── generic/
│   │       ├── stg_generic_customers.sql     # Clean customer data
│   │       ├── stg_generic_accounts.sql      # Clean account data
│   │       ├── stg_generic_decision.sql      # Clean decision data
│   │       └── stg_generic_applications.sql  # Clean applications data
│   ├── fdp/
│   │   ├── event_transaction_excess.sql    # JOIN: customers + accounts
│   │   ├── portfolio_account_excess.sql    # MAP: decision only
│   │   └── portfolio_account_facility.sql  # MAP: applications only
│   ├── marts/                              # Aggregated business views (placeholder)
│   └── analytics/                          # Reporting views (placeholder)
└── macros/
    ├── generate_schema_name.sql  # Routes models to Terraform-managed datasets
    ├── data_quality_check.sql    # Data quality validation
    └── incremental_strategy.sql  # Incremental load logic
```

**Flow:**
```
BigQuery ODP → Staging Views (odp_generic) → FDP Models (fdp_generic) → BigQuery FDP
     │                │                            │
     │          (clean data)              (JOINs + audit)
     │                │                            │
     └────────────────┴────────────────────────────┘
               Audit columns preserved (_run_id, _extract_date, _transformed_at)
```

---

### 4. mainframe-segment-transform (CDP/Segmentation)

**What it is:** Apache Beam pipeline that reads CDP tables and exports segmented files to GCS.

**What it does:**
- Reads CDP tables (e.g., `cdp_generic.customer_risk_profile`) from BigQuery
- Applies segmentation logic (e.g., by region, customer type)
- Normalizes data for downstream consumption
- Writes segmented JSONL files to GCS
- Handles large datasets without memory issues

**What it demonstrates:**
- **Consumable Data Product (CDP) pattern:** CDP → external-facing exports
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
BigQuery CDP (multiple tables) → Parallel Reads → Segment → GCS (JSONL files)
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
│   └── fdp/                                    # Schema: fdp_spanner
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

### 6. fdp-to-consumable-product (CDP Transformation)

**What it is:** dbt models that transform FDP data into Consumable Data Products (CDP).

**What it does:**
- Reads from multiple FDP tables
- Applies complex business logic (3-table JOIN)
- Creates consumable, business-facing data products
- Writes to CDP tables in BigQuery

**What it demonstrates:**
- **FDP → CDP pattern:** Foundation data transformed into consumable products
- **3-table JOIN:** Complex multi-source aggregation (`event_transaction_excess` + `portfolio_account_excess` + `portfolio_account_facility`)
- **Incremental model:** Efficient incremental processing for large datasets
- **Hand-written SQL:** CDP models use custom SQL (not auto-generated)

**Key files:**
```
dbt/
├── models/
│   └── cdp/
│       └── customer_risk_profile.sql    # 3-table JOIN CDP model
└── dbt_project.yml                       # CDP configuration
```

**Flow:**
```
BigQuery FDP (3 tables) → 3-Table JOIN → BigQuery CDP (customer_risk_profile)
```

**Status:** Code-complete, deployed via CI/CD.

---

### 7. postgres-cdc-streaming (Real-Time Streaming)

**What it is:** Apache Beam streaming pipeline for real-time Change Data Capture from Postgres via Kafka.

**What it does:**
- Captures change events from Postgres via CDC
- Streams through Kafka topics
- Processes with Apache Beam in streaming mode
- Writes to BigQuery ODP in near real-time

**What it demonstrates:**
- **CDC pattern:** Real-time change capture from operational databases
- **Streaming ingestion:** Continuous processing vs. batch
- **Kafka integration:** Event streaming with Apache Kafka
- **Beam streaming:** Dataflow streaming mode with windowing

**Status:** Reference/planned — stub implementation for future paved path.

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
| **JOIN (2→1)** | transform | Multiple sources to target |
| **MAP (1→1)** | transform | Single source to target |
| **CDP Export** | segment | CDP to external-facing files |
| **FDP → CDP** | cdp | Foundation to consumable data products |
| **CDC Streaming** | postgres-cdc | Real-time change data capture |
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
│  5. CDP TRANSFORMATION (fdp-to-consumable-product)                          │
│     ┌──────────────────┐                                                    │
│     │ Read FDP tables  │ → 3-table JOIN                                    │
│     │ Apply Logic      │ → business rules                                  │
│     │ Write to CDP     │ → BigQuery consumable tables                      │
│     └──────────────────┘                                                    │
│           │                                                                 │
│           ▼                                                                 │
│  6. OPTIONAL: CDP EXPORT (mainframe-segment-transform)                      │
│     ┌──────────────────┐                                                    │
│     │ Read CDP tables  │ → parallel BigQuery reads                         │
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

# Create infrastructure (one-time per environment)
./scripts/gcp/01_enable_services.sh
./scripts/gcp/02_create_state_bucket.sh
./scripts/gcp/03_create_infrastructure.sh generic
```

### Run Each Deployment

| Deployment | How to Run |
|------------|------------|
| **orchestrator** | Deploy DAGs to Cloud Composer, DAGs sync from GCS |
| **ingestion** | Triggered by Airflow or run directly via Dataflow |
| **transform** | Triggered by Airflow or run `dbt run` directly |
| **segment** | Run via Dataflow with custom parameters |
| **spanner** | Run `dbt run` with Spanner connection configured |

### Quick Test
```bash
# Run E2E test (simulates full flow)
./scripts/gcp/06_test_pipeline.sh generic
```

---

## Library Dependencies

Each deployment uses the shared libraries from `gcp-pipeline-libraries/`:

| Deployment | Libraries Used |
|------------|----------------|
| orchestrator | `gcp-pipeline-core`, `data-pipeline-orchestration` |
| ingestion | `gcp-pipeline-core`, `gcp-pipeline-beam` |
| transform | `gcp-pipeline-core`, `data-pipeline-transform` (dbt macros) |
| cdp | `gcp-pipeline-core`, `data-pipeline-transform` (dbt macros) |
| segment | `gcp-pipeline-core`, `gcp-pipeline-beam` |
| spanner | `data-pipeline-transform` (dbt macros) |
| postgres-cdc | `gcp-pipeline-core`, `gcp-pipeline-beam` |

**Zero-Bleed Policy:** No library imports code from another layer (e.g., `data-pipeline-orchestration` never imports `apache_beam`).

Libraries are installed from PyPI. Each deployment's `pyproject.toml` declares its library dependencies.

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
| data-pipeline-orchestrator | 2 |
| bigquery-to-mapped-product | 0 |
| **Total** | **28** |

