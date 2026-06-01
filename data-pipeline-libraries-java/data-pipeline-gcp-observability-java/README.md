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

---

## Structured-logging bridge (T12.2)

### Overview

`CulvertMdcPopulator` is a pure slf4j/Logback concern (no GCP or Apache Beam
imports). It writes three Culvert context fields into the SLF4J MDC at the
start of a stage execution and clears them in a `finally` block — even when
the stage body throws. Pipeline authors do not need to add MDC calls manually.

### MDC keys populated

| Key | Description |
|---|---|
| `run_id` | The pipeline run identifier |
| `stage_name` | The name of the executing stage |
| `pipeline_id` | The pipeline identifier |

The key constants are `CulvertMdcPopulator.RUN_ID_KEY`, `STAGE_NAME_KEY`, and
`PIPELINE_ID_KEY`.

### Usage

```java
// Void stage body:
CulvertMdcPopulator.withStageContext(runId, stageName, pipelineId, () -> {
    LOG.info("reading records");            // → MDC fields are present
});

// Stage body that returns a value:
List<Record> result = CulvertMdcPopulator.withStageContext(
        runId, stageName, pipelineId, () -> repository.readAll());
```

Both the `Runnable` and the `Supplier<T>` overloads clear the MDC even when
the body throws a `RuntimeException`. The exception propagates unwrapped.

---

## Activating Cloud Logging JSON output

The module ships a ready-to-use Logback configuration at
`logback-cloud.xml` (on the classpath inside the jar). It uses
`net.logstash.logback:logstash-logback-encoder` to emit each log record as a
single-line JSON object whose fields are compatible with the Google Cloud
Logging structured-log ingestion format.

**You must add the runtime dependencies to your application's pom.xml** (they
are not transitive from this module — the module itself only requires
`slf4j-api` at runtime):

```xml
<!-- Logback binding + JSON encoder — runtime/provided scope only needed -->
<dependency>
    <groupId>ch.qos.logback</groupId>
    <artifactId>logback-classic</artifactId>
    <version>1.4.14</version>
    <scope>runtime</scope>
</dependency>
<dependency>
    <groupId>net.logstash.logback</groupId>
    <artifactId>logstash-logback-encoder</artifactId>
    <version>7.2</version>
    <scope>runtime</scope>
</dependency>
```

### Activation options

**Option 1 — copy to classpath root as `logback.xml` (auto-discovered):**

Copy `logback-cloud.xml` from the jar to your application's
`src/main/resources/logback.xml`. Logback picks it up on startup with no
further configuration.

**Option 2 — JVM system property:**

```
-Dlogback.configurationFile=path/to/logback-cloud.xml
```

Useful for Dataflow workers via `--defaultWorkerLogLevel` or pipeline options.

**Option 3 — include from your own `logback.xml`:**

```xml
<configuration>
  <include resource="logback-cloud.xml"/>
  <!-- add application-specific appenders here -->
</configuration>
```

---

## JSON field layout

When `logback-cloud.xml` (or an equivalent LogstashEncoder configuration) is
active, each log record is emitted as a JSON object with at minimum:

| JSON field | Source | Notes |
|---|---|---|
| `severity` | Logback level | `INFO`, `WARN`, `ERROR`, `DEBUG`, `TRACE` |
| `message` | Log message | |
| `@timestamp` | Event time | RFC 3339 / ISO-8601, UTC with millis |
| `run_id` | MDC | Set by `CulvertMdcPopulator.withStageContext` |
| `stage_name` | MDC | Set by `CulvertMdcPopulator.withStageContext` |
| `pipeline_id` | MDC | Set by `CulvertMdcPopulator.withStageContext` |
| `logger_name` | Logger | Fully qualified class name |
| `thread_name` | Thread | |

`run_id`, `stage_name`, and `pipeline_id` are present only inside a
`withStageContext` call. Outside that scope they are absent from the JSON (MDC
keys are cleared).

Cloud Logging uses the `severity` field for log-level routing when
`jsonPayload.severity` is present.

---

## Auto-wiring via DefaultRuntimeContext (Sprint 12 T12.4)

`DefaultRuntimeContext` exposes two observability accessors, both advisory (no-op if not registered):

| Accessor | Interface | Impl in this module |
|----------|-----------|---------------------|
| `context.observability()` | `ObservabilityHook` | `CloudTraceObservabilityHook` |
| `context.stageMetrics()` | `StageMetricsHook` | `CloudMonitoringMetricsHook` |

Both classes are listed in `META-INF/services/` so `AutoConfig.discover()` knows about them. However, **neither has a no-arg constructor** (they both require a pre-built cloud client + config). `ServiceLoader` will silently skip them at auto-discovery time. Register explicitly for production pipelines:

```java
// Tracing
OpenTelemetry otel = ...; // build with TraceExporter for Cloud Trace
ObservabilityHook obsHook = new CloudTraceObservabilityHook(otel, "my-pipeline");

// Metrics
MetricServiceClient client = MetricServiceClient.create();
StageMetricsHook metricsHook = new CloudMonitoringMetricsHook(client, "my-gcp-project");

RuntimeContext ctx = DefaultRuntimeContext.builder("run-1", "prod")
        .register(ObservabilityHook.class, obsHook)
        .register(StageMetricsHook.class, metricsHook)
        .build();
```

`StageTransform` (in `data-pipeline-gcp-dataflow-java`) resolves both hooks worker-side via `context.observability()` and `context.stageMetrics()` — the T10.6 transient-registry pattern. MDC fields (`run_id`, `stage_name`, `pipeline_id`) are also set inline in `StageTransform.ExecuteStageFn` for each stage execution.

---

## Building

```bash
# Unit tests only (no Docker, no GCP credentials)
mvn -pl data-pipeline-gcp-observability-java -am test

# Offline (CI / sprint verification)
mvn -o -pl data-pipeline-gcp-observability-java -am test
```
