---
name: 'GCP defect remediation'
type: epics
status: ready
created: '2026-09-04'
source: '_bmad-output/planning-artifacts/architecture/architecture-culvert-2026-09-04/ARCHITECTURE-SPINE.md'
sprint: sprint-23
---

# Epic 1 — GCP defect remediation

**Why now:** Joseph's call, 2026-09-04 — fix what is broken on GCP before building Azure.
Every defect below was found while building the multi-cloud parity matrix from
`META-INF/services` rather than from the docs, and every one was verified in the code
before being written down. All five are live on `main` and silent: none raises an error.

**Baseline (established 2026-09-04, commit `998ac7f`):** the reactor is green.
`mvn -o -pl data-pipeline-libraries -amd test` → BUILD SUCCESS, 22 modules, core 123 passed.
Any agent reporting "tests fail" must show that its own change caused it.

**Governing invariants:** AD-2, AD-6, AD-14, AD-17 in the architecture spine.

---

## Story 1.1 — AutoConfig must not swallow discovery failures  `[AD-14]`

**As** an operator running a Culvert pipeline,
**I want** adapter discovery to fail loudly and select explicitly,
**so that** a jar on the classpath cannot silently change or disable which adapter runs.

**The defect.** `AutoConfig.loadServiceList` wraps the whole `ServiceLoader` iteration in
`catch (Throwable ignored)` (`AutoConfig.java:227`), so one provider whose constructor throws
truncates the provider list and everything after it is lost. `first()` then returns
`impls.get(0)` (`AutoConfig.java:253`) — classpath order decides. `S3BlobStore`'s
`CULVERT_CLOUD` gate throws exactly that way (`S3BlobStore.java:90`), so an AWS jar on the
classpath can disable a GCP adapter with no error. The code's own comment calls this a
"sprint-4 limitation" that "sprint-5 config-driven instantiation will replace"; it is Sprint 23.

**Acceptance criteria**
1. Per-provider failures are captured and reported (logged at WARN with the provider class and cause), never discarded; one failing provider does not hide the others.
2. Where more than one provider implements a contract, an explicit selector (`CULVERT_<CONTRACT>_PROVIDER`) chooses; an ambiguous set with no selector fails fast with a message naming the candidates.
3. A single provider with no selector continues to resolve exactly as today — no behaviour change for the common case.
4. Opting out is "return absent", not "throw": `S3BlobStore`'s `CULVERT_CLOUD` gate is migrated to the non-throwing form.
5. `AutoConfigTest` covers: one throwing provider does not hide a good one; ambiguity without a selector fails; the selector picks correctly.

**Files:** `data-pipeline-core-java/.../autoconfig/AutoConfig.java`, `data-pipeline-aws-s3-java/.../S3BlobStore.java`
**Verify:** `mvn -o -pl data-pipeline-libraries-java/data-pipeline-core-java,data-pipeline-libraries-java/data-pipeline-aws-s3-java -am test`

---

## Story 1.2 — Every registered adapter must be constructible  `[AD-2]`

**As** a developer adding an adapter,
**I want** a registration that ServiceLoader cannot construct to fail the build,
**so that** an adapter cannot advertise itself and then silently resolve to a no-op.

**The defect — full audit, verified 2026-09-04 across every registration in the reactor.**
Seven registered classes have no no-arg constructor, so `ServiceLoader` raises
`ServiceConfigurationError` on each — precisely the throw Story 1.1 was swallowing:

| Cloud | Class | Contract |
|---|---|---|
| GCP | `PubSubSource` | `Source` |
| GCP | `PubSubSink` | `Sink` |
| GCP | `DataflowPipeline` | `Pipeline` |
| GCP | `BigQueryFinOpsSink` | `FinOpsSink` |
| AWS | `SqsSource` | `Source` |
| AWS | `SqsSink` | `Sink` |
| Azure | `AzureBlobStore` | `BlobStore` |

Four of GCP's eleven cloud-bound contracts have therefore been unreachable through
auto-config. `DataCatalogLineageEmitter` was an eighth; Story 1.5 removed its registration.

