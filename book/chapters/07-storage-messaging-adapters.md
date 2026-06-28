# Chapter 7 — Storage and Messaging Adapters

\index{adapter|textbf}

The previous two chapters were about contracts: what they are, why they exist,
how sixteen interfaces form a portability boundary that lets you swap one cloud
for another without touching your pipeline logic. All of that is true and
useful and, if you are being honest, still a bit theoretical. Contracts are
just Java interfaces and Python Protocols. The thing that makes them real is
an adapter — the class that implements the contract against a specific cloud
SDK.

This chapter covers the first two concrete adapters in Culvert's GCP
implementation: `GcsBlobStore`, which backs `BlobStore` against Google Cloud
Storage, and `PubSubSource`/`PubSubSink`, which back `Source` and `Sink`
against Google Cloud Pub/Sub. They are the Sprint-1 and Sprint-2 deliverables
for issues #7 and #23 respectively. They are built, they are tested, and they
are sitting in the repo unpublished — exactly the honest status the framework
carries everywhere.

What I want to do in this chapter is not just show you the APIs. I want to
show you *where the cloud-specific mess lives*, because adapters are where
the clean abstractions meet the particular awkwardness of a real SDK. Each one
taught us something we had not anticipated when we wrote the contracts.

## Why adapters, not thin wrappers

There is a failure mode I have seen in almost every framework that attempts
abstraction over cloud services. The author writes the interface, then writes
a class that is essentially a one-to-one delegation to the SDK, gives it a
name ending in `Adapter`, and calls it done. What you get is an extra layer of
indirection that adds no value. The contract method calls the adapter method,
the adapter method calls the SDK method, the names are different, and you have
to trace through three files to understand what happens on a 404.

Culvert's adapters are meant to be different, and the way to be different is
to put real decisions in them. Three examples from `GcsBlobStore` alone:

1. **URI ownership.** The `BlobStore` contract (`data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/BlobStore.java:11-14`) declares URIs opaque strings. It explicitly does *not* parse them. That is a decision: the contract says what a URI conceptually is (an opaque address); the adapter decides what scheme it accepts and how to decompose it into bucket and object name. `GcsBlobStore` owns every bit of `gs://` parsing. Nothing else in the framework touches it.

2. **Null rejection.** A caller passing `null` as a URI is a programming error, not a runtime condition. The adapter enforces that upfront. In Java, `Objects.requireNonNull(uri, "uri must not be null")` (`GcsBlobStore.java:222`) throws `NullPointerException` with a useful message before anything touches the GCS client. In Python, `_parse` opens with an explicit `if uri is None: raise TypeError(...)` (`blob_store.py:89-90`). The error type differs by language — NPE in Java, `TypeError` in Python — because that is what each language's conventions demand, and the contract says nothing about error types. Adapters speak the language of their ecosystem.

3. **404 → contract semantics.** The `BlobStore` contract documents that `get` should raise `FileNotFoundException` for a missing object. GCS does not raise `FileNotFoundException`; it returns a null `Blob` from `Storage#get`. The adapter bridges that gap (`GcsBlobStore.java:84-90`): check for null, wrap in `UncheckedIOException` with `FileNotFoundException` as the cause. The caller gets the contract's promised exception, not GCS's null.

These decisions are not exotic. They are the mundane, necessary work that every real adapter has to do. The point of naming them is that they need to live somewhere, and if they live in the adapter, they are in exactly one place and that place has a contract to test against.

## GcsBlobStore — object storage with a URI parser inside

\index{GcsBlobStore|textbf}

`GcsBlobStore` implements `BlobStore` against the `com.google.cloud.storage.Storage` client. Its source lives at:

```
data-pipeline-libraries-java/data-pipeline-gcp-gcs-java/src/main/java/
    com/enrichmeai/culvert/gcp/gcs/GcsBlobStore.java
```

The class signature is straightforward:

```java
public final class GcsBlobStore implements BlobStore, AutoCloseable {

    public static final String SCHEME = "gs://";

    private final Storage client;

    // No-arg constructor for ServiceLoader discovery.
    public GcsBlobStore() {
        this(StorageOptions.getDefaultInstance().getService());
    }

    // Constructor for tests and custom-credential wiring.
    public GcsBlobStore(Storage client) {
        this.client = Objects.requireNonNull(client, "client must not be null");
    }
```

(Source: `GcsBlobStore.java:49-78`)

