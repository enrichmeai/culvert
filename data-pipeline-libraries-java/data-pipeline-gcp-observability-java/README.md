# data-pipeline-gcp-observability (Java)

Google Cloud observability adapters for the Culvert data pipeline framework, JVM edition. Provides three GCP implementations of cloud-neutral contracts defined in `data-pipeline-core-java`:

| Class | Contract | Backend |
|-------|----------|---------|
| `CloudTraceObservabilityHook` | `ObservabilityHook` | Cloud Trace (via OpenTelemetry exporter) |
| `DataCatalogLineageEmitter` | `LineageEmitter` | Data Catalog (tag-based lineage) |
| `CloudMonitoringMetricsHook` | `StageMetricsHook` | Cloud Monitoring (custom metrics) |

## Status

**Version 0.1.0 — multi-sprint deliverable:**
- `CloudTraceObservabilityHook` + `DataCatalogLineageEmitter` — Sprint 2 (issue [#24](https://github.com/enrichmeai/culvert/issues/24))
- `CloudMonitoringMetricsHook` — Sprint 12 (issue [#65](https://github.com/enrichmeai/culvert/issues/65))

## Install (Maven)

```xml
<dependency>
    <groupId>com.enrichmeai.culvert</groupId>
    <artifactId>data-pipeline-gcp-observability</artifactId>
    <version>0.1.0</version>
</dependency>
```

Pulls in `data-pipeline-core` (the contracts) plus `google-cloud-monitoring`,
`google-cloud-datacatalog`, and the OpenTelemetry/Cloud Trace exporter
(all versions managed by the Google Cloud `libraries-bom` pinned to `26.39.0`).

---

## CloudMonitoringMetricsHook

`StageMetricsHook` implementation that emits Culvert's three standard pipeline
metrics to Google Cloud Monitoring via `MetricServiceClient`.

### Metric schema

| Metric type | Kind | Value type |
|-------------|------|------------|
| `custom.googleapis.com/culvert/rows_processed` | CUMULATIVE | INT64 |
| `custom.googleapis.com/culvert/stage_latency_ms` | GAUGE | DOUBLE |
| `custom.googleapis.com/culvert/error_count` | CUMULATIVE | INT64 |

### Label schema

Every time series carries these three labels populated from `StageMetrics`:

| Label key | Source field | Example |
|-----------|-------------|---------|
| `pipeline_id` | `StageMetrics.pipelineId()` | `"invoice-etl"` |
| `run_id` | `StageMetrics.runId()` | `"run-2026-06-01"` |
| `stage_name` | `StageMetrics.stageName()` | `"transform"` |

Note: `run_id` is potentially high-cardinality in Cloud Monitoring. This is
intentional — the issue spec explicitly requires it to uniquely identify
pipeline runs in dashboards.

### Wiring project-id

```java
// 1. Build the MetricServiceClient (picks up Application Default Credentials)
MetricServiceClient client = MetricServiceClient.create();

// 2. Construct the hook with your GCP project ID
StageMetricsHook hook = new CloudMonitoringMetricsHook(client, "my-gcp-project");

// 3. Use at each stage boundary
StageMetrics metrics = new StageMetrics(
    "invoice-etl",       // pipelineId
    "run-2026-06-01",    // runId
    "transform",         // stageName
    1_000L,              // rowsProcessed
    250.0,               // stageLatencyMs
    0L                   // errorCount
);
hook.recordStageMetrics(metrics);

// 4. Close the hook (and the underlying client) when done
((AutoCloseable) hook).close();
```

### Monitoring failure isolation

If the Cloud Monitoring RPC fails (network, auth, quota), the exception is
**logged at WARN and swallowed** — the pipeline continues uninterrupted.
Failures are counted in `CloudMonitoringMetricsHook.monitoringFailureCount()`
for use in tests and operational alerting.

---

## CloudTraceObservabilityHook

`ObservabilityHook` backed by OpenTelemetry whose span/metric providers
export to Cloud Trace and Cloud Monitoring. Wiring is decoupled from the
class — callers supply an already-configured `OpenTelemetry` instance with
a `TraceExporter` from `com.google.cloud.opentelemetry:exporter-trace`.

See the class Javadoc for construction details.

---

## DataCatalogLineageEmitter

`LineageEmitter` that writes `LineageEvent` objects as Data Catalog tags on a
configurable entry. Each event becomes one `Tag` attached to the configured
entry. Tag fields mirror the four sub-records of `LineageEvent` (source,
pipeline, destination, audit), flattened to scalar strings.

See the class Javadoc and `DataCatalogLineageEmitterTest` for construction
and usage details.