**Not defects, do not "fix" them:** `AthenaWarehouse` and `DynamoDbJobControlRepository`
have working no-arg constructors that *throw* when `CULVERT_CLOUD` does not select their
family. That is the gate working as designed, and Story 1.1 made it visible rather than
swallowed. Leave them; Story 1.1 flagged migrating them to the non-throwing `isAvailable()`
form as separate follow-up work.

**Acceptance criteria**
1. A test walks **every** `META-INF/services/com.enrichmeai.culvert.contracts.*` file in the reactor and asserts each listed class is instantiable via `ServiceLoader`.
2. `BigQueryFinOpsSink` gains a working no-arg constructor resolving config from the environment, matching the convention `BigQueryWarehouse` already documents in its service file.
3. Per adapter, choose deliberately: give it a working no-arg constructor **if** it can honestly self-configure, **or** remove the registration if it cannot or should not be auto-discovered. Story 1.5 set the precedent — it removed `DataCatalogLineageEmitter` rather than make discovery succeed against a dead API. `AzureBlobStore` is the obvious candidate for removal: seven of its eight methods throw `UnsupportedOperationException`, so a discoverable skeleton is worse than none. Record the reason in the service file itself, as Story 1.5 did.
5. **Scope:** the four GCP entries are this sprint's target (Joseph's "GCP first"). Fix the AWS and Azure three as well **only** if it is a genuine no-arg constructor each; if either needs real design thought, leave the registration removed or the entry allowlisted with a comment, and flag it — do not invent configuration.
4. The test fails if a future module registers a class ServiceLoader cannot construct.

**Depends on:** Stories 1.1 (discovery reporting, merged) and 1.5 (owns `DataCatalogLineageEmitter`, merged). Both are in `sprint-23` — branch from it, not `main`.
**Verify:** `mvn -o -pl data-pipeline-libraries-java -amd test`

---

## Story 1.3 — BigQuery job control must be conditional  `[AD-6]`

**As** a data engineer re-running a failed pipeline,
**I want** every job-control transition to be compare-and-set,
**so that** a re-run cannot duplicate data and two writers cannot clobber a status.

**The defect.** `BigQueryJobControlRepository` inserts unconditionally and runs every status
transition as `UPDATE … WHERE run_id`, discarding the result — `runUpdate`'s javadoc says
"we only care that execution succeeded". So a transition against a row in the wrong state
passes silently, and one against **no row at all** also passes. Open issue #99 (`cleanupPartialLoad`
reading affected rows from `getTotalRows()`) is the same root cause.

**Acceptance criteria**
1. `createJob` is insert-if-absent and fails if the `runId` already exists.
2. Every status transition asserts the expected prior state and fails when it does not hold — not merely that the row exists.
3. DML affected-row counts are read correctly, closing issue #99; `cleanupPartialLoad` returns a truthful count.
4. ~~`cleanupPartialLoad`'s javadoc states it removes job-control records only~~ — **this AC was wrong and was corrected during the sprint.** `cleanupPartialLoad` deletes from the caller-supplied **warehouse** table (`BigQueryJobControlRepository.java:392`; `RetryOrchestrator` passes `job.targetTable()`). The javadoc states that truthfully instead. The real defect AD-17 was reaching for is that a *warehouse* operation lives on the *job-control* port — invisible on GCP where both are BigQuery, but on AWS it asks a DynamoDB adapter to delete rows from Athena/S3, which it cannot reach.
5. Tests cover: duplicate `createJob` rejected; a transition from the wrong prior state rejected; a transition against a missing row rejected.

**Files:** `data-pipeline-gcp-bigquery-java/.../BigQueryJobControlRepository.java`
**Verify:** `mvn -o -pl data-pipeline-libraries-java/data-pipeline-gcp-bigquery-java -am test`

---

## Story 1.4 — Emit `contract_version` and honour the audit schema

**As** a consumer of Culvert's audit records,
**I want** every emitted record to match the published wire contract,
**so that** a non-Culvert reader can parse them as `docs/CONTRACT.md` promises.

**The defect.** `docs/CONTRACT.md` §2 requires every emitted record to carry
`contract_version`. The string appears in **zero** source files repo-wide.
`BigQueryAuditEventPublisher` shares only `run_id` with the contract's audit schema and
adds fields of its own.

