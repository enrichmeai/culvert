# Changelog

All notable changes to the Culvert data pipeline framework. See [DEV_PROCESS.md](docs/framework-evolution/03-dev-process.md) for the sprint workflow.

## [0.2.0] — unreleased

### Breaking

- **`Warehouse.loadFromUri` now takes a required `LoadOptions`** (Java and
  Python). Before this, the method had no way to express what should happen to
  data already in the target, so each backend chose — and BigQuery applied its
  own default of `WRITE_APPEND`, which meant **re-running the same extract
  silently doubled the data**. There is deliberately no three-argument
  overload: a defaulted disposition is precisely what caused the bug. Pass
  `LoadOptions.append()` to keep the 0.1.x behaviour exactly. Full upgrade
  instructions in [MIGRATION.md](MIGRATION.md).
- Backends that cannot honour a requested disposition must now **throw, naming
  it**, rather than silently downgrading to append. `AthenaWarehouse` refuses
  anything but `APPEND` (no DML on non-Iceberg tables).

### Fixed

- **Nothing writes `job_control.*` outside the port any more.** `fdp-trigger`
  built its own parameterised `INSERT`, and `postgres-cdc-streaming` carried a
  second, unregistered `JobControlRepository` implementation — the shadow model
  the architecture forbids. Both now call the library adapter; the CDC copy is
  deleted.
- **The orchestration job-control reader no longer lets recency bury a
  failure.** `BigQueryJobControl.get_entity_status` collapsed several rows per
  entity with `ROW_NUMBER() … ORDER BY updated_at DESC`, so a later row could
  hide a recorded failure and the dependency checker would let downstream
  FDP/CDP transforms fire over an entity whose load had failed. Collapse is now
  by terminal-state precedence: `failed` outranks everything, `succeeded`
  outranks every non-terminal status, and recency only breaks ties among
  undecided rows. **Consequence:** a retry that succeeds does not clear a failed
  entity — per the contract a retry takes a new `run_id` and the failed run
  stays failed.
- **A reconciliation mismatch can no longer end `SUCCEEDED`.** The ingestion
  runner recorded the mismatch with `markFailed` and then returned normally, so
  the caller went on to `updateStatus(SUCCEEDED)` — an `UPDATE … SET status`
  that overwrote the failure it had just written. A load that did not reconcile
  reported green in the one table an operator would check. Reconciliation now
  runs **before** the target is written, and both it and the post-load
  integrity check are terminal.
- **Re-running an extract leaves one copy of the data, not two** — the load
  deletes the extract date's prior rows before appending.
- **The segment-transform job now reports completion**, so `fdp-trigger`'s
  dedup gate stops blocking every re-run. Nothing had ever written a terminal
  status, so a row stayed `running` forever and suppressed all later runs,
  including retries after a failure.
- **The Maven publish gate hardcoded `0.1.0`** and would have failed every
  future release at its first step.
- The whole-repo build works on JDK 25 as well as 21.

### Added

- **`BigQueryJobControlRepository` (Python)** — the BigQuery adapter for the
  write path of the `JobControlRepository` port (`create_job`, `update_status`,
  `mark_failed`), registered under the `job_control` entry-point slot. The
  Python side previously had *no* implementation of that port, which is why two
  deployments hand-rolled their own `job_control` SQL. Reads stay in
  `data_pipeline_orchestration._job_control` until `pipeline_jobs` becomes a
  projection.
- `MIGRATION.md` — breaking changes and how to upgrade.
- Root aggregator POM: one command builds the libraries and every deployment,
  with a CI guard that no deployment pins a library version other than the
  reactor's.
- `ExecutionSubstrate` / `SubstrateDagRenderer`: the orchestration substrate
  (Composer 2 + GKE pods, Composer 3, or Cloud Run jobs) is selected by
  configuration rather than hardcoded.

## [Unreleased]

### Changed

