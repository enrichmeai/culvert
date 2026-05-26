# Spanner Transformation (Federated)

**Unit for Spanner-to-BigQuery Federated Transformation**

This deployment unit demonstrates the **FEDERATED** pattern, where data is queried directly from Google Cloud Spanner using BigQuery External Queries and transformed into Foundation Data Product (FDP) tables.

---

## Flow Diagram

```
                         Spanner FEDERATED FLOW
                         ──────────────────────

  Cloud Spanner                BigQuery (Federated)            BigQuery FDP
  ─────────────                ────────────────────            ────────────

  customers table ───────────► External Query ───────────────► fdp_spanner.spanner_customer_summary
                               (via Connection)
```

---

## Pattern

**FEDERATED**:
1. **Source**: Cloud Spanner (External Table/Query)
2. **Logic**: dbt models using `EXTERNAL_QUERY` or federated connections.
3. **Target**: BigQuery FDP Dataset (`fdp_spanner`)

| Step | Description |
|------|-------------|
| 1 | dbt invokes BigQuery federated connection to Spanner |
| 2 | `spanner_customer_summary` model performs transformations on live Spanner data |
| 3 | Results are persisted into BigQuery as FDP tables |

---

## Infrastructure & Configurations

### Google Cloud Resources
This deployment requires the following GCP infrastructure:
- **Source**: Google Cloud Spanner instance and database.
- **Connection**: BigQuery Connection (Cloud Spanner type) to enable federated queries.
- **Target**: BigQuery dataset `fdp_spanner`.

For infrastructure definitions, see [infrastructure/terraform/systems/spanner/](../../infrastructure/terraform/systems/spanner/).

### dbt Configuration (`dbt_project.yml`)

| Variable | Description | Default / Source |
|----------|-------------|------------------|
| `spanner_connection_id` | BigQuery Connection ID for Spanner | `project.location.spanner-conn` |
| `spanner_table_name` | Source table name in Spanner | `customers` |

---

## Execution & Testing

### 1. Local Development Setup
Initialize the virtual environment:
```bash
./scripts/setup_deployment_venv.sh spanner-to-bigquery-load
source deployments/spanner-to-bigquery-load/venv/bin/activate
```

### 2. Local dbt Execution
Run dbt models locally against the development BigQuery dataset:
```bash
cd dbt
dbt run --profiles-dir . --target dev
```

### 3. Data Quality Validation
Run dbt tests to verify transformation logic:
```bash
dbt test --profiles-dir . --target dev
```

---

## SQL Example

```sql
-- spanner_customer_summary.sql
SELECT * FROM EXTERNAL_QUERY(
  "{{ var('spanner_connection_id') }}",
  "SELECT customer_id, first_name, last_name, email FROM {{ var('spanner_table_name') }}"
);
```
