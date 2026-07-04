# Appendix A — Library Reference

This appendix is a compact reference to the public surface of every Culvert library. It is intentionally telegraphic — a lookup table, not a tutorial. Consult the module README or the contract Javadoc / docstring for the full API. All libraries are at version **0.1.0**, built and held; nothing has been published to Maven Central or PyPI yet. The coordinated release under the `culvert` namespace is future work. Java `groupId` is `com.enrichmeai.culvert`; Python distributions are currently named `data-pipeline-*`.

---

## A.1 Contract quick-reference

The sixteen cloud-neutral contracts live in `data-pipeline-core-java` (Java interfaces) and `data-pipeline-core` (Python `@runtime_checkable Protocol`s). Every adapter in the framework implements one or more of these; every pipeline author codes against them.

| Contract | Language mirror | One-line purpose |
|---|---|---|
| `Source<T>` | `Source[T]` | Yields records into the pipeline |
| `Sink<U>` | `Sink[U]` | Consumes records out of the pipeline |
| `Transform<V,W>` | `Transform[V,W]` | Maps records V → W |
| `Pipeline` | `Pipeline` | Composition of stages, scheduler-agnostic |
| `PipelineStage` | `PipelineStage` | Named, dependency-aware unit of work |
| `RuntimeContext` | `RuntimeContext` | DI container: config, secrets, adapter registry |
| `BlobStore` | `BlobStore` | Object-storage abstraction (gs://, s3://, abfs://) |
| `Warehouse` | `Warehouse` | Tabular query/load abstraction |
| `JobControlRepository` | `JobControlRepository` | Pipeline-job state-machine |
| `SecretProvider` | `SecretProvider` | Single seam for secret lookup |
| `AuditEventPublisher` | `AuditEventPublisher` | At-least-once audit-record delivery |
| `ObservabilityHook` | `ObservabilityHook` | Unified metrics/logs/tracing seam |
| `LineageEmitter` | `LineageEmitter` | Publishes lineage events at stage boundaries |
| `FinOpsSink` | `FinOpsSink` | Receives cost metrics with attribution tags |
| `GovernancePolicy` | `GovernancePolicy` | Resolves masking, retention, classification |
| `StageMetricsHook` | `StageMetricsHook` | Emits per-stage pipeline metrics (narrow) |

`StageMetrics` is the accompanying value type (not a contract) — an immutable snapshot carrying `rowsProcessed`, `stageLatencyMs`, and `errorCount` labelled by `pipelineId`, `runId`, and `stageName`.

Sources:
- Java interfaces — `data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/` (17 files)
- Python Protocols — `data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/__init__.py:1–35`

---

## A.2 Java reactor modules

The Java side of Culvert is a Maven multi-module build rooted at `data-pipeline-libraries-java/pom.xml`. Thirteen modules in total (`pom.xml:<modules>` block, lines 6–50).

### Core (contracts)

**`data-pipeline-core`** (`data-pipeline-core-java/pom.xml:<description>`)
The cloud-neutral kernel: the sixteen contract interfaces above, plus the supporting records, enums, and value types those interfaces reference (`AuditRecord`, `LineageEvent`, `EntitySchema`, `CostMetrics`, `FinOpsTag`, `StageMetrics`, …). No GCP, AWS, or Azure SDK imports. This is the only module pipeline authors must depend on at compile time.

### GCP adapters

**`data-pipeline-gcp-secrets`** (`data-pipeline-gcp-secrets-java/pom.xml:<description>`)
`SecretManagerProvider` — a `SecretProvider` wrapping `com.google.cloud.secretmanager.v1.SecretManagerServiceClient`. Registered via `java.util.ServiceLoader` so consumers wire it without compile-time coupling to the GCP SDK.

**`data-pipeline-gcp-bigquery`** (`data-pipeline-gcp-bigquery-java/pom.xml:<description>`)
`BigQueryWarehouse` — a `Warehouse` wrapping `com.google.cloud.bigquery.BigQuery`. Also houses the `JobControlRepository` (BigQuery-backed) and `FinOpsSink` (BigQuery-backed) adapters for the same cloud.

**`data-pipeline-gcp-gcs`** (`data-pipeline-gcp-gcs-java/pom.xml:<description>`)
`GcsBlobStore` — a `BlobStore` wrapping `com.google.cloud.storage.Storage`. URIs are `gs://`-prefixed; the adapter parses them; the contract does not.

**`data-pipeline-gcp-pubsub`** (`data-pipeline-gcp-pubsub-java/pom.xml:<description>`)
`PubSubSource` (synchronous pull via `SubscriberStub`) and `PubSubSink` (publish via `Publisher`) — `Source` and `Sink` implementations for Google Cloud Pub/Sub.

**`data-pipeline-gcp-observability`** (`data-pipeline-gcp-observability-java/pom.xml:<description>`)
Two adapters in one module: `CloudTraceObservabilityHook` (spans exported to Cloud Trace via the OpenTelemetry GCP exporter, implements `ObservabilityHook`) and `DataCatalogLineageEmitter` (lineage events written as Data Catalog tags, implements `LineageEmitter`).

**`data-pipeline-gcp-dataflow`** (`data-pipeline-gcp-dataflow-java/pom.xml:<description>`)
`DataflowPipeline` — a `Pipeline` implementation that holds the stage topology and provides `buildBeam()` (translates the stage graph to an Apache Beam `Pipeline`) and `runOnDataflow()` (submits via `DataflowPipelineRunner`).

### Cloud-neutral skeletons (AWS / Azure)

**`data-pipeline-aws-s3`** (`data-pipeline-aws-s3-java/pom.xml:<description>`)
`S3BlobStore` — a `BlobStore` skeleton over `software.amazon.awssdk:s3`. One method implemented (`exists`); the rest throw `UnsupportedOperationException`. Sprint-8 deliverable: proves the cloud-neutral design accommodates AWS without any change to the contracts.

**`data-pipeline-azure-blob`** (`data-pipeline-azure-blob-java/pom.xml:<description>`)
`AzureBlobStore` — a `BlobStore` skeleton over `com.azure:azure-storage-blob`. Same shape as the S3 skeleton. Sprint-8 deliverable for Azure.

### Orchestration

**`data-pipeline-orchestration`** (`data-pipeline-orchestration-java/pom.xml:<description>`)
Cloud-neutral DAG model: `DagSpec` / `TaskSpec` value types and a `Pipeline → DagSpec` translator. No Beam, no Airflow, no GCP imports — depends only on `data-pipeline-core` and `java.util`. Renderer modules (Airflow / Composer) build on top.

### Test support

**`data-pipeline-tester`** (`data-pipeline-tester-java/pom.xml:<description>`)
Mockito-helper fixture builders for the five most-mocked contracts (`SecretProvider`, `Warehouse`, `BlobStore`, `JobControlRepository`, `FinOpsSink`). Eliminates repetitive `when(…).thenReturn(…)` boilerplate in consumer unit tests. Mockito and AssertJ are `compile`-scope deps here — this is a test library.

**`data-pipeline-it-support`** (`data-pipeline-it-support-java/pom.xml:<description>`)
Reusable Testcontainers fixtures for integration tests: BigQuery emulator (`goccy/bigquery-emulator`), GCS fake (`fsouza/fake-gcs-server`), and helpers that build GCP SDK clients pointed at those emulators. Pub/Sub uses Testcontainers' built-in `PubSubEmulatorContainer` directly.

**`data-pipeline-contract-tests`** (`data-pipeline-contract-tests-java/pom.xml:<description>`)
Abstract JUnit contract test classes. Cloud adapter modules extend the relevant class and supply the adapter under test; the abstract tests verify the adapter honours the protocol's documented behaviour. Every GCP adapter passes these before sprint sign-off.

---

## A.3 Python packages

The Python side of Culvert is a set of independently-installable packages under `data-pipeline-libraries/`. All are at `0.1.0`.

### Core (contracts)

**`data-pipeline-core`** (`data-pipeline-libraries/data-pipeline-core/pyproject.toml`)
Cloud-neutral kernel: `@runtime_checkable Protocol`s (the sixteen contracts), supporting dataclasses, and value types. Zero GCP/AWS/Azure SDK dependencies. The Python mirror of `data-pipeline-core-java`.

### GCP adapters

**`data-pipeline-gcp-secrets`** (`data-pipeline-libraries/data-pipeline-gcp-secrets/pyproject.toml`)
`SecretManagerProvider` — `SecretProvider` Protocol backed by `google-cloud-secret-manager`.

**`data-pipeline-gcp-gcs`** (`data-pipeline-libraries/data-pipeline-gcp-gcs/pyproject.toml`)
`GcsBlobStore` — `BlobStore` Protocol backed by `google-cloud-storage`. Counterpart to the Java module of the same name.

**`data-pipeline-gcp-bigquery`** (`data-pipeline-libraries/data-pipeline-gcp-bigquery/pyproject.toml`)
`BigQueryWarehouse` — `Warehouse` Protocol backed by `google-cloud-bigquery`. Also houses BigQuery-backed `JobControlRepository` and `FinOpsSink` adapters.

**`data-pipeline-gcp-pubsub`** (`data-pipeline-libraries/data-pipeline-gcp-pubsub/pyproject.toml`)
`PubSubSource` / `PubSubSink` — `Source` / `Sink` Protocols backed by `google-cloud-pubsub`.

**`data-pipeline-gcp-observability`** (`data-pipeline-libraries/data-pipeline-gcp-observability/pyproject.toml`)
Four adapters: `CloudTraceObservabilityHook` (implements `ObservabilityHook`), `CloudMonitoringStageMetricsHook` (implements `StageMetricsHook`), `DataCatalogLineageEmitter` (implements `LineageEmitter`), and `CulvertMdcPopulator` (log-correlation helper).

### Orchestration

**`data-pipeline-orchestration`** (`data-pipeline-libraries/data-pipeline-orchestration/pyproject.toml`)
Airflow DAG factory, operators, sensors, and callbacks. Cloud-coupled to Composer/Airflow; Airflow is Python-only and is not being ported to Java. Renamed successor of `gcp-pipeline-orchestration`.

### Transform

**`data-pipeline-transform`** (`data-pipeline-libraries/data-pipeline-transform/pyproject.toml`)
dbt macro library: audit columns, PII masking, data-quality checks. dbt-SQL only — no Beam, no Airflow imports. Renamed successor of `gcp-pipeline-transform`.

### Tester

**`data-pipeline-tester`** (`data-pipeline-libraries/data-pipeline-tester/pyproject.toml`)
Base test classes, builders, assertions, BDD steps, mocks, and fixtures for Source/Sink/Transform pipelines and their cloud adapters. pytest and `data-pipeline-core` are compile-time deps. Renamed successor of `gcp-pipeline-tester`.

### Contract tests

**`data-pipeline-contract-tests`** (`data-pipeline-libraries/data-pipeline-contract-tests/pyproject.toml`)
Abstract pytest contract tests that every Culvert adapter implementation must pass. Python counterpart to `data-pipeline-contract-tests-java`.

### Umbrella

**`data-pipeline-framework`** (`data-pipeline-libraries/data-pipeline-framework/pyproject.toml`)
Metapackage: installs the full reference stack (core + tester + transform + orchestration). Bundles deployment templates, Terraform modules, and CI workflow templates as embedded assets. No public API of its own.

---

## A.4 Summary by group

| Group | Java modules | Python packages |
|---|---|---|
| Core (contracts) | `data-pipeline-core` | `data-pipeline-core` |
| GCP adapters | `data-pipeline-gcp-secrets`, `-gcp-bigquery`, `-gcp-gcs`, `-gcp-pubsub`, `-gcp-observability`, `-gcp-dataflow` | `data-pipeline-gcp-secrets`, `-gcp-gcs`, `-gcp-bigquery`, `-gcp-pubsub`, `-gcp-observability` |
| Cloud-neutral skeletons | `data-pipeline-aws-s3`, `-azure-blob` | — |
| Orchestration | `data-pipeline-orchestration` | `data-pipeline-orchestration` |
| Transform (dbt) | — | `data-pipeline-transform` |
| Tester | `data-pipeline-tester` | `data-pipeline-tester` |
| IT support | `data-pipeline-it-support` | — |
| Contract tests | `data-pipeline-contract-tests` | `data-pipeline-contract-tests` |
| Umbrella | — | `data-pipeline-framework` |

**Totals:** 13 Java modules, 11 Python packages.

\newpage