The no-arg constructor is the `ServiceLoader` entry point. GCS URIs carry the
bucket inline — `gs://my-bucket/path/to/file` — so no default bucket or
project ID is needed at construction time. Application Default Credentials
handle authentication. The injectable-client constructor exists for tests:
you pass a Mockito mock and never touch real GCS.

The `AutoCloseable` implementation is honest about the SDK's checked
exception:

```java
@Override
public void close() {
    try {
        client.close();
    } catch (Exception e) {
        if (e instanceof IOException ioe) {
            throw new UncheckedIOException(ioe);
        }
        throw new RuntimeException(e);
    }
}
```

(Source: `GcsBlobStore.java:193-204`)

`Storage#close` throws `Exception`, which is the kind of signature that makes
Java programmers wince. We narrow it: `IOException` becomes
`UncheckedIOException`; anything else becomes `RuntimeException`. Callers of
`close()` are not expected to handle storage-close failures; surfacing them as
unchecked is the pragmatic choice.

### URI parsing

The URI parser is a private static helper that gets everything else right
regardless of what the caller passes:

```java
private static ParsedUri parseUri(String uri) {
    Objects.requireNonNull(uri, "uri must not be null");
    if (!uri.startsWith(SCHEME)) {
        throw new IllegalArgumentException(
                "URI must start with " + SCHEME + ": " + uri);
    }
    String rest = uri.substring(SCHEME.length());
    int slash = rest.indexOf('/');
    String bucket;
    String objectName;
    if (slash < 0) {
        bucket = rest;
        objectName = "";
    } else {
        bucket = rest.substring(0, slash);
        objectName = rest.substring(slash + 1);
    }
    if (bucket.isEmpty()) {
        throw new IllegalArgumentException(
                "URI must include a bucket: " + uri);
    }
    return new ParsedUri(bucket, objectName);
}
```

(Source: `GcsBlobStore.java:221-243`)

Three cases are rejected immediately: `null` (NPE), non-`gs://` scheme
(`IllegalArgumentException`), and a missing bucket (`IllegalArgumentException`).
A URI with a bucket but no object name — `gs://my-bucket` — is valid only for
`list(prefix)`, which calls `parseUri` without the further check that a
non-empty `objectName` is present (`GcsBlobStore.java:212-218`). Every other
operation calls the stricter `parse(uri)` wrapper which asserts the object
name is non-empty.

The equivalent in Python is via `urllib.parse.urlparse` with the same three
guards (`blob_store.py:88-101`). There the non-`gs://` scheme raises
`ValueError` rather than `IllegalArgumentException` — same conceptual error,
idiomatic for each language.

### The core operations

\index{BlobStore!get}\index{BlobStore!put}\index{BlobStore!list}

`get`, `put`, `openInput`, `openOutput`, `list`, `exists`, `delete`, and `copy`
are all present, which is the full `BlobStore` surface. A few are worth a
closer look.

**`list`** returns an `Iterator<String>` rather than loading all object names
into memory. The implementation wraps GCS's `Page<Blob>` in a bespoke
iterator that reconstructs the full `gs://bucket/object` URI from the `Blob`'s
name field (`GcsBlobStore.java:123-144`). This is intentional: the contract
says to return absolute URIs, and the caller should not need to know the
bucket name separately.

**`delete`** is idempotent by contract. The GCS SDK's `Storage#delete` returns
`false` for a missing object rather than throwing, but a `StorageException`
with code 404 can still escape if the client is configured differently.
The adapter catches it explicitly (`GcsBlobStore.java:160-167`) and treats it
as a no-op, consistent with the contract's documented behaviour.

**`copy`** documents cross-store copies as out of scope:

```java
@Override
public void copy(String src, String dst) {
    if (!isGcsUri(src) || !isGcsUri(dst)) {
        throw new UnsupportedOperationException(
                "GcsBlobStore.copy only supports gs:// to gs:// copies; got "
                        + "src=" + src + ", dst=" + dst);
    }
    // ...
}
```

(Source: `GcsBlobStore.java:172-179`)

The contract's comment on `copy` (`BlobStore.java:60-63`) explicitly permits
this: "Cross-store copies are out of scope; implementations may throw
`UnsupportedOperationException` for foreign schemes." The adapter enforces
the boundary at the right place — before the URI parser gets a chance to
produce a confusing `IllegalArgumentException` about the scheme.

### Python parity

The Python adapter (`data-pipeline-libraries/data-pipeline-gcp-gcs/src/data_pipeline_gcp_gcs/blob_store.py`) mirrors the Java surface with one difference worth noting: the constructor takes an explicit `client` argument with no default (`blob_store.py:26-29`). There is no equivalent of the no-arg ServiceLoader constructor in Python — the adapter is wired up by autoconfig rather than by Java's ServiceLoader mechanism. That difference is a natural consequence of the two runtimes' different discovery models, and Chapter 15 covers autoconfig in detail.

