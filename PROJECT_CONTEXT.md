# Project Context Summary

## Overview
This project is a mainframe-to-GCP data migration framework. It is built on a **Library-First** philosophy, where reusable infrastructure is decoupled from system-specific logic.

## Project Structure
- `libraries/`: Reusable Python libraries and dbt macros.
  - `gcp-pipeline-core`: Foundation (Audit, Job Control, Error Handling). **Portable & Engine-Agnostic.**
  - `gcp-pipeline-beam`: Ingestion (Header/Trailer Parsing, Beam Transforms).
  - `gcp-pipeline-orchestration`: Control (Airflow Sensors, Operators, Dependency Management).
  - `gcp-pipeline-transform`: SQL (dbt macros for lineage and PII).
  - `gcp-pipeline-tester`: Testing utilities (Mocks, BDD fixtures).
- `deployments/`: System-specific implementations using the libraries.
  - `em-*`: Application A (JOIN pattern: 3 sources -> 1 target).
  - `loa-*`: Application B Application (SPLIT pattern: 1 source -> 2 targets).
- `templates/`: Standardized DAG and CI/CD templates for new deployments.
- `docs/`: Technical Architecture (TAD) and User Guides.

## Core Governance Rules
1. **Zero-Bleed Dependency**: 
   - `core` library MUST NOT depend on Beam or Airflow.
   - `beam` and `orchestration` must remain functionally isolated.
2. **Strict Genericity**: 
   - Libraries provide the **Engine** (mechanisms).
   - Deployments provide the **Fuel** (configuration/metadata).
   - No project-specific IDs or regional biases in libraries.
3. **3-Unit Deployment**: Every system is split into independent `-ingestion`, `-transformation`, and `-orchestration` units to optimize scaling and costs.

## Technical Patterns
- **Audit Lineage**: All records track `_run_id` from arrival to final FDP table.
- **Idempotency**: `AuditTrail` and `JobControl` ensure jobs can be safely restarted.
- **Metadata-Driven PII**: PII masking is controlled by `EntitySchema` definitions, not hardcoded SQL.
- **Local Validation**: Airflow DAGs and Dataflow logic use stubs/mocks for testing without live GCP.

## Development Workflow
1. Use `scripts/setup_deployment_venv.sh` for local dev.
2. Follow `docs/CREATING_NEW_DEPLOYMENT_GUIDE.md` for new systems.
3. Enforce SonarQube quality standards and 90%+ test coverage.
