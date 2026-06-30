# Chapter 4 — Contracts as the Portability Boundary

## Why I renamed a perfectly working framework

The framework has a name now: **Culvert**\index{Culvert}. A culvert is the engineered pipe that carries water from one side of a road to the other — controlled flow through a designed channel, holding back what should be held back, releasing what should be released, at a known rate. The metaphor is exact. A data pipeline is a culvert: an engineered channel carrying records from a source to a destination, with controlled gates — governance, masking, quality checks — along the way. The name is short, distinctive, and as of this writing unclaimed on PyPI under the `culvert` namespace, which is the property that matters most when you are planning a coordinated open-source release. The book you are reading was written about the *reference implementation* — the GCP-specific deployment at `github.com/enrichmeai/culvert`\index{Culvert!reference implementation} that the earlier chapters document. **Culvert is the framework that reference grew into.**

The Python distributions are currently named `data-pipeline-core`, `data-pipeline-gcp-bigquery`, `data-pipeline-gcp-gcs`, and `data-pipeline-gcp-pubsub`. They will, in the coordinated release, become `culvert-core`\index{culvert-core} and the matching `culvert-gcp-*` family. The namespace `culvert` on PyPI is reserved; the Java groupId `com.enrichmeai.culvert` is in use in the reactor pom at `0.1.0`\index{Culvert!java-0.1.0} right now. I want to explain what happened between "GCP pipeline framework" and "Culvert 0.1.0", because the path is the point.

## The audit

I want to explain the rename, because at first glance this looks like exactly the kind of cosmetic renaming that gets engineers fired in their second year. The first time someone proposed I rename a working framework I rolled my eyes hard enough to dislodge a contact lens. I had a working system. The packages were on PyPI. Pipelines were running in production against it. What sort of muppet rewrites the package names of a system that already works?

The honest answer is that I sat down and did a proper audit of the codebase against the question: *how much of this is actually GCP code?*\index{cloud-neutral contracts!audit}

I expected the answer to be "almost all of it." The framework lived in a directory called `gcp-pipeline-libraries`. Every Python module started with `gcp_pipeline_`. Every docstring opened with "GCP Pipeline Framework —". When I went through the files one at a time and counted imports, the answer was about fifty-five per cent. The other forty-five-or-so per cent was already cloud-neutral, in fact if not in name.

The data-quality dimensions, the error taxonomy, the audit records, the lineage tracker, the structured logger, the run-ID generator, the alert manager, the OTEL bridge, the schema dataclasses, the HDR/TRL parser, the validators — none of these imported `google.cloud` anything. They lived in a directory called `gcp_pipeline_core` and they were not GCP code. They were generic Python with a GCP prefix glued to the front.

That is in-name-only coupling, and once you notice it you cannot un-notice it. The rename is the smallest move that lets the framework grow into the shape it already half-is. It is not a rewrite. It is closer to admitting what already exists.

## The Spring precedent, told properly

The cultural reference point I keep returning to is Spring Framework\index{Spring Framework}. The relevant fact about Spring is *not* that it ended up multi-database, multi-runtime, and multi-cloud. The relevant fact is the order in which it got there.

`spring-data-jpa` shipped first. It was the only persistence module for years. It targeted relational databases through a perfectly good Java standard, and people built real applications against it without ever having to wonder whether Spring would one day support a document store. When `spring-data-mongodb` finally appeared, it was written largely by the MongoDB team itself, and the JPA users did not have to learn a single new concept; the contracts that `spring-data` had defined — repositories, queries, conversion services — were honest enough that MongoDB could plug into them without contorting itself or contorting the JPA users' code.

What makes that story work is that `spring-core` was never contaminated with relational assumptions. It hosted *any* persistence model, even when only one existed in the wild. The team made the abstractions cloud-neutral — to drag the metaphor forward by twenty years — and then shipped the implementation they actually needed. The other implementations either followed from a community that wanted them, or were built deliberately and much later. They were not promised; they were enabled.

That is the move Culvert makes. The abstractions are cloud-neutral. The GCP implementation is the only one worth shipping right now, because it is the only cloud this framework has been run against in anger. AWS and Azure skeleton adapters exist in the reactor (`data-pipeline-aws-s3-java/`, `data-pipeline-azure-blob-java/`), proving the seam compiles — they are not production-ready and they are not pretending to be. If someone three years from now wants `culvert-aws-redshift` enough to write it, the contracts make that a 2–4 week build per service rather than a rewrite. If nobody ever writes it, the framework is no worse for the rename — the GCP code is the same code, with honest names.\index{Culvert!AWS skeleton}\index{Culvert!Azure skeleton}

