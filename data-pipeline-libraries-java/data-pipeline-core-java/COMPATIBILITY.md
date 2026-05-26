# Interface Compatibility — data-pipeline-core (Java) 0.1.0

Polyglot Stage 0 of the framework redesign defines the **target shape** of the eleven Protocols as Java interfaces. It does not refactor any existing Java code to satisfy them.

This document captures the gap between the new Java interfaces and the existing Java code (`deployments/mainframe-segment-transform-java/`), and the gap between the Java interfaces and their Python siblings. Stage 2 (refactor GCP implementations) consumes both.

## Existing Java code

The only Java code in the repo today is `deployments/mainframe-segment-transform-java/`, which contains:

- `com.gcp.pipeline.segment.transform.MainframeSegmentPipeline` — Beam pipeline `main` class.
- `com.gcp.pipeline.segment.transform.FormatFixedWidthDoFn` — A Beam `DoFn` (not a `Source`/`Sink`/`Transform`).
- `com.gcp.pipeline.segment.transform.SegmentTemplate` — YAML config model.
- `com.gcp.pipeline.segment.transform.FieldFormatter` — Field-value formatting helper.

This is a single deployment, not a library. None of these classes implement the new interfaces today.

**Gaps to reconcile (Stage 2 / Stage 3 Java):**
- groupId `com.gcp.pipeline` should become `com.enrichmeai.culvert.gcp.dataflow.segmenttransform` (or a sibling under `com.enrichmeai.culvert`).
- Java 11 → Java 17 (the framework's floor; matches the parent POM).
- JUnit 4 → JUnit 5 (matches the parent POM).
- Lombok is in use (`@Slf4j` and similar) — acceptable for a deployment, but **never inside the libraries**. Drop or keep per deployment owner's call.
- The Beam DoFns need adapters in `data-pipeline-gcp-dataflow-java` that wrap a `Source<T>`/`Sink<U>`/`Transform<V, W>` into a Beam `DoFn`. The DoFn-as-Transform style stays valid for Dataflow-specific logic; the adapter just makes pure transforms portable.

## Per-interface alignment with Python siblings

Each Java interface in `com.enrichmeai.culvert.contracts` is a one-to-one mirror of the Python Protocol in `data_pipeline_core.contracts`. Method names use Java conventions (camelCase) instead of Python (snake_case); structural shape is identical.

| Java | Python | Notes |
|---|---|---|
| `Source<T>` | `Source[T]` | Java invariant generics vs Python covariant. Use wildcards (`Source<? extends T>`) at call sites for variance. |
| `Sink<U>` | `Sink[U]` | Same story; use `Sink<? super U>` for contravariant call sites. |
| `Transform<V, W>` | `Transform[V, W]` | Invariant in Java as in Python. |
| `PipelineStage.name()` | `PipelineStage.name` | Field in Python, getter method in Java (Java doesn't have public read-only fields on interfaces). |
| `PipelineStage.inputs()` | `PipelineStage.inputs` | Returns `List<String>` vs `Sequence[str]`. |
| `Pipeline.validate()` | `Pipeline.validate()` | Throws `IllegalStateException` in Java vs raises in Python. |
| `RuntimeContext.get(Class<T>)` | `RuntimeContext.get(type)` | Type-safe in Java thanks to generics. |
| `RuntimeContext.register(Class<T>, T)` | `RuntimeContext.register(protocol, impl)` | Type-safe in Java. |
| `JobControlRepository` — 11 methods | `JobControlRepository` — 11 methods | One-to-one. `Optional<>` where Python uses `Optional[...]`. `LocalDate` where Python uses `date`. `Instant` where Python uses `datetime`. |
| `BlobStore.openInput` / `openOutput` | `BlobStore.open(uri, mode)` | Java splits the modal `open` into two clearer methods (the Python `mode` arg was a `"rb"`/`"wb"` string). |
| `Warehouse.query(sql, params)` | `Warehouse.query(sql, params)` | `Iterator<Map<String, Object>>` vs `Iterator[Mapping[str, Any]]`. |
| `AuditEventPublisher.publish` / `flush` | same | One-to-one. |
| `GovernancePolicy.{classify, maskingFor, retentionFor}` | `GovernancePolicy.{classify, masking_for, retention_for}` | Method name casing. Returns `DataClassification` / `Optional<MaskingPolicy>` / `Optional<RetentionPolicy>`. |
| `LineageEmitter.emit(LineageEvent)` | same | `LineageEvent` is a record-of-Optionals in Java, TypedDict in Python. Same key names, same semantics. |
| `ObservabilityHook.{counter, gauge, histogram, log, span}` | same | One-to-one. `Span` is an `AutoCloseable` inner interface in Java; the Python `span()` returns an `AbstractContextManager`. Equivalent. |
| `FinOpsSink.record(metrics, tags)` | same | One-to-one. |
| `SecretProvider.get(name, version)` | same | Includes a `default get(name)` convenience method in Java. |

## Per-supporting-type alignment

| Java | Python | Notes |
|---|---|---|
| `record AuditRecord(...)` (11 fields) | `@dataclass AuditRecord(...)` (11 fields) | Mirror. Java uses `Instant` for `processedTimestamp` (vs `datetime`), `Map<String, Object>` for `metadata` (vs `Dict[str, Any]`). Has a `Builder` because 11 positional args is hostile. |
| `record CostMetrics(...)` | `@dataclass CostMetrics` | Mirror. Has a `Builder` and a `zero(runId)` factory. |
| `record FinOpsTag(...)` | `@dataclass FinOpsTag` | Mirror. Has an `of(system, environment, costCenter, owner, runId)` factory that empties `extra`. |
| `record MaskingPolicy`, `MaskingStrategy`, `RetentionPolicy`, `DataClassification` | same | Mirrors. The enums match Python `str` enum values exactly. |
| `record PipelineJob(...)` (23 fields with optionals) | `@dataclass PipelineJob(...)` | Mirror. Has a `Builder` (23 fields is genuinely hostile positionally). |
| `record EntityStatus`, `FailedJob`, `FdpJobStatus` | TypedDicts | Java records replace TypedDicts. `Optional<...>` fields stand in for the Python `total=False` pattern. |
| `record SchemaField`, `EntitySchema` | `@dataclass` | Mirror. Has factory methods (`SchemaField.required`, `EntitySchema.of`). |
| `record LineageEvent`, `LineageSource`, `LineagePipeline`, `LineageDestination`, `LineageAudit` | TypedDicts | Java records, all fields `Optional<>` where Python had `total=False`. |
| `enum JobStatus`, `FailureStage`, `JobType` | string enums | Mirror. `getValue()` returns the wire-format string. |

## Decisions deliberately diverging from Python

1. **`BlobStore.open()` split into `openInput()` and `openOutput()`.** Python `open(uri, mode='rb')` couples mode to the call; Java is clearer as two methods. Functionally equivalent.

2. **`ObservabilityHook.Span` is a nested interface, not an opaque context manager.** Java doesn't have Python's `AbstractContextManager` pattern out of the box, but `AutoCloseable` is idiomatic. Adds `setAttribute(String, String)` and `recordException(Throwable)` so consumers can annotate spans inline; the Python equivalent is implementation-defined.

3. **Builders on `AuditRecord`, `CostMetrics`, `PipelineJob`.** Python uses keyword arguments + `default_factory`; Java doesn't have either. The Builder pattern is idiomatic when a record has more than 4-5 fields.

4. **`SecretProvider.get(String)` convenience default.** Java supports `default` methods on interfaces; this saves callers from typing `"latest"` every time.

These divergences are documented in Javadoc on the affected types. None of them change the underlying contract; serialised forms (audit records, cost metrics, lineage events) round-trip cleanly between Java and Python.

## What Stage 2 (Java) must do

For each cloud-specific implementation we eventually ship:

1. **`data-pipeline-gcp-bigquery-java`** — implements `Warehouse`, `JobControlRepository`, `FinOpsSink`. Wraps `com.google.cloud.bigquery.BigQuery`. Reuses the existing Python `BigQueryJobControlRepository` SQL (the SQL is language-neutral; only the client driver changes).

2. **`data-pipeline-gcp-gcs-java`** — implements `BlobStore`. Wraps `com.google.cloud.storage.Storage`.

3. **`data-pipeline-gcp-pubsub-java`** — implements `AuditEventPublisher`. Wraps `com.google.cloud.pubsub.v1.Publisher`.

4. **`data-pipeline-gcp-dataflow-java`** — Beam-on-Dataflow execution module. Provides Beam DoFn adapters for `Source<T>`/`Sink<U>`/`Transform<V, W>`. Houses the shared transforms (HDR/TRL parsing, schema validation, audit-column writers) that future Java Beam deployments depend on. The existing `deployments/mainframe-segment-transform-java/` code refactors against this module.

5. **`data-pipeline-gcp-observability-java`** — implements `ObservabilityHook` against OTEL + Cloud Trace + Cloud Monitoring.

6. **`data-pipeline-gcp-secrets-java`** — implements `SecretProvider` against Secret Manager.

7. **`data-pipeline-tester-java`** — base test classes, in-memory fakes for each contract, contract test suites.

Effort estimate (bottom-up, mirroring the Python COMPATIBILITY estimate):

| Module | Effort | Risk |
|---|---|---|
| `data-pipeline-gcp-bigquery-java` | 3-4 days | Medium (Warehouse is the largest interface) |
| `data-pipeline-gcp-gcs-java` | 2 days | Low |
| `data-pipeline-gcp-pubsub-java` | 1 day | Low |
| `data-pipeline-gcp-dataflow-java` | 4-5 days | Medium-high (Beam DoFn adapters are subtle) |
| `data-pipeline-gcp-observability-java` | 2 days | Low-medium |
| `data-pipeline-gcp-secrets-java` | 0.5 days | Low |
| `data-pipeline-tester-java` | 2 days | Low |
| **Total** | **~14-17 engineer-days** | **Mostly Low-Medium** |

That maps to ~3-4 engineer-weeks for the full Java GCP module set, comparable to the Python Stage 2 estimate of 2-3 weeks. Reasonable — the Java side rides on the existing Google Cloud client libraries the same way the Python side does.
