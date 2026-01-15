# EM Transformation

**Unit 2 of EM 3-Unit Deployment**

FDP Transformation - dbt models for ODP → FDP transformation.

---

## Flow Diagram

```
                         EM TRANSFORMATION FLOW
                         ──────────────────────

  BigQuery ODP                    dbt                      BigQuery FDP
  ────────────                    ───                      ────────────

  odp_em.customers ─────┐
                        │    ┌─────────────────┐
  odp_em.accounts  ─────┼───►│   JOIN Logic    │────────► fdp_em.event_transaction_excess
                        │    └─────────────────┘
                        │
  odp_em.decision  ─────┼───────────────────────────────► fdp_em.portfolio_account_excess
                        │
                        └───────────────────────
```

---

## Pattern

**MULTI-TARGET**:
1. **JOIN**: 2 ODP sources (customers, accounts) → 1 FDP target (`event_transaction_excess`)
2. **MAP**: 1 ODP source (decision) → 1 FDP target (`portfolio_account_excess`)

| Step | Description |
|------|-------------|
| 1 | Staging models clean and type-cast raw ODP data |
| 2 | `add_audit_columns` macro injects `run_id` and `source_file` |
| 3 | `mask_pii` macro applies environment-aware masking to sensitive fields |
| 4 | `event_transaction_excess` performs `INNER JOIN` between Customers and Accounts |
| 5 | `portfolio_account_excess` maps Decision ODP 1:1 to FDP |

---

## Data Mapping

| Source Table | Key Fields |
|--------------|------------|
| `odp_em.customers` | customer_id, ssn, name |
| `odp_em.accounts` | account_id, customer_id, balance |
| `odp_em.decision` | decision_id, customer_id, outcome |

| Target Table | Description |
|--------------|-------------|
| `fdp_em.event_transaction_excess` | Joined customer-account view |
| `fdp_em.portfolio_account_excess` | Decision-based portfolio view |

---

## Components

| Directory | Purpose |
|-----------|---------|
| `dbt/models/staging/em/` | Staging models (clean raw data) |
| `dbt/models/fdp/` | FDP models (JOIN and MAP logic) |

---

## Library-Driven Ease of Use

The EM transformation unit uses the `gcp-pipeline-transform` library to ensure data privacy and lineage with zero local macro development:

1.  **Zero-Bleed PII Masking**: Uses `{{ mask_pii(column, 'SSN') }}`. The library automatically applies the correct mask (Full in Prod, Partial in Staging) based on the environment.
2.  **Automated Lineage**: Uses `{{ add_audit_columns() }}` to inject `run_id` and `source_file` variables, maintaining the E2E lineage established in the ingestion layer.
3.  **Metadata Enrichment**: Replaces hardcoded business logic with generic library macros that interpret rules from the `EntitySchema`.

---

## How to Replicate this JOIN Transformation (3-to-1)

To create a new transformation unit that joins multiple entities, follow the [Creating New Deployment Guide](../../docs/CREATING_NEW_DEPLOYMENT_GUIDE.md).

Key steps for this JOIN pattern:
1.  **Register Library**: Point your `dbt_project.yml` to the `gcp-pipeline-transform` macro paths.
2.  **Staging Models**: Create views for your ODP tables. Use `add_audit_columns` for consistency.
3.  **FDP Models**: Implement your `LEFT JOIN` logic. Apply `mask_pii` to all sensitive fields.
4.  **Governance**: Run `validate_no_pii_in_export` in your CI/CD to prevent leakage.

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
./scripts/setup_deployment_venv.sh em-transformation
source deployments/em-transformation/venv/bin/activate
```

### 2. Local dbt Execution
Run dbt models locally against the development BigQuery dataset:
```bash
cd dbt
dbt run --profiles-dir . --target dev
```

### 3. Data Quality Validation
Run dbt tests to verify transformation logic and PII masking:
```bash
dbt test --profiles-dir . --target dev
```

### 4. Governance Verification
Use the library macro to ensure no unmasked PII exists in your models before deployment:
```sql
{{ validate_no_pii_in_export('fdp_em.event_transaction_excess') }}
```

### 5. Cloud Execution
In production, this unit is triggered by the `em_odp_load_dag` once ingestion is successful. The transformation is executed via a `BashOperator` running `dbt run`.

---

## SQL Example

```sql
-- fdp_em.event_transaction_excess
SELECT
    c.customer_id,
    c.first_name,
    c.last_name,
    a.account_id,
    a.current_balance,
    -- Audit columns
    c._run_id,
    CURRENT_TIMESTAMP() as _transformed_at
FROM {{ ref('stg_em_customers') }} c
JOIN {{ ref('stg_em_accounts') }} a 
    ON c.customer_id = a.customer_id
```

