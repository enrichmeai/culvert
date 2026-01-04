### Prompt for Implementing Logging Improvements

This prompt is designed to be given to an LLM or an engineer to refactor the current "print-based" logging into a production-ready, structured logging system integrated with GCP Cloud Logging.

---

**Task: Refactor Pipeline Logging to Structured GCP Cloud Logging**

**Context:**
The current `legacy-migration-reference` project uses a mix of `logging.getLogger()` and raw `print()` statements (particularly in the `AuditTrail` class and Apache Beam transforms). This makes it difficult to filter logs by severity or search for specific `run_id`s in GCP Cloud Logging.

**Objective:**
Standardize all logging to use a structured JSON-compatible format that includes critical metadata (`run_id`, `system_id`, `entity_type`) in every log entry.

**Requirements:**

1.  **Standardize Logger Configuration:**
    *   Create a central logging configuration utility in `gcp_pipeline_builder.utilities.logging`.
    *   Implement a formatter that outputs logs in a structured format (JSON or key-value pairs) compatible with GCP Cloud Logging.
    *   Ensure the logger captures `levelname`, `timestamp`, `message`, and any extra context provided.

2.  **Refactor `AuditTrail` (`libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/audit/trail.py`):**
    *   Replace all `print()` statements with `logger.info()`, `logger.error()`, or `logger.warning()`.
    *   Inject the `run_id` and `entity_type` into the logging context using `LoggerAdapter` or by passing them in the `extra` parameter of the logger calls.
    *   Example: `logger.info("Pipeline started", extra={"run_id": self.run_id, "entity": self.entity_type})`.

3.  **Update Beam Transforms (`libraries/gcp-pipeline-builder/src/gcp_pipeline_builder/pipelines/beam/transforms/`):**
    *   Audit all `DoFn` classes (e.g., `ParseCsvLine`, `FilterRecordsDoFn`).
    *   Ensure that when an error is caught in a `try-except` block, the logger captures the full stack trace and the specific record that caused the failure (if safe to log).
    *   Use appropriate severity levels: `ERROR` for records sent to the error side-channel, `WARNING` for schema mismatches that don't stop the pipeline.

4.  **Integrate with Airflow Callbacks:**
    *   Ensure that failure callbacks in `gcp_pipeline_builder.orchestration.callbacks` log the Airflow `dag_id` and `task_id` alongside the pipeline `run_id`.

5.  **Performance Check:**
    *   Ensure that logging in the "hot path" (inside Beam `process` methods) does not significantly impact throughput. Use `logger.isEnabledFor(logging.DEBUG)` for verbose data-level logs.

**Deliverables:**
*   A new `logging_utils.py` module.
*   Modified `trail.py` with no `print` statements.
*   Updated Beam transforms with consistent structured logging.
*   Unit tests verifying that logs contain the expected metadata fields.
