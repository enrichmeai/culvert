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

## Observability auto-wiring (Sprint 12 T12.4 + T12.6)

`DefaultRuntimeContext` now auto-wires observability by default. Two hooks
are registered as advisory protocols (fall back to no-op silently when absent):

| Accessor | Hook interface | Purpose |
|----------|---------------|---------|
| `context.observability()` | `ObservabilityHook` | General-purpose: spans, counters, histograms, structured logs |
| `context.stageMetrics()` | `StageMetricsHook` | Typed: the three Culvert-standard metrics per stage (rows_processed, stage_latency_ms, error_count) |

### How auto-wiring works

1. **Driver side**: `DefaultRuntimeContext.fromAutoConfig(runId, env, config, AutoConfig.discover())` calls `ServiceLoader` for all registered hook impls and registers the first discovered one for each type. Pipeline authors who call `DefaultRuntimeContext.builder(...).build()` get no-op defaults, or can call `context.register(StageMetricsHook.class, myHook)` explicitly.

2. **Worker side (Beam/Dataflow)**: The `registry` field is `transient` (T10.6). After Beam deserializes the context to a worker, the first access to `context.stageMetrics()` or `context.observability()` triggers a lazy rebuild via `AutoConfig.discover()`. This means any `StageMetricsHook` registered with a `META-INF/services/com.enrichmeai.culvert.contracts.StageMetricsHook` file on the worker classpath will be discovered and used.

3. **T12.6 — no-arg constructors are now real**: `CloudMonitoringMetricsHook` and
   `CloudTraceObservabilityHook` (in `data-pipeline-gcp-observability-java`) now both
   expose no-arg constructors. Worker-side `AutoConfig.discover()` will instantiate them
   — no driver-side `register(...)` call needed for production Dataflow jobs. See
   `data-pipeline-gcp-observability-java/README.md` for configuration requirements.

### RuntimeContext.pipelineId() (T12.6)

`RuntimeContext` now declares `pipelineId()` with a default implementation returning
`runId()`. This replaces the previous silent proxy in `StageTransform`. The `pipeline_id`
label in Cloud Monitoring metrics and MDC will therefore reflect the contract method — and
implementations that override `pipelineId()` will see their value flow through automatically.

### Overriding with a custom hook

```java
StageMetricsHook myHook = ...; // e.g. new CloudMonitoringMetricsHook(client, projectId)
RuntimeContext ctx = DefaultRuntimeContext.builder("run-1", "prod")
        .register(StageMetricsHook.class, myHook)
        .build();
// ctx.stageMetrics() returns myHook
```

Or rely on auto-discovery (T12.6 — now works for GCP hooks):
```
# META-INF/services/com.enrichmeai.culvert.contracts.StageMetricsHook
com.enrichmeai.culvert.gcp.observability.CloudMonitoringMetricsHook
# Set one of: -Dculvert.gcp.project=<id>  OR  CULVERT_GCP_PROJECT=<id>  OR  ADC default project
```

## License

MIT — see [LICENSE](../../LICENSE) at the repository root.
