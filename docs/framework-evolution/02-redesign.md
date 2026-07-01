# Framework Cloud-Neutral Redesign

A design document for renaming, splitting, and re-grouping the existing `gcp-pipeline-*` libraries into a cloud-neutral framework with cloud-specific modules attached. The audit in `docs/framework-evolution/01-audit.md` established what is already neutral, what needs a refactor, and what is genuinely GCP-coupled. This document picks up from that inventory and answers the next question: *what should the package layout look like if we take the "Spring for data pipelines" positioning seriously?*

Nothing here changes code. This is a layout, a set of contracts, and a sequenced migration. The intent is that an engineer can read this end-to-end, agree or disagree on specifics, and then execute the move with no further architectural surprises.

## 1. The commitment

The architectural commitment is this: there is a small cloud-neutral core that contains the framework's domain primitives (pipelines, sources, sinks, transforms, audit, lineage, governance, finops, observability, data quality) expressed as Python protocols and pure-Python implementations; there are cloud-specific modules that implement those protocols against a particular cloud's services; and the user composes a working pipeline by depending on the core plus whichever cloud modules they need. GCP is the first reference implementation because it already exists. AWS and Azure are reserved slots in the layout that the team is *not* committing to build but is committing not to design around.

This is the same shape Spring took. `spring-core` came first; `spring-data-jpa` shipped against a real database before `spring-data-mongodb` existed; the JPA module did not contaminate `spring-core` with relational assumptions because the team designed `spring-core` to host any persistence model, not just the one they happened to have first. The MongoDB module landed years later and the JPA users did not have to learn anything new. We can do the same. `data-pipeline-core` will not import a single Google Cloud client library. `data-pipeline-gcp-bigquery` is allowed — encouraged — to embrace BigQuery's specifics, just as `spring-data-jpa` embraced JPA's. When `data-pipeline-aws-redshift` arrives, it inherits the same contracts; the core does not move.

The positioning the book takes (Chapter 2, "The framework as the answer", around line 277) is consistent with this commitment: *small framework-agnostic core, opinionated modules clipped on around it, conventions over configuration, escape hatches everywhere*. The audit confirms the codebase is structurally about halfway there. This document closes the rest of the gap.

## 2. Target package layout

The naming convention is `data-pipeline-` (not `pipeline-`, and not `gcp-pipeline-`). The "data-" prefix is load-bearing: it signals the domain (data pipelines), keeps the namespace distinct from generic CI/CD or ML "pipeline" packages, and matches the way Spring distinguishes `spring-data-*` from `spring-batch-*` or `spring-cloud-*`. The Python import path mirrors the distribution name with underscores, so `data-pipeline-core` exposes `import data_pipeline_core`, and `data-pipeline-gcp-bigquery` exposes `import data_pipeline_gcp_bigquery`.