**Acceptance criteria**
1. `contract_version` is emitted on every contract record, sourced from one constant in `data-pipeline-core`, not duplicated per adapter.
2. `BigQueryAuditEventPublisher`'s record is reconciled with `docs/CONTRACT.md` — **either** the code changes to match the doc, **or** the doc changes to match the code and the version is bumped per its own policy. Whichever you choose, say which and why in the PR.
3. A test asserts the field is present and correctly valued.
4. If the divergence is larger than it looks, **flag and stop** rather than inventing a mapping.

**Files:** `data-pipeline-core-java/.../contracts/`, `data-pipeline-gcp-bigquery-java/.../BigQueryAuditEventPublisher.java`, `docs/CONTRACT.md`
**Verify:** `mvn -o -pl data-pipeline-libraries-java/data-pipeline-gcp-bigquery-java -am test`

---

## Story 1.5 — GCP lineage writes to an API that shut down in June

**As** a data governance owner,
**I want** lineage actually emitted,
**so that** the framework's lineage claim is true.

**The defect.** `DataCatalogLineageEmitter` writes `com.google.cloud.datacatalog.v1` Tags.
Data Catalog's phased shutdown began **2026-06-01**; it was superseded by Knowledge Catalog
(the Dataplex API), and lineage specifically now has its own **Data Lineage API**
(`datalineage.googleapis.com`, Java client `google-cloud-datalineage`, with an
OpenLineage-compatible producer library). The adapter is also unconstructible (Story 1.2),
so it currently resolves to `NoOpLineageEmitter` — it has emitted nothing for months, silently.

**Acceptance criteria**
1. **First, empirically:** does `datacatalog.googleapis.com` still answer in `joseph-antony-aruja`? Five minutes; record the answer in the PR. It sets urgency, not direction.
2. `LineageEmitter` is reimplemented against the Data Lineage API rather than Data Catalog tags.
3. It exposes a constructible no-arg entry point so discovery resolves it (Story 1.2's test must pass on it).
4. The Python `DataCatalogLineageEmitter`, if it has the same fault, is fixed or removed — do not leave one language correct and the other lying.
5. If the new client is not available offline in `~/.m2`, **stop and report** rather than half-migrating. A flagged blocker is correct; a silent partial migration is not.

**Files:** `data-pipeline-gcp-observability-java/.../DataCatalogLineageEmitter.java` (+ rename), its test, its service file
**Verify:** `mvn -o -pl data-pipeline-libraries-java/data-pipeline-gcp-observability-java -am test`

---

## Story 1.6 — The BigQuery audit sink has been writing to a table that does not exist

**Found while working Story 1.4. Not dispatched — new scope goes in the backlog, not mid-sprint.**

**As** an operator relying on the audit trail,
**I want** audit writes to reach a real table and fail loudly when they don't,
**so that** "we have an audit trail" is a true statement.

**The defect.** `BigQueryAuditEventPublisher` defaults to dataset `audit`, table `audit_events`
(`BigQueryAuditEventPublisher.java:93,:96`). The repo provisions neither: infrastructure creates
`job_control.audit_trail` (`scripts/gcp/03_create_infrastructure.sh:180`). Every write therefore
fails — and the failure is caught and logged at WARN with the message *"audit error swallowed"*
(`BigQueryAuditEventPublisher.java:238-243`). So GCP audit has been silently dark, in the same
shape as the lineage emitter in Story 1.5: an adapter that advertises a capability, emits
nothing, and never raises.

**Acceptance criteria**
1. Publisher and provisioned infrastructure agree on one dataset and table — decide which is canonical and change the other.
2. A write failure is no longer swallowed unconditionally; audit loss is surfaced (fail fast, or a metric plus an ERROR, per an explicit call recorded in the PR).
3. A test asserts the configured target matches what `03_create_infrastructure.sh` and the Terraform provision.
4. `auditFailures` is exposed somewhere an operator can actually see it.

**Depends on:** Story 1.4's reconciliation decision, since it may change the record shape.
