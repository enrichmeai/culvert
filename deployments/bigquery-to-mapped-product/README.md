# Generic Transformation

**Unit 2 of Generic 3-Unit Deployment**

FDP Transformation - dbt models for ODP → FDP transformation.

---

## Flow Diagram

```
                         Generic TRANSFORMATION FLOW
                         ──────────────────────

  BigQuery ODP                    dbt                      BigQuery FDP
  ────────────                    ───                      ────────────

  odp_generic.customers ─────┐
                        │    ┌─────────────────┐
  odp_generic.accounts  ─────┼───►│   JOIN Logic    │────────► fdp_generic.event_transaction_excess
                        │    └─────────────────┘
                        │
  odp_generic.decision  ─────┼───────────────────────────────► fdp_generic.portfolio_account_excess
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
| `odp_generic.customers` | customer_id, ssn, first_name, last_name, dob, status |
| `odp_generic.accounts` | account_id, customer_id, account_type, balance, open_date |
| `odp_generic.decision` | decision_id, customer_id, application_id, decision_code, score, decision_date |

| Target Table | Description |
|--------------|-------------|
| `fdp_generic.event_transaction_excess` | Joined customer-account view |
| `fdp_generic.portfolio_account_excess` | Decision-based portfolio view |

---

## Components

| Directory | Purpose |
|-----------|---------|
| `dbt/models/staging/generic/` | Staging models (clean raw data) |
| `dbt/models/fdp/` | FDP models (JOIN and MAP logic) |

---

## Library-Driven Ease of Use

The Generic transformation unit uses the `gcp-pipeline-transform` library to ensure data privacy and lineage with zero local macro development:

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

## Infrastructure & Configurations

### Google Cloud Resources
This deployment requires the following GCP infrastructure, provisioned via Terraform:
- **Data Warehouse**: BigQuery datasets `odp_generic` (source) and `fdp_generic` (target).
- **Processing**: dbt (running on Cloud Composer or as a standalone process) for executing transformations.

For detailed infrastructure definitions, see [infrastructure/terraform/systems/generic/transformation/](../../infrastructure/terraform/systems/generic/transformation/).

### dbt Configuration (`dbt_project.yml`)
The transformation behavior is controlled by variables and configurations in `dbt_project.yml`:

| Variable | Description | Default / Source |
|----------|-------------|------------------|
| `gcp_project_id` | Target GCP Project | `GCP_PROJECT_ID` env var |
| `source_dataset` | Source ODP dataset | `odp_generic` |
| `staging_dataset` | Intermediate staging dataset | `stg_generic` |
| `fdp_dataset` | Target FDP dataset | `fdp_generic` |
| `marts_dataset` | Marts dataset | `marts_generic` |
| `analytics_dataset` | Analytics dataset | `analytics_generic` |
| `extract_date` | Date of data extract | `null` (optional filter) |
| `generic_entities` | List of entities to process | `['customers', 'accounts', 'decision']` |
| `masking_level` | PII masking strategy (`FULL`, `PARTIAL`, `NONE`) | `AUTO` |

### Technology Stack & Documentation
- [Google BigQuery](https://cloud.google.com/bigquery/docs) - Serverless data warehouse
- [dbt (data build tool)](https://docs.getdbt.com/docs/introduction) - Transformation workflow
- [dbt-bigquery Adapter](https://docs.getdbt.com/reference/warehouse-setups/bigquery-setup) - dbt to BigQuery connector
- [Data Modeling in dbt](https://docs.getdbt.com/docs/build/models) - Best practices for models

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
./scripts/setup_deployment_venv.sh bigquery-to-mapped-product
source deployments/bigquery-to-mapped-product/venv/bin/activate
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
{{ validate_no_pii_in_export('fdp_generic.event_transaction_excess') }}
```

### 5. Cloud Execution
In production, this unit is triggered by the `generic_odp_load_dag` once ingestion is successful. The transformation is executed via a `BashOperator` running `dbt run`.

---

## SQL Example

```sql
-- fdp_generic.event_transaction_excess
SELECT
    c.customer_id,
    c.first_name,
    c.last_name,
    a.account_id,
    a.current_balance,
    -- Audit columns
    c._run_id,
    CURRENT_TIMESTAMP() as _transformed_at
FROM {{ ref('stg_generic_customers') }} c
JOIN {{ ref('stg_generic_accounts') }} a 
    ON c.customer_id = a.customer_id
```

