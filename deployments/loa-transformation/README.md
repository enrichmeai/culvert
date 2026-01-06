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

## Dependencies

| Library | Purpose |
|---------|---------|
| `dbt-bigquery` | dbt adapter for BigQuery |
| `gcp-pipeline-transform` | Shared macros (audit columns) |

---

## Run

```bash
cd deployments/loa-transformation/dbt
dbt run --profiles-dir .
```

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

