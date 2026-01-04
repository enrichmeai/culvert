# GDW Data Core - End-to-End Migration Functional Flow

**Ticket ID:** LIBRARY-E2E-001  
**Status:** Requirements Complete  
**Last Updated:** January 1, 2026  
**Version:** 1.0

---

## 📑 TABLE OF CONTENTS

1. [Executive Summary](#-executive-summary)
   - [High-Level E2E Flow](#high-level-e2e-flow)
   - [Key Concepts](#key-concepts)
   - [System Comparison](#system-comparison)
   - [Technology Stack](#technology-stack)
2. [Complete Data Flow Diagram](#-complete-data-flow-diagram)
3. [Source Systems](#-source-systems)
   - [System 1: EM (Application A)](#system-1-em-excess-management)
   - [System 2: LOA (Application B Application)](#system-2-loa-loan-origination-application)
4. [End-to-End Processing Flow](#-end-to-end-processing-flow)
   - [Stage 1: File Landing & Detection](#stage-1-file-landing--detection)
   - [Stage 2: Orchestration & Validation](#stage-2-orchestration--validation)
   - [Stage 3: ODP Load (Original Data Product)](#stage-3-odp-load-original-data-product)
   - [Stage 4: dbt Transformation (Foundation Data Product)](#stage-4-dbt-transformation-foundation-data-product)
5. [Stage Summary](#-stage-summary)
6. [BigQuery Dataset Structure](#-bigquery-dataset-structure)
7. [GCS Bucket Structure](#-gcs-bucket-structure)
8. [Implementation Phases](#-implementation-phases)
9. [Appendix](#-appendix)
   - [Error Codes Reference](#a-error-codes-reference)
   - [Job Status Values](#b-job-status-values)
   - [Audit Columns](#c-audit-columns-added-to-all-tables)

---

## 📋 EXECUTIVE SUMMARY

This document provides the complete end-to-end functional requirements for the legacy mainframe-to-GCP data migration framework. The framework migrates data from two mainframe systems (EM and LOA) through a standardized pipeline into BigQuery data products.

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
│  │  EM / LOA    │     │              │     │              │     │   Data)    ││
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

### Migration Scope

| System | Full Name | Description |
|--------|-----------|-------------|
| **EM** | Application A | Financial excess/surplus management system |
| **LOA** | Application B Application | Loan application processing system |

### System Comparison

| Aspect | EM (Application A) | LOA (Application B) |
|--------|------------------------|------------------------|
| **Source Entities** | 3 (Customers, Accounts, Decision) | 1 (Applications) |
| **Extract Schedule** | Customers/Accounts: 4 PM, Decision: 5 AM | Daily (TBD) |
| **Dependency Wait** | Yes - wait for all 3 entities | No - immediate trigger |
| **ODP Tables** | 3 tables | 1 table |
| **FDP Tables** | 1 (em_attributes) | 2 (event_transaction_excess, portfolio_account_excess) |
| **Transformation** | Join 3 sources → 1 target | Split 1 source → 2 targets |

### Technology Stack

| Layer | Technology |
|-------|------------|
| **Ingestion** | GCS (Cloud Storage), Pub/Sub notifications |
| **Processing** | Apache Beam on Dataflow |
| **Orchestration** | Apache Airflow (Cloud Composer) |
| **Transformation** | dbt (SQL), Beam DoFns (Python) |
| **Data Warehouse** | BigQuery |
| **Monitoring** | Cloud Monitoring, custom metrics |

### Security & Encryption

| Aspect | Configuration |
|--------|---------------|
| **Data in Transit** | TLS 1.2 encryption for all file transfers to GCS |
| **Data at Rest** | GCS default encryption (Google-managed keys) |
| **Bucket Type** | Regional bucket |
| **Access Control** | IAM-based access control |

---

## 📊 COMPLETE DATA FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    MAINFRAME SYSTEMS                                     │
│                                                                                          │
│    ┌────────────────────────────────┐         ┌────────────────────────────────┐        │
│    │         EM SYSTEM              │         │         LOA SYSTEM             │        │
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
│    ├── em/                                    ├── loa/                                  │
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
│                    STAGE 3: ODP LOAD (APACHE BEAM / DATAFLOW)                            │
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
│    │   odp_em.customers    odp_em.accounts    odp_em.decision    odp_loa.applications│  │
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
│              │ EM: Check All 3 Entities  │                          │                  │
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
│    │           EM FLOW                │    │           LOA FLOW               │       │
│    │                                  │    │                                  │       │
│    │  odp_em.customers ──┐            │    │  odp_loa.applications            │       │
│    │  odp_em.accounts  ──┼──► JOIN    │    │           │                      │       │
│    │  odp_em.decision  ──┘     │      │    │           ├────────┬─────────┐   │       │
│    │                           ▼      │    │           │        │         │   │       │
│    │               ┌──────────────┐   │    │           ▼        ▼         │   │       │
│    │               │fdp_em.       │   │    │    ┌──────────┐ ┌──────────┐ │   │       │
│    │               │em_attributes │   │    │    │fdp_loa.  │ │fdp_loa.  │ │   │       │
│    │               └──────────────┘   │    │    │event_    │ │portfolio_│ │   │       │
│    │                                  │    │    │transact- │ │account_  │ │   │       │
│    │  3 Sources → 1 Target (JOIN)     │    │    │ion_excess│ │excess    │ │   │       │
│    │                                  │    │    └──────────┘ └──────────┘ │   │       │
│    │                                  │    │                              │   │       │
│    │                                  │    │  1 Source → 2 Targets (SPLIT)│   │       │
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

## 🏢 SOURCE SYSTEMS

### System 1: EM (Application A)

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
gs://landing-bucket/em/customers/
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
│ Example: HDR|EM|Customer|20260101                           │
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
| System ID | 2 | Source system code | `EM` |
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

### System 2: LOA (Application B Application)

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

Same structure as EM system:

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER RECORD (1 row)                                       │
│ Format: HDR|{SYSTEM}|{ENTITY}|{DATE}                        │
│ Example: HDR|LOA|Applications|20260101                      │
├─────────────────────────────────────────────────────────────┤
│ DATA RECORDS (n rows)                                       │
│ Format: Standard CSV with column headers                    │
├─────────────────────────────────────────────────────────────┤
│ TRAILER RECORD (1 row)                                      │
│ Format: TRL|RecordCount={count}|Checksum={value}            │
│ Example: TRL|RecordCount=10000|Checksum=x9y8z7              │
└─────────────────────────────────────────────────────────────┘
```

#### LOA Data Flow Summary

LOA has a **simpler flow** compared to EM:
- **Single extract** (Applications) instead of 3 entities
- **No dependency wait** - Transform triggers immediately after ODP load
- **Two FDP outputs** from single ODP source

```
┌─────────────────────────────────────────────────────────────┐
│ LOA DATA FLOW                                               │
│                                                             │
│  ┌─────────────────┐                                        │
│  │ LOA Extract     │  Single daily extract                  │
│  │ (Applications)  │                                        │
│  └────────┬────────┘                                        │
│           │                                                 │
│           ▼                                                 │
│  ┌─────────────────┐                                        │
│  │ ODP Load        │  odp_loa.applications                  │
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
│  │  odp_loa.applications                                │   │
│  │           │                                          │   │
│  │           ├──────────────────┐                       │   │
│  │           │                  │                       │   │
│  │           ▼                  ▼                       │   │
│  │  ┌───────────────┐  ┌───────────────────┐           │   │
│  │  │ FDP 1:        │  │ FDP 2:            │           │   │
│  │  │ EventTrans-   │  │ PortfolioAccount- │           │   │
│  │  │ actionExcess  │  │ Excess            │           │   │
│  │  └───────────────┘  └───────────────────┘           │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### LOA BigQuery Dataset Structure

```
BigQuery Project: {project_id}
│
├── odp_loa                              # ODP: Original Data Product (Raw)
│   └── applications                     # 1:1 mapping of LOA.APPLICATIONS
│
└── fdp_loa                              # FDP: Foundation Data Product (Transformed)
    ├── event_transaction_excess         # FDP 1: Event/Transaction focused view
    └── portfolio_account_excess         # FDP 2: Portfolio/Account focused view
```

#### LOA Entity Dependency Configuration

```python
# LOA has single entity - no dependency wait required

SYSTEM_ENTITY_DEPENDENCIES = {
    "em": {
        "entities": ["customers", "accounts", "decision"],
        "required_count": 3,
        "trigger_next_stage": "transformation"
    },
    "loa": {
        "entities": ["applications"],
        "required_count": 1,  # Single entity - immediate trigger
        "trigger_next_stage": "transformation"
    }
}
```

#### LOA Transformation DAG

```python
# LOA Transformation DAG: loa_transformation_dag
# Triggered immediately after successful ODP load (no dependency wait)

[check_odp_ready]  ──► Verify applications ODP table has data for extract_date
        │
        ▼
[run_dbt_staging]  ──► dbt run --select staging.stg_loa_applications
        │
        ▼
[run_dbt_fdp]  ──► dbt run --select fdp_loa.event_transaction_excess fdp_loa.portfolio_account_excess
        │
        ▼
[run_dbt_tests]  ──► dbt test --select fdp_loa.*
        │
        ├── On Success ──► [update_transform_status] ──► [update_audit_table] ──► [trigger_reconciliation]
        │
        └── On Failure ──► [log_dbt_errors] ──► [send_alert]
```

#### LOA FDP Table Schemas

**FDP 1: event_transaction_excess**

```sql
-- Table: fdp_loa.event_transaction_excess
-- Event and Transaction focused view of LOA applications

CREATE TABLE fdp_loa.event_transaction_excess (
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
    _transformed_ts         TIMESTAMP
)
PARTITION BY _extract_date
CLUSTER BY application_id, event_date;
```

**FDP 2: portfolio_account_excess**

```sql
-- Table: fdp_loa.portfolio_account_excess
-- Portfolio and Account focused view of LOA applications

CREATE TABLE fdp_loa.portfolio_account_excess (
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
    _transformed_ts         TIMESTAMP
)
PARTITION BY _extract_date
CLUSTER BY portfolio_id, account_id;
```

#### LOA dbt Models

**File:** `transformations/dbt/models/fdp_loa/event_transaction_excess.sql`

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
    SELECT * FROM {{ ref('stg_loa_applications') }}
    {% if is_incremental() %}
    WHERE _extract_date > (SELECT MAX(_extract_date) FROM {{ this }})
    {% endif %}
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['application_id', 'event_type', 'event_date']) }} AS event_key,
    
    -- Event attributes (mapped from attribute mapping file)
    application_id,
    {{ map_code('loa', 'applications', 'event_type', 'event_type_code') }} AS event_type,
    {{ parse_mainframe_date('event_date_raw') }} AS event_date,
    {{ map_code('loa', 'applications', 'event_status', 'event_status_code') }} AS event_status,
    
    -- Transaction attributes
    transaction_id,
    transaction_amount,
    {{ parse_mainframe_date('transaction_date_raw') }} AS transaction_date,
    {{ map_code('loa', 'applications', 'transaction_type', 'txn_type_code') }} AS transaction_type,
    
    -- Excess attributes
    excess_amount,
    excess_reason,
    {{ map_code('loa', 'applications', 'excess_status', 'excess_status_code') }} AS excess_status,
    
    -- Audit columns
    _run_id,
    _extract_date,
    CURRENT_TIMESTAMP() AS _transformed_ts

FROM applications
WHERE event_type_code IS NOT NULL  -- Filter for event-related records
```

**File:** `transformations/dbt/models/fdp_loa/portfolio_account_excess.sql`

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
    SELECT * FROM {{ ref('stg_loa_applications') }}
    {% if is_incremental() %}
    WHERE _extract_date > (SELECT MAX(_extract_date) FROM {{ this }})
    {% endif %}
)

SELECT
    {{ dbt_utils.generate_surrogate_key(['portfolio_id', 'account_id']) }} AS portfolio_key,
    
    -- Portfolio attributes (mapped from attribute mapping file)
    portfolio_id,
    portfolio_name,
    {{ map_code('loa', 'applications', 'portfolio_type', 'portfolio_type_code') }} AS portfolio_type,
    
    -- Account attributes
    account_id,
    account_number,
    {{ map_code('loa', 'applications', 'account_type', 'acct_type_code') }} AS account_type,
    {{ map_code('loa', 'applications', 'account_status', 'acct_status_code') }} AS account_status,
    
    -- Excess attributes
    excess_amount,
    excess_category,
    excess_threshold,
    
    -- Application reference
    application_id,
    
    -- Audit columns
    _run_id,
    _extract_date,
    CURRENT_TIMESTAMP() AS _transformed_ts

FROM applications
WHERE portfolio_id IS NOT NULL  -- Filter for portfolio-related records
```

---

## 📊 SYSTEM COMPARISON: EM vs LOA

| Aspect | EM (Application A) | LOA (Application B Application) |
|--------|------------------------|-------------------------------------|
| **Source Entities** | 3 (Customers, Accounts, Decision) | 1 (Applications) |
| **Extract Schedule** | Customers/Accounts: 4 PM, Decision: 5 AM | TBD |
| **Dependency Wait** | Yes - wait for all 3 entities | No - immediate trigger |
| **ODP Tables** | 3 tables | 1 table |
| **FDP Tables** | 1 (em_attributes) | 2 (event_transaction_excess, portfolio_account_excess) |
| **Transformation Type** | Join 3 sources → 1 target | Split 1 source → 2 targets |

---

## 🔄 END-TO-END PROCESSING FLOW

### Stage 1: File Landing & Detection

```
┌─────────────────────────────────────────────────────────────┐
│ MAINFRAME (On-Premise)                                      │
│ ┌─────────┐    ┌─────────┐                                  │
│ │ EM      │    │ LOA     │                                  │
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
│  ├── em/                                                    │
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
│  └── loa/                                                   │
│      └── ...                                                │
│                                                             │
│  ──► GCS sends Pub/Sub notification on .ok file upload      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ PUB/SUB NOTIFICATION                                        │
│                                                             │
│  Topic: file-landing-notifications                          │
│  Message attributes:                                        │
│    - bucketId: landing-bucket                               │
│    - objectId: em/customers/customers.csv.ok                │
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
│    "name": "em/customers/customers.csv.ok",                 │
│    "metageneration": "1",                                   │
│    "timeCreated": "2026-01-01T16:00:00.000Z",               │
│    "updated": "2026-01-01T16:00:00.000Z"                    │
│  }                                                          │
│                                                             │
│  Message Attributes:                                        │
│    - bucketId: landing-bucket                               │
│    - objectId: em/customers/customers.csv.ok                │
│    - eventType: OBJECT_FINALIZE                             │
│    - payloadFormat: JSON_API_V1                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Note:** GCS notification is configured to filter for `.ok` files only to avoid unnecessary Pub/Sub messages for data files.

### Stage 2: Orchestration & Validation

```
┌─────────────────────────────────────────────────────────────┐
│ CLOUD COMPOSER (Apache Airflow)                             │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ PubSubPullSensor                                     │   │
│  │ ─────────────────                                    │   │
│  │ - Subscription: file-landing-sub                     │   │
│  │ - Filter: .ok files only                             │   │
│  │ - Extracts metadata from message                     │   │
│  │ - Pushes to XCom: system_id, entity_type, file_path  │   │
│  └──────────────────────┬──────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Pipeline Router Task                                 │   │
│  │ ────────────────────                                 │   │
│  │ - Reads metadata from XCom                           │   │
│  │ - Determines: system (EM/LOA), entity, file path     │   │
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
│  │   1. Parse header record (HDR|EM|Customer|YYYYMMDD)  │   │
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
# DAG: em_file_processing_dag / loa_file_processing_dag

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
| `object_path` | Message attribute | `em/customers/customers.csv.ok` |
| `system_id` | Parsed from path | `em` |
| `entity_type` | Parsed from path | `customers` |
| `ok_file_name` | Parsed from path | `customers.csv.ok` |
| `base_file_pattern` | Derived | `customers*.csv` |
| `event_time` | Message payload | `2026-01-01T16:00:00.000Z` |

#### File Discovery Logic

```
Input: ok_file_path = "em/customers/customers.csv.ok"

1. Extract directory: "em/customers/"
2. Extract base name: "customers" (remove .csv.ok)
3. List files matching pattern: "customers*.csv"
4. Filter out .ok files
5. Sort by split number (if applicable)

Output: [
    "gs://landing-bucket/em/customers/customers_1.csv",
    "gs://landing-bucket/em/customers/customers_2.csv"
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
│ STAGE 3: ODP LOAD TO BIGQUERY                               │
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
│  │  │ (ODP)      │  e.g., odp_em.customers              │   │
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
aa
│
└── odp_loa                         # LOA system ODP dataset
    ├── applications                # 1:1 mapping of LOA tables
    └── ...
```

#### ODP Table Schema Pattern

Each ODP table follows this schema pattern:

```sql
-- Example: odp_em.customers

CREATE TABLE odp_em.customers (
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
| `_run_id` | STRING | Unique pipeline execution ID | `em_customers_20260101_160500` |
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
│  │  Source: gs://landing-bucket/em/customers/           │   │
│  │    ├── customers_1.csv                               │   │
│  │    ├── customers_2.csv                               │   │
│  │    └── customers.csv.ok                              │   │
│  │                                                      │   │
│  │              │                                       │   │
│  │              ▼ (Move on failure)                     │   │
│  │                                                      │   │
│  │  Error: gs://error-bucket/em/customers/2026/01/01/   │   │
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
├── em/
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
└── loa/
    └── ...
```

#### Error Report JSON Structure

```json
{
  "run_id": "em_customers_20260101_160500",
  "system_id": "em",
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
  "source_path": "gs://landing-bucket/em/customers/",
  "error_path": "gs://error-bucket/em/customers/2026/01/01/"
}
```

#### Job Status Table Schema

```sql
-- Table: job_control.pipeline_jobs

CREATE TABLE job_control.pipeline_jobs (
    run_id              STRING NOT NULL,        -- Unique run identifier
    system_id           STRING NOT NULL,        -- EM, LOA
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
        # Build error path: gs://error-bucket/em/customers/2026/01/01/
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
│    gs://landing-bucket/em/customers/                        │
│    ├── customers_1.csv                                      │
│    ├── customers_2.csv                                      │
│    └── customers.csv.ok                                     │
│                                                             │
│                         │                                   │
│                         ▼ (Move on success)                 │
│                                                             │
│  Archive Location:                                          │
│    gs://archive-bucket/em/customers/2026/01/01/             │
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
├── em/
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
└── loa/
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
          "matchesPrefix": ["em/", "loa/"]
        }
      },
      {
        "action": {
          "type": "SetStorageClass",
          "storageClass": "NEARLINE"
        },
        "condition": {
          "age": 1,
          "matchesPrefix": ["em/", "loa/"]
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
        # Parse: gs://landing-bucket/em/customers/customers_1.csv
        # Build: gs://archive-bucket/em/customers/2026/01/01/customers_1.csv
        
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
    "input_files": ["gs://landing-bucket/em/customers/*.csv"],
    "skip_header_lines": 1,  # Skip HDR record
    
    # Output
    "output_table": "{project}:odp_em.customers",
    "write_disposition": "WRITE_APPEND",
    
    # Audit
    "run_id": "{run_id}",
    "extract_date": "{extract_date}"
}
```

---

### Stage 4: Transformation (dbt)

#### Entity Dependency Logic

The next stage of processing (Transformation) can **only be triggered when ALL entity extracts for a system are successfully loaded to ODP**. For EM, this means all 3 entities must complete:

```
┌─────────────────────────────────────────────────────────────┐
│ EM ENTITY DEPENDENCY CHECK                                  │
│                                                             │
│  Required Entities for EM System:                           │
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
│  │   │ odp_em.     │         │ odp_em.     │           │   │
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
│  │   │ odp_em.     │                                    │   │
│  │   │ decision    │                                    │   │
│  │   └──────┬──────┘                                    │   │
│  │          │                                           │   │
│  │          ▼                                           │   │
│  │   ┌─────────────────────────────────────────────┐   │   │
│  │   │ ALL 3 ENTITIES LOADED FOR EXTRACT DATE?     │   │   │
│  │   │                                             │   │   │
│  │   │  Check job_control.pipeline_jobs:           │   │   │
│  │   │    - system_id = 'em'                       │   │   │
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

# Example: Blueprint pipeline configuration (deployments/em/src/em/config.py)
EM_ENTITY_DEPENDENCIES = {
    "entities": ["customers", "accounts", "decision"],
    "required_count": 3,
    "trigger_next_stage": "transformation"
}

# Example: Blueprint pipeline configuration (deployments/loa/src/loa/config.py)
LOA_ENTITY_DEPENDENCIES = {
    "entities": ["applications"],
    "required_count": 1,  # Single entity - immediate trigger
    "trigger_next_stage": "transformation"
}

# Usage in DAG (pipeline code, not library)
from gcp_pipeline_builder.orchestration import EntityDependencyChecker

checker = EntityDependencyChecker(
    project_id="my-project",
    dependencies=EM_ENTITY_DEPENDENCIES  # Pipeline provides config
)

if checker.all_entities_loaded("em", extract_date):
    trigger_transformation_dag()
```

#### Dependency Check Table

| System | Required Entities | All Required? | Trigger Condition |
|--------|-------------------|---------------|-------------------|
| **EM** | Customers, Accounts, Decision | Yes, all 3 | All 3 SUCCESS for same extract_date |
| **LOA** | Applications | No (single entity) | Immediate after ODP load SUCCESS |

#### Dependency Check Query

```sql
-- Check if all EM entities are loaded for a given extract date

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
    system_id = 'em'
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
        system_id: System identifier (em, loa)
        extract_date: Extract date to check
    
    Returns:
        True if all entities loaded, False otherwise
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
        # All entities loaded - trigger transformation DAG
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
        # Still waiting for other entities
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
    system_id           STRING NOT NULL,
    extract_date        DATE NOT NULL,
    entity_type         STRING NOT NULL,
    status              STRING NOT NULL,        -- SUCCESS, FAILED, PENDING
    run_id              STRING,
    loaded_at           TIMESTAMP,
    record_count        INT64,
    
    PRIMARY KEY (system_id, extract_date, entity_type) NOT ENFORCED
)
PARTITION BY extract_date;

-- View: Ready for transformation
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
    (system_id = 'em' AND COUNT(*) = 3)
    OR (system_id = 'loa' AND COUNT(*) = ...)  -- Define LOA count
;
```

---

### Stage 4: dbt Transformation (Foundation Data Product)

Once all 3 EM entities (customers, accounts, decision) are loaded to ODP, the dbt transformation is triggered to create the **Foundation Data Product (FDP)**.

#### Foundation Data Product: EMAttributes

The **EMAttributes** FDP is created by joining and transforming data from all 3 ODP tables using an **Attribute Mapping File**.

```
┌─────────────────────────────────────────────────────────────┐
│ STAGE 4: DBT TRANSFORMATION                                 │
│                                                             │
│  Input: ODP Tables (Raw 1:1 Mainframe Data)                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ odp_em.     │  │ odp_em.     │  │ odp_em.     │         │
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
│  │  dbt run --select fdp_em.em_attributes               │   │
│  │                                                      │   │
│  │  Transformations Applied:                            │   │
│  │    1. Join customers + accounts + decision           │   │
│  │    2. Apply attribute mappings                       │   │
│  │    3. Transform data types                           │   │
│  │    4. Calculate derived fields                       │   │
│  │    5. Apply business rules                           │   │
│  │    6. Add audit columns                              │   │
│  │                                                      │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                   │
│                         ▼                                   │
│  Output: Foundation Data Product                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ fdp_em.em_attributes                                 │   │
│  │ ────────────────────                                 │   │
│  │                                                      │   │
│  │  Consolidated, transformed, business-ready data      │   │
│  │  from all 3 source entities                          │   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### Data Product Layers

```
BigQuery Project: {project_id}
│
├── odp_em                          # ODP: Original Data Product (Raw)
│   ├── customers                   # 1:1 mapping of EM.CUSTOMERS
│   ├── accounts                    # 1:1 mapping of EM.ACCOUNTS
│   └── decision                    # 1:1 mapping of EM.DECISION
│
├── fdp_em                          # FDP: Foundation Data Product (Transformed)
│   └── em_attributes               # Consolidated EMAttributes table
│
└── odp_loa                         # LOA system (similar pattern)
    └── ...
```

#### Attribute Mapping File

The attribute mapping file defines how ODP columns are transformed into FDP columns.

**Location:** `transformations/dbt/seeds/em_attribute_mapping.csv`

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
    system_id       STRING,
    entity_type     STRING,
    field_name      STRING,
    source_code     STRING,
    target_value    STRING,
    description     STRING,
    effective_date  DATE,
    expiry_date     DATE
);

-- Example data:
INSERT INTO reference.code_mappings VALUES
('em', 'customers', 'status', 'A', 'ACTIVE', 'Active customer', '2020-01-01', NULL),
('em', 'customers', 'status', 'I', 'INACTIVE', 'Inactive customer', '2020-01-01', NULL),
('em', 'customers', 'status', 'C', 'CLOSED', 'Closed account', '2020-01-01', NULL),
('em', 'accounts', 'account_type', 'CHK', 'CHECKING', 'Checking account', '2020-01-01', NULL),
('em', 'accounts', 'account_type', 'SAV', 'SAVINGS', 'Savings account', '2020-01-01', NULL),
('em', 'decision', 'decision_code', 'APP', 'APPROVED', 'Application approved', '2020-01-01', NULL),
('em', 'decision', 'decision_code', 'DEN', 'DENIED', 'Application denied', '2020-01-01', NULL),
('em', 'decision', 'decision_code', 'REV', 'REVIEW', 'Pending review', '2020-01-01', NULL);
```

#### dbt Model: em_attributes

**File:** `transformations/dbt/models/fdp_em/em_attributes.sql`

```sql
{{
    config(
        materialized='incremental',
        unique_key='attribute_key',
        partition_by={
            "field": "_extract_date",
            "data_type": "date"
        },
        cluster_by=['customer_id', 'account_id']
    )
}}

WITH customers AS (
    SELECT * FROM {{ ref('stg_em_customers') }}
    {% if is_incremental() %}
    WHERE _extract_date > (SELECT MAX(_extract_date) FROM {{ this }})
    {% endif %}
),

accounts AS (
    SELECT * FROM {{ ref('stg_em_accounts') }}
    {% if is_incremental() %}
    WHERE _extract_date > (SELECT MAX(_extract_date) FROM {{ this }})
    {% endif %}
),

decision AS (
    SELECT * FROM {{ ref('stg_em_decision') }}
    {% if is_incremental() %}
    WHERE _extract_date > (SELECT MAX(_extract_date) FROM {{ this }})
    {% endif %}
),

-- Join all entities
joined AS (
    SELECT
        -- Generate unique key
        {{ dbt_utils.generate_surrogate_key(['c.customer_id', 'a.account_id', 'd.decision_id']) }} AS attribute_key,
        
        -- Customer attributes
        c.customer_id,
        {{ mask_ssn('c.ssn') }} AS ssn_masked,
        UPPER(c.first_name) AS first_name,
        UPPER(c.last_name) AS last_name,
        c.date_of_birth,
        {{ map_code('em', 'customers', 'status', 'c.status') }} AS customer_status,
        
        -- Account attributes
        a.account_id,
        {{ map_code('em', 'accounts', 'account_type', 'a.account_type') }} AS account_type_desc,
        a.balance AS current_balance,
        a.open_date AS account_open_date,
        
        -- Decision attributes
        d.decision_id,
        {{ map_code('em', 'decision', 'decision_code', 'd.decision_code') }} AS decision_outcome,
        d.decision_date,
        d.decision_reason,
        
        -- Audit columns
        c._run_id,
        c._extract_date,
        CURRENT_TIMESTAMP() AS _transformed_ts
        
    FROM customers c
    LEFT JOIN accounts a ON c.customer_id = a.customer_id
        AND c._extract_date = a._extract_date
    LEFT JOIN decision d ON a.account_id = d.account_id
        AND a._extract_date = d._extract_date
)

SELECT * FROM joined
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

-- Macro: Mask SSN (show last 4 digits)
{% macro mask_ssn(column) %}
    CONCAT('XXX-XX-', RIGHT(REPLACE({{ column }}, '-', ''), 4))
{% endmacro %}

-- Macro: Parse mainframe date (YYYYMMDD to DATE)
{% macro parse_mainframe_date(column) %}
    SAFE.PARSE_DATE('%Y%m%d', {{ column }})
{% endmacro %}
```

#### Stage 4 DAG Tasks

```python
# Transformation DAG: em_transformation_dag

[check_odp_ready]  ──► Verify all 3 ODP tables have data for extract_date
        │
        ▼
[run_dbt_staging]  ──► dbt run --select staging.stg_em_*
        │
        ▼
[run_dbt_fdp]  ──► dbt run --select fdp_em.em_attributes
        │
        ▼
[run_dbt_tests]  ──► dbt test --select fdp_em.em_attributes
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
    system_id               STRING NOT NULL,        -- EM, LOA
    extract_date            DATE NOT NULL,          -- Extract date being processed
    
    -- Transformation details
    transformation_type     STRING NOT NULL,        -- ODP_TO_FDP, FDP_TO_CDP, etc.
    source_dataset          STRING NOT NULL,        -- odp_em
    target_dataset          STRING NOT NULL,        -- fdp_em
    target_table            STRING NOT NULL,        -- em_attributes
    
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
        system_id: System identifier (em, loa)
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
        "target_table": f"{system_id}_attributes",
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
        "dbt_model_name": f"fdp_{system_id}.{system_id}_attributes"
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
    
    # Get source entity counts from ODP
    source_entities = [
        {"entity_name": "customers", "record_count": get_odp_count("customers", extract_date), "odp_run_id": get_odp_run_id("customers", extract_date)},
        {"entity_name": "accounts", "record_count": get_odp_count("accounts", extract_date), "odp_run_id": get_odp_run_id("accounts", extract_date)},
        {"entity_name": "decision", "record_count": get_odp_count("decision", extract_date), "odp_run_id": get_odp_run_id("decision", extract_date)},
    ]
    
    # Get FDP record count
    target_count = get_fdp_count(f"fdp_{system_id}.{system_id}_attributes", extract_date)
    
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
  "audit_id": "audit_em_transform_20260101_170000",
  "run_id": "em_transform_20260101_170000",
  "system_id": "em",
  "extract_date": "2026-01-01",
  "transformation_type": "ODP_TO_FDP",
  "source_dataset": "odp_em",
  "target_dataset": "fdp_em",
  "target_table": "em_attributes",
  "source_entities": [
    {"entity_name": "customers", "record_count": 5000, "odp_run_id": "em_customers_20260101_160500"},
    {"entity_name": "accounts", "record_count": 8500, "odp_run_id": "em_accounts_20260101_160510"},
    {"entity_name": "decision", "record_count": 3200, "odp_run_id": "em_decision_20260101_050500"}
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
  "dbt_model_name": "fdp_em.em_attributes",
  "warnings": [],
  "created_at": "2026-01-01T17:05:31.000Z"
}
```

#### FDP Table Schema: em_attributes

```sql
-- Table: fdp_em.em_attributes

CREATE TABLE fdp_em.em_attributes (
    -- Primary key
    attribute_key       STRING NOT NULL,
    
    -- Customer attributes
    customer_id         STRING NOT NULL,
    ssn_masked          STRING,
    first_name          STRING,
    last_name           STRING,
    date_of_birth       DATE,
    customer_status     STRING,
    
    -- Account attributes
    account_id          STRING,
    account_type_desc   STRING,
    current_balance     NUMERIC,
    account_open_date   DATE,
    
    -- Decision attributes
    decision_id         STRING,
    decision_outcome    STRING,
    decision_date       DATE,
    decision_reason     STRING,
    
    -- Audit columns
    _run_id             STRING,
    _extract_date       DATE,
    _transformed_ts     TIMESTAMP
)
PARTITION BY _extract_date
CLUSTER BY customer_id, account_id;
```

---

## 🔄 STAGE SUMMARY

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
- Apache Beam pipeline reads validated CSV files
- Parses records, skips HDR/TRL
- Adds audit columns (_run_id, _source_file, _processed_ts, _extract_date)
- Loads 1:1 to BigQuery ODP tables
- On success: archive files, update job status
- EM: Wait for all 3 entities before Stage 4
- LOA: Immediate trigger to Stage 4

### Stage 4: FDP Transformation
- dbt transformation using attribute mapping
- Code translations (mainframe codes → business values)
- PII masking applied
- EM: Join 3 ODP tables → 1 FDP table (em_attributes)
- LOA: Split 1 ODP table → 2 FDP tables (event_transaction_excess, portfolio_account_excess)
- Update audit table on completion

---

## 📁 BIGQUERY DATASET STRUCTURE

```
BigQuery Project: {project_id}
│
├── odp_em                              # EM ODP (Original Data Product)
│   ├── customers                       # 1:1 mapping of EM.CUSTOMERS
│   ├── accounts                        # 1:1 mapping of EM.ACCOUNTS
│   └── decision                        # 1:1 mapping of EM.DECISION
│
├── fdp_em                              # EM FDP (Foundation Data Product)
│   └── em_attributes                   # Joined/transformed EM data
│
├── odp_loa                             # LOA ODP (Original Data Product)
│   └── applications                    # 1:1 mapping of LOA.APPLICATIONS
│
├── fdp_loa                             # LOA FDP (Foundation Data Product)
│   ├── event_transaction_excess        # Event/Transaction focused view
│   └── portfolio_account_excess        # Portfolio/Account focused view
│
├── job_control                         # Pipeline control tables
│   ├── pipeline_jobs                   # Job status tracking
│   └── entity_load_status              # Entity load status
│
├── audit                               # Audit tables
│   └── transformation_audit            # Transformation audit log
│
└── reference                           # Reference data
    └── code_mappings                   # Mainframe code translations
```

---

## 📂 GCS BUCKET STRUCTURE

### Bucket Configuration

| Attribute | Value |
|-----------|-------|
| **Bucket Type** | Regional |
| **Encryption at Rest** | Google-managed encryption keys (default) |
| **Transfer Encryption** | TLS 1.2 |
| **Access Control** | IAM-based |

### Bucket Layout

```
gs://landing-bucket/                    # Landing zone (source files)
├── em/
│   ├── customers/
│   ├── accounts/
│   └── decision/
└── loa/
    └── applications/

gs://archive-bucket/                    # Archive (3-month retention)
├── em/{entity}/{YYYY}/{MM}/{DD}/
└── loa/{entity}/{YYYY}/{MM}/{DD}/

gs://error-bucket/                      # Error files (quarantine)
├── em/{entity}/{YYYY}/{MM}/{DD}/
│   └── error_report.json
└── loa/{entity}/{YYYY}/{MM}/{DD}/
    └── error_report.json
```

---

## ✅ IMPLEMENTATION PHASES

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Requirements Gathering | ✅ COMPLETE |
| 2 | File Ingestion & Validation | 🏗️ IN PROGRESS |
| 3 | Beam Pipeline Processing (ODP Load) | 🏗️ IN PROGRESS |
| 4 | dbt Transformations (FDP) | 🏗️ IN PROGRESS |
| 5 | Reconciliation & Audit | 🏗️ IN PROGRESS |
| 6 | Monitoring & Alerting | ✅ COMPLETE |

---

## 📎 APPENDIX

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
| `BQ_LOAD_FAILED` | ODP Load | BigQuery load failed |

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
| `_transformed_ts` | TIMESTAMP | When record was transformed (FDP only) |

---

**Document Complete.**

