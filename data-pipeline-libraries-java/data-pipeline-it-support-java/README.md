# data-pipeline-it-support

Reusable [Testcontainers](https://testcontainers.com/) fixtures for the
Culvert framework's integration tests. Adapter modules depend on this
library in **test scope** and drive emulators from their `*IT.java` tests,
which run under the parent POM's `it` profile (Maven Failsafe) against a
running Docker daemon.

This is a *test-support library*, so its dependencies are declared in
**compile** scope. That means a consumer module that adds this in test scope
inherits Testcontainers and JUnit Jupiter transitively into its own
integration tests — it does not need to re-declare them.

Testcontainers versions are managed by the `testcontainers-bom` in the parent
POM's `dependencyManagement`. Do **not** pin Testcontainers versions in
consumer module POMs.

## Fixtures

### `BigQueryEmulatorContainer`

Wraps [`ghcr.io/goccy/bigquery-emulator`](https://github.com/goccy/bigquery-emulator).

- Exposes HTTP/REST on container port `9050` and gRPC (storage API) on `9060`.
- Started with `--project=test --dataset=test` by default (override via the
  `(projectId, datasetId)` or `(image, projectId, datasetId)` constructors).
- `newClient()` returns a `com.google.cloud.bigquery.BigQuery` client pointed
  at the mapped HTTP port using `NoCredentials` and the seeded project ID.
  `newClient(projectId)` overrides the project.
- `getEmulatorHttpEndpoint()` returns the base URL once started.

### `FakeGcsServerContainer`

Wraps [`fsouza/fake-gcs-server`](https://github.com/fsouza/fake-gcs-server)
(an in-memory GCS emulator).

- Started with `-scheme http`; exposes container port `4443`.
- `newClient()` returns a `com.google.cloud.storage.Storage` client pointed at
  the mapped port using `NoCredentials`. `newClient(projectId)` overrides the
  project.
- `getEmulatorHttpEndpoint()` returns the base URL once started.

### Pub/Sub — use Testcontainers' built-in container directly

There is **no wrapper fixture for Pub/Sub** and none is needed. Testcontainers
ships a ready-made `org.testcontainers.containers.PubSubEmulatorContainer` in
the `org.testcontainers:gcloud` module, which this library already pulls in
(so consumers inherit it transitively). Use it directly:

```java
import com.google.cloud.NoCredentials;
import com.google.api.gax.core.NoCredentialsProvider;
import com.google.api.gax.grpc.GrpcTransportChannel;
import com.google.api.gax.rpc.FixedTransportChannelProvider;
import com.google.api.gax.rpc.TransportChannelProvider;
import io.grpc.ManagedChannelBuilder;
import org.testcontainers.containers.PubSubEmulatorContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

@Testcontainers
class PubSubIT {
    @Container
    static final PubSubEmulatorContainer PUBSUB = new PubSubEmulatorContainer(
        DockerImageName.parse("gcr.io/google.com/cloudsdktool/google-cloud-cli:emulators"));

    // Build channel/credentials providers from PUBSUB.getEmulatorEndpoint(),
    // then pass them to TopicAdminClient / SubscriptionAdminClient / Publisher.
}
```

## Wiring a consumer module

Add the test-scope dependency in the adapter module's `pom.xml`:

```xml
<dependency>
    <groupId>com.enrichmeai.culvert</groupId>
    <artifactId>data-pipeline-it-support</artifactId>
    <version>${project.version}</version>
    <scope>test</scope>
</dependency>
```

Then write an `*IT.java` test (Failsafe picks up the `*IT` suffix under the
`it` profile):

```java
import com.enrichmeai.culvert.itsupport.BigQueryEmulatorContainer;
import com.google.cloud.bigquery.BigQuery;
import org.junit.jupiter.api.Test;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

@Testcontainers
class BigQueryWarehouseIT {

    @Container
    static final BigQueryEmulatorContainer EMULATOR = new BigQueryEmulatorContainer();

    @Test
    void roundTrip() {
        BigQuery bq = EMULATOR.newClient();
        // ... exercise the adapter against bq ...
    }
}
```

GCS is identical with `FakeGcsServerContainer` and a
`com.google.cloud.storage.Storage` client.

## Running the ITs

Integration tests run only under the `it` profile and need a running Docker
daemon:

```bash
mvn -P it verify
```

Day-to-day `mvn test` (Surefire, `*Test.java`) is unaffected.