```text
data-pipeline-libraries/
|
|-- data-pipeline-core/                          # cloud-neutral, no cloud SDKs
|   `-- src/data_pipeline_core/
|       |-- contracts/                            # Protocol definitions only
|       |   |-- source.py                         # Source[T], Sink[T], Transform[T,U]
|       |   |-- pipeline.py                       # Pipeline, PipelineStage
|       |   |-- runtime.py                        # RuntimeContext
|       |   |-- job_control.py                    # JobControlRepository protocol
|       |   |-- blob_store.py                     # BlobStore protocol
|       |   |-- warehouse.py                      # Warehouse protocol
|       |   |-- audit.py                          # AuditEventPublisher protocol
|       |   |-- governance.py                     # GovernancePolicy protocol
|       |   |-- lineage.py                        # LineageEmitter protocol
|       |   |-- observability.py                  # ObservabilityHook protocol
|       |   |-- finops.py                         # FinOpsTag, FinOpsSink protocol
|       |   `-- secrets.py                        # SecretProvider protocol
|       |-- runtime/                              # Composition container, lifecycle
|       |   |-- context.py                        # RuntimeContext implementation
|       |   |-- registry.py                       # ComponentRegistry, decorator wiring
|       |   |-- auto_config.py                    # AutoConfigure callable registry
|       |   `-- bootstrap.py                      # entry point: bootstrap_runtime()
|       |-- decorators/                           # @pipeline, @source, @sink, etc.
|       |   |-- pipeline.py
|       |   |-- components.py                     # @source, @transform, @sink
|       |   |-- governance.py                     # @governed, @masked, @classified
|       |   `-- quality.py                        # @quality_check
|       |-- errors/                               # cloud-neutral error taxonomy
|       |   |-- errors.py                         # PipelineError, ValidationError, ...
|       |   |-- handler.py                        # ErrorHandler, ErrorClassifier
|       |   |-- context.py                        # ErrorContext decorator
|       |   |-- models.py                         # ErrorConfig, ErrorRecord
|       |   |-- storage.py                        # ErrorStorageBackend ABC + InMemory impl
|       |   `-- types.py
|       |-- ids/                                  # run_id, correlation_id, idempotency
|       |   `-- run_id.py
|       |-- lineage/                              # OpenLineage-shaped events
|       |   |-- tracker.py                        # DataLineageTracker
|       |   `-- events.py                         # LineageEvent dataclasses
|       |-- audit/                                # cloud-neutral audit primitives
|       |   |-- records.py                        # AuditRecord, AuditEntry
|       |   |-- trail.py                          # AuditTrail
|       |   `-- reconciliation.py                 # ReconciliationEngine.reconcile_counts
|       |-- governance_api/                       # policy model
|       |   |-- policies.py                       # MaskingPolicy, RetentionPolicy
|       |   |-- classification.py                 # DataClassification enum
|       |   `-- engine.py                         # GovernancePolicyEngine
|       |-- observability_api/                    # metric/log/trace models
|       |   |-- metrics.py                        # MetricsCollector
|       |   |-- health.py                         # HealthChecker
|       |   |-- alerts.py                         # AlertManager, AlertBackend ABC
|       |   |-- otel.py                           # tracing, context, metrics_bridge
|       |   `-- observability.py                  # ObservabilityManager
|       |-- finops_api/                           # cost model, cloud-neutral
|       |   |-- models.py                         # CostMetrics
|       |   |-- labels.py                         # FinOpsTag (renamed from FinOpsLabels)
|       |   `-- aggregator.py                     # CostAggregator
|       |-- orchestration_api/                    # scheduling intent, cloud-neutral
|       |   |-- config.py                         # RetryPolicy, ScheduleConfig, ...
|       |   |-- dag.py                            # DAG model (graph of tasks)
|       |   |-- routing.py                        # DAGRouter, FileType, ProcessingMode
|       |   `-- validators.py
|       |-- job_control_api/                      # job ledger types
|       |   |-- models.py                         # PipelineJob
|       |   `-- types.py                          # JobStatus, FailureStage, JobType
|       |-- schema/                               # cloud-neutral schema model
|       |   `-- entity.py                         # SchemaField, EntitySchema
|       |-- file_management/                      # HDR/TRL parser
|       |   `-- hdr_trl/
|       `-- utilities/
|           |-- run_id.py
|           |-- logging.py                        # StructuredJsonFormatter
|           `-- blob_discovery.py                 # generic discovery against BlobStore
|
|-- data-pipeline-quality/                       # cloud-neutral data quality
|   `-- src/data_pipeline_quality/
|       |-- checker.py
|       |-- dimensions.py
|       |-- scoring.py
|       |-- anomaly.py
|       |-- reporting.py
|       |-- contracts.py                          # QualityCheck protocol, integrations
|       `-- types.py
|
|-- data-pipeline-governance/                    # cloud-neutral governance
|   `-- src/data_pipeline_governance/
|       |-- masking.py                            # masking algorithms (no cloud calls)
|       |-- classification.py                    # tagging logic
|       |-- retention.py                          # retention policy engine
|       `-- lineage.py                            # OpenLineage emitter, no cloud
|
|-- data-pipeline-orchestration-core/            # scheduler-agnostic DAG model
|   `-- src/data_pipeline_orchestration_core/
|       |-- dag.py                                # DAG, Task, Edge
|       |-- retry.py                              # RetryPolicy
|       |-- schedule.py                           # ScheduleConfig
|       |-- triggers.py                           # event triggers, time triggers
|       `-- callbacks/                            # callback handler protocols
|           |-- types.py
|           `-- handlers.py
|
|-- data-pipeline-observability/                 # OTEL exporters, generic
|   `-- src/data_pipeline_observability/
|       |-- exporters/
|       |   |-- otlp.py
|       |   |-- prometheus.py
|       |   `-- console.py
|       |-- backends/
|       |   |-- datadog.py
|       |   |-- slack.py
|       |   `-- logging.py
|       `-- bridges/
|           `-- metrics_bridge.py
|
|-- data-pipeline-finops/                        # cost aggregator, neutral
|   `-- src/data_pipeline_finops/
|       |-- aggregator.py
|       |-- reporter.py
|       `-- exporters/
|           `-- csv.py
|
|-- data-pipeline-test/                          # fixtures, golden data, contract tests
|   `-- src/data_pipeline_test/
|       |-- base/
|       |   |-- pipeline_test.py
|       |   |-- validation_test.py
|       |   |-- scenario_test.py
|       |   `-- result.py
|       |-- builders/
|       |   |-- record_builder.py
|       |   |-- pipeline_builder.py
|       |   `-- config_builder.py
|       |-- assertions/
|       |-- bdd/
|       |-- mocks/
|       |   |-- warehouse_mock.py                 # was bigquery_mock.py
|       |   |-- blob_store_mock.py                # was gcs_mock.py
|       |   `-- event_bus_mock.py                 # was pubsub_mock.py
|       |-- fixtures/
|       |   `-- common.py
|       `-- contracts/                            # protocol-driven contract tests
|           |-- test_job_control_contract.py
|           |-- test_blob_store_contract.py
|           |-- test_warehouse_contract.py
|           `-- test_audit_publisher_contract.py
|
|-- data-pipeline-validators/                    # extracted from gcp-pipeline-beam
|   `-- src/data_pipeline_validators/
|       |-- classes.py
|       |-- code.py
|       |-- date.py
|       |-- generic.py
|       |-- numeric.py
|       |-- schema_validator.py
|       `-- types.py
|
|-- data-pipeline-transform-core/                # dialect-neutral dbt macros
|   `-- src/data_pipeline_transform_core/
|       `-- dbt_shared/macros/                    # macros wrapped in adapter blocks
|
|-- data-pipeline-gcp-bigquery/                  # GCP: BigQuery adapter
|   `-- src/data_pipeline_gcp_bigquery/
|       |-- client.py                             # was clients/bigquery_client.py
|       |-- warehouse.py                          # implements Warehouse protocol
|       |-- bigquery_job_control_repository.py    # was job_control/repository.py
|       |-- bigquery_audit_publisher.py
|       |-- bigquery_reconciliation_engine.py     # was reconciliation.reconcile_with_bigquery
|       |-- cost_tracker.py                       # BigQuery-specific cost constants
|       |-- dual_run.py                           # was gcp-pipeline-tester/comparison/dual_run.py
|       |-- auto_config.py                        # @auto_configure entry point
|       `-- fixtures.py
|
|-- data-pipeline-gcp-dataflow/                  # GCP: Beam-on-Dataflow
|   `-- src/data_pipeline_gcp_dataflow/
|       |-- pipelines/base/                       # was gcp-pipeline-beam/pipelines/base
|       |-- pipelines/beam/                       # was gcp-pipeline-beam/pipelines/beam
|       |   |-- io/
|       |   |   |-- bigquery.py
|       |   |   |-- bigquery_retry.py
|       |   |   `-- gcs.py
|       |   |-- pubsub/
|       |   |-- streaming/
|       |   |-- transforms/
|       |   |-- builder.py
|       |   |-- resource_config.py
|       |   `-- options.py                        # GCPPipelineOptions -> DataflowPipelineOptions
|       `-- auto_config.py
|
|-- data-pipeline-gcp-composer/                  # GCP: Airflow-on-Composer
|   `-- src/data_pipeline_gcp_composer/
|       |-- factories/
|       |   |-- dag_factory.py
|       |   `-- _dag_builders.py
|       |-- operators/
|       |   `-- dataflow.py
|       |-- sensors/
|       |   |-- pubsub.py
|       |   `-- dataflow.py
|       |-- hooks/
|       |   `-- secrets.py                        # Secret Manager hook
|       |-- callbacks/
|       |   |-- dlq.py                            # Pub/Sub DLQ
|       |   `-- quarantine.py                     # GCS quarantine
|       `-- auto_config.py
|
|-- data-pipeline-gcp-dataplex/                  # GCP: governance + lineage
|   `-- src/data_pipeline_gcp_dataplex/
|       |-- governance.py                         # implements GovernancePolicy via Dataplex
|       |-- autodq.py                             # AutoDQ adapter -> data-pipeline-quality
|       |-- lineage_publisher.py                  # implements LineageEmitter
|       `-- auto_config.py
|
|-- data-pipeline-gcp-gcs/                       # GCP: GCS adapter
|   `-- src/data_pipeline_gcp_gcs/
|       |-- client.py                             # was clients/gcs_client.py
|       |-- blob_store.py                         # implements BlobStore protocol
|       |-- gcs_error_storage.py                  # was error_handling/storage.GCSErrorStorage
|       |-- gcs_recovery_manager.py               # was data_deletion/recovery.GCSRecoveryManager
|       |-- gcs_discovery.py                      # was utilities/gcs_discovery.py
|       |-- file_management/                      # archiver, lifecycle, metadata
|       `-- auto_config.py
|
|-- data-pipeline-gcp-pubsub/                    # GCP: Pub/Sub adapter
|   `-- src/data_pipeline_gcp_pubsub/
|       |-- client.py                             # was clients/pubsub_client.py
|       |-- pubsub_audit_publisher.py             # was audit/publisher.py
|       `-- auto_config.py
|
|-- data-pipeline-gcp-observability/             # GCP: Cloud Monitoring, Cloud Trace
|   `-- src/data_pipeline_gcp_observability/
|       |-- cloud_monitoring_alerts.py
|       |-- cloud_trace_exporter.py
|       `-- auto_config.py
|
|-- data-pipeline-gcp-secrets/                   # GCP: Secret Manager
|   `-- src/data_pipeline_gcp_secrets/
|       |-- secret_manager_provider.py            # implements SecretProvider
|       `-- auto_config.py
|
|-- data-pipeline-gcp-dbt/                       # dbt + BigQuery profile
|   `-- src/data_pipeline_gcp_dbt/
|       |-- profile.py                            # impersonation auth
|       |-- macros/                               # BigQuery dialect macros
|       `-- auto_config.py
|
|-- data-pipeline-starter-gcp-fdp/               # working FDP scaffold
|   `-- template/                                 # copier template
|       |-- pyproject.toml
|       |-- pipeline.yaml
|       |-- infrastructure/terraform/
|       |-- pipelines/
|       |-- Makefile
|       `-- README.md
|
|-- data-pipeline-starter-gcp-streaming/         # streaming scaffold
|   `-- template/...
|
# Reserved slots (not built, not designed against):
|-- data-pipeline-aws-redshift/                  # FUTURE: Redshift Warehouse impl
|-- data-pipeline-aws-s3/                        # FUTURE: S3 BlobStore impl
|-- data-pipeline-aws-glue/                      # FUTURE: Glue adapter
|-- data-pipeline-aws-mwaa/                      # FUTURE: MWAA orchestration
|-- data-pipeline-aws-dynamodb-jobcontrol/       # FUTURE: DynamoDB job ledger
|-- data-pipeline-azure-synapse/                 # FUTURE: Synapse warehouse
|-- data-pipeline-azure-adls/                    # FUTURE: ADLS BlobStore
|-- data-pipeline-azure-datafactory/             # FUTURE: ADF orchestration
`-- data-pipeline-starter-aws-fdp/               # FUTURE: AWS FDP scaffold
```

What lives in each package, and which audited files migrate in, follows.

