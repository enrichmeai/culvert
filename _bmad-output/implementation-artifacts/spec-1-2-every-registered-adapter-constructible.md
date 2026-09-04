---
title: 'Every registered adapter must be constructible'
type: 'bugfix'
created: '2026-09-04'
status: 'in-review'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Seven classes are listed in `META-INF/services/com.enrichmeai.culvert.contracts.*`
with no public no-arg constructor, so `ServiceLoader` raises `ServiceConfigurationError` on
each — the throw `AutoConfig` swallowed until Story 1.1. Four of GCP's cloud-bound contracts
(`Source`, `Sink`, `Pipeline`, `FinOpsSink`) were therefore unreachable through auto-config,
and nothing anywhere said so. A registration is a public promise; these seven broke it.

**Approach:** Decide per adapter, not by rule. Give an adapter a working no-arg constructor
**only if** it can honestly self-configure from the environment; otherwise withdraw the
registration and record the reason in the service file, as Story 1.5 did for
`DataCatalogLineageEmitter`. Then add a reactor-wide build gate so the eighth cannot happen.

## Boundaries & Constraints

**Always:** the reason for a withdrawal lives in the service file itself (AC 3), which stays
as a comment-only file rather than being deleted. The audit is structural — it asserts a
provider constructor *exists* and never invokes one.

**Never:** do not "fix" `AthenaWarehouse` or `DynamoDbJobControlRepository`. Their no-arg
constructors work and *throw* on a `CULVERT_CLOUD` mismatch; that is the gate working as
designed, and Story 1.1 made it visible rather than swallowed. Do not invent environment
variables no deployment sets in order to manufacture a green.

**Ask First:** none reachable — non-interactive session; decisions are in Design Notes.

## I/O & Edge-Case Matrix

| Case | Expectation |
|---|---|
| Adapter with a working no-arg ctor that throws on a cloud mismatch | Passes the audit. Structural check only. |
| Adapter with no no-arg ctor | Fails the audit, naming the file, the class and both remedies. |
| Registered class not on the audit's classpath | Fails, telling the author to add the module as a test dependency. |
| Registered class that does not implement its contract | Fails, naming the contract. |
| Constructors unresolvable (a parameter type missing from the audit classpath) | Fails as UNVERIFIABLE — never a silent pass. |
| Comment-only service file (a withdrawal) | Parses as zero registrations. |
| Repo root not locatable | Fails loudly rather than walking nothing and passing. |

## Code Map

- `.../gcp-bigquery-java/.../BigQueryFinOpsSink.java` -- AC 2; new no-arg ctor at the old
  sprint-4 TODO (`:86-89` before the change).
- `.../gcp-bigquery-java/.../BigQueryDefaults.java` -- new `finOpsDataset()` (required, no
  default) and `finOpsTable()` (defaults to `BigQueryFinOpsSink.DEFAULT_TABLE`).
- `.../gcp-bigquery-java/src/test/.../BigQueryWorkerAutoConfigTest.java` -- 5 new tests,
  mirroring the existing Warehouse/JobControl pattern at `:27-52`.
- Six service files emptied to comment-only, each carrying its reasoning: `gcp-pubsub`
  (`Source`, `Sink`), `gcp-dataflow` (`Pipeline`), `aws-sqs` (`Source`, `Sink`),
  `azure-blob` (`BlobStore`).
- `data-pipeline-registration-audit-java/` -- NEW module; build gate, publishes nothing.
- `pom.xml:25,78`, `README.md:32,99`, `.github/workflows/ci.yml:6,86,114,130,134,174` --
  the 18 -> 19 module count and the two enumerated module lists CI diffs against the pom.

## Tasks & Acceptance

