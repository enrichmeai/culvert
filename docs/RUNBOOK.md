# Culvert GCP Operational Runbook

**Status:** Sprint 16 (T16.3, #107) · **Audience:** On-call engineer, SRE  
**Cross-references:**
- Architecture overview: [`docs/framework-evolution/10-architecture.md`](framework-evolution/10-architecture.md)
- Reference deployment: [`deployments/reference-e2e-gcp/`](../deployments/reference-e2e-gcp/)
- SLO/Alerting companion: [`docs/SLO_ALERTING.md`](SLO_ALERTING.md)

---

## 1. Pipeline run flow

A Culvert GCP pipeline run is initiated by an Airflow / Cloud Composer DAG and flows through three layers. The canonical diagram is in [`10-architecture.md § 6`](framework-evolution/10-architecture.md).

```
config (system.yaml)
        │
        ▼
Pipeline (stages + edges)
        │  PipelineToDagSpec → DagSpec → AirflowDagRenderer / ComposerDagRenderer
        │  (produces the Cloud Composer DAG; schedules run via Airflow task executor)
        ▼
DataflowPipeline.buildBeam()        ← topological stage ordering
        │
        ▼  per stage (wrapped in Beam PTransform by StageTransform)
StageTransform.ExecuteStageFn
        │  resolves all adapters worker-side via DefaultRuntimeContext / ServiceLoader
        │  auto-emits: trace span (CloudTraceObservabilityHook) + stage metrics (CloudMonitoringMetricsHook)
        │  populates MDC: run_id, stage_name, pipeline_id on every log line
        ▼
PipelineStage.execute(context)
        │  stages call: Source → DataQualityTransform → Sink / Warehouse / BlobStore
        │  optional side effects: FinOpsSink.record(), AuditEventPublisher.publish()
        ▼
JobControlRepository (BigQueryJobControlRepository)
        │  DAG task calls: createJob → updateStatus(RUNNING) → updateStatus(SUCCEEDED)
        │  on failure:     markFailed / markRetrying
```

**Key classes:**

| Class | Module | Role |
|---|---|---|
| `DataflowPipeline` | `data-pipeline-gcp-dataflow-java` | Builds the Beam graph in topological order |
| `StageTransform` | `data-pipeline-gcp-dataflow-java` | Adapts each `PipelineStage` into a `PTransform<PBegin, PDone>`; provides auto-instrumentation |
| `DefaultRuntimeContext` | `data-pipeline-core-java` | DI container; resolves adapters worker-side via ServiceLoader; `registry` is `transient` (T10.6) |
| `BigQueryJobControlRepository` | `data-pipeline-gcp-bigquery-java` | Persists job state (`pipeline_jobs` table) via parameterised BigQuery DML |
| `PipelineToDagSpec` | `data-pipeline-orchestration-java` | Translates a `Pipeline` graph into a `DagSpec` (Airflow/Composer shape) |

---

## 2. Failure detection

### 2.1 Job-control table

`BigQueryJobControlRepository` is the primary failure signal. Every DAG task writes to `<project>.job_control.pipeline_jobs`.

**Query failed runs for a date:**
```sql
SELECT run_id, pipeline_name, failure_stage, error_code, error_message,
       error_file_path, error_count, retry_count, completed_at
FROM `<project>.job_control.pipeline_jobs`
WHERE system_id = '<system>'
  AND extract_date = '<YYYY-MM-DD>'
  AND status = 'FAILED'
ORDER BY completed_at DESC;
```

Relevant `JobStatus` values: `CREATED` · `RUNNING` · `SUCCEEDED` · `FAILED` · `RETRYING`

The `failure_stage` column maps to `FailureStage` enum values (e.g. `VALIDATION`, `LOAD`, `TRANSFORM`).

### 2.2 Quarantine path (DQ failures)

When `DataQualityTransform` produces invalid rows, `QuarantineHandler` writes a NDJSON file to GCS and calls `BigQueryJobControlRepository.markFailed()` with the quarantine URI:

```
gs://<error-bucket>/errors/<pipeline-id>/quarantine/<runId>/<yyyyMMdd'T'HHmmssSSS'Z'>.jsonl
```

The quarantine URI is stored in `error_file_path` in `pipeline_jobs`. The `error_code` is always `DQ_VALIDATION_FAILURE`.

**Query quarantine events:**
```sql
SELECT run_id, error_file_path, error_count, completed_at
FROM `<project>.job_control.pipeline_jobs`
WHERE error_code = 'DQ_VALIDATION_FAILURE'
  AND extract_date = '<YYYY-MM-DD>';
```

**Inspect a quarantine file (bad rows + violations):**
```bash
gsutil cat gs://<error-bucket>/errors/<pipeline-id>/quarantine/<runId>/<ts>.jsonl | head -20
```

Each NDJSON line:
```json
{"row":{"id":"case-003","score":150.0},"violations":[{"field":"score","rule":"Field 'score' value 150.0 is outside range [0.0, 100.0]"}]}
```

### 2.3 Audit events

`BigQueryAuditEventPublisher` writes one row per event to `<project>.job_control.audit_events` — the ten columns of `docs/CONTRACT.md` §4. Event-specific detail (record counts, error messages) lives in the `payload` JSON column, not in bare columns.

**A failed write is never silent.** How it surfaces depends on the `event_kind` (spine AD-5):

| Event class | `event_kind` | On write failure |
|---|---|---|
| Run-level | `RUN_START`, `RUN_END`, `ERROR_RAISED`, `RECONCILIATION`, `RETRY_ATTEMPTED` | **Throws — the pipeline fails.** These events *are* the run's state; continuing without one is how a run reports success it never had. |
| Aggregate | `RECORD_VALIDATED`, `RECORD_REJECTED` | Logged at `ERROR` with the full event, counted, ingestion continues. |

**Query recent audit events for a run:**
```sql
SELECT event_ts, event_kind, entity, payload, producer, contract_version
FROM `<project>.job_control.audit_events`
WHERE run_id = '<run-id>'
ORDER BY event_ts;
```

### 2.4 Cloud Monitoring metrics

`CloudMonitoringMetricsHook` (S12, `data-pipeline-gcp-observability-java`) emits three custom metrics to Cloud Monitoring via `MetricServiceClient.createTimeSeries` after each stage completes:

| Metric type | Kind | Value type | Labels |
|---|---|---|---|
| `custom.googleapis.com/culvert/rows_processed` | CUMULATIVE | INT64 | `pipeline_id`, `run_id`, `stage_name` |
| `custom.googleapis.com/culvert/stage_latency_ms` | GAUGE | DOUBLE | `pipeline_id`, `run_id`, `stage_name` |
| `custom.googleapis.com/culvert/error_count` | CUMULATIVE | INT64 | `pipeline_id`, `run_id`, `stage_name` |

**Important caveat — `rows_processed`:** `StageTransform.ExecuteStageFn` auto-emits `rows_processed = 0` (the documented sentinel `ROWS_PROCESSED_UNKNOWN`) because `PipelineStage.execute()` is `void` and cannot return an element count. Real row counts are emitted only by stages that call the metrics hook directly (e.g., `DataQualityTransform` emits the actual count after its iterator is exhausted). Do not rely on auto-instrumented `rows_processed` for throughput alerting on stages that do not implement this explicitly.

**List metric time series (live run):**
```bash
gcloud monitoring time-series list \
  --filter='metric.type="custom.googleapis.com/culvert/stage_latency_ms"' \
  --project=<project> \
  --interval-start-time=$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)
```

`CloudMonitoringMetricsHook` swallows Cloud Monitoring API errors (logged at WARN) so pipeline execution is never interrupted by monitoring backend failures. The in-process `monitoringFailureCount()` counter is not itself pushed to Cloud Monitoring.

### 2.5 Trace spans

`CloudTraceObservabilityHook` (`data-pipeline-gcp-observability-java`) opens a trace span named `culvert.stage/<stage-name>` for every stage execution. The span carries the attribute `culvert.run_id`. View spans in Cloud Trace → Trace list → filter by span name prefix `culvert.stage/`.

### 2.6 Structured logs

`StageTransform.ExecuteStageFn` populates the SLF4J MDC (mirroring `CulvertMdcPopulator`) with three keys before each stage invocation:

| MDC key | Value |
|---|---|
| `run_id` | Pipeline run identifier |
| `stage_name` | Name of the executing stage |
| `pipeline_id` | Pipeline identifier |

All log lines emitted within a stage execution carry these keys automatically. When a Cloud Logging JSON encoder (e.g. `logback-cloud.xml`) is active on the classpath, the keys surface as top-level JSON fields in Cloud Logging. Without a JSON encoder, they appear in the default Logback format. The MDC keys are populated regardless of the log layout; the JSON encoder is a separate `needs-engineer` wiring step.

**Query structured logs for a run:**
```bash
gcloud logging read \
  'labels.run_id="<run-id>" AND resource.type="dataflow_step"' \
  --project=<project> \
  --limit=50
```

### 2.7 Budget breach detection

`BudgetGovernancePolicy` (`data-pipeline-core-java`) enforces a cost ceiling before a pipeline is submitted:

- **`BLOCK` mode:** throws `BudgetExceededException` — the run does not start. Look for this exception in the DAG task log.
- **`WARN` mode:** logs a `WARNING` via `java.util.logging` and continues.

A budget breach is NOT a Cloud Monitoring metric. Detect breaches via the `budget_breach_log` BigQuery query over the `cost_metrics` table:

```sql
SELECT run_id, estimated_cost_usd, system, environment, cost_center, owner, timestamp
FROM cost_metrics
WHERE estimated_cost_usd > <ceiling_usd>
ORDER BY timestamp DESC;
```

---

## 3. Retry / idempotent re-run

### 3.1 Retry flow

`RetryOrchestrator` (S14, `data-pipeline-gcp-bigquery-java`) sequences the full retry lifecycle:

```
1. getJob(runId)                          — load current job state from BigQuery
2. if status == RETRYING → return (idempotency guard, no double-increment)
3. if status not in {CREATED, RUNNING, FAILED} → throw, delete nothing
   -- eligibility BEFORE cleanup: a SUCCEEDED run must not have its rows removed
4. if targetTable present → cleanupPartialLoad(runId, tableId)
   -- DELETE FROM <table> WHERE _run_id = @run_id
5. markRetrying(runId, retryCount + 1)    — sets status=RETRYING, bumps retry_count
6. return RetryResult(runId, retryCount, rowsCleaned)
```

Caller re-submits the pipeline with the same `runId` after `prepareRetry()` returns.

### 3.2 Schema contract for idempotency

Every target table written by a Culvert pipeline **must** include a `_run_id STRING` column populated at load time. `cleanupPartialLoad` issues:

```sql
DELETE FROM `<tableId>` WHERE _run_id = @run_id
```

Without this column, `cleanupPartialLoad` cannot remove partial rows from a failed run, making re-runs non-idempotent.

### 3.3 Idempotency guard

Calling `RetryOrchestrator.prepareRetry()` on a job already in `RETRYING` status returns immediately without calling `markRetrying` again. This prevents counter double-increment when the orchestrating DAG retries the task itself.

A job in a status that may not be retried at all — `SUCCEEDED` or `CANCELLED` — raises `IllegalStateException` **before** `cleanupPartialLoad` runs, so an ineligible retry leaves both the target table and the job record untouched. Retrying a run that already succeeded is precisely how a re-run duplicates data.

### 3.3.1 The job-control ledger is append-only, and every write is conditional

Since Sprint 23, `BigQueryJobControlRepository` issues **no `UPDATE` and no `DELETE`** against `job_control.pipeline_jobs`. The table holds one row per state change, not one row per run. Each state change reads the run's current projected state, carries it forward, applies its change and `INSERT`s a new row.

| Call | Condition, checked before the append | On violation |
|------|--------------------------------------|--------------|
| `createJob` | `MERGE ... WHEN NOT MATCHED THEN INSERT` — the `runId` must have no rows at all | `IllegalStateException` — the `runId` already exists |
| `updateStatus`, `markFailed`, `markRetrying` | the run's **projected** status must be one of the allowed prior states | `IllegalStateException` naming the actual status, or reporting that no such run exists |
| `updateCostMetrics` | the run must exist | `IllegalStateException` — no such run |

Allowed prior states: `RUNNING` from `CREATED`/`RETRYING`; `SUCCEEDED` from `RUNNING`; `FAILED` from `CREATED`/`RUNNING`/`RETRYING`/`FAILED`; `RETRYING` from `CREATED`/`RUNNING`/`FAILED`; `CANCELLED` from `CREATED`/`RUNNING`/`RETRYING`. `FAILED` → `FAILED` is allowed on purpose: `QuarantineHandler` marks a run failed when it quarantines rows, and the ingestion runner's reconciliation check can then mark the same run failed again with a more specific error code — but see the projection rule below, which decides **which** of the two failures an operator reads.

An operator seeing `IllegalStateException: ... expected one of [...]` in a task log is looking at a transition that would previously have passed silently against the wrong row — or against no row at all.

### 3.3.2 Querying the ledger: use the projection, not the raw table

Because a run has many rows, **`SELECT * FROM pipeline_jobs WHERE run_id = ...` returns a history, not a state.** The repository ranks the rows and keeps one per `run_id`; an ad-hoc query must do the same or it will read a superseded state:

```sql
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY run_id
    ORDER BY
      CASE WHEN status IN ('succeeded','failed','cancelled') THEN 0 ELSE 1 END,
      CASE WHEN status IN ('succeeded','failed','cancelled') THEN updated_at END ASC,
      updated_at DESC
  ) AS rn FROM `<project>.job_control.pipeline_jobs`
) SELECT * FROM ranked WHERE rn = 1 AND run_id = '<run-id>';
```

A terminal row (`succeeded`, `failed`, `cancelled`) beats a non-terminal one; among terminal rows the **earliest** wins; with no terminal row the latest wins. Two operational consequences:

- **The first terminal state a run reaches is the one it keeps.** A `failed` row appended after a run succeeded does not make the run failed, and therefore does not make it retryable. That is deliberate: a retry runs `cleanupPartialLoad`, a `DELETE` against the target table, and a late failure flipping a green run would delete the data that run had just loaded. If you see contradictory rows for one run, the projection is the answer and the extra rows are evidence of the writer that produced them.
- **`ORDER BY updated_at DESC LIMIT 1` is wrong** for the same reason. Any dashboard, DAG or script doing that against `pipeline_jobs` is reading recency, which is exactly what this design rejects.

### 3.4 Tracking retry state

```sql
-- Check retry progress
SELECT run_id, status, retry_count, error_code, error_message, updated_at
FROM `<project>.job_control.pipeline_jobs`
WHERE run_id = '<run-id>';
```

`BigQueryJobControlRepository.markRetrying(runId, retryCount)` appends a row with `status = 'retrying'` and a fresh `updated_at`. When the re-run succeeds, `updateStatus(runId, SUCCEEDED, totalRecords)` appends another with `completed_at` stamped. Neither overwrites anything — query through the projection in §3.3.2 to see the current state.

### 3.5 Cost metrics on re-run

`BigQueryJobControlRepository.updateCostMetrics(runId, estimatedCostUsd, billedBytesScanned, billedBytesWritten)` appends a row carrying the FinOps columns and the run's current status. Nothing is overwritten, and on a retry the prior run's cost estimate stays in the ledger alongside the new one.

**Call it before the run reaches a terminal state.** Under §3.3.2's projection an appended row is only read back if it wins the ranking; a cost row appended after the run finished carries the run's terminal status with a later `updated_at`, so the original terminal row keeps winning and the figures do not read back through `getJob`. The row is still in the ledger and a direct query over the raw table finds it.

---

## 4. Observability locations

| Signal | Where it lives | How to access |
|---|---|---|
| Job state / failures | BigQuery `<project>.job_control.pipeline_jobs` | SQL query (see §2.1) |
| DQ quarantine files | GCS `gs://<error-bucket>/errors/<pipeline-id>/quarantine/<runId>/` | `gsutil cat` or Cloud Console |
| Audit events | BigQuery `<project>.job_control.audit_events` | SQL query (see §2.3) |
| Custom metrics | Cloud Monitoring `custom.googleapis.com/culvert/*` | `gcloud monitoring time-series list` or Cloud Console |
| Trace spans | Cloud Trace, span name prefix `culvert.stage/` | Cloud Trace UI |
| Structured logs | Cloud Logging, field `labels.run_id` | `gcloud logging read` |
| Cost data | BigQuery `<project>.finops_dataset.cost_metrics` | SQL (see §2.7 and reference-e2e-gcp README §Sprint-13) |

**IAM roles required for live GCP runs** (set once per Dataflow service account):

| Role | Purpose |
|---|---|
| `roles/monitoring.metricWriter` | Write `culvert/*` custom metrics |
| `roles/logging.logWriter` | Ingest structured logs to Cloud Logging |
| `roles/cloudtrace.agent` | Write Cloud Trace spans |
| `roles/bigquery.dataEditor` | Stream rows into `cost_metrics`, `audit_events` |
| `roles/bigquery.jobUser` | Run BigQuery dry-run estimates and DML |

---

## 5. Common-failure playbook

### 5.1 DQ quarantine — invalid rows routed to dead letter

**Symptom:** `pipeline_jobs.status = 'FAILED'`, `error_code = 'DQ_VALIDATION_FAILURE'`

**Steps:**
1. Note `error_file_path` from `pipeline_jobs` — this is the quarantine GCS URI.
2. Inspect the quarantine NDJSON file to identify which rows failed and which `violation` rules triggered (see §2.2).
3. Determine if the data is fixable upstream (e.g. schema mismatch, range violation).
4. If re-processable: fix the source data; call `RetryOrchestrator.prepareRetry(runId)` to clean the partial load; re-submit the pipeline (§3).
5. If expected bad data: update the `DataQualityTransform`'s `EntitySchema` range or mode, or raise a data-provider issue.

### 5.2 Budget breach — run blocked by BudgetGovernancePolicy

**Symptom (BLOCK mode):** DAG task fails with `BudgetExceededException` in the task log. Run never starts.

**Steps:**
1. Check the DAG task log for the exception message — it includes the projected cost and the configured ceiling.
2. Query the cost estimate that triggered it: check `cost_metrics` or the dry-run result.
3. If the run is genuinely large: raise the `finops.budget.ceiling_usd` config value and re-trigger the DAG.
4. If the estimate is wrong: investigate `BigQueryCostTracker.estimateDryRun()` — the dry-run `getTotalBytesBilled()` may fall back to `getTotalBytesProcessed()` (see BigQueryCostTracker javadoc); verify the query configuration.
5. To audit cost ceiling breaches historically, run the `budget_breach_log` query (see §2.7).

**Symptom (WARN mode):** Pipeline ran. Check `cost_metrics` for actual cost and compare to the ceiling. Update the ceiling or switch to BLOCK mode if runaway spending is a risk.

### 5.3 Partial load — pipeline failed mid-write

**Symptom:** `pipeline_jobs.status = 'FAILED'`, `failure_stage = 'LOAD'` or `'TRANSFORM'`; target table may contain rows from the failed run.

**Steps:**
1. Confirm `targetTable` is set in `pipeline_jobs` for the `run_id`.
2. Call `RetryOrchestrator.prepareRetry(runId)`:
   - If `targetTable` is present, `cleanupPartialLoad` deletes partial rows (`WHERE _run_id = @run_id`).
   - `markRetrying` sets `status = 'RETRYING'` and increments `retry_count`.
3. Verify `rowsCleaned` in the `RetryResult` matches expectations (count of partial rows).
4. Re-submit the pipeline with the same `runId`.
5. After success, verify `pipeline_jobs.status = 'SUCCEEDED'` and `record_count` is correct.

**If `targetTable` is empty in `pipeline_jobs`:** The partial cleanup step is skipped. Manually identify and delete stale rows before re-running:
```sql
DELETE FROM `<project>.<dataset>.<table>` WHERE _run_id = '<run-id>';
```

### 5.4 Cloud Monitoring write failures

**Symptom:** Metrics missing from Cloud Monitoring dashboards; pipeline ran successfully.

`CloudMonitoringMetricsHook` swallows all `MetricServiceClient.createTimeSeries` errors (logged at WARN; in-process `monitoringFailureCount()` increments). The pipeline is never interrupted.

**Steps:**
1. Check Cloud Logging for `WARN` lines containing `CloudMonitoringMetricsHook: failed to write metrics`.
2. Common causes: missing `roles/monitoring.metricWriter` IAM role, incorrect `CULVERT_GCP_PROJECT` / `culvert.gcp.project` config, ADC unavailable.
3. Verify project-id resolution order: `culvert.gcp.project` sysprop → `CULVERT_GCP_PROJECT` env var → ADC default.
4. Fix IAM / config; next pipeline run will emit metrics normally (the hook is stateless per-run).

### 5.5 Audit event write failures

**Symptom:** `job_control.audit_events` is missing aggregate rows (`RECORD_VALIDATED` / `RECORD_REJECTED`) while the pipeline ran successfully.

Only aggregate events can be missing from a successful run. A failed run-level write fails the run, so a *successful* run with no `RUN_START` / `RUN_END` row is not possible — if you see that, the rows were deleted or you are querying the wrong table.

**Steps:**
1. Check Cloud Logging for `ERROR` lines from `BigQueryAuditEventPublisher` / `PubSubAuditPublisher`. The full event is logged, so the missing row is recoverable from the log.
2. Common causes: missing `roles/bigquery.dataEditor` role, wrong `culvert.audit.dataset` / `culvert.audit.table` config.
3. Aggregate counts also appear in the DQ quarantine files (§2.2), which are an independent source for the same numbers.

**Symptom:** the pipeline failed with `Audit publish FAILED for run-level event ...`.

This is working as designed — the run stopped rather than reporting a state it never recorded. Fix the audit write path (IAM, dataset/table config, topic), then re-run. The run has no partial audit trail to clean up: the events are append-only and the run took a new `run_id`.
