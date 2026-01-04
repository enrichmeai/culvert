# Prompt: Library Enhancement - Structured JSON Logging

## Context
Currently, the library uses standard Python logging, which is often inconsistent across different modules. For production cloud environments like GCP, structured JSON logging is essential for effective log analysis, monitoring, and alerting in Cloud Logging.

## Objectives
- Implement a standardized, structured JSON logging module within the `gcp-pipeline-builder` library.
- Ensure all library components and system-specific deployments (EM, LOA) produce logs in a consistent, machine-readable format.

## Implementation Steps
1.  **Core Logging Module (`libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/utilities/logging.py`):**
    - Create a `configure_structured_logging` function.
    - Use a library like `python-json-logger` or a custom formatter to output logs in JSON format.
    - Include standard fields: `timestamp`, `level`, `module`, `run_id`, `system_id`, `entity_type`, and `message`.
2.  **Library-wide Integration:**
    - Refactor existing library modules to use this standardized logging configuration.
    - Ensure `run_id` and other context fields are automatically injected into logs when available in the execution context.
3.  **Pipeline Update:**
    - Update `em_pipeline.py` and `loa_pipeline.py` to call `configure_structured_logging()` at the start of their execution.
    - Ensure all pipeline stages (validation, transformation) leverage the structured logger.

## Target Files
- `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/utilities/logging.py`
- `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/pipelines/beam/base.py`
- `deployments/em/src/em/pipeline/em_pipeline.py`
- `deployments/loa/src/loa/pipeline/loa_pipeline.py`
