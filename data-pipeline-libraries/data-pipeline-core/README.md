# data-pipeline-core

The cloud-neutral kernel of the Culvert data pipeline framework. Contains the framework's contracts (Python Protocols), the dataclass/enum/TypedDict types those contracts reference, and nothing else. Zero dependencies on `google.cloud.*`, `boto3`, or `azure.*`.

## Status

**Version 0.1.0 — Stage 0 of the framework redesign.** The Protocols define the *target shape* of the framework. The existing `gcp-pipeline-*` packages have not yet been refactored to satisfy these contracts; see `COMPATIBILITY.md` for the per-Protocol gap analysis that drives Stage 2 of the migration (`docs/framework-evolution/02-redesign.md`).

## Install

```bash
pip install data-pipeline-core
```

This package is intentionally tiny. It is meant to be installed alongside one or more cloud-specific modules (`data-pipeline-gcp-bigquery`, `data-pipeline-gcp-gcs`, `data-pipeline-gcp-pubsub`, ...) that provide concrete implementations of the Protocols.

## The contracts

Eleven Protocols are the entire framework-to-cloud seam:

| Protocol | Purpose | Default impl (when none provided) |
|---|---|---|
| `Source[T]` | Yields records into the pipeline | none — must be supplied per pipeline |
| `Sink[U]` | Writes records out of the pipeline | none — must be supplied per pipeline |
| `Transform[V, W]` | Maps records V to W | none — must be supplied per pipeline |
| `Pipeline` | A graph of `PipelineStage` nodes | none — the user's class |
| `PipelineStage` | A named, dependency-aware stage | derived from `@source`/`@transform`/`@sink` decorators (Stage 3) |
| `RuntimeContext` | The framework's DI container + run metadata | concrete implementation in `data-pipeline-core.runtime` (Stage 3) |
| `JobControlRepository` | Pipeline-job state machine | `BigQueryJobControlRepository` (in `data-pipeline-gcp-bigquery`) |
| `BlobStore` | Object storage abstraction | `GCSBlobStore` (in `data-pipeline-gcp-gcs`) |
| `Warehouse` | Tabular query/load abstraction | `BigQueryWarehouse` (in `data-pipeline-gcp-bigquery`) |
| `AuditEventPublisher` | Emits audit records | `PubSubAuditPublisher` (in `data-pipeline-gcp-pubsub`) |
| `GovernancePolicy` | Masking/retention/classification lookups | `StaticGovernancePolicy` (yaml-driven, cloud-neutral default) |
| `LineageEmitter` | Publishes OpenLineage events | `OpenLineageEmitter` (cloud-neutral default) |
| `ObservabilityHook` | The single observability seam (metrics/logs/traces) | `OTELObservabilityHook` (cloud-neutral default) |
| `FinOpsSink` | Cost-metric aggregation | `BigQueryFinOpsSink` (in `data-pipeline-gcp-bigquery`) |
| `SecretProvider` | Secret lookup | `EnvSecretProvider` (cloud-neutral default) |

## Architectural rules

1. **No cloud SDK imports.** Anywhere in this distribution that needs to talk to a cloud, it does so through one of the Protocols. CI fails the build if `grep -r "google\.cloud\|boto3\|azure\." src/` finds anything.
2. **Protocols are small.** Each contract covers the operations every serious cloud supports and stops there. Cloud-specific extensions (BigQuery clustering, S3 lifecycle, ADLS hierarchical namespaces) live in the cloud-specific module as extension classes, not in core.
3. **Implementations register themselves.** A cloud module's `auto_config.py` (added in Stage 3) calls `runtime.register(Warehouse, BigQueryWarehouse(...))` at bootstrap time. Core does not import the cloud module.

## What's in v0.1.0 (Stage 0)

- `data_pipeline_core/contracts/` — the eleven Protocols.
- `data_pipeline_core/{audit,lineage,finops_api,governance_api,job_control_api,schema}/` — the dataclasses, enums, and TypedDicts the Protocols reference.
- `COMPATIBILITY.md` — per-Protocol gap analysis against existing `gcp-pipeline-*` code.

## What's NOT in v0.1.0

- The runtime container, decorators (`@pipeline`, `@source`, etc.), and auto-config registry. Those land in Stage 3.
- Any concrete implementation of any Protocol. Those live in the `data-pipeline-gcp-*` packages (Stages 2-3).
- The cloud-neutral helpers (run-id generation, structured logging, blob discovery against a `BlobStore`) currently in `gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/utilities/`. Those migrate in Stage 1.

## License

MIT — see [LICENSE](../../LICENSE) at the repository root.
