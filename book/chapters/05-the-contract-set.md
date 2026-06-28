# Chapter 5 — The Contract Set

I said in the previous chapter that the framework's relationship with the cloud lives entirely in its contracts. Let me be more precise than that, because I have a habit of writing from memory and then discovering that memory is wrong in exactly the ways that flatter the speaker.

The v1 manuscript — the raw GCP-origin memoir that became this book — describes "roughly a dozen Python protocols." Roughly a dozen is wrong. There are sixteen, and I have now gone and counted them properly, because the reader deserves better than a confident miscount. While I was at it, I also wrote about `Warehouse` having five methods. It has six. The one I dropped from memory is `copy` — the server-side table clone that BigQuery executes as a metadata operation and Snowflake serves as a `CLONE`. It is not the interesting one, which is precisely why I forgot it.

I am telling you this not to flag my own limitations (though there is that), but because the drift between what a design *feels like* and what it *actually is* turns out to be exactly the kind of thing the contracts prevent in the codebase itself. The contract is the memory you cannot argue with. Write it down, with types. If my prose summary of the surface diverges from the interface, the interface is right.

So: sixteen interfaces, one value type. Here is the real surface.

---

## Storage and I/O

Three contracts handle how data moves in and out of the pipeline. They sit at different levels of abstraction and they compose in a single natural pattern: a stage reads from a `Source`, optionally bounces intermediate objects through a `BlobStore`, and writes to a `Sink`. The stage never imports anything from a cloud module. The `RuntimeContext` carries the concrete implementations.

| Contract | Java | Python | Core methods |
|---|---|---|---|
| `BlobStore` | `BlobStore.java:18` | `blob_store.py:16` | `get`, `put`, `openInput`, `openOutput`, `list`, `exists`, `delete`, `copy` |
| `Source<T>` | `Source.java:19` | `source.py:38` | `read(context)` |
| `Sink<U>` | `Sink.java:16` | `source.py:42` | `write(records, context)` |

(`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/`)
(`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/`)

### BlobStore

`BlobStore`\index{BlobStore} is the lowest-level storage primitive. Eight methods: two bulk-transfer ones (`get` returns bytes, `put` overwrites); two streaming alternatives for large objects (`openInput` and `openOutput`, both caller-closes); `list` which yields URIs under a prefix in lexicographic order, returning an `Iterator<String>` rather than materialising the whole listing; and `exists`, `delete`, and `copy`. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/BlobStore.java:18`]

The thing that keeps `BlobStore` cloud-neutral is not what it does — it is what it refuses to do. The framework never parses URIs. A `gs://bucket/path` is an opaque string; the GCS adapter knows what to do with it. The Javadoc at line 59 explicitly states that cross-store copies (`gs://` to `s3://`) are out of scope: implementations may throw `UnsupportedOperationException` for foreign schemes. The boundary is documented, not just assumed.

Python reflects the same contract at [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/blob_store.py:16`], decorated `@runtime_checkable` so that `isinstance(impl, BlobStore)` works in tests without inheritance.

### Source\<T\> and Sink\<U\>

`Source<T>` is a single-method contract: `read(context)` returns a lazy `Iterator<T>`. The `@FunctionalInterface` annotation in Java is intentional — any lambda that accepts a `RuntimeContext` and returns an iterator qualifies. The Javadoc is explicit that `read` must be lazy: implementations must not materialise the full result in memory. That constraint propagates to every adapter. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Source.java:19`]

`Sink<U>` is the mirror: `write(records, context)` consumes the iterator. Also a `@FunctionalInterface`. Also lazy by expectation. Both live as Protocols in [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/source.py`] — Python can express covariant type variables that Java cannot, which is occasionally useful and never a source of confusion. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Sink.java:16`]

---

## Compute and pipeline composition

Four contracts describe what a pipeline *is* and what it *does*. They say nothing about scheduling or execution — that belongs to the orchestration layer.

| Contract | Java | Python | Core methods |
|---|---|---|---|
| `Warehouse` | `Warehouse.java:24` | `warehouse.py:25` | `query`, `execute`, `loadFromUri`, `merge`, `copy`, `tableExists` |
| `Pipeline` | `Pipeline.java:15` | `pipeline.py:19` | `name()`, `stages()`, `validate()` |
| `PipelineStage` | `PipelineStage.java:14` | `pipeline.py:28` | `name`, `inputs`, `outputs`, `execute(context)` |
| `Transform<V,W>` | `Transform.java:16` | `source.py:52` | `apply(records, context)` |

### Warehouse

