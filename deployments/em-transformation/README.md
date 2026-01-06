# EM Transformation

**Unit 2 of EM 3-Unit Deployment**

FDP Transformation - dbt models for ODP → FDP transformation.

## Pattern

**JOIN**: 3 ODP sources → 1 FDP target
- Sources: 
  - `odp_em.customers`
  - `odp_em.accounts`
  - `odp_em.decision`
- Target: `fdp_em.em_attributes`

## Components

- `dbt/models/staging/em/` - Staging models
- `dbt/models/fdp/` - FDP models (JOIN logic)

## Dependencies

- `dbt-bigquery` - dbt for BigQuery

## Run

```bash
cd deployments/em-transformation/dbt
dbt run --profiles-dir .
```

