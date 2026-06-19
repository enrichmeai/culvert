# Changelog

All notable changes to the Culvert data pipeline framework. See [DEV_PROCESS.md](docs/framework-evolution/03-dev-process.md) for the sprint workflow.

## [1.0.0] — 2026-06-13

**All 16 contract interfaces have real Java adapters. The Java v1.0 feature bar is met — built and HELD, not yet published.**

This spans Sprints 9–16: every contract interface defined in `data-pipeline-core-java` now has at least one concrete adapter under `com.enrichmeai.culvert:*`. The Java reactor is frozen at tag `java-1.0.0`, but it does **not** publish alone — the release gate is Java **and** Python both ready, then a coordinated `1.0.0` to Maven Central **and** PyPI (`culvert`). See `docs/framework-evolution/13-python-parity-release.md`. The Python parity work (Sprints 17+) is in progress.

### Java libraries (`com.enrichmeai.culvert:*`) — Sprint 9–16 additions

- **Sprint 9 (exec core)** — `data-pipeline-core-java`: `DefaultRuntimeContext` wiring through `JobControlRepository`; `governance` package (`PiiMaskingGovernancePolicy`, `MaskingPolicy`, `RetentionPolicy`); `lineage` support types; `finops` package (`BudgetGovernancePolicy`, `CostMetrics`, `FinOpsTag`). `RuntimeContext` and `GovernancePolicy` contracts fully covered.
- **Sprint 10 (emulator ITs)** — `data-pipeline-it-support-java`: Testcontainers GCP emulator fixtures (`BigQueryEmulatorContainer`, `FakeGcsServerContainer`); `*IT.java` tests activated by `mvn -P it verify`. All adapter modules gained corresponding IT tests.
- **Sprint 11 (orchestration)** — `data-pipeline-orchestration-java`: cloud-neutral DAG model (`DagSpec`, `TaskSpec`); `PipelineToDagSpec` translator; `AirflowDagRenderer` + `ComposerDagRenderer` (both implement `DagRenderer`). Scheduler-agnostic; no Airflow runtime dependency. 61 tests.
- **Sprint 12 (observability)** — `data-pipeline-gcp-observability-java`: `CloudTraceObservabilityHook` (`ObservabilityHook`); `DataCatalogLineageEmitter` (`LineageEmitter`); `CloudMonitoringMetricsHook`; `CulvertMdcPopulator` for structured-log correlation. 20 tests.
- **Sprint 13 (FinOps)** — `data-pipeline-gcp-bigquery-java` `BigQueryFinOpsSink` (`FinOpsSink` impl) + `BigQueryCostTracker`; `data-pipeline-gcp-gcs-java` `GcsCostTracker`; `data-pipeline-gcp-pubsub-java` `PubSubCostTracker`. `FinOpsSink` contract fully implemented.
- **Sprint 14 (data quality)** — `data-pipeline-core-java` `dataquality` package: `DataQualityTransform`, `ValidationResult`, `FieldViolation`, `ViolationKind`, `NumericRange`; `data-pipeline-gcp-gcs-java` `QuarantineHandler` + `FailedRowRecord` for quarantine-path routing.
- **Sprint 15 (CI gate)** — `.github/workflows/ci.yml`: per-module parallel matrix (Java 21); integration-test stage (`-P it verify`); PR check suite blocking merge until all contract modules pass.
- **Sprint 16 (hardening)** — Dataflow perf/load-test notes (`docs/PERF_TUNING.md`); security review (`docs/SECURITY_IAM.md`, `docs/SECURITY_CVE.md`); operational runbook (`docs/RUNBOOK.md`); SLO/alerting docs (`docs/SLO_ALERTING.md`); release dry-run (T16.4, this ticket).

### Contract completion status at 1.0.0

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

**Java reactor at 1.0.0: 13 modules, 478 tests (0 failures, 0 errors).**

### Not published in this release

- Maven Central publication is a manual gate; see [RELEASE.md](RELEASE.md) for the procedure.
- This release entry documents the dry-run only — no artifact was uploaded.
- **Signing — mechanism verified, passphrase is the only missing input.** GPG key `11921786` (rsa4096, Joseph Aruja) is in the keyring and **can sign headlessly** — confirmed by a direct `gpg --batch --pinentry-mode loopback --detach-sign` which produced a valid `.asc`. The key is **passphrase-protected**, so the `maven-gpg-plugin` `release` dry-run needs `-Dgpg.passphrase=<key passphrase>` (Joseph's secret — intentionally not supplied here). The artifact-assembly dry-run was therefore completed with `-Dgpg.skip=true` (BUILD SUCCESS, all 13 jar trios assembled); the signing step is proven-working pending the passphrase at real-release time. To sign in CI/non-interactive: `allow-loopback-pinentry` in `~/.gnupg/gpg-agent.conf` + `-Dgpg.passphrase=$KEY_PASSPHRASE`.

---

## [0.1.0] — unreleased

The framework's first feature-complete dev-cycle. **Not yet published to PyPI / Maven Central** — that step waits for explicit go.

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
- Repo rename — see [REPO_RENAME.md](REPO_RENAME.md) for the procedure.
- Book v1 ship to Leanpub / other channel — separate workflow, not in scope for this changelog.
