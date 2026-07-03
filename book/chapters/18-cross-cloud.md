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
and wraps `S3Client` from the AWS SDK v2. As of Sprint 21 (epic #144) it implements
all eight `BlobStore` methods, not a subset — more on that below. The Azure
implementation lives in
`data-pipeline-azure-blob-java/.../azure/blob/AzureBlobStore.java`. It accepts
`abfs://container@account.dfs.core.windows.net/path` URIs and wraps
`BlobServiceClient` from the Azure SDK. It is still a Sprint-8 skeleton: `exists()`
works, the other seven methods throw `UnsupportedOperationException`. Both classes
compile and pass their unit tests; only one of them is honestly describable as
"incomplete" any more.

## AWS: from one method to a real family

Let me be specific, because this is the point where framework authors tend to go
vague.

Through Sprint 8, `S3BlobStore`\index{S3BlobStore} implemented `exists()` and
nothing else — the other seven methods threw `UnsupportedOperationException`. That
was true when the first edition of this chapter was written. It is not true any
more. Sprint 21 (epic #144) closed that gap: `S3BlobStore` now implements `get`,
`openInput`, `openOutput`, `put`, `list`, `delete`, and `copy` alongside the
original `exists()` — all eight `BlobStore` methods, unit-tested and exercised
against a real S3 API surface via a LocalStack integration test
(`S3BlobStoreLocalStackIT`). The one deliberate simplification worth knowing about:
`openOutput()` buffers the write in memory and issues a single `PutObject` call on
close, rather than driving S3's multipart-upload protocol — the right tradeoff for
config, manifests, and small extracts, and documented in the class Javadoc as a
follow-up seam if multi-gigabyte streaming writes ever show up.

`BlobStore` was not the only contract that moved. The same sprint added three more
real AWS adapters:

- `AwsSecretsManagerProvider` (`data-pipeline-aws-secrets-java`) implements
  `SecretProvider` against AWS Secrets Manager, mapping the contract's `"latest"`
  version onto AWS's `AWSCURRENT` version stage — AWS has no `"latest"` alias the
  way GCP Secret Manager does, so the adapter translates the concept rather than
  assuming it.
- `SqsSource` and `SqsSink` (`data-pipeline-aws-sqs-java`) implement `Source` and
  `Sink` against an SQS queue, mirroring `PubSubSource`/`PubSubSink`'s shape but
  documenting where SQS's semantics genuinely differ — eager-delete-on-read makes
  `SqsSource` at-most-once by design, and `SqsSink` batches at SQS's own
  ten-message `sendMessageBatch` ceiling, surfacing partial-batch failures as a
  `SqsPublishException` rather than swallowing them.
- `DynamoDbJobControlRepository` (`data-pipeline-aws-dynamodb-java`) implements
  `JobControlRepository` against DynamoDB, and it is worth dwelling on because it
  is not just a port — it is a genuine improvement over what BigQuery offers. More
  on that below.

`AzureBlobStore` is unchanged: `exists()` works, the rest throw. It is still exactly
the Sprint-8 proof-of-concept the first edition of this chapter described: a
skeleton that proves the seam takes the plug, not a production adapter.

## The DynamoDB control plane: better than BigQuery, not just different

`BigQueryJobControlRepository` implements every status transition — `markFailed`,
`updateStatus`, and friends — as a plain `UPDATE ... WHERE run_id = @run_id`
statement. BigQuery has no compare-and-swap primitive. Two concurrent callers
racing to, say, mark the same run both failed and succeeded can both "succeed" —
the last writer wins silently, and neither caller finds out it lost the race.

DynamoDB's `PutItem` and `UpdateItem` APIs accept a `ConditionExpression` that is
evaluated atomically against the server-side item state as part of the same
request: the write either commits or is rejected with
`ConditionalCheckFailedException`, with no window for a concurrent writer to
interleave. `DynamoDbJobControlRepository` uses exactly that — conditional writes
as the concurrency primitive for status transitions. That is a genuine
transactional control plane that the BigQuery implementation structurally cannot
offer without adding a lock table or an optimistic-concurrency column of its own.
It is the reason DynamoDB is in the AWS family at all, not just a box-ticking
"cover `JobControlRepository` too."

I want to be precise about what this does and does not mean. It does not mean AWS's
`JobControlRepository` is "ahead" of GCP's in the way a feature-completeness
scoreboard would suggest — the BigQuery adapter has years of production traffic
behind it, and DynamoDB's is new. It means the *contract* exposed a real
architectural difference between the two backends, and the difference resolved in
DynamoDB's favour for this one property. That is exactly what a contract-driven
design is supposed to surface.

## Where AWS still isn't done

Two AWS modules are registered but empty: `data-pipeline-aws-athena-java` and
`data-pipeline-aws-cloudwatch-java`. Both exist in the reactor's `pom.xml` as
pre-registered coordination seams — the same pattern used for every wave of
GCP modules in this book — and both are in progress in parallel with the rest of
Sprint 21, not yet landed as this chapter goes to print.

`Warehouse` against Athena is the harder of the two, for a boring infrastructure
reason: unlike S3, SQS, Secrets Manager, and DynamoDB, there is no mature
community LocalStack implementation of Athena to integration-test against. The
adapter is being built and mock-tested against the AWS SDK client directly; real-AWS
validation is still pending. That is a meaningfully different confidence level than
`S3BlobStoreLocalStackIT` or `SqsLocalStackIT` running against a real (if emulated)
service, and I am not going to blur that distinction in the text.

CloudWatch hooks — the `ObservabilityHook`/`StageMetricsHook` analog of
`CloudMonitoringMetricsHook`/`CloudTraceObservabilityHook` — are the more
mechanical of the two remaining pieces; the mapping is closer to one-for-one with
the GCP observability module.

Also explicitly out of scope for Sprint 21, and worth stating plainly rather than
letting it be assumed: an AWS execution layer. Apache Beam is runner-portable by
design — the same `Pipeline`/`PipelineStage` graph that targets Dataflow can in
principle target a different Beam runner — so there is no `data-pipeline-aws-emr`
or `data-pipeline-aws-flink` module and no immediate plan for one. An
EMR-or-Flink-as-the-Dataflow-equivalent runner story is a future consideration, not
a current gap in "the AWS family," because it was never this sprint's job. And
Python parity for any of this — an AWS family in the Python library set — is
explicitly deferred past the 0.1.0 release; see
`docs/framework-evolution/13-python-parity-release.md`.

## The full contract set

`BlobStore` is one of sixteen contracts in
`data-pipeline-core-java/.../contracts/`\index{contracts!full set}. The other
fifteen are:

`Source`, `Sink`, `Transform`, `Pipeline`, `PipelineStage`, `RuntimeContext`,
`JobControlRepository`, `AuditEventPublisher`, `FinOpsSink`, `GovernancePolicy`,
`LineageEmitter`, `ObservabilityHook`, `SecretProvider`, `StageMetricsHook`, and
`Warehouse`. (There is also `StageMetrics`, which is a value type carried through the
pipeline, not an adapter contract — the seam is sixteen.)

AWS now implements five of those sixteen: `BlobStore` (S3), `SecretProvider`
(Secrets Manager), `Source` and `Sink` (SQS), and `JobControlRepository`
(DynamoDB) — with `Warehouse` (Athena) and the observability pair (CloudWatch)
in progress, which would bring the count to eight. Azure implements one:
`BlobStore`, and at one of its eight methods. The GCP family covers the
cloud-specific seams in full: six adapter modules implementing `BlobStore` (GCS),
`Warehouse` + `AuditEventPublisher` + `FinOpsSink` + `JobControlRepository`
(BigQuery), `Source` + `Sink` for streaming (Pub/Sub), `SecretProvider` (Secret
Manager), `ObservabilityHook` + `StageMetricsHook` + `LineageEmitter` (Cloud
Monitoring, Cloud Trace, Data Catalog), and the Beam execution layer (Dataflow).
The contracts that are cloud-neutral by design — `GovernancePolicy`,
`RuntimeContext`, and the no-op defaults — are implemented in core itself
(`data-pipeline-core-java/.../finops/BudgetGovernancePolicy.java`,
`.../runtime/NoOpDefaults.java`), not in a cloud-specific module.

That is the gap stated plainly: the cloud-specific contracts have a full GCP
family; AWS has a real, growing family that is not yet complete (five of sixteen,
soon eight, still short of an execution layer and of `AuditEventPublisher`,
`FinOpsSink`, and `LineageEmitter`); Azure still has a single skeleton covering
`BlobStore` only.

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
denominator that any serious data warehouse supports, and nothing more — and that
same discipline is what the in-progress `AthenaWarehouse` adapter is being held to.

The non-goal is a lowest-common-denominator warehouse. If you need BigQuery's
materialised views or partition pruning, you call `BigQueryWarehouse` directly and
call its BigQuery-specific extensions directly. The framework does not paper over that
with a `MaterializedViewAware` superinterface. It gives you the generic seam for the
generic work and steps aside for the specific work.

## What closing the rest of the AWS gap took — and what closing Azure's would take

Sprint 21 is a useful data point against the estimate the first edition of this
chapter made, so let me update the estimate with the actual experience rather than
just restating the old guess.

The old estimate was: seven more `BlobStore` methods on `S3BlobStore`, "a week's
work — mostly the streaming variants, the list iterator, and a careful mapping of
SDK exceptions into the framework's error taxonomy." That is what shipped. The
contract test in
`data-pipeline-contract-tests-java/.../BlobStoreContractTest.java` — five
behavioural checks (round-trip get, `exists` true/false, idempotent delete, null
rejection) — is what `S3BlobStore` now passes via a LocalStack-backed
implementation, the same specification the GCP `GcsBlobStore` passes in CI.

`SecretProvider` against AWS Secrets Manager was estimated at "probably two days,
a thin wrapper around the AWS SDK." That is also roughly what it took, with one
wrinkle the estimate did not anticipate: AWS has no `"latest"` version alias, so
the adapter had to design a mapping (`"latest"` → the `AWSCURRENT` version stage)
rather than simply forward a string. Contract-driven design earns its keep exactly
in moments like this — the contract says `"latest"` must mean something, and the
adapter has to figure out what that means on a backend that models versioning
differently.

`JobControlRepository` against DynamoDB was flagged as "architectural, not
mechanical," needing a schema and query patterns mapping the job ledger onto
DynamoDB's key-value model rather than BigQuery's SQL model. That held up, and
then some — the conditional-write control plane described above is the
architectural payoff the estimate anticipated, delivered as a genuine improvement
rather than a like-for-like port.

What is left for a *complete* AWS family: `Warehouse` (Athena — in progress, mock-tested,
real-AWS validation pending), the observability pair (CloudWatch — in progress),
`AuditEventPublisher` and `FinOpsSink` (not yet started; likely SNS/SQS and an
S3 `put` respectively, similarly scoped to what shipped this sprint), and an
execution adapter — Beam on EMR or an equivalent runner — which remains the
heaviest piece and is explicitly out of scope for this block. A complete AWS
family including that execution layer and real-AWS CI is still a multi-month
build; the difference from the first edition of this chapter is that "a complete
AWS family" no longer means starting from `exists()` — it means finishing three or
four more contracts plus the execution layer, with the storage, secrets, streaming,
and job-control tier already real and tested.

Azure has had no equivalent investment this sprint and the estimate for it is
unchanged: the most complicated piece would be `AzureBlobStore`'s URI convention
— the ABFS scheme (`abfs://container@account.dfs.core.windows.net/path`) that
`AzureBlobStore.java` already parses — and mapping Azure Data Lake Storage Gen2's
namespace semantics onto the `list` and `copy` methods. Synapse as a `Warehouse`
implementation has subtler divergences from BigQuery's SQL semantics than Athena
or Redshift do, so the `WarehouseContractTest` may expose a protocol revision.
Not impossible, just non-trivial, and nobody has started.

## What "enabled, not promised" means in practice

AWS's family and Azure's skeleton are both *enabled by the design*; only AWS has
also been *built*, this sprint, by this team. Those are three different states —
enabled, built, and published — and it matters to keep them distinct.

"Enabled" means the contracts are honest, the naming convention reserves the module
slots, the contract test harness will validate any adapter against the same
behavioural specification the GCP adapters pass today, and the `AutoConfig` registry
discovers installed adapters at boot via Java's `ServiceLoader` —
`data-pipeline-core-java/.../autoconfig/AutoConfig.java` loads every
`META-INF/services/com.enrichmeai.culvert.contracts.*` entry it finds on the
classpath. That is how `S3BlobStore`, `AwsSecretsManagerProvider`, `SqsSource`,
`SqsSink`, and `DynamoDbJobControlRepository` all get picked up at runtime without
any core changes — the same mechanism Azure's `AzureBlobStore` uses today, and the
same mechanism a future `AthenaWarehouse` or `CloudWatchMetricsHook` will use once
they land.

"Built" is what actually happened for AWS in Sprint 21: five real contracts,
unit- and LocalStack-tested, not hypothetical. "Promised" would mean I have
committed to a ship date for the *rest* of the AWS family, or for Azure, and a team
is working toward it on a calendar. That is still not true. Culvert is built and
held at version 0.1.0. Nothing is published to Maven Central. The AWS family that
exists is real, but it is not complete, and Azure's skeleton exists in the
repository to validate the seam, not to promise a release.

I have watched other vendors make the rhetorical drift from "the contracts allow
multi-cloud" to "we are a multi-cloud framework". The gap between those two
sentences is the gap that burns customers. I am not going to smudge over it. If
your procurement team asks whether Culvert runs on AWS today: for blob storage,
secrets, SQS-based streaming, and transactional job control, yes, and it is
tested against LocalStack, not just compiled. For a data warehouse, for
observability, for an execution engine, not yet. If they ask about Azure, the
answer is still no beyond `exists()` on a blob path.

## The contract tests as the handshake

The contract test module —
`data-pipeline-contract-tests-java/.../contracttests/BlobStoreContractTest.java` — is
the mechanism that makes the seam real rather than rhetorical. It is abstract. It
declares three abstract methods: `store()`, `knownUri()`, and `missingUri()`. Any
`BlobStore` implementor extends it, provides a real store backed by their cloud or a
localstack equivalent, and gets five behavioural tests for free.

`S3BlobStore` is no longer a hypothetical "future AWS implementor" in this
section — it is a real extender of `BlobStoreContractTest`, backed by a LocalStack
container, running the same specification the GCP `GcsBlobStore` passes in CI
today. The abstraction held: no leak surfaced that required revising the
`BlobStore` contract itself to accommodate S3's shape. `SqsSource`/`SqsSink` and
`AwsSecretsManagerProvider` follow the same handshake pattern against their own
contract test bases.

`DynamoDbJobControlRepository` is presently unit- and mocked-client-tested rather
than run against a LocalStack-backed `JobControlRepositoryContractTest`; a
DynamoDB LocalStack IT is tracked as in-progress alongside the Athena and
CloudWatch work, the same way the S3 and SQS LocalStack ITs preceded this
chapter's rewrite. The `WarehouseContractTest` and `SecretProviderContractTest`
in the same module follow the same extend-provide-run pattern once
`AthenaWarehouse` lands.

## The honest summary

AWS is no longer "one skeleton class." It is a real adapter family covering five
of sixteen contracts — `BlobStore` (S3, all eight methods), `SecretProvider`
(Secrets Manager), `Source`/`Sink` (SQS), and `JobControlRepository` (DynamoDB,
with a transactional control plane BigQuery cannot structurally match) — built,
unit-tested, and partially LocalStack-integration-tested in Sprint 21 (epic #144).
Two more contracts, `Warehouse` (Athena) and the observability pair (CloudWatch),
are in progress in the same sprint; Athena in particular is mock-tested only, for
the honest reason that no mature community LocalStack Athena implementation
exists yet to validate against. An AWS execution layer and Python-side AWS parity
are explicitly out of scope for this block.

Azure is exactly where it was: a single skeleton class, one of eight `BlobStore`
methods implemented, proof that the seam compiles against a non-GCP cloud and
nothing more.

Sixteen contracts exist in core. The cloud-specific ones — `BlobStore`, `Warehouse`,
`JobControlRepository`, `AuditEventPublisher`, `FinOpsSink`, `LineageEmitter`,
`ObservabilityHook`, `StageMetricsHook`, `SecretProvider`, `Source`, `Sink` — have
GCP adapters across six modules, the only family that runs production pipelines.
AWS now has real adapters for five of those eleven cloud-specific contracts
(soon seven), Azure for one. The cloud-neutral ones (`GovernancePolicy`,
`RuntimeContext`) have core-module implementations that work without any cloud at
all, on any backend.

That is the current state. The design made the AWS work additive rather than
reconstructive, and Sprint 21 is the evidence: the estimate this chapter made in
its first edition — days for `SecretProvider`, a week for the remaining `BlobStore`
methods, "architectural, not mechanical" for `JobControlRepository` — held up
against what actually got built. The contract tests made the work verifiable
against the same specification the GCP adapters already pass. The naming
convention reserved the module slots long before anyone wrote code into them.

Unlike the first edition's framing, this was not a case of waiting for an outside
team to want AWS badly enough to build it — this team built it, in-house, this
sprint, because the client work needed it. Azure is still the piece nobody has
needed badly enough to build past the skeleton, and that framing — "enabled, not
yet built, because nobody has needed it enough" — is now Azure's story specifically,
not AWS's and Azure's story together.

The seam is real. Half the family is now real too, for AWS specifically. The rest
of the family — for AWS and for Azure both — is not yet. All three of those
sentences are true and none of them cancels the others.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item \textbf{AWS moved from one skeleton method to a real adapter family in
        Sprint 21 (epic \#144):} \texttt{S3BlobStore} implements all eight
        \texttt{BlobStore} methods (\texttt{data-pipeline-aws-s3-java});
        \texttt{AwsSecretsManagerProvider} implements \texttt{SecretProvider}
        against Secrets Manager; \texttt{SqsSource}/\texttt{SqsSink} implement
        \texttt{Source}/\texttt{Sink} against SQS; \texttt{DynamoDbJobControlRepository}
        implements \texttt{JobControlRepository} with a transactional,
        conditional-write control plane that BigQuery's plain-UPDATE approach
        cannot structurally match. Five of sixteen contracts, unit-tested and
        partially LocalStack-IT-tested.
  \item \textbf{Azure is unchanged}: \texttt{AzureBlobStore}
        (\texttt{data-pipeline-azure-blob-java}) still implements only
        \texttt{BlobStore.exists()}; the remaining seven methods throw
        \texttt{UnsupportedOperationException}. It remains proof that the seam
        compiles across clouds, not a production adapter.
  \item \textbf{Two AWS contracts are in progress, not done}: \texttt{Warehouse}
        via Athena (mock-tested only — no mature community LocalStack Athena
        exists, so real-AWS validation is still pending) and the observability
        pair via CloudWatch. An AWS execution layer (Beam on EMR/Flink) and
        Python-side AWS parity are explicitly out of scope for this block.
  \item There are \textbf{sixteen contracts} in
        \texttt{data-pipeline-core-java/.../contracts/}. The cloud-specific seams
        have a full GCP family across six modules. AWS now covers five of the
        eleven cloud-specific contracts (soon seven); Azure covers one, at one
        of eight methods. The cloud-neutral contracts
        (\texttt{GovernancePolicy}, \texttt{RuntimeContext}) have core
        implementations that work on any cloud.
  \item The Sprint-21 AWS build \textbf{validated the first edition's estimates}:
        days for \texttt{SecretProvider}, about a week for the remaining
        \texttt{BlobStore} methods, "architectural, not mechanical" for
        DynamoDB's \texttt{JobControlRepository}. The contract test harness
        (\texttt{BlobStoreContractTest}, and in progress,
        \texttt{JobControlRepositoryContractTest} against DynamoDB) validated
        the new adapters against the same behavioural specification GCP
        adapters pass today.
  \item \textbf{Enabled, built, and published are three different states.}
        \texttt{AutoConfig} discovers installed adapters at boot via Java
        \texttt{ServiceLoader} — register an impl under
        \texttt{META-INF/services/} and the runtime picks it up. AWS is now
        both enabled and built for five contracts. Azure is enabled but not
        built beyond the skeleton. Neither is published: no Maven Central
        release exists, and version 0.1.0 is built and held.
  \item The Spring precedent still holds, with one update: this AWS family was
        built in-house because the work needed it, not by an outside team
        that wanted it badly enough. Azure is still waiting for that team.
        Tourist adapters are worse than no adapters; the AWS family shipped
        this sprint was not a tourist adapter.
\end{itemize}
\end{takeaways}

\newpage
