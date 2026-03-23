# Project Context

## Overview

GCP Pipeline Reference is a standardized legacy-to-GCP data migration framework using a **Generic Engine** model. Common infrastructure lives in reusable libraries; system-specific behaviour is driven entirely by deployment configuration (`config/system.yaml`). The framework is published to PyPI as `gcp-pipeline-framework` and used across multiple teams.

## 4-Library Architecture

All libraries are published to PyPI. Libraries provide mechanisms; deployments provide configuration.

| Library | Role | Dependency Rule |
|---|---|---|
| `gcp-pipeline-core` | Foundation: audit, monitoring, error handling, job control | **NO beam, NO airflow** |
| `gcp-pipeline-beam` | Ingestion: HDR/TRL parsing, schema validation, Beam transforms | Depends on core. **NO airflow** |
| `gcp-pipeline-orchestration` | Control: Pub/Sub sensors, DAG factory, entity dependency | Depends on core. **NO beam** |
| `gcp-pipeline-transform` | SQL: dbt audit macros, PII masking | **dbt only** |

Supplementary packages:
- `gcp-pipeline-tester` — Testing toolkit (mocks, fixtures, base test classes)
- `gcp-pipeline-framework` — Umbrella package that installs all libraries

Libraries are versioned at **1.0.28**. Reference packages (`gcp-pipeline-ref-ingestion`, `gcp-pipeline-ref-transform`, `gcp-pipeline-ref-orchestration`) are at **1.0.14**.

## Data Layer Hierarchy

```
ODP  (Original Data Product)     — Raw 1:1 copy from source (e.g. odp_generic.customers)
 ↓
FDP  (Foundation Data Product)   — Transformed, business-ready (e.g. fdp_generic.event_transaction_excess)
 ↓
CDP  (Consumable Data Product)   — Complex business logic joining multiple FDP tables (e.g. cdp_generic.customer_risk_profile)
```

## Active Deployments (3-Unit Model)

Each system is split into independent ingestion, orchestration, and transformation units.

| Deployment | Type | What It Does |
|---|---|---|
| `original-data-to-bigqueryload` | Dataflow Flex Template | GCS CSV files to BigQuery ODP tables |
| `data-pipeline-orchestrator` | Airflow DAGs (Cloud Composer) | Pub/Sub sensor triggers Dataflow, then triggers dbt |
| `bigquery-to-mapped-product` | dbt models | ODP to FDP transformation |

## Additional Deployments

| Deployment | Status | What It Does |
|---|---|---|
| `fdp-to-consumable-product` | Code-complete | dbt models: FDP to CDP |
| `mainframe-segment-transform` | Code-complete | Beam pipeline: CDP to GCS segment files |
| `postgres-cdc-streaming` | Reference/stub | Real-time CDC: Postgres to Kafka to Beam to BigQuery |
| `spanner-to-bigquery-load` | Reference/stub | Federated queries: Spanner to BigQuery |

## Project Structure

```
gcp-pipeline-libraries/       Reusable Python libraries and dbt macros
deployments/                   System-specific configurations (install libraries from PyPI)
infrastructure/terraform/      GCP infrastructure as code
docs/                          Technical architecture and guides
scripts/                       Setup, validation, and infrastructure scripts
```

## Config-Driven Design

Each deployment has a `config/system.yaml` that drives all pipeline behaviour. System-specific logic (entity names, file patterns, schema definitions, trigger rules) lives in deployment config, never in libraries. Generic placeholders "Application1" and "Application2" are used in examples per governance rules.

## Governance Rules

1. **Zero-Bleed Policy** — `core` has no engine dependencies. Beam and Airflow logic stay separate.
2. **Generic Tools, Specific Data** — Libraries provide how; deployments provide what.
3. **3-Unit Model** — Every system splits into ingestion, orchestration, and transformation.
4. **Full Tracking** — Every record tracked from source to target via `run_id`.
5. **Idempotent** — Pipelines can be safely restarted without creating duplicate data.
6. **Privacy by Design** — PII masked using generic strategies (FULL, PARTIAL, REDACTED).

## Infrastructure

- **GCP Project**: `joseph-antony-aruja`
- **CI/CD**: GitHub Actions (`deploy-generic.yml`), Terraform-managed infrastructure
- **Push to `main`** auto-deploys (path-filtered)
- **`[publish:deploy]`** keyword in commit message publishes libraries to PyPI then deploys

## Development Workflow

1. Use `scripts/setup_deployment_venv.sh` for local development.
2. Follow `docs/CREATING_NEW_DEPLOYMENT_GUIDE.md` for new systems.
3. Libraries are published to PyPI; deployments install from PyPI.
4. Run both library and deployment tests locally before pushing.
