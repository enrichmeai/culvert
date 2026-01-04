# Prompt: Library Enhancement - Automated Reconciliation

## Context
The `gcp-pipeline-builder` library has a `ReconciliationEngine` and `HDRTRLParser`, but they are not integrated. Currently, the "ground truth" record count from the mainframe trailer record is not automatically compared with the final BigQuery row count in a systematic way.

## Objectives
- Automate the reconciliation process as a standard part of the pipeline lifecycle.
- Provide a clear pass/fail status for every migration run based on record counts.

## Implementation Steps
1.  **Reconciliation Engine Enhancement (`libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/audit/reconciliation.py`):**
    - Update `ReconciliationEngine` to support direct ingestion of `TrailerRecord` objects from the `HDRTRLParser`.
    - Implement a method `reconcile_with_bigquery` that uses the `BigQueryClient` to fetch the actual count of records with a specific `run_id` from the destination table.
2.  **Pipeline Integration:**
    - In the pipeline orchestration logic (or as a post-execution step in `em_pipeline.py` and `loa_pipeline.py`), instantiate the `ReconciliationEngine`.
    - Fetch the expected count from the `TrailerRecord` (extracted during the file reading phase).
    - After the Dataflow job completes, trigger the reconciliation check.
3.  **Reporting:**
    - Ensure the reconciliation result is logged to Cloud Logging and potentially updated in the `pipeline_jobs` table (via `JobControlRepository`).

## Target Files
- `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/audit/reconciliation.py`
- `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/job_control/repository.py`
- `deployments/em/src/em/pipeline/em_pipeline.py`
- `deployments/loa/src/loa/pipeline/loa_pipeline.py`
