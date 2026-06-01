# data-pipeline-core (Java)

The cloud-neutral kernel of the Culvert data pipeline framework, Java edition. Sibling of the Python `data-pipeline-core` package; same contracts, JVM language. Zero dependencies on `google.cloud.*`, `software.amazon.awssdk.*`, or `com.azure.*`.

## Status

**Version 0.1.0 — Polyglot Stage 0.** The interfaces define the *target shape* of the framework on the JVM. They mirror the Python `data-pipeline-core==0.1.0` Protocol set one-for-one. The existing Java code in `deployments/mainframe-segment-transform-java/` has not yet been refactored to satisfy these contracts; see `COMPATIBILITY.md` for the per-interface gap analysis.

## Install (Maven)

```xml
<dependency>
    <groupId>com.enrichmeai.culvert</groupId>
    <artifactId>data-pipeline-core</artifactId>
    <version>0.1.0</version>
</dependency>
```

Like its Python sibling this package is intentionally tiny. It is meant to be used alongside one or more cloud-specific modules (`data-pipeline-gcp-bigquery-java`, `data-pipeline-gcp-gcs-java`, `data-pipeline-gcp-dataflow-java`, ...) that provide concrete implementations.

## The contracts

Eleven interfaces in `com.enrichmeai.culvert.contracts` — the entire framework-to-cloud seam:

| Interface | Purpose | Default impl |
|---|---|---|
| `Source<T>` | Yields records into the pipeline | none — supplied per pipeline |
| `Sink<U>` | Writes records out of the pipeline | none — supplied per pipeline |
| `Transform<V, W>` | Maps records V to W | none — supplied per pipeline |
| `Pipeline` | A graph of `PipelineStage` nodes | none — the user's class |
| `PipelineStage` | A named, dependency-aware stage | derived from `@Pipeline`/`@Source`/`@Sink` (Stage 3 Java) |
| `RuntimeContext` | Framework's DI container + run metadata | `RuntimeContextImpl` (Stage 3 Java) |
| `JobControlRepository` | Pipeline-job state machine | `BigQueryJobControlRepository` (in `data-pipeline-gcp-bigquery-java`) |
| `BlobStore` | Object storage abstraction | `GcsBlobStore` (in `data-pipeline-gcp-gcs-java`) |
| `Warehouse` | Tabular query/load abstraction | `BigQueryWarehouse` (in `data-pipeline-gcp-bigquery-java`) |
| `AuditEventPublisher` | Emits audit records | `PubSubAuditPublisher` (in `data-pipeline-gcp-pubsub-java`) |
| `GovernancePolicy` | Masking/retention/classification lookups | `StaticGovernancePolicy` (cloud-neutral default) |
| `LineageEmitter` | OpenLineage events | `OpenLineageEmitter` (cloud-neutral default) |
| `ObservabilityHook` | Metrics/logs/traces, general-purpose seam | OTEL-backed (Sprint 2 / `data-pipeline-gcp-observability-java`) |
| `StageMetricsHook` | Typed per-stage Culvert metrics (rows/latency/errors) | `CloudMonitoringMetricsHook` (Sprint 12 T12.1 / `data-pipeline-gcp-observability-java`) |
| `FinOpsSink` | Cost-metric aggregation | `BigQueryFinOpsSink` (in `data-pipeline-gcp-bigquery-java`) |
| `SecretProvider` | Secret lookup | env-var default |

## Architectural rules

