# Chapter 18 — Cross-Cloud: The Adapter Seam

There is a specific kind of promise that framework authors make and then quietly stop
talking about. The promise is multi-cloud support. The quiet part is the small print:
*planned*, *roadmap*, *coming soon*. I have been on the receiving end of that small
print and I do not enjoy it.

So let me tell you exactly what exists today, why the design makes the rest possible,
and what "the rest" would actually cost to build. No small print.

## What the seam looks like

The `BlobStore` contract in
`data-pipeline-core-java/.../contracts/BlobStore.java`\index{BlobStore} is eight
methods: `get`, `openInput`, `openOutput`, `put`, `list`, `exists`, `delete`, and
`copy`. The contract's Javadoc says what every implementor must provide; it says
nothing about clouds.

```java
public interface BlobStore {
    byte[] get(String uri);
    InputStream openInput(String uri);
    OutputStream openOutput(String uri);
    void put(String uri, byte[] data);
    Iterator<String> list(String prefix);
    boolean exists(String uri);
    void delete(String uri);
    void copy(String src, String dst);
}
```

URIs are opaque strings — `gs://`, `s3://`, `abfs://`. The framework never parses
them. Implementations do. That single design decision is why a new cloud is a new
module rather than a new version of the framework.

The GCP implementation lives in
`data-pipeline-gcp-gcs-java/.../gcp/gcs/GcsBlobStore.java`. It accepts `gs://`
URIs, wraps the Google Cloud Storage client, and is production-tested. If you have
run a GCS pipeline against Culvert, this class is what did the byte-moving.

The AWS implementation lives in
`data-pipeline-aws-s3-java/.../aws/s3/S3BlobStore.java`. It accepts `s3://` URIs
and wraps `S3Client` from the AWS SDK v2. The Azure implementation lives in
`data-pipeline-azure-blob-java/.../azure/blob/AzureBlobStore.java`. It accepts
`abfs://container@account.dfs.core.windows.net/path` URIs and wraps
`BlobServiceClient` from the Azure SDK. Both classes compile, both pass their unit
tests, and both are honest about how incomplete they are.

## One of eight

Let me be specific, because this is the point where framework authors tend to go
vague.

`S3BlobStore`\index{S3BlobStore} (line 38 of `S3BlobStore.java`) implements
`exists()` and nothing else. The other seven methods — `get`, `openInput`,
`openOutput`, `put`, `list`, `delete`, `copy` — throw
`UnsupportedOperationException` with a message pointing at the post-sprint-8
expansion plan on GitHub. The Javadoc says this plainly: *"Sprint-8 skeleton. One
method (`exists()`) is implemented and tested; the others throw
`UnsupportedOperationException`."*\index{sprint-8 skeleton}

`AzureBlobStore`\index{AzureBlobStore} is in the same shape (line 43 of
`AzureBlobStore.java`): `exists()` works, the rest throw.

Both classes implement `BlobStore`. Both classes compile and are wired up in their
respective modules. They prove that the seam takes the plug — they are not production
adapters. A production adapter would need all eight methods, an integration test suite
against real cloud credentials, and a sensible error-mapping layer that turns SDK
exceptions into the framework's own exception taxonomy.

None of that exists yet. I am telling you this now so you do not have to find out
later.

## The full contract set

`BlobStore` is one of sixteen contracts in
`data-pipeline-core-java/.../contracts/`\index{contracts!full set}. The other
fifteen are:

`Source`, `Sink`, `Transform`, `Pipeline`, `PipelineStage`, `RuntimeContext`,
`JobControlRepository`, `AuditEventPublisher`, `FinOpsSink`, `GovernancePolicy`,
`LineageEmitter`, `ObservabilityHook`, `SecretProvider`, `StageMetricsHook`, and
`Warehouse`. (There is also `StageMetrics`, which is a value type carried through the
pipeline, not an adapter contract — the seam is sixteen.)

