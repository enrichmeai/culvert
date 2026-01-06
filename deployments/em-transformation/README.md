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
  odp_em.accounts  ─────┼───►│   JOIN Logic    │────────► fdp_em.em_attributes
                        │    │                 │
  odp_em.decision  ─────┘    │  - Customer ID  │
                             │  - Account ID   │
                             │  - Decision ID  │
                             └─────────────────┘

  3 ODP Sources ────────────────────────────────────────► 1 FDP Target
```

---

## Pattern

**JOIN**: 3 ODP sources → 1 FDP target

| Source Table | Key Fields |
|--------------|------------|
| `odp_em.customers` | customer_id, ssn, name |
| `odp_em.accounts` | account_id, customer_id, balance |
| `odp_em.decision` | decision_id, customer_id, outcome |

| Target Table | Description |
|--------------|-------------|
| `fdp_em.em_attributes` | Joined customer-account-decision view |

---

## Components

| Directory | Purpose |
|-----------|---------|
| `dbt/models/staging/em/` | Staging models (clean raw data) |
| `dbt/models/fdp/` | FDP models (JOIN logic) |

---

## Dependencies

| Library | Purpose |
|---------|---------|
| `dbt-bigquery` | dbt adapter for BigQuery |
| `gcp-pipeline-transform` | Shared macros (audit columns) |

---

## Run

```bash
cd deployments/em-transformation/dbt
dbt run --profiles-dir .
```

---

## SQL Example

```sql
-- fdp_em.em_attributes
SELECT
    c.customer_id,
    c.first_name,
    c.last_name,
    a.account_id,
    a.current_balance,
    d.decision_outcome,
    d.decision_date,
    -- Audit columns
    c._run_id,
    CURRENT_TIMESTAMP() as _transformed_at
FROM {{ ref('stg_em_customers') }} c
LEFT JOIN {{ ref('stg_em_accounts') }} a 
    ON c.customer_id = a.customer_id
LEFT JOIN {{ ref('stg_em_decision') }} d 
    ON c.customer_id = d.customer_id
```

