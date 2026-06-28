# Chapter 13 — Cost and FinOps

\index{FinOps}

A pipeline that nobody can afford to run is not a product. It is a proof of concept with a billing alarm attached.

I say that because I have watched it happen — not once, not twice. The pattern is consistent enough that I now consider it a distinct class of pipeline failure: technically green, financially untenable. The Dataflow job returns `SUCCESS`. The BigQuery table is populated. The audit trail is clean. And then the finance team sends an email on the fifteenth of the month and the engineering lead learns, for the first time, that the entity they put into production last quarter is spending more per day than the product it feeds earns per week.

This happens when cost is an afterthought. Culvert treats it as a first-class concern — not because "FinOps" is a fashionable acronym but because I built the framework after living through the consequences of the alternative. Everything in this chapter is earned the hard way.

## Cost as a metric, not an invoice line

The first thing Culvert does differently is treat cost the same way it treats any other operational metric: measured per run, attributed per entity, stored in a queryable table, and surfaced before the pipeline runs if it is going to be expensive.

The `FinOpsSink` contract is the seam that makes this possible.

```java
// data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/
//   com/enrichmeai/culvert/contracts/FinOpsSink.java:17–27
@FunctionalInterface
public interface FinOpsSink {

    /**
     * Record cost metrics with attribution tags.
     *
     * Implementations may batch internally; the framework calls this once
     * per cost-incurring operation (a BigQuery query, a GCS upload, a Pub/Sub
     * publish) and the sink decides when to flush.
     */
    void record(CostMetrics metrics, FinOpsTag tags);
}
```

\index{FinOpsSink}

One method. The cloud-specific cost tracker calls it once per operation; the sink decides what to do with the record. The `BigQueryFinOpsSink` streams it into a `cost_metrics` table. A test double captures it in memory. A future Athena sink would write to S3. The contract does not care.

There is a design decision hidden in this signature that I want to explain, because it took a failed integration test to understand it properly. The tags — `FinOpsTag` — are passed explicitly to `record()`. They are not read from a runtime context or inferred from ambient state.

The reason is attribution loss. Cost emissions are infrequent: one call per BigQuery query, one per GCS upload batch, one per Pub/Sub publish. But lossy attribution is the most common bug in cost tracking systems. Ambient context can be overwritten. Thread locals can bleed. Reactor context can be dropped across async boundaries. Explicit tags make the data flow visible at every call site — you can read `tracker.trackJob(job, runId, tag)` and see exactly what attribution is being recorded. If it is wrong, the mistake is on that line, not somewhere in a context propagation chain three calls up. The comment in the source is direct about this: "Cost emissions are infrequent and lossy attribution is the most common bug; explicit tags make the data flow visible" (`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/finops.py:10–12`).

## `CostMetrics` and `FinOpsTag`: what travels through the seam

\index{CostMetrics}\index{FinOpsTag}

`CostMetrics` is a record — immutable, value-typed, with all numeric fields defaulting to zero. The fields cover what every cloud charges for: bytes scanned (BigQuery queries), bytes written (loads, GCS uploads, Pub/Sub), bytes stored (GCS object lifetime), message counts (Pub/Sub), slot-milliseconds (BigQuery flat-rate), and a generic `computeUnits` field for warehouses that bill differently.

```java
// data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/
//   com/enrichmeai/culvert/finops/CostMetrics.java:32–52
public record CostMetrics(
        String runId,
        double estimatedCostUsd,
        long billedBytesScanned,
        long billedBytesWritten,
        long billedBytesStored,
        long billedMessagesCount,
        long slotMillis,
        double computeUnits,
        Map<String, String> labels,
        Instant timestamp) { ... }
```

The zero-default pattern matters. A GCS upload tracker does not know the slot-milliseconds; a Pub/Sub tracker does not know the bytes stored. Rather than inventing a hierarchy of subtypes — `BigQueryCostMetrics`, `GcsCostMetrics` — the same record carries whatever the cloud service measured and leaves the rest at zero. The record that travels from `BigQueryCostTracker` to `BigQueryFinOpsSink` happens to have `billedBytesScanned` and `slotMillis` populated; the one from `GcsCostTracker` has `billedBytesStored`. Downstream analytics are straightforward `SUM` queries grouped by field.