AWS and Azure each implement one of those sixteen. The GCP family covers the
cloud-specific seams: six adapter modules implementing `BlobStore` (GCS),
`Warehouse` + `AuditEventPublisher` + `FinOpsSink` + `JobControlRepository`
(BigQuery), `Source` + `Sink` for streaming (Pub/Sub), `SecretProvider` (Secret
Manager), `ObservabilityHook` + `StageMetricsHook` + `LineageEmitter` (Cloud
Monitoring, Cloud Trace, Data Catalog), and the Beam execution layer (Dataflow).
The contracts that are cloud-neutral by design — `GovernancePolicy`,
`RuntimeContext`, and the no-op defaults — are implemented in core itself
(`data-pipeline-core-java/.../finops/BudgetGovernancePolicy.java`,
`.../runtime/NoOpDefaults.java`), not in a GCP module.

That is the gap stated plainly: the cloud-specific contracts have a full GCP family;
AWS and Azure have a single skeleton each covering `BlobStore` only.

## The Spring move, explained without nostalgia

I keep reaching for the Spring comparison\index{Spring Framework} and I am going to
keep reaching for it because I have not found a better one.

`spring-data-jpa` shipped first. It was the only persistence module for years. When
`spring-data-mongodb` eventually arrived — written largely by the MongoDB team itself —
the JPA users did not need to learn a single new concept. The contracts that
`spring-data` had defined were honest enough that MongoDB could plug into them
without contorting itself or contorting the users' existing code. The contracts were
designed for *persistence in general*, not for relational databases specifically, even
when only one persistence family existed.

That is the move here. The `BlobStore` interface does not mention buckets or blob
containers or S3's eventual consistency model or Azure's hierarchical namespace. It
mentions bytes and URIs and eight operations that any object store you have ever used
would recognise. The BigQuery-specific optimisations — clustering, partitioning,
slot-aware cost predicates — live in
`data-pipeline-gcp-bigquery-java/.../BigQueryWarehouse.java` and are not in
`Warehouse`\index{Warehouse}. The `Warehouse` contract covers the lowest common
denominator that any serious data warehouse supports, and nothing more.

The non-goal is a lowest-common-denominator warehouse. If you need BigQuery's
materialised views or partition pruning, you call `BigQueryWarehouse` directly and
call its BigQuery-specific extensions directly. The framework does not paper over that
with a `MaterializedViewAware` superinterface. It gives you the generic seam for the
generic work and steps aside for the specific work.

## What a full AWS or Azure family would take

If you wanted to close the gap for AWS, here is what "close the gap" means in
practice.

`BlobStore` needs seven more methods on `S3BlobStore`. That is a week's work —
mostly the streaming variants, the list iterator, and a careful mapping of SDK
exceptions into the framework's error taxonomy. The contract test in
`data-pipeline-contract-tests-java/.../BlobStoreContractTest.java` runs five
behavioural checks (round-trip get, `exists` true/false, idempotent delete, null
rejection) against any implementation; you extend the abstract class, provide a
localstack-backed store, and run it. When those five tests pass, the contract is met.

The remaining fifteen contracts need implementations. Some are relatively contained:
`SecretProvider` against AWS Secrets Manager is a thin wrapper around the AWS SDK,
probably two days. `AuditEventPublisher` pushing records to an SNS topic or an SQS
queue is similarly scoped. `FinOpsSink` writing cost records to an S3 bucket is a
`put` call once `S3BlobStore.put` exists.

Some are non-trivial. `Warehouse` against Redshift needs a connection-pool strategy,
an error taxonomy that maps Redshift's JDBC exceptions, and a `load_from_uri`
implementation that generates a `COPY ... FROM ... IAM_ROLE` statement — a surface
that has subtle differences from BigQuery's `LOAD DATA` semantics, and the contract
test harness will expose them. `JobControlRepository` against DynamoDB needs a schema
and a set of query patterns that map the pipeline job ledger's read/write profile
onto DynamoDB's key-value model rather than BigQuery's SQL model. That is
architectural, not mechanical.