**Execution:**
- [x] `BigQueryFinOpsSink` no-arg ctor + `BigQueryDefaults.finOpsDataset()/finOpsTable()` -- AC 2.
- [x] Six registrations withdrawn, each with its reason in the service file -- AC 3, AC 5.
- [x] `ServiceRegistrationAuditTest` walks every shipped service file in the reactor -- AC 1, AC 4.
- [x] New module wired into the reactor + both CI module lists + the three module counts.
- [x] `README.md` auto-config claim corrected: it said `discover()` "finds every installed
      implementation", which was false before this story and is now precise about which
      contracts register and why.

**Acceptance Criteria:**
- Given any shipped `META-INF/services/com.enrichmeai.culvert.contracts.*` entry, when the
  audit runs, then the class is public, concrete, implements its contract, and exposes a
  public no-arg constructor (or a static `provider()`).
- Given a class registered but absent from the audit's classpath, when the audit runs, then
  it fails telling the author to add the owning module as a test dependency.
- Given `gcp.project` and `gcp.finOpsDataset` set, when `new BigQueryFinOpsSink()` runs,
  then it constructs.
- Given no `FINOPS_DATASET`, when `new BigQueryFinOpsSink()` runs, then it throws
  `IllegalStateException` naming the variable.

## Design Notes

**Why six removals and one fix.** All seven were equally broken; removal loses no capability,
because none of them could ever be constructed by `ServiceLoader` in the first place. The
split falls out of one question — can this adapter honestly self-configure from the
environment?

`FinOpsSink` can: one cost sink per deployment, which is exactly the shape
`AutoConfig.finOpsSink()` (`AutoConfig.java:200-202`) assumes. `Source` and `Sink` cannot:
`AutoConfig` deliberately has no singular `source()`/`sink()` accessor, only the plural lists
(`AutoConfig.java:264-270`), because a subscription or queue URL is per-stage wiring — a
self-configuring `PubSubSource` would pick one subscription from the environment and be wrong
for every pipeline with two inputs. `Pipeline` cannot even in principle: the contract *is*
name + stages (`Pipeline.java:18-21`), and no environment variable supplies a
`List<PipelineStage>`.

**Azure is the strongest removal, and not for the reason the story gives.** Seven of eight
methods throwing (`AzureBlobStore.java:51-84`) is sufficient. But the decisive one is that
*adding* a no-arg ctor would break working classpaths: since Story 1.1, `blobStore()` fails
fast on more than one available provider without a selector (`AutoConfig.java:357-362`), and
`S3BlobStore` opts out via `ProviderAvailability` (`S3BlobStore.java:108`) while Azure would
not. Today's silent no-op would become a hard `IllegalStateException` for anyone carrying both
the GCP and Azure jars.

**`FINOPS_DATASET` has no default, deliberately.** Its siblings default because
`job_control.pipeline_jobs` is a name this repo provisions and agrees on. The FinOps dataset
is not: docs and the reference deployment say `finops_dataset.cost_metrics`
(`docs/SLO_ALERTING.md:111`, `docs/RUNBOOK.md:254`,
`deployments/reference-e2e-gcp/README.md:422`) while the Grafana chart queries
`job_control.finops_usage` (`grafana-dashboards-configmap.yaml:722`), and no Terraform creates
either. Guessing would put cost rows where nobody reads them. `FINOPS_TABLE` *does* default —
`cost_metrics` is settled on both language sides (`BigQueryFinOpsSink.java:60`, Python
`finops_sink.py:26`).

**Why a new module.** No existing module sees every adapter, and making one do so would inflict
a dozen cloud SDKs on a published artifact. It depends on the modules that carry registrations
rather than on every adapter: `gcp-dataflow` in particular drags Beam's GCP IO closure onto the
classpath at versions no module has built with, which does not resolve under `mvn -o`. The list
staying correct is not left to memory — an unlisted module fails the audit with instructions.

**Scope decision recorded (AC 5).** The AWS/Azure three are removals, not fixes. Each needs
per-stage state (`SqsSource.java:86`, `SqsSink.java:71`) or is a skeleton, so AC 5's "leave the
registration removed and flag it" branch applies rather than its "genuine no-arg constructor"
branch.

