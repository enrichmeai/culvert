---
title: 'AutoConfig must not swallow discovery failures'
type: 'bugfix'
created: '2026-09-04'
status: 'in-review'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `AutoConfig.loadServiceList` wraps the whole `ServiceLoader` iteration in
`catch (Throwable ignored)` (`AutoConfig.java:227`, and the same at `:246` in
`loadServiceListRaw`), so one provider whose construction throws truncates the list and
everything after it is lost. `first()` then returns `impls.get(0)` (`AutoConfig.java:253`),
so classpath order picks the adapter. `S3BlobStore`'s `CULVERT_CLOUD` gate throws exactly
that way (`S3BlobStore.java:89`), so an AWS jar can silently disable a GCP adapter.

**Approach:** Iterate `ServiceLoader.stream()` and catch **per provider**, recording each
failure (provider class + cause) and logging it at WARN. Filter the loaded list through a
non-throwing opt-out (`ProviderAvailability.isAvailable()`) **before** deciding
zero/one/many, then resolve: none → empty; one → that one (unchanged); many → require an
explicit `CULVERT_<CONTRACT>_PROVIDER` selector and fail fast naming the candidates and
the variable to set. Migrate `S3BlobStore`'s gate from throw to "report unavailable".

## Boundaries & Constraints

**Always:** availability filtering runs before the ambiguity check, so a gated adapter
never causes a spurious ambiguity failure. Selector resolution reads env var first, then
the lower-cased system property (mirrors `S3BlobStore.java:84-87`) so tests can drive it.
`IllegalStateException` is the repo's convention for selector failures
(`S3BlobStore.java:89`, `BigQueryDefaults.java:50`).

**Ask First:** none reachable — this session is non-interactive; decisions are recorded in
Design Notes instead of halting.

**Never:** do not add the availability interface to `com.enrichmeai.culvert.contracts` —
"16 contract interfaces" is hard-coded in `CHANGELOG.md:89`, `README.md:5/103/109`,
`docs/framework-evolution/{02,09,10,13}-*.md`; a 17th would falsify all of them. Do not
migrate the sibling gates (`AthenaDefaults.java:26`,
`DynamoDbJobControlRepository.java:180`, `BigQueryDefaults.java:50`) — out of story scope;
after this change their throws are *reported*, not swallowed. Do not run `mvn -P it verify`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Single provider | one entry for a contract | resolves to it — unchanged (AC 3) | N/A |
| Throwing provider listed first | throwing + good entry | good one resolves; failure recorded + WARN | captured in `failures()` |
| Missing no-arg ctor | class with no public no-arg ctor | other providers still load | `ServiceConfigurationError` captured |
| Ambiguity, no selector | two available providers | `IllegalStateException` naming both + the selector var | fail fast |
| Ambiguity + selector | selector = one candidate's FQCN | that provider resolves | N/A |
| Selector names a stranger | selector = class not discovered | `IllegalStateException` listing candidates | never falls back to index 0 |
| Gated-out provider | `CULVERT_CLOUD` != aws | `S3BlobStore()` constructs, reports unavailable | no throw (AC 4) |

</frozen-after-approval>

## Code Map

- `data-pipeline-core-java/.../autoconfig/AutoConfig.java` -- the defect; both load helpers + `first()`.
- `data-pipeline-core-java/.../autoconfig/ProviderAvailability.java` -- NEW; non-throwing opt-out.
- `data-pipeline-core-java/.../autoconfig/DiscoveryFailure.java` -- NEW; captured per-provider failure.
- `data-pipeline-core-java/src/test/.../autoconfig/AutoConfigTest.java` -- AC 5 tests; must keep its
  "core classpath has no providers" assumptions intact (`AutoConfigTest.java:21-31`).
- `data-pipeline-aws-s3-java/.../S3BlobStore.java` -- AC 4; gate at `:83-93`.
- `data-pipeline-aws-s3-java/src/test/.../S3WorkerAutoConfigTest.java` -- asserts the throw at `:13`; must be rewritten.
- `data-pipeline-core-java/README.md:288` and
  `data-pipeline-aws-secrets-java/.../AwsSecretsManagerProvider.java:52` -- state "silently skipped"; now false.

## Tasks & Acceptance

**Execution:**
- [x] `ProviderAvailability.java` -- new interface, `default boolean isAvailable() { return true; }` -- non-throwing opt-out (AC 4).
- [x] `DiscoveryFailure.java` -- new record (contract, providerClass, cause) -- makes AC 1 assertable, not log-scraping.
- [x] `AutoConfig.java` -- per-provider catch via `stream()`; WARN log; `failures()`; availability filter then selector/ambiguity in `first()`; `discover(ClassLoader)` seam -- AC 1, 2, 3.
- [x] `AutoConfigTest.java` -- `@TempDir` + `URLClassLoader` service-file fixtures -- AC 5.
- [x] `S3BlobStore.java` -- lazy client; `isAvailable()`; no-arg ctor no longer throws -- AC 4.
- [x] `S3WorkerAutoConfigTest.java` -- assert non-throwing + unavailable -- AC 4.
- [x] docs -- correct the two "silently skipped" claims.

**Acceptance Criteria:**
- Given a contract with exactly one provider and no selector, when `discover()` runs, then it resolves as it does today.
- Given a provider whose construction throws, when `discover()` runs, then the other providers still load and the failure is in `failures()` and logged at WARN.
- Given two available providers and no selector, when the typed accessor is called, then it throws `IllegalStateException` naming both candidates and the selector variable.
- Given `CULVERT_CLOUD` unset, when `new S3BlobStore()` runs, then it does not throw and `isAvailable()` is false.

## Design Notes

Fixtures are built at test time: write `META-INF/services/<contract>` into a `@TempDir`, then
`new URLClassLoader(new URL[]{tmp.toUri().toURL()}, getClass().getClassLoader())`. Provider
classes resolve through parent delegation (required for `service.isAssignableFrom` to pass);
only the service *file* comes from the child URL. This keeps fixtures out of
`target/test-classes` root so `AutoConfigTest.java:21-31`'s empty-classpath assumption holds.

Loop shape: a throw from `next()` is resumable (the JDK clears its pending error before
throwing), so `continue`; a throw from `hasNext()` does not advance, so record and `break`.

Known consequence, accepted: `gcp-observability` and `aws-cloudwatch` both register
`ObservabilityHook` + `StageMetricsHook` with ungated, never-throwing no-arg ctors, so a
both-families classpath now fails fast in `DefaultRuntimeContext.fromAutoConfig` instead of
taking `impls.get(0)`. That is AC 2 working as designed. No reactor module aggregates both
families, so no existing test is affected.

## Verification

**Commands:**
- `mvn -o -pl data-pipeline-libraries-java/data-pipeline-core-java,data-pipeline-libraries-java/data-pipeline-aws-s3-java -am test` -- expected: BUILD SUCCESS, 0 failures.
- `mvn -o -pl data-pipeline-libraries-java -amd test` -- expected: reactor still green vs the `998ac7f` baseline.