The observability module — `CloudMonitoringMetricsHook` and
`CloudTraceObservabilityHook` in
`data-pipeline-gcp-observability-java/.../gcp/observability/` — would become a
CloudWatch-backed pair. The effort is comparable; the mapping is one-for-one.
`DataCatalogLineageEmitter` would become a Glue Data Catalog or OpenLineage-direct
emitter. Slightly less one-for-one, but the `LineageEmitter` contract is
OpenLineage-shaped already, so the GCP coupling in that module is limited to Data
Catalog's client library.

The v1 manuscript's estimate for adding a new cloud service is two to four weeks per
service — not a rewrite, a per-service build. The GCP experience supports that number
for the storage and warehouse tier. What it does not surface is the cost of the
heavier pieces: an execution adapter (Beam on EMR or AWS Glue as the Dataflow
equivalent) and a streaming Source/Sink (Kinesis or SQS as the Pub/Sub equivalent)
are the most complex contracts in the GCP family. Those are not a week each. A
complete AWS family — all sixteen contracts, integration tests running against
localstack and real AWS in CI, and an execution module that can run Beam on EMR —
is realistically a three- to six-month build for one experienced engineer. The
contracts make it additive work rather than reconstructive work. That distinction
matters enormously; it still takes time.

Azure would be similar in scope. The most complicated piece would be
`AzureBlobStore`'s URI convention — the ABFS scheme
(`abfs://container@account.dfs.core.windows.net/path`) that `AzureBlobStore.java`
already parses — and mapping Azure Data Lake Storage Gen2's namespace semantics onto
the `list` and `copy` methods. Synapse as a `Warehouse` implementation has subtler
divergences from BigQuery's SQL semantics than Redshift does, so the
`WarehouseContractTest` may expose a protocol revision. Not impossible, just
non-trivial.

## What "enabled, not promised" means in practice

AWS and Azure are *enabled by the design*, not promised by a roadmap date. Those are
different things.

"Enabled" means the contracts are honest, the naming convention reserves the module
slots, the contract test harness will validate any adapter against the same
behavioural specification the GCP adapters pass today, and the `AutoConfig` registry
discovers installed adapters at boot via Java's `ServiceLoader` —
`data-pipeline-core-java/.../autoconfig/AutoConfig.java` loads every
`META-INF/services/com.enrichmeai.culvert.contracts.*` entry it finds on the
classpath. A team that wants an AWS `BlobStore` registers `S3BlobStore` there and
the runtime picks it up without any core changes. A team that wants `culvert-aws-s3`
can build it without changing a line of core.

"Promised" would mean I have committed to a ship date and a team is working on it.
That is not true. Culvert is built and held at version 0.1.0. Nothing is published to
Maven Central. The AWS and Azure skeletons exist in the repository to validate the
seam, not to promise a release.

I have watched other vendors make the rhetorical drift from "the contracts allow
multi-cloud" to "we are a multi-cloud framework". The gap between those two sentences
is the gap that burns customers. I am not going to smudge over it. If your procurement
team asks whether Culvert runs on AWS today, the answer is no.

## The contract tests as the handshake

The contract test module —
`data-pipeline-contract-tests-java/.../contracttests/BlobStoreContractTest.java` — is
the mechanism that makes the seam real rather than rhetorical. It is abstract. It
declares three abstract methods: `store()`, `knownUri()`, and `missingUri()`. Any
`BlobStore` implementor extends it, provides a real store backed by their cloud or a
localstack equivalent, and gets five behavioural tests for free.

When a future AWS implementor extends `BlobStoreContractTest` with a localstack-backed
`S3BlobStore` and runs those tests, they are not running hand-rolled AWS tests — they
are running the same specification the GCP `GcsBlobStore` passes in CI today. If the
abstraction has a leak — some assumption baked into the test that only GCS satisfies
and S3 does not — the test will fail and the abstraction will need fixing. That is
correct and good. I would rather find the abstraction leak in a failing test than in a
customer's production pipeline.

