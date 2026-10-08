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
| S15    | #83 (T15.3) | CI gating     | `e2e-gate` job in `ci.yml` — structural DirectRunner tests wired as required check. Live-emulator (@Disabled IT) is architect-run. |

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
mvn -pl data-pipeline-core-java,data-pipeline-gcp-dataflow-java,data-pipeline-orchestration-java,\
data-pipeline-gcp-gcs-java,data-pipeline-gcp-bigquery-java,data-pipeline-postgres-java \
    -am -DskipTests install

# Then run all tests (offline is fine; no Docker, no cloud account):
cd ../deployments/reference-e2e-gcp
mvn -o test
```

Build the libraries from this checkout, not from Maven Central: the control-plane slice needs
the readiness gate (#230), which is on `main` and not in the 0.4.0 release.

Expected output after the control-plane slice (#231):
```
Tests run: 33, Failures: 0, Errors: 0, Skipped: 1
BUILD SUCCESS
```

The 33 tests break down as:
- 3 skeleton tests (`ReferenceE2EPipelineTest`) — unchanged from T12.0.
- 3 launcher tests (`ReferenceE2EMainTest`).
- 3 observability tests (`ReferenceE2EObservabilityTest`) — the S12 slice.
- 2 cost/FinOps tests (`ReferenceE2ECostTest`) — the S13 slice.
- 5 DQ tests (`ReferenceE2EDqTest`, 1 `@Disabled` = Skipped) — the S14 slice.
- 17 control-plane tests (`ControlPlaneRunTest` 11, `KilledWorkerTest` 2, `ReferenceDagTest` 4) —
  the #231 slice, on an embedded PostgreSQL 16.

**CI gate (S15, #83, now wired):**

The GitHub Actions `ci.yml` workflow now contains an `e2e-gate` job (Job 5) that:

1. Checks out the repo and sets up JDK 21 (temurin).
2. Installs the five Culvert library artifacts into the runner's `~/.m2` via
   `mvn --batch-mode -pl data-pipeline-core-java,...-gcp-gcs-java -am -DskipTests install`
   (the deployment is standalone and its deps are not published to Maven Central).
3. Runs `mvn --batch-mode test` in `deployments/reference-e2e-gcp/`.
4. Is wired as a required check via the `ci-gate` aggregator job.

Expected: ~13 tests, 1 skipped (`@Disabled` live-GCS skeleton), `BUILD SUCCESS`.
No Docker is required for this tier — all tests run on DirectRunner + in-memory
recording hooks.

**Architect-run box (open until Joseph confirms):** The `liveGcsQuarantineIT_skeleton`
test in `ReferenceE2EDqTest` is intentionally `@Disabled`. Enabling it requires Docker
(FakeGCS + BigQuery emulator via Testcontainers) and is gated as a live-CI run that
Joseph confirms manually before the PR merges.

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

---

---

## Sprint-14 data-quality slice (T14.5, #82)

### What was added

```
src/
├── main/java/com/enrichmeai/culvert/e2e/dq/
│   └── InvalidRowAdapter.java          seam adapter: InvalidRow<R> → FailedRowRecord
└── test/java/com/enrichmeai/culvert/e2e/dq/
    ├── InMemoryBlobStore.java           stub BlobStore (no live GCS)
    ├── StubJobControlRepository.java    stub JobControlRepository (no live BigQuery)
    └── ReferenceE2EDqTest.java          4 DQ assertions + 1 @Disabled live-GCS skeleton
```

### Schema under test

```
EntitySchema "caseRecord"
  id       STRING  REQUIRED              — MISSING_REQUIRED if absent
  score    FLOAT64 REQUIRED [0.0, 100.0] — OUT_OF_RANGE if > 100
  email    STRING  NULLABLE  (PII)       — masked to "***" on valid rows