`Warehouse`\index{Warehouse} is the tabular complement to `BlobStore`. Six operations — `query` (SELECT), `execute` (DML/DDL), `loadFromUri` (bulk load from blob storage), `merge` (standard upsert), `copy` (table clone), and `tableExists`. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Warehouse.java:24`]

The Javadoc at line 11 states the design constraint plainly: cloud-specific capabilities — BigQuery partitioning, Redshift sort keys, Snowflake clustering, Synapse distribution — do not appear on this interface. They live on cloud-specific extension classes in the cloud module. The reason is not philosophy. The reason is that putting BigQuery idioms on the shared interface breaks every non-GCP adapter immediately.

`fqtn` (fully-qualified table name) is, like all URIs in this framework, an opaque string. BigQuery parses it as `project.dataset.table`; Redshift and Snowflake parse it as `database.schema.table`. The contract specifies the convention; the implementation does the parsing. `loadFromUri` bridges `BlobStore` and `Warehouse`: hand it a blob URI and a target table and the warehouse arranges the bulk load. GCP's BigQuery does this in a `LoadJob`; Redshift does it with a `COPY ... FROM ... IAM_ROLE` statement. The call-site is identical in both cases — the protocol does not care which one fires.

A worked example, because the abstract version is hard to argue with and hard to evaluate. Here is what the `Warehouse` protocol looks like stripped to its real surface — and note the six methods, not five:

```python
# data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/warehouse.py:25
class Warehouse(Protocol):
    def query(self, sql: str, params=None) -> Iterator[Mapping[str, Any]]: ...
    def execute(self, sql: str, params=None) -> None: ...
    def load_from_uri(self, uri: str, target_table: str,
                      schema: EntitySchema) -> int: ...
    def merge(self, source_table: str, target_table: str,
              keys: List[str]) -> int: ...
    def copy(self, source_table: str, target_table: str) -> int: ...
    def table_exists(self, fqtn: str) -> bool: ...
```

The GCP implementation lives in `data-pipeline-gcp-bigquery`. A hypothetical AWS implementation would live in `data-pipeline-aws-redshift` and look something like this:

```python
class RedshiftWarehouse:
    def __init__(self, conn: redshift_connector.Connection):
        self._conn = conn

    def query(self, sql, params=None):
        cur = self._conn.cursor()
        cur.execute(sql, params or {})
        cols = [d[0] for d in cur.description]
        for row in cur:
            yield dict(zip(cols, row))

    def load_from_uri(self, uri, target_table, schema):
        copy_sql = f"COPY {target_table} FROM '{uri}' IAM_ROLE ... FORMAT CSV"
        cur = self._conn.cursor()
        cur.execute(copy_sql)
        return cur.rowcount
    # ...
```

These are different. The first one talks to BigQuery; the second one talks to Redshift. The protocol does not care. The pipeline code that calls `context.get(Warehouse).load_from_uri(...)` does not care. The decision about which `Warehouse` is in the runtime context is made once, at bootstrap, by whichever `culvert-*` cloud package the user has installed. That is the entire trick. Spring did this in 2003. We are not inventing anything.

### Pipeline and PipelineStage

`Pipeline` and `PipelineStage` are the composition contracts. `Pipeline` has three methods: `name()` returns a unique string identifier; `stages()` returns the ordered list of `PipelineStage` objects; `validate()` checks the graph — no orphan inputs, no cycles, every stage's declared inputs are produced by an earlier stage — and raises `IllegalStateException` if the pipeline cannot run. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Pipeline.java:15`]

`PipelineStage` carries four items: `name()`, `inputs()` (a list of upstream stage names), `outputs()` (a list of logical output names downstream stages reference), and `execute(context)`. The dependency edges are declared by string name, not by object reference. That keeps the graph data-serialisable: a Composer DAG renderer can read a `Pipeline` object and produce Airflow task dependency declarations without instantiating the stage implementations. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/PipelineStage.java:14`]

Both live in [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/pipeline.py:19`].

### Transform\<V, W\>

`Transform<V, W>` maps a stream of V records to a stream of W records via `apply(records, context)`, returning a lazy `Iterator<W>`. Like `Source` and `Sink` it is a `@FunctionalInterface`. The Javadoc notes that transforms should be pure where possible. The Python equivalent lives at [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/source.py:52`]. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Transform.java:16`]

`Transform` is the workhorse for field-level logic: type coercion, enrichment, PII redaction. A masking transform reads the `GovernancePolicy` from the `RuntimeContext`, applies the field masking rules, and emits sanitised records — without ever importing a cloud SDK.

---

## Operational seams

Six contracts cover the runtime concerns. They are the instruments by which the framework is observable, auditable, governable, and self-aware.

