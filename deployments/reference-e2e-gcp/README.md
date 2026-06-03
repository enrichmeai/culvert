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
| S13    | #81 (T13.5) | Cost / FinOps | `FinOpsSink` tagging per stage; `BudgetGovernancePolicy` wiring; budget-ceiling block test. |
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

Expected output after S13 T13.5:
```
Tests run: 8, Failures: 0, Errors: 0, Skipped: 0
BUILD SUCCESS
```

The 8 tests break down as:
- 3 skeleton tests (`ReferenceE2EPipelineTest`) — unchanged from T12.0.
- 3 observability tests (`ReferenceE2EObservabilityTest`) — the S12 slice.
- 2 cost/FinOps tests (`ReferenceE2ECostTest`) — the S13 slice.

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

---

## Sprint-13 cost/FinOps slice (T13.5, #81)

### What was added

```
src/
├── main/java/com/enrichmeai/culvert/e2e/
│   ├── NoOpReadStage.java       updated: emits CostMetrics via context.finops().record()
│   └── NoOpTransformStage.java  updated: emits CostMetrics via context.finops().record()
└── test/java/com/enrichmeai/culvert/e2e/
    ├── RecordingFinOpsSink.java  serializable recording FinOpsSink (ServiceLoader)
    └── ReferenceE2ECostTest.java  2 DirectRunner assertions (the S13 gate)
test/resources/META-INF/services/
    └── com.enrichmeai.culvert.contracts.FinOpsSink  → RecordingFinOpsSink
```

### How cost recording works

Each stage's `execute(RuntimeContext context)` method calls:

```java
CostMetrics metrics = CostMetrics.builder(context.runId())
        .estimatedCostUsd(0.000005)
        .billedBytesScanned(1_000_000L)
        .labels(Map.of("stage", name()))   // required by cost_by_stage query
        .build();

FinOpsTag tag = new FinOpsTag(
        "reference-e2e-gcp", context.environment(),
        "cost-center-reference", "culvert-framework-team",
        context.runId(),
        Map.of("stage", name())             // extra tag label
);

context.finops().record(metrics, tag);
```

In production, replace the stub values with statistics from
`BigQueryCostTracker.trackJob(job, runId, tag)` (in `data-pipeline-gcp-bigquery-java`).

### Budget governance wiring

Register a `BudgetGovernancePolicy` in the context for pre-flight cost control:

```java
BudgetGovernancePolicy budget = new BudgetGovernancePolicy(
        Double.parseDouble(config.getOrDefault("finops.budget.ceiling_usd", "100.0").toString()),
        BudgetViolationMode.WARN   // reference deployment: WARN so the run is never blocked
);
DefaultRuntimeContext ctx = DefaultRuntimeContext.builder(runId, "prod")
        .budgetPolicy(budget)
        .build();

// Pre-flight check before submitting:
CostMetrics estimate = bigQueryCostTracker.estimateDryRun(queryConfig, ctx.runId());
budget.checkBudget(estimate, ctx.runId());  // throws BudgetExceededException if BLOCK mode
```

Config key: **`finops.budget.ceiling_usd`** (default `100.0`). Pass via `Map.of(...)` to
`DefaultRuntimeContext.builder(...).config(...)`. The reference deployment uses `WARN` mode
so the reference run is never blocked; set `BLOCK` in production where runaway cost is
unacceptable.

### The `cost_metrics` table columns

The `BigQueryFinOpsSink` (production) streams one row per `record()` call:

| Column | Type | Source |
|--------|------|--------|
| `system` | STRING | `FinOpsTag.system()` |
| `environment` | STRING | `FinOpsTag.environment()` |
| `cost_center` | STRING | `FinOpsTag.costCenter()` |
| `owner` | STRING | `FinOpsTag.owner()` |
| `tag_run_id` | STRING | `FinOpsTag.runId()` |
| `tag_extra` | RECORD ARRAY | `FinOpsTag.extra()` flattened as `[{key, value}]` |
| `run_id` | STRING | `CostMetrics.runId()` |
| `estimated_cost_usd` | FLOAT64 | `CostMetrics.estimatedCostUsd()` |
| `billed_bytes_scanned` | INT64 | `CostMetrics.billedBytesScanned()` |
| `billed_bytes_written` | INT64 | `CostMetrics.billedBytesWritten()` |
| `billed_bytes_stored` | INT64 | `CostMetrics.billedBytesStored()` |
| `billed_messages_count` | INT64 | `CostMetrics.billedMessagesCount()` |
| `slot_millis` | INT64 | `CostMetrics.slotMillis()` |
| `compute_units` | FLOAT64 | `CostMetrics.computeUnits()` |
| `labels` | RECORD ARRAY | `CostMetrics.labels()` flattened as `[{key, value}]` |
| `timestamp` | TIMESTAMP | `CostMetrics.timestamp()` |