## What was already cloud-neutral

The audit's most useful finding was the inventory of code that contains zero references to `google`, `bigquery`, `gcs`, `dataflow`, or `pubsub`. The list is longer than I expected.

The entire data-quality subpackage — `checker.py`, `dimensions.py`, `scoring.py`, `anomaly.py`, `reporting.py`. These operate on `List[Dict[str, Any]]` and have always done so. The error taxonomy — every exception class, the classifier, the retry policy, the in-memory storage. The audit primitives — pure dataclasses and dict assembly. The whole of the data-deletion logic except for one GCS subclass — the malformation detector, the quarantine manager, the deletion workflow, the recovery bookkeeping. The HDR/TRL parser, modulo one `gs://`-sniffing block that disappears once you inject a `BlobStore`. The monitoring primitives: `MetricsCollector`, `HealthChecker`, `AlertManager`, the OTEL tracing and context modules. The structured logger. The run-ID generator. The schema dataclasses. The finops cost-metrics model and the label dataclass.

None of this code was wrong. The naming was wrong. These modules had been generic the whole time; calling them GCP because they lived under a `gcp_pipeline_*` namespace was a category error I committed when I first laid the repo out, and the audit caught me at it.

What the rename does for this code is honest labelling. `data-pipeline-core` — the module that will become `culvert-core` in the coordinated release — is allowed to import `typing_extensions`, `pydantic`, and `opentelemetry-api`. It is not allowed to import `google.cloud.anything`.

## What is genuinely GCP

The other half of the audit is the inventory of code that is GCP-coupled by design. I want to name these by name, because I am not going to pretend they are not what they are.

The BigQuery client wrapper. The GCS client wrapper. The Pub/Sub client wrapper. The BigQuery-backed job-control repository — every method builds parameterised BigQuery SQL and ships it through `bigquery.Client.query()`; the class has dozens of BigQuery references across hundreds of lines, and that is correct, because it is doing BigQuery work\index{job control repository}. The cost tracker with its `BQ_COST_PER_TIB` constant. The Pub/Sub audit publisher. The Cloud Monitoring alert backend. The GCS error storage and recovery manager. The GCS file lifecycle and archiver. The Dataplex governance hooks. The entire Beam-on-Dataflow execution package. The entire Composer DAG factory built around `airflow.providers.google.cloud.*`. The dbt macros that emit BigQuery SQL.

All of this stays GCP. All of it gets named honestly: `data-pipeline-gcp-bigquery`, `data-pipeline-gcp-dataflow`, `data-pipeline-gcp-composer`, `data-pipeline-gcp-gcs`, `data-pipeline-gcp-pubsub`, `data-pipeline-gcp-dataplex`, `data-pipeline-gcp-observability`, `data-pipeline-gcp-secrets`, `data-pipeline-gcp-dbt`. These are first-class modules in the framework, not afterthoughts. They are what makes the framework useful to a team running on GCP today.

The point is that they are no longer the *whole* framework. They are the GCP family within it.

## Sixteen contracts

The audit sharpened into a concrete question: what is the minimum set of abstractions that a cloud-neutral data pipeline framework needs to express? I landed on sixteen interfaces, mirrored across Java and Python, plus the `StageMetrics` value type.

The sixteen, in the Java package `com.enrichmeai.culvert.contracts` (`data-pipeline-libraries-java/data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/`\index{Culvert!contract directory}):

```text
Source             — anything that yields records (lazy iterator)
Sink               — anything that consumes records
Transform          — anything that maps records from one type to another
Pipeline           — a named, validated graph of stages
PipelineStage      — one node in that graph: name, inputs, outputs, execute()
RuntimeContext     — the framework's DI container (run_id, config, secrets, …)
JobControlRepository — the job ledger (create, update, mark failed, retry, …)
BlobStore          — object storage (get, put, list, exists, delete, copy)
Warehouse          — tabular query/load (query, execute, load_from_uri, merge)
AuditEventPublisher — emit audit records at-least-once
GovernancePolicy   — resolve masking/retention/classification per field/table
LineageEmitter     — publish OpenLineage-shaped lineage events
ObservabilityHook  — the single observability seam (counter, gauge, span, log)
FinOpsSink         — receive cost metrics from cloud-specific cost trackers
SecretProvider     — single seam for secret lookup
StageMetricsHook   — typed per-stage pipeline metrics (rows, latency, errors)
```