**`data-pipeline-core`** is the framework's kernel. Purpose: define the contracts, the runtime container, the decorator surface, the error taxonomy, the schema model, and the cloud-neutral helpers. Zero GCP dependencies — no `google.cloud.*` import is allowed anywhere in this distribution, and the pyproject's `dependencies` lists only `typing-extensions`, `pydantic` (for `RuntimeContext` config validation), and `opentelemetry-api` (open standard, no GCP coupling). Migrations: from `gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/`, all of `data_quality/` moves out to `data-pipeline-quality` instead; `audit/records.py`, `audit/trail.py`, `audit/lineage.py`, and `audit/reconciliation.py` (minus the BigQuery method) move to `data_pipeline_core/audit/` and `data_pipeline_core/lineage/`; `data_deletion/{detector,quarantine,deletion,types,framework}.py` move to `data_pipeline_core/governance_api/` (data deletion is a governance concern); `error_handling/{errors,handler,context,models,types}.py` and the in-memory part of `storage.py` move to `data_pipeline_core/errors/`; `finops/models.py` and `finops/labels.py` move to `data_pipeline_core/finops_api/`; `job_control/models.py` and `job_control/types.py` move to `data_pipeline_core/job_control_api/`; `file_management/hdr_trl/` moves to `data_pipeline_core/file_management/` (the parser gets a `BlobStore` injection point as the audit recommended); `monitoring/{metrics,health,types,observability}.py`, `monitoring/alerts.py` (minus `CloudMonitoringBackend`), and `monitoring/otel/{tracing,context,metrics_bridge}.py` move to `data_pipeline_core/observability_api/`; `schema.py` moves to `data_pipeline_core/schema/entity.py`; `utilities/run_id.py` and `utilities/logging.py` move as-is. The public API surface is the `contracts/` package plus a top-level `data_pipeline_core` namespace that re-exports the protocols and decorators a user actually needs (`Source`, `Sink`, `Transform`, `Pipeline`, `RuntimeContext`, `@pipeline`, `@source`, `@transform`, `@sink`, `@governed`, `@masked`, `@quality_check`).

**`data-pipeline-quality`** is the data quality framework, factored out of core because it is large enough to deserve its own distribution and because users may want it without the rest of the framework. Purpose: dimension checks (completeness, validity, uniqueness, freshness), scoring, anomaly detection, reporting, and protocol-level integration points for Soda Core, Great Expectations, and Dataplex AutoDQ adapters. Migrations: every file currently under `gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/data_quality/` — `checker.py`, `dimensions.py`, `scoring.py`, `anomaly.py`, `reporting.py`, `types.py` — moves in unchanged. GCP dependencies: zero. The Soda/GE/AutoDQ integrations live behind a `QualityCheck` protocol so the core library does not depend on any of them.

**`data-pipeline-governance`** holds the cloud-neutral parts of governance: masking algorithms, classification taxonomies, retention policy logic, and an OpenLineage-shaped lineage emitter. The cloud-specific Dataplex adapter lives in `data-pipeline-gcp-dataplex`. Migrations: PII masking transforms from `gcp-pipeline-libraries/gcp-pipeline-beam/src/gcp_pipeline_beam/pipelines/beam/transforms/pii.py` (the algorithmic part — Beam wrappers stay in the Beam package) come in here; the new policy model is fresh code. GCP dependencies: zero.

**`data-pipeline-orchestration-core`** is the cloud-neutral DAG model: a graph of tasks with retry policies, schedule intent, dependency edges, and callback hooks. It is *not* an Airflow replacement; it is a scheduler-agnostic specification that the Composer module compiles into an Airflow DAG, that a future AWS module will compile into Step Functions or MWAA DAGs, and that a future Azure module will compile into ADF pipelines. Migrations: from `gcp-pipeline-libraries/gcp-pipeline-orchestration/src/gcp_pipeline_orchestration/factories/config.py` (the `RetryPolicy`, `TimeoutConfig`, `ScheduleConfig`, `DefaultArgs`, `TaskConfig`, `DAGConfig` dataclasses) and `factories/validators.py`; from `routing/` (`router.py`, `config.py`, `yaml_selector.py`); from `callbacks/types.py` and `callbacks/handlers.py`. GCP dependencies: zero.

**`data-pipeline-observability`** is the OTEL exporter library plus the generic alert backends (Datadog, Slack, console/logging). The cloud-specific exporters (Cloud Trace, Cloud Monitoring) live in `data-pipeline-gcp-observability`. Migrations: `monitoring/alerts.py`'s `DatadogAlertBackend`, `SlackAlertBackend`, `LoggingAlertBackend` move here; `monitoring/otel/config.py` and `monitoring/otel/provider.py` move here, with the `GCP_OTLP` and `GCP_TRACE` enum members replaced by a plugin lookup (the GCP module registers them at import time). GCP dependencies: zero.

**`data-pipeline-finops`** is the cloud-neutral cost-aggregation library. The `CostMetrics` dataclass and `FinOpsTag` (renamed from `FinOpsLabels`) live in core; this package provides the aggregator that sums costs across runs, exports them, and joins them with the audit trail. The cloud-specific cost adapters (BigQuery slot pricing, GCS storage pricing, Pub/Sub message pricing) live in their respective GCP modules. GCP dependencies: zero.

**`data-pipeline-test`** is the testing harness: base test classes, builders, assertions, BDD steps, mocks renamed from cloud-specific to protocol-specific (`bigquery_mock.py` becomes `warehouse_mock.py`; `gcs_mock.py` becomes `blob_store_mock.py`; `pubsub_mock.py` becomes `event_bus_mock.py`), and — new — a `contracts/` subpackage that provides protocol-level contract test suites that any concrete adapter can run against itself. Migrations: most of `gcp-pipeline-libraries/gcp-pipeline-tester/` moves here unchanged; the BigQuery-specific `comparison/dual_run.py` moves to `data-pipeline-gcp-bigquery/dual_run.py` (or is kept generalised through a `Warehouse` adapter, decided in stage 4); the BigQuery and GCS fixtures move to the GCP-specific packages with thin aliases left here.

**`data-pipeline-validators`** is extracted from the current Beam package. Purpose: pure record-level validators with no Beam coupling. Migrations: `gcp-pipeline-libraries/gcp-pipeline-beam/src/gcp_pipeline_beam/validators/{classes,code,date,generic,numeric,schema_validator,types}.py` move here unchanged. GCP dependencies: zero. Beam dependencies: zero.

**`data-pipeline-transform-core`** is the dialect-neutral half of the dbt macros. Migrations: `gcp-pipeline-libraries/gcp-pipeline-transform/src/gcp_pipeline_transform/dbt_shared/macros/` moves here, with the dialect-sensitive SQL wrapped in `{% if target.type == 'bigquery' %} ... {% endif %}` blocks. BigQuery-specific implementations move to `data-pipeline-gcp-dbt`.

**`data-pipeline-gcp-bigquery`** is the BigQuery adapter. Purpose: BigQuery client, the BigQuery-backed `JobControlRepository`, the BigQuery `AuditEventPublisher`, the BigQuery `Warehouse`, BigQuery cost constants, and the dual-run comparison utility. Migrations: `gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/clients/bigquery_client.py` moves to `data_pipeline_gcp_bigquery/client.py`. `gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/job_control/repository.py` moves to `data_pipeline_gcp_bigquery/bigquery_job_control_repository.py`, and a new `JobControlRepository` protocol is extracted into `data_pipeline_core/contracts/job_control.py`. `gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/finops/tracker.py` moves to `data_pipeline_gcp_bigquery/cost_tracker.py` (the BigQuery half) and `data-pipeline-gcp-gcs/cost_tracker.py` (the GCS half) and `data-pipeline-gcp-pubsub/cost_tracker.py` (the Pub/Sub half). `gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/audit/reconciliation.py`'s `reconcile_with_bigquery` method moves to `data_pipeline_gcp_bigquery/bigquery_reconciliation_engine.py`. `gcp-pipeline-libraries/gcp-pipeline-tester/src/gcp_pipeline_tester/comparison/dual_run.py` moves here. Public API: the concrete classes plus an `auto_config()` callable that registers them with the runtime when this package is imported.

**`data-pipeline-gcp-dataflow`** is the Beam-on-Dataflow execution module. Migrations: the entire `gcp-pipeline-libraries/gcp-pipeline-beam/src/gcp_pipeline_beam/pipelines/` tree moves here, with `GCPPipelineOptions` renamed to `DataflowPipelineOptions`. The validators that were extracted out go to `data-pipeline-validators`. GCP dependencies: explicit, expected, embraced.

