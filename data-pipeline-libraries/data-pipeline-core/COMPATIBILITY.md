# Protocol Compatibility — data-pipeline-core 0.1.0 vs existing gcp-pipeline-* code

Stage 0 of the framework redesign (see `docs/framework-evolution/02-redesign.md`) defines the **target shape** of the eleven Protocols. It does not refactor any existing code to satisfy them.

This document is the per-Protocol gap analysis that Stage 2 (move GCP-coupled files out of core) consumes. For each Protocol it captures: which existing class is the GCP reference implementation, how the existing public surface differs from the Protocol, and what Stage 2 must do to close the gap.

Source-of-truth file paths are relative to the repo root.

---

## JobControlRepository

**Reference impl:** `gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/job_control/repository.py`

**Match:** Strong. All eleven public method signatures already match the Protocol with no GCP type leakage in arguments or return types (the BigQuery client is constructed internally from the constructor's `project_id`/`dataset`/`table` args). The existing dataclasses (`PipelineJob`, `JobStatus`, `FailureStage`, `JobType`) are structurally identical to the ones in `data_pipeline_core.job_control_api`.

**Stage 2 work:**

1. Move the file to `data-pipeline-gcp-bigquery/bigquery_job_control_repository.py`. No method-signature changes.
2. Add a `from data_pipeline_core.contracts.job_control import JobControlRepository` import and an inheritance/structural-subtype declaration (`class BigQueryJobControlRepository(JobControlRepository):` works because the Protocol is `@runtime_checkable`).
3. Adopt the three new TypedDicts (`EntityStatus`, `FailedJob`, `FdpJobStatus`) on the three methods that currently return `List[dict]` (`get_entity_status`, `get_failed_jobs`, `get_fdp_job_status`). The returned dict shapes are already what the TypedDicts spell out.

**Risk:** Low. Pure file move + import update.

---

## Warehouse

**Reference impl:** `gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/clients/bigquery_client.py`

**Match:** Weak. Only 2 of the 6 Protocol methods (`query`, `table_exists`) have a corresponding method on the existing `BigQueryClient`, and even those have signature mismatches:

- `query(self, sql: str) -> pd.DataFrame` vs Protocol `query(sql, params=None) -> Iterator[Mapping[str, Any]]` — DataFrame return is pandas-coupled; missing params support.
- `table_exists(table_id: str, dataset: str = None) -> bool` vs Protocol `table_exists(fqtn: str) -> bool` — uses split args instead of a single FQTN.

Missing on `BigQueryClient`: `execute`, `load_from_uri`, `merge`, `copy`.

Extra on `BigQueryClient` (NOT on the Protocol by design): `write_to_table(table_id, data: List[dict])`, `read_table(...) -> pd.DataFrame`. These stay on the implementation, not the Protocol — they are BigQuery-shaped (DataFrame is pandas; `write_to_table` takes a record list whose semantics differ across warehouses).

**Stage 2 work:**

1. Build a new `BigQueryWarehouse` class in `data-pipeline-gcp-bigquery/warehouse.py` that wraps `bigquery.Client` and satisfies the six Protocol methods.
2. Implement `query` to stream rows via `Client.query(sql, job_config=QueryJobConfig(query_parameters=...)).result()` — yielding row dicts, not pandas DataFrames.
3. Implement `load_from_uri` over `Client.load_table_from_uri(uri, table_ref, job_config=LoadJobConfig(schema=schema, ...))`.
4. Implement `merge` and `copy` as DDL via `execute`.
5. Keep the existing `BigQueryClient` as-is for the duration of Stage 2 — it has callers in the Beam package. The new `BigQueryWarehouse` is additive.
6. `write_to_table` and `read_table` move into a sibling `BigQueryExtensions` class in the same package, expressing the BigQuery-shaped operations that don't fit the Protocol.

**Risk:** Medium. Real new code in `BigQueryWarehouse`. Pandas dependency moves to `data-pipeline-gcp-bigquery`.

---

## BlobStore

**Reference impl:** `gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/clients/gcs_client.py`

**Match:** Method names diverge, types diverge:

| Protocol | Existing | Diff |
|---|---|---|
| `get(uri) -> bytes` | `read_file(bucket, path) -> str` | name + arg split + returns str not bytes |
| `put(uri, data: bytes)` | `write_file(bucket, path, content: str) -> bool` | name + arg split + str not bytes |
| `list(prefix) -> Iterator[str]` | `list_files(bucket, prefix="") -> List[str]` | name + arg split + List not Iterator |
| `exists(uri) -> bool` | `blob_exists(gcs_uri) -> bool` | name only |
| `copy(src, dst)` | `archive_file(bucket, source_path, archive_path) -> bool` | semantically narrower (archive, not generic copy) |
| `delete(uri)` | (none) | missing |
| `open(uri, mode) -> BinaryIO` | (none) | missing |

Critical bug surfaced during analysis: `gcp_pipeline_core/utilities/gcs_discovery.py` calls a non-existent `list_prefix()` method on the GCS client (line ~47 and ~75). This is **broken in main today** and will fail at runtime in any code path that exercises discovery. Tracked in Stage 2; **not fixed in Stage 0** (different scope).

**Stage 2 work:**

1. Build a new `GCSBlobStore` class in `data-pipeline-gcp-gcs/blob_store.py` that wraps `google.cloud.storage.Client` and satisfies the seven Protocol methods. Parses `gs://bucket/path` URIs internally.
2. Implement `get` returning bytes (call `Blob.download_as_bytes()`), `put` accepting bytes (`Blob.upload_from_string(data, content_type=...)`).
3. Implement `list` as a generator over `Bucket.list_blobs(prefix=...)`.
4. Implement `delete` (currently used inside `archive_file`).
5. Implement `open` over `Blob.open(mode)` (the GCS client already supports streaming handles).
6. Keep the existing `GCSClient` as a Stage 1 deprecation shim that re-exports a `GCSBlobStore` wrapper with the old method names + DeprecationWarning.
7. Fix the `list_prefix` bug in `gcs_discovery.py` while moving it to `data-pipeline-gcp-gcs/discovery.py` — refactor to take a `BlobStore` injection instead of a concrete `GCSClient`.

**Risk:** Medium. Type changes (str -> bytes) ripple through callers; need to verify the `hdr_trl/parser.py` callsite that reads file content.

---

## AuditEventPublisher

**Reference impl:** `gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/audit/publisher.py`

**Match:** Close.

- `publish(self, record: AuditRecord) -> str` vs Protocol `publish(record) -> None` — return type differs; Pub/Sub message ID dropped.
- No `flush()` method exists today (publisher is stateless).

**Stage 2 work:**

1. Move the file to `data-pipeline-gcp-pubsub/pubsub_audit_publisher.py`.
2. Drop the return value of `publish()` (the Pub/Sub message ID is captured internally for diagnostic logging, not returned).
3. Add a no-op `flush()` method (the publisher buffers nothing today; `flush()` is a contractual guarantee, not a behavioural one).

**Risk:** Low.

---

## LineageEmitter

**Reference impl:** `gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/audit/lineage.py`

**Match:** Shape only.

`DataLineageTracker.generate_data_lineage(audit_record: AuditRecord) -> Dict[str, Any]` is a **static method** that returns a dict with `source`/`pipeline`/`destination`/`audit` sub-dicts. It does not emit anywhere — the caller is expected to forward the dict.

**Stage 2 work:**

1. Refactor `DataLineageTracker` into an instance class with an `emit(event: LineageEvent) -> None` method.
2. Move the dict-generation logic into a `build_event_from_audit_record(record)` helper (cloud-neutral).
3. The default implementation in `data-pipeline-core.lineage.OpenLineageEmitter` (Stage 3) targets Marquez/OpenLineage Proxy via HTTP.
4. The GCP implementation `data_pipeline_gcp_dataplex.DataplexLineagePublisher` targets Dataplex Lineage API.

**Risk:** Low. Logic stays the same; surface changes.

---

## ObservabilityHook

**Reference impl:** Split across `gcp_pipeline_core.monitoring.observability`, `monitoring.metrics`, `monitoring.otel.*`.

**Match:** Distributed.

- Metrics: `MetricsCollector.{increment, set_gauge, record_histogram, record_timer}` — names differ from Protocol's `{counter, gauge, histogram, ...}` (no histogram timer split).
- Logging: `StructuredLogger` in `utilities/logging.py` — has a `log(level, message, **fields)` method that matches.
- Tracing: `monitoring/otel/tracing.py` has `OTELContext` context manager — matches `span` shape.

Monolithic vs split: the existing code splits, the Protocol is monolithic. This is a deliberate redesign decision (see redesign section 8 + the advisor consult that landed this Protocol shape).

**Stage 2 work:**

1. Build a new `CompositeObservabilityHook` in `data-pipeline-core.observability_api` that delegates to `MetricsCollector`, `StructuredLogger`, and the OTEL bridge internally. Single user-facing dependency, three internal backends.
2. Add a `counter(name, value, tags)` method that adapts to `MetricsCollector.increment(name, value, labels)`. Same for `gauge` -> `set_gauge`, `histogram` -> `record_histogram`.
3. Wire `log()` through to `StructuredLogger`.
4. Wire `span()` through to `OTELContext`.

**Risk:** Low-medium. Adapter, no new logic.

---

## FinOpsSink

**Reference impl:** None. `gcp_pipeline_core.finops.tracker` produces `CostMetrics` but does not record them anywhere.

**Match:** Net-new Protocol filling a real gap.

**Stage 2 work:**

1. Build `BigQueryFinOpsSink` in `data-pipeline-gcp-bigquery/finops_sink.py`. Writes `(CostMetrics, FinOpsTag)` pairs to a `cost_metrics` table.
2. Add a CloudWatch-equivalent slot reserved for `data-pipeline-aws-finops` (future, not now).

**Risk:** Low. New code, no existing behaviour to preserve.

---

## GovernancePolicy

**Reference impl:** None. `gcp_pipeline_beam.pipelines.beam.transforms.pii` has masking algorithms but no policy lookup; Dataplex integration is buried in Composer DAGs.

**Match:** Net-new Protocol.

**Stage 2 work:**

1. Build `StaticGovernancePolicy` in `data-pipeline-core/runtime/static_governance.py` — reads policies from a YAML file shipped with the pipeline project. Default for any project that hasn't adopted Dataplex/Glue/Purview.
2. Build `DataplexGovernancePolicy` in `data-pipeline-gcp-dataplex/governance.py` (Stage 2+).
3. Extract masking algorithms from `transforms/pii.py` into `data-pipeline-governance/masking.py` so they're decoupled from Beam.

**Risk:** Low to medium. The masking-algorithm extraction needs careful test coverage to ensure behaviour parity.

---

## SecretProvider

**Reference impl:** `gcp-pipeline-libraries/gcp-pipeline-orchestration/src/gcp_pipeline_orchestration/hooks/secrets.py`

**Match:** Close.

- `get_secret(secret_id: str, project_id: Optional[str] = None, version_id: str = "latest") -> str` vs Protocol `get(name, version="latest")` — method rename + arg renames + drop `project_id` (moves to constructor).

**Stage 2 work:**

1. Move the hook to `data-pipeline-gcp-secrets/secret_manager_provider.py`.
2. Rename `get_secret` -> `get`, `secret_id` -> `name`, `version_id` -> `version`.
3. Move `project_id` to the constructor (set once when the provider is registered with the runtime, not threaded through every call).
4. Build `EnvSecretProvider` in `data-pipeline-core/runtime/env_secrets.py` as the default — reads from `os.environ`.

**Risk:** Low.

---

## Pipeline, PipelineStage, RuntimeContext, Source, Sink, Transform

**Reference impl:** Indirect — `BasePipeline` in `gcp_pipeline_beam.pipelines.base.pipeline` is the closest, but it's imperative (`build(beam_pipeline)`/`run()`), not declarative (a graph of stages).

**Match:** Net-new abstractions.

**Stage 3 work:** These Protocols are not satisfied by any existing class. Stage 3 adds:

1. A concrete `RuntimeContextImpl` in `data_pipeline_core.runtime` (the DI container — a dict of `Type -> impl` plus the eight named fields).
2. The `@pipeline`/`@source`/`@transform`/`@sink` decorators that turn a decorated class into a `Pipeline` satisfying the Protocol (with auto-generated `PipelineStage` nodes from the methods).
3. Adapters in `data-pipeline-gcp-dataflow` that wrap a `Source`/`Sink`/`Transform` into a Beam `ParDo`. The existing Beam DoFns keep running unchanged.

**Risk:** Medium-high — this is the bulk of the design work in Stage 3 and the user-facing API. Not blocking for Stages 1 and 2.

---

## Summary table — Stage 2 effort estimate

| Protocol | Effort | Risk |
|---|---|---|
| `JobControlRepository` | 0.5 day | Low |
| `AuditEventPublisher` | 0.5 day | Low |
| `LineageEmitter` | 1 day | Low |
| `SecretProvider` | 0.5 day | Low |
| `GovernancePolicy` | 2 days | Low-medium |
| `FinOpsSink` | 1 day | Low |
| `ObservabilityHook` | 2 days | Low-medium |
| `Warehouse` | 3-4 days | Medium |
| `BlobStore` | 3 days | Medium |
| `Pipeline` / `Source` / `Sink` / `Transform` / `RuntimeContext` | Stage 3 | n/a |
| **Total (Stage 2)** | **13-14 engineer-days** | **Mostly Low-Medium** |

The redesign's "2-3 weeks" estimate for Stage 2 lines up with the bottom-up estimate above (≈ 13-14 engineer-days + integration/test/CI work = ~3 weeks).
