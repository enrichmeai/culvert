# Blueprint Implementation Prompt - EM and LOA Pipelines

**Ticket ID:** BLUEPRINT-IMPL-001  
**Status:** Ready for Implementation  
**Priority:** P1 - Critical  
**Created:** January 2, 2026  
**Prerequisites:** Library gaps completed (LIBRARY-FIX-001)

---

## 📋 OBJECTIVE

Implement two complete data migration pipelines (EM and LOA) in the existing `blueprint/` structure using the `gdw_data_core` library.

---

## 📊 SYSTEM REQUIREMENTS SUMMARY

### EM System

| Attribute | Value |
|-----------|-------|
| **System ID** | EM |
| **Description** | Application A |
| **Source Entities** | 3 (Customers, Accounts, Decision) |
| **Extract Schedule** | Customers/Accounts: 4 PM, Decision: 5 AM |
| **ODP Tables** | 3 (`odp_em.customers`, `odp_em.accounts`, `odp_em.decision`) |
| **FDP Tables** | 1 (`fdp_em.em_attributes`) |
| **Transformation** | JOIN 3 sources → 1 target |
| **Dependency** | Wait for all 3 entities before FDP transformation |

### LOA System

| Attribute | Value |
|-----------|-------|
| **System ID** | LOA |
| **Description** | Application B Application |
| **Source Entities** | 1 (Applications) |
| **Extract Schedule** | Daily (TBD) |
| **ODP Tables** | 1 (`odp_loa.applications`) |
| **FDP Tables** | 2 (`fdp_loa.event_transaction_excess`, `fdp_loa.portfolio_account_excess`) |
| **Transformation** | SPLIT 1 source → 2 targets |
| **Dependency** | No wait - immediate trigger after ODP load |

---

## 📥 INPUT SPECIFICATIONS

### File Format (Both Systems)

```
HDR|{SYSTEM}|{ENTITY}|{YYYYMMDD}     ← Header record
{csv_header_row}                      ← Column names
{data_row_1}                          ← Data records
{data_row_2}
...
TRL|RecordCount={n}|Checksum={hash}   ← Trailer record
```

### File Landing Structure

```
gs://landing-bucket/
├── em/
│   ├── customers/
│   │   ├── em_customers_20260102.csv
│   │   └── em_customers_20260102.ok      ← Trigger
│   ├── accounts/
│   │   ├── em_accounts_20260102.csv
│   │   └── em_accounts_20260102.ok       ← Trigger
│   └── decision/
│       ├── em_decision_20260102.csv
│       └── em_decision_20260102.ok       ← Trigger
└── loa/
    └── applications/
        ├── loa_applications_20260102.csv
        └── loa_applications_20260102.ok  ← Trigger
```

### EM Entity Schemas

#### EM Customers (Input CSV)
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| customer_id | STRING | Yes | Primary key |
| first_name | STRING | Yes | First name |
| last_name | STRING | Yes | Last name |
| ssn | STRING | Yes | Social Security Number (PII) |
| dob | DATE | Yes | Date of birth (PII) |
| status | STRING | No | A=Active, I=Inactive, C=Closed |
| created_date | DATE | No | Customer creation date |

#### EM Accounts (Input CSV)
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| account_id | STRING | Yes | Primary key |
| customer_id | STRING | Yes | Foreign key to customers |
| account_type | STRING | No | CHECKING, SAVINGS, MONEY_MARKET, CD, IRA |
| balance | NUMERIC | No | Current balance |
| status | STRING | No | A=Active, I=Inactive, C=Closed |
| open_date | DATE | No | Account open date |

#### EM Decision (Input CSV)
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| decision_id | STRING | Yes | Primary key |
| customer_id | STRING | Yes | Foreign key to customers |
| application_id | STRING | No | Related application |
| decision_code | STRING | Yes | APPROVE, DECLINE, REVIEW, PENDING |
| decision_date | TIMESTAMP | Yes | When decision was made |
| score | INTEGER | No | Credit score (300-850) |
| reason_codes | STRING | No | Pipe-separated reason codes |

### LOA Entity Schema