**`data-pipeline-gcp-dataplex`** is the Dataplex adapter for governance, AutoDQ, and lineage. New code, but the integration shape is established by the `GovernancePolicy`, `QualityCheck`, and `LineageEmitter` protocols in core. Migrations: any Dataplex glue currently buried inside the Composer DAGs lifts out here.

**`data-pipeline-gcp-composer`** is the Airflow-on-Composer adapter. Migrations: `gcp-pipeline-libraries/gcp-pipeline-orchestration/src/gcp_pipeline_orchestration/factories/dag_factory.py`, `_dag_builders.py`, `operators/dataflow.py`, `sensors/pubsub.py`, `sensors/dataflow.py`, `hooks/secrets.py`, `callbacks/dlq.py`, `callbacks/quarantine.py` move here. The cloud-neutral routing and config bits move to `data-pipeline-orchestration-core`.

**`data-pipeline-gcp-gcs`** is the GCS adapter. Migrations: `gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/clients/gcs_client.py`, `error_handling/storage.py` (the `GCSErrorStorage` class only), `data_deletion/recovery.py` (the `GCSRecoveryManager` class only), `utilities/gcs_discovery.py`, and the file-management subpackage from `gcp-pipeline-beam` (archiver, lifecycle, metadata) move here.

**`data-pipeline-gcp-pubsub`** is the Pub/Sub adapter. Migrations: `gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/clients/pubsub_client.py` and `audit/publisher.py` move here.

