# GCP Migration Framework - Short Context

## Core Concept
Framework for migrating mainframe data to GCP using a metadata-driven, decoupled 3-unit model (Ingestion, Transformation, Orchestration) coordinated via a `run_id` in a `job_control` table.

## Architecture & Libraries (`gcp-pipeline-libraries/`)
1.  **core**: Foundation (Audit, Error Handling, Job Tracking). No Beam/Airflow.
2.  **beam**: Ingestion (Dataflow). HDR/TRL parsing, schema validation.
3.  **orchestration**: Control (Airflow/Composer). Event-driven (GCS → Pub/Sub).
4.  **transform**: Data Modeling (dbt/BigQuery). Audit columns, PII masking.
5.  **tester**: Mocks/helpers for Airflow-free/Beam-free local testing.

## Deployment Units (`deployments/`)
-   **Generic (Application A (the multi-entity JOIN system))**: 3 sources → 2 FDP (JOIN pattern).
-   **Generic (Application B (the single-entity MAP system))**: 1 source → 1 FDP (MAP pattern).
-   **CDP (Consumable Data Product)**: FDP → Segmented GCS exports.
-   **Structure**: Each has `-ingestion` (Python/Beam), `-transformation` (dbt), and `-orchestration` (Airflow).

## Infrastructure & CI/CD
-   **Terraform**: `infrastructure/terraform/` (unified root module) + `infrastructure/terraform/systems/generic/` (system-specific resources).
-   **GitHub Actions**: 
    -   `publish-libraries.yml`: Auto-publishes to PyPI on push to `main`.
    -   `deploy-generic.yml`/`deploy-generic.yml`: Infrastructure (TF) + Code deployment.
-   **Dependency**: Deployments pull `gcp-pipeline-*` from PyPI.

## Key Technical Rules
-   **Idempotency**: All stages restartable via `run_id` tracking.
-   **Validation**: 100% auditability (source counts = target counts).
-   **Privacy**: In-flight PII masking via `gcp-pipeline-transform` macros.
-   **Generic Logic**: Libraries provide mechanisms; deployments provide config.