- **Relicensed from MIT to Apache License 2.0** (2026-08-20). Rationale: an
  explicit patent grant from every contributor (and patent-retaliation
  termination) that enterprise dependency review expects of infrastructure
  code; built-in contribution licensing (§5); an explicit trademark
  reservation (§6); and one license posture across EnrichMeAI projects
  (Cistern is Apache-2.0). All code to date is the copyright of Good Shepherd
  Software Consultancy Limited, so no contributor consent was required.
  Versions already published under MIT (PyPI `culvert` 0.1.0, Maven Central
  `com.enrichmeai.culvert:*` 0.1.0) remain MIT — that grant is irrevocable;
  the next release is the first to ship Apache-2.0 metadata. Added the
  canonical `LICENSE` text and a `NOTICE` file; updated license metadata in
  every `pyproject.toml`, the parent POM, and docs.

## [0.1.0] — 2026-07-15

**RELEASED — both ecosystems. Python: `culvert` 0.1.0 on PyPI (2026-07-11). Java:
`com.enrichmeai.culvert:*` 0.1.0 on Maven Central, 19 artifacts (2026-07-15).**

Culvert's first public release. Every contract interface in the core has at
least one concrete adapter; the Python distribution `culvert` (one wheel with
`[gcp]`/`[orchestration]`/`[transform]`/`[all]` extras, all nine GCP adapters
auto-discoverable) is **live on PyPI** — published only after the reference
deployments ran end-to-end on a real GCP project (Cloud Run + BigQuery +
Pub/Sub, event-driven), which caught eight production-only bugs that every
local/emulator test had passed. The Java reactor is at the same feature bar,
frozen at tag `java-0.1.0` and verified Maven-Central-ready (all 18 modules
carry sources+javadoc; POM metadata complete); its publish to
`com.enrichmeai.culvert:*` is the remaining half of the coordinated release.
See `docs/framework-evolution/13-python-parity-release.md` and `RELEASE.md`.
(The predecessor framework's `1.0.x` line is unrelated and retired; Culvert
versions start fresh at 0.1.0.)

### Java libraries (`com.enrichmeai.culvert:*`) — Sprint 9–16 additions

- **Sprint 9 (exec core)** — `data-pipeline-core-java`: `DefaultRuntimeContext` wiring through `JobControlRepository`; `governance` package (`PiiMaskingGovernancePolicy`, `MaskingPolicy`, `RetentionPolicy`); `lineage` support types; `finops` package (`BudgetGovernancePolicy`, `CostMetrics`, `FinOpsTag`). `RuntimeContext` and `GovernancePolicy` contracts fully covered.
- **Sprint 10 (emulator ITs)** — `data-pipeline-it-support-java`: Testcontainers GCP emulator fixtures (`BigQueryEmulatorContainer`, `FakeGcsServerContainer`); `*IT.java` tests activated by `mvn -P it verify`. All adapter modules gained corresponding IT tests.
- **Sprint 11 (orchestration)** — `data-pipeline-orchestration-java`: cloud-neutral DAG model (`DagSpec`, `TaskSpec`); `PipelineToDagSpec` translator; `AirflowDagRenderer` + `ComposerDagRenderer` (both implement `DagRenderer`). Scheduler-agnostic; no Airflow runtime dependency. 61 tests.
- **Sprint 12 (observability)** — `data-pipeline-gcp-observability-java`: `CloudTraceObservabilityHook` (`ObservabilityHook`); `DataCatalogLineageEmitter` (`LineageEmitter`); `CloudMonitoringMetricsHook`; `CulvertMdcPopulator` for structured-log correlation. 20 tests.
- **Sprint 13 (FinOps)** — `data-pipeline-gcp-bigquery-java` `BigQueryFinOpsSink` (`FinOpsSink` impl) + `BigQueryCostTracker`; `data-pipeline-gcp-gcs-java` `GcsCostTracker`; `data-pipeline-gcp-pubsub-java` `PubSubCostTracker`. `FinOpsSink` contract fully implemented.
- **Sprint 14 (data quality)** — `data-pipeline-core-java` `dataquality` package: `DataQualityTransform`, `ValidationResult`, `FieldViolation`, `ViolationKind`, `NumericRange`; `data-pipeline-gcp-gcs-java` `QuarantineHandler` + `FailedRowRecord` for quarantine-path routing.
- **Sprint 15 (CI gate)** — `.github/workflows/ci.yml`: per-module parallel matrix (Java 21); integration-test stage (`-P it verify`); PR check suite blocking merge until all contract modules pass.
- **Sprint 16 (hardening)** — Dataflow perf/load-test notes (`docs/PERF_TUNING.md`); security review (`docs/SECURITY_IAM.md`, `docs/SECURITY_CVE.md`); operational runbook (`docs/RUNBOOK.md`); SLO/alerting docs (`docs/SLO_ALERTING.md`); release dry-run (T16.4, this ticket).