Plus the `StageMetrics` record — immutable snapshot of the three Culvert metric series (`culvert/rows_processed`, `culvert/stage_latency_ms`, `culvert/error_count`) with their fixed label schema of `pipeline_id`, `run_id`, and `stage_name`. `StageMetrics` is not a contract in the Protocol/interface sense; it is the value type that `StageMetricsHook.record_stage_metrics()` carries. I count it separately because it is semantically different from the sixteen behavioural interfaces.

The same set exists in Python, in `data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/`\index{Culvert!python contracts directory}. Python packages them differently — `source.py` holds `Source`, `Sink`, and `Transform` together; `stage_metrics.py` holds both the frozen dataclass and the hook Protocol — but the behavioural surface is identical.

```python
# data_pipeline_core/contracts/source.py (excerpt)
@runtime_checkable
class Source(Protocol[T_co]):
    """Anything that yields records into the pipeline."""
    def read(self, context: "RuntimeContext") -> Iterator[T_co]: ...

@runtime_checkable
class Sink(Protocol[U_contra]):
    """Anything that consumes records."""
    def write(self, records: Iterator[U_contra], context: "RuntimeContext") -> None: ...

@runtime_checkable
class Transform(Protocol[V, W]):
    """Anything that maps records."""
    def apply(self, records: Iterator[V], context: "RuntimeContext") -> Iterator[W]: ...
```

```java
// contracts/Source.java (excerpt)
@FunctionalInterface
public interface Source<T> {
    /** Stream records into the pipeline. Must be lazy — do not materialise. */
    Iterator<T> read(RuntimeContext context);
}
```

The Java interface and the Python Protocol describe the same contract. An implementation that satisfies one will satisfy the other in any polyglot pipeline that crosses the language boundary.

## The seam in practice

`BlobStore` is the contract that illustrates the seam most clearly.\index{BlobStore}

```python
# data_pipeline_core/contracts/blob_store.py
class BlobStore(Protocol):
    """Object storage abstraction. URIs are opaque strings."""
    def get(self, uri: str) -> bytes: ...
    def open(self, uri: str, mode: str = "rb") -> BinaryIO: ...
    def put(self, uri: str, data: bytes) -> None: ...
    def list(self, prefix: str) -> Iterator[str]: ...
    def exists(self, uri: str) -> bool: ...
    def delete(self, uri: str) -> None: ...
    def copy(self, src: str, dst: str) -> None: ...
```

GCP implementation: `data_pipeline_gcp_gcs.GCSBlobStore` — a thin wrapper around `google.cloud.storage.Client`. Hypothetical AWS implementation: `data_pipeline_aws_s3.S3BlobStore`. Hypothetical Azure implementation: `data_pipeline_azure_adls.ADLSBlobStore`. The Java reactor has the same contract at `com.enrichmeai.culvert.contracts.BlobStore`\index{BlobStore!Java interface}, with the same seven methods.

The HDR/TRL parser, which used to sniff `gs://` from the URI and talk directly to GCS, now takes a `BlobStore` and calls `blob_store.open(uri)`. The parser does not care what scheme the URI has. That one dependency-inversion eliminates the parser's GCP coupling entirely.

`JobControlRepository` is the contract that illustrates the depth of the cloud-specific work.\index{JobControlRepository} The GCP implementation, `BigQueryJobControlRepository`, has 49 BigQuery references across 511 lines — it builds parameterised SQL, manages partitioned tables, handles retry bookkeeping, and keeps the job ledger consistent under concurrent Dataflow workers. That is the right amount of BigQuery for a BigQuery-backed job ledger. A DynamoDB implementation would do the equivalent amount of DynamoDB work. The contract does not know and does not care.

## Holding the boundary

The boundary is enforced. Not by a shell-script grep in CI — but by compiled assertions baked into the Java unit-test suite itself. In `BudgetGovernancePolicyTest` and `PiiMaskingGovernancePolicyTest`, AssertJ assertions walk the source of every class in `data-pipeline-core-java` and fail the build if any import line contains `com.google.cloud` or `org.apache.beam`\index{cloud-neutral contracts!test enforcement}:

