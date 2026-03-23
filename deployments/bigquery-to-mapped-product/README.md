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
  odp_generic.applications ──┼───────────────────────────────► fdp_generic.portfolio_account_facility
                        │
                        └───────────────────────
```

---

## Pattern

**MULTI-TARGET**:
1. **JOIN**: 2 ODP sources (customers, accounts) → 1 FDP target (`event_transaction_excess`)
2. **MAP**: 1 ODP source (decision) → 1 FDP target (`portfolio_account_excess`)
3. **MAP**: 1 ODP source (applications) → 1 FDP target (`portfolio_account_facility`)

| Step | Description |
|------|-------------|
| 1 | Staging models clean and type-cast raw ODP data |
| 2 | `data_quality_check` macro validates data integrity |
| 3 | `incremental_strategy` macro handles incremental load logic |
| 4 | `event_transaction_excess` performs `INNER JOIN` between Customers and Accounts |
| 5 | `portfolio_account_excess` maps Decision ODP 1:1 to FDP |

---

## Data Mapping

| Source Table | Key Fields |
|--------------|------------|
| `odp_generic.customers` | customer_id, ssn, first_name, last_name, dob, status |
| `odp_generic.accounts` | account_id, customer_id, account_type, balance, open_date |
| `odp_generic.decision` | decision_id, customer_id, application_id, decision_code, score, decision_date |
| `odp_generic.applications` | application_id, customer_id, loan_amount, interest_rate, term_months, application_date, status, event_type, account_type |

| Target Table | Description |
|--------------|-------------|
| `fdp_generic.event_transaction_excess` | Joined customer-account view |
| `fdp_generic.portfolio_account_excess` | Decision-based portfolio view |
| `fdp_generic.portfolio_account_facility` | Applications-based facility view |

---

## Components

| Directory | Purpose |
|-----------|---------|
| `dbt/models/staging/generic/` | Staging views (clean raw ODP data) |
| `dbt/models/fdp/` | FDP incremental models (JOIN and MAP logic) |
| `dbt/macros/` | Custom macros (schema routing, data quality, incremental strategy) |
| `dbt/models/marts/` | Marts models — placeholder (empty) |
| `dbt/models/analytics/` | Analytics models — placeholder (empty) |

### Key files

| Layer | File | Purpose |
|-------|------|---------|
| Staging | `stg_generic_customers.sql` | Customer data view |
| Staging | `stg_generic_accounts.sql` | Account data view |
| Staging | `stg_generic_decision.sql` | Decision data view |
| Staging | `stg_generic_applications.sql` | Applications data view |
| Staging | `_generic_sources.yml` | Source definitions |
| FDP | `event_transaction_excess.sql` | JOIN: customers + accounts |
| FDP | `portfolio_account_excess.sql` | MAP: decision → portfolio |
| FDP | `portfolio_account_facility.sql` | MAP: applications → facility |
| FDP | `_fdp_generic_models.yml` | Model schemas and tests |
| Macro | `generate_schema_name.sql` | Routes models to Terraform-managed datasets |
| Macro | `data_quality_check.sql` | Data quality validation |
| Macro | `incremental_strategy.sql` | Incremental load logic |

---

## Library-Driven Ease of Use

The Generic transformation unit uses the `gcp-pipeline-transform` library for lineage and audit:

1.  **Schema Routing**: Uses a custom `generate_schema_name` macro to route staging models to `odp_generic` and FDP models to `fdp_generic`, matching the Terraform-managed datasets.
2.  **Automated Lineage**: Audit columns (`_run_id`, `_extract_date`, `_transformed_at`) are preserved from ingestion through to FDP, maintaining end-to-end traceability.
3.  **Incremental Processing**: All FDP models use `merge` strategy with `on_schema_change='append_new_columns'` for efficient incremental loads.

> **Note on PII Masking:** The `mask_pii` macro from `gcp-pipeline-transform` is available but not currently applied in the FDP models. PII masking can be re-enabled per-environment when the library's `get_masking_level` Jinja whitespace issue is resolved.

---

## How to Replicate this JOIN Transformation (3-to-1)

To create a new transformation unit that joins multiple entities, follow the [Creating New Deployment Guide](../../docs/CREATING_NEW_DEPLOYMENT_GUIDE.md).

Key steps for this JOIN pattern:
1.  **Register Library**: Point your `dbt_project.yml` to the `gcp-pipeline-transform` macro paths.
2.  **Schema Routing**: Create a `generate_schema_name` macro to map logical schemas to your Terraform-managed datasets.
3.  **Staging Models**: Create views for your ODP tables. Include all audit columns (`_run_id`, `_extract_date`, `_processed_at`).
4.  **FDP Models**: Implement your JOIN/MAP logic with `incremental` materialization and `merge` strategy.

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
| `masking_level` | PII masking strategy (`FULL`, `PARTIAL`, `NONE`) | `NONE` |
| `extract_date` | Date of data extract | `null` (optional filter) |
| `all_entities` | List of entities to process | `['customers', 'accounts', 'decision', 'applications']` |

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

### 4. Cloud Execution
In production, this unit is triggered by the `generic_transformation_dag` once ingestion is successful. The transformation runs via Cloud Build executing `dbt run --target int` against BigQuery.

---

## SQL Example

```sql
-- fdp_generic.event_transaction_excess (simplified)
SELECT
    {{ dbt_utils.generate_surrogate_key(['c.customer_id', 'a.account_id', 'c._extract_date']) }} as event_key,
    c.customer_id,
    c.ssn as ssn_masked,
    c.first_name,
    c.last_name,
    a.account_id,
    a.balance as current_balance,
    -- Audit columns
    c._run_id,
    c._extract_date,
    CURRENT_TIMESTAMP() as _transformed_at
FROM {{ ref('stg_generic_customers') }} c
INNER JOIN {{ ref('stg_generic_accounts') }} a
    ON c.customer_id = a.customer_id
```