The Python `_is_not_found` helper (`blob_store.py:103-108`) uses duck-typing
to check for 404 errors rather than importing `google.api_core.exceptions.NotFound`
directly. That keeps the adapter loosely coupled to the SDK version — a small
thing that has quietly saved us from a version bump once already.

## PubSubSource and PubSubSink — messaging with delivery decisions

\index{PubSubSource|textbf}\index{PubSubSink|textbf}

The messaging pair lives at:

```
data-pipeline-libraries-java/data-pipeline-gcp-pubsub-java/src/main/java/
    com/enrichmeai/culvert/gcp/pubsub/PubSubSource.java
    com/enrichmeai/culvert/gcp/pubsub/PubSubSink.java
```

with Python siblings at:

```
data-pipeline-libraries/data-pipeline-gcp-pubsub/src/data_pipeline_gcp_pubsub/io.py
```

The contracts they implement are `Source<T>` and `Sink<U>` from
`data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/`.
Both are `@FunctionalInterface` — `Source.read(RuntimeContext)` returns
`Iterator<T>`; `Sink.write(Iterator<U>, RuntimeContext)` consumes it
(`Source.java:20-30`, `Sink.java:16-26`).

The Pub/Sub SDK does not map cleanly onto those shapes. That is the whole
problem the adapters solve.

### PubSubSource — pulling and the at-most-once decision

\index{PubSubSource!at-most-once}

```java
public final class PubSubSource implements Source<PubsubMessage>, AutoCloseable {

    public static final int DEFAULT_MAX_MESSAGES = 100;

    private final SubscriberStub stub;
    private final String subscriptionName;
    private final int maxMessages;
```

(Source: `PubSubSource.java:50-57`)

The design is a synchronous pull wrapper. Each call to `read(context)` issues
one `pull` RPC against the subscription, acknowledges the batch eagerly, and
returns an iterator over the payloads. The delivery model is **at-most-once**:
a consumer that crashes mid-iteration after `read` has returned will lose the
pulled batch, because the acknowledgements were sent before the iterator was
handed back.

This is an explicit, documented decision, not an accident:

```java
// Eager ack: collect ackIds and acknowledge before exposing
// messages. This gives at-most-once semantics — documented on the
// class — and keeps the iterator simple (no per-message ack callback
// for the consumer to forget).
List<String> ackIds = new ArrayList<>(received.size());
List<PubsubMessage> payloads = new ArrayList<>(received.size());
for (ReceivedMessage rm : received) {
    ackIds.add(rm.getAckId());
    payloads.add(rm.getMessage());
}

AcknowledgeRequest ackRequest = AcknowledgeRequest.newBuilder()
        .setSubscription(subscriptionName)
        .addAllAckIds(ackIds)
        .build();
stub.acknowledgeCallable().call(ackRequest);

return payloads.iterator();
```

(Source: `PubSubSource.java:122-139`)

Why at-most-once? Because the `Source<T>` contract has no per-message ack
callback. There is nowhere to surface it. If we had tried to implement
at-least-once semantics through the `Source` interface alone, we would have
had to either (a) add a callback to the contract — which would break every
other `Source` implementation — or (b) require callers to cast to
`PubSubSource` and call a separate ack method, which defeats the purpose of
the abstraction. At-most-once with eager ack is the honest choice given the
contract shape.

The Javadoc is explicit: callers needing at-least-once semantics should wire
a separate `Subscriber`-based reader, not use this adapter
(`PubSubSource.java:24-28`).

The Python counterpart in `io.py` has slightly different timing. The Python
`read(context)` is a generator — it `yield`s each message as it processes the
received list and sends the `acknowledge` call after the loop finishes
(`io.py:37-62`). The ack goes out after all messages have been yielded, which
means a consumer that breaks out of the iteration early will still get the
whole batch acknowledged on the next garbage-collection cycle of the generator.
In practice this is a minor distinction — the Python code even labels it
"eager-ack" in its comment — but if you are writing contract tests, the
difference in timing is real.

**`subscriptionName`** must be the fully-qualified resource name:
`projects/{project}/subscriptions/{name}`. The constructor does not validate
this format — it trusts the caller has used
`ProjectSubscriptionName.of(project, name)` — but an unqualified name will
produce a Pub/Sub gRPC error at pull time that will not be pleasant to
diagnose. A note for the future.

