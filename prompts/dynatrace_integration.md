### Finalized Prompt: Dynatrace Enterprise Integration

**Task: Implement Dynatrace Observability for Migration Pipelines**

**Objective:** Enable full-stack visibility of the migration lifecycle within Dynatrace by implementing OpenTelemetry tracing and Business Event ingestion.

**Requirements:**
1.  **OTLP Exporter Integration**:
    *   Add `opentelemetry-exporter-otlp` to `gcp-pipeline-builder` dependencies.
    *   Initialize a global tracer in a new `gcp_pipeline_builder.monitoring.otel` module.
    *   Retrieve Dynatrace OTLP credentials (`DT_API_TOKEN`, `DT_URL`) from GCP Secret Manager.

2.  **Core Library Instrumentation**:
    *   **AuditTrail**: Instrument `log_entry` and `record_processing_end` to emit Dynatrace Business Events. This allows "Davis AI" to track the success/failure of logical migration batches.
    *   **BasePipeline (Beam)**: Wrap the `run()` method in a trace span and ensure the `run_id` is attached as a span attribute.
    *   **Orchestration**: Instrument the `BasePubSubPullSensor` to start a new trace context when a `.ok` file is detected.

3.  **Distributed Trace Propagation**:
    *   Implement context propagation from the Airflow DAG to the Dataflow Job so that the entire migration flow appears as a single "Service Flow" in Dynatrace.

4.  **Infrastructure (Terraform)**:
    *   Update IAM roles for the Pipeline Service Account to allow `secretmanager.versions.get` for Dynatrace tokens.

**Deliverables**:
*   A functional `otel.py` utility in the core library.
*   Traced execution flows visible in Dynatrace.
*   A Dynatrace Dashboard template showing Migration Batch throughput and error rates.
