# Chapter 8 — Warehouse and Job Control

## The double life of a columnar store

In Chapter 5 I walked through the six methods on the `Warehouse` contract — the tabular complement to `BlobStore`, the thing that can run a SELECT, fire a bulk load, and clone a table server-side. I made a small drama out of having forgotten `copy` entirely when writing from memory, and used it to argue that the contract is the memory you cannot argue with.

What I did not explain in Chapter 5 is the thing that most surprises engineers seeing Culvert's GCP adapter stack for the first time: BigQuery is not just the warehouse. It is also the pipeline-job ledger. Every `createJob`, every `updateStatus`, every `markFailed` — those are `UPDATE … WHERE run_id = @run_id` statements issued against BigQuery DML, not against a Postgres primary store or a Cloud Spanner transaction. The same columnar OLAP store that scans terabytes in seconds is doing your row-by-row job bookkeeping.

This is a deliberate choice, and it is worth explaining properly, because it is not the choice I would have made in 2019. My instinct — I suspect yours too — is to reach for a transactional database for state management. PostgreSQL for the job ledger, BigQuery for the warehouse. That is two data stores, two IAM surfaces, two connection pools, two billing lines, and a new class of cross-store consistency bug to write integration tests for. When I worked out that BigQuery DML was fast enough at pipeline-job volumes — and that having the job history SQL-joinable against the pipeline output tables was genuinely useful for debugging — I kept it. This chapter explains how that works, what it costs you, and where the seam is.

## BigQueryWarehouse: five of six, honestly

The contract surface from Chapter 5:

```
query(sql, params)       → Iterator<Map<String, Object>>
execute(sql, params)     → void
loadFromUri(uri, table, schema) → long
merge(sourceTable, targetTable, keys) → long
copy(sourceTable, targetTable) → long
tableExists(fqtn)        → boolean
```

`BigQueryWarehouse` implements five of those. The sixth — `merge` — throws `UnsupportedOperationException`. The Javadoc is honest about why:

```java
// BigQuery's MERGE syntax requires explicit non-key column lists in
// `WHEN MATCHED THEN UPDATE SET ...`; `SET t.* = s.*` is not valid.
// Generating the column list requires a schema lookup against the
// source table, which expands this method's responsibility beyond
// sprint-1's "match the pilot's adaptation patterns" rule.
throw new UnsupportedOperationException(
        "merge() is sprint-4 scope (requires column-aware SQL generation). "
                + "Use execute(String, Map) with an explicit MERGE statement until then. "
                + "Tracked at https://github.com/enrichmeai/gcp-pipeline-reference/issues/6");
```
[`data-pipeline-libraries-java/data-pipeline-gcp-bigquery-java/src/main/java/com/enrichmeai/culvert/gcp/bigquery/BigQueryWarehouse.java:164`]

I want to be plain about this because the task sheet I handed the team for Chapter 8 listed all six methods as if they work. They do not all work. BigQuery's MERGE requires you to enumerate every column you want updated; generating that list requires a prior schema fetch, and that turned the implementation into a more complicated beast than a Sprint 1 deliverable should be. The workaround — pass an explicit MERGE statement through `execute()` — is not elegant, but it is honest. The issue is tracked; it will land.