| Contract | Java | Python | Core methods |
|---|---|---|---|
| `JobControlRepository` | `JobControlRepository.java:25` | `job_control.py:27` | 11 methods (lifecycle + query + cost) |
| `ObservabilityHook` | `ObservabilityHook.java:20` | `observability.py:26` | `counter`, `gauge`, `histogram`, `log`, `span` |
| `StageMetricsHook` | `StageMetricsHook.java:32` | `stage_metrics.py:71` | `recordStageMetrics(metrics)` |
| `LineageEmitter` | `LineageEmitter.java:16` | `lineage.py:17` | `emit(event)` |
| `AuditEventPublisher` | `AuditEventPublisher.java:15` | `audit.py:17` | `publish(record)`, `flush()` |
| `GovernancePolicy` | `GovernancePolicy.java:20` | `governance.py:21` | `classify`, `maskingFor`, `retentionFor` |

### JobControlRepository

`JobControlRepository`\index{JobControlRepository} is the pipeline-job state machine. Every pipeline run is a row in a ledger; this contract describes the full CRUD on that ledger. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/JobControlRepository.java:25`]

Eleven methods. `createJob` inserts a new row in `CREATED` state. `updateStatus` advances the state machine. `markFailed` records structured error context including a URI to quarantined records. `markRetrying` bumps the retry counter. `cleanupPartialLoad` deletes partial rows before a retry attempt. The query side: `getJob` by run ID; `getPendingJobs` by system; `getEntityStatus` for orchestration gating; `getFailedJobs` for operator dashboards; `getFdpJobStatus` for FDP model tracking. And `updateCostMetrics`, which attaches cost figures to the job row after compute completes. That is the actual eleven — I am counting rather than claiming a round number.

The Javadoc at line 22 notes that implementations must be transactional within a single `runId`. That constraint is enforced by the backing store, not by the contract itself, but callers can rely on the guarantee. Python mirrors all eleven at [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/job_control.py:27`].

### ObservabilityHook

`ObservabilityHook`\index{ObservabilityHook} is the framework's single observability seam. Metrics, structured logs, and distributed traces all flow through this one interface. Three concerns, one dependency to inject. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/ObservabilityHook.java:20`]

Five methods: `counter(name, value, tags)` increments a monotonic counter; `gauge(name, value, tags)` sets a current value; `histogram(name, value, tags)` records a distribution sample; `log(level, message, fields)` emits a structured log line; `span(name)` opens an `AutoCloseable` tracing span. The nested `Span` interface carries `setAttribute` and `recordException`, and implements `AutoCloseable` so try-with-resources works cleanly.

The consolidation was deliberate. The earlier code had `MetricsCollector` for counters and gauges, `StructuredLogger` for logs, and OTEL helpers for traces. Keeping them separate meant every stage needed three injected dependencies and the first thing you forgot was the structured logger. A `CompositeObservabilityHook` can delegate to all three backends. Tags follow OpenTelemetry attribute conventions — string keys, string values. The Python contract at [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/observability.py:26`] reflects the same five methods; `span` returns an `AbstractContextManager` rather than a custom interface, which fits Python idioms without losing the contract guarantee.

### StageMetricsHook and StageMetrics

`StageMetricsHook` is a narrower, Culvert-specific companion to `ObservabilityHook`. Its single method is `recordStageMetrics(metrics)`, where `metrics` is a `StageMetrics` value. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/StageMetricsHook.java:32`]

`StageMetrics`\index{StageMetrics} is the companion value type — not a contract itself (no implementation is expected to implement it), but an immutable snapshot that the contract passes. In Java it is a `record`; in Python a `frozen=True` dataclass. Three label dimensions: `pipelineId`, `runId`, `stageName`. Three metric values: `rowsProcessed` (metric `culvert/rows_processed`, CUMULATIVE INT64), `stageLatencyMs` (metric `culvert/stage_latency_ms`, GAUGE DOUBLE), `errorCount` (metric `culvert/error_count`, CUMULATIVE INT64). Both enforce non-null labels in the constructor. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/StageMetrics.java:26`] [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/stage_metrics.py:32`]

Why a separate interface rather than three calls to `ObservabilityHook`? Because `ObservabilityHook` is a general-purpose surface — arbitrary name, arbitrary tags. The `StageMetricsHook` codifies the Culvert-specific semantic: one call per stage completion, three fixed metric series, a fixed label schema. It makes it structurally impossible to mis-name a metric or accidentally omit a label. The Javadoc at line 14 explains this directly, and I think it is one of the better small design decisions in the framework.

### LineageEmitter

