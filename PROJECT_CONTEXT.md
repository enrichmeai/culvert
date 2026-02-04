# Project Context Summary

## Overview
This project is a framework for migrating data from legacy mainframe systems to Google Cloud Platform. It uses a **shared library** approach, where common infrastructure is separated from system-specific logic. This approach is officially supported by multiple teams across the **the enterprise platform**, providing a standardized way (called "paved paths") to move data reliably.

## Project Structure
- `gcp-pipeline-libraries/`: Reusable Python libraries and dbt macros.
  - `gcp-pipeline-core`: Foundation (Audit, Job Tracking, Error Handling). Works with any engine.
  - `gcp-pipeline-beam`: Ingestion (File parsing and validation using Apache Beam).
  - `gcp-pipeline-orchestration`: Coordination (Scheduling and dependency management using Airflow).
  - `gcp-pipeline-transform`: Data Modeling (SQL macros for tracking and data privacy using dbt).
  - `gcp-pipeline-tester`: Testing tools (Mocks and test helpers).
- `deployments/`: System-specific settings using the libraries (currently using embedded libraries).
  - `em-*`: Application A (Multi-target transformation: 3 sources -> 2 targets).
  - `loa-*`: Application B (Single-target transformation: 1 source -> 1 target).
  - `spanner-*`: Spanner Transformation examples.
- `templates/`: Pre-built templates for new systems.
- `docs/`: Technical Architecture and User Guides.

## Core Governance Rules
1. **Separation of Concerns**: 
   - The `core` library must not depend on specific processing engines like Beam or Airflow.
   - Ingestion and Scheduling logic must stay separate.
2. **Generic Tools, Specific Data**: 
   - Libraries provide the mechanisms (how to move data).
   - Deployments provide the configuration (what data to move).
3. **3-Unit Model**: Every system is split into independent `-ingestion`, `-transformation`, and `-orchestration` parts to save costs and improve speed.
4. **Standardized Patterns**: Anyone can create a new migration pattern, but it must follow the mandatory rules in the [Technical Architecture Document](./docs/TECHNICAL_ARCHITECTURE.md#106-governance-for-custom-paved-paths).

## Technical Patterns
- **Full Tracking**: Every record is tracked from source to target using a unique `run_id`.
- **Safety First**: Systems are designed so they can be safely restarted without creating duplicate data.
- **Privacy by Design**: Sensitive data (PII) is masked based on clear rules, not hidden in complex SQL.
- **Local Testing**: Logic can be tested on a developer's machine without needing a live cloud environment.

## Development Workflow
1. Use `scripts/setup_deployment_venv.sh` for local dev.
2. Follow `docs/CREATING_NEW_DEPLOYMENT_GUIDE.md` for new systems.
3. Enforce SonarQube quality standards and 90%+ test coverage.
