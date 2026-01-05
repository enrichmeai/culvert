# Prompt: Library Enhancement - Standardized Monitoring Metrics

## Context
While Dataflow provides some built-in metrics, there is no standardized way for the migration framework to report business-level metrics (e.g., "records processed per second", "validation failure rate by entity type") consistently across all systems.

## Objectives
- Implement a standardized metrics collection module within the `gcp-pipeline-builder` library.
- Enable automatic reporting of key migration performance indicators (KPIs) to Cloud Monitoring.

## Implementation Steps
1.  **Core Metrics Module (`libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/monitoring/metrics.py`):**
    - Create a `MigrationMetrics` class that wraps the Cloud Monitoring API or uses Apache Beam's `Metrics` class.
    - Define standard metric names: `records_read`, `records_validated`, `records_failed`, `processing_duration`, `reconciliation_status`.
    - Ensure all metrics are tagged with `run_id`, `system_id`, and `entity_type`.
2.  **Beam Transform Integration:**
    - Update core transforms (like `ValidateRecordDoFn` and `ParseCsvLine`) to automatically increment these standard metrics.
3.  **Pipeline Integration:**
    - Ensure system-specific pipelines (EM, LOA) automatically inherit these metrics by using the standard library transforms.
    - Add a final step to report aggregate run metrics to the `pipeline_jobs` table.

## Target Files
- `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/monitoring/metrics.py`
- `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/pipelines/beam/transforms/validators.py`
- `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/pipelines/beam/transforms/parsers.py`
- `deployments/em/src/em/pipeline/em_pipeline.py`
- `deployments/loa/src/loa/pipeline/loa_pipeline.py`


