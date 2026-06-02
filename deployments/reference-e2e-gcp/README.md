# reference-e2e-gcp — Culvert E2E Skeleton

**Sprint:** 12 · **Ticket:** T12.0 · **Issue:** [#92](https://github.com/enrichmeai/culvert/issues/92)

The `reference-e2e-gcp` deployment is the foundation every sprint's E2E slice
appends to. It contains a minimal 2-stage Culvert `Pipeline` that is runnable
today on Beam's in-process `DirectRunner` and will be submitted to Cloud
Dataflow once the CI gating in S15 (#83) is in place.

---

## What is here

```
deployments/reference-e2e-gcp/
├── pom.xml                               standalone Maven module (no parent-pom entry needed)
├── README.md                             this file
└── src/
    ├── main/java/com/enrichmeai/culvert/e2e/
    │   ├── NoOpReadStage.java            stub "read" stage  ([] → ["rows"])
    │   └── NoOpTransformStage.java       stub "transform" stage (["rows"] → ["clean"])
    └── test/java/com/enrichmeai/culvert/e2e/
        └── ReferenceE2EPipelineTest.java DirectRunner structural test (3 cases)
```

### The 2-stage pipeline

```
NoOpReadStage  ──(rows)──►  NoOpTransformStage
   inputs: []                   inputs: ["rows"]
   outputs: ["rows"]            outputs: ["clean"]
```

Both stages are no-ops: they produce no real I/O. They are serializable named
classes (not anonymous) so Beam can serialize them into a `DoFn` for the
`DirectRunner` and, later, for Cloud Dataflow workers.

The pipeline is wired through:
- `DefaultRuntimeContext` — the framework's DI container; advisory hooks
  (observability, metrics, finops, lineage, governance) fall back to no-ops
  when nothing is registered.
- `StageTransform` — the Beam `PTransform` adapter that wraps each
  `PipelineStage` and triggers its `execute(RuntimeContext)` hook exactly once.
- `DataflowPipeline` — the Culvert `Pipeline` implementation that computes
  topological order and builds the Beam graph.
- `PipelineToDagSpec` — the scheduler-agnostic translator that emits a
  `DagSpec` (Cloud Composer / Airflow shape).

---

## The slice-append model

Each sprint appends or replaces behaviour in this skeleton without touching
the core contracts. The planned slices are:

| Sprint | Issue | Slice | What changes |
|--------|-------|-------|--------------|
| S12    | #80 (T12.5) | Observability | `ObservabilityHook` + `StageMetricsHook` verified end-to-end; MDC fields asserted in log output. |
| S13    | #81         | Cost / FinOps | `FinOpsSink` tagging; cost-budget assertion. |
| S14    | #82         | Data Quality  | DQ assertions inside the transform stage; bad-record routing. |
| S15    | #83         | CI gating     | Live emulator via Testcontainers; GitHub Actions gate on E2E green. |

Each sprint's dev-agent should:
1. Branch off `sprint-N`.
2. Add its slice into this directory (or into an existing stage class) rather
   than duplicating the skeleton.
3. Keep the DirectRunner test green.
4. Open a PR into `sprint-N` referencing the parent issue.

---

## How it is validated now

**Structural / DirectRunner (today, no live GCP, no Docker):**

```bash
# Prerequisites: Culvert libraries must be installed in ~/.m2.
# If this is your first run (or on a fresh clone), install them first.
# NOTE: -o is NOT used here — the dataflow module's -am dependency chain
# includes testcontainers/fake-gcs transitive deps that may not be cached.
# Drop -o for the one-time bootstrap; re-add it on warm caches.
cd data-pipeline-libraries-java
mvn -pl data-pipeline-core-java,data-pipeline-gcp-dataflow-java,data-pipeline-orchestration-java \
    -am -DskipTests install

# Then run all tests (skeleton + observability E2E slice — offline is fine):
cd ../deployments/reference-e2e-gcp
mvn -o test
```

Expected output after S12 T12.5:
```
Tests run: 6, Failures: 0, Errors: 0, Skipped: 0
BUILD SUCCESS
```

The 6 tests break down as:
- 3 skeleton tests (`ReferenceE2EPipelineTest`) — unchanged from T12.0.
- 3 observability tests (`ReferenceE2EObservabilityTest`) — the S12 slice.

**Live emulator / CI (S15, #83, future):**

Once S15 lands, a Testcontainers-based `*IT.java` test will be added here and
gated via `mvn -P it verify` in GitHub Actions. The `[deploy]` commit-message
trigger is deliberately absent from this skeleton; Cloud Dataflow runs are out
of scope until that gate exists.

---

---

## Sprint-12 observability slice (T12.5, #80)

### What was added

```
src/
├── test/java/com/enrichmeai/culvert/e2e/
│   ├── RecordingStageMetricsHook.java   serializable recording StageMetricsHook (ServiceLoader)
│   ├── RecordingObservabilityHook.java  serializable recording ObservabilityHook (ServiceLoader)
│   └── ReferenceE2EObservabilityTest.java  3 DirectRunner E2E assertions (the S12 gate)
└── test/resources/META-INF/services/
    ├── com.enrichmeai.culvert.contracts.StageMetricsHook   → RecordingStageMetricsHook
    └── com.enrichmeai.culvert.contracts.ObservabilityHook  → RecordingObservabilityHook
```

### How auto-instrumentation fires (no per-stage boilerplate)

`StageTransform` (the Beam adapter) wraps every stage execution with:
1. SLF4J MDC populated with `run_id`, `stage_name`, `pipeline_id`.
2. A span opened via `ObservabilityHook#span("culvert.stage/<stage-name>")` — closed in
   `finally` even on error.
3. A `StageMetricsHook#recordStageMetrics(StageMetrics)` call in `finally` emitting the
   three Culvert-standard metrics.

The hooks are resolved **worker-side** via `AutoConfig.discover()` (ServiceLoader) after
Beam serializes the `RuntimeContext`. The test-scope `META-INF/services` files make the
recording hooks discoverable by ServiceLoader, so they are picked up automatically — no
`context.register(...)` call needed.

### Observability outputs (live Cloud run — [Joseph runs])

The production hooks (enabled when `data-pipeline-gcp-observability-java` is on the classpath
with a real GCP project configured) emit:

| Signal | Name / format |
|--------|---------------|
| Metric: rows processed | `culvert/rows_processed` (CUMULATIVE INT64, labels: `pipeline_id`, `run_id`, `stage_name`) |
| Metric: stage latency  | `culvert/stage_latency_ms` (GAUGE DOUBLE, same labels) |
| Metric: error count    | `culvert/error_count` (CUMULATIVE INT64, same labels) |
| Trace span             | `culvert.stage/<stage-name>` (attribute: `culvert.run_id`) |
| Log fields (MDC)       | `run_id`, `stage_name`, `pipeline_id` on every log line from within the stage |

To activate the production `CloudMonitoringMetricsHook` and `CloudTraceObservabilityHook`,
add `data-pipeline-gcp-observability-java` to the classpath and set one of:

```bash
# System property (highest priority):
-Dculvert.gcp.project=my-gcp-project

# Environment variable:
export CULVERT_GCP_PROJECT=my-gcp-project

# ADC default (lowest priority — requires gcloud auth application-default login):
# No extra config; ServiceOptions.getDefaultProjectId() is used.
```

### Cloud Logging JSON layout (for structured log ingestion)

To activate GCP Cloud Logging JSON format, place `logback-cloud.xml` on the classpath and
point Logback to it:

```bash
-Dlogback.configurationFile=logback-cloud.xml
```

A reference `logback-cloud.xml` (JSON layout with the three Culvert MDC fields) should be
added to `src/main/resources/` in a future slice. Until then, logs are emitted in the
default Logback format; the MDC keys (`run_id`, `stage_name`, `pipeline_id`) are present
on every log line regardless of layout.

### IAM roles required for the live GCP run ([Joseph runs])

The service account running the Dataflow job must have:

| Role | Purpose |
|------|---------|
| `roles/monitoring.metricWriter` | Write `culvert/*` custom metrics to Cloud Monitoring |
| `roles/logging.logWriter` | Ingest structured JSON logs to Cloud Logging |
| `roles/cloudtrace.agent` | Create and write Cloud Trace spans |

Stub Terraform resource blocks (apply these once the SA is known):

```hcl
# terraform/iam.tf — stub: [Joseph runs terraform apply]
resource "google_project_iam_member" "culvert_metric_writer" {
  project = var.gcp_project
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${var.dataflow_sa_email}"
}

resource "google_project_iam_member" "culvert_log_writer" {
  project = var.gcp_project
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${var.dataflow_sa_email}"
}

resource "google_project_iam_member" "culvert_trace_agent" {
  project = var.gcp_project
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${var.dataflow_sa_email}"
}
```

### Verify metrics and logs after a live run ([Joseph runs])

```bash
# List custom metric time series for the last hour:
gcloud monitoring time-series list \
  --filter='metric.type="custom.googleapis.com/culvert/stage_latency_ms"' \
  --project=my-gcp-project \
  --interval-start-time=$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)

# Query structured logs for a specific run_id:
gcloud logging read \
  'labels.run_id="run-<your-run-id>" AND resource.type="dataflow_step"' \
  --project=my-gcp-project \
  --limit=50

# List Cloud Trace spans for the reference pipeline:
# (Use the Cloud Trace UI or the Cloud Trace API; gcloud does not have a
#  first-class trace-list command.)
# Cloud Console → Cloud Trace → Trace list → filter by span name prefix "culvert.stage/"
```

---

## Module placement notes (for the architect)

This directory is a **standalone Maven module** — it does NOT inherit from
`data-pipeline-libraries-java/pom.xml`. No `<modules>` entry is required in
that parent pom. The pattern mirrors
`deployments/mainframe-segment-transform-java/pom.xml`.

Culvert library coordinates this module depends on:

| Artifact | Version |
|----------|---------|
| `com.enrichmeai.culvert:data-pipeline-core` | `0.1.0` |
| `com.enrichmeai.culvert:data-pipeline-gcp-dataflow` | `0.1.0` |
| `com.enrichmeai.culvert:data-pipeline-orchestration` | `0.1.0` |