`LineageEmitter` is as small as a contract gets: a single method, `emit(event)`, where `event` is a `LineageEvent`. The `@FunctionalInterface` annotation means any lambda that accepts a `LineageEvent` qualifies. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/LineageEmitter.java:16`]

`LineageEvent` carries the four OpenLineage-shaped sub-structures: source, destination, pipeline, and audit metadata. GCP's adapter routes to Cloud Data Catalog / Dataplex; a cloud-neutral implementation targets a Marquez or OpenLineage Proxy endpoint. The Python protocol at [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/lineage.py:17`] is structurally identical: one `emit(event)` method.

### AuditEventPublisher

`AuditEventPublisher` publishes `AuditRecord` values with at-least-once delivery semantics. Two methods: `publish(record)` may buffer for throughput; `flush()` blocks until all buffered records have been acknowledged by the backing event bus. `flush()` is idempotent — calling it on an empty buffer is a no-op. The framework calls `flush()` at pipeline-stage boundaries and at shutdown, so the publisher never silently drops records. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/AuditEventPublisher.java:15`]

The separation from `ObservabilityHook` is deliberate. Audit records have compliance requirements — at-least-once delivery, idempotent flush, durable backing store — that do not apply to metrics or logs. Conflating them would either weaken the audit guarantees or impose unnecessary complexity on metrics implementations. You do not want your counter-increment to trigger a Pub/Sub flush. Python at [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/audit.py:17`].

### GovernancePolicy

`GovernancePolicy` answers three questions about any field or table: what is its sensitivity classification, what masking applies, and what retention policy applies. `classify(field, table)` returns a `DataClassification` enum value, defaulting to `INTERNAL` and never throwing. `maskingFor(field, table)` returns an `Optional<MaskingPolicy>`, empty if no masking applies. `retentionFor(table)` returns an `Optional<RetentionPolicy>`, empty for indefinite retention. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/GovernancePolicy.java:20`]

The default implementation — `StaticGovernancePolicy`, added in Stage 3 — reads a YAML file and requires no cloud service. That makes governance testable without credentials, which matters more than it sounds. The Python protocol at [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/governance.py:21`] reflects the same three methods using snake_case (`masking_for`, `retention_for`).

---

## Configuration and dependency injection

Three contracts handle what the pipeline needs before it can run: credentials, cost attribution, and the context object that wires everything together.

| Contract | Java | Python | Core methods |
|---|---|---|---|
| `SecretProvider` | `SecretProvider.java:18` | `secrets.py:18` | `get(name, version)` |
| `FinOpsSink` | `FinOpsSink.java:16` | `finops.py:23` | `record(metrics, tags)` |
| `RuntimeContext` | `RuntimeContext.java:33` | `runtime.py:38` | `runId()`, `environment()`, `config()`, named accessors, `get(type)`, `register(type, impl)` |

### SecretProvider — the side-by-side

`SecretProvider` is the simplest contract to reason about and the one that most clearly exposes the language-specific idiom difference in the set. There is one method. In Java you need two overloads to express a default argument; in Python you need one method with a default parameter. Both compile to the same semantic. Here is the full surface in both languages:

**Java** [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/SecretProvider.java:18`]:

```java
@FunctionalInterface
public interface SecretProvider {

    /**
     * Return the secret value at {@code name}.
     *
     * Implementations should never log the returned value, even at DEBUG level.
     *
     * @throws java.util.NoSuchElementException if the secret does not exist.
     */
    String get(String name, String version);

    /** Convenience: fetch the {@code "latest"} version. */
    default String get(String name) {
        return get(name, "latest");
    }
}
```

**Python** [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/secrets.py:18`]:

```python
@runtime_checkable
class SecretProvider(Protocol):
    """Look up secrets by name. Implementations call Secret Manager,
    AWS Secrets Manager, Azure Key Vault, HashiCorp Vault, or just
    read from the environment.
    """

    def get(self, name: str, version: str = "latest") -> str:
        """Return the secret value at `name` (and optional `version`).

        Raises KeyError if the secret does not exist. Implementations
        should never log the returned value, even at DEBUG level.
        """
        ...
```

Same contract. The error type differs — Java throws `NoSuchElementException`, Python raises `KeyError` — because those are the idiomatic choices in each language for a missing key. The prohibition on logging the returned value appears in both docstrings in identical terms. Implementations range from GCP Secret Manager to AWS Secrets Manager, Azure Key Vault, HashiCorp Vault, or plain environment variables. The protocol does not care which one fires at runtime.

### FinOpsSink