The Python mirror is a dataclass:

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/
#   finops_api/models.py:22–40
@dataclass
class CostMetrics:
    run_id: str
    estimated_cost_usd: float = 0.0
    billed_bytes_scanned: int = 0
    billed_bytes_written: int = 0
    billed_bytes_stored: int = 0
    billed_messages_count: int = 0
    slot_millis: int = 0
    compute_units: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=_utc_now)
```

Identical fields, identical semantics, different language. This is the polyglot contract pattern from Chapter 6 applied to cost data: one conceptual type, two implementations, one set of analytics queries over the result.

`FinOpsTag` is the attribution metadata that travels alongside every `CostMetrics` record:

```java
// data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/
//   com/enrichmeai/culvert/finops/FinOpsTag.java:24–49
public record FinOpsTag(
        String system,
        String environment,
        String costCenter,
        String owner,
        String runId,
        Map<String, String> extra) { ... }
```

Five required fields — system, environment, cost centre, owner, run ID — and an `extra` map for anything else the team needs (business unit, feature flag, customer tier). The Python mirror is a frozen dataclass in `data-pipeline-core/src/data_pipeline_core/finops_api/labels.py:17–30`. The name is deliberate: it used to be `FinOpsLabels` (a GCP-specific term) and was renamed `FinOpsTag` because AWS calls them tags, Azure calls them tags, and cloud-neutral vocabulary matters if you want adapters to compose cleanly. That rename echoes exactly the framework rename story in Chapter 4.

## The three service trackers

\index{BigQueryCostTracker}\index{GcsCostTracker}\index{PubSubCostTracker}

Culvert ships three service-specific cost trackers for GCP. Each lives in its cloud-adapter module, holds a reference to the `FinOpsSink`, and knows how to translate raw cloud-API statistics into a `CostMetrics` record.

### BigQuery: bytes billed and slot-milliseconds

`BigQueryCostTracker` (`data-pipeline-libraries-java/data-pipeline-gcp-bigquery-java/src/main/java/com/enrichmeai/culvert/gcp/bigquery/BigQueryCostTracker.java`) reads `JobStatistics` from a completed BigQuery `Job` and calls the sink.

The cost formula for query jobs:

```
estimatedCostUsd = billedBytesScanned / BYTES_PER_TIB * QUERY_COST_USD_PER_TIB
```

The constants are not magic numbers:

```java
// BigQueryCostTracker.java:81
public static final long BYTES_PER_TIB = 1_099_511_627_776L; // 2^40

