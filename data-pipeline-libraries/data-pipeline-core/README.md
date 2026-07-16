# data-pipeline-core

The cloud-neutral kernel of the Culvert data pipeline framework. Contains the framework's contracts (Python Protocols), the dataclass/enum/TypedDict types those contracts reference, and nothing else. Zero dependencies on `google.cloud.*`, `boto3`, or `azure.*`.

## Status

**Released** — published to PyPI as part of the [`culvert`](https://pypi.org/project/culvert/) distribution. The Protocols here are the framework's contract set; the `data-pipeline-gcp-*` adapter packages implement them and self-register via entry points (see `autoconfig.py`). The design rationale lives in `docs/framework-evolution/02-redesign.md`.

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
3. **Implementations register themselves.** Each cloud package registers its adapters as `data_pipeline_core.adapters` entry points; `autoconfig.discover()` finds every installed implementation. Core does not import the cloud module.

## What's in the package

- `data_pipeline_core/contracts/` — the contract Protocols (plus the `StageMetrics` record).
- `data_pipeline_core/{audit,lineage,finops_api,governance_api,job_control_api,schema}/` — the dataclasses, enums, and TypedDicts the Protocols reference.
- `autoconfig.py`, `runtime.py`, `decorators.py` — discovery (entry-point registry), the runtime context, and the `@pipeline`/`@source`-style decorators.

## What's NOT in the package

- Any concrete implementation of any Protocol. Those live in the `data-pipeline-gcp-*` adapter packages, installed via the `culvert[gcp]` extra.

## License

MIT — see [LICENSE](../../LICENSE) at the repository root.