#### LOA Applications (Input CSV)
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| application_id | STRING | Yes | Primary key |
| customer_id | STRING | Yes | Foreign key |
| product_type | STRING | Yes | MORTGAGE, AUTO, PERSONAL, CREDIT_CARD |
| amount | NUMERIC | Yes | Loan amount |
| term_months | INTEGER | Yes | Loan term in months |
| rate | NUMERIC | No | Interest rate |
| status | STRING | Yes | PENDING, APPROVED, DECLINED, WITHDRAWN |
| created_date | DATE | Yes | Application date |

---

## 📤 OUTPUT SPECIFICATIONS

### ODP Layer (1:1 Mapping)

All ODP tables include audit columns:
- `_run_id` - Pipeline run identifier
- `_source_file` - Source file path
- `_processed_at` - Processing timestamp

#### odp_em.customers
Same as input schema + audit columns. Partitioned by `created_date`.

#### odp_em.accounts
Same as input schema + audit columns. Partitioned by `open_date`.

#### odp_em.decision
Same as input schema + audit columns. Partitioned by `decision_date`.

#### odp_loa.applications
Same as input schema + audit columns. Partitioned by `created_date`.

### FDP Layer (Transformed)

#### fdp_em.em_attributes (JOIN of 3 sources)

```sql
CREATE TABLE fdp_em.em_attributes (
    -- Primary key
    attribute_key       STRING NOT NULL,
    
    -- Customer attributes
    customer_id         STRING NOT NULL,
    ssn_masked          STRING,          -- Masked SSN (PII)
    first_name          STRING,
    last_name           STRING,
    date_of_birth       DATE,
    customer_status     STRING,
    
    -- Account attributes
    account_id          STRING,
    account_type_desc   STRING,          -- Mapped from code
    current_balance     NUMERIC,
    account_open_date   DATE,
    
    -- Decision attributes
    decision_id         STRING,
    decision_outcome    STRING,          -- Mapped from code
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

#### fdp_loa.event_transaction_excess (SPLIT target 1)

```sql
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

#### fdp_loa.portfolio_account_excess (SPLIT target 2)

```sql
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

---

## 🔒 CONSTRAINTS & RULES

### File Validation
1. **HDR must be first line** - Format: `HDR|{SYSTEM}|{ENTITY}|{YYYYMMDD}`
2. **TRL must be last line** - Format: `TRL|RecordCount={n}|Checksum={hash}`
3. **Record count must match** - TRL count must equal actual data rows
4. **Checksum must validate** - MD5 of data rows must match TRL checksum
5. **No HDR/TRL in middle** - Only at start/end of file

### Data Quality
1. **Required fields** - Must not be null
2. **Primary keys** - Must be unique
3. **Foreign keys** - Should reference valid parent records
4. **Data types** - Must match schema
5. **Code values** - Must be in allowed list

### EM Dependency Rule
```
TRIGGER FDP TRANSFORMATION ONLY WHEN:
  odp_em.customers   has data for extract_date AND
  odp_em.accounts    has data for extract_date AND
  odp_em.decision    has data for extract_date
```

### LOA Dependency Rule
```
TRIGGER FDP TRANSFORMATION IMMEDIATELY AFTER:
  odp_loa.applications has data for extract_date
