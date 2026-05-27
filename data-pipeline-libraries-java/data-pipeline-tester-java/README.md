# data-pipeline-tester (Java)

Mockito-helper fixture builders for the Culvert framework's contract
Protocols. Consumers of `data-pipeline-core` use these helpers to mock
`SecretProvider`, `Warehouse`, `BlobStore`, `JobControlRepository`, and
`FinOpsSink` in their own unit tests without repeating the
`Mockito.mock(...)` + `when(...).thenReturn(...)` boilerplate.

Sprint-2 deliverable (issue #26). Sprint-5 will add a full contract test
harness on top of these fixtures.

## Add to your tests

```xml
<dependency>
    <groupId>com.enrichmeai.culvert</groupId>
    <artifactId>data-pipeline-tester</artifactId>
    <version>0.1.0</version>
    <scope>test</scope>
</dependency>
```

Mockito and AssertJ come transitively (the tester library uses them at
compile scope, so consumers don't need to add them separately).

## SecretProviderFixtures

Build a `SecretProvider` mock backed by a static map, or one that fails
on every call. Use this when your unit under test reads secrets via a
`SecretProvider` and you don't want to touch real Secret Manager.

```java
import static com.enrichmeai.culvert.tester.SecretProviderFixtures.*;

SecretProvider sp = staticSecretProvider(Map.of(
    "db.password", "hunter2",
    "api.key", "abc"));
String pwd = sp.get("db.password");           // "hunter2"
sp.get("missing");                             // throws NoSuchElementException

SecretProvider broken = failingSecretProvider(
    new RuntimeException("IAM denied"));
broken.get("anything");                        // throws

SecretProvider partial = notFoundFor("missing.one");
partial.get("present");                        // "fixture-value-for-present"
partial.get("missing.one");                    // throws NoSuchElementException
```

## WarehouseFixtures

Build a `Warehouse` mock with empty defaults (queries empty, tableExists
false) and add specific stubbing on top. The `rows(...)` helper builds a
lazy iterator over row maps for stubbing `query` results.

```java
import static com.enrichmeai.culvert.tester.WarehouseFixtures.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.when;

Warehouse w = warehouseWithTables("proj.ds.users", "proj.ds.orders");
w.tableExists("proj.ds.users");                // true
w.tableExists("proj.ds.missing");              // false

when(w.query(anyString(), anyMap()))
    .thenReturn(rows(Map.of("id", 1), Map.of("id", 2)));

Warehouse broken = failingWarehouse(new RuntimeException("outage"));
broken.query("SELECT 1", Map.of());            // throws
```

## BlobStoreFixtures

Build a `BlobStore` mock backed by an in-memory URI -> bytes map.
`get`, `openInput`, and `exists` reflect the map; missing URIs raise
`UncheckedIOException(FileNotFoundException)` matching the contract.
`put`/`openOutput`/`delete`/`copy` default to Mockito no-ops; stub on
top with `doAnswer`/`verify` when you need to assert against writes.

```java
import static com.enrichmeai.culvert.tester.BlobStoreFixtures.*;

BlobStore bs = blobStoreWith(Map.of(
    "gs://b/users.csv",  "id,name\n1,Alice\n".getBytes(),
    "gs://b/orders.csv", "id,total\n1,100\n".getBytes()));

bs.exists("gs://b/users.csv");                 // true
byte[] bytes = bs.get("gs://b/users.csv");
bs.list("gs://b/");                            // iterates both URIs (sorted)
bs.get("gs://b/missing");                      // throws UncheckedIOException
```

## JobControlRepositoryFixtures

Build a `JobControlRepository` mock pre-populated with `PipelineJob`
records. `getJob(runId)` resolves the matching job; `getPendingJobs`
returns the seed list. Mutating methods (`createJob`, `updateStatus`,
`markFailed`, etc.) are Mockito no-ops — use `verify(repo).createJob(...)`
to assert your unit under test wrote what it should.

```java
import static com.enrichmeai.culvert.tester.JobControlRepositoryFixtures.*;

PipelineJob job = PipelineJob.builder(
        "run-1", "retail", "ingest", LocalDate.of(2026, 1, 1),
        JobStatus.RUNNING)
    .build();

JobControlRepository repo = repoWith(job);
repo.getJob("run-1");                          // Optional.of(job)
repo.getJob("missing");                        // Optional.empty()

// Mockito verify-style assertions still work:
// verify(repo).updateStatus("run-1", JobStatus.SUCCEEDED, Optional.of(100L));
```

## FinOpsSinkFixtures

Build a `CaptureSink` — a real `FinOpsSink` (not a mock) that records
every `record(...)` invocation to a thread-safe list for later
assertion. Simpler than wrestling Mockito `ArgumentCaptor` for a record
of two non-null arguments.

```java
import static com.enrichmeai.culvert.tester.FinOpsSinkFixtures.*;

CaptureSink sink = captureSink();
pipeline.run(sink);

assertThat(sink.records()).hasSize(3);
assertThat(sink.records().get(0).metrics().runId()).isEqualTo("run-1");
assertThat(sink.records().get(0).tags().environment()).isEqualTo("dev");
```

## Build and test

```sh
cd data-pipeline-libraries-java
mvn -pl data-pipeline-tester-java -am clean test
```