`FinOpsSink` receives cost metrics from cloud-specific cost trackers and persists them wherever the team aggregates cost data. `record(metrics, tags)` is the single method. `CostMetrics` carries the numeric figures (estimated USD, billed bytes scanned, billed bytes written); `FinOpsTag` carries the attribution dimensions (pipeline name, stage name, system ID, environment). [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/FinOpsSink.java:16`]

The Javadoc at line 12 explains the explicit-tags decision: `FinOpsTag` is passed directly rather than read from the `RuntimeContext`. Cost emissions are infrequent and lossy attribution is the most common bug in cost-tracking systems. Making attribution tags explicit in the method signature makes the data flow visible and keeps attribution from silently disappearing if a context is mis-wired. Python at [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/finops.py:23`].

### RuntimeContext

`RuntimeContext`\index{RuntimeContext} is the framework's dependency-injection container. It is not a factory or a registry in the traditional IoC sense; it is the object that every stage method receives, carrying both configuration data and pointers to all the registered contract implementations. [`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/RuntimeContext.java:33`]

Three categories of member. Identity and configuration: `runId()`, `pipelineId()`, `environment()`, `config()`. Named accessors for each registered contract: `secrets()`, `observability()`, `stageMetrics()`, `lineage()`, `finops()`, `governance()`. And the generic registry: `get(Class<T> protocolType)` and `register(Class<T> protocolType, T impl)`.

The `get` and `register` methods are the extension points. The framework's auto-config bootstrap calls `register` for each contract that an installed cloud module provides. Test code calls `register` to inject mocks. A stage that needs a `BlobStore` calls `context.get(BlobStore.class)` and gets back whatever the runtime has registered — GCS in production, an in-memory fake in unit tests. Change the cloud by changing which module is on the classpath. The stage code is untouched.

The Python protocol at [`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/runtime.py:38`] reflects the same structure with one extra note in the module docstring at line 17: when a `RuntimeContext` crosses a distributed compute boundary — a Beam worker, for example — only `run_id`, `environment`, and `config` serialise. The registry is transient and is rebuilt worker-side by the auto-config mechanism. That constraint belongs on the concrete implementation, not the contract, but the Python module docstring flags it explicitly so implementors know it is coming.

---

## How the families compose

The four families are not isolated; `RuntimeContext` is the thread that stitches them together. A typical stage touch-point: `PipelineStage.execute(context)` is the entry point. The stage calls `context.get(BlobStore.class)` to retrieve its source storage, `context.get(Warehouse.class)` to reach its target table, `context.observability().counter(...)` to emit metrics, and `context.lineage().emit(...)` to publish a lineage event. Nothing imported from a cloud module. By the time the stage returns, the ledger row is updated via `JobControlRepository`, the lineage event is queued, the audit record is buffered for the next `flush()`, and the stage metrics — via `StageMetricsHook` and its typed `StageMetrics` value — are on their way to wherever the team has registered them to go.

That is the surface. Nothing else in the framework talks to a cloud SDK directly. If you find yourself reaching for `from google.cloud import bigquery` in a file that does not live under a `culvert-gcp-*` module, you have made a mistake and the CI grep check will tell you so.

---

\begin{takeaways}
**The sixteen contracts and one value type**

The contracts are: `BlobStore`, `Source<T>`, `Sink<U>` (storage/I-O); `Warehouse`, `Pipeline`, `PipelineStage`, `Transform<V,W>` (compute/pipeline); `JobControlRepository`, `ObservabilityHook`, `StageMetricsHook`, `LineageEmitter`, `AuditEventPublisher`, `GovernancePolicy` (operational seams); `SecretProvider`, `FinOpsSink`, `RuntimeContext` (configuration/DI). `StageMetrics` is the companion value type, not a contract. All sixteen Java interfaces are in `data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/`; all sixteen Python Protocols are in `data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/`. The Java reactor is built and frozen at `java-1.0.0`; the Python Protocols exist and are `@runtime_checkable`; neither is yet published to Maven Central or PyPI.

**The design rules that keep them cloud-neutral**

URIs are opaque strings. The framework never parses them. Cloud-specific features (BigQuery partitioning, Redshift sort keys) go on cloud-specific extension classes, not on the shared interface. `RuntimeContext` carries the registry; stages call `context.get(ContractType.class)` and never import a cloud SDK. The one exception is `ObservabilityHook`'s nested `Span` — a handle type, not a seam. Audit and observability are separate contracts because they have different delivery guarantees.

**The memory-vs-reality check**

The v1 manuscript said "roughly a dozen protocols." There are sixteen. It showed `Warehouse` with five methods. There are six — `copy` is the one that does not announce itself. The contracts are the corrective: write the interface down, with types, and the surface is what the types say it is, not what you remember.
\end{takeaways}

\newpage
