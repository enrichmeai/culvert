# Secret Manager integration tests — why no emulator

Sprint-10 (T10.5). This note explains why `data-pipeline-gcp-secrets-java` is
the one GCP adapter module whose integration test does **not** start a
Testcontainers emulator, and how integration is validated instead.

## There is no Secret Manager emulator

The other GCP adapter modules each have a local emulator they can drive under
the parent's `it` profile:

| Module | Adapter | Emulator |
| --- | --- | --- |
| `data-pipeline-gcp-bigquery-java` | `BigQueryWarehouse` | `goccy/bigquery-emulator` (via `BigQueryEmulatorContainer`) |
| `data-pipeline-gcp-gcs-java` | `GcsBlobStore` | `fsouza/fake-gcs-server` (via `FakeGcsServerContainer`) |
| `data-pipeline-gcp-pubsub-java` | Pub/Sub adapter | `gcloud` SDK emulator (via Testcontainers' `PubSubEmulatorContainer`) |

**Google Cloud Secret Manager has no public emulator.** Google does not ship a
Secret Manager emulator in the `gcloud` SDK, and there is no community container
image that serves the Secret Manager gRPC API offline the way
`fake-gcs-server` / `bigquery-emulator` do. The only ways to hit a real Secret
Manager endpoint are the live GCP service (needs credentials, network, and a
real project — not allowed in CI) or a hand-rolled gRPC stub server, which is
far heavier than this adapter warrants.

So there is **no `@Testcontainers` / `@Container`** in this module's IT, and no
container starts when the `it` profile runs it.

## How integration is validated instead

`SecretManagerProviderIT` exercises the **real** `SecretManagerProvider` against
an **in-process stateful fake** of `SecretManagerServiceClient`:

- The fake is a Mockito mock of `SecretManagerServiceClient` backed by an
  in-memory `Map` keyed by `"{secret}/{version}"`. It behaves like a tiny
  Secret Manager store that holds state across calls (seed once, read many),
  rather than a one-shot canned stub.
- A request for a secret/version that is not in the map throws the real GCP
  `com.google.api.gax.rpc.NotFoundException` — exactly what the live service
  raises — so the adapter's exception-adaptation path is exercised, not faked.
- The fake is injected through the production
  `SecretManagerProvider(String projectId, SecretManagerServiceClient client)`
  constructor, so the adapter's real code path runs end-to-end: build the
  `SecretVersionName`, call `accessSecretVersion`, decode the UTF-8 payload, and
  adapt `NotFoundException` -> the contract's `NoSuchElementException`.

This complements `SecretManagerProviderTest` (which stubs one canned response
per test and asserts on the captured request). The IT seeds a populated store
and drives several contract operations against the same backing map:

- multi-secret round-trip — distinct names resolve to distinct values;
- single-arg `get` defaults to the `"latest"` version;
- an explicit version resolves distinctly from `latest`;
- a missing secret surfaces as `NoSuchElementException`;
- `close()` delegates to the wrapped client.

The IT needs **no Docker daemon and no network**, but is still named
`*IT.java` so failsafe picks it up under the `it` profile (and surefire ignores
it under `mvn test`), keeping it consistent with the rest of the sprint-10 IT
suite.

## About the Testcontainers dependencies in this module's POM

`pom.xml` declares `data-pipeline-it-support`, `testcontainers`, and
`testcontainers:junit-jupiter` in test scope for **consistency** with the other
adapter modules (and per the sprint ticket). They are not used by
`SecretManagerProviderIT` — nothing here starts a container. Versions are
managed by the `testcontainers-bom` in the parent POM, so none are pinned here.
The `gcloud` Testcontainers module is deliberately **not** added: it only
provides `PubSubEmulatorContainer`, which this module has no use for.

`maven-compiler-plugin` is configured with `<proc>none</proc>`: pulling
`data-pipeline-it-support` (compile-scope `google-cloud-bigquery`) onto the test
classpath drags in an annotation processor that claims none of our JUnit/Mockito
annotations, which under the parent's `-Xlint:all -Werror` would otherwise fail
the build. This mirrors `data-pipeline-gcp-gcs-java` and
`data-pipeline-it-support-java`.