### Four cost-analysis SQL queries (T13.4)

These queries are loadable via `CostAnalysisQueries.loadQuery(name)` from the
`data-pipeline-gcp-bigquery-java` artifact:

#### 1. `cost_by_run` — total cost per pipeline run

```sql
SELECT
    run_id,
    SUM(estimated_cost_usd)      AS total_estimated_cost_usd,
    SUM(slot_millis)             AS total_slot_millis
FROM cost_metrics
GROUP BY run_id
ORDER BY total_estimated_cost_usd DESC;
```

Expected columns: `run_id STRING`, `total_estimated_cost_usd FLOAT64`,
`total_slot_millis INT64`.

#### 2. `cost_by_stage` — cost attributed per stage name

```sql
SELECT
    label.value                  AS stage,
    SUM(estimated_cost_usd)      AS total_estimated_cost_usd
FROM cost_metrics, UNNEST(labels) AS label
WHERE label.key = 'stage'
GROUP BY stage
ORDER BY total_estimated_cost_usd DESC;
```

Expected columns: `stage STRING`, `total_estimated_cost_usd FLOAT64`.
**Requires**: `CostMetrics.labels()` contains `"stage" → stageName` (set in both
`NoOpReadStage` and `NoOpTransformStage`).

#### 3. `top_expensive_runs_7d` — top 10 runs by cost in the last 7 days

```sql
SELECT
    run_id,
    SUM(estimated_cost_usd)      AS total_estimated_cost_usd,
    MIN(`timestamp`)             AS earliest,
    MAX(`timestamp`)             AS latest
FROM cost_metrics
WHERE `timestamp` >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY run_id
ORDER BY total_estimated_cost_usd DESC
LIMIT 10;
```

Expected columns: `run_id STRING`, `total_estimated_cost_usd FLOAT64`,
`earliest TIMESTAMP`, `latest TIMESTAMP`.

#### 4. `budget_breach_log` — all rows where cost exceeded a threshold

```sql
SELECT
    run_id,
    estimated_cost_usd,
    system,
    environment,
    cost_center,
    owner,
    `timestamp`
FROM cost_metrics
WHERE estimated_cost_usd > ?
ORDER BY `timestamp` DESC;
```

Bind the `?` placeholder with the ceiling value before executing.
Expected columns: `run_id STRING`, `estimated_cost_usd FLOAT64`, `system STRING`,
`environment STRING`, `cost_center STRING`, `owner STRING`, `timestamp TIMESTAMP`.

### Production wiring with BigQueryFinOpsSink ([Joseph runs])

```java
// 1. Build the BigQuery client (ADC or service account):
BigQuery bqClient = BigQueryOptions.getDefaultInstance().getService();

// 2. Build the sink pointing at your cost_metrics table:
BigQueryFinOpsSink sink = new BigQueryFinOpsSink(
        bqClient, "my-gcp-project", "finops_dataset", BigQueryFinOpsSink.DEFAULT_TABLE);

// 3. Wire into the context:
DefaultRuntimeContext ctx = DefaultRuntimeContext.builder(runId, "prod")
        .register(FinOpsSink.class, sink)
        .budgetPolicy(new BudgetGovernancePolicy(100.0, BudgetViolationMode.WARN))
        .build();
```

Add `data-pipeline-gcp-bigquery` (`0.1.0`) as a dependency for access to
`BigQueryFinOpsSink`, `BigQueryCostTracker`, and `CostAnalysisQueries`.

### IAM roles required for the live GCP run ([Joseph runs])

| Role | Purpose |
|------|---------|
| `roles/bigquery.dataEditor` | Stream rows into the `cost_metrics` table |
| `roles/bigquery.jobUser` | Run BigQuery dry-run estimates |

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