The five that do work follow a consistent pattern: every operation goes through a BigQuery `Job`. `query` and `execute` use `QueryJobConfiguration`; `loadFromUri` uses `LoadJobConfiguration`; `copy` uses `CopyJobConfiguration`. The client blocks on `job.waitFor()` and the result is unpacked in a single private helper, `waitFor()`, which distinguishes the three error modes — null job (quota/ADC failure), job disappeared before completion (`NoSuchElementException`), job completed with a status error (`BigQueryException` synthesised from the job's error message) — at [`BigQueryWarehouse.java:360`].

The one design decision worth calling out is in `query`. Rather than materialising the entire `TableResult` into a `List`, the adapter wraps `result.iterateAll().iterator()` in an anonymous `Iterator<Map<String, Object>>` that pages through BigQuery's cursor lazily. The contract's Javadoc requires this: *"implementations should not buffer the entire result in memory."* A 50-million-row query result should not allocate a 50-million-entry list at [`BigQueryWarehouse.java:249`].

`loadFromUri` does the one thing that makes BigQuery an attractive warehouse: it lets you hand it a `gs://` URI and it arranges the bulk load server-side. The adapter guesses the format from the URI extension — CSV, Parquet, Avro, ORC, or newline-delimited JSON as fallback — at [`BigQueryWarehouse.java:341`]. GCS-to-BigQuery at that point is a metadata operation on Google's infrastructure; the data does not traverse your network. `copy` is even cheaper: it is a BigQuery `CopyJob`, which is a metadata-only table clone. The output row count is retrieved from `table.getNumRows()` after the copy, not from any job statistics, because `CopyStatistics` does not expose a row count.

## The fqtn convention

`BigQueryWarehouse` and `BigQueryJobControlRepository` both parse table names the same way. The adapter accepts either two-part `dataset.table` or three-part `project.dataset.table`. Two-part names default to the warehouse's configured `projectId`. The parsing lives in `parseFqtn()` at [`BigQueryWarehouse.java:287`] and is replicated as template-literal construction in `BigQueryJobControlRepository` at [`BigQueryJobControlRepository.java:73`]:

```java
this.fqtn = "`" + projectId + "." + dataset + "." + table + "`";
```

The backtick-quoting matters. BigQuery's SQL parser requires backtick-quoted fully-qualified table names in parameterised DML statements. Miss the backticks and you get a parse error; this is one of those things you learn by getting the error and then reading the error message for longer than you should need to.

## BigQueryJobControlRepository: the ledger

The job-control contract — `JobControlRepository` — is the pipeline state machine. Eleven methods: create a job row, fetch it, transition its status, mark it failed, mark it retrying, list pending runs, report per-entity status, list failed jobs, query FDP model status, clean up a partial load, and attach cost metrics. The Java surface at [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/JobControlRepository.java:25`] is a one-for-one mirror of the Python job-control repository documented in the Python `gcp_pipeline_core.job_control.repository` module — the Java port carries that lineage explicitly in its Javadoc at line 28.

`BigQueryJobControlRepository` implements all eleven. Every method issues a parameterised BigQuery query. The parameters are bound using `QueryParameterValue` typed constructors — `.string()`, `.int64()`, `.float64()`, `.date()`, `.timestamp()` — rather than string interpolation. That is not a minor style point. BigQuery parameterised queries prevent SQL injection and, more practically in a pipeline context, prevent the kind of run-ID collision where an accidental quote in a system identifier corrupts the WHERE clause.

The `updateStatus` method illustrates the pattern. Status transitions branch on three cases:

```java
if (status == JobStatus.RUNNING) {
    // stamps started_at
} else if (status == JobStatus.SUCCEEDED) {
    // stamps completed_at + record_count
} else {
    // bumps status + updated_at only
}
```
[`BigQueryJobControlRepository.java:159`]

This branching comes directly from the Python original. RUNNING starts a job's clock; SUCCEEDED closes it and records the final row count; every other transition (FAILED, RETRYING, CANCELLED) only updates status and the audit timestamp. The split is pragmatic: it avoids nulling out `started_at` or `completed_at` on intermediate transitions, which would make duration queries on the `pipeline_jobs` table unreliable.

`markFailed` is the one that matters most at three in the morning. It writes structured error context — `error_code`, `error_message`, `failure_stage`, and an optional `error_file_path` (a `gs://` URI pointing at the quarantined records that caused the failure) — atomically with the status flip. The framework does not require you to write these separately and hope the process does not crash between statements. They go in one UPDATE at [`BigQueryJobControlRepository.java:197`].

`cleanupPartialLoad` is the twin of `markFailed` for recovery. Pipeline-written target tables carry a `_run_id STRING` column populated at load time. When a run fails and the caller wants to retry cleanly, `cleanupPartialLoad` issues `DELETE FROM <table> WHERE _run_id = @run_id` to remove any partially-written rows before the orchestrator resubmits. The `RetryOrchestrator` helper at [`BigQueryRetryOrchestrator.java`] sequences the full lifecycle: detect prior partial load, clean it, mark retrying, return cleared state. The idempotency guarantee is explicit: if the job is already in `RETRYING` state, the orchestrator does not call `markRetrying` again, which prevents double-incrementing the retry counter when a caller restarts an already-in-progress re-run.

## The honest trade-off

Using BigQuery as a CRUD store has real costs. BigQuery DML — UPDATE, DELETE — is not free. Each statement competes for DML slots and can take seconds to complete at low concurrency. At pipeline-job volumes — dozens of jobs per hour, not tens of thousands per second — the latency is acceptable. At application-CRUD volumes it would be absurd.

The benefit is that the job history is a BigQuery table, full stop. You can join it against your pipeline output tables, your cost metrics, your audit events, your BI exports. Debugging a failed run means one SQL query against a familiar interface, not a context switch to a different database with a different auth model and a different query tool. The operations team we work with found that more valuable than I expected.

The other thing you give up is transactional isolation. BigQuery DML does not support BEGIN/COMMIT in the sense that PostgreSQL does. Two concurrent `markFailed` calls for the same `run_id` are theoretically possible — BigQuery will serialise them, but the result is non-deterministic ordering. In practice, a well-structured pipeline runner ensures that only one process owns a given `run_id` at any moment. The contract documentation at [`JobControlRepository.java:17`] is explicit: *"implementations are expected to be transactional within a single `runId`."* The BigQuery implementation honours the spirit of that clause by relying on single-writer discipline rather than database locks. If your runner does not enforce single-writer discipline, you will find out the hard way.

## BigQueryFinOpsSink: the cost trail

`FinOpsSink` is a functional interface with one method: `record(CostMetrics metrics, FinOpsTag tags)`. The tag carries attribution — system, environment, cost centre, owner, run ID. The metrics carry the numbers — bytes scanned, bytes written, bytes stored, slot-milliseconds, compute units, estimated cost in USD. The sink writes them wherever the team aggregates them. On GCP, that is BigQuery.

`BigQueryFinOpsSink` implements `record` via a streaming insert: `client.insertAll(InsertAllRequest)` at [`BigQueryFinOpsSink.java:100`]. One call per cost-incurring operation. The Javadoc is candid about the trade-off: streaming inserts land in BigQuery's streaming buffer, queryable within seconds but not immediately visible to `COPY` or `EXPORT` jobs; the buffer flushes to managed storage on BigQuery's own schedule, typically within 90 minutes. Streaming inserts also cost money — per GB written to the buffer on top of regular storage. For high-volume cost emission, a load-job-based variant would be cheaper; that is flagged in the Javadoc at [`BigQueryFinOpsSink.java:30`] as a future-sprint item.

The partial-failure handling is worth noting: `InsertAllResponse.hasErrors()` is checked explicitly at line 101, and any per-row error throws `FinOpsInsertException` rather than silently swallowing it. Silently dropping cost rows would undermine the FinOps audit trail. The exception preserves the full GCP `Map<Long, List<BigQueryError>>` so a caller can report which rows failed and why.

The map fields — `CostMetrics.labels()` and `FinOpsTag.extra()` — are flattened into `RECORD<key STRING, value STRING>` arrays via `flattenMap()` at [`BigQueryFinOpsSink.java:149`]. BigQuery's stable way to ship arbitrary key-value data without a DDL change per new label. The query side UNNESTs the array; `CostAnalysisQueries` at [`BigQueryCostTracker:java`] ships the canned SQL for the common aggregations.

## BigQueryCostTracker: the formula

`BigQueryCostTracker` sits one level above `BigQueryFinOpsSink`. It reads a completed `Job`'s statistics and builds the `CostMetrics` record before handing it to the sink. The pricing model is:

```java
public static final long BYTES_PER_TIB = 1_099_511_627_776L; // 2^40
public static final double QUERY_COST_USD_PER_TIB = 5.00;
public static final double LOAD_COST_USD_PER_TIB = 0.01;
```
[`BigQueryCostTracker.java:81`, `90`, `103`]

The formula that applies those constants:

```java
private static double bytesToUsd(long bytes, double costPerTib) {
    if (bytes <= 0L) {
        return 0.0;
    }
    return (double) bytes / (double) BYTES_PER_TIB * costPerTib;
}
```
[`BigQueryCostTracker.java:321`]

Called for query jobs at line 243: `double costUsd = bytesToUsd(bytesScanned, QUERY_COST_USD_PER_TIB)`. Note the binary definition of TiB — 2^40 bytes, not 10^12. BigQuery's on-demand pricing uses the binary definition. Using 10^12 instead would undercount the estimated cost by about 9.95%. That is not a rounding error; it is an invoice surprise. The comment on the constant says as much.

`LOAD_COST_USD_PER_TIB = 0.01` has an honest footnote: BigQuery batch loads are actually free to ingest. The `$0.01` rate is a GCS-egress-equivalent accounting placeholder — the cost of moving data into BigQuery falls on the GCS side, not the BigQuery load side. Teams that do not pay GCS egress fees for this path may legitimately set it to zero. It is here to give the cost trail a non-null entry for load operations; otherwise load jobs appear free in the attribution dashboard and the FinOps team gets confused about why ingestion looks so cheap.

The dry-run pre-flight — `estimateDryRun()` at line 193 — is a useful capability with a documented uncertainty. BigQuery dry-run jobs populate `getTotalBytesBilled()` on *some* configurations; on others they populate only `getTotalBytesProcessed()`. The method tries `billed` first, falls back to `processed` if billed is null or zero, emits a `WARN`, and ultimately returns a zero estimate if both are absent. The Javadoc at line 54 flags this as a runtime guarantee risk and notes that the emulator integration test (`BigQueryCostTrackerIT`) is the place to verify the behaviour before trusting it in production. That is the kind of honesty I want baked into the implementation, not added later as a postmortem note.

## Why one store

I will make the argument plainly, because the alternative — BigQuery for the warehouse, a separate transactional store for the ledger — is the one I get asked about most often.

The separate-store approach is perfectly defensible. A Cloud Spanner instance or a Cloud SQL PostgreSQL gives you proper serialisable isolation, sub-millisecond commit latency, and a familiar JDBC driver. You know exactly what you are getting.

What it also gives you is a second IAM surface, a second connection pool, a second backup policy, a second point of failure, and a billing line that will confuse whoever does the next cost review. It means that debugging a failed run requires querying two databases and mentally joining the results. It means that your FinOps dashboard cannot JOIN the job ledger against the cost metrics table, because they live in different systems.

BigQuery-as-ledger trades transactional isolation guarantees for operational simplicity. At pipeline-job frequencies — where "high volume" means tens of jobs per minute — the DML latency is negligible and the joining capability is immediately useful. If you are building something where hundreds of processes are competing to update the same job row simultaneously, this is not the right design. For the data pipelines this framework targets, it has been the right design.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item \texttt{BigQueryWarehouse} implements five of the six \texttt{Warehouse} contract methods. \texttt{merge()} throws \texttt{UnsupportedOperationException} — BigQuery requires explicit column enumeration in MERGE that the sprint-1 implementation defers; callers pass explicit MERGE SQL via \texttt{execute()} until sprint-4 lands. [\texttt{BigQueryWarehouse.java:164}]
  \item Every operation goes through a BigQuery \textit{Job} — \texttt{QueryJobConfiguration} for query/execute, \texttt{LoadJobConfiguration} for bulk load, \texttt{CopyJobConfiguration} for table clone. The \texttt{waitFor} helper distinguishes null job, vanished job, and error-status job in one place. [\texttt{BigQueryWarehouse.java:360}]
  \item Using BigQuery as the job ledger is a deliberate trade: one IAM surface, one billing line, joinable job history against pipeline output tables — at the cost of DML latency and no serialisable isolation. Acceptable at pipeline-job frequencies; not at OLTP frequencies.
  \item The query cost formula is \texttt{bytes / BYTES\_PER\_TIB * QUERY\_COST\_USD\_PER\_TIB} where \texttt{BYTES\_PER\_TIB = 1\_099\_511\_627\_776L} (2\textsuperscript{40}, the binary definition). Using the decimal 10\textsuperscript{12} would undercount by roughly 10\%. [\texttt{BigQueryCostTracker.java:81}, \texttt{90}, \texttt{321}]
  \item \texttt{BigQueryFinOpsSink} uses streaming inserts — rows are queryable within seconds but not immediately available to COPY/EXPORT jobs; the streaming buffer flushes on BigQuery's schedule, typically within 90 minutes. Streaming inserts also carry a per-GB cost. [\texttt{BigQueryFinOpsSink.java:30}]
  \item Python job-control parity already exists in the predecessor \texttt{gcp\_pipeline\_core.job\_control.repository}. A Python \texttt{Warehouse} adapter for BigQuery is in progress on a separate branch; it is not yet shipped.
\end{itemize}
\end{takeaways}

\newpage