```

### DQ stage config

```java
// PII masking policy (structural — column-name match, no cloud SDK)
PiiMaskingGovernancePolicy piiPolicy = PiiMaskingGovernancePolicy.builder()
        .piiColumns(Set.of("email"))
        .defaultMaskingPolicy(new MaskingPolicy(MaskingStrategy.FULL, "***", ""))
        .build();

// DataQualityTransform wired with schema + masking policy
DataQualityTransform<Map<String, Object>> dq =
        new DataQualityTransform<>(CASE_SCHEMA, Function.identity(), piiPolicy);
```

The `rowAccessor` is `Function.identity()` because `R = Map<String,Object>` in the
reference pipeline. For any other row type supply the accessor that extracts the
field map.

### Quarantine path convention

Failed rows (those producing an `InvalidRow`) are adapted via `InvalidRowAdapter`
and passed to `QuarantineHandler`:

```java
List<FailedRowRecord> records = InvalidRowAdapter.adaptAll(invalidRows, Function.identity());
QuarantineHandler handler = new QuarantineHandler(blobStore, jobRepo, errorPrefix);
handler.writeFailures(runId, records);
```

**Stub (dev-agent run):** `InMemoryBlobStore` backed by a `LinkedHashMap`.
No credentials, no network.

**Live GCS URI pattern (architect/prod run):**
```
gs://<error-bucket>/errors/<pipeline-id>/quarantine/<runId>/<yyyyMMdd'T'HHmmssSSS'Z'>.jsonl
```
Example:
```
gs://culvert-errors-prod/errors/reference-e2e-gcp/quarantine/run-abc/20260601T120000000Z.jsonl
```
The `errorPathPrefix` passed to `QuarantineHandler` should be:
```
gs://<error-bucket>/errors/<pipeline-id>
```
No trailing slash — the handler normalises it.

Each quarantine file is newline-delimited JSON (NDJSON). One record per failed row:
```json
{"row":{"id":"case-003","score":150.0,"email":"carol@example.com"},"violations":[{"field":"score","rule":"Field 'score' value 150.0 is outside range [0.0, 100.0]"}]}
```

### The InvalidRow → FailedRowRecord seam adapter

`T14.1` (`InvalidRow<R>`) and `T14.2` (`FailedRowRecord`) were built against
assumed shapes of each other. The bridge is in `InvalidRowAdapter` (main scope,
deployment module):

```java
// Single row
FailedRowRecord adapted = InvalidRowAdapter.adapt(invalidRow, Function.identity());

// Batch
List<FailedRowRecord> records = InvalidRowAdapter.adaptAll(invalidRows, rowToMap);
```

**R-vs-Map reconciliation:** `InvalidRow<R>` stores the row as generic `R`; it
does not expose a `Map<String,Object>`. The adapter re-applies the same
`Function<R, Map<String,Object>>` accessor (the same one `DataQualityTransform` was
built with) to project `R` into its field map. `FailedRowRecord.rowContent()` returns
that map.

**Violation mapping:**
- `FieldViolation.fieldName()` → `ViolationDescriptor.field()`
- `FieldViolation.detail()` → `ViolationDescriptor.rule()`

(`violationKind` is the structural enum category; the seam interface surfaces the
human-readable rule message instead.)

### Retry steps

```java
// 1. Seed a FAILED job (job already in DB after a real pipeline run)
RetryOrchestrator orchestrator = new RetryOrchestrator(jobRepo);

// 2. Prepare retry: cleanup stale rows + markRetrying
RetryOrchestrator.RetryResult result = orchestrator.prepareRetry(runId);
// result.rowsCleaned() == N rows removed from targetTable WHERE _run_id = runId
// result.retryCount()  == previous count + 1

// 3. Re-submit the pipeline (same runId, clean table)
// ... pipeline runs, inserts fresh rows ...

