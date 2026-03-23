# Project Context Summary

## Overview
This project is a framework for migrating data from legacy mainframe systems to Google Cloud Platform. It uses a **shared library** approach, where common infrastructure is separated from system-specific configuration. This approach is officially supported by multiple teams across the **the enterprise platform**, providing standardized patterns (called "paved paths") to move data reliably.

The reference implementation uses a single **Generic** system that demonstrates two pipeline patterns simultaneously: JOIN (multi-entity dependency) and MAP (single-entity immediate trigger).

## Project Structure
- `gcp-pipeline-libraries/`: Reusable Python libraries and dbt macros (4-library architecture + tester + umbrella).
  - `gcp-pipeline-core`: Foundation (Audit, Job Tracking, Error Handling). Works with any engine. **NO beam, NO airflow.**
  - `gcp-pipeline-beam`: Ingestion (File parsing and validation using Apache Beam). Depends on core.
  - `gcp-pipeline-orchestration`: Coordination (Scheduling and dependency management using Airflow). Depends on core.
  - `gcp-pipeline-transform`: Data Modeling (SQL macros for audit columns and PII masking using dbt). **dbt only.**
  - `gcp-pipeline-tester`: Testing tools (Mocks, fixtures, and base test classes).
  - `gcp-pipeline-framework`: Umbrella package that installs all libraries.
- `deployments/`: System-specific configurations using the libraries (installed from PyPI).
  - `original-data-to-bigqueryload`: Generic Ingestion (GCS CSV → BigQuery ODP via Dataflow).
  - `data-pipeline-orchestrator`: Generic Orchestration (Airflow DAGs on Cloud Composer).
  - `bigquery-to-mapped-product`: Generic Transformation (dbt: ODP → FDP).
  - `fdp-to-consumable-product`: CDP Transformation (dbt: FDP → CDP, code-complete).
  - `mainframe-segment-transform`: Segment Writer (Beam: CDP → GCS segment files, code-complete).
  - `postgres-cdc-streaming`: Streaming CDC (Postgres → Kafka → Beam → BigQuery, reference).
  - `spanner-to-bigquery-load`: Federated queries (Spanner → BigQuery via dbt, reference).
- `docs/`: Technical Architecture and User Guides.
- `infrastructure/terraform/`: GCP infrastructure as code.

## Data Layer Hierarchy
- **ODP** (Original Data Product): Raw 1:1 copy from source (e.g., `odp_generic.customers`)
- **FDP** (Foundation Data Product): Transformed, business-ready data (e.g., `fdp_generic.event_transaction_excess`)
- **CDP** (Consumable Data Product): Built from multiple FDP tables (e.g., `cdp_generic.customer_risk_profile`)

## Core Governance Rules
1. **Separation of Concerns (Zero-Bleed Policy)**:
   - The `core` library must not depend on specific processing engines like Beam or Airflow.
   - Ingestion (Beam) and Scheduling (Airflow) logic must stay separate.
2. **Generic Tools, Specific Data**:
   - Libraries provide the mechanisms (how to move data).
   - Deployments provide the configuration (what data to move).
3. **3-Unit Model**: Every system is split into independent ingestion, transformation, and orchestration parts.
4. **Standardized Patterns**: Anyone can create a new migration pattern, but it must follow the mandatory rules in the [Technical Architecture Document](./docs/TECHNICAL_ARCHITECTURE.md#106-governance-for-custom-paved-paths).

## Technical Patterns
- **Full Tracking**: Every record is tracked from source to target using a unique `run_id`.
- **Safety First**: Systems are designed so they can be safely restarted without creating duplicate data.
- **Privacy by Design**: Sensitive data (PII) is masked based on clear rules using generic strategies (FULL, PARTIAL, REDACTED).
- **Local Testing**: Logic can be tested on a developer's machine without needing a live cloud environment.

## Development Workflow
1. Use `scripts/setup_deployment_venv.sh` for local dev.
2. Follow `docs/CREATING_NEW_DEPLOYMENT_GUIDE.md` for new systems.
3. Libraries published to PyPI; deployments install from PyPI.
4. Push to `main` triggers automated deployment via `deploy-generic.yml`.
