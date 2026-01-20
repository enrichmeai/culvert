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
                             │   MAP Logic     │
  odp_loa.applications ─────►│                 │────► fdp_loa.portfolio_account_facility
                             └─────────────────┘

  1 ODP Source ─────────────────────────────────────────► 1 FDP Target
```

---

## Pattern

**MAP**: 1 ODP source → 1 FDP target

| Step | Description |
|------|-------------|
| 1 | Staging model cleans and type-casts raw ODP applications data |
| 2 | `add_audit_columns` macro injects `run_id` and `source_file` |
| 3 | FDP model maps applications to `portfolio_account_facility` |
| 4 | `mask_pii` macro handles sensitive fields |

---

## Data Mapping

| Source Table | Key Fields |
|--------------|------------|
| `odp_loa.applications` | application_id, customer_id, loan_amount, application_date, application_status, product_type |

| Target Table | Description |
|--------------|-------------|
| `fdp_loa.portfolio_account_facility` | Loan facility records |

---

## Components

| Directory | Purpose |
|-----------|---------|
| `dbt/models/staging/loa/` | Staging models (clean raw data) |
| `dbt/models/fdp/` | FDP models (MAP logic) |

---

## Library-Driven Ease of Use

The LOA transformation unit showcases how the `gcp-pipeline-transform` library simplifies system-agnostic transformation:

1.  **Macro Reusability**: Uses `add_audit_columns` and `mask_pii` exactly like EM, proving the library's "Zero-Bleed" and "Generic-First" implementation.
2.  **Schema Alignment**: The staging models align with the `EntitySchema` defined in the ingestion layer, ensuring no type mismatches during the MAP transformation.
3.  **Governance**: Leverages the library's `validate_no_pii_in_export` to ensure that even after transforming data, no sensitive data is leaked.

---

## How to Replicate this MAP Transformation (1-to-1)

To create a new transformation unit that maps a single source to a single target, follow the [Creating New Deployment Guide](../../docs/CREATING_NEW_DEPLOYMENT_GUIDE.md).

Key steps for this MAP pattern:
1.  **Macro Paths**: Register the library macros in your `dbt_project.yml`.
2.  **Clean Staging**: Create a single staging view for your ODP source.
3.  **FDP Mapping**: Create an FDP model referencing the staging view.
4.  **Audit**: Use `add_audit_columns` to track origin.

---

## Infrastructure & Configurations

### Google Cloud Resources
This deployment requires the following GCP infrastructure, provisioned via Terraform:
- **Data Warehouse**: BigQuery datasets `odp_loa` (source) and `fdp_loa` (target).
- **Processing**: dbt (running on Cloud Composer or as a standalone process) for executing transformations.

For detailed infrastructure definitions, see [infrastructure/terraform/systems/loa/transformation/](../../infrastructure/terraform/systems/loa/transformation/).

### dbt Configuration (`dbt_project.yml`)
The transformation behavior is controlled by variables and configurations in `dbt_project.yml`:

| Variable | Description | Default |
|----------|-------------|---------|
| `gcp_project_id` | Target GCP Project | From `GCP_PROJECT_ID` env var |
| `source_dataset` | Source ODP dataset | `odp_loa` |
| `staging_dataset` | Intermediate staging dataset | `stg_loa` |
| `fdp_dataset` | Target FDP dataset | `fdp_loa` |
| `masking_level` | PII masking strategy (`FULL`, `PARTIAL`, `NONE`) | `AUTO` |

### GCP Documentation Links
- [BigQuery Documentation](https://cloud.google.com/bigquery/docs)
- [dbt Documentation](https://docs.getdbt.com/docs/introduction)
- [dbt-bigquery Adapter](https://docs.getdbt.com/reference/warehouse-setups/bigquery-setup)

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
Run dbt tests to verify transformation logic and MAP pattern:
```bash
dbt test --profiles-dir . --target dev
```

### 4. Governance Verification
Use the library macro to ensure no unmasked PII exists in your models before deployment:
```sql
{{ validate_no_pii_in_export('fdp_loa.portfolio_account_facility') }}
```

### 5. Cloud Execution
In production, this unit is triggered by the `loa_odp_load_dag` once ingestion is successful. The transformation is executed via a `BashOperator` running `dbt run`.

---

## SQL Example

```sql
-- fdp_loa.portfolio_account_facility
SELECT
    application_id,
    customer_id,
    loan_amount,
    application_date,
    application_status,
    -- Audit columns
    _run_id,
    CURRENT_TIMESTAMP() as _transformed_at
FROM {{ ref('stg_loa_applications') }}
```