**`data-pipeline-gcp-observability`** holds the Cloud Monitoring alert backend (was `monitoring/alerts.py.CloudMonitoringBackend`) and the Cloud Trace exporter wiring (was `monitoring/otel/provider.py`'s `gcp_otlp` and `gcp_trace` enum branches).

**`data-pipeline-gcp-secrets`** holds the Secret Manager hook currently in `gcp-pipeline-orchestration/src/gcp_pipeline_orchestration/hooks/secrets.py`, refactored to implement the `SecretProvider` protocol from core.

**`data-pipeline-gcp-dbt`** holds the BigQuery dbt profile (impersonation auth), the BigQuery-dialect macros split out of `data-pipeline-transform-core`, and a `dbt_project.yml` snippet that downstream pipelines can import.

**`data-pipeline-starter-gcp-fdp`** is the canonical FDP starter — see section 6 for its contents. **`data-pipeline-starter-gcp-streaming`** is the streaming equivalent.

The AWS and Azure slots at the bottom are *not* packages we are building. They are *reserved names* in the convention so that anyone reading the layout sees the shape and knows where new modules go. We are not designing for AWS or Azure speculatively; we are designing for *not painting ourselves into a GCP corner*, which is a different thing.

## 3. Cloud-neutral contracts

The contracts are Python `typing.Protocol` definitions, kept in `data_pipeline_core/contracts/`. Each is small. Each is implementable in any cloud. None of them imports anything cloud-specific. Where the audit identified an obvious GCP implementation, that implementation lives in `data-pipeline-gcp-*` and is named for the GCP service it wraps.

```python
# data_pipeline_core/contracts/source.py
from typing import Protocol, TypeVar, Iterator, Generic, runtime_checkable

T = TypeVar("T", covariant=True)

@runtime_checkable
class Source(Protocol[T]):
    """Anything that yields records. Stateless from the caller's perspective.
    Implementations may be backed by a file, a queue, a table, an API."""
    def read(self, context: "RuntimeContext") -> Iterator[T]: ...

U = TypeVar("U", contravariant=True)

@runtime_checkable
class Sink(Protocol[U]):
    """Anything that consumes records. The framework guarantees ordering
    only within a single Sink invocation; cross-sink ordering is the caller's
    responsibility."""
    def write(self, records: Iterator[U], context: "RuntimeContext") -> None: ...

V = TypeVar("V")
W = TypeVar("W")

@runtime_checkable
class Transform(Protocol[V, W]):
    """Anything that maps records. Pure where possible; side effects must
    be declared via the @governed decorator so the runtime can track them."""
    def apply(self, records: Iterator[V], context: "RuntimeContext") -> Iterator[W]: ...
```

`Source`, `Sink`, and `Transform` are the foundational primitives. Every pipeline is a graph of these. A GCS file is a `Source[bytes]`. A BigQuery table is both a `Source[dict]` (when reading) and a `Sink[dict]` (when writing). A Pub/Sub topic is a `Source[dict]` for streaming. The Beam package will provide adapters that take a `Source` or `Sink` and wrap it in a Beam `ParDo`.

```python
# data_pipeline_core/contracts/pipeline.py
from typing import Protocol, Sequence

class PipelineStage(Protocol):
    name: str
    inputs: Sequence[str]
    outputs: Sequence[str]
    def execute(self, context: "RuntimeContext") -> None: ...

class Pipeline(Protocol):
    """Composition of stages. The pipeline does not know what runtime it
    will execute on; the runtime is responsible for picking it up and
    scheduling its stages."""
    name: str
    stages: Sequence[PipelineStage]
    def validate(self) -> None: ...
```

`Pipeline` deliberately does not say anything about *how* it executes. A Composer DAG, a Dataflow Flex template, a local in-process runner, and a future AWS Step Functions execution all consume the same `Pipeline` object and translate it into their native scheduling primitives.

```python
# data_pipeline_core/contracts/runtime.py
from typing import Protocol, Any, Mapping

class RuntimeContext(Protocol):
    """Carries config, secrets, observability, lineage, finops tags, and
    the lookup table for all registered protocol implementations. Every
    Source/Sink/Transform method receives a RuntimeContext.

    The runtime context is the framework's dependency-injection container.
    """
    run_id: str
    environment: str
    config: Mapping[str, Any]
    secrets: "SecretProvider"
    observability: "ObservabilityHook"
    lineage: "LineageEmitter"
    finops: "FinOpsSink"
    governance: "GovernancePolicyEngine"
    def get(self, protocol: type) -> Any: ...
    def register(self, protocol: type, impl: Any) -> None: ...
```

`RuntimeContext` is the framework's `ApplicationContext` (the Spring analogue). It is constructed once at startup by the bootstrap routine, populated by the auto-config registry, and threaded through every component invocation.

```python
# data_pipeline_core/contracts/job_control.py
from typing import Protocol, Optional, Sequence
from data_pipeline_core.job_control_api.models import PipelineJob
from data_pipeline_core.job_control_api.types import JobStatus

class JobControlRepository(Protocol):
    """Tracks the lifecycle of a pipeline-job: created, running, succeeded,
    failed, retrying. Implementations are expected to be transactional within
    a single run_id."""
    def create_job(self, job: PipelineJob) -> None: ...
    def get_job(self, run_id: str) -> Optional[PipelineJob]: ...
    def update_status(self, run_id: str, status: JobStatus) -> None: ...
    def mark_failed(self, run_id: str, error: str, stage: str) -> None: ...
    def mark_retrying(self, run_id: str, attempt: int) -> None: ...
    def get_pending_jobs(self, system: str) -> Sequence[PipelineJob]: ...
    def get_failed_jobs(self, since_hours: int) -> Sequence[PipelineJob]: ...
    def cleanup_partial_load(self, run_id: str) -> None: ...
    def update_cost_metrics(self, run_id: str, metrics: "CostMetrics") -> None: ...
```

GCP implementation: `data_pipeline_gcp_bigquery.BigQueryJobControlRepository` — the existing class moved with no behavioural change. Hypothetical AWS implementation: `data_pipeline_aws_dynamodb_jobcontrol.DynamoDBJobControlRepository`. Hypothetical Azure implementation: `data_pipeline_azure_cosmos_jobcontrol.CosmosJobControlRepository`. The point is that core never imports any of these.

```python
# data_pipeline_core/contracts/blob_store.py
from typing import Protocol, Iterator, Optional, BinaryIO

class BlobStore(Protocol):
    """Object storage abstraction. URIs are opaque strings (gs://, s3://,
    abfs://). The framework does not parse them; implementations do."""
    def get(self, uri: str) -> bytes: ...
    def open(self, uri: str, mode: str = "rb") -> BinaryIO: ...
    def put(self, uri: str, data: bytes) -> None: ...
    def list(self, prefix: str) -> Iterator[str]: ...
    def exists(self, uri: str) -> bool: ...
    def delete(self, uri: str) -> None: ...
    def copy(self, src: str, dst: str) -> None: ...
```

GCP implementation: `data_pipeline_gcp_gcs.GCSBlobStore`. AWS: `data_pipeline_aws_s3.S3BlobStore`. Azure: `data_pipeline_azure_adls.ADLSBlobStore`. The `gs://`-sniffing code in today's HDR/TRL parser disappears because the parser now takes a `BlobStore` and asks it; the parser does not care what scheme the URI has.

```python
# data_pipeline_core/contracts/warehouse.py
from typing import Protocol, Iterator, Mapping, Any, Optional

class Warehouse(Protocol):
    """Tabular query/load abstraction. Deliberately conservative — only
    the operations every serious warehouse supports. Cloud-specific
    operations (BigQuery clustering, Redshift sortkeys, Synapse distribution)
    are exposed via a cloud-specific extension protocol; see the open
    questions section."""
    def query(self, sql: str, params: Optional[Mapping[str, Any]] = None) -> Iterator[Mapping[str, Any]]: ...
    def execute(self, sql: str, params: Optional[Mapping[str, Any]] = None) -> None: ...
    def load_from_uri(self, uri: str, target_table: str, schema: "EntitySchema") -> int: ...
    def merge(self, source_table: str, target_table: str, keys: list[str]) -> int: ...
    def copy(self, source_table: str, target_table: str) -> int: ...
    def table_exists(self, fqtn: str) -> bool: ...
```

GCP implementation: `data_pipeline_gcp_bigquery.BigQueryWarehouse`. AWS: `data_pipeline_aws_redshift.RedshiftWarehouse`. The `fqtn` (fully-qualified table name) is an opaque string; the warehouse implementation parses it according to its own conventions (`project.dataset.table` for BigQuery, `database.schema.table` for Redshift).

```python
# data_pipeline_core/contracts/audit.py
from typing import Protocol
from data_pipeline_core.audit.records import AuditRecord

class AuditEventPublisher(Protocol):
    """Emit audit records. Implementations may batch, but must guarantee
    at-least-once delivery within a single run_id boundary."""
    def publish(self, record: AuditRecord) -> None: ...
    def flush(self) -> None: ...
```

GCP implementation: `data_pipeline_gcp_pubsub.PubSubAuditPublisher` (the current `audit/publisher.py`). AWS: `data_pipeline_aws_firehose.FirehoseAuditPublisher`. Azure: `data_pipeline_azure_eventhub.EventHubAuditPublisher`.

```python
# data_pipeline_core/contracts/governance.py
from typing import Protocol
from data_pipeline_core.governance_api.policies import MaskingPolicy, RetentionPolicy
from data_pipeline_core.governance_api.classification import DataClassification

class GovernancePolicy(Protocol):
    """Resolves what masking/retention/classification applies to a given
    field or table. Implementations may consult Dataplex, Glue Data Catalog,
    Purview, or a static config file."""
    def classify(self, field: str, table: str) -> DataClassification: ...
    def masking_for(self, field: str, table: str) -> Optional[MaskingPolicy]: ...
    def retention_for(self, table: str) -> Optional[RetentionPolicy]: ...
```

GCP implementation: `data_pipeline_gcp_dataplex.DataplexGovernancePolicy`. The default core implementation is a `StaticGovernancePolicy` that reads a YAML file; this is what runs in tests and in any project that hasn't adopted Dataplex.

```python
# data_pipeline_core/contracts/lineage.py
from typing import Protocol
from data_pipeline_core.lineage.events import LineageEvent

class LineageEmitter(Protocol):
    """Publishes OpenLineage-shaped events. Implementations should batch
    by run_id and emit on stage completion."""
    def emit(self, event: LineageEvent) -> None: ...
```

GCP implementation: `data_pipeline_gcp_dataplex.DataplexLineagePublisher`. Cloud-neutral default: `data_pipeline_core.lineage.OpenLineageEmitter` (emits to a Marquez or OpenLineage Proxy endpoint).

```python
# data_pipeline_core/contracts/observability.py
from typing import Protocol, Mapping

class ObservabilityHook(Protocol):
    """The framework's single observability seam. Metrics, logs, and traces
    all flow through this. Implementations bridge to OTEL by default."""
    def counter(self, name: str, value: int = 1, tags: Mapping[str, str] = ...) -> None: ...
    def gauge(self, name: str, value: float, tags: Mapping[str, str] = ...) -> None: ...
    def histogram(self, name: str, value: float, tags: Mapping[str, str] = ...) -> None: ...
    def log(self, level: str, message: str, **fields) -> None: ...
    def span(self, name: str) -> "AbstractContextManager": ...
```

Default implementation: `data_pipeline_core.observability_api.OTELObservabilityHook`. GCP-flavoured implementation: `data_pipeline_gcp_observability.CloudTraceObservabilityHook`.

```python
# data_pipeline_core/contracts/finops.py
from dataclasses import dataclass
from typing import Protocol, Mapping

@dataclass(frozen=True)
class FinOpsTag:
    """Cost-attribution metadata. Maps cleanly to GCP labels, AWS tags,
    and Azure tags."""
    system: str
    environment: str
    cost_center: str
    owner: str
    run_id: str
    extra: Mapping[str, str] = ...

class FinOpsSink(Protocol):
    """Receives cost metrics from cloud-specific cost trackers and writes
    them to wherever the team aggregates them (BigQuery, Athena, Synapse)."""
    def record(self, metrics: "CostMetrics", tags: FinOpsTag) -> None: ...
```

GCP implementation: `data_pipeline_gcp_bigquery.BigQueryFinOpsSink` (writes to the cost-metrics table the audit identified in `finops/tracker.py`).

```python
# data_pipeline_core/contracts/secrets.py
from typing import Protocol

class SecretProvider(Protocol):
    """Single seam for secret lookup. Implementations can call Secret Manager,
    AWS Secrets Manager, Azure Key Vault, HashiCorp Vault, or just read from
    env."""
    def get(self, name: str, version: str = "latest") -> str: ...
```

GCP implementation: `data_pipeline_gcp_secrets.SecretManagerProvider`. Default: `data_pipeline_core.runtime.EnvSecretProvider`.

These sixteen contract interfaces are the entire framework-to-cloud seam. Anything that needs to be cloud-specific touches one of them and lives in a `data-pipeline-<cloud>-*` module. Anything that does not need to be cloud-specific does not.

## 4. The decorator/annotation surface

This is the user-facing API. A user writes a pipeline by decorating Python functions and classes; the framework wires them into the runtime container, attaches observability, applies governance, and schedules them. The decorators are the Spring `@Component`/`@Service`/`@Repository` equivalent — they give the framework permission to introspect, wire, and instrument the code.

```python
from data_pipeline_core import (
    pipeline, source, transform, sink,
    governed, masked, quality_check,
    RuntimeContext,
)
from data_pipeline_core.schema import EntitySchema
from data_pipeline_gcp_gcs import GCSBlobStore   # auto-config wires this in
from data_pipeline_gcp_bigquery import BigQueryWarehouse

CUSTOMER_SCHEMA = EntitySchema.from_yaml("schemas/customer.yaml")


@pipeline(
    name="customer_fdp",
    schedule="0 2 * * *",            # cron, scheduler-agnostic
    retry={"attempts": 3, "backoff_seconds": 60},
    finops_tags={"cost_center": "retail", "owner": "data-platform"},
)
class CustomerFDP:
    """Fixed-width customer file -> landing -> curated."""

    @source(
        uri="gs://incoming/customer/*.dat",
        schema=CUSTOMER_SCHEMA,
        format="fixed-width-hdr-trl",
    )
    def read_files(self, context: RuntimeContext):
        # No body needed for the standard case. The decorator pulls a
        # BlobStore + HDR/TRL parser from the RuntimeContext and yields
        # records. Override the body only if you need bespoke logic.
        ...

    @transform(input="read_files")
    @quality_check(dimension="completeness", min_score=0.99)
    @governed(retention_days=2555, classification="PII")
    def landing(self, records, context):
        for r in records:
            yield {**r, "ingested_at": context.now()}

    @transform(input="landing")
    @masked(fields=["ssn", "dob"], policy="last4")
    def mask_pii(self, records, context):
        # @masked replaces field values per the policy attached to the
        # field in the EntitySchema. The body sees pre-masked records;
        # the decorator post-processes the output.
        return records

    @sink(
        target="bigquery://retail.curated.customer",
        schema=CUSTOMER_SCHEMA,
        write_disposition="WRITE_APPEND",
    )
    def write_curated(self, records, context):
        ...
```

What each decorator does, in plain language. `@pipeline` registers the class with the runtime's `ComponentRegistry`, assigns a `run_id` for every invocation, attaches the schedule and retry config to the cloud-neutral orchestration model (which `data-pipeline-gcp-composer` later compiles into an Airflow DAG), threads finops tags through the runtime context so every downstream cost record is tagged, and wraps the whole pipeline in an `ObservabilityHook` span. `@source` declares an input stage; the URI is opaque to the framework (a `BlobStore` from auto-config parses it), the schema drives validation, and the format string tells the framework which parser to use. `@transform` declares a transformation stage with an explicit input dependency; it can be stacked with `@quality_check` and `@governed` and `@masked`. `@quality_check` invokes the `data-pipeline-quality` framework with the named dimension and threshold; a check failure routes through the error classifier (validation = no retry). `@governed` applies a `GovernancePolicy` lookup against the records; it can attach retention, classification, and lineage metadata. `@masked` applies a `MaskingPolicy` to named fields before they are passed downstream; the schema is consulted for field-level masking defaults so the decorator can be omitted when the schema already says how to mask. `@sink` declares an output stage; the URI scheme tells the framework which `Warehouse` or `BlobStore` to use, and the schema drives the load.

The promise: a typical FDP pipeline is 30–60 lines of decorated Python. Everything else — the BigQuery client, the audit publisher, the lineage events, the cost tracking, the OTEL spans, the retry behaviour, the schema validation, the masking — is the framework's responsibility. The user reads the decorators and knows what is happening. The decorators are *not* magic; they are visible, named, documented, and overridable. Every decorator accepts a `context` kwarg in the wrapped function so the user can drop into the framework's primitives when they need to.

This is what "Spring for data pipelines" buys the user: not the syntax (Python isn't Java; `@pipeline` isn't `@SpringBootApplication`), but the *posture*. Conventions over configuration. Annotations declare intent. The framework does the wiring.

## 5. Auto-configuration model

Spring Boot's killer feature is auto-configuration: add `spring-boot-starter-data-jpa` to your dependencies and JPA is configured; the user does not write XML or `@Configuration` classes for the common case. We replicate this for cloud modules.

Each cloud-specific package exports an `auto_config()` callable. Core exposes a registry. Import-time, the cloud package registers itself; bootstrap-time, the runtime invokes every registered auto-config in dependency order.

```python
# data_pipeline_core/runtime/auto_config.py
from typing import Callable, List
from data_pipeline_core.contracts.runtime import RuntimeContext

AutoConfigure = Callable[[RuntimeContext], None]
_REGISTRY: List[AutoConfigure] = []

def register(fn: AutoConfigure) -> None:
    _REGISTRY.append(fn)

def apply_all(context: RuntimeContext) -> None:
    for fn in _REGISTRY:
        fn(context)
```

A cloud module's `auto_config.py` looks like this:

```python
# data_pipeline_gcp_bigquery/auto_config.py
import os
from google.cloud import bigquery
from data_pipeline_core.runtime.auto_config import register
from data_pipeline_core.contracts.warehouse import Warehouse
from data_pipeline_core.contracts.job_control import JobControlRepository
from data_pipeline_gcp_bigquery.warehouse import BigQueryWarehouse
from data_pipeline_gcp_bigquery.bigquery_job_control_repository import BigQueryJobControlRepository

@register
def configure_bigquery(context):
    project = os.environ.get("GCP_PROJECT") or context.config.get("gcp.project")
    location = os.environ.get("GCP_LOCATION", "EU")
    if not project:
        return                                    # nothing to do; no creds available
    client = bigquery.Client(project=project, location=location)
    context.register(Warehouse, BigQueryWarehouse(client))
    context.register(
        JobControlRepository,
        BigQueryJobControlRepository(
            client=client,
            project_id=project,
            dataset=context.config.get("gcp.job_control.dataset", "pipeline_control"),
            table=context.config.get("gcp.job_control.table", "pipeline_jobs"),
        ),
    )
```

The rule: a `data-pipeline-gcp-*` package's `auto_config` reads its required config from environment variables and the runtime context's `config` mapping; if the config is missing it returns silently rather than crashing (so the import does not break test environments); and it registers concrete implementations against the protocols defined in core. The order is well-defined: core's defaults register first; cloud modules register on top of them and win.

Bootstrap is one line of user code:

```python
# user's entry point (e.g. inside a Dataflow flex template main, or a DAG)
from data_pipeline_core.runtime import bootstrap_runtime

context = bootstrap_runtime(config_path="pipeline.yaml")
context.get_pipeline("customer_fdp").execute(context)
```

Two worked examples make the pattern concrete. First, a user who installs `data-pipeline-core`, `data-pipeline-gcp-bigquery`, and `data-pipeline-gcp-gcs` and sets `GCP_PROJECT` in their env gets a `RuntimeContext` where `context.get(Warehouse)` returns a `BigQueryWarehouse`, `context.get(BlobStore)` returns a `GCSBlobStore`, and `context.get(JobControlRepository)` returns a `BigQueryJobControlRepository`. They write their pipeline against the protocols and never type the word "BigQuery". Second, a user who additionally installs `data-pipeline-gcp-dataplex` gets `context.get(GovernancePolicy)` returning a `DataplexGovernancePolicy` and `context.get(LineageEmitter)` returning a `DataplexLineagePublisher`; without that package, the same calls return the static-config defaults. Adding a module changes wiring, not application code. That is the Spring Boot starter promise.

A future AWS user would install `data-pipeline-aws-redshift`, `data-pipeline-aws-s3`, `data-pipeline-aws-dynamodb-jobcontrol`, set `AWS_REGION`, and get the same protocols wired to AWS implementations. The pipeline definition does not change. That is the cloud-neutrality promise.

## 6. The starter pattern

`data-pipeline-starter-gcp-fdp` is the "rails new"-equivalent for a GCP FDP pipeline. It is a copier template plus a pinned dependency set. The user runs:

```bash
pip install data-pipeline-starter-gcp-fdp
copier copy data-pipeline-starter-gcp-fdp ./my-pipeline
cd my-pipeline && make init test
```

…and gets a working project. Not a skeleton; a working project, deployable to GCP with `make deploy`, that lands a fixed-width file into a curated BigQuery table with audit, lineage, and cost tracking turned on.

Directory tree the template renders into the target:

```text
my-pipeline/
|-- pyproject.toml                      # pins data-pipeline-core, data-pipeline-gcp-*
|-- pipeline.yaml                       # runtime config: schemas, schedules, tags
|-- README.md
|-- Makefile                            # init, test, deploy, teardown targets
|-- .github/workflows/
|   |-- ci.yml                          # pytest + lint
|   `-- deploy.yml                      # gated on commit message
|-- infrastructure/terraform/
|   |-- main.tf                         # uses data-pipeline-gcp-deployment modules
|   |-- variables.tf
|   `-- outputs.tf
|-- schemas/
|   `-- customer.yaml                   # EntitySchema in YAML
|-- pipelines/
|   |-- __init__.py
|   `-- customer_fdp.py                 # the decorated pipeline class
|-- dags/                               # generated by gcp-composer; do not edit
|   `-- customer_fdp_dag.py
|-- tests/
|   |-- unit/test_customer_fdp.py       # uses data-pipeline-test
|   `-- integration/test_e2e.py
`-- test_data/
    |-- customer_sample.dat
    `-- expected_curated.csv
```

The `pyproject.toml` pins exact versions:

```toml
[project]
name = "my-pipeline"
dependencies = [
  "data-pipeline-core==1.0.*",
  "data-pipeline-gcp-bigquery==1.0.*",
  "data-pipeline-gcp-gcs==1.0.*",
  "data-pipeline-gcp-dataflow==1.0.*",
  "data-pipeline-gcp-composer==1.0.*",
  "data-pipeline-gcp-pubsub==1.0.*",
  "data-pipeline-gcp-dbt==1.0.*",
]

[project.optional-dependencies]
test = ["data-pipeline-test==1.0.*", "pytest>=7", "pytest-cov"]
```

The `pipeline.yaml` is the single config file the runtime reads at bootstrap:

```yaml
runtime:
  environment: ${ENVIRONMENT:dev}
  gcp:
    project: ${GCP_PROJECT}
    location: ${GCP_LOCATION:EU}

job_control:
  dataset: pipeline_control
  table: pipeline_jobs

finops:
  default_tags:
    cost_center: retail
    owner: data-platform

pipelines:
  - module: pipelines.customer_fdp
    class: CustomerFDP
```

The `Makefile` exposes `init`, `test`, `deploy`, `teardown`, `cost-estimate`, and `lint`. `deploy` requires `[deploy]` in the most recent commit message (matching the project's CLAUDE.md rules). `teardown` calls `scripts/gcp/00_full_reset.sh --force`. `cost-estimate` runs the finops estimator against the current Terraform plan before any `apply`.

There is a parallel `data-pipeline-starter-gcp-streaming` for Pub/Sub-fed streaming pipelines, and a `data-pipeline-starter-gcp-odp` for operational data products. The `data-pipeline-starter-aws-fdp` slot is reserved for the day an AWS user wants the same experience; the template is identical in structure, only the dependency pins and the Terraform module change.

## 7. Migration path from today's code

The work splits into six stages. None of them is "rename everything on Friday and hope". Each stage produces a green build, deprecation shims keep downstream consumers running, and a stage can ship to PyPI independently.

| Stage | Scope | Effort | Downstream breakage | Compatibility shim |
|---|---|---|---|---|
| 0 | Extract protocols into `data_pipeline_core/contracts/` alongside existing `gcp_pipeline_core`; both packages installable, no behaviour change. | 3-5 days | None | New package; old imports unchanged |
| 1 | Rename `gcp-pipeline-*` distributions to `data-pipeline-*`. Keep `gcp-pipeline-*` as deprecation-shim packages whose `__init__.py` re-exports from the new names with a `DeprecationWarning`. | 5-8 days | Imports continue to work; downstream sees warnings | Re-export shim packages |
| 2 | Move GCP-coupled files out of `data-pipeline-core` into `data-pipeline-gcp-*` modules per the layout. Update `BasePipeline` and `dag_factory` to take protocol-typed dependencies. | 2-3 weeks | Direct imports of moved classes break; users on protocol-typed APIs unaffected | Shim re-exports of moved classes from old paths |
| 3 | Build the auto-config registry, the decorator surface (`@pipeline`, `@source`, ...), and the first starter scaffold. | 3-4 weeks | None (additive) | n/a |
| 4 | Write `data-pipeline-test` contract suites for the four protocols. Run them against the GCP implementations to validate the abstractions. Generalise `dual_run.py` to take a `Warehouse`. | 1-2 weeks | None | n/a |
| 5 | Future: first non-GCP module (recommend `data-pipeline-aws-s3` because S3+BlobStore is the smallest possible test of the abstraction). | 2-4 weeks when triggered | None to existing users | n/a |

Stage 0 is preparation. Extract Python `Protocol` definitions for `Source`, `Sink`, `Transform`, `Pipeline`, `RuntimeContext`, `JobControlRepository`, `BlobStore`, `Warehouse`, `AuditEventPublisher`, `GovernancePolicy`, `LineageEmitter`, `ObservabilityHook`, `FinOpsSink`, and `SecretProvider` into a fresh `data-pipeline-core` distribution. The existing classes are not yet refactored to use them — they sit side by side. The protocols *describe* the existing classes' public methods, which is why this can be done in days rather than weeks. Downstream is untouched. Risk: low. The deliverable is a published `data-pipeline-core==0.1.0` to internal PyPI plus a design review of the protocol shapes against the existing classes.

Stage 1 is the rename. Every Python distribution `gcp-pipeline-*` gets a sibling `data-pipeline-*`. The new distributions contain the actual code; the old distributions become deprecation shims whose `__init__.py` looks like `from data_pipeline_core import *; warnings.warn(...)`. Imports continue to resolve. `from gcp_pipeline_core.audit import AuditTrail` still works; it now resolves to `data_pipeline_core.audit.trail.AuditTrail` and emits a `DeprecationWarning`. CI pipelines, deployment pipelines, and downstream notebooks keep running. Risk: low if the egg-info regeneration is handled cleanly. Effort: a week or so for the mechanical rename (~150 cross-package imports, ~80 deployment imports, ~30 test imports per the audit), plus the shim packaging. The deliverable is a published `data-pipeline-*==0.1.0` plus `gcp-pipeline-*==2.0.0` (the deprecation shim).

Stage 2 is the split. The GCP-coupled files identified in section 2 above move out of `data-pipeline-core` into `data-pipeline-gcp-*` packages. `BasePipeline.__init__` no longer imports `BigQueryClient` directly; it accepts a `Warehouse` (default supplied by auto-config). `dag_factory.py` accepts an `Orchestrator`-typed dependency. The shim re-exports stay in place: a user importing `data_pipeline_core.clients.BigQueryClient` gets a `DeprecationWarning` pointing to `data_pipeline_gcp_bigquery.BigQueryClient`. Risk: medium — this is real refactoring, not search-and-replace, and the `dag_factory` is a load-bearing piece. Effort: 2-3 weeks. Downstream breakage: code that imports concrete classes by name from old paths sees deprecation warnings; code that uses the framework's documented APIs is unaffected.

Stage 3 is the new surface. Build the auto-config registry, the decorator-based pipeline definition, and the first starter scaffold (`data-pipeline-starter-gcp-fdp`). This is the work that turns the framework from "library you import" into "framework you write against". It is additive — nothing breaks — but it is the bulk of the design work, because the decorators need to work cleanly with both Dataflow and Composer execution and need to thread the runtime context correctly. Effort: 3-4 weeks. The deliverable is a working starter template plus updated book chapters showing the new user-facing API.

Stage 4 is contract testing. The `data-pipeline-test/contracts/` subpackage gets a test suite per protocol; each test exercises the documented behaviour of the protocol (e.g., "a `JobControlRepository.create_job` followed by `get_job` returns the same job") without referencing any concrete implementation. The GCP implementations run those tests and pass. This is what makes the abstraction *real*: it forces the protocol authors to spell out the contract in executable form, and it catches abstraction leaks before a non-GCP implementation ever tries to comply. Effort: 1-2 weeks.

Stage 5 is the optional future move: build a non-GCP module to prove the abstraction. Recommend `data-pipeline-aws-s3` because S3 is the simplest of the AWS services to wrap and `BlobStore` is the simplest of the protocols. Building this validates that the protocols are honest. If it takes a week, the design works. If it takes a month, the design needs another iteration. We are not committing to this; we are reserving the option, and the layout makes it cheap to exercise.

Across the whole sequence, the deployment pipelines (Terraform, GitHub Actions, deploy-generic workflow, Composer DAG deployment) are unaffected — they reference Python package names through `requirements.txt`-style files, and the shim distributions keep the old names resolvable through at least one major version. The framework's runtime behaviour does not change at any stage. The framework's user-facing API gains the decorators in stage 3 but does not lose anything before then.

## 8. What we are NOT doing

We are not shipping AWS or Azure modules. The slots are reserved in the naming convention, the protocols are designed to be honest about cloud independence, and the contract test suite makes it possible to validate any future implementation — but the team's commitment is to GCP. Selling the framework as multi-cloud while only shipping GCP modules would be misleading, and writing speculative AWS code that nobody runs in anger would let abstractions drift in directions that fit nobody's real workload. Some abstractions are best validated by *trying* to write the next implementation, not by pre-emptively writing it.

We are not creating a lowest-common-denominator abstraction over warehouses or object stores. The `Warehouse` protocol covers the operations every serious warehouse supports (query, execute, load from URI, merge, copy, table existence) and stops there. BigQuery's clustering, partitioning, materialised views, BI Engine, and slot-aware cost predicates are not in the protocol; they live in `data-pipeline-gcp-bigquery` as a `BigQueryExtensions` interface that users can call directly when they need BigQuery-specific behaviour. The audit's note about partitioning being "BQ-shaped today" stands: we will not water down BigQuery's capabilities to fit Redshift's. If a user wants BigQuery semantics, they call BigQuery extensions explicitly; the framework does not pretend Redshift would do the same thing.

We are not rewriting the existing GCP code. The migration is a rename, a split, and a contract extraction — not a refactor of how `JobControlRepository` queries BigQuery or how the Beam pipelines emit to Pub/Sub. Existing tests will continue to pass against the same code that has been running in production. The audit's verdict — that the GCP-specific implementations are coherent and well-named — is the load-bearing precondition for the migration being a week-scale effort rather than a quarter-scale rewrite. We are not going to invalidate that precondition by changing the GCP code in flight.

We are not pretending the framework is production-ready on AWS or Azure. Until `data-pipeline-aws-*` modules exist and have been run against real workloads, the README and the book will state plainly that GCP is the only supported cloud and that the AWS/Azure slots are architectural reservations. If a customer asks whether they can deploy on AWS, the honest answer is "not yet, but the framework is structured so that an AWS adapter is a 2-4 week build per service rather than a rewrite". That is a defensible answer. "Yes, we support AWS" with no shipped AWS module is not.

We are not making `data-pipeline-core` depend on Google Cloud client libraries. Anywhere in the codebase that today reads `from google.cloud import bigquery` or `from google.cloud import storage` or `from google.cloud import pubsub_v1` either lives in a `data-pipeline-gcp-*` module after the migration or is replaced by an import from a protocol in `data_pipeline_core.contracts`. CI for `data-pipeline-core` includes a static check (`grep -r "google\.cloud" src/`) that fails the build if a GCP import leaks back in. This is the cheapest possible enforcement of the boundary, and it has caught analogous mistakes in Spring projects for two decades.

We are not designing the `RuntimeContext` to be Spring's `ApplicationContext`. Python is not Java; we are taking the *posture* of dependency injection (named components, protocol-typed lookups, lifecycle hooks) without dragging in the full Spring machinery (bean factories, scopes, application events, refresh, profiles, conditional configuration). The simpler model — a dict-shaped context populated by auto-config callables — is enough for a data-pipeline framework and avoids the conceptual surface area of Spring's container that has accumulated over twenty years. If we find later that we need scopes or profiles, we will add them; we will not add them speculatively.

We are not bundling Terraform, GitHub Actions, or Dockerfiles inside Python wheels. The audit noted that today's `gcp-pipeline-framework` package includes these as bundled assets and exposes them via `export_project()`. That stays — it is genuinely useful — but the assets move to a dedicated `data-pipeline-gcp-deployment` distribution rather than living inside `data-pipeline-core`. Python `site-packages` is not the right place to ship Terraform modules. A separate distribution makes it explicit that the infrastructure assets are a GCP-only concern.

## 9. Open questions

These are real decisions with real tradeoffs. The answers shape the next several months of work.

1. **Does `data-pipeline-orchestration-core` cover the full Airflow DAG model or just schedule/retry intent?** Option A: define a cloud-neutral DAG (nodes, edges, retries, triggers) that the Composer module compiles into a real Airflow DAG and that future AWS/Azure modules compile into Step Functions or ADF pipelines. This is the cleanest abstraction but requires the team to maintain a meta-DAG model that nobody runs natively. Option B: keep `orchestration-core` to schedule/retry/timeout config dataclasses only and let each cloud module define its own DAG model. This is honest but means a future AWS module reinvents work that the Composer module already did. Recommendation pending: A, on the basis that the contract test will catch leaks and the Composer compiler is a 1-2 week build.

2. **Should `data-pipeline-quality` integrate with Soda Core, Great Expectations, or neither?** Option A: integrate with Soda Core via a `SodaCheck` adapter under `data-pipeline-quality/integrations/soda.py`. Soda has good momentum in the data quality space and its open-source core is appropriately licensed. Option B: integrate with Great Expectations similarly. GE is older, more widely deployed, more complex. Option C: ship our own dimension checks (already exists in `data_quality/`) and treat Soda/GE as optional adapters that users add if they want. Recommendation pending: C, with stubs for Soda and GE adapters so the integration story is clear without the maintenance burden.

3. **How do we handle the "BigQuery semantics leak"?** Partitioning, clustering, materialised views, and slot-aware cost predicates are BigQuery-specific concepts that today's code uses freely. Option A: expose these as a `BigQueryExtensions` protocol that lives in `data-pipeline-gcp-bigquery` and that users call directly when they need BigQuery-specific behaviour; the cross-warehouse `Warehouse` protocol stays minimal. Option B: add `partitioning` and `clustering` to `Warehouse` and let other warehouses no-op on them, accepting that the abstraction is leaky. Option C: build a "table options" dataclass that warehouses translate into their native equivalents (BigQuery partitioning, Redshift sortkeys, Synapse distribution). Recommendation pending: A. Option C is the most architecturally pure but is also the most likely to produce a hopeless lowest-common-denominator artefact.

4. **What does `Warehouse.load_from_uri` mean when the warehouse is not in the same cloud as the URI?** A BigQuery `load_from_uri` of an S3 URI is technically possible via BigQuery Omni but cost-prohibitive and slow. Option A: declare cross-cloud loads as out of scope; `Warehouse` implementations may reject URIs from foreign schemes. Option B: define a `Stager` protocol that copies between blob stores; the warehouse loads only from same-cloud URIs. Recommendation pending: B, because the staging step is real-world common and worth modelling.

5. **Where does dbt fit?** dbt runs against a warehouse, so it is downstream of `Warehouse`. But dbt has its own profile model, its own project structure, and its own dependency graph that does not fit cleanly inside the framework's pipeline decorators. Option A: treat dbt as a black-box transformation step; pipelines invoke `dbt run` via a `DbtRunner` that the framework wires up but does not understand. Option B: parse dbt's manifest and expose dbt models as `Transform` components in the framework's DAG, allowing fine-grained governance and observability. Option B is much more work but produces a much more unified user experience. Recommendation pending: A for v1, B as a roadmap item — start with the black-box runner, deepen the integration when there is demand.

6. **How do auto-configs handle conflicts?** If a user installs both `data-pipeline-gcp-bigquery` and a hypothetical `data-pipeline-snowflake-warehouse`, both will try to register a `Warehouse` implementation. Option A: last-registered wins (matches Python module import order — fragile). Option B: registration is explicit per-protocol and the user picks via config (`runtime.warehouse: bigquery`). Option C: per-pipeline override via `@pipeline(warehouse="bigquery")`. Recommendation pending: B as the default plus C for per-pipeline override.

7. **What is the minimum Python version?** The audit does not say. Spring-style decorators benefit from `typing.ParamSpec` (3.10+), `Protocol` with `@runtime_checkable` (3.8+, mature 3.10+), and PEP 604 union syntax (3.10+). Composer 2.x runs Python 3.8; Composer 3.x runs 3.11. Option A: target 3.10+ and require Composer 3 for orchestration. Option B: support 3.8+ and avoid the newer typing features. Recommendation pending: A. Composer 3 is GA, the typing improvements are worth it, and three-year-old Python releases are not a constituency we owe support to.

8. **Where does configuration validation live?** Pydantic v2 is the obvious choice for validating `pipeline.yaml` and the `EntitySchema` model, but pydantic is a heavy dependency for `data-pipeline-core` and pulls in `pydantic-core` (compiled Rust). Option A: use pydantic v2 in core. Option B: use `dataclasses` + a hand-written validator in core; offer pydantic models as an optional extra (`data-pipeline-core[pydantic]`). Recommendation pending: A. The dependency is unobjectionable in 2026 and the validation quality is worth the install footprint.