```java
// BudgetGovernancePolicyTest.java (line ~278)
assertThat(importLine)
    .as("BudgetGovernancePolicy must not import com.google.cloud.*")
    .doesNotContain("com.google.cloud");
```

The Python side is simpler: a grep against the contracts package returns zero matches on `google.cloud`. I have checked this; the number is zero
(`data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/` has no GCP imports).

This is the same trick Spring projects have used for two decades to keep their kernels honest — make the boundary machine-checkable, not a convention people hope everyone remembers.

## What the contracts do not include

`RuntimeContext` is the framework's `ApplicationContext`\index{RuntimeContext} — it carries `run_id`, `environment`, `config`, `secrets`, `observability`, `lineage`, `finops`, and `governance`, and it provides a `get(protocol)` / `register(protocol, impl)` pair that amounts to a one-method dependency-injection container. It is constructed once per pipeline execution by the bootstrap routine, populated by each cloud module's `auto_config()` callable, and threaded through every component invocation. A pipeline author never constructs a `BigQueryWarehouse` directly; they call `context.get(Warehouse)` and the auto-config machinery has already wired the right implementation in.

The contracts do not include anything about *scheduling*. A `Pipeline` knows its name, its stages, and how to validate its own graph. It does not know whether it runs on Composer, Step Functions, or a local in-process runner — that is the orchestration module's job, handled in the GCP case by `data-pipeline-gcp-composer` compiling the cloud-neutral DAG model into Airflow operators. Chapter 11 covers that in detail.

The contracts also do not include anything about *format*. A `Source[bytes]` might be yielding CSV, fixed-width, Avro, or Parquet. The parser is a separate concern — typically a `Transform[bytes, Mapping[str, Any]]` wrapping the HDR/TRL parser or an Avro decoder. Format-awareness belongs at the stage boundary, not the storage boundary.

## What is shipped and what is not

The Java reactor is at `0.1.0` (`data-pipeline-libraries-java/pom.xml`). The sixteen contracts compile, the GCP adapter modules compile, the integration test tier passes against Testcontainers emulators. This is built and frozen.\index{Culvert!java-0.1.0}

What is not shipped: the coordinated Maven Central + PyPI release. Publishing the Java artifact as `com.enrichmeai.culvert:data-pipeline-core-java:0.1.0` to Maven Central, and publishing the Python adapter modules to PyPI under the `culvert-*` names, requires the coordinated release process described in Chapter 17. The `culvert` PyPI name is reserved; the `culvert-*` names are reserved. The current PyPI distributions are still `data-pipeline-core`, `data-pipeline-gcp-bigquery`, `data-pipeline-gcp-gcs`, and `data-pipeline-gcp-pubsub`. That is the honest status, and it matters: nothing in the code changes when the coordinated release lands. The contracts are the contracts. The adapters are the adapters. The release is an act of publication, not an act of engineering.

\begin{takeaways}
**Chapter 4 — key points**

- Culvert was GCP-first by necessity and cloud-neutral by design: the audit
  found roughly half the codebase had zero `google.cloud` dependencies despite
  living under a `gcp_pipeline_*` namespace.
- The Spring precedent is the instructive one: `spring-core` was never
  contaminated with relational assumptions even when JPA was the only
  implementation. Culvert's core carries no GCP imports even though GCP is the
  only full implementation today.
- Sixteen behavioural interfaces (`Source`, `Sink`, `Transform`, `Pipeline`,
  `PipelineStage`, `RuntimeContext`, `JobControlRepository`, `BlobStore`,
  `Warehouse`, `AuditEventPublisher`, `GovernancePolicy`, `LineageEmitter`,
  `ObservabilityHook`, `FinOpsSink`, `SecretProvider`, `StageMetricsHook`)
  plus the `StageMetrics` value record define the entire framework-to-cloud
  seam. They live in the contracts packages of both the Java reactor
  (`com.enrichmeai.culvert.contracts`) and the Python core
  (`data_pipeline_core.contracts`).
- The boundary is machine-enforced: AssertJ assertions in the Java unit suite
  fail the build on any `com.google.cloud.*` import in core; the Python
  contracts package is clean by grep.
- The Java reactor is frozen at `0.1.0`. The coordinated Maven Central + PyPI
  `culvert` release is ahead; current Python distributions remain
  `data-pipeline-*` until that release lands.
\end{takeaways}

\newpage