**Not addressed, flagged:** `AthenaWarehouse` and `DynamoDbJobControlRepository` still gate by
throwing rather than by `ProviderAvailability`. Story 1.1 flagged that migration as separate
follow-up and this story does not change it; the audit passes them because their constructors
exist, which is the correct structural verdict.

**Docs deliberately left unchanged (DoD 5).** `docs/framework-evolution/10-architecture.md:114`
and `CHANGELOG.md:63` both list adapters that *exist* (`BlobStore | GcsBlobStore, S3BlobStore,
AzureBlobStore`), not adapters that are auto-discoverable. Withdrawing a registration does not
delete a class, so both stay true and neither was edited. Worth noting for whoever reads that
table next: `10-architecture.md` was already stale before this story — it shows
`LineageEmitter | DataCatalogLineageEmitter | OK` although Story 1.5 removed that registration,
and `AuditEventPublisher | — | planned` although `BigQueryAuditEventPublisher` exists and
registers. It reads as a Sprint-14-era snapshot ("After Sprint 14, all 16 contract
interfaces..."), and CLAUDE.md names 01-08 as the canonical plan, so it is not this story's to
rewrite — but it should not be read as current truth.

**`reference-e2e-gcp` — analysed, not merely assumed.** That module has `gcp-bigquery` at
compile scope and registers `RecordingFinOpsSink` in its test resources, so making
`BigQueryFinOpsSink` constructable creates a second `FinOpsSink` candidate there — and since
Story 1.1, `finOpsSink()` fails fast on two available providers with no selector
(`AutoConfig.java:357-362`). Measured: the module runs 16 tests (1 skipped), byte-identical
before and after. To rule out a lucky pass I re-ran `ReferenceE2ECostTest` with
`-DargLine="-Dculvert.finopssink.provider=NoSuchProviderAnywhere"`, a selector that matches
nothing and therefore *must* throw wherever `finOpsSink()` is reached — it still passed, so
that path is not exercised by this module's surefire tests (they build their context with
`DefaultRuntimeContext.builder`, not `fromAutoConfig`).

*Flagged for the architect:* the risk is real on paths that genuinely rebuild the transient
registry — `DefaultRuntimeContext.registry()` (`:133-147`) calls `fromAutoConfig` -> 
`finOpsSink()` — i.e. a real Dataflow worker, or `mvn -P it verify`. It only fires where
`FINOPS_DATASET` is set *and* a project resolves, since otherwise the constructor throws and
Story 1.1 records it as a `DiscoveryFailure` rather than a candidate. This is the same
"known consequence, accepted" shape Story 1.1 recorded for the two observability hooks.
I did not run `mvn -P it verify` (Docker; architect-run).

**Untestable offline, flagged:** `maven.deploy.skip` is honoured by maven-deploy-plugin, but
the parent's `release` profile wires `central-publishing-maven-plugin` with
`<extensions>true</extensions>`, which has its own `skipPublishing` switch. Whether the audit
module is excluded from a Central publish should be confirmed on the next `mvn -P release`
dry run rather than assumed from `maven.deploy.skip` alone.

**Story text nit:** Story 1.2's acceptance criteria are misnumbered — "5. Scope" appears before
"4. The test fails if a future module...". Cosmetic; both were implemented.

## Verification

**Commands:**
- `mvn -o -pl data-pipeline-libraries-java -amd test` -- BUILD SUCCESS, 23 modules.

**Measured baseline** (this worktree at `df6d460`, before any change): BUILD SUCCESS, 22
modules, core 119. Note the epic preamble's "core 123 passed" is stale — it was measured at
`998ac7f`, before Stories 1.1/1.3/1.5 merged.

**After:** every module identical to baseline except `gcp-bigquery` 137 -> 142 (the 5 new
FinOps tests) and the new `data-pipeline-registration-audit` at 6.

**Negative test performed** (registrations temporarily added, then reverted): a class with no
no-arg ctor, and a class name that does not resolve, each failed the audit with its own
actionable message. The gate fails when it should.
