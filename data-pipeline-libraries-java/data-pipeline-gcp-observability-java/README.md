# data-pipeline-gcp-observability

Google Cloud observability adapters for the Culvert framework.

## What is in this module

| Class | Purpose |
|---|---|
| `CloudTraceObservabilityHook` | `ObservabilityHook` implementation backed by OpenTelemetry exporting spans to Cloud Trace |
| `DataCatalogLineageEmitter` | `LineageEmitter` implementation that writes lineage events as Data Catalog tags |
| `CulvertMdcPopulator` | Structured-logging bridge — populates SLF4J MDC with Culvert context keys for every stage execution |

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

## Building

```bash
# Unit tests only (no Docker, no GCP credentials)
mvn -pl data-pipeline-gcp-observability-java -am test

# Offline (CI / sprint verification)
mvn -o -pl data-pipeline-gcp-observability-java -am test
```