```

### Job Control
1. **Create job record** - Before processing starts
2. **Update status** - PENDING → RUNNING → SUCCESS/FAILED
3. **Track metrics** - Record count, duration, errors
4. **On failure** - Record error details, failure stage

---

## 🔄 PROCESSING FLOW

### EM Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ EM PROCESSING FLOW                                                          │
│                                                                             │
│  .ok file arrives (customers/accounts/decision)                            │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STAGE 1: File Validation                                            │   │
│  │  - Parse HDR (extract system, entity, date)                         │   │
│  │  - Parse TRL (extract record count, checksum)                       │   │
│  │  - Validate row types (HDR first, TRL last)                         │   │
│  │  - Validate record count                                            │   │
│  │  - Validate checksum                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STAGE 2: ODP Load (Dataflow)                                        │   │
│  │  - Create job_control record (RUNNING)                              │   │
│  │  - Parse CSV (skip HDR/TRL)                                         │   │
│  │  - Validate records                                                 │   │
│  │  - Add audit columns (_run_id, _source_file, _processed_at)         │   │
│  │  - Write to odp_em.{entity}                                         │   │
│  │  - Write errors to odp_em.{entity}_errors                           │   │
│  │  - Update job_control (SUCCESS/FAILED)                              │   │
│  │  - Archive source file                                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STAGE 3: Dependency Check                                           │   │
│  │  - Check: All 3 entities loaded for extract_date?                   │   │
│  │  - If NO: Wait (other entities still processing)                    │   │
│  │  - If YES: Trigger FDP transformation                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STAGE 4: FDP Transformation (dbt)                                   │   │
│  │  - Run stg_em_customers, stg_em_accounts, stg_em_decision           │   │
│  │  - Run fdp_em.em_attributes (JOIN)                                  │   │
│  │  - Run dbt tests                                                    │   │
│  │  - Update audit/reconciliation                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### LOA Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ LOA PROCESSING FLOW                                                         │
│                                                                             │
│  .ok file arrives (applications)                                           │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STAGE 1: File Validation                                            │   │
│  │  - Parse HDR (extract system, entity, date)                         │   │
│  │  - Parse TRL (extract record count, checksum)                       │   │
│  │  - Validate row types, record count, checksum                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STAGE 2: ODP Load (Dataflow)                                        │   │
│  │  - Create job_control record (RUNNING)                              │   │
│  │  - Parse CSV (skip HDR/TRL)                                         │   │
│  │  - Validate records                                                 │   │
│  │  - Add audit columns                                                │   │
│  │  - Write to odp_loa.applications                                    │   │
│  │  - Write errors to odp_loa.applications_errors                      │   │
│  │  - Update job_control (SUCCESS/FAILED)                              │   │
│  │  - Archive source file                                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼  (No dependency wait - immediate trigger)                          │
│       │                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ STAGE 3: FDP Transformation (dbt)                                   │   │
│  │  - Run stg_loa_applications                                         │   │
│  │  - Run fdp_loa.event_transaction_excess (SPLIT)                     │   │
│  │  - Run fdp_loa.portfolio_account_excess (SPLIT)                     │   │
│  │  - Run dbt tests                                                    │   │
│  │  - Update audit/reconciliation                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🗂️ BLUEPRINT STRUCTURE (Current → Target)

### Current Blueprint Structure
```
blueprint/
├── components/
│   ├── loa_domain/          # LOA schemas & validation
│   ├── loa_pipelines/       # LOA pipeline code
│   ├── orchestration/       # Airflow DAGs, sensors
│   ├── schemas/             # JSON schemas
│   └── tests/
└── transformations/
    └── dbt/
        └── models/
            ├── staging/     # stg_applications, stg_customers, etc.
            └── marts/       # fct_applications_complete (JOIN pattern)
```

### Target Blueprint Structure
```
blueprint/
├── components/
│   ├── em/                       # NEW: EM domain
│   │   ├── __init__.py
│   │   ├── schema.py             # EM schemas
│   │   ├── validation.py         # EM validation
│   │   └── pipeline.py           # EM Dataflow pipeline
│   ├── loa/                      # RENAMED: LOA domain
│   │   ├── __init__.py
│   │   ├── schema.py             # LOA schemas (from loa_domain)
│   │   ├── validation.py         # LOA validation (from loa_domain)
│   │   └── pipeline.py           # LOA Dataflow pipeline
│   ├── orchestration/
│   │   └── airflow/
│   │       ├── dags/
│   │       │   ├── em_daily_load_dag.py    # NEW: EM DAG
│   │       │   └── loa_daily_load_dag.py   # UPDATED: LOA DAG
│   │       └── sensors/
│   ├── schemas/
│   │   ├── em/                   # NEW: EM JSON schemas
│   │   └── loa/                  # RENAMED: LOA JSON schemas
│   └── tests/
└── transformations/
    └── dbt/
        └── models/
            ├── staging/
            │   ├── em/                      # NEW
            │   │   ├── stg_em_customers.sql
            │   │   ├── stg_em_accounts.sql
            │   │   └── stg_em_decision.sql
            │   └── loa/                     # REORGANIZED
            │       └── stg_loa_applications.sql
            └── fdp/                         # NEW: Foundation Data Products
                ├── fdp_em/
                │   └── em_attributes.sql    # JOIN model
                └── fdp_loa/
                    ├── event_transaction_excess.sql    # SPLIT model 1
                    └── portfolio_account_excess.sql    # SPLIT model 2
