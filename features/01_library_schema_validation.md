# Prompt: Library Enhancement - Schema-Driven Validation

## Context
The `gcp-pipeline-builder` library contains an `EntitySchema` class and a generic `ValidateRecordDoFn`. However, they are currently disconnected. Pipelines must manually implement validation logic even though the schema already defines requirements like `required`, `allowed_values`, and `max_length`.

## Objectives
- Enhance the core library to support automated, schema-driven validation.
- Reduce boilerplate code in system-specific pipelines (EM, LOA).

## Implementation Steps
1.  **Core Validator Enhancement (`libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/validators/generic.py` or new module):**
    - Create a `SchemaValidator` class that takes an `EntitySchema` and a record.
    - Implement logic to check:
        - Presence of all `required` fields.
        - Field values against `allowed_values` (if defined).
        - String lengths against `max_length`.
        - Basic type consistency (e.g., can a value be cast to the schema's `field_type`).
2.  **Beam Transform Update (`libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/pipelines/beam/transforms/validators.py`):**
    - Update `ValidateRecordDoFn` to optionally accept an `EntitySchema` in its constructor.
    - If a schema is provided, the `process` method should use the `SchemaValidator` to validate the record.
    - Ensure it still supports the existing custom `validation_fn` for complex, cross-field business logic.
3.  **Refactoring Pipelines:**
    - Update `em_pipeline.py` and `loa_pipeline.py` to use the new schema-driven `ValidateRecordDoFn`, passing in the appropriate entity schema.

## Target Files
- `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/schema.py`
- `libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/pipelines/beam/transforms/validators.py`
- `deployments/em/src/em/pipeline/em_pipeline.py`
- `deployments/loa/src/loa/pipeline/loa_pipeline.py`