// 4. Idempotency guard: calling prepareRetry again on an ALREADY-RETRYING job
//    does NOT double-increment. rowsCleaned() == 0.
```

Every target table written by the pipeline must have a `_run_id STRING` column
(populated at load time). `cleanupPartialLoad` issues
`DELETE FROM <table> WHERE _run_id = @run_id` against that column.

### What the tests assert

| Test | Asserts |
|------|---------|
| `mixedValidityRowSet_...` | 1 valid row reaches success path; 2 invalid rows written to quarantine stub; `markFailed` called once with `DQ_VALIDATION_FAILURE` and the quarantine URI |
| `piiMasking_...` | Valid row's `email` field is masked to `"***"` by `DataQualityTransform` before it exits the DQ stage; non-PII fields unchanged |
| `retry_cleanupPartialLoad_...` | First `prepareRetry` removes 2 stale rows + increments counter to 1; re-run inserts 2 fresh rows; second `prepareRetry` on RETRYING job is idempotent (counter stays 1, 0 rows cleaned) |
| `seamAdapter_invalidRowAdaptsToFailedRowRecord_roundTrip` | `InvalidRow<Map>` produced by real DQ engine adapts to `FailedRowRecord`; `rowContent()` matches original map; `violations()` carry identical field+rule pairs |
| `liveGcsQuarantineIT_skeleton` | `@Disabled` — live-GCS emulator skeleton; enable in Sprint-15 T15.3 |

### Build commands (after this slice)

```bash
# Prerequisites: install framework libraries
cd data-pipeline-libraries-java
mvn -o -pl data-pipeline-core-java,data-pipeline-gcp-gcs-java,data-pipeline-gcp-bigquery-java \
    -am -DskipTests install

# Run all tests (offline, no live GCP):
cd ../deployments/reference-e2e-gcp
mvn -o test
```

Expected output after S14 T14.5:
```
Tests run: 13, Failures: 0, Errors: 0, Skipped: 1
BUILD SUCCESS
```

The 13 tests break down as:
- 3 skeleton tests (`ReferenceE2EPipelineTest`)
- 3 observability tests (`ReferenceE2EObservabilityTest`)
- 2 cost/FinOps tests (`ReferenceE2ECostTest`)
- 4 DQ tests (`ReferenceE2EDqTest`, 1 `@Disabled` = Skipped)

**Live E2E run (S15 T15.3, architect-run):** The `@Disabled`
`liveGcsQuarantineIT_skeleton` test in `ReferenceE2EDqTest` will be enabled in
Sprint-15 T15.3 when the Testcontainers-based GCS emulator gate is green in CI.
Until then, the full quarantine path is validated structurally via the in-memory
stubs above.

---

## Control-plane slice (#231, epic #188 Phase 3)

The reference pipeline runs on the control plane: PostgreSQL job control, stage claims, stage and
readiness gates, and a capped fan-out. The stages still do trivial I/O (a count over `--records`
records); the control-plane work in each one is real. This is the shape the Phase 3 proof harness
(#232) runs its scenarios against, and the real-GCP run (#234) deploys.

### The pipeline shape

```
orders     load ──► validate ──► publish
customers  load ──► validate ──► publish      at most --max-concurrency units at once (default 2)
products   load ──► validate ──► publish
```

Each stage of each unit, in order:

1. **Claim** `StageKey(unit, stage, period)` with `StageClaim.tryClaim`, without waiting.
   - `Completed`: the stage is skipped (`SKIPPED`); it never runs twice.
   - `Held`: another worker has it. The unit stops (`HELD`) and the run exits 2.
2. **Gate**: re-check the task's gate with `StageGate`, from the same `DagSpec` the DAG is rendered
   from. `validate` waits on `load` completed; `publish` waits on `load` and `validate` completed
   and on the unit's input being ready. Closed: the claim is released without completing
   (`GATE_CLOSED`), the unit stops, and the run exits 1.
3. **Work**, with the input's readiness events. Each unit expects one input, `<unit>.raw`, declared
   with `InputReadiness.declareExpected` at the start of every run.
   - `load` publishes the input as produced.
   - `validate` rules on the standing attempt: validated, or failed. A failed attempt can only be
     answered by a declared retry, so re-validating after a failure publishes a new attempt naming
     the failed one (`retryOf`).
4. **Complete** the claim (`DONE`).

**Job control:** each unit that acquires a stage records one run in `PostgresJobControlRepository`.
- It is created at the unit's first acquired stage.
- It ends `succeeded` with the record count, or failed with `GATE_CLOSED`, `STAGE_HELD`,
  `INPUT_INVALID`, `INPUT_MISSING` or `INPUT_NOT_DECLARED`. Any other error (a store or the gate
  throwing) fails it with `STAGE_ERROR` before the error is rethrown, so a run is never left
  `running` by an error.
- A killed worker is the exception: nothing is left to record anything, so its run stays
  `running`. The re-run opens a new run. Proof 7 (#232) reads the ledger with that row in it.
- A unit with nothing to do (every stage already completed, or its first stage held) writes no row.

### Running it

```bash
export CULVERT_POSTGRES_URL=jdbc:postgresql://localhost:5432/culvert
export CULVERT_POSTGRES_USER=culvert CULVERT_POSTGRES_PASSWORD=...   # if the server needs them
# The bigquery module on the classpath also offers a JobControlRepository; choose PostgreSQL:
export CULVERT_JOBCONTROLREPOSITORY_PROVIDER=PostgresJobControlRepository