The `WarehouseContractTest` and `SecretProviderContractTest` in the same module follow
the same pattern. Extend, provide a backend, run the tests. The contract either holds
or it tells you where it needs to be revised.

## The honest summary

Two clouds beyond GCP have a single skeleton class each. Both skeletons implement
`BlobStore`. Both implement one of eight methods. Neither is production-ready. Both
prove the seam compiles against a non-GCP cloud, which is exactly what a sprint-8
proof-of-concept is supposed to prove.

Sixteen contracts exist in core. The cloud-specific ones — `BlobStore`, `Warehouse`,
`JobControlRepository`, `AuditEventPublisher`, `FinOpsSink`, `LineageEmitter`,
`ObservabilityHook`, `StageMetricsHook`, `SecretProvider`, `Source`, `Sink` — have
GCP adapters. The cloud-neutral ones (`GovernancePolicy`, `RuntimeContext`) have
core-module implementations that work without any cloud at all. AWS and Azure cover
`BlobStore` only, and at one of eight methods. The GCP family spans six modules and
is the only one that runs production pipelines.

That is the current state. The design makes the rest a per-service build rather than
a rewrite. The contract tests make the per-service build verifiable against the same
specification. The naming convention reserves the module slots. The rest waits for the
team or the community that needs it badly enough to build it.

That is the Spring move. Small honest core. One reference implementation. Wait for the
people who actually run the other clouds to build the adapters, because they will
build them right and I will not.

The seam is real. The full family is not yet. Both of those sentences are true and
neither of them cancels the other.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item AWS and Azure each have \textbf{one skeleton class} today:
        \texttt{S3BlobStore} and \texttt{AzureBlobStore}
        (\texttt{data-pipeline-aws-s3-java} and \texttt{data-pipeline-azure-blob-java}).
        Each implements \texttt{BlobStore.exists()} and throws
        \texttt{UnsupportedOperationException} for the remaining seven methods.
        They are proof that the seam compiles across clouds, not production adapters.
  \item There are \textbf{sixteen contracts} in
        \texttt{data-pipeline-core-java/.../contracts/}. The cloud-specific seams
        (\texttt{BlobStore}, \texttt{Warehouse}, \texttt{JobControlRepository}, etc.)
        have GCP adapters across six modules. The cloud-neutral contracts
        (\texttt{GovernancePolicy}, \texttt{RuntimeContext}) have core implementations
        that work on any cloud. AWS and Azure implement \texttt{BlobStore} only —
        and at one of eight methods.
  \item The GCP adapter family — \texttt{data-pipeline-gcp-gcs-java},
        \texttt{-bigquery-java}, \texttt{-pubsub-java}, \texttt{-secrets-java},
        \texttt{-observability-java}, \texttt{-dataflow-java} — is the only
        production-tested implementation family in the framework.
  \item A complete AWS family (all sixteen contracts, localstack and real-AWS CI,
        an execution module for Beam on EMR) is a \textbf{three- to six-month build},
        not a rewrite. The contracts make it per-service additive work. The contract
        test harness (\texttt{BlobStoreContractTest}, \texttt{WarehouseContractTest})
        validates any adapter against the same behavioural specification GCP adapters
        pass today.
  \item \textbf{Enabled, not promised.} \texttt{AutoConfig} discovers installed
        adapters at boot via Java \texttt{ServiceLoader} —
        register an impl under \texttt{META-INF/services/} and the runtime picks it
        up. Nothing in core prevents a non-GCP implementation. No Maven Central
        release exists. Version 0.1.0 is built and held, not published.
  \item The Spring precedent holds: ship the implementation you have, keep the core
        honest, wait for the people who run the other clouds to build the adapters.
        They will build them correctly. Tourist adapters are worse than no adapters.
\end{itemize}
\end{takeaways}

\newpage