```

---

## 📚 LIBRARY COMPONENTS TO USE

```python
# File Management (new)
from gdw_data_core.core.file_management import (
    HDRTRLParser,
    HeaderRecord,
    TrailerRecord,
    FileMetadata,
    validate_record_count,
    validate_checksum,
)

# Data Quality (new)
from gdw_data_core.core.data_quality import (
    validate_row_types,
    check_duplicate_keys,
)

# Job Control (new)
from gdw_data_core.core.job_control import (
    JobControlRepository,
    JobStatus,
    FailureStage,
    PipelineJob,
)

# Entity Dependency (new)
from gdw_data_core.orchestration import (
    EntityDependencyChecker,
    SYSTEM_DEPENDENCIES,
)

# Beam Transforms
from gdw_data_core.pipelines.beam.transforms.parsers import ParseCsvLine

# Existing (already in blueprint)
from gdw_data_core.core.validators import validate_ssn, ValidationError
from gdw_data_core.core.error_handling import ErrorHandler, ErrorContext
from gdw_data_core.core.audit import AuditTrail
```

---

## 🔄 DBT TRANSFORMATION CONFIGURATION

### dbt_project.yml Updates

**Current:** `blueprint/transformations/dbt/dbt_project.yml` (LOA only)  
**Update:** Add EM models and FDP layer

```yaml
name: 'gdw_transformations'  # Renamed from loa_transformations
version: '2.0.0'
config-version: 2

profile: 'gdw_migration'  # Renamed from loa_migration

model-paths: ["models"]
macro-paths: ["macros", "../../gdw_data_core/transformations/dbt_shared/macros"]
# ... other paths remain same

models:
  gdw_transformations:
    # EM Staging Models
    staging:
      em:
        +materialized: view
        +schema: stg_em
        +tags: ["staging", "em"]
      loa:
        +materialized: view
        +schema: stg_loa
        +tags: ["staging", "loa"]
    
    # FDP Models (new layer)
    fdp:
      fdp_em:
        +materialized: incremental
        +schema: fdp_em
        +tags: ["fdp", "em"]
        +partition_by:
          field: _extract_date
          data_type: date
        +cluster_by: ["customer_id", "account_id"]
        +incremental_strategy: merge
        +unique_key: attribute_key
      
      fdp_loa:
        +materialized: incremental
        +schema: fdp_loa
        +tags: ["fdp", "loa"]
        +partition_by:
          field: _extract_date
          data_type: date
        +incremental_strategy: merge

vars:
  # EM-specific variables
  em_source_dataset: "odp_em"
  em_staging_dataset: "stg_em"
  em_fdp_dataset: "fdp_em"
  
  # LOA-specific variables
  loa_source_dataset: "odp_loa"
  loa_staging_dataset: "stg_loa"
  loa_fdp_dataset: "fdp_loa"
  
  # Shared variables
  lookback_days: 90
  
  # Data quality thresholds
  quality_completeness_threshold: 95
  quality_uniqueness_threshold: 100
