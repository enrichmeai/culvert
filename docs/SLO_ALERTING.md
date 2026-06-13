# Culvert GCP — SLO / Alerting Reference

**Status:** Sprint 16 (T16.3, #107) · **Audience:** SRE, platform engineer  
**Cross-references:**
- Architecture overview: [`docs/framework-evolution/10-architecture.md`](framework-evolution/10-architecture.md)
- Reference deployment: [`deployments/reference-e2e-gcp/`](../deployments/reference-e2e-gcp/)
- Operational runbook: [`docs/RUNBOOK.md`](RUNBOOK.md)

---

## 1. Overview

This document defines SLIs, SLOs, and the alert-wiring approach for Culvert GCP pipelines. Every SLI maps to a **signal source** that actually exists in the framework — no invented telemetry. The "Wiring status" column explicitly marks which alerts are available now vs. which require an engineer to configure live Cloud Monitoring.

**Signal sources available today:**

| Source | Description |
|---|---|
| **Cloud Monitoring time series** | `CloudMonitoringMetricsHook` pushes 3 custom metrics after each stage; requires `roles/monitoring.metricWriter` on the Dataflow SA |
| **BigQuery `pipeline_jobs`** | `BigQueryJobControlRepository` persists job state, timing, and error codes for every run |
| **BigQuery `cost_metrics`** | `BigQueryFinOpsSink` streams one row per `FinOpsSink.record()` call |
| **Cloud Logging (MDC fields)** | `StageTransform.ExecuteStageFn` populates `run_id`, `stage_name`, `pipeline_id` on every log line |

---

## 2. Cloud Monitoring metrics (emitted by `CloudMonitoringMetricsHook`)

All three metrics are emitted in a single `CreateTimeSeries` RPC per stage completion. They share the label set `{pipeline_id, run_id, stage_name}`.

| Metric type | Kind | Value type | Notes |
|---|---|---|---|
| `custom.googleapis.com/culvert/rows_processed` | CUMULATIVE | INT64 | Auto-instrumented value is **0** (sentinel `ROWS_PROCESSED_UNKNOWN`) — see §2.1. Real count is emitted only by stages that call the hook directly (e.g. `DataQualityTransform`). |
| `custom.googleapis.com/culvert/stage_latency_ms` | GAUGE | DOUBLE | Wall-clock elapsed time for `PipelineStage.execute()` in milliseconds. Reliable for all stages. |
| `custom.googleapis.com/culvert/error_count` | CUMULATIVE | INT64 | `1` when `execute()` throws; `0` on success (auto-instrumented path). Real per-row error count from `DataQualityTransform` is additive to this. |

### 2.1 `rows_processed` caveat

`StageTransform.ExecuteStageFn` auto-emits `rows_processed = 0` (the constant `ROWS_PROCESSED_UNKNOWN`) because `PipelineStage.execute()` is `void` — the framework cannot observe element counts from the execute contract. `DataQualityTransform` overrides this by calling `context.stageMetrics().recordStageMetrics(...)` directly after exhausting its iterator, supplying real `rowsProcessed` and `errorCount` values. Any SLI that relies on throughput (rows/s) must therefore be **scoped to stages that implement explicit metric emission** — auto-instrumented stages always report 0.

---

## 3. SLI → SLO → Alert table

> **Legend for "Wiring status":**
> - `active` — metric/query exists now; alert rule can be configured today.
> - `needs-engineer` — the metric is emitted by the framework but the Cloud Monitoring alert rule (MQL / alerting policy) must be created by an engineer with project access.
> - `BigQuery-query` — SLI is derived from a BigQuery SQL query, not from a Cloud Monitoring time series; no native Cloud Monitoring alerting without a custom export.

| # | SLI (what we measure) | SLO (target) | Alert threshold | Signal source | Wiring status |
|---|---|---|---|---|---|
| 1 | **Pipeline success rate** — fraction of `pipeline_jobs` runs with `status = 'SUCCEEDED'` per day, per `system_id` | ≥ 99% of daily runs succeed (rolling 7-day window) | Alert when ≥ 2 consecutive failures for the same `system_id` and `extract_date` | `pipeline_jobs` table: `COUNT(*) FILTER (WHERE status='FAILED') / COUNT(*)` | `BigQuery-query` — needs-engineer to schedule the query and pipe results to alerting (Cloud Monitoring custom metric export, PagerDuty, or Alertmanager) |
| 2 | **Pipeline freshness / latency** — wall-clock time from `extract_date` to `completed_at` for `status = 'SUCCEEDED'` runs | `completed_at` within 4 hours of `extract_date` (configurable per pipeline) | Alert when `TIMESTAMP_DIFF(completed_at, TIMESTAMP(extract_date), HOUR) > 4` | `pipeline_jobs.completed_at` - `pipeline_jobs.extract_date` | `BigQuery-query` — needs-engineer to schedule and route |
| 3 | **Stage latency p99** — 99th percentile of `custom.googleapis.com/culvert/stage_latency_ms` per `stage_name` over a 1-hour window | p99 ≤ 300,000 ms (5 min) per stage; adjust per SLA | Alert when p99 > 300,000 ms in any 15-min alignment period | `custom.googleapis.com/culvert/stage_latency_ms` (GAUGE DOUBLE), label `stage_name` | `needs-engineer` — create MQL alerting policy on `custom.googleapis.com/culvert/stage_latency_ms` |
| 4 | **Stage error rate** — per-stage `error_count > 0` from Cloud Monitoring, over a 1-hour window | Zero `error_count` events in production; any `error_count = 1` is a page | Alert when `error_count > 0` for any `{pipeline_id, stage_name}` in a 5-min window | `custom.googleapis.com/culvert/error_count` (CUMULATIVE INT64) | `needs-engineer` — create MQL alerting policy; filter on `error_count > 0` |
| 5 | **DQ quarantine rate** — fraction of runs per `system_id` where `error_code = 'DQ_VALIDATION_FAILURE'` | ≤ 1% of daily runs quarantine rows | Alert when quarantine rate exceeds 1% over a 7-day window, or when a single run's `error_count > 500` rows | `pipeline_jobs` where `error_code = 'DQ_VALIDATION_FAILURE'`; quarantine file on GCS | `BigQuery-query` + `needs-engineer` for Cloud Monitoring export |
| 6 | **Estimated cost per run** — `SUM(estimated_cost_usd)` from `cost_metrics` grouped by `run_id` | Per-run cost ≤ configured `finops.budget.ceiling_usd` (default `100.0` USD) | Alert on any `budget_breach_log` row (cost > ceiling); `BudgetGovernancePolicy` in BLOCK mode throws `BudgetExceededException` immediately | `cost_metrics` table (SQL); `BudgetGovernancePolicy` log WARNING / exception | `BigQuery-query` — not a Cloud Monitoring time series; needs-engineer to export or schedule query alert |
| 7 | **Cloud Monitoring write reliability** — `CloudMonitoringMetricsHook.monitoringFailureCount()` | Zero monitoring write failures per run | Alert when WARN log `CloudMonitoringMetricsHook: failed to write metrics` appears in Cloud Logging | Cloud Logging: filter on `textPayload=~"CloudMonitoringMetricsHook: failed to write metrics"` | `needs-engineer` — create a Cloud Logging-based alert policy (log-based metric or log sink to alerting) |

---

## 4. Alert wiring guide

### 4.1 Cloud Monitoring metrics (SLIs 3 and 4)

These are the only SLIs directly backed by Cloud Monitoring time series today. Both require an engineer to create an **Alerting Policy** in the GCP project where the Dataflow jobs run.

**Stage latency p99 alert (SLI 3) — example MQL:**
```
fetch global
| metric 'custom.googleapis.com/culvert/stage_latency_ms'
| group_by [metric.stage_name, metric.pipeline_id], [val: percentile(value.stage_latency_ms, 99)]
| condition val > 300000
```

**Stage error count alert (SLI 4) — example MQL:**
```
fetch global
| metric 'custom.googleapis.com/culvert/error_count'
| align delta(5m)
| group_by [metric.stage_name, metric.pipeline_id], [val: sum(value.error_count)]
| condition val > 0
```

**IAM required:** The Dataflow service account must have `roles/monitoring.metricWriter`. The engineer creating the alert policy must have `roles/monitoring.alertPolicyEditor`.

**Project resolution:** `CloudMonitoringMetricsHook` resolves the GCP project from:
1. System property `culvert.gcp.project`
2. Environment variable `CULVERT_GCP_PROJECT`
3. ADC default (`gcloud config set project <PROJECT_ID>`)

All three metrics include labels `pipeline_id`, `run_id`, `stage_name` — scope alerts by `pipeline_id` to avoid cross-pipeline noise.

### 4.2 BigQuery-query SLIs (SLIs 1, 2, 5, 6)

Pipeline success rate, freshness, DQ quarantine rate, and cost ceiling are derived from BigQuery tables, not from Cloud Monitoring time series. Options for alerting:

**Option A — Scheduled BigQuery query + Pub/Sub notification:**
Use BigQuery scheduled queries or Cloud Workflows to run the detection SQL on a schedule; publish alerts via Pub/Sub → Cloud Monitoring custom metric → Alerting policy.

**Option B — Cloud Monitoring log-based metrics:**
Export `pipeline_jobs` status events via Dataflow pipeline log lines; create log-based metrics.

**Option C — External alerting (Grafana, PagerDuty, etc.):**
Connect BigQuery to Grafana via the BigQuery data source plugin; configure threshold alerts in the dashboard.

Until Option A/B/C is wired, engineers should run the detection SQL queries manually or as scheduled jobs. Queries are documented in [`RUNBOOK.md §2`](RUNBOOK.md).

**Budget breach detection SQL (SLI 6):**
```sql
SELECT run_id, estimated_cost_usd, system, environment, cost_center, owner, timestamp
FROM `<project>.finops_dataset.cost_metrics`
WHERE estimated_cost_usd > <ceiling_usd>
ORDER BY timestamp DESC;
```

**Pipeline success rate SQL (SLI 1):**
```sql
SELECT
    system_id,
    extract_date,
    COUNTIF(status = 'FAILED') AS failed_count,
    COUNT(*) AS total_count,
    ROUND(100.0 * COUNTIF(status = 'SUCCEEDED') / COUNT(*), 2) AS success_rate_pct
FROM `<project>.job_control.pipeline_jobs`
WHERE extract_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
GROUP BY system_id, extract_date
HAVING success_rate_pct < 99
ORDER BY extract_date DESC;
```

### 4.3 Log-based alert (SLI 7 — monitoring write failures)

Create a Cloud Logging alerting policy with the filter:
```
textPayload=~"CloudMonitoringMetricsHook: failed to write metrics"
severity=WARNING
resource.type="dataflow_step"
```

Note: `monitoringFailureCount()` is an in-process counter on `CloudMonitoringMetricsHook` — it is not pushed to Cloud Monitoring automatically. The WARN log line is the operational signal.

---

## 5. `BudgetGovernancePolicy` — what it is and what it is not

`BudgetGovernancePolicy` (`data-pipeline-core-java`) is a **pre-flight gate** that compares a `CostMetrics` estimate (from `BigQueryCostTracker.estimateDryRun()`) against a configured ceiling before a run is submitted.

- It does NOT emit a Cloud Monitoring metric.
- In `BLOCK` mode it throws `BudgetExceededException` — the Airflow task fails and the run never starts.
- In `WARN` mode it logs a `WARNING` via `java.util.logging` — the run proceeds.

The `budget_breach_log` SQL query over `cost_metrics` (§4.2) is the primary retrospective signal. The exception log line in the DAG task is the real-time BLOCK signal.

Wire the exception as an alert: create a log-based metric on `textPayload=~"BudgetExceededException"` or `textPayload=~"Budget ceiling exceeded"` in Cloud Logging and attach an alerting policy.

---

## 6. Runbook cross-reference

| Failure scenario | SLI affected | Runbook section |
|---|---|---|
| DQ quarantine | SLIs 1, 5 | [RUNBOOK §5.1](RUNBOOK.md) |
| Budget breach (BLOCK) | SLI 6 | [RUNBOOK §5.2](RUNBOOK.md) |
| Partial load / retry | SLIs 1, 4 | [RUNBOOK §5.3](RUNBOOK.md) |
| Cloud Monitoring write failure | SLI 7 | [RUNBOOK §5.4](RUNBOOK.md) |
| Audit event write failure | — | [RUNBOOK §5.5](RUNBOOK.md) |
| Stage latency spike | SLI 3 | [RUNBOOK §2.4](RUNBOOK.md) |
| Stage error (execute throws) | SLIs 1, 4 | [RUNBOOK §2.1, §2.4](RUNBOOK.md) |
