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
                    Used by: application1-transformation, application2-transformation
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
                  │     • JOINs (Application1: 2→1)             │
                  │     • MAPs (Application2: 1→1)             │
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
    entity_name="customers",
    system_id="Application1",
    fields=[
        SchemaField(name="customer_id", field_type="STRING", required=True),
        SchemaField(name="ssn", field_type="STRING", is_pii=True),
        SchemaField(name="dob", field_type="DATE", is_pii=True),
    ],
    primary_key=["customer_id"]
)
```

---

## Key Findings

### 1. Standardized Audit Macros
- **`add_audit_columns()`**: Ensures consistent lineage tracking across all models by adding `run_id`, `processed_timestamp`, and `source_file`.
- **`apply_audit_columns()`**: Utility to retroactively add audit columns to existing tables.

### 2. Metadata-Driven PII Masking
- **Generic Masking Engine**: Focuses on the *shape* of masking rather than the *type* of data.
- **Core Strategies**:
    - `mask_full()`: Complete masking based on field length.
    - `mask_partial_last4()`: Preserves utility (last 4) while protecting privacy.
    - `mask_redacted()`: Replaces sensitive values with a constant "REDACTED" label.
- **Metadata-Powered**: Selection is driven by `pii_type` in the schema metadata (e.g., `pii_type: PARTIAL`), ensuring the library doesn't make blind assumptions about data content.
- **Environment-Aware**: Automatically adjusts depth (Full vs. Partial vs. None) based on the target environment (Prod vs. Staging vs. Dev).

### 3. Configurable Data Enrichment
- **Generic Macro**: `apply_enrichment(rules)`
- **Rule Types**:
    - `DATE_PARTS`: Automatically extracts year, month, day, and day name.
    - `BUCKET`: Categorizes numeric values into ranges (e.g., credit scores).
    - `LOOKUP`: Maps legacy codes to human-readable statuses.
    - `EXPRESSION`: Applies custom SQL expressions for complex logic.
- **Config-Driven**: Enrichment is defined via metadata, keeping the library code generic and reusable across systems.

### 4. Data Safety & Validation
- **`validate_no_pii_in_export`**: Safety macro that checks for unmasked PII patterns before data export, preventing accidental exposure of sensitive information.

---

## Governance & Compliance

- **SQL Only**: This library is strictly for dbt/SQL logic. **NO** Python dependencies (Beam/Airflow) allowed.
- **Consistency**: All transformation models must use `add_audit_columns()` to maintain data lineage.
- **Privacy**: High-risk PII fields (SSN, etc.) MUST be masked using the provided macros in all non-production exports.

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
name: 'application1_transformation'

# Reference shared macros
packages:
  - local: ../../gcp-pipeline-libraries/gcp-pipeline-transform/dbt_shared
```

Or copy macros to your project:

```bash
cp -r gcp-pipeline-libraries/gcp-pipeline-transform/dbt_shared/macros \
      deployments/application1-transformation/dbt/macros/shared/
```

---

## Run Tests

Run dbt macro unit tests:

```bash
cd gcp-pipeline-libraries/gcp-pipeline-transform
pytest tests/unit/test_pii_macros.py
```

These tests verify the compiled SQL of the dbt macros using a mock dbt project.