// BigQueryCostTracker.java:90
public static final double QUERY_COST_USD_PER_TIB = 5.00;
```

\index{BigQuery!pricing}

`BYTES_PER_TIB` is exactly 2^40 — not 10^12. This is the binary definition of tebibyte that BigQuery's pricing page uses. If you use one trillion instead you undercount by roughly ten per cent. That is a ten per cent undercount on your most expensive queries. At scale, that is real money going unaccounted for. The constant is named and documented for precisely this reason: the wrong answer is not dramatically wrong, it is plausibly wrong, which is worse.

`QUERY_COST_USD_PER_TIB` is $5.00 per tebibyte scanned, the 2025 BigQuery on-demand rate. The formula runs at line 325:

```java
// BigQueryCostTracker.java:321–326
private static double bytesToUsd(long bytes, double costPerTib) {
    if (bytes <= 0L) {
        return 0.0;
    }
    return (double) bytes / (double) BYTES_PER_TIB * costPerTib;
}
```

For load jobs, `BigQueryCostTracker` uses a placeholder rate of `LOAD_COST_USD_PER_TIB = 0.01` (`BigQueryCostTracker.java:103`). BigQuery batch loads are actually free to ingest; the constant represents GCS-egress-equivalent accounting for teams that want to attribute the cost of moving data. The Javadoc says so explicitly, and teams may set it to zero.

### GCS: bytes written and storage class

`GcsCostTracker` (`data-pipeline-libraries-java/data-pipeline-gcp-gcs-java/src/main/java/com/enrichmeai/culvert/gcp/gcs/GcsCostTracker.java`) tracks two operation types: uploads and storage-class attribution.

The storage formula:

```
estimatedCostUsd = bytesStored / BYTES_PER_GIB * rateForClass
```

Storage is priced in **gibibytes**, not tebibytes, so the denominator shifts:

```java
// GcsCostTracker.java:77
public static final long BYTES_PER_GIB = 1_073_741_824L; // 2^30
```

The per-class monthly rates (US multi-region, 2025):

```java
// GcsCostTracker.java:99,108,117,126
public static final double STANDARD_STORAGE_USD_PER_GIB  = 0.020;  // $0.020/GiB-month
public static final double NEARLINE_STORAGE_USD_PER_GIB  = 0.010;  // $0.010/GiB-month
public static final double COLDLINE_STORAGE_USD_PER_GIB  = 0.004;  // $0.004/GiB-month
public static final double ARCHIVE_STORAGE_USD_PER_GIB   = 0.0012; // $0.0012/GiB-month
```

\index{GCS!storage pricing}

The formula at line 244–248:

```java
// GcsCostTracker.java:244–248
private static double bytesToUsd(long bytes, double ratePerGib) {
    if (bytes <= 0L) {
        return 0.0;
    }
    return (double) bytes / (double) BYTES_PER_GIB * ratePerGib;
}
```

The upload tracker uses `WRITE_COST_USD_PER_GIB = 0.01` (`GcsCostTracker.java:90`) — another accounting placeholder, since GCS charges per-10,000 Class A operations rather than per byte. Teams that do not need per-upload attribution can zero it out.

An unknown storage class falls back to the Standard rate with a `WARN` log rather than throwing. Cost tracking should never crash the pipeline.

### Pub/Sub: throughput bytes

`PubSubCostTracker` (`data-pipeline-libraries-java/data-pipeline-gcp-pubsub-java/src/main/java/com/enrichmeai/culvert/gcp/pubsub/PubSubCostTracker.java`) records both the message count and the throughput bytes for publish and subscribe operations.

I want to dwell on this one for a moment, because it contains the clearest example of why the outline for this book flags pricing as a danger zone. The original ticket for the Pub/Sub tracker — issue #70 — described the cost as "$0.04/MiB". That figure is approximately one thousand times the actual rate. The Javadoc notes this explicitly:

```java
// PubSubCostTracker.java:76–79
// Note on issue #70 paraphrase: the ticket text mentioned
// "$0.04/MiB" which is approximately 1000× the actual per-TiB rate
// ($40/TiB ≈ $0.000038/MiB). This constant uses the correct per-TiB
// billing unit from the GCP pricing page.
```

\index{Pub/Sub!pricing}

The correct constants:

```java
// PubSubCostTracker.java:65
public static final long BYTES_PER_TIB = 1_099_511_627_776L; // 2^40

