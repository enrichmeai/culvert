# Prompt: Library Enhancement - Automated PII Masking

## Context
Data privacy is critical in migration projects. The `EntitySchema` already includes an `is_pii` flag on `SchemaField`, but there is no automated mechanism in the `gcp-pipeline-builder` library to act on this flag during the data processing phase.

## Objectives
- Implement a reusable, schema-driven PII masking transform.
- Ensure consistent data privacy across all entities and systems (EM, LOA).

## Implementation Steps
1.  **PII Masking Transform (`libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/pipelines/beam/transforms/transformers.py`):**
    - Create a new Beam `DoFn` called `MaskPIIDoFn`.
    - It should accept an `EntitySchema` in its constructor.
    - In the `process` method, it should:
        - Identify all fields in the schema marked with `is_pii=True`.
        - Apply a masking strategy to these fields (e.g., replace with `***MASKED***`, or keep only the last 4 digits).
        - Allow the masking strategy to be configurable (e.g., via a mapping or a default mask).
2.  **Integration Helper:**
    - Create a helper method in the `pipelines.beam.builder` (or similar) to easily inject this transform into any pipeline if a schema is provided.
3.  **Pipeline Update:**
    - Update `em_pipeline.py` and `loa_pipeline.py` to include the `MaskPIIDoFn` transform for all entities before writing to BigQuery.

## Target Files
- `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/pipelines/beam/transforms/transformers.py`
- `deployments/em/src/em/pipeline/em_pipeline.py`
- `deployments/loa/src/loa/pipeline/loa_pipeline.py`
