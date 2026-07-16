# GCP Migration Framework - End-to-End Migration Functional Flow

> **Culvert deployment guide.** The reference deployments live under `deployments/`:
> Java Dataflow pipelines (`original-data-to-bigqueryload-java`,
> `postgres-cdc-streaming-java`, `mainframe-segment-transform-java`,
> `reference-e2e-gcp`), dbt transforms (`bigquery-to-mapped-product`,
> `fdp-to-consumable-product`, `spanner-to-bigquery-load`), and the config-driven
> orchestrator (`data-pipeline-orchestrator`, built on the `data-pipeline-orchestration`
> library — no more `generate_dags.py` codegen). The GCP steps here are Culvert's
> **first-implementation** operations; the deploy→test→validate→publish gate is in
> [`docs/framework-evolution/13-python-parity-release.md`](framework-evolution/13-python-parity-release.md) §2.
> The framework is **Culvert** ([`README.md`](../README.md)): the Python libraries publish
> to PyPI as the single distribution `culvert`, the Java libraries to Maven Central as
> `com.enrichmeai.culvert` (see [`RELEASE.md`](../RELEASE.md)).

**Ticket ID:** LIBRARY-E2E-001  
**Status:** Requirements Complete  
**Last Updated:** March 2026
**Version:** 1.1

---

## TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
   - [High-Level E2E Flow](#high-level-e2e-flow)
   - [Key Concepts](#key-concepts)
   - [System Comparison](#system-comparison)
   - [Technology Stack](#technology-stack)
   - [Technical Architecture Summary](#technical-architecture-summary)
2. [Complete Data Flow Diagram](#complete-data-flow-diagram)
3. [Source Systems](#source-systems)
   - [JOIN Pattern: Generic (Application A (the multi-entity JOIN system))](#join-pattern-generic-excess-management)
   - [MAP Pattern: Generic (Application B (the single-entity MAP system) Application)](#map-pattern-generic-loan-origination-application)
4. [End-to-End Processing Flow](#end-to-end-processing-flow)
   - [Stage 1: File Landing & Detection](#stage-1-file-landing--detection)
   - [Stage 2: Orchestration & Validation](#stage-2-orchestration--validation)
   - [Stage 3: ODP Load (Original Data Product)](#stage-3-odp-load-original-data-product)
   - [Stage 4: dbt Transformation (Foundation Data Product)](#stage-4-dbt-transformation-foundation-data-product)
5. [Stage Summary](#stage-summary)
6. [BigQuery Dataset Structure](#bigquery-dataset-structure)
7. [GCS Bucket Structure](#gcs-bucket-structure)
8. [Implementation Phases](#implementation-phases)
9. [Appendix](#appendix)
   - [Error Codes Reference](#a-error-codes-reference)
   - [Job Status Values](#b-job-status-values)
   - [Audit Columns](#c-audit-columns-added-to-all-tables)

---

## EXECUTIVE SUMMARY

This document provides the complete end-to-end functional requirements for the GCP Pipeline Reference Implementation. The framework migrates data from legacy mainframe systems through a standardised, event-driven pipeline into BigQuery data products.

> **Related:** For the full Technical Architecture — including security model, pluggable/hybrid patterns, architectural rationale for Beam & Composer, and governance rules — see [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md).

The **Generic system** is a combined reference demonstrating two distinct pipeline patterns simultaneously:
- **JOIN pattern** (from Application A (the multi-entity JOIN system)): 3 source entities → 3 ODP tables → 2 FDP tables. All 3 entities must complete before transformation triggers.
- **MAP pattern** (from Application B (the single-entity MAP system)): 1 source entity → 1 ODP table → 1 FDP table. Transformation triggers immediately after ODP load. 

### Why the 3-Unit Deployment model?
By decoupling **Ingestion**, **Transformation**, and **Orchestration** into independent units, the framework simplifies the end-to-end lifecycle:
- **Simpler Development**: Each unit has its own source code, dependencies, and unit tests.
- **Simpler Deployment**: Units can be deployed independently, reducing the blast radius of changes. Ingestion (Beam) and Orchestration (Airflow) can scale and fail without affecting each other.
- **Simpler Testing**: End-to-end flows can be validated unit-by-unit. For example, Ingestion can be tested with sample files without requiring an Airflow environment.
- **Micro-Orchestration**: Within the Orchestration unit, logic is further split into **separate, focused DAGs** (Trigger, Load, Transform). This prevents a "monolithic DAG" where a transformation failure could accidentally re-trigger a costly ingestion job.

### High-Level E2E Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        END-TO-END DATA MIGRATION FLOW                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌────────────┐│
│  │  MAINFRAME   │     │     GCS      │     │   BIGQUERY   │     │  BIGQUERY  ││
│  │   EXTRACT    │────►│   LANDING    │────►│     ODP      │────►│    FDP     ││
│  │              │     │    ZONE      │     │  (Raw Data)  │     │(Transformed││
│  │ System A / B │     │              │     │              │     │   Data)    ││
│  └──────────────┘     └──────────────┘     └──────────────┘     └────────────┘│
│         │                    │                    │                    │       │
│         │                    │                    │                    │       │
│         ▼                    ▼                    ▼                    ▼       │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌────────────┐│
│  │ CSV Files    │     │ .ok Trigger  │     │ 1:1 Schema   │     │ Attribute  ││
│  │ with HDR/TRL │     │ Pub/Sub Msg  │     │ Audit Cols   │     │ Mapping    ││
│  │ Split if >25M│     │ DQ Checks    │     │ Partitioned  │     │ dbt Models ││
│  └──────────────┘     └──────────────┘     └──────────────┘     └────────────┘│
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│  STAGE 1              STAGE 2              STAGE 3              STAGE 4        │
│  File Landing         Validation &         ODP Load             FDP Transform  │
│  & Detection          DQ Checks            (Beam/Dataflow)      (dbt)          │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Key Concepts

| Term | Definition |
|------|------------|
| **ODP** | Original Data Product - Raw 1:1 copy of mainframe data in BigQuery |
| **FDP** | Foundation Data Product - Transformed, business-ready data |
| **HDR** | Header record in CSV file containing metadata |
| **TRL** | Trailer record in CSV file containing record count and checksum |
| **.ok file** | Signal file indicating transfer completion |

### Reference Scope

| Pattern | Origin | Description |
|---------|--------|-------------|
| **JOIN** | Application A (the multi-entity JOIN system) | Multi-entity system: all 3 entities required before FDP transformation |
| **MAP** | Application B (the single-entity MAP system) | Single-entity system: immediate trigger after ODP load |

Both patterns are deployed together as the **Generic** reference system.

### System Comparison

| Aspect | JOIN Pattern (Application A (the multi-entity JOIN system)) | MAP Pattern (Application B (the single-entity MAP system)) |
|--------|----------------------------------|-------------------------------|
| **Source Entities** | 3 (Customers, Accounts, Decision) | 1 (Applications) |
| **Extract Schedule** | Staggered: Customers/Accounts 4 PM, Decision 5 AM | Daily |
| **Dependency Wait** | Yes — all 3 entities must succeed | No — immediate trigger |
| **ODP Tables** | 3 tables | 1 table |
| **FDP Tables** | 2 (`event_transaction_excess`, `portfolio_account_excess`) | 1 (`portfolio_account_facility`) |
| **Transformation** | JOIN (3 sources) + MAP (1 source) → 2 targets | MAP: 1 source → 1 target |

### Technology Stack

| Layer | Technology |
|-------|------------|
| **Ingestion** | GCS (Cloud Storage), Pub/Sub notifications |
| **Processing** | Apache Beam on Dataflow (Java — `data-pipeline-gcp-dataflow-java`) |
| **Orchestration** | Apache Airflow (Cloud Composer) (using `data-pipeline-orchestration`) |
| **Transformation** | dbt (SQL) (using `data-pipeline-transform`) |
| **Core Utilities** | Audit, Logging, Job Control (using `data-pipeline-core` / `data-pipeline-core-java`) |
| **Data Warehouse** | BigQuery |
| **Monitoring** | Cloud Monitoring, custom metrics |

### Technical Architecture Summary

The following architectural decisions underpin the E2E flow described in this document. Full detail is in [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md).

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Coordination** | `job_control` table (not inter-DAG calls) | Decoupled state machine; any unit can query status independently |
| **Orchestration** | Multi-DAG pattern (Trigger, Load, Transform) | Failure isolation — retry transformation without re-ingesting data |
| **Ingestion** | Apache Beam on Dataflow | HDR/TRL validation, split-file reassembly, per-record DLQ — capabilities `bq load` lacks |
| **Orchestration Runtime** | Cloud Composer (Airflow) | Complex state coordination (JOIN pattern), DAG Factory, operational UI |
| **Transformation** | dbt push-down SQL on BigQuery | Audit macros (`_run_id`, `_transformed_at`), incremental models, PII masking |
| **Security** | Dedicated Service Account per unit | Principle of Least Privilege; ingestion SA cannot modify FDP tables |
| **Pluggability** | Metadata Contract (`run_id` + `job_control`) | Any tool respecting the contract can replace Beam or dbt without redesigning orchestration |
| **Infrastructure** | Single unified Terraform module | All GCS, BigQuery datasets, Pub/Sub, IAM provisioned from `infrastructure/terraform/main.tf`; BigQuery tables are application-managed |

### Functional Library Split

To ensure clean dependency management and independent scaling, the framework is split into specialised libraries. The Python libraries are published to PyPI as the single distribution `culvert` (extras `[gcp]`, `[orchestration]`, `[transform]`, `[tester]`); the Java libraries are on Maven Central under `com.enrichmeai.culvert`:

1. **`data-pipeline-core`**: The lightweight foundation containing the contracts (audit, job control, observability, lineage), `EntitySchema`, and data quality. Zero dependencies on Beam or Airflow.
2. **`data-pipeline-gcp-dataflow-java`** (Java): The ingestion engine — Beam execution is Java-only. `DataflowPipeline`/`StageTransform` plus the GCS/BigQuery adapter libraries. Used by Ingestion deployment units.
3. **`data-pipeline-orchestration`**: The control plane logic. Contains the Pub/Sub and Dataflow sensors, `DagFactory`, `EntityDependencyChecker`, error-handling callbacks, and Airflow operators. No dependency on Beam.
4. **`data-pipeline-transform`**: The SQL logic layer. Contains shared dbt macros for PII masking, audit column injection, and code mapping.
5. **`data-pipeline-tester`**: Mocks, fixtures, and base test classes for consistent pipeline testing across all units.

### Deployment Architecture (3-Unit Model)

The Generic reference system is organised into three independent deployment units:

1. **Ingestion Unit (`original-data-to-bigqueryload-java`)**: Handles GCS → ODP load. Java Beam pipeline packaged as a shaded jar (Cloud Run Job / Dataflow).
2. **Transformation Unit (`bigquery-to-mapped-product`)**: Handles ODP → FDP transformation. Manages dbt models and SQL logic.
3. **Orchestration Unit (`data-pipeline-orchestrator`)**: The conductor. Manages Airflow DAGs deployed to Cloud Composer, Pub/Sub sensing, and cross-unit coordination.

### Security & Encryption

| Aspect | Configuration |
|--------|---------------|
| **Data in Transit** | TLS 1.2 encryption for all file transfers to GCS |
| **Data at Rest** | GCS default encryption (Google-managed keys) |
| **Bucket Type** | Regional bucket |
| **Access Control** | IAM-based access control |

---

## COMPLETE DATA FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    MAINFRAME SYSTEMS                                     │
│                                                                                          │
│    ┌────────────────────────────────┐         ┌────────────────────────────────┐        │
│    │      JOIN PATTERN (Excess Mgmt)     │         │   MAP PATTERN (Application B (the single-entity MAP system))  │        │
│    │  ┌──────────┐ ┌──────────┐    │         │  ┌──────────────────────┐      │        │
│    │  │Customers │ │ Accounts │    │         │  │    Applications      │      │        │
│    │  │ (4 PM)   │ │ (4 PM)   │    │         │  │       (Daily)        │      │        │
│    │  └────┬─────┘ └────┬─────┘    │         │  └──────────┬───────────┘      │        │
│    │       │            │          │         │             │                  │        │
│    │  ┌────┴────────────┴────┐     │         │             │                  │        │
│    │  │      Decision        │     │         │             │                  │        │
│    │  │      (5 AM)          │     │         │             │                  │        │
│    │  └──────────┬───────────┘     │         │             │                  │        │
│    └─────────────┼─────────────────┘         └─────────────┼──────────────────┘        │
│                  │                                         │                            │
└──────────────────┼─────────────────────────────────────────┼────────────────────────────┘
                   │           CSV Extract                   │
                   │         (HDR + Data + TRL)              │
                   ▼                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                           STAGE 1: GCS LANDING ZONE                                      │
│                                                                                          │
│    gs://landing-bucket/                                                                  │
│    ├── generic/                                    ├── generic/                                  │
│    │   ├── customers/                         │   └── applications/                     │
│    │   │   ├── customers_1.csv               │       ├── applications.csv              │
│    │   │   ├── customers_2.csv               │       └── applications.csv.ok ◄─TRIGGER │
│    │   │   └── customers.csv.ok ◄─TRIGGER    │                                         │
│    │   ├── accounts/                          │                                         │
│    │   │   ├── accounts.csv                   │                                         │
│    │   │   └── accounts.csv.ok ◄─TRIGGER     │                                         │
│    │   └── decision/                          │                                         │
│    │       ├── decision.csv                   │                                         │
│    │       └── decision.csv.ok ◄─TRIGGER     │                                         │
│                                                                                          │
│    ──────────────────► Pub/Sub Notification (on .ok file only)                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                    STAGE 2: CLOUD COMPOSER (AIRFLOW ORCHESTRATION)                       │
│                                                                                          │
│    ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐              │
│    │ PubSubPullSensor │────►│ File Discovery   │────►│ File Validation  │              │
│    │ (Filter .ok)     │     │ (Find splits)    │     │ (HDR/TRL check)  │              │
│    └──────────────────┘     └──────────────────┘     └────────┬─────────┘              │
│                                                                │                        │
│                                                                ▼                        │
│    ┌────────────────────────────────────────────────────────────────────────────────┐  │
│    │                         DATA QUALITY CHECKS                                     │  │
│    │  ☑ Row Type Validation      ☑ Mandatory Field Validation                       │  │
│    │  ☑ Data Type Validation     ☑ Duplicate Record Validation                      │  │
│    │  ☑ Checksum Validation      ☑ File Corruption Check                            │  │
│    └────────────────────────────────────────────────────────────────────────────────┘  │
│                              │                           │                              │
│                        SUCCESS                       FAILURE                            │
│                              │                           │                              │
│                              ▼                           ▼                              │
│                    ┌─────────────────┐         ┌─────────────────┐                     │
│                    │ Trigger Dataflow│         │ Move to Error   │                     │
│                    │ Pipeline        │         │ Folder + Alert  │                     │
│                    └────────┬────────┘         └─────────────────┘                     │
│                             │                                                           │
└─────────────────────────────┼───────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                    STAGE 3: ODP LOAD (APACHE BEAM / DATAFLOW)                               │
│                                                                                          │
│    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐        │
│    │ Read CSV     │───►│ Parse Records│───►│ Add Audit    │───►│ Write to     │        │
│    │ from GCS     │    │ (Skip HDR/TRL│    │ Columns      │    │ BigQuery ODP │        │
│    └──────────────┘    └──────────────┘    └──────────────┘    └──────┬───────┘        │
│                                                                        │                │
│                                                                        ▼                │
│    ┌────────────────────────────────────────────────────────────────────────────────┐  │
│    │                              BigQuery ODP Layer                                 │  │
│    │                                                                                 │  │
│    │   odp_generic.customers    odp_generic.accounts    odp_generic.decision    odp_generic.applications│  │
│    │   (1:1 mapping)       (1:1 mapping)      (1:1 mapping)      (1:1 mapping)       │  │
│    │                                                                                 │  │
│    └────────────────────────────────────────────────────────────────────────────────┘  │
│                              │                                       │                  │
│                   On Success │                            On Success │                  │
│                              ▼                                       ▼                  │
│              ┌───────────────────────────┐           ┌───────────────────────────┐     │
│              │ Archive Files (3 months)  │           │ Archive Files (3 months)  │     │
│              │ Update Job Status: SUCCESS│           │ Update Job Status: SUCCESS│     │
│              └───────────────┬───────────┘           └───────────────┬───────────┘     │
│                              │                                       │                  │
│              ┌───────────────▼───────────┐                          │                  │
│              │ Generic: Check All 3 Entities  │                          │                  │
│              │ Loaded for Extract Date?  │                          │                  │
│              │                           │                          │                  │
│              │ Customers ☑ Accounts ☑   │                          │                  │
│              │ Decision  ☑              │                          │                  │
│              └───────────────┬───────────┘                          │                  │
│                    All Loaded│                     Single Entity    │                  │
│                              │                     (No Wait)        │                  │
│                              ▼                                       ▼                  │
└──────────────────────────────┼───────────────────────────────────────┼──────────────────┘
                               │                                       │
                               └───────────────────┬───────────────────┘
                                                   │
                                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                    STAGE 4: FDP TRANSFORMATION (dbt)                                     │
│                                                                                          │
│    ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│    │                         Attribute Mapping (XLS)                                  │  │
│    │  - Source to target column mappings                                              │  │
│    │  - Data type transformations                                                     │  │
│    │  - Code translations (mainframe codes → business values)                         │  │
│    │  - PII masking rules                                                             │  │
│    └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                          │                                              │
│                         ┌────────────────┴────────────────┐                            │
│                         │                                  │                            │
│                         ▼                                  ▼                            │
│    ┌──────────────────────────────────┐    ┌──────────────────────────────────┐       │
│    │         JOIN PATTERN FLOW            │    │         MAP PATTERN FLOW             │       │
│    │                                  │    │                                  │       │
│    │  odp_generic.customers ──┐            │    │  odp_generic.applications            │       │
│    │  odp_generic.accounts  ──┼──► JOIN ──┐│    │           │                      │       │
│    │  odp_generic.decision  ──┼──► MAP  ──┤│    │           │                      │       │
│    │                     │           ││    │           ▼                      │       │
│    │                     ▼           ││    │    ┌───────────────────┐         │       │
│    │    ┌───────────────────────────┐││    │    │ FDP:              │         │       │
│    │    │fdp_generic:                   │││    │    │ PortfolioAccount- │         │       │
│    │    │event_transaction_excess   │││    │    │ Facility          │         │       │
│    │    │portfolio_account_excess   │││    │    └───────────────────┘         │       │
│    │    └───────────────────────────┘││    │                                  │       │
│    │                                 ││    │                                  │       │
│    │  3 Sources → 2 Targets (MULTI)  ││    │  1 Source → 1 Target (MAP)       │       │
│    └──────────────────────────────────┘    └──────────────────────────────────┘       │
│                         │                                  │                            │
│                         └────────────────┬─────────────────┘                            │
│                                          ▼                                              │
│    ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│    │                     Update Audit Table on Success                                │  │
│    │  - Source record counts        - Transformation duration                         │  │
│    │  - Target record counts        - dbt run details                                 │  │
│    │  - Run ID and timestamps       - Status (SUCCESS/FAILED)                         │  │
│    └─────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## SOURCE SYSTEMS

### JOIN Pattern: Generic (Application A (the multi-entity JOIN system))

#### Entities & Tables

| Entity | Description | Schedule | Landing Time |
|--------|-------------|----------|--------------|
| **Customers** | Customer master data | Daily | 4:00 PM |
| **Accounts** | Account information | Daily | 4:00 PM |
| **Decision** | Decisioning engine outcomes | Daily | 5:00 AM |

#### File Characteristics

| Attribute | Value |
|-----------|-------|
| **Format** | CSV (pipe-delimited for header/trailer) |
| **Split Threshold** | 25 MB |
| **Split Naming** | `{entity}_{n}` (e.g., `customers_1.csv`, `customers_2.csv`) |
| **Landing Location** | GCP Cloud Storage bucket |
| **Transfer Complete Signal** | `.ok` file (e.g., `customers.csv.ok`) |

#### Transfer Completion Pattern

Each file transfer includes a signal file to indicate completion:

```
gs://landing-bucket/generic/customers/
├── customers.csv          # Data file (or split files)
├── customers_1.csv        # Split file 1 (if > 25MB)
├── customers_2.csv        # Split file 2 (if > 25MB)
└── customers.csv.ok       # Transfer complete signal ← TRIGGERS PROCESSING
```

**Rules:**
- `.ok` file is created AFTER all data files are fully transferred
- Pipeline processing is triggered ONLY when `.ok` file is detected
- `.ok` file name matches the base entity name: `{entity}.csv.ok`
- For split files, single `.ok` file signals ALL splits are complete

#### File Structure

Each file contains three record types:

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER RECORD (1 row)                                       │
│ Format: HDR|{SYSTEM}|{ENTITY}|{DATE}                        │
│ Example: HDR|Generic|Customer|20260101                           │
├─────────────────────────────────────────────────────────────┤
│ DATA RECORDS (n rows)                                       │
│ Format: Standard CSV with column headers                    │
│ Example: id,name,ssn,status,created_date                    │
│          1001,John Doe,123-45-6789,ACTIVE,2025-01-15        │
├─────────────────────────────────────────────────────────────┤
│ TRAILER RECORD (1 row)                                      │
│ Format: TRL|RecordCount={count}|Checksum={value}            │
│ Example: TRL|RecordCount=5000|Checksum=a1b2c3d4             │
└─────────────────────────────────────────────────────────────┘
```

#### Header Record Schema

| Field | Position | Description | Example |
|-------|----------|-------------|---------|
| Record Type | 1 | Always "HDR" | `HDR` |
| System ID | 2 | Source system code | `Generic` |
| Entity Type | 3 | Entity name | `Customer`, `Account`, `Decision` |
| Extract Date | 4 | Date in YYYYMMDD format | `20260101` |

#### Trailer Record Schema

| Field | Position | Description | Example |
|-------|----------|-------------|---------|
| Record Type | 1 | Always "TRL" | `TRL` |
| Record Count | 2 | Data record count (key=value) | `RecordCount=5000` |
| Checksum | 3 | File integrity checksum (key=value) | `Checksum=a1b2c3d4` |

#### Processing Trigger

- **Responsibility starts**: When file lands in GCP bucket
- **File discovery**: Monitor bucket for new files
- **Split file handling**: Reassemble or process independently based on entity

---

### MAP Pattern: Generic (Application B (the single-entity MAP system) Application)

#### Entities & Tables

| Entity | Description | Schedule | Landing Time |
|--------|-------------|----------|--------------|
| **Applications** | Loan application data | Daily | TBD |

#### File Characteristics

| Attribute | Value |
|-----------|-------|
| **Format** | CSV (pipe-delimited for header/trailer) |
| **Split Threshold** | 25 MB |
| **Split Naming** | `{entity}_{n}` (e.g., `applications_1.csv`, `applications_2.csv`) |
| **Landing Location** | GCP Cloud Storage bucket |
| **Transfer Complete Signal** | `.ok` file (e.g., `applications.csv.ok`) |

#### File Structure

Same structure as Generic system:

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER RECORD (1 row)                                       │
│ Format: HDR|{SYSTEM}|{ENTITY}|{DATE}                        │
│ Example: HDR|Generic|Applications|20260101                      │
├─────────────────────────────────────────────────────────────┤
│ DATA RECORDS (n rows)                                       │
│ Format: Standard CSV with column headers                    │
├─────────────────────────────────────────────────────────────┤
│ TRAILER RECORD (1 row)                                      │
│ Format: TRL|RecordCount={count}|Checksum={value}            │
│ Example: TRL|RecordCount=10000|Checksum=x9y8z7              │
└─────────────────────────────────────────────────────────────┘
```

#### MAP Pattern Data Flow Summary

The MAP pattern has a simpler flow compared to the JOIN pattern:
- **Single extract** (Applications) instead of 3 entities
- **No dependency wait** — transformation triggers immediately after ODP load
- **One FDP output** (`fdp_generic.portfolio_account_facility`) from a single ODP source

```
┌─────────────────────────────────────────────────────────────┐
│ MAP PATTERN DATA FLOW                                       │
│                                                             │
│  ┌─────────────────┐                                        │
│  │ Daily Extract   │  Single daily extract                  │
│  │ (Applications)  │                                        │
│  └────────┬────────┘                                        │
│           │                                                 │
│           ▼                                                 │
│  ┌─────────────────┐                                        │
│  │ ODP Load        │  odp_generic.applications              │
│  │ (1:1 Mapping)   │                                        │
│  └────────┬────────┘                                        │
│           │                                                 │
│           │  No dependency wait (single entity)             │
│           │                                                 │
│           ▼                                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ dbt Transformation                                   │   │
│  │ (Attribute Mapping)                                  │   │
│  │                                                      │   │
│  │  odp_generic.applications                                │   │
│  │           │                                          │   │
│  │           └──────────────────┐                       │   │
│  │                              │                       │   │
│  │                              ▼                       │   │
│  │                    ┌───────────────────┐             │   │
│  │                    │ FDP:              │             │   │
│  │                    │ PortfolioAccount- │             │   │
│  │                    │ Facility          │             │   │
│  │                    └───────────────────┘             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### MAP Pattern: BigQuery Dataset Structure

```
BigQuery Project: {project_id}
│
├── odp_generic
│   └── applications                     # 1:1 mapping of mainframe APPLICATIONS
│
└── fdp_generic
    └── portfolio_account_facility       # MAP pattern FDP output
```

The MAP pattern shares the same `odp_generic` and `fdp_generic` datasets as the JOIN pattern.

#### MAP Pattern: Entity Dependency Configuration

```python
# MAP pattern: single entity — no dependency wait required

SYSTEM_ENTITY_DEPENDENCIES = {
    "generic_join": {     # JOIN pattern: Customers + Accounts + Decision
        "entities": ["customers", "accounts", "decision"],
        "required_count": 3,
        "trigger_next_stage": "transformation"
    },
    "generic_map": {      # MAP pattern: Applications only
        "entities": ["applications"],
        "required_count": 1,  # Single entity — immediate trigger
        "trigger_next_stage": "transformation"
    }
}
```

#### MAP Pattern: Transformation DAG

```python
# MAP Pattern Transformation DAG: generic_map_transformation_dag
# Triggered immediately after successful ODP load (no dependency wait)

[check_odp_ready]  ──► Verify applications ODP table has data for extract_date
        │
        ▼
[run_dbt_staging]  ──► dbt run --select staging.stg_generic_applications
        │
        ▼
[run_dbt_fdp]  ──► dbt run --select fdp_generic.portfolio_account_facility
        │
        ▼
[run_dbt_tests]  ──► dbt test --select fdp_generic.*
        │
        ├── On Success ──► [update_transform_status] ──► [update_audit_table] ──► [trigger_reconciliation]
        │
        └── On Failure ──► [log_dbt_errors] ──► [send_alert]
```

#### JOIN Pattern: FDP Table Schemas (event_transaction_excess, portfolio_account_excess)

**FDP 1: event_transaction_excess**

```sql
-- Table: fdp_generic.event_transaction_excess
-- Event and Transaction focused view of Generic applications

CREATE TABLE fdp_generic.event_transaction_excess (
    -- Primary key
    event_key               STRING NOT NULL,
    
    -- Event attributes
    application_id          STRING NOT NULL,
    event_type              STRING,
    event_date              DATE,
    event_status            STRING,
    
    -- Transaction attributes
    transaction_id          STRING,
    transaction_amount      NUMERIC,
    transaction_date        DATE,
    transaction_type        STRING,
    
    -- Excess attributes
    excess_amount           NUMERIC,
    excess_reason           STRING,
    excess_status           STRING,
    
    -- Audit columns
    _run_id                 STRING,
    _extract_date           DATE,
    _transformed_at         TIMESTAMP
)
PARTITION BY _extract_date
CLUSTER BY application_id, event_date;
```

**FDP 2: portfolio_account_excess**

```sql
-- Table: fdp_generic.portfolio_account_excess
-- Portfolio and Account focused view of Generic applications

CREATE TABLE fdp_generic.portfolio_account_excess (
    -- Primary key
    portfolio_key           STRING NOT NULL,
    
    -- Portfolio attributes
    portfolio_id            STRING NOT NULL,
    portfolio_name          STRING,
    portfolio_type          STRING,
    
    -- Account attributes
    account_id              STRING,
    account_number          STRING,
    account_type            STRING,
    account_status          STRING,
    
    -- Excess attributes
    excess_amount           NUMERIC,
    excess_category         STRING,
    excess_threshold        NUMERIC,
    
    -- Application reference
    application_id          STRING,
    
    -- Audit columns
    _run_id                 STRING,
    _extract_date           DATE,
    _transformed_at         TIMESTAMP
)
PARTITION BY _extract_date
CLUSTER BY portfolio_id, account_id;
```

#### JOIN Pattern: dbt Models

**File:** `transformations/dbt/models/fdp_generic/event_transaction_excess.sql`

```sql
{{
    config(
        materialized='incremental',
        unique_key='event_key',
        partition_by={"field": "_extract_date", "data_type": "date"},
        cluster_by=['application_id', 'event_date']
    )
}}

WITH applications AS (
    SELECT * FROM {{ ref('stg_generic_applications') }}
    {% if is_incremental() %}
    WHERE _extract_date > (SELECT MAX(_extract_date) FROM {{ this }})
    {% endif %}
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['application_id', 'event_type', 'event_date']) }} AS event_key,
    
    -- Event attributes (mapped from attribute mapping file)
    application_id,
    {{ map_code('generic', 'applications', 'event_type', 'event_type_code') }} AS event_type,
    {{ parse_mainframe_date('event_date_raw') }} AS event_date,
    {{ map_code('generic', 'applications', 'event_status', 'event_status_code') }} AS event_status,
    
    -- Transaction attributes
    transaction_id,
    transaction_amount,
    {{ parse_mainframe_date('transaction_date_raw') }} AS transaction_date,
    {{ map_code('generic', 'applications', 'transaction_type', 'txn_type_code') }} AS transaction_type,
    
    -- Excess attributes
    excess_amount,
    excess_reason,
    {{ map_code('generic', 'applications', 'excess_status', 'excess_status_code') }} AS excess_status,
    
    -- Audit columns
    _run_id,
    _extract_date,
    CURRENT_TIMESTAMP() AS _transformed_at

FROM applications
WHERE event_type_code IS NOT NULL  -- Filter for event-related records
```

**File:** `transformations/dbt/models/fdp_generic/portfolio_account_excess.sql`

```sql
{{
    config(
        materialized='incremental',
        unique_key='portfolio_key',
        partition_by={"field": "_extract_date", "data_type": "date"},
        cluster_by=['portfolio_id', 'account_id']
    )
}}

WITH applications AS (
    SELECT * FROM {{ ref('stg_generic_applications') }}
    {% if is_incremental() %}
    WHERE _extract_date > (SELECT MAX(_extract_date) FROM {{ this }})
    {% endif %}
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['portfolio_id', 'account_id']) }} AS portfolio_key,
    
    -- Portfolio attributes (mapped from attribute mapping file)
    portfolio_id,
    portfolio_name,
    {{ map_code('generic', 'applications', 'portfolio_type', 'portfolio_type_code') }} AS portfolio_type,
    
    -- Account attributes
    account_id,
    account_number,
    {{ map_code('generic', 'applications', 'account_type', 'acct_type_code') }} AS account_type,
    {{ map_code('generic', 'applications', 'account_status', 'acct_status_code') }} AS account_status,
    
    -- Excess attributes
    excess_amount,
    excess_category,
    excess_threshold,
    
    -- Application reference
    application_id,
    
    -- Audit columns
    _run_id,
    _extract_date,
    CURRENT_TIMESTAMP() AS _transformed_at

FROM applications
WHERE portfolio_id IS NOT NULL  -- Filter for portfolio-related records
```

---

## PATTERN COMPARISON: JOIN vs MAP

| Aspect | JOIN Pattern (Application A (the multi-entity JOIN system)) | MAP Pattern (Application B (the single-entity MAP system)) |
|--------|----------------------------------|-------------------------------|
| **Source Entities** | 3 (Customers, Accounts, Decision) | 1 (Applications) |
| **Extract Schedule** | Customers/Accounts: 4 PM; Decision: 5 AM | Daily |
| **Dependency Wait** | Yes — all 3 entities must succeed | No — immediate trigger |
| **ODP Tables** | 3 (`customers`, `accounts`, `decision`) | 1 (`applications`) |
| **FDP Tables** | 2 (`event_transaction_excess`, `portfolio_account_excess`) | 1 (`portfolio_account_facility`) |
| **Transformation Type** | Multi-source JOIN (3 → 2 targets) | Single-source MAP (1 → 1 target) |

---

## END-TO-END PROCESSING FLOW

### Stage 1: File Landing & Detection

```
┌─────────────────────────────────────────────────────────────┐
│ MAINFRAME (On-Premise)                                      │
│ ┌─────────┐    ┌─────────┐                                  │
│ │ Generic      │    │ Generic     │                                  │
│ └────┬────┘    └────┬────┘                                  │
│      │              │                                       │
│      └──────┬───────┘                                       │
│             │                                               │
│      File Extract (CSV)                                     │
│             │                                               │
│      ┌──────▼──────┐                                        │
│      │ File Transfer│                                       │
│      │ (SFTP/MFT)   │                                       │
│      └──────┬──────┘                                        │
│             │                                               │
│   1. Transfer data files (customers.csv, customers_1.csv)   │
│   2. Transfer .ok file (customers.csv.ok) ← LAST            │
└─────────────┼───────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│ GCP CLOUD STORAGE (Landing Zone)                            │
│                                                             │
│  gs://landing-bucket/                                       │
│  ├── generic/                                                    │
│  │   ├── customers/                                         │
│  │   │   ├── customers_1.csv      ← Data file (split 1)    │
│  │   │   ├── customers_2.csv      ← Data file (split 2)    │
│  │   │   └── customers.csv.ok     ← TRIGGER FILE            │
│  │   ├── accounts/                                          │
│  │   │   ├── accounts.csv                                   │
│  │   │   └── accounts.csv.ok                                │
│  │   └── decision/                                          │
│  │       ├── decision.csv                                   │
│  │       └── decision.csv.ok                                │
│  └── generic/                                                   │
│      └── ...                                                │
│                                                             │
│  ──► GCS sends Pub/Sub notification on .ok file upload      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ PUB/SUB NOTIFICATION                                        │
│                                                             │
│  Topic: generic-file-notifications                          │
│  Message attributes:                                        │
│    - bucketId: landing-bucket                               │
│    - objectId: generic/customers/customers.csv.ok                │
│    - eventType: OBJECT_FINALIZE                             │
│                                                             │
│  ──► Triggers Airflow DAG via sensor                        │
└─────────────────────────────────────────────────────────────┘
```

#### Stage 1 Processing Logic

1. **File Transfer**: Mainframe transfers data files first, then `.ok` file last
2. **GCS Notification**: Pub/Sub message triggered ONLY after `.ok` file lands successfully
3. **Sensor Filtering**: Airflow sensor listens for `.ok` file notifications only
4. **Trigger Pipeline**: When `.ok` notification received, pipeline processes associated data files

#### Pub/Sub Message Trigger

```
┌─────────────────────────────────────────────────────────────┐
│ GCS OBJECT NOTIFICATION (on .ok file only)                  │
│                                                             │
│  Trigger Condition:                                         │
│    - Object name ends with ".ok"                            │
│    - Event type: OBJECT_FINALIZE                            │
│                                                             │
│  Pub/Sub Message Payload:                                   │
│  {                                                          │
│    "bucket": "landing-bucket",                              │
│    "name": "generic/customers/customers.csv.ok",                 │
│    "metageneration": "1",                                   │
│    "timeCreated": "2026-01-01T16:00:00.000Z",               │
│    "updated": "2026-01-01T16:00:00.000Z"                    │
│  }                                                          │
│                                                             │
│  Message Attributes:                                        │
│    - bucketId: landing-bucket                               │
│    - objectId: generic/customers/customers.csv.ok                │
│    - eventType: OBJECT_FINALIZE                             │
│    - payloadFormat: JSON_API_V1                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Note:** GCS notification is configured to filter for `.ok` files only to avoid unnecessary Pub/Sub messages for data files.

### Stage 2: Orchestration & Validation

```
┌─────────────────────────────────────────────────────────────┐
│ CLOUD COMPOSER (Managed Apache Airflow)                     │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ PubSubPullSensor                                     │   │
│  │ ─────────────────                                    │   │
│  │ - Subscription: generic-file-notifications-sub        │   │
│  │ - Filter: .ok files only                             │   │
│  │ - Extracts metadata from message                     │   │
│  │ - Pushes to XCom: system_id, entity_type, file_path   │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Pipeline Router Task                                 │   │
│  │ ────────────────────                                 │   │
│  │ - Reads metadata from XCom                           │   │
│  │ - Determines: system_id (generic), entity, file path      │   │
│  │ - Selects appropriate pipeline configuration         │   │
│  │ - Routes to entity-specific processing               │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ File Discovery Task                                  │   │
│  │ ───────────────────                                  │   │
│  │ - Lists all data files matching .ok file pattern    │   │
│  │ - Handles split files: customers_1.csv, customers_2 │   │
│  │ - Returns list of files to process                   │   │
│  │ - Validates all expected files are present           │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ File Validation Task                                 │   │
│  │ ────────────────────                                 │   │
│  │ For each data file:                                  │   │
│  │   1. Parse header record (HDR|Generic|Customer|YYYYMMDD)  │   │
│  │   2. Validate system ID matches expected             │   │
│  │   3. Validate entity type matches expected           │   │
│  │   4. Validate extract date                           │   │
│  │   5. Parse trailer record (TRL|RecordCount|Checksum) │   │
│  │   6. Validate record count matches actual rows       │   │
│  │   7. Validate checksum (if applicable)               │   │
│  │                                                      │   │
│  │ On Validation Failure:                               │   │
│  │   - Move file to quarantine bucket                   │   │
│  │   - Send alert notification                          │   │
│  │   - Mark DAG run as failed                           │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Data Quality Check Task                              │   │
│  │ ───────────────────────                              │   │
│  │                                                      │   │
│  │ 1. ROW TYPE VALIDATION                               │   │
│  │    - Verify HDR record is first row                  │   │
│  │    - Verify TRL record is last row                   │   │
│  │    - Verify all middle rows are DATA records         │   │
│  │    - Verify no mixed record types in data section    │   │
│  │                                                      │   │
│  │ 2. DATA TYPE VALIDATION                              │   │
│  │    - Validate numeric fields contain numbers only    │   │
│  │    - Validate date fields match expected format      │   │
│  │    - Validate decimal precision/scale                │   │
│  │    - Validate string lengths within bounds           │   │
│  │    - Validate enum fields match allowed values       │   │
│  │                                                      │   │
│  │ 3. MANDATORY FIELD VALIDATION                        │   │
│  │    - Check required fields are not null/empty        │   │
│  │    - Check primary key fields are present            │   │
│  │    - Check foreign key fields are present            │   │
│  │    - Report missing field statistics                 │   │
│  │                                                      │   │
│  │ 4. DUPLICATE RECORD VALIDATION                       │   │
│  │    - Check for duplicate primary keys                │   │
│  │    - Check for duplicate composite keys              │   │
│  │    - Identify exact duplicate rows                   │   │
│  │    - Report duplicate count and sample records       │   │
│  │                                                      │   │
│  │ 5. FILE CORRUPTION VALIDATION                        │   │
│  │    - Compute file checksum (MD5/SHA256)              │   │
│  │    - Compare with trailer checksum value             │   │
│  │    - Verify file is complete (no truncation)         │   │
│  │    - Validate UTF-8 encoding                         │   │
│  │                                                      │   │
│  │ On DQ Failure:                                       │   │
│  │   - Log detailed error report                        │   │
│  │   - Move file to quarantine bucket                   │   │
│  │   - Send alert with failure summary                  │   │
│  │   - Mark DAG run as failed                           │   │
│  │                                                      │   │
│  │ On DQ Success:                                       │   │
│  │   - Log quality metrics                              │   │
│  │   - Continue to Beam pipeline processing             │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│              (Continue to Stage 3)                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### Stage 2 DAG Structure

```python
# DAG: generic_file_processing_dag (handles both JOIN and MAP pattern entities)

[PubSubPullSensor] 
        │
        ▼
[extract_metadata]  ──► XCom: {system, entity, ok_file_path, extract_date}
        │
        ▼
[discover_data_files] ──► XCom: [file1.csv, file2.csv, ...]
        │
        ▼
[validate_files]  ──► Header/Trailer structure validation
        │
        ▼
[data_quality_checks]  ──► Row type, Data type, Mandatory, Duplicates, Checksum
        │
        ├── On Success ──► [trigger_beam_pipeline]
        │
        └── On Failure ──► [quarantine_files] ──► [send_alert]
```

#### Metadata Extraction from Pub/Sub

| Extracted Field | Source | Example |
|-----------------|--------|---------|
| `bucket_id` | Message attribute | `landing-bucket` |
| `object_path` | Message attribute | `generic/customers/customers.csv.ok` |
| `system_id` | Parsed from path | `generic` |
| `entity_type` | Parsed from path | `customers` |
| `ok_file_name` | Parsed from path | `customers.csv.ok` |
| `base_file_pattern` | Derived | `customers*.csv` |
| `event_time` | Message payload | `2026-01-01T16:00:00.000Z` |

#### File Discovery Logic

```
Input: ok_file_path = "generic/customers/customers.csv.ok"

1. Extract directory: "generic/customers/"
2. Extract base name: "customers" (remove .csv.ok)
3. List files matching pattern: "customers*.csv"
4. Filter out .ok files
5. Sort by split number (if applicable)

Output: [
    "gs://landing-bucket/generic/customers/customers_1.csv",
    "gs://landing-bucket/generic/customers/customers_2.csv"
]
```

#### Validation Rules

| Validation | Rule | On Failure |
|------------|------|------------|
| **Header Present** | First line starts with `HDR\|` | Quarantine + Alert |
| **System ID Match** | Header system matches path | Quarantine + Alert |
| **Entity Match** | Header entity matches path | Quarantine + Alert |
| **Date Valid** | Header date is valid YYYYMMDD | Quarantine + Alert |
| **Trailer Present** | Last line starts with `TRL\|` | Quarantine + Alert |
| **Record Count** | Trailer count = actual data rows | Quarantine + Alert |
| **Checksum Valid** | Computed checksum matches trailer | Quarantine + Alert |
| **Split Consistency** | All splits have same header date | Quarantine + Alert |

#### Data Quality Checks

| Check Category | Validation | Details | Threshold |
|----------------|------------|---------|-----------|
| **Row Type** | HDR position | Header must be first row | 100% |
| **Row Type** | TRL position | Trailer must be last row | 100% |
| **Row Type** | Data rows | All rows between HDR and TRL are data | 100% |
| **Data Type** | Numeric fields | Must contain valid numbers | 100% |
| **Data Type** | Date fields | Must match YYYY-MM-DD or YYYYMMDD | 100% |
| **Data Type** | Decimal fields | Must have correct precision/scale | 100% |
| **Data Type** | String length | Must be within defined max length | 100% |
| **Data Type** | Enum values | Must be in allowed value list | 100% |
| **Mandatory** | Primary key | Must not be null or empty | 100% |
| **Mandatory** | Required fields | Entity-specific required fields | 100% |
| **Mandatory** | Foreign keys | Must be present if defined | 100% |
| **Duplicate** | Primary key | No duplicate primary keys | 0 duplicates |
| **Duplicate** | Composite key | No duplicate composite keys | 0 duplicates |
| **Duplicate** | Full row | No exact duplicate rows | 0 duplicates |
| **Corruption** | Checksum | MD5/SHA256 matches trailer | 100% match |
| **Corruption** | Completeness | File not truncated | 100% |
| **Corruption** | Encoding | Valid UTF-8 encoding | 100% |

#### Entity-Specific Mandatory Fields

| Entity | Mandatory Fields |
|--------|------------------|
| **Customer** | `customer_id`, `ssn`, `first_name`, `last_name`, `status` |
| **Account** | `account_id`, `customer_id`, `account_type`, `status`, `open_date` |
| **Decision** | `decision_id`, `account_id`, `decision_date`, `decision_code`, `decision_reason` |

#### Data Quality Report Output

```json
{
  "file_name": "customers_1.csv",
  "validation_timestamp": "2026-01-01T16:05:00.000Z",
  "status": "PASSED",
  "total_records": 5000,
  "checks": {
    "row_type": {"status": "PASSED", "errors": 0},
    "data_type": {"status": "PASSED", "errors": 0, "details": []},
    "mandatory_fields": {"status": "PASSED", "missing_count": 0},
    "duplicates": {"status": "PASSED", "duplicate_count": 0},
    "corruption": {"status": "PASSED", "checksum_match": true}
  },
  "quality_score": 100.0
}
```

### Stage 3: ODP Load (Original Data Product)

Post successful file validation and data quality checks, data is loaded directly to BigQuery as the **ODP (Original Data Product)**. This is a 1:1 mapping of the original mainframe DB2 data structure.

```
┌─────────────────────────────────────────────────────────────┐
│ STAGE 3: ODP LOAD TO BIGQUERY                                   │
│                                                             │
│  Input: Validated CSV files from GCS                        │
│  Output: BigQuery ODP tables (1:1 mainframe mapping)        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Apache Beam Pipeline (Dataflow)                      │   │
│  │ ──────────────────────────────                       │   │
│  │                                                      │   │
│  │  ┌────────────┐                                      │   │
│  │  │ Read CSV   │  Read from GCS (validated files)     │   │
│  │  │ from GCS   │  - customers_1.csv, customers_2.csv  │   │
│  │  └─────┬──────┘                                      │   │
│  │        │                                             │   │
│  │        ▼                                             │   │
│  │  ┌────────────┐                                      │   │
│  │  │ Parse CSV  │  - Skip HDR/TRL records              │   │
│  │  │ Records    │  - Parse data rows to dict           │   │
│  │  └─────┬──────┘                                      │   │
│  │        │                                             │   │
│  │        ▼                                             │   │
│  │  ┌────────────┐                                      │   │
│  │  │ Add Audit  │  - run_id                            │   │
│  │  │ Columns    │  - source_file                       │   │
│  │  │            │  - processed_timestamp               │   │
│  │  │            │  - extract_date (from header)        │   │
│  │  └─────┬──────┘                                      │   │
│  │        │                                             │   │
│  │        ▼                                             │   │
│  │  ┌────────────┐                                      │   │
│  │  │ Write to   │  Target: ODP dataset in BigQuery     │   │
│  │  │ BigQuery   │  Table: odp_{system}.{entity}        │   │
│  │  │ (ODP)      │  e.g., odp_generic.customers              │   │
│  │  └────────────┘                                      │   │
│  │                                                      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### ODP Design Principles

| Principle | Description |
|-----------|-------------|
| **1:1 Mapping** | ODP tables mirror original mainframe DB2 schema exactly |
| **No Transformation** | Data loaded as-is from source (raw data preservation) |
| **Audit Columns** | Additional columns added for lineage tracking |
| **Append Mode** | Daily extracts appended with extract_date partition |
| **Source of Truth** | ODP serves as the raw data layer for downstream processing |

#### ODP BigQuery Dataset Structure

```
BigQuery Project: {project_id}
│
├── odp_generic                         # Generic ODP dataset (all entities)
│   ├── customers                   # 1:1 mapping of mainframe CUSTOMERS
│   ├── accounts                    # 1:1 mapping of mainframe ACCOUNTS
│   ├── decision                    # 1:1 mapping of mainframe DECISION
│   └── applications                # 1:1 mapping of mainframe APPLICATIONS
│
└── fdp_generic                         # Generic FDP dataset (all targets)
    ├── event_transaction_excess    # JOIN pattern output
    ├── portfolio_account_excess    # JOIN pattern output
    └── portfolio_account_facility  # MAP pattern output
```

#### ODP Table Schema Pattern

Each ODP table follows this schema pattern:

```sql
-- Example: odp_generic.customers

CREATE TABLE odp_generic.customers (
    -- Original DB2 columns (1:1 mapping)
    customer_id         STRING,
    ssn                 STRING,
    first_name          STRING,
    last_name           STRING,
    date_of_birth       DATE,
    status              STRING,
    created_date        DATE,
    updated_date        DATE,
    -- ... all original columns ...
    
    -- Audit columns (added by pipeline)
    _run_id             STRING,         -- Pipeline run identifier
    _source_file        STRING,         -- Source CSV file name
    _processed_ts       TIMESTAMP,      -- When record was loaded
    _extract_date       DATE            -- Extract date from header
)
PARTITION BY _extract_date
CLUSTER BY customer_id;
```

#### ODP Audit Columns

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `_run_id` | STRING | Unique pipeline execution ID | `generic_customers_20260101_160500` |
| `_source_file` | STRING | Source file name | `customers_1.csv` |
| `_processed_ts` | TIMESTAMP | Load timestamp | `2026-01-01T16:10:00.000Z` |
| `_extract_date` | DATE | Extract date from HDR record | `2026-01-01` |

#### ODP Load Strategy

| Attribute | Value |
|-----------|-------|
| **Write Mode** | WRITE_APPEND |
| **Partitioning** | By `_extract_date` |
| **Clustering** | By primary key column(s) |
| **Deduplication** | Handled in downstream (TDP layer) |
| **Schema Evolution** | Managed via schema registry |

#### Stage 3 DAG Tasks

```python
# Continuing from Stage 2...

[data_quality_checks]
        │
        ▼ (On Success)
[trigger_dataflow_pipeline]  ──► Launches Beam job
        │
        ▼
[monitor_dataflow_job]  ──► Waits for job completion
        │
        ├── On Success ──► [record_load_metrics] ──► [archive_source_files] ──► [update_job_status_success] ──► [trigger_reconciliation]
        │
        └── On Failure ──► [move_to_error_folder] ──► [update_job_status_failure] ──► [send_alert]
```

#### Error Handling Flow

On failure of any data quality check or pipeline job, the following error handling process is executed:

```
┌─────────────────────────────────────────────────────────────┐
│ ERROR HANDLING FLOW                                         │
│                                                             │
│  Failure Triggers:                                          │
│    - Data Quality Check failure                             │
│    - File Validation failure                                │
│    - Dataflow Pipeline failure                              │
│    - BigQuery Load failure                                  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 1. Move Files to Error Folder                        │   │
│  │ ─────────────────────────────                        │   │
│  │                                                      │   │
│  │  Source: gs://landing-bucket/generic/customers/           │   │
│  │    ├── customers_1.csv                               │   │
│  │    ├── customers_2.csv                               │   │
│  │    └── customers.csv.ok                              │   │
│  │                                                      │   │
│  │              │                                       │   │
│  │              ▼ (Move on failure)                     │   │
│  │                                                      │   │
│  │  Error: gs://error-bucket/generic/customers/2026/01/01/   │   │
│  │    ├── customers_1.csv                               │   │
│  │    ├── customers_2.csv                               │   │
│  │    ├── customers.csv.ok                              │   │
│  │    └── error_report.json   ← Error details           │   │
│  │                                                      │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 2. Update Job Status Table                           │   │
│  │ ──────────────────────────                           │   │
│  │                                                      │   │
│  │  Table: job_control.pipeline_jobs                    │   │
│  │                                                      │   │
│  │  UPDATE pipeline_jobs SET                            │   │
│  │    status = 'FAILED',                                │   │
│  │    error_code = '{error_code}',                      │   │
│  │    error_message = '{error_message}',                │   │
│  │    error_file_path = 'gs://error-bucket/...',        │   │
│  │    failed_at = CURRENT_TIMESTAMP(),                  │   │
│  │    updated_at = CURRENT_TIMESTAMP()                  │   │
│  │  WHERE run_id = '{run_id}'                           │   │
│  │                                                      │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 3. Send Alert Notification                           │   │
│  │ ──────────────────────────                           │   │
│  │                                                      │   │
│  │  - Email to data-ops team                            │   │
│  │  - Slack notification to #data-alerts                │   │
│  │  - PagerDuty (if critical failure)                   │   │
│  │                                                      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### Error Folder Structure

```
gs://error-bucket/
├── generic/
│   ├── customers/
│   │   ├── 2026/01/01/
│   │   │   ├── customers_1.csv
│   │   │   ├── customers_2.csv
│   │   │   ├── customers.csv.ok
│   │   │   └── error_report.json
│   │   └── 2026/01/02/
│   │       └── ...
│   ├── accounts/
│   │   └── ...
│   └── decision/
│       └── ...
└── generic/
    └── ...
```

#### Error Report JSON Structure

```json
{
  "run_id": "generic_customers_20260101_160500",
  "system_id": "generic",
  "entity_type": "customers",
  "extract_date": "2026-01-01",
  "failed_at": "2026-01-01T16:15:00.000Z",
  "failure_stage": "DATA_QUALITY_CHECK",
  "error_code": "DQ_DUPLICATE_PK",
  "error_message": "Duplicate primary keys detected: 15 records",
  "files_affected": [
    "customers_1.csv",
    "customers_2.csv"
  ],
  "error_details": {
    "check_type": "DUPLICATE_RECORD_VALIDATION",
    "duplicate_count": 15,
    "sample_duplicates": [
      {"customer_id": "1001", "count": 2},
      {"customer_id": "1055", "count": 3}
    ]
  },
  "source_path": "gs://landing-bucket/generic/customers/",
  "error_path": "gs://error-bucket/generic/customers/2026/01/01/"
}
```

#### Job Status Table Schema

```sql
-- Table: job_control.pipeline_jobs

CREATE TABLE job_control.pipeline_jobs (
    run_id              STRING NOT NULL,        -- Unique run identifier
    system_id                STRING NOT NULL,        -- Source system identifier (e.g., generic)
    entity_type         STRING NOT NULL,        -- customers, accounts, etc.
    extract_date        DATE NOT NULL,          -- Extract date from header
    
    -- Status tracking
    status              STRING NOT NULL,        -- PENDING, RUNNING, SUCCESS, FAILED
    started_at          TIMESTAMP,              -- Pipeline start time
    completed_at        TIMESTAMP,              -- Pipeline completion time
    failed_at           TIMESTAMP,              -- Failure timestamp (if failed)
    
    -- File information
    source_files        ARRAY<STRING>,          -- List of source files
    total_records       INT64,                  -- Total records processed
    
    -- Error information (populated on failure)
    error_code          STRING,                 -- Error classification code
    error_message       STRING,                 -- Human-readable error message
    error_file_path     STRING,                 -- Path to error folder
    failure_stage       STRING,                 -- Stage where failure occurred
    
    -- Audit
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    updated_at          TIMESTAMP,
    
    PRIMARY KEY (run_id) NOT ENFORCED
)
PARTITION BY DATE(extract_date);
```

#### Job Status Values

| Status | Description |
|--------|-------------|
| `PENDING` | Job created, waiting to start |
| `RUNNING` | Pipeline currently executing |
| `SUCCESS` | Pipeline completed successfully |
| `FAILED` | Pipeline failed (see error_code) |
| `RETRYING` | Automatic retry in progress |
| `QUARANTINED` | Manual intervention required |

#### Error Codes

| Error Code | Stage | Description |
|------------|-------|-------------|
| `FILE_NOT_FOUND` | File Discovery | Expected data files not found |
| `HDR_INVALID` | File Validation | Invalid or missing header record |
| `TRL_INVALID` | File Validation | Invalid or missing trailer record |
| `RECORD_COUNT_MISMATCH` | File Validation | Trailer count doesn't match actual |
| `CHECKSUM_MISMATCH` | File Validation | Checksum validation failed |
| `DQ_ROW_TYPE` | Data Quality | Row type validation failed |
| `DQ_DATA_TYPE` | Data Quality | Data type validation failed |
| `DQ_MANDATORY_FIELD` | Data Quality | Mandatory field missing |
| `DQ_DUPLICATE_PK` | Data Quality | Duplicate primary keys found |
| `DQ_CORRUPTION` | Data Quality | File corruption detected |
| `DATAFLOW_FAILED` | ODP Load | Dataflow pipeline failed |
| `BQ_LOAD_FAILED` | ODP Load | BigQuery load failed |

#### Move to Error Folder Task

```python
# move_to_error_folder task

def move_to_error_folder(
    source_files: List[str], 
    extract_date: str,
    error_details: dict
) -> dict:
    """
    Move failed files from landing zone to error bucket.
    
    Args:
        source_files: List of file paths to move
        extract_date: Extract date from header (YYYYMMDD)
        error_details: Error information for report
    
    Returns:
        Move result with paths and error report location
    """
    move_results = []
    
    for source_path in source_files:
        # Build error path: gs://error-bucket/generic/customers/2026/01/01/
        error_path = build_error_path(
            source_path=source_path,
            error_bucket="error-bucket",
            extract_date=extract_date
        )
        
        # Move file (copy + delete source)
        gcs_client.copy(source_path, error_path)
        gcs_client.delete(source_path)
        
        move_results.append({
            "source": source_path,
            "destination": error_path
        })
    
    # Write error report JSON
    error_report_path = f"{error_path}error_report.json"
    gcs_client.write_json(error_report_path, error_details)
    
    return {
        "status": "MOVED_TO_ERROR",
        "files_moved": len(move_results),
        "error_report": error_report_path,
        "details": move_results
    }
```

#### Update Job Status Task

```python
# update_job_status task

def update_job_status_failure(
    run_id: str,
    error_code: str,
    error_message: str,
    error_file_path: str,
    failure_stage: str
) -> None:
    """
    Update job status table on pipeline failure.
    """
    query = """
        UPDATE `{project}.job_control.pipeline_jobs`
        SET
            status = 'FAILED',
            error_code = @error_code,
            error_message = @error_message,
            error_file_path = @error_file_path,
            failure_stage = @failure_stage,
            failed_at = CURRENT_TIMESTAMP(),
            updated_at = CURRENT_TIMESTAMP()
        WHERE run_id = @run_id
    """
    
    bq_client.query(query, parameters={
        "run_id": run_id,
        "error_code": error_code,
        "error_message": error_message,
        "error_file_path": error_file_path,
        "failure_stage": failure_stage
    })


def update_job_status_success(run_id: str, total_records: int) -> None:
    """
    Update job status table on pipeline success.
    """
    query = """
        UPDATE `{project}.job_control.pipeline_jobs`
        SET 
            status = 'SUCCESS',
            total_records = @total_records,
            completed_at = CURRENT_TIMESTAMP(),
            updated_at = CURRENT_TIMESTAMP()
        WHERE run_id = @run_id
    """
    
    bq_client.query(query, parameters={
        "run_id": run_id,
        "total_records": total_records
    })
```

#### File Archival (Post Successful Load)

On successful completion of the ODP data load, source files are moved to the archive folder.

```
┌─────────────────────────────────────────────────────────────┐
│ FILE ARCHIVAL PROCESS                                       │
│                                                             │
│  Source Location (Landing Zone):                            │
│    gs://landing-bucket/generic/customers/                        │
│    ├── customers_1.csv                                      │
│    ├── customers_2.csv                                      │
│    └── customers.csv.ok                                     │
│                                                             │
│                         │                                   │
│                         ▼ (Move on success)                 │
│                                                             │
│  Archive Location:                                          │
│    gs://archive-bucket/generic/customers/2026/01/01/             │
│    ├── customers_1.csv                                      │
│    ├── customers_2.csv                                      │
│    └── customers.csv.ok                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### Archive Configuration

| Attribute | Value |
|-----------|-------|
| **Archive Bucket** | `gs://archive-bucket/` |
| **Archive Path Pattern** | `{system}/{entity}/{YYYY}/{MM}/{DD}/` |
| **Retention Period** | 3 months |
| **Lifecycle Policy** | Auto-delete after 90 days |
| **Storage Class** | Nearline (cost-optimized for infrequent access) |

#### Archive Path Structure

```
gs://archive-bucket/
├── generic/
│   ├── customers/
│   │   ├── 2026/01/01/
│   │   │   ├── customers_1.csv
│   │   │   ├── customers_2.csv
│   │   │   └── customers.csv.ok
│   │   ├── 2026/01/02/
│   │   │   └── ...
│   │   └── ...
│   ├── accounts/
│   │   └── 2026/01/01/
│   │       └── ...
│   └── decision/
│       └── ...
└── generic/
    └── ...
```

#### GCS Lifecycle Policy (3-Month Retention)

```json
{
  "lifecycle": {
    "rule": [
      {
        "action": {
          "type": "Delete"
        },
        "condition": {
          "age": 90,
          "matchesPrefix": ["generic/"]
        }
      },
      {
        "action": {
          "type": "SetStorageClass",
          "storageClass": "NEARLINE"
        },
        "condition": {
          "age": 1,
          "matchesPrefix": ["generic/"]
        }
      }
    ]
  }
}
```

#### Archival Task Logic

```python
# archive_source_files task

def archive_source_files(source_files: List[str], extract_date: str) -> dict:
    """
    Move processed files from landing zone to archive bucket.
    
    Args:
        source_files: List of processed file paths
        extract_date: Extract date from header (YYYYMMDD)
    
    Returns:
        Archive result with source and destination paths
    """
    archive_results = []
    
    for source_path in source_files:
        # Parse: gs://landing-bucket/generic/customers/customers_1.csv
        # Build: gs://archive-bucket/generic/customers/2026/01/01/customers_1.csv
        
        archive_path = build_archive_path(
            source_path=source_path,
            archive_bucket="archive-bucket",
            extract_date=extract_date  # "20260101" → "2026/01/01"
        )
        
        # Move file (copy + delete source)
        gcs_client.copy(source_path, archive_path)
        gcs_client.delete(source_path)
        
        archive_results.append({
            "source": source_path,
            "destination": archive_path,
            "archived_at": datetime.utcnow().isoformat()
        })
    
    return {
        "status": "SUCCESS",
        "files_archived": len(archive_results),
        "details": archive_results
    }
```

#### Beam Pipeline Configuration

```python
# ODP Load Pipeline Configuration

pipeline_config = {
    "job_name": "odp-load-{system}-{entity}-{date}",
    "runner": "DataflowRunner",
    "project": "{gcp_project}",
    "region": "us-central1",
    "temp_location": "gs://{bucket}/temp/",
    "staging_location": "gs://{bucket}/staging/",
    
    # Input
    "source_file": ["gs://landing-bucket/generic/customers/*.csv"],
    "skip_header_lines": 1,  # Skip HDR record
    
    # Output
    "output_table": "{project}:odp_generic.customers",
    "write_disposition": "WRITE_APPEND",
    
    # Audit
    "run_id": "{run_id}",
    "extract_date": "{extract_date}"
}
```

---

### Stage 4: Transformation (dbt)

#### Entity Dependency Logic

The next stage of processing (Transformation) can **only be triggered when ALL entity extracts for a system are successfully loaded to ODP**. For Generic, this means all 3 entities must complete:

```
┌─────────────────────────────────────────────────────────────┐
│ JOIN PATTERN: ENTITY DEPENDENCY CHECK                           │
│                                                             │
│  Required Entities (JOIN pattern — Application A (the multi-entity JOIN system)):          │
│    ☑ Customers  (Daily @ 4:00 PM)                          │
│    ☑ Accounts   (Daily @ 4:00 PM)                          │
│    ☑ Decision   (Daily @ 5:00 AM)                          │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                      │   │
│  │   [Customers ODP Load]    [Accounts ODP Load]        │   │
│  │          │                       │                   │   │
│  │          ▼                       ▼                   │   │
│  │   ┌─────────────┐         ┌─────────────┐           │   │
│  │   │ SUCCESS     │         │ SUCCESS     │           │   │
│  │   │ odp_generic.     │         │ odp_generic.     │           │   │
│  │   │ customers   │         │ accounts    │           │   │
│  │   └──────┬──────┘         └──────┬──────┘           │   │
│  │          │                       │                   │   │
│  │          └───────────┬───────────┘                   │   │
│  │                      │                               │   │
│  │                      ▼                               │   │
│  │   [Decision ODP Load]                                │   │
│  │          │                                           │   │
│  │          ▼                                           │   │
│  │   ┌─────────────┐                                    │   │
│  │   │ SUCCESS     │                                    │   │
│  │   │ odp_generic.     │                                    │   │
│  │   │ decision    │                                    │   │
│  │   └──────┬──────┘                                    │   │
│  │          │                                           │   │
│  │          ▼                                           │   │
│  │   ┌─────────────────────────────────────────────┐   │   │
│  │   │ ALL 3 ENTITIES LOADED FOR EXTRACT DATE?         │   │   │
│  │   │                                             │   │   │
│  │   │  Check job_control.pipeline_jobs:           │   │   │
│  │   │    - system_id = 'generic'                           │   │   │
│  │   │    - extract_date = '2026-01-01'            │   │   │
│  │   │    - status = 'SUCCESS'                     │   │   │
│  │   │    - entity_type IN (customers, accounts,   │   │   │
│  │   │                      decision)              │   │   │
│  │   │                                             │   │   │
│  │   │  COUNT = 3? ──► YES ──► Trigger Stage 4     │   │   │
│  │   │             └─► NO  ──► Wait for remaining  │   │   │
│  │   └─────────────────────────────────────────────┘   │   │
│  │                                                      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### Entity Dependency Configuration

```python
# LIBRARY provides the EntityDependencyChecker class (flow/mechanism)
# PIPELINE provides the configuration (entities, counts, triggers)

# JOIN pattern configuration (Application A (the multi-entity JOIN system) entities)
# deployments/data-pipeline-orchestrator/src/config.py
JOIN_ENTITY_DEPENDENCIES = {
    "entities": ["customers", "accounts", "decision"],
    "required_count": 3,
    "trigger_next_stage": "transformation"
}

# MAP pattern configuration (Application B (the single-entity MAP system) — immediate trigger)
# deployments/data-pipeline-orchestrator/src/config.py
MAP_ENTITY_DEPENDENCIES = {
    "entities": ["applications"],
    "required_count": 1,  # Single entity — immediate trigger
    "trigger_next_stage": "transformation"
}

# Usage in DAG (pipeline code, not library)
from data_pipeline_orchestration import EntityDependencyChecker

checker = EntityDependencyChecker(
    project_id="my-project",
    dependencies=JOIN_ENTITY_DEPENDENCIES  # Pipeline provides config
)

if checker.all_entities_loaded("generic", extract_date):
    trigger_transformation_dag()
```

#### Dependency Check Table

| Pattern | Required Entities | Dependency Wait? | Trigger Condition |
|---------|-------------------|-----------------|-------------------|
| **JOIN** (Application A (the multi-entity JOIN system)) | Customers, Accounts, Decision | Yes — all 3 | All 3 reach SUCCESS for same `extract_date` |
| **MAP** (Application B (the single-entity MAP system)) | Applications | No | Immediate after ODP load SUCCESS |

#### Dependency Check Query

```sql
-- Check if all Generic entities are loaded for a given extract date

SELECT 
    extract_date,
    COUNT(DISTINCT entity_type) as loaded_count,
    ARRAY_AGG(entity_type) as loaded_entities,
    CASE 
        WHEN COUNT(DISTINCT entity_type) = 3 THEN 'READY_FOR_TRANSFORM'
        ELSE 'WAITING'
    END as transform_status
FROM `{project}.job_control.pipeline_jobs`
WHERE
    system_id = 'generic'
    AND extract_date = @extract_date
    AND status = 'SUCCESS'
    AND entity_type IN ('customers', 'accounts', 'decision')
GROUP BY extract_date;
```

#### Dependency Check DAG Task

```python
# check_all_entities_loaded task

def check_all_entities_loaded(system_id: str, extract_date: str) -> bool:
    """
    Check if all required entities for a system are loaded to ODP.

    Args:
        system_id: System identifier (e.g., 'generic')
        extract_date: Extract date to check

    Returns:
        True if all required entities are loaded, False otherwise
    """
    required_entities = SYSTEM_ENTITY_DEPENDENCIES[system_id]["entities"]
    required_count = SYSTEM_ENTITY_DEPENDENCIES[system_id]["required_count"]

    query = """
        SELECT COUNT(DISTINCT entity_type) as loaded_count
        FROM `{project}.job_control.pipeline_jobs`
        WHERE
            system_id = @system_id
            AND extract_date = @extract_date
            AND status = 'SUCCESS'
            AND entity_type IN UNNEST(@required_entities)
    """

    result = bq_client.query(query, parameters={
        "system_id": system_id,
        "extract_date": extract_date,
        "required_entities": required_entities
    })

    loaded_count = list(result)[0]["loaded_count"]

    return loaded_count == required_count


def trigger_transformation_if_ready(system_id: str, extract_date: str) -> str:
    """
    Trigger transformation stage if all entities are loaded.
    Called after each successful ODP load.

    Returns:
        'TRIGGERED' if transformation started, 'WAITING' otherwise
    """
    if check_all_entities_loaded(system_id, extract_date):
        # All entities loaded — trigger transformation DAG
        trigger_dag(
            dag_id=f"{system_id}_transformation_dag",
            conf={
                "system_id": system_id,
                "extract_date": extract_date,
                "run_id": generate_run_id(system_id, "transform", extract_date)
            }
        )
        return "TRIGGERED"
    else:
        # Still waiting for other entities (JOIN pattern)
        log.info(f"Waiting for all {system_id} entities to load for {extract_date}")
        return "WAITING"
```

#### Updated Stage 3 DAG Flow (with Dependency Check)

```python
# Updated DAG flow with entity dependency check

[data_quality_checks]
        │
        ▼ (On Success)
[trigger_dataflow_pipeline]
        │
        ▼
[monitor_dataflow_job]
        │
        ├── On Success ──► [record_load_metrics] 
        │                          │
        │                          ▼
        │                  [archive_source_files]
        │                          │
        │                          ▼
        │                  [update_job_status_success]
        │                          │
        │                          ▼
        │                  [check_all_entities_loaded]  ◄── NEW
        │                          │
        │                          ├── All Loaded ──► [trigger_transformation_dag]
        │                          │
        │                          └── Waiting ──► END (wait for other entities)
        │
        └── On Failure ──► [move_to_error_folder] ──► [update_job_status_failure] ──► [send_alert]
```

#### Entity Load Status Tracking

```sql
-- Table: job_control.entity_load_status
-- Tracks which entities are loaded for each extract date

CREATE TABLE job_control.entity_load_status (
    system_id            STRING NOT NULL,        -- e.g., 'generic'
    extract_date         DATE NOT NULL,
    entity_type          STRING NOT NULL,
    status               STRING NOT NULL,        -- SUCCESS, FAILED, PENDING
    run_id               STRING,
    loaded_at            TIMESTAMP,
    record_count         INT64,

    PRIMARY KEY (system_id, extract_date, entity_type) NOT ENFORCED
)
PARTITION BY extract_date;

-- View: Identify extract dates ready for transformation
CREATE VIEW job_control.v_ready_for_transformation AS
SELECT
    system_id,
    extract_date,
    COUNT(*) as entities_loaded,
    ARRAY_AGG(entity_type) as entities,
    MIN(loaded_at) as first_load,
    MAX(loaded_at) as last_load
FROM job_control.entity_load_status
WHERE status = 'SUCCESS'
GROUP BY system_id, extract_date
HAVING
    -- JOIN pattern: all 3 entities must be loaded
    (system_id = 'generic' AND COUNT(*) = 3
     AND ARRAY_LENGTH(ARRAY(SELECT e FROM UNNEST(ARRAY_AGG(entity_type)) AS e
                            WHERE e IN ('customers', 'accounts', 'decision'))) = 3)
;
```

---

### Stage 4: dbt Transformation (Foundation Data Product)

Once all 3 Generic entities (customers, accounts, decision) are loaded to ODP, the dbt transformation is triggered to create the **Foundation Data Product (FDP)**.

#### JOIN Pattern: Foundation Data Products

The JOIN pattern FDP tables (`event_transaction_excess`, `portfolio_account_excess`) are created by joining and transforming data from all 3 ODP tables using an **Attribute Mapping File**.

```
┌─────────────────────────────────────────────────────────────┐
│ STAGE 4: DBT TRANSFORMATION                                 │
│                                                             │
│  Input: ODP Tables (Raw 1:1 Mainframe Data)                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ odp_generic.     │  │ odp_generic.     │  │ odp_generic.     │         │
│  │ customers   │  │ accounts    │  │ decision    │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                 │
│         └────────────────┼────────────────┘                 │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ATTRIBUTE MAPPING FILE                               │   │
│  │ ───────────────────────                              │   │
│  │                                                      │   │
│  │  - Defines source-to-target column mappings          │   │
│  │  - Specifies data type transformations               │   │
│  │  - Defines join conditions between entities          │   │
│  │  - Specifies derived/calculated columns              │   │
│  │  - Maps mainframe codes to business values           │   │
│  │                                                      │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ DBT TRANSFORMATION                                   │   │
│  │ ──────────────────                                   │   │
│  │                                                      │   │
│  │  dbt run --select fdp_generic                          │   │
│  │                                                      │   │
│  │  Transformations Applied:                            │   │
│  │    1. event_transaction_excess: Join customers +     │   │
│  │       accounts                                       │   │
│  │    2. portfolio_account_excess: Map decision         │   │
│  │    3. Apply attribute mappings                       │   │
│  │    4. Transform data types                           │   │
│  │    5. Apply business rules                           │   │
│  │    6. Add audit columns                              │   │
│  │                                                      │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  Output: Foundation Data Product                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ fdp_generic.event_transaction_excess                    │   │
│  │ fdp_generic.portfolio_account_excess                    │   │
│  │ ─────────────────────────────────                    │   │
│  │                                                      │   │
│  │  Transformed, business-ready data targets            │   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### Data Product Layers

```
BigQuery Project: {project_id}
│
├── odp_generic                          # ODP: Original Data Product (all entities)
│   ├── customers                   # JOIN pattern — 1:1 mapping of mainframe CUSTOMERS
│   ├── accounts                    # JOIN pattern — 1:1 mapping of mainframe ACCOUNTS
│   ├── decision                    # JOIN pattern — 1:1 mapping of mainframe DECISION
│   └── applications                # MAP pattern  — 1:1 mapping of mainframe APPLICATIONS
│
└── fdp_generic                          # FDP: Foundation Data Product (all targets)
    ├── event_transaction_excess    # JOIN pattern output: joined customer-account view
    ├── portfolio_account_excess    # JOIN pattern output: decision-based portfolio view
    └── portfolio_account_facility  # MAP pattern output: loan facility records
```

#### Attribute Mapping File

The attribute mapping file defines how ODP columns are transformed into FDP columns.

**Location:** `transformations/dbt/seeds/generic_attribute_mapping.csv`

```csv
source_entity,source_column,target_column,data_type,transformation,is_required,description
customers,customer_id,customer_id,STRING,DIRECT,true,Primary customer identifier
customers,ssn,ssn_masked,STRING,MASK_SSN,true,Masked SSN (last 4 visible)
customers,first_name,first_name,STRING,UPPER,true,Customer first name
customers,last_name,last_name,STRING,UPPER,true,Customer last name
customers,date_of_birth,date_of_birth,DATE,PARSE_DATE,true,Customer DOB
customers,status,customer_status,STRING,CODE_MAP,true,Customer status description
accounts,account_id,account_id,STRING,DIRECT,true,Primary account identifier
accounts,customer_id,customer_id,STRING,DIRECT,true,FK to customer
accounts,account_type,account_type_desc,STRING,CODE_MAP,true,Account type description
accounts,balance,current_balance,NUMERIC,DIRECT,false,Current account balance
accounts,open_date,account_open_date,DATE,PARSE_DATE,true,Account opening date
decision,decision_id,decision_id,STRING,DIRECT,true,Decision identifier
decision,account_id,account_id,STRING,DIRECT,true,FK to account
decision,decision_code,decision_outcome,STRING,CODE_MAP,true,Decision outcome description
decision,decision_date,decision_date,DATE,PARSE_DATE,true,Date decision was made
decision,decision_reason,decision_reason,STRING,DIRECT,false,Reason for decision
```

#### Transformation Types

| Transformation | Description | Example |
|----------------|-------------|---------|
| `DIRECT` | No transformation, copy as-is | `customer_id` → `customer_id` |
| `UPPER` | Convert to uppercase | `first_name` → `UPPER(first_name)` |
| `LOWER` | Convert to lowercase | `email` → `LOWER(email)` |
| `TRIM` | Trim whitespace | `name` → `TRIM(name)` |
| `MASK_SSN` | Mask SSN (show last 4) | `123-45-6789` → `XXX-XX-6789` |
| `MASK_ACCOUNT` | Mask account number | `1234567890` → `******7890` |
| `PARSE_DATE` | Parse mainframe date | `20260101` → `2026-01-01` |
| `CODE_MAP` | Map code to description | `A` → `ACTIVE` |
| `CONCAT` | Concatenate fields | `first + last` → `full_name` |
| `COALESCE` | Default value if null | `COALESCE(val, 'N/A')` |
| `CALCULATED` | Custom SQL expression | `balance * rate` |

#### Code Mapping Reference Table

```sql
-- Table: reference.code_mappings
-- Stores mainframe code to business value mappings

CREATE TABLE reference.code_mappings (
    system_id        STRING,
    entity_type      STRING,
    field_name      STRING,
    source_code     STRING,
    target_value    STRING,
    description     STRING,
    effective_date  DATE,
    expiry_date     DATE
);

-- Example data:
INSERT INTO reference.code_mappings VALUES
('generic', 'customers', 'status', 'A', 'ACTIVE', 'Active customer', '2020-01-01', NULL),
('generic', 'customers', 'status', 'I', 'INACTIVE', 'Inactive customer', '2020-01-01', NULL),
('generic', 'customers', 'status', 'C', 'CLOSED', 'Closed account', '2020-01-01', NULL),
('generic', 'accounts', 'account_type', 'CHK', 'CHECKING', 'Checking account', '2020-01-01', NULL),
('generic', 'accounts', 'account_type', 'SAV', 'SAVINGS', 'Savings account', '2020-01-01', NULL),
('generic', 'decision', 'decision_code', 'APP', 'APPROVED', 'Application approved', '2020-01-01', NULL),
('generic', 'decision', 'decision_code', 'DEN', 'DENIED', 'Application denied', '2020-01-01', NULL),
('generic', 'decision', 'decision_code', 'REV', 'REVIEW', 'Pending review', '2020-01-01', NULL);
```

#### dbt Model: event_transaction_excess (JOIN)

**File:** `deployments/generic-transformation/dbt/models/fdp/event_transaction_excess.sql`

```sql
{{
    config(
        materialized='table',
        partition_by={
            "field": "_extract_date",
            "data_type": "date"
        },
        cluster_by=['customer_id', 'account_id']
    )
}}

SELECT
    c.customer_id,
    {{ mask_pii('c.ssn', 'SSN') }} AS ssn_masked,
    UPPER(c.first_name) AS first_name,
    UPPER(c.last_name) AS last_name,
    a.account_id,
    {{ map_code('generic', 'accounts', 'account_type', 'a.account_type') }} AS account_type_desc,
    a.balance AS current_balance,
    -- Audit columns
    c._run_id,
    c._extract_date,
    CURRENT_TIMESTAMP() AS _transformed_at
FROM {{ ref('stg_generic_customers') }} c
JOIN {{ ref('stg_generic_accounts') }} a ON c.customer_id = a.customer_id
    AND c._extract_date = a._extract_date
```

#### dbt Model: portfolio_account_excess (MAP)

**File:** `deployments/generic-transformation/dbt/models/fdp/portfolio_account_excess.sql`

```sql
{{
    config(
        materialized='table',
        partition_by={
            "field": "_extract_date",
            "data_type": "date"
        },
        cluster_by=['customer_id', '_run_id']
    )
}}

SELECT
    decision_id,
    customer_id,
    {{ map_code('generic', 'decision', 'decision_code', 'decision_code') }} AS decision_outcome,
    score,
    -- Audit columns
    _run_id,
    _extract_date,
    CURRENT_TIMESTAMP() AS _transformed_at
FROM {{ ref('stg_generic_decision') }}
```

#### dbt Macros for Transformation

**File:** `transformations/dbt/macros/attribute_transforms.sql`

```sql
-- Macro: Map code to description using reference table
{% macro map_code(system_id, entity_type, field_name, source_column) %}
    COALESCE(
        (SELECT target_value
         FROM {{ ref('code_mappings') }}
         WHERE system_id = '{{ system_id }}'
           AND entity_type = '{{ entity_type }}'
           AND field_name = '{{ field_name }}'
           AND source_code = {{ source_column }}
           AND CURRENT_DATE() BETWEEN effective_date AND COALESCE(expiry_date, '9999-12-31')
        ),
        {{ source_column }}  -- Default to original if no mapping found
    )
{% endmacro %}

-- Macro: Mask PII using mask_with_suffix (show last 4 digits)
{% macro mask_pii(column, pii_type) %}
    CASE
        WHEN '{{ pii_type }}' IN ('SSN', 'ID_SUFFIX') THEN {{ mask_with_suffix(column) }}
        WHEN '{{ pii_type }}' = 'EMAIL' THEN {{ mask_email(column) }}
        WHEN '{{ pii_type }}' = 'FULL' THEN {{ mask_full(column) }}
        ELSE {{ column }}
    END
{% endmacro %}

-- Macro: Parse mainframe date (YYYYMMDD to DATE)
{% macro parse_mainframe_date(column) %}
    SAFE.PARSE_DATE('%Y%m%d', {{ column }})
{% endmacro %}
```

#### Stage 4 DAG Tasks

```python
# JOIN Pattern Transformation DAG: generic_join_transformation_dag

[check_odp_ready]  ──► Verify all 3 ODP tables have data for extract_date
        │
        ▼
[run_dbt_staging]  ──► dbt run --select staging.stg_generic_*
        │
        ▼
[run_dbt_fdp]  ──► dbt run --select fdp_generic.event_transaction_excess fdp_generic.portfolio_account_excess
        │
        ▼
[run_dbt_tests]  ──► dbt test --select fdp_generic.*
        │
        ├── On Success ──► [update_transform_status] ──► [update_audit_table] ──► [trigger_reconciliation]
        │
        └── On Failure ──► [log_dbt_errors] ──► [send_alert]
```

#### Audit Table Update (Post FDP Success)

On successful completion of the FDP transformation job, the audit table is updated to record the transformation details.

```
┌─────────────────────────────────────────────────────────────┐
│ AUDIT TABLE UPDATE                                          │
│                                                             │
│  Table: audit.transformation_audit                          │
│                                                             │
│  Records:                                                   │
│    - Transformation run details                             │
│    - Source ODP tables and record counts                    │
│    - Target FDP table and record count                      │
│    - Transformation start/end timestamps                    │
│    - Status and any warnings                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### Audit Table Schema

```sql
-- Table: audit.transformation_audit

CREATE TABLE audit.transformation_audit (
    audit_id                STRING NOT NULL,        -- Unique audit record ID
    run_id                  STRING NOT NULL,        -- Transformation run ID
    system_id                    STRING NOT NULL,        -- Source system identifier (e.g., generic)
    extract_date            DATE NOT NULL,          -- Extract date being processed
    
    -- Transformation details
    transformation_type     STRING NOT NULL,        -- ODP_TO_FDP, FDP_TO_CDP, etc.
    source_dataset          STRING NOT NULL,        -- odp_generic
    target_dataset          STRING NOT NULL,        -- fdp_generic
    target_table            STRING NOT NULL,        -- event_transaction_excess
    
    -- Source entity details
    source_entities         ARRAY<STRUCT<
                                entity_name STRING,
                                record_count INT64,
                                odp_run_id STRING
                            >>,
    
    -- Record counts
    source_total_records    INT64,                  -- Total records from ODP
    target_record_count     INT64,                  -- Records written to FDP
    records_transformed     INT64,                  -- Successfully transformed
    records_rejected        INT64,                  -- Rejected during transformation
    
    -- Timestamps
    started_at              TIMESTAMP NOT NULL,
    completed_at            TIMESTAMP,
    duration_seconds        INT64,
    
    -- Status
    status                  STRING NOT NULL,        -- SUCCESS, FAILED, PARTIAL
    error_message           STRING,
    warnings                ARRAY<STRING>,
    
    -- dbt details
    dbt_run_id              STRING,
    dbt_model_name          STRING,
    dbt_execution_time_ms   INT64,
    
    -- Audit metadata
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    created_by              STRING DEFAULT SESSION_USER()
)
PARTITION BY DATE(extract_date)
CLUSTER BY system_id, transformation_type;
```

#### Update Audit Table Task

```python
# update_audit_table task

def update_audit_table(
    run_id: str,
    system_id: str,
    extract_date: str,
    source_entities: List[dict],
    target_record_count: int,
    started_at: datetime,
    completed_at: datetime,
    dbt_run_id: str,
    status: str = "SUCCESS"
) -> None:
    """
    Record transformation audit entry after successful FDP job.

    Args:
        run_id: Transformation run ID
        system_id: System identifier (e.g., 'generic')
        extract_date: Extract date processed
        source_entities: List of source entity details
        target_record_count: Records written to FDP
        started_at: Transformation start time
        completed_at: Transformation end time
        dbt_run_id: dbt run identifier
        status: Final status (SUCCESS, FAILED, PARTIAL)
    """

    # Calculate totals
    source_total = sum(e['record_count'] for e in source_entities)
    duration = int((completed_at - started_at).total_seconds())

    audit_record = {
        "audit_id": f"audit_{run_id}",
        "run_id": run_id,
        "system_id": system_id,
        "extract_date": extract_date,
        "transformation_type": "ODP_TO_FDP",
        "source_dataset": f"odp_{system_id}",
        "target_dataset": f"fdp_{system_id}",
        "source_entities": source_entities,
        "source_total_records": source_total,
        "target_record_count": target_record_count,
        "records_transformed": target_record_count,
        "records_rejected": source_total - target_record_count,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_seconds": duration,
        "status": status,
        "dbt_run_id": dbt_run_id,
    }
    
    # Insert audit record
    bq_client.insert_rows("audit.transformation_audit", [audit_record])
    
    log.info(f"Audit record created: {audit_record['audit_id']}")


# Example usage in DAG
def record_fdp_audit(**context):
    """Task to record audit after successful FDP transformation."""
    
    ti = context['ti']
    
    # Get details from previous tasks
    run_id = context['dag_run'].conf['run_id']
    system_id = context['dag_run'].conf['system_id']
    extract_date = context['dag_run'].conf['extract_date']

    # Get source entity counts from ODP (JOIN pattern: 3 entities)
    source_entities = [
        {"entity_name": "customers", "record_count": get_odp_count("customers", extract_date), "odp_run_id": get_odp_run_id("customers", extract_date)},
        {"entity_name": "accounts", "record_count": get_odp_count("accounts", extract_date), "odp_run_id": get_odp_run_id("accounts", extract_date)},
        {"entity_name": "decision", "record_count": get_odp_count("decision", extract_date), "odp_run_id": get_odp_run_id("decision", extract_date)},
    ]

    # Get FDP record count
    target_count = get_fdp_count(f"fdp_{system_id}.event_transaction_excess", extract_date)

    # Get timing from XCom
    started_at = ti.xcom_pull(task_ids='run_dbt_fdp', key='start_time')
    completed_at = datetime.utcnow()

    # Get dbt run ID
    dbt_run_id = ti.xcom_pull(task_ids='run_dbt_fdp', key='dbt_run_id')

    update_audit_table(
        run_id=run_id,
        system_id=system_id,
        extract_date=extract_date,
        source_entities=source_entities,
        target_record_count=target_count,
        started_at=started_at,
        completed_at=completed_at,
        dbt_run_id=dbt_run_id,
        status="SUCCESS"
    )
```

#### Sample Audit Record

```json
{
  "audit_id": "audit_generic_transform_20260101_170000",
  "run_id": "generic_transform_20260101_170000",
  "system_id": "generic",
  "extract_date": "2026-01-01",
  "transformation_type": "ODP_TO_FDP",
  "source_dataset": "odp_generic",
  "target_dataset": "fdp_generic",
  "target_table": "event_transaction_excess",
  "source_entities": [
    {"entity_name": "customers", "record_count": 5000, "odp_run_id": "generic_customers_20260101_160500"},
    {"entity_name": "accounts", "record_count": 8500, "odp_run_id": "generic_accounts_20260101_160510"},
    {"entity_name": "decision", "record_count": 3200, "odp_run_id": "generic_decision_20260101_050500"}
  ],
  "source_total_records": 16700,
  "target_record_count": 8500,
  "records_transformed": 8500,
  "records_rejected": 0,
  "started_at": "2026-01-01T17:00:00.000Z",
  "completed_at": "2026-01-01T17:05:30.000Z",
  "duration_seconds": 330,
  "status": "SUCCESS",
  "dbt_run_id": "dbt_run_12345",
  "dbt_model_name": "fdp_generic.event_transaction_excess",
  "warnings": [],
  "created_at": "2026-01-01T17:05:31.000Z"
}
```

#### FDP Table Schema: event_transaction_excess (JOIN)

```sql
-- Table: fdp_generic.event_transaction_excess
-- Transformed customer and account data (JOIN pattern)

CREATE TABLE fdp_generic.event_transaction_excess (
    -- Primary Keys
    customer_id             STRING NOT NULL,
    account_id              STRING NOT NULL,
    
    -- Customer Attributes
    ssn_masked              STRING,
    first_name              STRING,
    last_name               STRING,
    
    -- Account Attributes
    account_type_desc       STRING,
    current_balance         NUMERIC,
    
    -- Audit Columns
    _run_id                 STRING NOT NULL,
    _extract_date           DATE NOT NULL,
    _transformed_at         TIMESTAMP NOT NULL
)
PARTITION BY _extract_date
CLUSTER BY customer_id, account_id;
```

#### FDP Table Schema: portfolio_account_excess (MAP)

```sql
-- Table: fdp_generic.portfolio_account_excess
-- Transformed decision data (MAP pattern)

CREATE TABLE fdp_generic.portfolio_account_excess (
    -- Primary Keys
    decision_id             STRING NOT NULL,
    customer_id             STRING NOT NULL,
    
    -- Attributes
    decision_outcome        STRING,
    score                   INT64,
    
    -- Audit Columns
    _run_id                 STRING NOT NULL,
    _extract_date           DATE NOT NULL,
    _transformed_at         TIMESTAMP NOT NULL
)
PARTITION BY _extract_date
CLUSTER BY customer_id, _run_id;
```

---

## STAGE SUMMARY

### Stage 1: File Landing & Detection
- Mainframe extracts CSV files with HDR/TRL records
- Files transferred to GCS landing bucket
- `.ok` file signals transfer completion
- Pub/Sub notification triggers pipeline

### Stage 2: Orchestration & Validation  
- Cloud Composer DAG receives Pub/Sub message
- File discovery identifies all split files
- Header/Trailer validation
- Data Quality checks (row type, data type, mandatory, duplicates, checksum)
- On failure: move to error folder, update job status, send alert

### Stage 3: ODP Load
- Apache Beam pipeline (Dataflow Flex Template) reads validated CSV files
- Parses records, skips HDR/TRL envelope rows
- Adds audit columns (`_run_id`, `_source_file`, `_processed_ts`, `_extract_date`)
- Loads 1:1 to BigQuery ODP tables (`odp_generic.*`)
- On success: archive files to `{PROJECT_ID}-generic-{ENV}-archive`, update job status to SUCCESS
- **JOIN pattern**: `EntityDependencyChecker` waits for all 3 entities (customers, accounts, decision) before triggering Stage 4
- **MAP pattern**: Transformation triggered immediately after applications ODP load

### Stage 4: FDP Transformation
- Cloud Composer triggers dbt (`bigquery-to-mapped-product`)
- dbt applies attribute mapping, code translations, and PII masking macros from `data-pipeline-transform`
- **JOIN pattern**: Joins `odp_generic.customers` + `odp_generic.accounts` → `fdp_generic.event_transaction_excess`; maps `odp_generic.decision` → `fdp_generic.portfolio_account_excess`
- **MAP pattern**: Maps `odp_generic.applications` → `fdp_generic.portfolio_account_facility`
- Transformation audit record written to `audit.transformation_audit`
- Job status updated to SUCCESS in `job_control.pipeline_jobs`

---

## BIGQUERY DATASET STRUCTURE

```
BigQuery Project: {project_id}
│
├── odp_generic                              # ODP: Original Data Product (all entities)
│   ├── customers                       # JOIN pattern — 1:1 mapping of CUSTOMERS
│   ├── accounts                        # JOIN pattern — 1:1 mapping of ACCOUNTS
│   ├── decision                        # JOIN pattern — 1:1 mapping of DECISION
│   └── applications                    # MAP pattern  — 1:1 mapping of APPLICATIONS
│
├── fdp_generic                              # FDP: Foundation Data Product (all targets)
│   ├── event_transaction_excess        # JOIN pattern output: joined customer-account view
│   ├── portfolio_account_excess        # JOIN pattern output: decision-based portfolio view
│   └── portfolio_account_facility      # MAP pattern output: loan facility records
│
├── job_control                          # Pipeline coordination tables
│   ├── pipeline_jobs                   # Job status tracking (run_id, status, extract_date)
│   └── entity_load_status              # Per-entity load status for dependency checking
│
├── audit                                # Audit tables
│   └── transformation_audit            # Transformation audit log (ODP → FDP)
│
└── reference                            # Reference data
    └── code_mappings                   # Mainframe code-to-business-value translations
```

---

## GCS BUCKET STRUCTURE

### Bucket Configuration

| Attribute | Value |
|-----------|-------|
| **Bucket Type** | Regional |
| **Encryption at Rest** | Google-managed encryption keys (default) |
| **Transfer Encryption** | TLS 1.2 |
| **Access Control** | IAM-based |

### Bucket Layout

GCS buckets are environment-scoped: `{PROJECT_ID}-generic-{ENV}-{purpose}`.

```
gs://{PROJECT_ID}-generic-{ENV}-landing/      # Landing zone (source files from mainframe)
├── generic/
│   ├── customers/                            # Customers data + .ok files
│   ├── accounts/                             # Accounts data + .ok files
│   └── decision/                             # Decision data + .ok files
└── generic/
    └── applications/                         # Applications data + .ok files

gs://{PROJECT_ID}-generic-{ENV}-archive/      # Archive (3-month retention, Nearline storage)
├── generic/{entity}/{YYYY}/{MM}/{DD}/
└── generic/{entity}/{YYYY}/{MM}/{DD}/

gs://{PROJECT_ID}-generic-{ENV}-error/        # Error files (quarantine on failure)
├── generic/{entity}/{YYYY}/{MM}/{DD}/
│   └── error_report.json
└── generic/{entity}/{YYYY}/{MM}/{DD}/
    └── error_report.json

gs://{PROJECT_ID}-generic-{ENV}-temp/         # Dataflow temp/staging files
```

---

## IMPLEMENTATION PHASES

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Requirements Gathering | COMPLETE |
| 2 | Library & Deployment Restructuring | COMPLETE |
| 3 | File Ingestion & Validation | IN PROGRESS |
| 4 | Beam Pipeline Processing (ODP Load) | IN PROGRESS |
| 5 | dbt Transformations (FDP) | IN PROGRESS |
| 6 | Reconciliation & Audit | IN PROGRESS |
| 7 | Monitoring & Alerting | COMPLETE |

---

## APPENDIX

### A. Error Codes Reference

| Error Code | Stage | Description |
|------------|-------|-------------|
| `FILE_NOT_FOUND` | File Discovery | Expected data files not found |
| `HDR_INVALID` | File Validation | Invalid or missing header record |
| `TRL_INVALID` | File Validation | Invalid or missing trailer record |
| `RECORD_COUNT_MISMATCH` | File Validation | Trailer count doesn't match actual |
| `CHECKSUM_MISMATCH` | File Validation | Checksum validation failed |
| `DQ_ROW_TYPE` | Data Quality | Row type validation failed |
| `DQ_DATA_TYPE` | Data Quality | Data type validation failed |
| `DQ_MANDATORY_FIELD` | Data Quality | Mandatory field missing |
| `DQ_DUPLICATE_PK` | Data Quality | Duplicate primary keys found |
| `DQ_CORRUPTION` | Data Quality | File corruption detected |
| `DATAFLOW_FAILED` | ODP Load | Dataflow pipeline failed |
| `BQ_LOAD_FAILED` | ODP Load | BigQuery write operation failed |

### B. Job Status Values

| Status | Description |
|--------|-------------|
| `PENDING` | Job created, waiting to start |
| `RUNNING` | Pipeline currently executing |
| `SUCCESS` | Pipeline completed successfully |
| `FAILED` | Pipeline failed (see error_code) |
| `RETRYING` | Automatic retry in progress |
| `QUARANTINED` | Manual intervention required |

### C. Audit Columns (Added to All Tables)

| Column | Type | Description |
|--------|------|-------------|
| `_run_id` | STRING | Unique pipeline execution ID |
| `_source_file` | STRING | Source file name |
| `_processed_ts` | TIMESTAMP | When record was loaded |
| `_extract_date` | DATE | Extract date from HDR record |
| `_transformed_at` | TIMESTAMP | When record was transformed (FDP only) |

---

**Document Complete.**

