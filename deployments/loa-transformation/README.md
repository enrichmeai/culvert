# LOA Transformation

**Unit 2 of LOA 3-Unit Deployment**

FDP Transformation - dbt models for ODP → FDP transformation.

---

## Flow Diagram

```
                         LOA TRANSFORMATION FLOW
                         ───────────────────────

  BigQuery ODP                    dbt                      BigQuery FDP
  ────────────                    ───                      ────────────

                             ┌─────────────────┐
                             │  SPLIT Logic    │
                             │                 │
  odp_loa.applications ─────►│  Filter by:     │────┬──► fdp_loa.event_transaction_excess
                             │  - event_type   │    │
                             │  - account_type │    │
                             │                 │    └──► fdp_loa.portfolio_account_excess
                             └─────────────────┘

  1 ODP Source ─────────────────────────────────────────► 2 FDP Targets
```

---

## Pattern

**SPLIT**: 1 ODP source → 2 FDP targets

| Step | Description |
|------|-------------|
| 1 | Staging model cleans and type-casts raw ODP applications data |
| 2 | `add_audit_columns` macro injects `run_id` and `source_file` |
| 3 | FDP model 1 filters by `event_type` for `event_transaction_excess` |
| 4 | FDP model 2 filters by `account_type` for `portfolio_account_excess` |
| 5 | `mask_pii` macro handles sensitive fields in both targets |

---

## Data Mapping

| Source Table | Description |
|--------------|-------------|
| `odp_loa.applications` | All loan applications |

| Target Table | Description |
|--------------|-------------|
| `fdp_loa.event_transaction_excess` | Event-based transactions |
| `fdp_loa.portfolio_account_excess` | Portfolio account records |

---

## Components

| Directory | Purpose |
|-----------|---------|
| `dbt/models/staging/loa/` | Staging models (clean raw data) |
| `dbt/models/fdp/` | FDP models (SPLIT logic) |

---

## Library-Driven Ease of Use

The LOA transformation unit showcases how the `gcp-pipeline-transform` library simplifies system-agnostic transformation:

1.  **Macro Reusability**: Uses `add_audit_columns` and `mask_pii` exactly like EM, proving the library's "Zero-Bleed" and "Generic-First" implementation.
2.  **Schema Alignment**: The staging models align with the `EntitySchema` defined in the ingestion layer, ensuring no type mismatches during the SPLIT transformation.
3.  **Governance**: Leverages the library's `validate_no_pii_in_export` to ensure that even after splitting data into multiple FDPs, no sensitive data is leaked.

---

## How to Replicate this SPLIT Transformation (1-to-2)

To create a new transformation unit that splits a single source, follow the [Creating New Deployment Guide](../../docs/CREATING_NEW_DEPLOYMENT_GUIDE.md).

Key steps for this SPLIT pattern:
1.  **Macro Paths**: Register the library macros in your `dbt_project.yml`.
2.  **Clean Staging**: Create a single staging view for your ODP source.
3.  **FDP Partitioning**: Create multiple FDP models referencing the same staging view. Use `WHERE` clauses to split the data.
4.  **Audit**: Ensure all FDP models use `add_audit_columns` to track their common origin.

---

## Dependencies

| Library | Purpose |
|---------|---------|
| `dbt-bigquery` | dbt adapter for BigQuery |
| `gcp-pipeline-transform` | Shared macros (audit columns) |

---

## Execution & Testing

### 1. Local Development Setup
Initialize the virtual environment:
```bash
./scripts/setup_deployment_venv.sh loa-transformation
source deployments/loa-transformation/venv/bin/activate
```

### 2. Local dbt Execution
Run dbt models locally against the development BigQuery dataset:
```bash
cd dbt
dbt run --profiles-dir . --target dev
```

### 3. Data Quality Validation
Run dbt tests to verify transformation logic and SPLIT pattern:
```bash
dbt test --profiles-dir . --target dev
```

### 4. Governance Verification
Use the library macro to ensure no unmasked PII exists in your models before deployment:
```sql
{{ validate_no_pii_in_export('fdp_loa.event_transaction_excess') }}
```

### 5. Cloud Execution
In production, this unit is triggered by the `loa_odp_load_dag` once ingestion is successful. The transformation is executed via a `BashOperator` running `dbt run`.

---

## SQL Example

```sql
-- fdp_loa.event_transaction_excess
SELECT
    application_id,
    customer_id,
    loan_amount,
    application_date,
    event_type,
    -- Audit columns
    _run_id,
    CURRENT_TIMESTAMP() as _transformed_at
FROM {{ ref('stg_loa_applications') }}
WHERE event_type IS NOT NULL

-- fdp_loa.portfolio_account_excess
SELECT
    application_id,
    customer_id,
    account_type,
    loan_amount,
    interest_rate,
    -- Audit columns
    _run_id,
    CURRENT_TIMESTAMP() as _transformed_at
FROM {{ ref('stg_loa_applications') }}
WHERE account_type IN ('PORTFOLIO', 'EXCESS')
```

