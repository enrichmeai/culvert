# data-pipeline-gcp-secrets (Java)

Google Cloud Secret Manager adapter for the Culvert data pipeline framework, JVM edition. Provides `SecretManagerProvider`, the GCP implementation of the cloud-neutral [`SecretProvider`](../data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/SecretProvider.java) contract defined in `data-pipeline-core-java`.

Sibling of the Python adapter that will lift out of `data-pipeline-orchestration/hooks/secrets.py` in a later stage.

## Status

**Version 0.1.0 — Sprint 1 deliverable** (issue [#5](https://github.com/enrichmeai/culvert/issues/5)). First concrete GCP adapter to ship under the Culvert polyglot framework — the pilot that validates the sprint-1 coordination pattern for `data-pipeline-gcp-bigquery-java` and `data-pipeline-gcp-gcs-java`.

## Install (Maven)

```xml
<dependency>
    <groupId>com.enrichmeai.culvert</groupId>
    <artifactId>data-pipeline-gcp-secrets</artifactId>
    <version>0.1.0</version>
</dependency>
```

Pulls in `data-pipeline-core` (the contracts) plus `google-cloud-secretmanager` (version managed by the Google Cloud `libraries-bom`).

## Contract satisfied

[`com.enrichmeai.culvert.contracts.SecretProvider`](../data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/SecretProvider.java):

```java
public interface SecretProvider {
    String get(String name, String version);
    default String get(String name) { return get(name, "latest"); }
}
```

`SecretManagerProvider` resolves each lookup to a Secret Manager resource path of the form `projects/{projectId}/secrets/{name}/versions/{version}`.

## Construction

Three constructors:

```java
// 1. Production — builds a default SecretManagerServiceClient from
//    Application Default Credentials.
SecretProvider sm = new SecretManagerProvider("my-gcp-project");

// 2. Tests / custom credentials — inject a pre-built client (a Mockito
//    mock in unit tests, or a client built with non-default credentials
//    in production).
SecretProvider sm = new SecretManagerProvider("my-gcp-project", client);

// 3. ServiceLoader discovery — reads GCP_PROJECT_ID from the
//    environment. Required so java.util.ServiceLoader can instantiate
//    this provider via the META-INF/services registration.
SecretProvider sm = new SecretManagerProvider();
```

The wrapped client is closed when you call `provider.close()`. The class implements `AutoCloseable` so it works in try-with-resources:

```java
try (SecretManagerProvider sm = new SecretManagerProvider("my-project")) {
    String token = sm.get("api-token");
    String pinnedKey = sm.get("api-key", "3");
    // ...
}
```

## Environment variables

| Variable | Used by | Required? |
|---|---|---|
| `GCP_PROJECT_ID` | The no-arg constructor (and therefore `ServiceLoader` discovery) | Only if you use the no-arg path |
| `GOOGLE_APPLICATION_CREDENTIALS` | The underlying `SecretManagerServiceClient` (standard ADC) | Only when not running on a GCP-managed identity |

The two explicit-`projectId` constructors do **not** read any environment variable themselves.

## ServiceLoader registration

`src/main/resources/META-INF/services/com.enrichmeai.culvert.contracts.SecretProvider` lists `com.enrichmeai.culvert.gcp.secrets.SecretManagerProvider` so runtime auto-discovery picks it up:

```java
ServiceLoader.load(SecretProvider.class).findFirst()
    .orElseThrow(() -> new IllegalStateException("no SecretProvider on classpath"));
```

## Errors

| Cause | Thrown |
|---|---|
| Secret does not exist (GCP `NotFoundException`) | `java.util.NoSuchElementException` (per the contract) |
| Default-client construction fails (no ADC) | `java.io.UncheckedIOException` |
| `GCP_PROJECT_ID` unset, no-arg constructor | `IllegalStateException` |
| Null `name`, `version`, `projectId`, or `client` | `NullPointerException` |

Implementations never log the returned secret value, even at DEBUG.

## Testing

Unit tests mock `com.google.cloud.secretmanager.v1.SecretManagerServiceClient` with Mockito — no real GCP credentials, no network. From the repo root:

```bash
mvn -f data-pipeline-libraries-java/pom.xml -pl data-pipeline-gcp-secrets-java -am clean test
```

Live-cloud integration tests against a real Secret Manager instance are sprint-2+ scope.