```

### Model Configuration Options

| Config Option | Values | Description | Used For |
|---------------|--------|-------------|----------|
| `materialized` | `view`, `table`, `incremental`, `ephemeral` | How dbt builds the model | Staging=view, FDP=incremental |
| `schema` | string | Target schema/dataset name | `stg_em`, `fdp_loa`, etc. |
| `partition_by` | `{field, data_type}` | BigQuery partitioning | FDP tables by `_extract_date` |
| `cluster_by` | list of columns | BigQuery clustering | Optimize query performance |
| `incremental_strategy` | `merge`, `insert_overwrite`, `append` | How to handle incremental | `merge` for FDP |
| `unique_key` | column name or list | Primary key for merge | `attribute_key`, `event_key` |
| `tags` | list of strings | Model tags for selection | `["fdp", "em"]` |
| `on_schema_change` | `fail`, `ignore`, `sync_all_columns` | Schema drift handling | `fail` recommended |

### FDP Model Config Examples

**EM em_attributes (JOIN):**
```sql
{{
    config(
        materialized='incremental',
        unique_key='attribute_key',
        partition_by={"field": "_extract_date", "data_type": "date"},
        cluster_by=['customer_id', 'account_id'],
        incremental_strategy='merge',
        on_schema_change='fail',
        tags=['fdp', 'em', 'join']
    )
}}
```

**LOA event_transaction_excess (SPLIT):**
```sql
{{
    config(
        materialized='incremental',
        unique_key='event_key',
        partition_by={"field": "_extract_date", "data_type": "date"},
        cluster_by=['application_id', 'event_date'],
        incremental_strategy='merge',
        on_schema_change='fail',
        tags=['fdp', 'loa', 'split']
    )
}}
```

### Available Macros

| Macro | File | Purpose | Usage |
|-------|------|---------|-------|
| `add_audit_columns()` | `audit_columns.sql` | Add standard audit columns | `{{ add_audit_columns() }}` |
| `mask_pii(column, type)` | `pii_masking.sql` | Mask PII data | `{{ mask_pii('ssn', 'ssn') }}` |
| `check_data_quality(table)` | `data_quality_check.sql` | Run quality checks | `{{ check_data_quality('stg_em_customers') }}` |
| `build_merge_statement(...)` | `incremental_strategy.sql` | Build MERGE SQL | For custom incremental |

### PII Masking Types

| Type | Input | Output |
|------|-------|--------|
| `ssn` | `123-45-6789` | `***-**-6789` |
| `email` | `john@email.com` | `j***@***` |
| `phone` | `555-123-4567` | `555-***-4567` |
| `name` | `John Doe` | `J***` |
| `address` | `123 Main St` | `***MASKED***` |

### dbt Run Commands

```bash
# Run all staging models
dbt run --select staging

# Run EM staging only
dbt run --select staging.em

# Run FDP models
dbt run --select fdp

# Run EM FDP (after dependency check)
dbt run --select fdp.fdp_em.em_attributes

# Run LOA FDP (both tables)
dbt run --select fdp.fdp_loa

# Run with tags
dbt run --select tag:em
dbt run --select tag:fdp

# Run tests
dbt test --select fdp_em
dbt test --select fdp_loa

# Full refresh (rebuild entire table)
dbt run --select fdp_em.em_attributes --full-refresh
```

### New dbt Models to Create

```
transformations/dbt/models/
├── staging/
│   ├── em/
│   │   ├── _em_sources.yml          # NEW: EM source definitions
│   │   ├── stg_em_customers.sql     # NEW
│   │   ├── stg_em_accounts.sql      # NEW
│   │   └── stg_em_decision.sql      # NEW
│   └── loa/
│       ├── _loa_sources.yml         # MOVE from staging/loa_sources.yml
│       └── stg_loa_applications.sql # MOVE from staging/stg_applications.sql
└── fdp/
    ├── fdp_em/
    │   ├── _fdp_em_models.yml       # NEW: Model docs & tests
    │   └── em_attributes.sql        # NEW: JOIN model
    └── fdp_loa/
        ├── _fdp_loa_models.yml      # NEW: Model docs & tests
        ├── event_transaction_excess.sql    # NEW: SPLIT model 1
        └── portfolio_account_excess.sql    # NEW: SPLIT model 2
