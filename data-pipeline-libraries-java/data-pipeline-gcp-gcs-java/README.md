# data-pipeline-gcp-gcs (Java)

Google Cloud Storage adapter for the Culvert data pipeline framework, JVM edition. Provides `GcsBlobStore`, the GCP implementation of the cloud-neutral [`BlobStore`](../data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/BlobStore.java) contract defined in `data-pipeline-core-java`.

Sibling of the Python adapter that will lift out of `data-pipeline-orchestration/hooks/storage.py` in a later stage.

## Status

**Version 0.1.0 — Sprint 1 deliverable** (issue [#7](https://github.com/enrichmeai/culvert/issues/7)). Sibling adapter to the sprint-1 pilot [`data-pipeline-gcp-secrets-java`](../data-pipeline-gcp-secrets-java/) and to the parallel `data-pipeline-gcp-bigquery-java`.

## Install (Maven)

```xml
<dependency>
    <groupId>com.enrichmeai.culvert</groupId>
    <artifactId>data-pipeline-gcp-gcs</artifactId>
    <version>0.1.0</version>
</dependency>
```

Pulls in `data-pipeline-core` (the contracts) plus `google-cloud-storage` (version managed by the Google Cloud `libraries-bom`).

## Contract satisfied

[`com.enrichmeai.culvert.contracts.BlobStore`](../data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/BlobStore.java):

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

## URI scheme

`GcsBlobStore` accepts URIs of the form:

```
gs://<bucket>/<object-name>
```

- `<bucket>` is required for every method.
- `<object-name>` is required for `get`, `openInput`, `openOutput`, `put`, `exists`, `delete`, and both `copy` operands.
- `list(prefix)` accepts a bucket-only URI (`gs://bucket`) to enumerate the whole bucket, or a URI with an object-name prefix (`gs://bucket/dir/`) to filter.
- Yielded URIs from `list` are absolute (full `gs://bucket/path`).
- Foreign schemes (`s3://`, `abfs://`, etc.) are rejected with `IllegalArgumentException` for single-URI methods. For `copy`, the contract documents `UnsupportedOperationException` for foreign-scheme operands; `GcsBlobStore` honours that.

## Construction

Two constructors:

```java
// 1. Production — builds a default Storage client from Application
//    Default Credentials. The bucket is supplied per-call inside each
//    gs://bucket/path URI, so no environment variable is needed.
BlobStore store = new GcsBlobStore();

// 2. Tests / custom credentials — inject a pre-built Storage client
//    (a Mockito mock in unit tests, or a client built with non-default
//    credentials in production).
BlobStore store = new GcsBlobStore(storageClient);
```

The wrapped client is closed when you call `store.close()`. The class implements `AutoCloseable` so it works in try-with-resources:

```java
try (GcsBlobStore store = new GcsBlobStore()) {
    store.put("gs://my-bucket/key.txt", "hello".getBytes());
    byte[] back = store.get("gs://my-bucket/key.txt");
}
```

## Environment variables

| Variable | Used by | Required? |
|---|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | The underlying `Storage` client (standard ADC) | Only when not running on a GCP-managed identity |

No GCP-specific environment variables are read by `GcsBlobStore` itself — GCS URIs carry the bucket inline, so there is no concept of a "default bucket" or "default project" to bind at construction time.

## ServiceLoader registration

`src/main/resources/META-INF/services/com.enrichmeai.culvert.contracts.BlobStore` lists `com.enrichmeai.culvert.gcp.gcs.GcsBlobStore` so runtime auto-discovery picks it up:

```java
ServiceLoader.load(BlobStore.class).findFirst()
    .orElseThrow(() -> new IllegalStateException("no BlobStore on classpath"));
```

## Streaming I/O

`openInput` and `openOutput` wrap GCS `ReadChannel` and `WriteChannel` via `java.nio.channels.Channels.newInputStream` / `newOutputStream`. Use these for large objects where loading the full bytes into memory would be wasteful. **Callers must close the streams** — the output stream commits the write on close.

## Errors

| Cause | Thrown |
|---|---|
| Object does not exist on `get` / `openInput` | `UncheckedIOException` wrapping `FileNotFoundException` (per contract) |
| Object does not exist on `delete` | (no exception — delete is idempotent) |
| Non-`gs://` URI | `IllegalArgumentException` |
| Foreign-scheme `copy` operand | `UnsupportedOperationException` (per contract) |
| Null `uri`, `data`, or `client` | `NullPointerException` |
| Underlying GCS failure (5xx, auth, etc.) | `StorageException` (propagated unchanged) |

## Testing

Unit tests mock `com.google.cloud.storage.Storage`, `Blob`, and `Page` with Mockito — no real GCS credentials, no network. From the `data-pipeline-libraries-java/` directory:

```bash
cd data-pipeline-libraries-java && mvn -pl data-pipeline-gcp-gcs-java -am clean test
```

Live-cloud integration tests against a real GCS bucket are sprint-2+ scope.