`PubSubSource` implements `AutoCloseable` because `SubscriberStub` extends
`BackgroundResource`, which itself extends `AutoCloseable`
(`PubSubSource.java:154-156`). Use it in a try-with-resources and the gRPC
channel closes cleanly.

### PubSubSink — publish futures and surface-level failures

\index{PubSubSink!PubSubPublishException}

`PubSubSink` wraps a `Publisher` — the Pub/Sub SDK's async publish client.
The mismatch with the `Sink` contract is stark: `Sink.write` is synchronous
from the caller's perspective; `Publisher#publish` returns an `ApiFuture<String>`
immediately. The adapter bridges them by collecting all futures and then
blocking:

```java
@Override
public void write(Iterator<PubsubMessage> records, RuntimeContext context) {
    Objects.requireNonNull(records, "records must not be null");

    List<ApiFuture<String>> futures = new ArrayList<>();
    while (records.hasNext()) {
        PubsubMessage message = records.next();
        if (message == null) {
            throw new NullPointerException(
                    "records iterator yielded a null PubsubMessage");
        }
        futures.add(publisher.publish(message));
    }

    if (futures.isEmpty()) {
        return;
    }

    try {
        ApiFutures.allAsList(futures).get();
    } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
        throw new PubSubPublishException(
                "Interrupted while waiting for Pub/Sub publish futures", e);
    } catch (ExecutionException e) {
        throw new PubSubPublishException(
                "Pub/Sub publish failed: " + e.getCause().getMessage(),
                e.getCause());
    }
}
```

(Source: `PubSubSink.java:79-109`)

The `ApiFutures.allAsList(futures).get()` call resolves when every future
resolves; if any fails, the composite future fails with the first cause.
That cause surfaces as `PubSubPublishException` — a public `RuntimeException`
subclass nested in `PubSubSink` (`PubSubSink.java:139-145`). The wrapper
exists so callers can catch publish failures specifically without depending
on the GCP SDK's exception hierarchy at the catch site.

One nuance the Javadoc is careful about: later records in the same batch may
have already been published before the first failure surfaces
(`PubSubSink.java:68-71`). This is partial-failure territory, and there is no
clean way to make it otherwise when the underlying transport is asynchronous
and batch-acknowledged. The honest answer is that `PubSubSink` gives you
synchronous error surfacing, not idempotent batch retry. If you need the
latter, you need a richer layer on top.

**Lifecycle asymmetry.** `Publisher` does not implement `AutoCloseable`. It
exposes `shutdown()` + `awaitTermination(long, TimeUnit)` instead, which is
an older Java lifecycle convention. Per the framework's rule — "AutoCloseable
only when the wrapped client supports it" — `PubSubSink` also does not
implement `AutoCloseable`. There is an explicit `shutdown` method
(`PubSubSink.java:124-127`) that passes through to the publisher. Wire it
into your pipeline teardown hook; the framework does not call it
automatically.

This is the direct contrast to `GcsBlobStore` (which does implement
`AutoCloseable` because `Storage#close` exists) and `PubSubSource` (which
does, because `SubscriberStub` extends `BackgroundResource`). Three adapters,
two different lifecycle shapes — the inconsistency is GCP's, not ours.

The Python `PubSubSink` (`io.py:65-93`) takes a similar approach: collect
futures from `publisher.publish(topic_path, data, **attributes)` and block on
each with `future.result()` (`io.py:91-93`). The Python publisher's topic path
is passed per-call rather than being baked into the publisher object, which is
why `PubSubSink.__init__` accepts both `publisher` and `topic_path` separately.

### What the contract hides — and what it doesn't

These two adapters between them implement four contract methods: `BlobStore` (8
methods), `Source.read` (1), `Sink.write` (1). The pipeline logic that uses
them sees `BlobStore`, `Source<PubsubMessage>`, and `Sink<PubsubMessage>`. It
does not see `Storage`, `SubscriberStub`, `Publisher`, `ApiFuture`, or any
GCS-specific URI handling.

What the contract does *not* hide is the message type. `PubSubSource` and
`PubSubSink` are both typed over `PubsubMessage` — a Pub/Sub SDK protobuf type.
That means pipeline logic that uses these adapters has a dependency on the
Pub/Sub SDK even if it never touches a `Publisher`. We considered a
message-type abstraction (`Map<String, Object>` or a bespoke record) but
rejected it: the serialisation logic would live somewhere, and pushing it into
an intermediate type made the adapter more complex without removing the SDK
dependency in any useful sense. The Python adapters do use
`Mapping[str, Any]` (`io.py:12`) — a more natural choice in Python where
protobuf types are less pervasive — so the two sides have drifted on message
representation. Chapter 6 covers polyglot parity in more detail; the honest
summary is that this is the seam that needs a contract-test to keep it honest.