### Contract completion status at 0.1.0

| Contract | Adapter(s) |
|---|---|
| `Source` | `PubSubSource` |
| `Sink` | `PubSubSink` |
| `Transform` | `DataQualityTransform` (core) |
| `Pipeline` | `DataflowPipeline` |
| `PipelineStage` | core framework |
| `RuntimeContext` | `DefaultRuntimeContext` |
| `JobControlRepository` | `BigQueryJobControlRepository` |
| `BlobStore` | `GcsBlobStore`, `S3BlobStore`, `AzureBlobStore` |
| `Warehouse` | `BigQueryWarehouse` |
| `AuditEventPublisher` | `BigQueryAuditEventPublisher` |
| `GovernancePolicy` | `PiiMaskingGovernancePolicy`, `BudgetGovernancePolicy` |
| `LineageEmitter` | `DataCatalogLineageEmitter` |
| `ObservabilityHook` | `CloudTraceObservabilityHook` |
| `StageMetricsHook` | `CloudMonitoringMetricsHook` |
| `FinOpsSink` | `BigQueryFinOpsSink` |
| `SecretProvider` | `SecretManagerProvider` |

**Java reactor at 0.1.0: 13 modules, 478 tests (0 failures, 0 errors).**

### Not published in this release

- Maven Central publication is a manual gate; see [RELEASE.md](RELEASE.md) for the procedure.
- This release entry documents the dry-run only — no artifact was uploaded.
- **Signing — mechanism verified, passphrase is the only missing input.** GPG key `11921786` (rsa4096, Joseph Aruja) is in the keyring and **can sign headlessly** — confirmed by a direct `gpg --batch --pinentry-mode loopback --detach-sign` which produced a valid `.asc`. The key is **passphrase-protected**, so the `maven-gpg-plugin` `release` dry-run needs `-Dgpg.passphrase=<key passphrase>` (Joseph's secret — intentionally not supplied here). The artifact-assembly dry-run was therefore completed with `-Dgpg.skip=true` (BUILD SUCCESS, all 13 jar trios assembled); the signing step is proven-working pending the passphrase at real-release time. To sign in CI/non-interactive: `allow-loopback-pinentry` in `~/.gnupg/gpg-agent.conf` + `-Dgpg.passphrase=$KEY_PASSPHRASE`.

---

### 0.1.0 foundation — the first feature-complete dev-cycle (Sprints 0–8)

The earlier foundation of the same unreleased 0.1.0 (the Sprint 9–16 additions above build on this). **Not yet published to PyPI / Maven Central** — that step waits for explicit go.

### Java libraries (`com.enrichmeai.culvert:*`)

- `data-pipeline-core` — cloud-neutral kernel: 16 contract interfaces (Source, Sink, Transform, Pipeline, PipelineStage, RuntimeContext, JobControlRepository, BlobStore, Warehouse, AuditEventPublisher, GovernancePolicy, LineageEmitter, ObservabilityHook, StageMetricsHook, FinOpsSink, SecretProvider) + supporting records (incl. `StageMetrics`) + `AutoConfig` ServiceLoader-driven registry. 36 tests.
- `data-pipeline-gcp-secrets` — SecretManagerProvider implementing SecretProvider. 4 tests.
- `data-pipeline-gcp-bigquery` — three impls under one module: BigQueryWarehouse (Warehouse, 12), BigQueryJobControlRepository (JobControlRepository, 17), BigQueryFinOpsSink (FinOpsSink, 11). 40 tests.
- `data-pipeline-gcp-gcs` — GcsBlobStore (BlobStore). 17 tests.
- `data-pipeline-gcp-pubsub` — PubSubSource + PubSubSink (Source + Sink). 17 tests.
- `data-pipeline-gcp-observability` — CloudTraceObservabilityHook + DataCatalogLineageEmitter. 20 tests.
- `data-pipeline-gcp-dataflow` — DataflowPipeline (Pipeline) + Beam-bridging utility methods. 12 tests.
- `data-pipeline-tester` — Mockito-helper fixture builders for 5 protocols. 15 tests.
- `data-pipeline-contract-tests` — abstract JUnit contract test classes (SecretProvider, BlobStore, Warehouse). 1 smoke test.

**Java reactor: ~172 tests across 9 modules.**

### Python libraries (`data-pipeline-*`)

- `data-pipeline-core` — Python Protocols mirroring the Java contracts; `AutoConfig` registry + decorator surface (`@pipeline`, `@stage`, `@source`, `@sink`, `@transform`). 11 tests.
- `data-pipeline-gcp-bigquery` — BigQueryWarehouse Python equivalent. 10 tests.
- `data-pipeline-gcp-gcs` — GcsBlobStore Python equivalent. 12 tests.
- `data-pipeline-gcp-pubsub` — PubSubSource + PubSubSink Python equivalents. 10 tests.
- `data-pipeline-contract-tests` — pytest mixin classes mirroring the Java abstract contract test classes. 2 smoke tests.

Plus the Stage 1 deprecation shims (`gcp-pipeline-tester`, `gcp-pipeline-transform`, `gcp-pipeline-framework`, `gcp-pipeline-orchestration`) that re-export from the renamed `data-pipeline-*` packages.

### Tooling and process

- `docs/framework-evolution/03-dev-process.md` — orchestrator / advisor / dev-agent role model, sprint-branch workflow, oversized-ticket split rule, standup-comment protocol, 5-minute retro.
- `docs/framework-evolution/04-sprint-plan.md` — 8-sprint plan.
- `uat/` — WireMock 3.5.4 harness with `docker-compose.uat.yml` + 3 sample HTTP-style mock endpoints. Internal-demo only.

## Sprint history

| Sprint | Closed | Tickets | Tests added |
|---|---|---|---|
| 0 | 2026-05-26 | Plan backlog 8 sprints deep, scaffold sprint-1 modules | — |
| 1 | 2026-05-26 | #5 secrets / #6 bigquery-warehouse / #7 gcs / #8 bq-job-control / #9 bq-finops | 66 |
| 2 | 2026-05-27 | #23 pubsub / #24 observability / #25 dataflow / #26 tester | 64 |
| 3 | 2026-05-27 | Python GCP modules (bigquery + gcs + pubsub) | 32 |
| 4 | 2026-05-27 | AutoConfig + decorators (Java + Python) | 14 |
| 5 | 2026-05-27 | Contract test scaffolding (Java + Python) | ~15 |
| 6 | 2026-05-27 | WireMock UAT harness | — |
| 7 | 2026-05-27 | Release prep docs (this changelog + RELEASE.md) | — |
| 8 | 2026-05-27 | AWS / Azure skeletons + book v2 outline (planned) | TBD |

## Not yet shipped

- Publishing to PyPI / Maven Central — see [RELEASE.md](RELEASE.md) for the procedure when ready.
- Repo rename — completed (`enrichmeai/culvert`); the procedure doc has been retired.
- Book v1 ship to Leanpub / other channel — separate workflow, not in scope for this changelog.