// PubSubCostTracker.java:81
public static final double THROUGHPUT_COST_USD_PER_TIB = 40.00;
```

The formula at lines 182–186:

```java
// PubSubCostTracker.java:182–186
private static double bytesToUsd(long bytes) {
    if (bytes <= 0L) {
        return 0.0;
    }
    return (double) bytes / (double) BYTES_PER_TIB * THROUGHPUT_COST_USD_PER_TIB;
}
```

Pub/Sub charges $40 per tebibyte of message throughput, with the first 10 GiB per month free. The tracker records gross cost — no free-tier deduction — so per-run attribution is consistent regardless of how far the monthly free tier has been consumed. The `billedMessagesCount` field is populated for attribution purposes but does not contribute to the USD estimate, since Pub/Sub bills on throughput bytes, not per-message.

Both the message count and total bytes figure are recorded for every operation. A pipeline that publishes ten thousand tiny messages and one that publishes ten large ones might have identical throughput cost but very different operational profiles; keeping both numbers means the analytics table can surface either cut.

## The dry-run pre-flight: enforcement before the spend

Here is where cost tracking becomes cost *control*.

The `BigQueryCostTracker` has an `estimateDryRun` method that submits a BigQuery dry-run job — the query is validated and estimated without actually executing — and returns a `CostMetrics` with only `estimatedCostUsd` and `billedBytesScanned` populated. All other fields are zero; this is a pre-flight estimate, not an execution record.

```java
// BigQueryCostTracker.java:193–234
public CostMetrics estimateDryRun(QueryJobConfiguration config, String runId) {
    QueryJobConfiguration dryRunConfig = config.toBuilder()
            .setDryRun(true)
            .build();
    Job dryRunJob = client.create(JobInfo.of(dryRunConfig));
    Job completedJob = dryRunJob.waitFor();
    // ... null-safety + fallback to getTotalBytesProcessed() if billed is null
    long bytesScanned = resolveDryRunBytes(qs, runId);
    double costUsd = bytesToUsd(bytesScanned, QUERY_COST_USD_PER_TIB);
    return CostMetrics.builder(runId)
            .billedBytesScanned(bytesScanned)
            .estimatedCostUsd(costUsd)
            .build();
}
```

A quick note on the dry-run contract: BigQuery dry-run jobs are designed to populate `getTotalBytesBilled()`, but in practice the field can be null or zero on some responses — because no billing event occurs on a job that never executes. The tracker falls back to `getTotalBytesProcessed()` and logs a `WARN` if that happens (`BigQueryCostTracker.java:303–317`). This is flagged in the Javadoc as a runtime guarantee to verify against the emulator integration test (`BigQueryCostTrackerIT`). Honest status: the fallback is there; whether you hit it depends on the BigQuery version responding to your project.

That estimated `CostMetrics` is the input to `BudgetGovernancePolicy`.

## Budget governance: `BudgetGovernancePolicy` and `BudgetViolationMode`

\index{BudgetGovernancePolicy}\index{BudgetViolationMode}\index{BudgetExceededException}

`BudgetGovernancePolicy` (`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/finops/BudgetGovernancePolicy.java`) is the enforcement gate. It holds a cost ceiling in USD and a `BudgetViolationMode` — either `BLOCK` or `WARN` — and exposes one method:

```java
// BudgetGovernancePolicy.java:116
public void checkBudget(CostMetrics projected, String runId) throws BudgetExceededException
```

The logic is strict-greater-than: if `projected.estimatedCostUsd() > ceilingUsd`, the violation triggers. If cost equals the ceiling exactly, the run is allowed. The boundary test in the unit suite makes this explicit:

```java
// BudgetGovernancePolicyTest.java:81–89
@Test
void block_mode_does_not_throw_when_cost_equals_ceiling_boundary() {
    // Boundary: cost == ceiling is ALLOWED (strict > semantics).
    BudgetGovernancePolicy policy =
            new BudgetGovernancePolicy(CEILING_USD, BudgetViolationMode.BLOCK);
    CostMetrics exactCeiling = metricsWithCost(CEILING_USD);
    assertThatCode(() -> policy.checkBudget(exactCeiling, RUN_ID))
            .doesNotThrowAnyException();
}
```

In `BLOCK` mode, a violation throws `BudgetExceededException`. The message is human-readable — `"Budget ceiling exceeded for run 'run-id': projected cost $31.2500 USD > ceiling $25.0000 USD"` — so it surfaces cleanly in a log or alert without additional formatting. The typed accessors (`getRunId()`, `getProjectedCostUsd()`, `getCeilingUsd()`) are there for programmatic handling (`BudgetExceededException.java:35–57`).

In `WARN` mode, the policy logs at `WARNING` level via `java.util.logging` and returns normally. The run continues.

The wiring into `DefaultRuntimeContext` looks like this:

```java
// BudgetGovernancePolicy.java:53–63 (Javadoc example)
BudgetGovernancePolicy budget =
        new BudgetGovernancePolicy(50.0, BudgetViolationMode.BLOCK);
RuntimeContext ctx = DefaultRuntimeContext.builder("run-1", "prod")
        .register(GovernancePolicy.class, budget)
        .build();

