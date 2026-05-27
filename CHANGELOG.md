# Changelog

All notable changes to the Culvert data pipeline framework. See [DEV_PROCESS.md](docs/framework-evolution/03-dev-process.md) for the sprint workflow.

## [0.1.0] — unreleased

The framework's first feature-complete dev-cycle. **Not yet published to PyPI / Maven Central** — that step waits for explicit go.

### Java libraries (`com.enrichmeai.culvert:*`)

- `data-pipeline-core` — cloud-neutral kernel: 15 contract interfaces (Source, Sink, Transform, Pipeline, PipelineStage, RuntimeContext, JobControlRepository, BlobStore, Warehouse, AuditEventPublisher, GovernancePolicy, LineageEmitter, ObservabilityHook, FinOpsSink, SecretProvider) + supporting records + `AutoConfig` ServiceLoader-driven registry. 36 tests.
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