1. **No cloud SDK imports.** Anywhere in this module that needs to talk to a cloud, it goes through one of the interfaces. CI fails the build if `grep -r "com.google.cloud\|software.amazon\|com.azure" src/main/java` finds anything.
2. **No application framework.** Plain Maven, plain Java. No Spring, no Quarkus, no Micronaut. Libraries should not force framework choices on consumers. See [the rationale in CLAUDE.md](../../CLAUDE.md) (and the saved-memory note: "feedback-java-no-frameworks").
3. **Interfaces are small.** Each contract covers the operations every serious cloud supports and stops there. Cloud-specific extensions (BigQuery clustering, S3 lifecycle, ADLS hierarchical namespaces) live in the cloud-specific module as extension classes, not in core.
4. **Implementations register via ServiceLoader.** A cloud module's `META-INF/services/com.enrichmeai.culvert.contracts.Warehouse` lists its concrete class. Bootstrap-time the runtime invokes each registered impl. Mirrors the Python entry-point auto-config pattern.

## What's in v0.1.0 (Polyglot Stage 0)

- `com.enrichmeai.culvert.contracts` — the 15 interfaces.
- `com.enrichmeai.culvert.{audit,lineage,finops,governance,jobcontrol,schema}` — the records and enums those interfaces reference.
- `COMPATIBILITY.md` — per-interface gap analysis against the existing Java port at `deployments/mainframe-segment-transform-java/` and against the Python implementations.

## What's NOT in v0.1.0

- The runtime container, annotations (`@Pipeline`, `@Source`, ...), or ServiceLoader bootstrap. Those land in Stage 3 Java.
- Any concrete implementation of any interface. Those live in the `data-pipeline-gcp-*-java` modules (Stages 2-3).
- Beam adapters that wrap a `Source<T>`/`Sink<U>`/`Transform<V,W>` into a Beam `DoFn`. Those land in `data-pipeline-gcp-dataflow-java`.

## Build

```bash
mvn -f data-pipeline-libraries-java/pom.xml clean install
```

## Observability auto-wiring (Sprint 12 T12.4)

`DefaultRuntimeContext` now auto-wires observability by default. Two hooks
are registered as advisory protocols (fall back to no-op silently when absent):

| Accessor | Hook interface | Purpose |
|----------|---------------|---------|
| `context.observability()` | `ObservabilityHook` | General-purpose: spans, counters, histograms, structured logs |
| `context.stageMetrics()` | `StageMetricsHook` | Typed: the three Culvert-standard metrics per stage (rows_processed, stage_latency_ms, error_count) |

### How auto-wiring works

1. **Driver side**: `DefaultRuntimeContext.fromAutoConfig(runId, env, config, AutoConfig.discover())` calls `ServiceLoader` for all registered hook impls and registers the first discovered one for each type. Pipeline authors who call `DefaultRuntimeContext.builder(...).build()` get no-op defaults, or can call `context.register(StageMetricsHook.class, myHook)` explicitly.

2. **Worker side (Beam/Dataflow)**: The `registry` field is `transient` (T10.6). After Beam deserializes the context to a worker, the first access to `context.stageMetrics()` or `context.observability()` triggers a lazy rebuild via `AutoConfig.discover()`. This means any `StageMetricsHook` registered with a `META-INF/services/com.enrichmeai.culvert.contracts.StageMetricsHook` file on the worker classpath will be discovered and used.

3. **No-arg constructor limitation**: `CloudMonitoringMetricsHook` (and `CloudTraceObservabilityHook`) require constructor arguments (client + project-id), so ServiceLoader silently skips them at auto-discovery time. Worker-side resolution therefore falls back to `NoOpStageMetricsHook` unless a future config-driven constructor is added. For now, register the hook explicitly on the driver side for production pipelines.

### Overriding with a custom hook

```java
StageMetricsHook myHook = ...; // e.g. new CloudMonitoringMetricsHook(client, projectId)
RuntimeContext ctx = DefaultRuntimeContext.builder("run-1", "prod")
        .register(StageMetricsHook.class, myHook)
        .build();
// ctx.stageMetrics() returns myHook
```

Or via AutoConfig if your hook has a no-arg constructor and a `META-INF/services` entry:
```
# META-INF/services/com.enrichmeai.culvert.contracts.StageMetricsHook
com.example.MyNoArgMetricsHook
```

## License

MIT — see [LICENSE](../../LICENSE) at the repository root.
