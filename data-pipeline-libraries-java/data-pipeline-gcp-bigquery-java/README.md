# data-pipeline-gcp-bigquery (Java)

Google Cloud BigQuery adapter for the Culvert data pipeline framework, JVM edition. Provides `BigQueryWarehouse`, the GCP implementation of the cloud-neutral [`Warehouse`](../data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Warehouse.java) contract defined in `data-pipeline-core-java`.

Sibling of the Python adapter that will lift out of `gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/clients/bigquery_client.py` in a later stage.

## Status

**Version 0.1.0 — Sprint 1 deliverable** (issue [#6](https://github.com/enrichmeai/gcp-pipeline-reference/issues/6)). Wave 2 of sprint-1; follows the `data-pipeline-gcp-secrets-java` pilot pattern (BOM in module-level `dependencyManagement`, parent stays cloud-neutral).

## Install (Maven)

```xml
<dependency>
    <groupId>com.enrichmeai.culvert</groupId>
    <artifactId>data-pipeline-gcp-bigquery</artifactId>
    <version>0.1.0</version>
</dependency>
```

Pulls in `data-pipeline-core` (the contracts) plus `google-cloud-bigquery` (version managed by the Google Cloud `libraries-bom`).

## Contract satisfied

[`com.enrichmeai.culvert.contracts.Warehouse`](../data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Warehouse.java):

```java
public interface Warehouse {
    Iterator<Map<String, Object>> query(String sql, Map<String, Object> params);
    void execute(String sql, Map<String, Object> params);
    long loadFromUri(String uri, String targetTable, EntitySchema schema);
    long merge(String sourceTable, String targetTable, List<String> keys);
    long copy(String sourceTable, String targetTable);
    boolean tableExists(String fqtn);
}
```

`BigQueryWarehouse` translates each operation into a BigQuery job:

| Contract method | BigQuery realisation |
|---|---|
| `query` | `client.query(QueryJobConfiguration)` returning a `TableResult`; rows streamed lazily via `iterateAll()` |
| `execute` | Same as `query`; returned `TableResult` is discarded |
| `loadFromUri` | `LoadJobConfiguration` from a `gs://` URI; returns `LoadStatistics.outputRows` |
| `merge` | Throws `UnsupportedOperationException` in sprint-1. BigQuery `MERGE` needs explicit non-key columns in `WHEN MATCHED THEN UPDATE SET ...` (no `SET t.* = s.*` shorthand); generating them requires a source-schema lookup that's deferred to sprint-4. Use `execute(String, Map)` with an explicit MERGE statement until then. |
| `copy` | `CopyJobConfiguration`; returns the target table's row count after the copy completes |
| `tableExists` | `client.getTable(TableId)`; returns `false` on `null` or a 404 `BigQueryException` |

Fully-qualified table names accept either `project.dataset.table` or `dataset.table` (the project component defaults to the warehouse's configured `projectId`).

Named parameters in `query` / `execute` accept `String`, `Long`, `Integer`, `Double`, `Float`, and `Boolean`. Anything else throws `IllegalArgumentException`.

## Construction

One public constructor — explicit `projectId` plus a pre-built `BigQuery` client:

```java
// Production
BigQuery client = BigQueryOptions.newBuilder()
        .setProjectId("my-gcp-project")
        .setLocation("EU")
        .build()
        .getService();
Warehouse warehouse = new BigQueryWarehouse("my-gcp-project", client);

// Tests / custom credentials — pass a Mockito mock or a client built with
// non-default credentials.
Warehouse warehouse = new BigQueryWarehouse("my-gcp-project", mockClient);
```

The wrapped client is closed when you call `warehouse.close()`. The class implements `AutoCloseable` so it works in try-with-resources:

```java
try (BigQueryWarehouse w = new BigQueryWarehouse("my-project", client)) {
    Iterator<Map<String, Object>> rows = w.query(
            "SELECT id, name FROM ds.customers WHERE id = @id",
            Map.of("id", 42L));
    while (rows.hasNext()) {
        System.out.println(rows.next());
    }
}
```

### No no-arg constructor (yet)

Unlike `SecretManagerProvider`, `BigQueryWarehouse` does **not** expose a no-arg constructor. A real BigQuery client needs project + location + credentials at construction time, which exceeds the pilot's "no-arg only if <=2 env vars of state" rule. The `META-INF/services` file is pre-registered, but direct `ServiceLoader.load(Warehouse.class).findFirst()` will fail with `ServiceConfigurationError` until sprint-4 introduces a config-driven constructor. Wire it explicitly until then.

## Environment variables

| Variable | Used by | Required? |
|---|---|---|
| `GCP_PROJECT` | The sprint-4 auto-config no-arg constructor (planned) | Not yet — no consumer reads it in this version |
| `GCP_LOCATION` | The sprint-4 auto-config no-arg constructor (planned) | Not yet — set `BigQueryOptions.setLocation(...)` on the injected client instead |
| `GOOGLE_APPLICATION_CREDENTIALS` | The underlying `BigQuery` client (standard ADC) | Only when not running on a GCP-managed identity |

## ServiceLoader registration

`src/main/resources/META-INF/services/com.enrichmeai.culvert.contracts.Warehouse` lists `com.enrichmeai.culvert.gcp.bigquery.BigQueryWarehouse` so a future sprint-4 auto-config wiring can resolve the implementation by contract.

```java
// Reserved for sprint-4 — will throw ServiceConfigurationError today.
ServiceLoader.load(Warehouse.class).findFirst()
    .orElseThrow(() -> new IllegalStateException("no Warehouse on classpath"));
```

## Errors

| Cause | Thrown |
|---|---|
| Job completes with a status error | `com.google.cloud.bigquery.BigQueryException` |
| 404 on `tableExists` | `false` (not thrown) |
| Job disappears before completion | `java.util.NoSuchElementException` |
| `query` / `execute` thread interrupted | `RuntimeException` (interrupt flag restored) |
| Empty `keys` to `merge` | `IllegalArgumentException` |
| Unsupported parameter type | `IllegalArgumentException` |
| Null `sql`, `fqtn`, `client`, or `projectId` | `NullPointerException` |

## Sibling adapters (same module)

`data-pipeline-gcp-bigquery-java` is intentionally a multi-contract module — three GCP services share the same Google Cloud SDK family and `libraries-bom` pin, so they ship together. Sprint-1 lands `BigQueryWarehouse` and pre-wires the module's POM; the other two contracts ship as follow-up issues that only add classes:

- [#8](https://github.com/enrichmeai/gcp-pipeline-reference/issues/8) — `JobControlRepository` (BigQuery-backed job-control table)
- [#9](https://github.com/enrichmeai/gcp-pipeline-reference/issues/9) — `FinOpsSink` (BigQuery-backed cost/observability sink)

Both sibling issues will share the `pom.xml` defined here; they should only add `.java` sources and (where relevant) extra `META-INF/services` registrations.

## Testing

Unit tests mock `com.google.cloud.bigquery.BigQuery` with Mockito — no real GCP credentials, no network. From the parent libraries directory:

```bash
cd data-pipeline-libraries-java && mvn -pl data-pipeline-gcp-bigquery-java -am clean test
# or equivalently
mvn -f data-pipeline-libraries-java/pom.xml -pl data-pipeline-gcp-bigquery-java -am clean test
```

Live-cloud integration tests against a real BigQuery dataset (or the BigQuery emulator) are sprint-2+ scope.
