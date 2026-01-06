# LOA Transformation

**Unit 2 of LOA 3-Unit Deployment**

FDP Transformation - dbt models for ODP → FDP transformation.

## Pattern

**SPLIT**: 1 ODP source → 2 FDP targets
- Source: `odp_loa.applications`
- Targets: 
  - `fdp_loa.event_transaction_excess`
  - `fdp_loa.portfolio_account_excess`

## Components

- `dbt/models/staging/loa/` - Staging models
- `dbt/models/fdp/` - FDP models

## Dependencies

- `dbt-bigquery` - dbt for BigQuery

## Run

```bash
cd deployments/loa-transformation/dbt
dbt run --profiles-dir .
```

