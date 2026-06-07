# data-pipeline-gcp-bigquery (Java)

Google Cloud BigQuery adapter for the Culvert data pipeline framework, JVM edition. Provides `BigQueryWarehouse`, the GCP implementation of the cloud-neutral [`Warehouse`](../data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Warehouse.java) contract defined in `data-pipeline-core-java`.

Sibling of the Python adapter that will lift out of `gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/clients/bigquery_client.py` in a later stage.

## Status

**Version 0.1.0 — Sprint 1 deliverable** (issue [#6](https://github.com/enrichmeai/culvert/issues/6)). Wave 2 of sprint-1; follows the `data-pipeline-gcp-secrets-java` pilot pattern (BOM in module-level `dependencyManagement`, parent stays cloud-neutral).

## Install (Maven)

```xml
<dependency>
    <groupId>com.enrichmeai.culvert</groupId>
    <artifactId>data-pipeline-gcp-bigquery</artifactId>
    <version>0.1.0</version>
</dependency>
```

Pulls in `data-pipeline-core` (the contracts) plus `google-cloud-bigquery` (version managed by the Google Cloud `libraries-bom`).

## Contract satisfied

[`com.enrichmeai.culvert.contracts.Warehouse`](../data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Warehouse.java):

```java
public interface Warehouse {
    Iterator<Map<String, Object>> query(String sql, Map<String, Object> params);
    void execute(String sql, Map<String, Object> params);
    long loadFromUri(String uri, String targetTable, EntitySchema schema);
    long merge(String sourceTable, String targetTable, List<String> keys);
    long copy(String sourceTable, String targetTable);
    boolean tableExists(String fqtn);
}
```

`BigQueryWarehouse` translates each operation into a BigQuery job:

| Contract method | BigQuery realisation |
|---|---|
| `query` | `client.query(QueryJobConfiguration)` returning a `TableResult`; rows streamed lazily via `iterateAll()` |
| `execute` | Same as `query`; returned `TableResult` is discarded |
| `loadFromUri` | `LoadJobConfiguration` from a `gs://` URI; returns `LoadStatistics.outputRows` |
| `merge` | Throws `UnsupportedOperationException` in sprint-1. BigQuery `MERGE` needs explicit non-key columns in `WHEN MATCHED THEN UPDATE SET ...` (no `SET t.* = s.*` shorthand); generating them requires a source-schema lookup that's deferred to sprint-4. Use `execute(String, Map)` with an explicit MERGE statement until then. |
| `copy` | `CopyJobConfiguration`; returns the target table's row count after the copy completes |
| `tableExists` | `client.getTable(TableId)`; returns `false` on `null` or a 404 `BigQueryException` |

Fully-qualified table names accept either `project.dataset.table` or `dataset.table` (the project component defaults to the warehouse's configured `projectId`).

Named parameters in `query` / `execute` accept `String`, `Long`, `Integer`, `Double`, `Float`, and `Boolean`. Anything else throws `IllegalArgumentException`.

## Construction

One public constructor — explicit `projectId` plus a pre-built `BigQuery` client:

```java
// Production
BigQuery client = BigQueryOptions.newBuilder()
        .setProjectId("my-gcp-project")
        .setLocation("EU")
        .build()
        .getService();
Warehouse warehouse = new BigQueryWarehouse("my-gcp-project", client);

// Tests / custom credentials — pass a Mockito mock or a client built with
// non-default credentials.
Warehouse warehouse = new BigQueryWarehouse("my-gcp-project", mockClient);
```

**Client lifecycle:** `BigQueryWarehouse` does NOT implement `AutoCloseable`. The google-cloud-bigquery 2.x `BigQuery` interface itself is not `AutoCloseable` (this is the divergence from the `SecretManagerProvider` pilot pattern, where `SecretManagerServiceClient` is closeable). Consumers manage the wrapped client's lifecycle directly; the client is safe to keep alive for the lifetime of the JVM.

```java
BigQuery client = BigQueryOptions.newBuilder()
        .setProjectId("my-project")
        .build()
        .getService();
Warehouse w = new BigQueryWarehouse("my-project", client);

Iterator<Map<String, Object>> rows = w.query(
        "SELECT id, name FROM ds.customers WHERE id = @id",
        Map.of("id", 42L));
while (rows.hasNext()) {
    System.out.println(rows.next());
}
// No explicit close needed; the BigQuery client manages its own gRPC channels.
```

### No no-arg constructor (yet)

Unlike `SecretManagerProvider`, `BigQueryWarehouse` does **not** expose a no-arg constructor. A real BigQuery client needs project + location + credentials at construction time, which exceeds the pilot's "no-arg only if <=2 env vars of state" rule. The `META-INF/services` file is pre-registered, but direct `ServiceLoader.load(Warehouse.class).findFirst()` will fail with `ServiceConfigurationError` until sprint-4 introduces a config-driven constructor. Wire it explicitly until then.

## Environment variables

| Variable | Used by | Required? |
|---|---|---|
| `GCP_PROJECT` | The sprint-4 auto-config no-arg constructor (planned) | Not yet — no consumer reads it in this version |
| `GCP_LOCATION` | The sprint-4 auto-config no-arg constructor (planned) | Not yet — set `BigQueryOptions.setLocation(...)` on the injected client instead |
| `GOOGLE_APPLICATION_CREDENTIALS` | The underlying `BigQuery` client (standard ADC) | Only when not running on a GCP-managed identity |

## ServiceLoader registration

`src/main/resources/META-INF/services/com.enrichmeai.culvert.contracts.Warehouse` lists `com.enrichmeai.culvert.gcp.bigquery.BigQueryWarehouse` so a future sprint-4 auto-config wiring can resolve the implementation by contract.

```java
// Reserved for sprint-4 — will throw ServiceConfigurationError today.
ServiceLoader.load(Warehouse.class).findFirst()
    .orElseThrow(() -> new IllegalStateException("no Warehouse on classpath"));
```

## Errors

| Cause | Thrown |
|---|---|
| Job completes with a status error | `com.google.cloud.bigquery.BigQueryException` |
| 404 on `tableExists` | `false` (not thrown) |
| Job disappears before completion | `java.util.NoSuchElementException` |
| `query` / `execute` thread interrupted | `RuntimeException` (interrupt flag restored) |
| Empty `keys` to `merge` | `IllegalArgumentException` |
| Unsupported parameter type | `IllegalArgumentException` |
| Null `sql`, `fqtn`, `client`, or `projectId` | `NullPointerException` |

## Sibling adapters (same module)

`data-pipeline-gcp-bigquery-java` is a multi-contract module — three GCP services share the same Google Cloud SDK family and `libraries-bom` pin, so they ship together. Sprint-1 status:

- ✅ `BigQueryWarehouse` — issue [#6](https://github.com/enrichmeai/culvert/issues/6) (Warehouse contract)
- ✅ `BigQueryJobControlRepository` — issue [#8](https://github.com/enrichmeai/culvert/issues/8) (JobControlRepository contract); see section below
- ✅ `BigQueryFinOpsSink` — issue [#9](https://github.com/enrichmeai/culvert/issues/9) (FinOpsSink contract); see section below
- ✅ `BigQueryCostTracker` — issue [#69](https://github.com/enrichmeai/culvert/issues/69) (T13.1: JobStatistics → CostMetrics pipeline); see section below
- ✅ `BigQueryAuditEventPublisher` — issue [#95](https://github.com/enrichmeai/culvert/issues/95) (T14.6: AuditEventPublisher contract — fills the final v1.0.0 gap); see section below

All five share this module's `pom.xml`.

## BigQueryJobControlRepository

Implementation of [`JobControlRepository`](../data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/JobControlRepository.java) — the pipeline-job state-machine contract. Java port of the Python `gcp_pipeline_core.job_control.repository.JobControlRepository`. Same eleven public methods; SQL patterns inherited but adapted to the richer Java `PipelineJob` record schema (more columns: `pipeline_name`, `source_file`, `target_table`, `record_count`, `error_count`, FinOps fields).

### Construction

```java
BigQuery client = BigQueryOptions.newBuilder().setProjectId("my-project").build().getService();
JobControlRepository repo = new BigQueryJobControlRepository(
        client,
        "my-project",
        "job_control",         // dataset
        "pipeline_jobs");      // table
```

Like `BigQueryWarehouse`, this class does not implement `AutoCloseable`. Consumers own the `BigQuery` client lifecycle.

### Method → SQL pattern

| Contract method | SQL |
|---|---|
| `createJob(PipelineJob)` | `INSERT INTO ` *`fqtn`* ` (...) VALUES (...)` — all 23 PipelineJob fields, `created_at`/`updated_at` use `CURRENT_TIMESTAMP()` |
| `getJob(String runId)` | `SELECT * FROM ` *`fqtn`* ` WHERE run_id = @run_id` |
| `updateStatus(runId, status, totalRecords)` | Three flavours: `RUNNING` stamps `started_at`; `SUCCEEDED` stamps `completed_at` + `record_count`; all others bump `status` + `updated_at` |
| `markFailed(runId, code, msg, stage, errorFile)` | `UPDATE` sets `status = 'failed'`, error fields, `completed_at = CURRENT_TIMESTAMP()` |
| `markRetrying(runId, retryCount)` | `UPDATE` sets `status = 'retrying'`, `retry_count = @retry_count` |
| `getPendingJobs(systemId?)` | `SELECT * WHERE status IN ('created', 'running')`, optionally `AND system_id = @system_id`, ordered by `created_at` |
| `getEntityStatus(systemId, date)` | `SELECT entity_type, status, run_id, record_count, error_count, started_at, completed_at WHERE system_id = ? AND extract_date = ?` |
| `getFailedJobs(systemId, date)` | Like above but filtered to `status = 'failed'`, returns failure context columns |
| `getFdpJobStatus(systemId, date, modelName)` | Filtered to `job_type = 'TRANSFORMATION'` and `pipeline_name = @model_name`, ordered DESC LIMIT 1 |
| `cleanupPartialLoad(runId, tableId)` | `DELETE FROM \`<tableId>\` WHERE _run_id = @run_id` — returns DML affected rows |
| `updateCostMetrics(runId, cost, scanned, written)` | `UPDATE` sets the three FinOps columns |

### Errors

| Cause | Thrown |
|---|---|
| `markRetrying` with negative `retryCount` | `IllegalArgumentException` |
| `cleanupPartialLoad` affected-row count exceeds `Integer.MAX_VALUE` | `ArithmeticException` (real-world this shouldn't happen — defensive) |
| Thread interrupted during a `client.query` | `RuntimeException` (interrupt flag restored) |
| Any BigQuery job error | `com.google.cloud.bigquery.BigQueryException` (propagated) |
| Null required argument | `NullPointerException` |

### ServiceLoader registration

`src/main/resources/META-INF/services/com.enrichmeai.culvert.contracts.JobControlRepository` lists the impl. Same caveat as `BigQueryWarehouse` — no no-arg constructor (needs `client`, `projectId`, `dataset`, `table` — 4 args, far past the pilot's ≤2-env-var rule), so direct `ServiceLoader.load(JobControlRepository.class).findFirst()` will throw `ServiceConfigurationError` until sprint-4 auto-config arrives. Wire it explicitly until then.

## Testing

Unit tests mock `com.google.cloud.bigquery.BigQuery` with Mockito — no real GCP credentials, no network. From the parent libraries directory:

```bash
cd data-pipeline-libraries-java && mvn -pl data-pipeline-gcp-bigquery-java -am clean test
# or equivalently
mvn -f data-pipeline-libraries-java/pom.xml -pl data-pipeline-gcp-bigquery-java -am clean test
```

Live-cloud integration tests against a real BigQuery dataset (or the BigQuery emulator) are sprint-2+ scope.

## BigQueryFinOpsSink

Implementation of [`FinOpsSink`](../data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/FinOpsSink.java) — receives `(CostMetrics, FinOpsTag)` pairs and streams them into the configured `cost_metrics` BigQuery table via `BigQuery.insertAll`.

### Construction

```java
BigQuery client = BigQueryOptions.newBuilder().setProjectId("my-project").build().getService();
FinOpsSink sink = new BigQueryFinOpsSink(
        client,
        "my-project",
        "finops",              // dataset
        "cost_metrics");       // table (the DEFAULT_TABLE constant)
```

Like its siblings, this class is not `AutoCloseable`; consumer owns the client.

### Row shape

Every `record(metrics, tags)` call writes one row. The columns flatten both records:

| Column | Source | Type |
|---|---|---|
| `system`, `environment`, `cost_center`, `owner` | `FinOpsTag` | STRING |
| `tag_run_id` | `FinOpsTag.runId()` | STRING (separate from `run_id` so analysts can detect attribution drift) |
| `tag_extra` | `FinOpsTag.extra()` | `ARRAY<STRUCT<key STRING, value STRING>>` |
| `run_id` | `CostMetrics.runId()` | STRING |
| `estimated_cost_usd` | `CostMetrics` | FLOAT64 |
| `billed_bytes_scanned`, `billed_bytes_written`, `billed_bytes_stored`, `billed_messages_count`, `slot_millis` | `CostMetrics` | INT64 |
| `compute_units` | `CostMetrics` | FLOAT64 |
| `labels` | `CostMetrics.labels()` | `ARRAY<STRUCT<key STRING, value STRING>>` |
| `timestamp` | `CostMetrics.timestamp()` | TIMESTAMP (ISO-8601 string) |

The flattened `labels` / `tag_extra` shape avoids BigQuery DDL changes when teams add new tag keys — new keys just appear in the array.

### Streaming buffer + cost

`insertAll` is BigQuery's streaming insert path. Rows are queryable within seconds but are NOT immediately visible to `COPY`/`EXPORT` jobs (streaming buffer flushes on BigQuery's schedule, typically within 90 minutes). Streaming inserts incur a per-GB cost on top of regular storage. For very high-volume cost emission, consider a load-job-based variant in a future sprint.

### Partial failures

`InsertAllResponse` can succeed at the request level while reporting per-row errors. `BigQueryFinOpsSink.FinOpsInsertException` (extends `RuntimeException`) is thrown if `response.hasErrors()` returns true — silently dropping cost rows would defeat the FinOps audit trail. The exception carries the underlying `Map<Long, List<BigQueryError>>` so callers can report specific row failures.

### ServiceLoader registration

`src/main/resources/META-INF/services/com.enrichmeai.culvert.contracts.FinOpsSink` lists the impl. Same no-arg-constructor caveat as the siblings — sprint-4 auto-config will resolve it.

## Retry &amp; partial-load cleanup (Sprint 14 / T14.3)

Sprint-14 deliverable for issue [#75](https://github.com/enrichmeai/culvert/issues/75).

### `_run_id` column contract

Every pipeline-written **target table** must contain a `_run_id STRING` column populated with the pipeline run's identifier at row-load time. `cleanupPartialLoad` deletes rows from that table using:

```sql
DELETE FROM `<tableId>` WHERE _run_id = @run_id
```

Required DDL addition for any BigQuery table loaded by the Culvert framework:

```sql
ALTER TABLE `my-project.warehouse.customers`
    ADD COLUMN IF NOT EXISTS _run_id STRING;
```

Populate this column in every load job (e.g. `LoadJobConfiguration`, Dataflow, `bq load --schema`). Without this column `cleanupPartialLoad` will throw a BigQuery job error on the DELETE.

### `RetryOrchestrator` usage

`RetryOrchestrator` is a stateless helper that sequences the full retry lifecycle: detect prior partial load → `cleanupPartialLoad` → `markRetrying` → return cleared state for re-submission.

```java
JobControlRepository repo = new BigQueryJobControlRepository(
        client, "my-project", "job_control", "pipeline_jobs");
RetryOrchestrator orchestrator = new RetryOrchestrator(repo);

// Called when you detect a FAILED run that needs a clean retry:
RetryOrchestrator.RetryResult result = orchestrator.prepareRetry("run-abc-123");
System.out.printf("Job ready to re-submit: retryCount=%d, rowsCleaned=%d%n",
        result.retryCount(), result.rowsCleaned());
// Caller re-submits the pipeline using result.runId().
```

**Idempotency:** calling `prepareRetry` on a job already in `RETRYING` state returns its current counter unchanged and does not call `markRetrying` or `cleanupPartialLoad` again. Safe to call multiple times.

**No target table:** if `PipelineJob.targetTable()` is empty, the cleanup step is skipped (`rowsCleaned = 0`) and the job is still marked `RETRYING`.

**Ordering guarantee:** `cleanupPartialLoad` is always called before `markRetrying`. The orchestrator does not expose partial state; either the full sequence completes or an exception propagates.

### `BigQueryJobControlRepository` SQL for retry

| Method | SQL |
|---|---|
| `markRetrying(runId, retryCount)` | `UPDATE <fqtn> SET status = 'retrying', retry_count = @retry_count, updated_at = CURRENT_TIMESTAMP() WHERE run_id = @run_id` |
| `cleanupPartialLoad(runId, tableId)` | `DELETE FROM \`<tableId>\` WHERE _run_id = @run_id` — returns DML affected rows |

## BigQueryCostTracker

Sprint-13 deliverable for issue [#69](https://github.com/enrichmeai/culvert/issues/69) (T13.1). Sets the pattern for T13.2. Reads `JobStatistics` from a completed BigQuery `Job`, builds a `CostMetrics` record, and pushes it to the `FinOpsSink`.

### Construction

```java
BigQuery client = BigQueryOptions.newBuilder().setProjectId("my-project").build().getService();
FinOpsSink sink = new BigQueryFinOpsSink(client, "my-project", "finops", "cost_metrics");
BigQueryCostTracker tracker = new BigQueryCostTracker(client, sink);
```

### Rate constants

| Constant | Value | Meaning |
|---|---|---|
| `BYTES_PER_TIB` | `1_099_511_627_776L` (2^40) | Binary definition of tebibyte; BigQuery pricing uses binary TiB. Use this — not 1e12 — to avoid ~10% undercount. |
| `QUERY_COST_USD_PER_TIB` | `5.00` | BigQuery on-demand query rate as of 2025 ($5.00/TiB scanned). Source: [BigQuery on-demand pricing](https://cloud.google.com/bigquery/pricing#on_demand_pricing). |
| `LOAD_COST_USD_PER_TIB` | `0.01` | GCS-egress-equivalent placeholder for load job accounting. **BigQuery batch loads are actually free to ingest** — set this to 0.0 if no GCS egress applies. |

USD formula for query jobs: `estimatedCostUsd = billedBytesScanned / BYTES_PER_TIB * QUERY_COST_USD_PER_TIB`

### trackJob usage

```java
// After a BigQuery job completes (query or load):
FinOpsTag tag = FinOpsTag.of("retail-fdp", "prod", "cc-1234", "platform-team", runId);
tracker.trackJob(completedJob, runId, tag);
// CostMetrics are pushed to the FinOpsSink automatically.
```

Field mapping:

| Job type | Statistics field | CostMetrics field |
|---|---|---|
| Query | `QueryStatistics.getTotalBytesBilled()` | `billedBytesScanned` |
| Query | `JobStatistics.getTotalSlotMs()` | `slotMillis` |
| Load | `LoadStatistics.getOutputBytes()` | `billedBytesWritten` |

Null statistics fields are treated as zero and a `WARN` log is emitted. If `Job.getStatistics()` is null, no metrics are emitted and a `WARN` is logged.

### estimateDryRun — pre-flight cost check

Submits a `setDryRun(true)` job so BigQuery validates the query and returns an estimate **without executing** it. Returns a `CostMetrics` with only `billedBytesScanned` and `estimatedCostUsd` populated; all other fields are zero.

```java
QueryJobConfiguration config = QueryJobConfiguration.newBuilder(
        "SELECT COUNT(*) FROM `project.dataset.table`").build();
CostMetrics estimate = tracker.estimateDryRun(config, runId);
System.out.printf("Estimated cost: $%.4f%n", estimate.estimatedCostUsd());
```

**Dry-run field fallback**: `getTotalBytesBilled()` may be null on a dry-run response (the query never executes, so no billing event occurs). When null/zero, the implementation falls back to `getTotalBytesProcessed()` and emits a WARN. This is a known runtime risk that can only be verified against a live BigQuery endpoint — see `BigQueryCostTrackerIT` (architect-run via `mvn -P it verify`).

## Cost-analysis SQL pack (Sprint 13 / T13.4)

A set of pre-written BigQuery Standard SQL queries for analysing the
`cost_metrics` table populated by `BigQueryFinOpsSink`. The queries live in
`src/main/resources/com/enrichmeai/culvert/gcp/bigquery/sql/cost_analysis.sql`
and are loaded at runtime via `CostAnalysisQueries.loadQuery(name)`.

### Available queries

| Name | Purpose |
|------|---------|
| `cost_by_run` | Total estimated USD and slot-ms grouped by `run_id`, ordered by cost DESC |
| `cost_by_stage` | Total estimated USD grouped by the `stage` label, using `UNNEST(labels)` — surfaces per-stage cost ready for T13.5 |
| `top_expensive_runs_7d` | Top 10 `run_id`s by total estimated cost in the last 7 days |
| `budget_breach_log` | All rows where `estimated_cost_usd > ?` (positional parameter), ordered by timestamp DESC |

### Usage

```java
// Load a named SQL block from the classpath resource.
String sql = CostAnalysisQueries.loadQuery("cost_by_run");

// budget_breach_log has one positional parameter — bind before executing.
String breachSql = CostAnalysisQueries.loadQuery("budget_breach_log");
// Replace ? with a QueryParameterValue or pass as a named param after adaptation.
```

`CostAnalysisQueries.loadQuery(name)` throws `IllegalArgumentException` for
unknown names and `NullPointerException` for null. It parses the SQL file once
at class-init (static block) so repeated calls are cheap.

### Add new queries

Drop a new `-- query: <name>` block in `cost_analysis.sql`. No Java changes
needed; the parser picks it up on the next class load.

### Verify-at-start notes (issue #69, T13.1)

- **Version check**: Ticket assumes `google-cloud-bigquery 2.55.x`. Actual BOM-resolved version is **2.40.1** (via `libraries-bom 26.39.0`). All required API surface (`getTotalBytesBilled`, `getTotalSlotMs` on `JobStatistics`, `getOutputBytes` on `LoadStatistics`) is present in 2.40.1. No workaround needed; architect should update the ticket's version assumption.
- **Dry-run population**: Whether `getTotalBytesBilled()` is populated at runtime on a dry-run cannot be verified offline (no emulator IT in agent scope). The fallback to `getTotalBytesProcessed()` is the mitigation — see `resolveDryRunBytes` in the source.

## BigQueryAuditEventPublisher (Sprint 14 / T14.6)

Sprint-14 deliverable for issue [#95](https://github.com/enrichmeai/culvert/issues/95). Fills the **last contract gap** in v1.0.0 — `AuditEventPublisher` was the only core contract with an interface but no adapter.

Implementation of [`AuditEventPublisher`](../data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/AuditEventPublisher.java) — writes `AuditRecord` instances as rows to a configurable BigQuery audit table using a parameterised `INSERT ... VALUES` DML statement (via `client.query`, same mechanism as `BigQueryJobControlRepository`).

### Construction

```java
// Tests / custom-credential wiring: explicit constructor
BigQuery client = BigQueryOptions.newBuilder().setProjectId("my-project").build().getService();
AuditEventPublisher pub = new BigQueryAuditEventPublisher(
        client,
        "my-project",
        "audit",          // dataset (default)
        "audit_events");  // table (default)

// ServiceLoader: no-arg ADC constructor (resolves project from env chain)
// Requires culvert.gcp.project sysprop or CULVERT_GCP_PROJECT env var (or ADC default project)
AuditEventPublisher pub = new BigQueryAuditEventPublisher();
```

### Project-id / dataset / table precedence chain

| Config | Sysprop | Env var | Default |
|--------|---------|---------|---------|
| GCP project | `culvert.gcp.project` | `CULVERT_GCP_PROJECT` | ADC `ServiceOptions.getDefaultProjectId()` |
| Dataset | `culvert.audit.dataset` | `CULVERT_AUDIT_DATASET` | `audit` |
| Table | `culvert.audit.table` | `CULVERT_AUDIT_TABLE` | `audit_events` |

### Audit table schema

```sql
CREATE TABLE `<project>.<dataset>.<table>` (
    run_id                        STRING    NOT NULL,
    pipeline_name                 STRING    NOT NULL,
    entity_type                   STRING    NOT NULL,
    source_file                   STRING    NOT NULL,
    record_count                  INT64     NOT NULL,
    processed_timestamp           TIMESTAMP NOT NULL,
    processing_duration_seconds   FLOAT64   NOT NULL,
    success                       BOOL      NOT NULL,
    error_count                   INT64     NOT NULL,
    audit_hash                    STRING,
    metadata_json                 STRING,
    published_at                  TIMESTAMP
);
```

`metadata` (`Map<String,Object>` from `AuditRecord`) is serialised to a compact JSON string in `metadata_json`. This avoids the `ARRAY<STRUCT<key,value>>` schema complexity that `BigQueryFinOpsSink` uses for label maps, and remains compatible with the goccy emulator.

`published_at` is populated with `CURRENT_TIMESTAMP()` by the INSERT statement — no client-side clock is needed.

### Failure isolation

Any exception during `publish` is caught, logged at WARN, and swallowed. A failing audit write must never interrupt the data pipeline. The cumulative failure count is accessible via `auditFailureCount()` for tests and alerting. `InterruptedException` restores the thread's interrupt flag before swallowing. This mirrors `CloudMonitoringMetricsHook`'s error handling (T12.6).

### flush

`flush()` is a no-op. Every `publish` call writes synchronously (no internal buffer). Calling `flush()` on an empty publisher is safe and idempotent as required by the contract.

### ServiceLoader registration

`src/main/resources/META-INF/services/com.enrichmeai.culvert.contracts.AuditEventPublisher` registers `com.enrichmeai.culvert.gcp.bigquery.BigQueryAuditEventPublisher`. The no-arg constructor is the ServiceLoader entry point, resolving all config from environment/sysprops and building the BigQuery client via `BigQueryOptions.getDefaultInstance().getService()` (ADC).

### Timestamp parameter format (implementation note)

`QueryParameterValue.timestamp(String)` in google-cloud-bigquery 2.40.1 (via the bundled threeten-bp library) requires the format `"yyyy-MM-dd HH:mm:ss.SSSSSS"` with a space separator — ISO-8601 `T` separator is rejected. This is different from the human-readable `OffsetDateTime.toString()` output and requires an explicit `DateTimeFormatter.ofPattern(...)` in the publisher.

### Known risk: emulator named-parameter support

The goccy emulator's support for named parameters (`@param_name`) in DML `INSERT` statements is not fully documented. The `BigQueryAuditEventPublisherIT` is authored and correct; if the emulator rejects named parameters in INSERT context when the architect runs it, the fallback is to use literal substitution in the IT-only path (the unit tests are the primary correctness gate and remain unaffected). See also `BigQueryCostTrackerIT` for a similar "architect-run only" note.
