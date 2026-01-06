# gcp-pipeline-transform

SQL library - dbt macros for audit columns and PII masking.

**NO Apache Beam or Airflow dependencies.**

---

## Architecture

```
                      GCP-PIPELINE-TRANSFORM
                      ──────────────────────

  ┌─────────────────────────────────────────────────────────────────┐
  │                     SQL LAYER                                    │
  │                                                                  │
  │  ┌─────────────────────────────────────────────────────────┐    │
  │  │                   dbt Macros                             │    │
  │  │                                                          │    │
  │  │  ┌─────────────────┐    ┌─────────────────┐             │    │
  │  │  │ Audit Columns   │    │  PII Masking    │             │    │
  │  │  │                 │    │                 │             │    │
  │  │  │ • _run_id       │    │ • SSN masking   │             │    │
  │  │  │ • _source_file  │    │ • DOB masking   │             │    │
  │  │  │ • _processed_at │    │ • Configurable  │             │    │
  │  │  │ • _transformed  │    │                 │             │    │
  │  │  └─────────────────┘    └─────────────────┘             │    │
  │  │                                                          │    │
  │  └─────────────────────────────────────────────────────────┘    │
  │                              │                                   │
  │                              ▼                                   │
  │  ┌─────────────────────────────────────────────────────────┐    │
  │  │                   SQL Templates                          │    │
  │  │                                                          │    │
  │  │  • Staging models (clean raw data)                      │    │
  │  │  • FDP models (business transformations)                │    │
  │  │  • Quality checks (dbt tests)                           │    │
  │  │                                                          │    │
  │  └─────────────────────────────────────────────────────────┘    │
  │                                                                  │
  └─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    Used by: em-transformation, loa-transformation
```

---

## Transformation Flow

```
  BigQuery ODP                   dbt                      BigQuery FDP
  ────────────                   ───                      ────────────

  Raw tables      ┌───────────────────────────────────┐
  (from Beam)     │                                   │
       │          │  1. Staging Models                │
       └─────────►│     {{ source('odp', 'table') }}  │
                  │     • Clean data types            │
                  │     • Apply naming conventions    │
                  │                                   │
                  │  2. Add Audit Columns             │
                  │     {{ add_audit_columns() }}     │
                  │     • _run_id                     │
                  │     • _transformed_at             │
                  │                                   │
                  │  3. Apply PII Masking             │────► FDP Tables
                  │     {{ mask_ssn(column) }}        │
                  │     {{ mask_dob(column) }}        │
                  │                                   │
                  │  4. Business Logic                │
                  │     • JOINs (EM: 3→1)             │
                  │     • SPLITs (LOA: 1→2)           │
                  │                                   │
                  └───────────────────────────────────┘
```

---

## Macros

### add_audit_columns

Adds standard audit columns to every FDP table.

```sql
-- Usage in dbt model
SELECT
    customer_id,
    first_name,
    last_name,
    {{ add_audit_columns() }}
FROM {{ ref('stg_customers') }}

-- Output columns added:
--   _run_id STRING
--   _source_file STRING
--   _processed_at TIMESTAMP
--   _transformed_at TIMESTAMP (current time)
```

### mask_ssn

Masks Social Security Numbers for PII compliance.

```sql
-- Usage
SELECT
    customer_id,
    {{ mask_ssn('ssn') }} as ssn_masked
FROM {{ ref('stg_customers') }}

-- Input:  123-45-6789
-- Output: XXX-XX-6789
```

### mask_dob

Masks date of birth for PII compliance.

```sql
-- Usage
SELECT
    customer_id,
    {{ mask_dob('date_of_birth') }} as dob_masked
FROM {{ ref('stg_customers') }}

-- Input:  1990-05-15
-- Output: 1990-01-01 (only year preserved)
```

---

## PII Masking Configuration

PII masking is configurable per schema. Define which fields to mask in the entity schema:

```python
# In deployment schema definition
from gcp_pipeline_core.schema import EntitySchema, SchemaField

CustomerSchema = EntitySchema(
    name="customers",
    fields=[
        SchemaField(name="customer_id", field_type="STRING", required=True),
        SchemaField(name="ssn", field_type="STRING", pii=True, pii_type="SSN"),
        SchemaField(name="dob", field_type="DATE", pii=True, pii_type="DOB"),
    ]
)
```

---

## Directory Structure

```
gcp-pipeline-transform/
└── dbt_shared/
    ├── macros/
    │   ├── audit_columns.sql      # add_audit_columns()
    │   ├── pii_masking.sql        # mask_ssn(), mask_dob()
    │   └── quality_checks.sql     # row_count_check(), etc.
    └── templates/
        ├── staging_model.sql      # Template for staging
        └── fdp_model.sql          # Template for FDP
```

---

## Usage in Deployment

Reference in your deployment's dbt project:

```yaml
# dbt_project.yml
name: 'em_transformation'

# Reference shared macros
packages:
  - local: ../../libraries/gcp-pipeline-transform/dbt_shared
```

Or copy macros to your project:

```bash
cp -r libraries/gcp-pipeline-transform/dbt_shared/macros \
      deployments/em-transformation/dbt/macros/shared/
```

---

## Run dbt

```bash
cd deployments/em-transformation/dbt
dbt run --profiles-dir .
```