```

---

## ✅ IMPLEMENTATION CHECKLIST

### Phase 1: Restructure Blueprint
- [ ] Create `components/em/` directory
- [ ] Rename `components/loa_domain/` → `components/loa/`
- [ ] Create `components/schemas/em/` and `components/schemas/loa/`
- [ ] Reorganize dbt models into `staging/em/`, `staging/loa/`, `fdp/`

### Phase 2: EM Implementation
- [ ] Create `components/em/schema.py` (customers, accounts, decision)
- [ ] Create `components/em/validation.py`
- [ ] Create `components/em/pipeline.py` (Dataflow)
- [ ] Create `dags/em_daily_load_dag.py`
- [ ] Create `staging/em/stg_em_customers.sql`
- [ ] Create `staging/em/stg_em_accounts.sql`
- [ ] Create `staging/em/stg_em_decision.sql`
- [ ] Create `fdp/fdp_em/em_attributes.sql` (JOIN)
- [ ] Add HDR/TRL parsing with new library
- [ ] Add Job Control integration
- [ ] Add Entity Dependency Check

### Phase 3: LOA Implementation
- [ ] Update `components/loa/schema.py` (applications only)
- [ ] Update `components/loa/validation.py`
- [ ] Create `components/loa/pipeline.py` (Dataflow)
- [ ] Update `dags/loa_daily_load_dag.py`
- [ ] Create `staging/loa/stg_loa_applications.sql`
- [ ] Create `fdp/fdp_loa/event_transaction_excess.sql` (SPLIT)
- [ ] Create `fdp/fdp_loa/portfolio_account_excess.sql` (SPLIT)
- [ ] Add HDR/TRL parsing with new library
- [ ] Add Job Control integration

### Phase 4: Testing
- [ ] Create test data generator
- [ ] Unit tests for EM pipeline
- [ ] Unit tests for LOA pipeline
- [ ] Integration tests
- [ ] dbt tests

### Phase 5: Infrastructure (Terraform)
- [ ] Create/update BigQuery datasets (`odp_em`, `fdp_em`, `odp_loa`, `fdp_loa`, `job_control`)
- [ ] Create ODP tables with schemas
- [ ] Create FDP tables with schemas
- [ ] Create job_control.pipeline_jobs table
- [ ] Create GCS buckets (landing, archive, error)
- [ ] Create Pub/Sub topics and subscriptions
- [ ] Configure IAM permissions

### Phase 6: GitHub Workflows
- [ ] Update `deploy-loa.yml` for new LOA structure
- [ ] Create `deploy-em.yml` for EM pipeline
- [ ] Update paths to match new folder structure
- [ ] Add EM schema deployments
- [ ] Add FDP table deployments

### Phase 7: Documentation Updates
- [ ] Update `blueprint/README.md` (add EM, update for dual-pipeline)
- [ ] Update `.github/copilot-instructions.md` (already done)
- [ ] Update `docs/01-getting-started/GETTING_STARTED.md`
- [ ] Create `docs/01-getting-started/EM_QUICK_START.md`
- [ ] Update `docs/02-architecture/ARCHITECTURE.md` (add EM)
- [ ] Create `docs/02-architecture/EM_VISUAL_ARCHITECTURE.md`
- [ ] Create `docs/02-architecture/SYSTEM_COMPARISON.md`
- [ ] Update `docs/03-implementation/*` (add EM sections)
- [ ] Update `docs/04-deployment/*` (add EM deployment)
- [ ] Update `components/orchestration/README.md`
- [ ] Update `transformations/dbt/README.md`
- [ ] Update `.github/workflows/deploy-loa.yml` (new paths, FDP tables)
- [ ] Create `.github/workflows/deploy-em.yml`

---

## 📄 DOCUMENTATION UPDATES REQUIRED

### Blueprint README.md

**File:** `blueprint/README.md`

**Current:** LOA-only focus  
**Update to:** EM and LOA dual-pipeline focus

**Changes needed:**
1. Update title: "LOA Blueprint" → "EM & LOA Blueprint"
2. Update description to include both systems
3. Add EM pipeline features
4. Update requirements mapping table for both systems
5. Update component references

### Blueprint Docs to Update

| File | Current | Update To |
|------|---------|-----------|
| `docs/01-getting-started/GETTING_STARTED.md` | LOA only | EM and LOA |
| `docs/01-getting-started/LOA_QUICK_START.md` | LOA only | Rename or add EM version |
| `docs/02-architecture/ARCHITECTURE.md` | LOA only | Add EM architecture |
| `docs/02-architecture/BLUEPRINT_PROJECT_SUMMARY.md` | LOA only | Both systems |
| `docs/02-architecture/LOA_VISUAL_ARCHITECTURE.md` | LOA only | Add EM diagram |
| `docs/03-implementation/*` | LOA only | Add EM sections |
| `docs/04-deployment/*` | LOA only | Add EM deployment |

### New Documentation to Create

| File | Purpose |
|------|---------|
| `docs/01-getting-started/EM_QUICK_START.md` | EM-specific quick start |
| `docs/02-architecture/EM_VISUAL_ARCHITECTURE.md` | EM architecture diagram |
| `docs/02-architecture/SYSTEM_COMPARISON.md` | EM vs LOA comparison |
| `docs/03-implementation/EM_IMPLEMENTATION.md` | EM implementation guide |
| `docs/04-deployment/EM_DEPLOYMENT.md` | EM deployment guide |

### Component READMEs to Update

| File | Update |
|------|--------|
| `components/orchestration/README.md` | Add EM DAG references |
| `components/loa_domain/README.md` | Rename folder, update for both |
| `transformations/dbt/README.md` | Add EM models, FDP section |

### Workflow Updates

**File:** `.github/workflows/deploy-loa.yml`

**Changes needed:**
```yaml
# Update paths
paths:
  - 'blueprint/components/loa/**'           # was: loa_common, loa_pipelines
  - 'blueprint/components/schemas/loa/**'   # was: schemas/

# Update dataset
${{ secrets.GCP_PROJECT_ID_DEV }}:odp_loa   # was: loa_dev

# Add FDP tables
odp_loa.applications
fdp_loa.event_transaction_excess
fdp_loa.portfolio_account_excess
```

**New file:** `.github/workflows/deploy-em.yml` (template provided above)

---

## 🔧 GITHUB WORKFLOWS

### Existing: `.github/workflows/deploy-loa.yml`

**Current paths (need update):**
```yaml
paths:
  - 'blueprint/components/loa_common/**'    # → blueprint/components/loa/**
  - 'blueprint/components/loa_pipelines/**' # → blueprint/components/loa/**
  - 'blueprint/components/schemas/**'       # → blueprint/components/schemas/loa/**
```

**Current tables (need update for FDP):**
- `applications_raw` → `odp_loa.applications`
- `applications_errors` → `odp_loa.applications_errors`
- ADD: `fdp_loa.event_transaction_excess`
- ADD: `fdp_loa.portfolio_account_excess`

### New: `.github/workflows/deploy-em.yml`

```yaml
name: Deploy EM to GCP (DEV)

on:
  push:
    branches:
      - main
      - develop
    paths:
      - 'blueprint/components/em/**'
      - 'blueprint/components/schemas/em/**'
      - '.github/workflows/deploy-em.yml'
  workflow_dispatch:

env:
  PYTHON_VERSION: '3.10'
  REGION: 'europe-west2'

jobs:
  validate:
    name: Validate Code
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ./gdw_data_core
          pip install -e ./blueprint
          pip install pytest flake8 black

      - name: Lint code
        run: |
          black --check blueprint/components/em/ || true
          flake8 blueprint/components/em/ --count --select=E9,F63,F7,F82 --show-source --statistics

      - name: Run tests
        run: |
          pytest blueprint/components/tests/em/ -v --tb=short || echo "Tests not yet implemented"

  deploy-dev:
    name: Deploy to Dev
    runs-on: ubuntu-latest
    needs: validate
    environment: dev
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ./gdw_data_core
          pip install -e ./blueprint
          pip install google-cloud-bigquery google-cloud-storage apache-beam[gcp]

      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY_DEV }}

      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v2
        with:
          project_id: ${{ secrets.GCP_PROJECT_ID_DEV }}

      - name: Create BigQuery datasets if not exists
        run: |
          # ODP dataset
          bq mk --dataset --location=${{ env.REGION }} \
            ${{ secrets.GCP_PROJECT_ID_DEV }}:odp_em || echo "Dataset odp_em already exists"
          
          # FDP dataset
          bq mk --dataset --location=${{ env.REGION }} \
            ${{ secrets.GCP_PROJECT_ID_DEV }}:fdp_em || echo "Dataset fdp_em already exists"
          
          # Job control dataset
          bq mk --dataset --location=${{ env.REGION }} \
            ${{ secrets.GCP_PROJECT_ID_DEV }}:job_control || echo "Dataset job_control already exists"

      - name: Update BigQuery ODP tables
        run: |
          # EM Customers
          bq mk --table \
            --schema=blueprint/components/schemas/em/customers_raw.json \
            --time_partitioning_field=created_date \
            --clustering_fields=_run_id,status \
            ${{ secrets.GCP_PROJECT_ID_DEV }}:odp_em.customers || \
          bq update \
            --schema=blueprint/components/schemas/em/customers_raw.json \
            ${{ secrets.GCP_PROJECT_ID_DEV }}:odp_em.customers

          # EM Accounts
          bq mk --table \
            --schema=blueprint/components/schemas/em/accounts_raw.json \
            --time_partitioning_field=open_date \
            --clustering_fields=_run_id,account_type \
            ${{ secrets.GCP_PROJECT_ID_DEV }}:odp_em.accounts || \
          bq update \
            --schema=blueprint/components/schemas/em/accounts_raw.json \
            ${{ secrets.GCP_PROJECT_ID_DEV }}:odp_em.accounts

          # EM Decision
          bq mk --table \
            --schema=blueprint/components/schemas/em/decision_raw.json \
            --time_partitioning_field=decision_date \
            --clustering_fields=_run_id,decision_code \
            ${{ secrets.GCP_PROJECT_ID_DEV }}:odp_em.decision || \
          bq update \
            --schema=blueprint/components/schemas/em/decision_raw.json \
            ${{ secrets.GCP_PROJECT_ID_DEV }}:odp_em.decision

      - name: Deploy Dataflow template
        run: |
          python blueprint/components/em/pipeline.py \
            --project=${{ secrets.GCP_PROJECT_ID_DEV }} \
            --region=${{ env.REGION }} \
            --runner=DataflowRunner \
            --staging_location=gs://${{ secrets.GCS_BUCKET_DEV }}/staging \
            --temp_location=gs://${{ secrets.GCS_BUCKET_DEV }}/temp \
            --template_location=gs://${{ secrets.GCS_BUCKET_DEV }}/templates/em_pipeline_template \
            --setup_file=./blueprint/setup.py \
            --save_main_session

      - name: Deployment summary
        run: |
          echo "✅ EM deployed to DEV environment"
          echo "Project: ${{ secrets.GCP_PROJECT_ID_DEV }}"
          echo "Region: ${{ env.REGION }}"
          echo "Datasets: odp_em, fdp_em"
```

---

## 🏗️ INFRASTRUCTURE (BigQuery)

### Datasets Required

| Dataset | Purpose | Tables |
|---------|---------|--------|
| `odp_em` | EM Original Data Product | customers, accounts, decision, *_errors |
| `fdp_em` | EM Foundation Data Product | em_attributes |
| `odp_loa` | LOA Original Data Product | applications, applications_errors |
| `fdp_loa` | LOA Foundation Data Product | event_transaction_excess, portfolio_account_excess |
| `job_control` | Pipeline job tracking | pipeline_jobs |

### JSON Schema Files Required

```
blueprint/components/schemas/
├── em/
│   ├── customers_raw.json
│   ├── customers_errors.json
│   ├── accounts_raw.json
│   ├── accounts_errors.json
│   ├── decision_raw.json
│   └── decision_errors.json
├── loa/
│   ├── applications_raw.json
│   └── applications_errors.json
└── job_control/
    └── pipeline_jobs.json
```

### GCS Bucket Structure

```
gs://{project}-landing-{env}/
├── em/
│   ├── customers/
│   ├── accounts/
│   └── decision/
└── loa/
    └── applications/

gs://{project}-archive-{env}/
├── em/
└── loa/

gs://{project}-error-{env}/
├── em/
└── loa/
```

### Pub/Sub Topics

| Topic | Subscription | Purpose |
|-------|--------------|---------|
| `em-file-notifications` | `em-file-notifications-sub` | EM .ok file triggers |
| `loa-file-notifications` | `loa-file-notifications-sub` | LOA .ok file triggers |

---

## 📝 NOTES
- Use new library components (HDR/TRL, Job Control, Dependency Check)
- EM has 3 entities with dependency wait
- LOA has 1 entity with immediate FDP trigger
- EM FDP is a JOIN (3→1)
- LOA FDP is a SPLIT (1→2)

