# data-pipeline-gcp-pubsub (Java)

Google Cloud Pub/Sub adapter for the Culvert data pipeline framework, JVM edition. Provides `PubSubSource` and `PubSubSink`, the GCP implementations of the cloud-neutral [`Source`](../data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Source.java) and [`Sink`](../data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Sink.java) contracts defined in `data-pipeline-core-java`.

## Status

**Version 0.1.0 — Sprint 2 deliverable** (issue [#23](https://github.com/enrichmeai/culvert/issues/23)). Mirrors the sprint-1 BigQuery and Secrets pilots in shape: BOM-in-module, no application framework, ServiceLoader-registered, AutoCloseable only when the wrapped client supports it.

## Install (Maven)

```xml
<dependency>
    <groupId>com.enrichmeai.culvert</groupId>
    <artifactId>data-pipeline-gcp-pubsub</artifactId>
    <version>0.1.0</version>
</dependency>
```

Pulls in `data-pipeline-core` (the contracts) plus `google-cloud-pubsub` (version managed by the Google Cloud `libraries-bom`, pinned to `26.39.0` here).

## Contracts satisfied

```java
public interface Source<T> {
    Iterator<T> read(RuntimeContext context);
}

public interface Sink<U> {
    void write(Iterator<U> records, RuntimeContext context);
}
```

Record type is `com.google.pubsub.v1.PubsubMessage` for both, so a sink can re-emit messages a source produced without translation.

## PubSubSource

Wraps a [`SubscriberStub`](https://cloud.google.com/java/docs/reference/google-cloud-pubsub/latest/com.google.cloud.pubsub.v1.stub.SubscriberStub) and performs a single synchronous `pull` per `read()` call. Returned messages are acknowledged eagerly before `read()` returns, so the delivery model is **at-most-once**. Callers who need at-least-once should wire a Subscriber-based reader instead.

### Constructors

```java
// Default: max 100 messages per pull
PubSubSource source = new PubSubSource(subscriberStub, "projects/p/subscriptions/my-sub");

// Explicit per-pull batch size
PubSubSource source = new PubSubSource(subscriberStub, "projects/p/subscriptions/my-sub", 25);
```

`subscriptionName` must be the fully-qualified resource name. Use [`ProjectSubscriptionName.of(project, name).toString()`](https://cloud.google.com/java/docs/reference/google-cloud-pubsub/latest/com.google.pubsub.v1.ProjectSubscriptionName) to build it.

### Lifecycle

`PubSubSource` implements `AutoCloseable` because `SubscriberStub` extends `BackgroundResource extends AutoCloseable`. Use try-with-resources:

```java
try (PubSubSource source = new PubSubSource(stub, subscriptionName)) {
    source.read(context).forEachRemaining(msg ->
        System.out.println(msg.getData().toStringUtf8()));
}
```

## PubSubSink

Wraps a [`Publisher`](https://cloud.google.com/java/docs/reference/google-cloud-pubsub/latest/com.google.cloud.pubsub.v1.Publisher) and forwards each record via `publisher.publish(message)`. Per-message futures are collected and awaited before `write()` returns, so per-message publish failures surface as `PubSubSink.PubSubPublishException`.

### Constructor

```java
// Publisher carries the topic name and any batching/retry settings.
Publisher publisher = Publisher.newBuilder(TopicName.of("p", "t")).build();
PubSubSink sink = new PubSubSink(publisher);
```

### Lifecycle

`Publisher` does **not** implement `AutoCloseable` — it exposes `shutdown()` plus `awaitTermination(long, TimeUnit)`. Per the framework's "AutoCloseable only when the wrapped client supports it" rule, `PubSubSink` is not `AutoCloseable` either. Use the passthrough:

```java
sink.write(records, context);
sink.shutdown(30, TimeUnit.SECONDS);
```

## Environment variables

| Variable | Used by | Required? |
|---|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | The underlying `SubscriberStub` / `Publisher` (standard ADC) | Only when not running on a GCP-managed identity |

No Pub/Sub-specific environment variables are read by this module — the subscription FQN and topic FQN are explicit constructor arguments, so there is no concept of a "default subscription" or "default topic" baked in.

## ServiceLoader registration

`src/main/resources/META-INF/services/` lists both:

- `com.enrichmeai.culvert.contracts.Source` → `com.enrichmeai.culvert.gcp.pubsub.PubSubSource`
- `com.enrichmeai.culvert.contracts.Sink` → `com.enrichmeai.culvert.gcp.pubsub.PubSubSink`

Like the BigQuery pilot, the implementations do **not** expose a no-arg constructor (they need a `SubscriberStub` / `Publisher` injected). Direct `ServiceLoader.load(Source.class).findFirst()` will therefore fail with `ServiceConfigurationError` until sprint-4 wires a config-driven constructor. Instantiate explicitly until then.

## Errors

| Cause | Thrown |
|---|---|
| Pull RPC fails | Underlying `ApiException` propagates unchanged |
| Acknowledge RPC fails (after pull succeeds) | Underlying `ApiException` propagates unchanged (caller may see ack loss) |
| Any publish future fails | `PubSubSink.PubSubPublishException` (cause is the underlying SDK exception) |
| Interrupted during publish await | `PubSubSink.PubSubPublishException` after restoring the interrupt flag |
| Null constructor arg or `read`/`write` arg | `NullPointerException` |
| `maxMessages <= 0` | `IllegalArgumentException` |

## Testing

Unit tests mock `SubscriberStub` (plus its `UnaryCallable` chains) and `Publisher` with Mockito. Future-driven behaviour uses `com.google.api.core.ApiFutures.immediateFuture` / `immediateFailedFuture` so no thread juggling is needed. No real Pub/Sub credentials, no network. From the `data-pipeline-libraries-java/` directory:

```bash
cd data-pipeline-libraries-java && mvn -pl data-pipeline-gcp-pubsub-java -am clean test
```

Live-cloud integration tests against a real Pub/Sub topic are sprint-3+ scope.