java -cp ... com.enrichmeai.culvert.e2e.controlplane.ControlPlaneMain \
    --apply-ddl --period=2026-10-06 --units=orders,customers,products --max-concurrency=2
```

It prints one line per stage (`orders/load DONE claimant=host:4242 run=... records=5`) and exits
0 when done, 1 if a stage failed or a gate was closed, 2 if a stage was held, and 64 on a bad
argument.

| Setting | Default | What it does |
|---|---|---|
| `CULVERT_POSTGRES_URL` | *(required)* | The `jdbc:postgresql://` URL. All three stores read it (`-Dculvert.postgres.url` also works). |
| `CULVERT_POSTGRES_USER`, `CULVERT_POSTGRES_PASSWORD` | none | Credentials, if the server needs them. |
| `CULVERT_JOBCONTROLREPOSITORY_PROVIDER` | none | Needed only when more than one `JobControlRepository` is discovered; `AutoConfig` refuses to guess. |
| `--apply-ddl` | off | Apply the `job_control.sql` that `data-pipeline-postgres` ships before running. It is idempotent. |
| `--period` | today (UTC) | The period, an ISO date. It is also the job-control `extract_date`. |
| `--units` | `orders,customers,products` | The units of the fan-out. |
| `--stages` | `load,validate,publish` | Run only these, as a scheduler firing a task early or alone would. |
| `--max-concurrency` | `2` | At most this many units at once, and `max_active_tasks` in the DAG (#199). |
| `--records` | `5` | Records per stage. |
| `--claimant` | `host:pid` | The name each claim and completion records. |

`ControlPlane.discover` refuses to run if any of the three stores is missing: a run without
claims could double-start a stage, and one without readiness could publish an input that never
validated.

### Infrastructure for the real-GCP run (#233)

[`terraform/control-plane/`](terraform/control-plane/README.md) creates the infrastructure for the
real-GCP run: Cloud SQL (PostgreSQL 16, private IP, with the claim session timeout set), Composer 2
and the Dataflow service account. It is a module of this deployment's Terraform root, off unless
`control_plane.enabled = true`. The founder applies it; no apply runs from CI or a session.

### Fault switches (for #232)

| Switch | What it does | Proof it serves |
|---|---|---|
| `--fault.kill-after=N` | Halt the JVM (exit 137, no cleanup) after `N` records of `--fault.kill-stage`, in the first unit that gets there. `N` above `--records` is refused, since the kill could never happen. The PostgreSQL session dies with it, so the server releases the claim. | 2, 3 |
| `--fault.kill-stage=load\|validate\|publish` | Where the kill happens. Default `validate`, stage 2 of 3. | 2 |
| `--fault.fail-validation=unit[,unit]` | Those units' validation fails: the input is recorded failed and the unit's run fails. It only acts when `validate` runs: a unit whose `validate` is already completed skips it, and an input already validated is not ruled on again. | 5 |
| `--fault.duplicate-trigger` | Start the whole run twice at once, as `<claimant>#1` and `<claimant>#2`. Each trigger has its own `--max-concurrency` pool, as two scheduler triggers would, so up to twice that many units run at once in this mode. | 1 |

### The rendered DAG

`dags/reference_e2e_control_plane.py` is the same spec rendered through `ComposerDagRenderer` with
job control, both gates and `max_active_tasks=2`. `ReferenceDagTest` renders it again and fails on
any difference; regenerate it with `mvn -o test -Dculvert.e2e.regenerateDag=true`.

- **The stores.** The DAG takes its three stores from a Python module,
  `reference_e2e_control_plane_stores` (`job_control()`, `stage_claim()`, `input_readiness()`).
  Culvert ships no Python `StageClaim` (#196) or `InputReadiness`, so the deployment must supply
  that module on the Airflow workers (#234). This repository does not ship one.
- **Checked in Airflow 2.9.3.** With a stub stores module, the DAG imports with no errors (9 tasks,
  `max_active_tasks=2`). The `customers__publish` callable refused to run while its stages were not
  completed, then while its input was failed, and ran once both were open.
- **The task bodies are stubs.** Each callable checks its gates and wraps job control around
  `pass`: it does not claim or complete a stage. Until the stages run in Airflow (#234), nothing on
  the Airflow side writes the completions the gates wait on.
- **Job control differs from the Java runner.** The DAG's job-control wiring is the renderer's
  (T11.3): one run per DAG run, keyed by Airflow's `run_id` and created by the first task. The Java
  runner records one run per unit.

### What the tests prove (embedded PostgreSQL 16, no Docker)

| Test | What it shows, read from the control store's own tables |
|---|---|
| `everyStageOfEveryUnitRunsOnce...` | 9 completions, 3 `succeeded` runs with 15 records each, every unit ready. |
| `aSecondRunSkipsEveryCompletedStage...` | A re-run does nothing and writes no job-control row. |
| `aStageHeldByAnotherClaimant...` | A held `load` stops that unit only; the run exits 2. |
| `aDuplicateTriggerDoesEachStageExactlyOnce` | Two triggers at once: each stage `DONE` once, each input produced once. |
| `publishFiredEarlyIsStoppedByItsGate...` | `publish` alone: closed, naming both stages and the missing input; no completion, no run. |
| `aFailedValidationKeepsThatUnitShut...` | The failed input keeps `publish` shut. The re-run skips `load`, re-validates as a declared retry, and publishes. |
| `aKillThatCouldNeverFireIsRefused`, `aKillAfterTheLastRecord...` | `--fault.kill-after` above `--records` is refused; equal to it, the kill still fires before the stage is recorded. |
| `anUnexpectedStoreErrorFails...` | A store that throws leaves the run `failed` with `STAGE_ERROR` and the claim released, not completed. |
| `aWorkerKilledInStageTwoResumes...` | A real JVM halted in `validate`: the re-run skips `load`, redoes `validate` from its start, publishes once. The input was produced once. |

Each new rule was shown red first, by breaking it and re-running the suite:
- never completing a claim: 7 failures;
- not checking the gate: 2;
- not declaring the retry: 1;
- letting a held stage carry on: 2;
- ignoring the kill switch: 1;
- a drifted DAG: 1;
- ignoring `--fault.fail-validation`: 1;
- not failing the run on an unexpected error: 1;
- accepting a kill that can never fire: 1.

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
| `com.enrichmeai.culvert:data-pipeline-gcp-gcs` | `0.1.0` |
| `com.enrichmeai.culvert:data-pipeline-gcp-bigquery` | `0.1.0` |