// Pre-flight check before submitting the job:
CostMetrics estimate = costTracker.estimateDryRun(queryConfig, ctx.runId());
budget.checkBudget(estimate, ctx.runId()); // throws BudgetExceededException if over ceiling
```

The flow is: `estimateDryRun` → `CostMetrics` → `checkBudget` → proceed or throw. If it throws, the BigQuery job is never submitted. The spend never happens. That is the difference between observability and control.

`BudgetGovernancePolicy` implements `GovernancePolicy` (`contracts/GovernancePolicy`) with no-op pass-throughs for `classify`, `maskingFor`, and `retentionFor` (`BudgetGovernancePolicy.java:162–182`). Cost enforcement and data governance are composable concerns. A pipeline that needs both registers a real `GovernancePolicy` delegate for classification and masking, and wraps it with `BudgetGovernancePolicy` for budget enforcement.

The policy is intentionally cloud-neutral. It imports only `java.*` and `com.enrichmeai.culvert.*` — no `com.google.cloud.*`, no `org.apache.beam.*`. The unit test suite asserts this invariant by grepping the source file for cloud imports (`BudgetGovernancePolicyTest.java:265–283`). `BudgetGovernancePolicy` could enforce budgets on Redshift queries, Azure Synapse runs, or any source that produces a `CostMetrics` record. The enforcement logic does not know or care what cloud generated the number.

The Python mirror in `data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/finops_api/budget.py` is a direct port: `BudgetViolationMode` as a `str, Enum` with `BLOCK = "block"` and `WARN = "warn"`, `BudgetExceededException` with the same typed properties, and `BudgetGovernancePolicy.check_budget()` with the same strict-greater-than semantics (`budget.py:29–209`).

## The sink: `BigQueryFinOpsSink` and the `cost_metrics` table

\index{BigQueryFinOpsSink}

`BigQueryFinOpsSink` (`data-pipeline-libraries-java/data-pipeline-gcp-bigquery-java/src/main/java/com/enrichmeai/culvert/gcp/bigquery/BigQueryFinOpsSink.java`) is the production implementation of `FinOpsSink`. It streams a row into a BigQuery table for every `record()` call, using `insertAll` for sub-second queryability.

The table name follows the convention `cost_metrics` (`BigQueryFinOpsSink.java:60`). Every field from both `CostMetrics` and `FinOpsTag` is flattened into columns. The `labels` and `extra` maps are stored as `RECORD<key STRING, value STRING>` arrays — BigQuery's only stable representation for arbitrary map data without a schema change per row. The wire format is built in `toRow()` (`BigQueryFinOpsSink.java:113–141`).

One operational consideration: streaming inserts land in BigQuery's streaming buffer. Rows are queryable within seconds but not immediately available to `COPY` or `EXPORT` jobs — the buffer flushes to managed storage on BigQuery's own schedule, usually within 90 minutes. For most cost analytics this is acceptable. For high-volume cost emission, a load-job-based variant is a future option; the `FinOpsSink` contract makes swapping it in a single constructor call.

Partial failures matter here. `InsertAllResponse` can succeed at the HTTP level while reporting per-row failures. `BigQueryFinOpsSink` treats any non-empty `getInsertErrors()` as a hard failure and throws `FinOpsInsertException` (`BigQueryFinOpsSink.java:101–104`). Silently dropping cost rows would defeat the purpose of having an audit trail. The failure is loud by design.

## Querying cost: `CostAnalysisQueries`

\index{CostAnalysisQueries}

`CostAnalysisQueries` (`data-pipeline-libraries-java/data-pipeline-gcp-bigquery-java/src/main/java/com/enrichmeai/culvert/gcp/bigquery/CostAnalysisQueries.java`) is a utility that loads named SQL blocks from a classpath resource (`sql/cost_analysis.sql`). Four queries ship:

- `cost_by_run` — total estimated USD and slot-milliseconds grouped by `run_id`, ordered by cost descending.
- `cost_by_stage` — total estimated USD grouped by the `stage` label key (UNNESTing the labels array).
- `top_expensive_runs_7d` — the ten most expensive `run_id`s in the past seven days.
- `budget_breach_log` — all rows where `estimated_cost_usd > ?` (positional parameter), ordered by timestamp descending.

The query that answers "which entity is my most expensive?" is two lines of SQL:

```sql
-- cost_analysis.sql (top_expensive_runs_7d, adapted for entity label)
SELECT run_id, SUM(estimated_cost_usd) AS total_estimated_cost_usd, ...
FROM cost_metrics
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY run_id ORDER BY total_estimated_cost_usd DESC LIMIT 10;
```

Without the `cost_metrics` table and the `run_id`-keyed rows that flow into it, that question requires a week of billing-export archaeology. With it, the answer is a weekend SQL query. That shift — from archaeology to query — is the point of the FinOps layer.

## A FinOps reality check

\index{FinOps!practices}

I will be direct here, because the framework ships first-class cost tracking and I want to be clear about what that gets you and what it does not.

Cost tracking is not cost control. The framework makes the data trivial to surface; the team has to choose to look at it on a cadence that catches problems while they are still small.

**Things that work.** Per-entity `FinOpsTag` on every Dataflow job, BigQuery query, and Pub/Sub batch, with a weekly query over `cost_metrics` that surfaces the top ten entities by daily spend. A fifteen-minute cost-trend review with the engineering lead and the product owner, once a week, looking at the deltas. Budget alerts at 50%, 75%, 90%, and 100% of monthly target — and the 100% alert must page the on-call, not just email a distribution list. GCS lifecycle rules that move landing bucket objects to Coldline after 90 days and Archive after a year: do this once at provisioning, never think about it again. Cloud Composer is the single most expensive resource in the stack — roughly £250–400/month for `ENVIRONMENT_SIZE_SMALL` — and the `docs/FINOPS_STRATEGY.md` policy is correct: Composer is disabled by default (`enable_composer = false` in Terraform, `deploy_composer = false` in the deploy workflow) and enabled only via explicit manual dispatch. Standing rule: any new Dataflow job runs with `--max-workers` set; jobs that want more get reviewed.

**Things that do not work.** Daily cost dashboards that nobody reads. Slack channels that fire on every budget alert until the channel is muted. Monthly cost optimisation reviews that get cancelled whenever the team is under pressure — which is always. Reactive optimisation after a finance complaint; by then the budget is spent and the muscle memory for preventing it next time is not built.

The `BudgetViolationMode.WARN` setting is development mode. In staging and production, use `BLOCK`. The reason is simple: if you allow the run to proceed when it is over budget, the cost ceiling is advisory rather than enforced, and advisory ceilings accumulate exceptions until they stop meaning anything. BLOCK mode means someone has to consciously raise the ceiling rather than quietly letting overruns through. That conversation is the one you want happening before the finance email arrives.

## What the polyglot mirror shows

One of the more interesting things about implementing both Java and Python cost types is what the mirroring reveals about the abstraction.

The Java `FinOpsTag` Javadoc says: "Replaces the older `FinOpsLabels` class on the Python side; the rename signals the universal vocabulary (AWS tags, Azure tags, GCP labels all map cleanly)" (`FinOpsTag.java:14–16`). The Python `labels.py` opens with the same rationale: "`labels` is a GCP-specific term; `tags` is the universal vocabulary" (`labels.py:5–7`). The rename happened in both languages, from the same motivation, to the same result.

That consistency is not coincidental. It is the outcome of designing the contract first and the implementation second. When you have a language-neutral name (`FinOpsTag`, `CostMetrics`, `BudgetGovernancePolicy`) that both languages have to implement, you cannot allow GCP terminology to leak into the core type — it would break the Java mirror immediately. The discipline of maintaining the mirror is also the discipline of keeping the contract clean.

The GCP predecessor in `gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/finops/tracker.py` used `BQ_COST_PER_TIB = 6.25` and wrote to a `finops_usage` table. Culvert 0.1.0 uses `QUERY_COST_USD_PER_TIB = 5.00` and the `cost_metrics` table. The rate difference reflects the updated 2025 GCP pricing; the table rename reflects the contract-first design. Both are correct for their context.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item The \texttt{FinOpsSink} contract is a single-method seam: \texttt{record(CostMetrics, FinOpsTag)}. Cloud-specific cost trackers (\texttt{BigQueryCostTracker}, \texttt{GcsCostTracker}, \texttt{PubSubCostTracker}) call it once per cost-incurring operation; the sink handles persistence. Attribution tags (\texttt{FinOpsTag}) are passed explicitly — not inferred from ambient context — because lossy attribution is the most common bug in cost tracking.
  \item Pricing constants are not magic numbers. BigQuery on-demand: $5.00/TiB where TiB = 2\textsuperscript{40} = \texttt{1\_099\_511\_627\_776}\ bytes (\texttt{BigQueryCostTracker.java:81,90}). GCS storage: per-GiB-month where GiB = 2\textsuperscript{30}; Standard \$0.020, Nearline \$0.010, Coldline \$0.004, Archive \$0.0012. Pub/Sub throughput: \$40.00/TiB. The Pub/Sub ticket that described the rate as \$0.04/MiB was off by 1000×; the code documents the correction.
  \item \texttt{BudgetGovernancePolicy} enforces a cost ceiling before the pipeline runs. \texttt{estimateDryRun()} yields a \texttt{CostMetrics} estimate; \texttt{checkBudget()} either throws \texttt{BudgetExceededException} (BLOCK mode) or logs a WARNING (WARN mode). Cost equals ceiling is allowed — the check is strict-greater-than. The policy is cloud-neutral: no \texttt{com.google.cloud.*} imports.
  \item \texttt{CostAnalysisQueries} ships four named SQL blocks — \texttt{cost\_by\_run}, \texttt{cost\_by\_stage}, \texttt{top\_expensive\_runs\_7d}, \texttt{budget\_breach\_log} — that answer the operational questions in seconds rather than a week of billing-export archaeology.
  \item Cost discipline is a habit, not a quarterly initiative. Use BLOCK mode in production. Set \texttt{--max-workers} on every Dataflow job. Run a fifteen-minute weekly cost review. Deploy Composer only on explicit dispatch. The framework makes the data available; the team has to choose to use it.
\end{itemize}
\end{takeaways}

\newpage