## The contract-test anchor

Both adapters are tested against contract mixins from `data-pipeline-contract-tests`.
The Python GCS test binds `BlobStoreContract` to `GcsBlobStore` via
`TestGcsBlobStoreContract(BlobStoreContract)` with a mocked `storage.Client`
(`tests/test_blob_store.py:22-24`). The contract mixin exercises every method
in the `BlobStore` surface — not just the happy path — with the same fixture
setup. That is the mechanism that keeps the adapter honest: you cannot add an
operation to the contract without updating the mixin, and you cannot implement
a broken adapter without the mixin catching it.

Chapter 16 goes into contract testing in depth. For now, the key point is
that "implements BlobStore" is not a claim you verify by inspection. It is a
claim you verify by binding the implementation to the contract-test suite and
running it.

## FinOps trackers — a forward note

\index{GcsCostTracker}\index{PubSubCostTracker}

Alongside the adapters sit two cost-tracking classes: `GcsCostTracker`
(`GcsBlobStore.java`'s sibling) and `PubSubCostTracker`. They record bytes
written, bytes stored, and message-throughput costs against a `FinOpsSink` —
the framework's contract for cost attribution. They are baked into the
adapter modules so you get cost visibility as part of the storage and messaging
wiring, not as an afterthought.

Chapter 13 covers the FinOps layer properly. The short version: per-GiB
storage cost for GCS (`GcsCostTracker.java:90`); per-TiB throughput cost for
Pub/Sub (`PubSubCostTracker.java:81`); both emit `CostMetrics` records via
`FinOpsSink` keyed to a `run_id` so you can join them to the audit trail.

## What we learnt

I will confess that writing these adapters was more work than I expected,
and most of that work was *not* the GCS or Pub/Sub API calls. Those are
well-documented. What took time was the small decisions: null handling that
speaks each language's idiom, URI validation that belongs in the adapter
rather than the contract, lifecycle shapes that differ between adapters because
the underlying SDKs differ. None of it is glamorous. All of it matters when
you are debugging a pipeline at two in the morning.

The reward is that `BlobStore`, `Source`, and `Sink` are now GCP-concrete
without either being GCP-aware. The next chapter (Chapter 8) takes a similar
approach to BigQuery — the warehouse adapter — which has more surface area and
a few sharper edges.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item \textbf{The contract declares URIs opaque; the adapter owns the scheme.}
        \texttt{BlobStore} says nothing about \texttt{gs://}. \texttt{GcsBlobStore}
        owns every byte of URI parsing, null-rejection (NPE in Java,
        \texttt{TypeError} in Python), and scheme validation
        (\texttt{IllegalArgumentException} / \texttt{ValueError}).
        Different error types per language are deliberate — adapters speak
        their ecosystem's idiom.
  \item \textbf{Eager-ack is an explicit delivery model, not an oversight.}
        \texttt{PubSubSource} acknowledges the pulled batch before returning
        the iterator — at-most-once semantics by design. The
        \texttt{Source<T>} contract has no per-message ack callback; any
        attempt to wire at-least-once semantics through the same interface
        would break every other \texttt{Source} implementation.
  \item \textbf{Publish futures block synchronously; failures surface as
        \texttt{PubSubPublishException}.} The sink collects all futures from
        a \texttt{write} call and waits for them before returning. Silent
        publish failures are not acceptable; the exception type is public so
        callers can catch it without depending on the GCP SDK's hierarchy.
  \item \textbf{Lifecycle shapes are inherited from the SDK, not invented.}
        \texttt{GcsBlobStore} and \texttt{PubSubSource} implement
        \texttt{AutoCloseable} because their wrapped clients support
        \texttt{close()}. \texttt{PubSubSink} does not, because
        \texttt{Publisher} uses \texttt{shutdown}/\texttt{awaitTermination}.
        The asymmetry is GCP's; the adapters document it honestly.
  \item \textbf{Contract tests are the verification mechanism.} Claiming an
        adapter "implements \texttt{BlobStore}" means nothing until the
        implementation is bound to the \texttt{BlobStoreContract} test mixin.
        The mixin is the executable specification.
\end{itemize}
\end{takeaways}

\newpage
