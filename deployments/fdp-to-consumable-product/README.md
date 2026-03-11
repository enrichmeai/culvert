# fdp-to-consumable-product

**Deployment type:** BigQuery (dbt)
**Layer:** CDP — Consumable Data Product
**Pattern:** JOIN across 3 FDP tables → 1 CDP table

## Overview

This deployment builds the **CDP (Consumable Data Product)** layer by joining all three FDP tables from `fdp_generic` into a single denormalised view per customer:

```
fdp_generic.event_transaction_excess    ─┐
fdp_generic.portfolio_account_excess    ─┼──► cdp_generic.customer_risk_profile
fdp_generic.portfolio_account_facility  ─┘
```

The `customer_risk_profile` CDP table is the primary source for the `mainframe-segment-transform` pipeline, which reads each row and writes an outbound fixed-width segment file back to GCS for downstream mainframe consumption.

## Data Flow

```
ODP (odp_generic) ──► FDP (fdp_generic) ──► CDP (cdp_generic) ──► GCS segment files
       ↑                    ↑                      ↑                      ↑
  Dataflow/Beam          dbt JOIN/MAP           dbt JOIN          Dataflow/Beam
  (ingestion)          (bigquery-to-         (this deployment)   (mainframe-segment-
                       mapped-product)                            transform)
```

## CDP Table: `cdp_generic.customer_risk_profile`

One row per customer per extract date. Combines:

| Source FDP Table | Fields |
|-----------------|--------|
| `event_transaction_excess` | customer identity, account exposure, current balance |
| `portfolio_account_excess` | risk decision, score, decision outcome |
| `portfolio_account_facility` | loan amount, interest rate, term, facility status |

Derived field `cdp_segment`:
- `ACTIVE_APPROVED` — decision approved + positive balance
- `DECLINED` — decision declined
- `REFERRED` — decision referred for manual review
- `PENDING` — no decision yet

## Structure

```
deployments/fdp-to-consumable-product/
├── pyproject.toml
├── Dockerfile                   # generic-cdp-transformation image
├── cloudbuild.yaml
├── dbt/
│   ├── dbt_project.yml
│   ├── packages.yml
│   └── models/
│       ├── staging/fdp/         # Thin wrappers over fdp_generic source tables
│       │   ├── _fdp_sources.yml
│       │   ├── stg_fdp_event_transaction_excess.sql
│       │   ├── stg_fdp_portfolio_account_excess.sql
│       │   └── stg_fdp_portfolio_account_facility.sql
│       └── cdp/                 # CDP output table
│           ├── _cdp_models.yml
│           └── customer_risk_profile.sql
└── tests/
```

## Running Locally

```bash
# Setup venv
./scripts/setup_deployment_venv.sh fdp-to-consumable-product

# Activate and install dbt deps
source deployments/fdp-to-consumable-product/venv/bin/activate
cd deployments/fdp-to-consumable-product/dbt
dbt deps

# Run CDP models
export GCP_PROJECT_ID=joseph-antony-aruja
dbt run --target dev

# Run tests
dbt test
```

## Docker Build

```bash
cd /path/to/gcp-pipeline-reference
gcloud builds submit \
  --config deployments/fdp-to-consumable-product/cloudbuild.yaml \
  --substitutions _LIBRARY_VERSION=1.0.7 \
  .
```
