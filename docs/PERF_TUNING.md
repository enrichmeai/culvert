# Dataflow Perf/Load Test — Tuning Notes

**Sprint:** 16 · **Ticket:** T16.1 · **Issue:** [#108](https://github.com/enrichmeai/culvert/issues/108)  
**Status:** PREP ONLY — agent authored config + notes; **Joseph runs the live benchmark**

> **needs-engineer:** every command in §1 costs real GCP money.  No command in
> this document was executed by the agent.  Complete the `/finops-estimate` gate
> in §0 before proceeding.

---

## 0. FinOps gate — mandatory before any live run

Before submitting a live Dataflow job:

1. Run the `/finops-estimate` skill inside Claude Code (or the canonical cost
   estimation flow for this project).  Provide the job parameters from
   `deployments/reference-e2e-gcp/perf-test-dataflow.properties`:
   - Machine type: `n2-standard-4`, up to `maxNumWorkers=20`
   - Estimated wall-clock: **TODO — fill from first real run** (see §4)
   - Region: `<YOUR_GCP_REGION>`
2. Review the cost breakdown table that `/finops-estimate` returns.
3. Approve the run explicitly before proceeding to §1.

Rough back-of-envelope ceiling (do NOT rely on this — run `/finops-estimate`):
- n2-standard-4 Dataflow price ≈ $0.056/vCPU-hour + $0.003/GB-hour (us-central1,
  as of mid-2026; prices change).
- 20 workers × 4 vCPU × T hours ≈ budget ceiling before you commit.
- Add shuffle storage, GCS reads/writes, and any downstream BigQuery queries.

The `BudgetGovernancePolicy` in `DefaultRuntimeContext` (wired in the reference
pipeline context) is set to `BudgetViolationMode.WARN` — it will not block the
run, but it will log a warning if the cumulative `CostMetrics` stub cost
(`≈ $0.000005` per stage, emitted by `NoOpReadStage` / `NoOpTransformStage`)
exceeds the ceiling.  The real Dataflow compute cost is tracked separately —
see §3 for how to capture it.

---

## 1. Prerequisites before the first live run

The following must be in place before running any command in this document.
None of these are set up by the prep agent (T16.1 scope is config + notes only).

### 1a. Launcher entry point

`deployments/reference-e2e-gcp/` **does not yet have a `public static void main`
that calls `DataflowPipeline#runOnDataflow(DataflowPipelineOptions)`.**  The
pipeline currently runs only on `DirectRunner` (structural/CI tests).  Add a
launcher class before executing any Dataflow submission:

```java
// deployments/reference-e2e-gcp/src/main/java/.../ReferenceE2EPipelineLauncher.java
public class ReferenceE2EPipelineLauncher {
    public static void main(String[] args) {
        DataflowPipelineOptions opts =
            PipelineOptionsFactory.fromArgs(args)
                                  .withValidation()
                                  .as(DataflowPipelineOptions.class);
        List<PipelineStage> stages = List.of(
            new NoOpReadStage(),
            new NoOpTransformStage()
        );
        DataflowPipeline pipeline = new DataflowPipeline("reference-e2e-gcp", stages);
        PipelineResult result = pipeline.runOnDataflow(opts);
        result.waitUntilFinish();
    }
}
```

Wire a `PerfRunLauncher` maven exec target or fat-jar build as needed.

### 1b. GCP infra

- GCS bucket for `stagingLocation` / `tempLocation` exists.
- Service account email is provisioned with the IAM roles listed in
  `deployments/reference-e2e-gcp/README.md` (observability + FinOps sections).
- Dataflow API enabled in the project.

### 1c. Build the fat jar

```bash
# Install Culvert library artifacts first (not published to Maven Central):
cd data-pipeline-libraries-java
mvn -pl data-pipeline-core-java,data-pipeline-gcp-dataflow-java,\
data-pipeline-orchestration-java,data-pipeline-gcp-bigquery-java,\
data-pipeline-gcp-gcs-java -am -DskipTests install

# Build the reference-e2e-gcp deployment jar:
cd ../deployments/reference-e2e-gcp
mvn -DskipTests package
```

---

## 2. Running the benchmark (Joseph runs)

> **STOP:** complete §0 (FinOps gate) and §1 (prerequisites) first.

### 2a. Submit via CLI flags (recommended for first pass)

Substitute all `<…>` placeholders with your project values:

```bash
# *** Joseph runs — NOT executed by agent ***
java -cp target/reference-e2e-gcp-1.0.0-SNAPSHOT.jar \
  com.enrichmeai.culvert.e2e.ReferenceE2EPipelineLauncher \
  --runner=DataflowRunner \
  --project=<YOUR_GCP_PROJECT_ID> \
  --region=<YOUR_GCP_REGION> \
  --stagingLocation=gs://<YOUR_STAGING_BUCKET>/staging/reference-e2e-gcp \
  --tempLocation=gs://<YOUR_STAGING_BUCKET>/tmp/reference-e2e-gcp \
  --serviceAccount=<YOUR_DATAFLOW_SA>@<YOUR_GCP_PROJECT_ID>.iam.gserviceaccount.com \
  --numWorkers=2 \
  --maxNumWorkers=20 \
  --autoscalingAlgorithm=THROUGHPUT_BASED \
  --workerMachineType=n2-standard-4 \
  --diskSizeGb=30 \
  --labels=project=culvert-framework,system=reference-e2e-gcp,environment=perf,managed_by=manual-perf-run
```

All flags above map to `DataflowPipelineOptions` / `DataflowPipelineWorkerPoolOptions`
setters verified from `beam-runners-google-cloud-dataflow-java-2.55.0.jar` (javap):

| CLI flag | Java setter | Interface |
|---|---|---|
| `--project` | `setProject(String)` | `DataflowPipelineOptions` |
| `--region` | `setRegion(String)` | `DataflowPipelineOptions` |
| `--stagingLocation` | `setStagingLocation(String)` | `DataflowPipelineOptions` |
| `--tempLocation` | `setTempLocation(String)` | `GcpOptions` |
| `--serviceAccount` | `setServiceAccount(String)` | `DataflowPipelineOptions` |
| `--numWorkers` | `setNumWorkers(int)` | `DataflowPipelineWorkerPoolOptions` |
| `--maxNumWorkers` | `setMaxNumWorkers(int)` | `DataflowPipelineWorkerPoolOptions` |
| `--autoscalingAlgorithm` | `setAutoscalingAlgorithm(AutoscalingAlgorithmType)` | `DataflowPipelineWorkerPoolOptions` |
| `--workerMachineType` | `setWorkerMachineType(String)` | `DataflowPipelineWorkerPoolOptions` |
| `--diskSizeGb` | `setDiskSizeGb(int)` | `DataflowPipelineWorkerPoolOptions` |
| `--labels` | `setLabels(Map)` | `DataflowPipelineOptions` |

The enum constants verified: `NONE`, `BASIC`, `THROUGHPUT_BASED` (from
`DataflowPipelineWorkerPoolOptions.AutoscalingAlgorithmType`).

### 2b. Fixed-pool pass (optional, for controlled comparison)

Run a second pass with autoscaling disabled to measure throughput at a fixed
worker count.  This isolates framework overhead from GCP scheduler variance:

```bash
# *** Joseph runs — NOT executed by agent ***
# Same as 2a but replace autoscaling flags:
  --autoscalingAlgorithm=NONE \
  --numWorkers=10 \
  --maxNumWorkers=10
```

---

## 3. What to measure

Capture all of the following during (and immediately after) the run.

### 3a. Dataflow throughput

In the Dataflow UI (console.cloud.google.com → Dataflow → Jobs):

| Metric | Where | Record |
|---|---|---|
| Elements per second (per stage) | Job graph → select a step → "Throughput" tab | rows/sec peak + average |
| Wall-clock job duration | Job detail → "Total time" | seconds / minutes |
| Peak worker count | Job detail → autoscaling graph | count |
| Time to first autoscale event | Autoscaling graph | seconds from job start |

### 3b. S13 FinOps cost trackers

The `NoOpReadStage` and `NoOpTransformStage` call `context.finops().record(CostMetrics, FinOpsTag)`
with **stub values** (`estimatedCostUsd=0.000005`, `billedBytesScanned=1_000_000`).
These are framework wiring placeholders — not the real Dataflow compute cost.

To capture actual downstream service cost (BigQuery, GCS), wire a
`BigQueryCostTracker` or `GcsCostTracker` in the context and call
`trackJob(completedJob, runId, tag)` after each BQ/GCS operation.  Then query
the `cost_metrics` table using the four SQL queries from the README
(`cost_by_run`, `cost_by_stage`, `top_expensive_runs_7d`, `budget_breach_log`).

The real Dataflow compute cost appears in GCP Billing under the job label
`system=reference-e2e-gcp` (if you applied the `--labels` flag in §2a).
Pull it from the Billing console or via:

```bash
# *** Joseph runs — NOT executed by agent ***
gcloud billing budgets list --billing-account=<YOUR_BILLING_ACCOUNT> 2>/dev/null
# Or use GCP Cost Management → Cost table → filter by label "system=reference-e2e-gcp"
```

### 3c. Cloud Monitoring metrics (observability slice)

If `data-pipeline-gcp-observability-java` is on the classpath with a real GCP
project configured, the `CloudMonitoringMetricsHook` emits:

```bash
# *** Joseph runs — NOT executed by agent ***
gcloud monitoring time-series list \
  --filter='metric.type="custom.googleapis.com/culvert/stage_latency_ms"' \
  --project=<YOUR_GCP_PROJECT_ID> \
  --interval-start-time=$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)
```

Capture `culvert/stage_latency_ms` (per-stage latency) and
`culvert/rows_processed` (per-stage throughput counter) for both `NoOpReadStage`
and `NoOpTransformStage`.

### 3d. Autoscaling behaviour

From the Dataflow UI autoscaling graph, note:

- Time from job start to first scale-up event (ms / sec)
- Maximum worker count reached
- Whether the job scaled back down before completion
- Any scale-down latency (time between throughput drop and worker removal)

---

## 4. Expected baselines (TODO — fill from real run)

All values below are **placeholders**.  Fill them in after Joseph's first
benchmark run.  They must not be treated as measured values until then.

| Metric | Baseline (TODO) | Tuning target |
|---|---|---|
| Throughput — NoOpReadStage | **TODO rows/sec** | > X rows/sec |
| Throughput — NoOpTransformStage | **TODO rows/sec** | > X rows/sec |
| Wall-clock (2-worker start, autoscale to N) | **TODO min** | < Y min |
| Peak worker count reached | **TODO** | ≤ 20 |
| Time to first autoscale event | **TODO sec** | < 120 sec |
| Estimated Dataflow compute cost per run | **TODO USD** | < $Z (per /finops-estimate ceiling) |
| BQ slot-ms (from BigQueryCostTracker) | **TODO** | baseline TBD |

After recording actuals, commit an update to this table and close the
`needs-engineer` label on issue #108.

---

## 5. Tuning levers

Use these levers if the baseline does not meet targets.

### 5a. Worker count

- **Increase `maxNumWorkers`** if throughput is CPU-bound (workers are at 100%
  CPU during peak phases).  Set to 40 or 80 for large historical backfills.
- **Decrease `numWorkers` (start)** to 1 if you want to measure framework
  overhead with no parallelism, then compare to the autoscaled result.

### 5b. Machine type

| Scenario | Recommended type |
|---|---|
| Default baseline (current) | `n2-standard-4` (4 vCPU / 16 GB) |
| Memory pressure at peak workers | `n2-standard-8` (8 vCPU / 32 GB) |
| Shuffle-heavy stages (future real I/O) | `n2-highmem-8` (8 vCPU / 64 GB) |

Do not move to a larger machine type without first profiling the bottleneck
(use Cloud Profiler or `gcloud dataflow metrics list` for CPU/memory per step).

### 5c. Batch size (Beam bundle size)

Beam's default bundle size is determined by the runner's splitting policy.
For the NoOp stages (no source, no sink) the bundle size has no practical
impact today.  When real I/O stages are wired:

- For BigQuery reads: increase `--maxBundleSizeBytes` or use `withRowRestriction`
  to partition the source.
- For GCS reads: use `FileIO.read()` with `withBatchSize()`.
- For Pub/Sub streaming (future): tune `maxNumWorkers` and the subscription's
  message backlog.

### 5d. Beam fusion

Beam fuses compatible transforms into a single bundle step to reduce
serialization overhead.  Fusion can be inspected in the Dataflow execution
graph (fused steps appear as a single node).

To **disable fusion** for profiling individual stage costs:
```bash
# *** Joseph runs — NOT executed by agent ***
--experiments=disable_runner_v2_reason_string,unfusedstages
```
Re-enable fusion (the default) for production runs.

### 5e. Autoscaling algorithm comparison

| Algorithm | When to use |
|---|---|
| `THROUGHPUT_BASED` (default for this test) | Variable-throughput batch; Dataflow adjusts workers based on measured bundle throughput |
| `NONE` | Fixed-pool controlled passes; isolates framework overhead |
| `BASIC` | Deprecated in favour of `THROUGHPUT_BASED`; prefer `THROUGHPUT_BASED` |

Run a `NONE` pass at 10 workers to get a deterministic baseline, then compare
to the `THROUGHPUT_BASED` run at `maxNumWorkers=20` to quantify the autoscaler's
effect on wall-clock time and cost.

---

## 6. Appendix — config file reference

The committed config file is at:

```
deployments/reference-e2e-gcp/perf-test-dataflow.properties
```

It contains all parameters from §2a in a properties format with inline comments
explaining each setting and the rationale.  When a launcher `main()` is wired
(§1a), it can load this file via `PipelineOptionsFactory.fromArgs(...)` after
converting each `key=value` line to a `--key=value` JVM flag.

---

*Authored by dev-agent (T16.1 prep); Joseph runs the live benchmark.  No GCP
command was executed during authoring of this document.*
