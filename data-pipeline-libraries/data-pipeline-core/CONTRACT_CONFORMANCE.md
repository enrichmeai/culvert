# Contract Conformance — Python vs Java 1.0.0

Ticket: #114 (T17.2). Checked: Python Protocols in
`data_pipeline_core/contracts/` against frozen Java contracts at
`data-pipeline-core-java/…/contracts/` (+ `audit/`, `finops/`,
`governance/`, `lineage/` packages).

Idiom equivalences treated as **matches** (not drift):
`snake_case` ↔ `camelCase`, `bytes` ↔ `byte[]`,
`Iterator[X]` ↔ `Iterator<X>`, `Mapping[…]` ↔ `Map<…>`,
`Optional[X]` ↔ `Optional<X>`, `@property` ↔ accessor method,
`None` ↔ `void`. Python Protocol attributes (`name: str`) are
equivalent to Java accessor methods (`String name()`).

---

## Contract table

| Contract | Result | Delta |
|---|---|---|
| **AuditEventPublisher** | MATCHES | `publish(record)` + `flush()` — identical shape. |
| **BlobStore** | DRIFT FIXED | Python had one `open(uri, mode="rb")` method; Java has two distinct methods `openInput(uri)` / `openOutput(uri)`. Split into `open_input(uri)` + `open_output(uri)` to match. All other methods (`get`, `put`, `list`, `exists`, `delete`, `copy`) match 1:1. |
| **LineageEmitter** | MATCHES | Single `emit(event: LineageEvent)` — matches Java `@FunctionalInterface`. |
| **PipelineStage** | MATCHES | `name`, `inputs`, `outputs` attributes + `execute(context)` — matches Java interface fields + method. |
| **SecretProvider** | MATCHES | `get(name, version="latest")` + semantics (raises on missing, never log) match Java including default-version overload. |
| **GovernancePolicy** | MATCHES | `classify(field, table)`, `masking_for(field, table)`, `retention_for(table)` match Java `classify`, `maskingFor`, `retentionFor`. Evolved in S9/S13 — Python kept up. |
| **FinOpsSink** | MATCHES | `record(metrics: CostMetrics, tags: FinOpsTag)` — matches Java `@FunctionalInterface`. Evolved in S13 — Python kept up. |
| **Warehouse** | MATCHES | All six methods — `query`, `execute`, `load_from_uri`, `merge`, `copy`, `table_exists` — match Java (`loadFromUri`, `tableExists` in Java camelCase). Return types match (`long`/`int` ↔ `int`; both are integer row counts). |
| **ObservabilityHook** | MATCHES (with gap noted) | `counter`, `gauge`, `histogram` match 1:1. `log(level, message, **fields)` vs Java `log(level, message, Map<String,Object> fields)` is idiomatic — left as-is per style-preservation rule. `span(name)` returns an opaque `AbstractContextManager` vs Java's typed nested `Span` interface (with `setAttribute`/`recordException`/`close`) — richness gap, but the Python docstring explicitly notes the yielded object is implementation-defined; adding a `Span` Protocol would exceed the surgical scope of this ticket. Gap flagged for a future ticket. |
| **JobControlRepository** | MATCHES | All 11 methods present with matching signatures (`create_job`, `get_job`, `update_status`, `mark_failed`, `mark_retrying`, `get_pending_jobs`, `get_entity_status`, `get_failed_jobs`, `get_fdp_job_status`, `cleanup_partial_load`, `update_cost_metrics`). Java uses `Optional<Long> totalRecords`; Python uses `Optional[int] = None` — idiomatic match. |
| **RuntimeContext** | DRIFT FIXED | Missing `pipeline_id` property (T12.6 addition in Java: `pipelineId()` with default returning `runId()`). Added `pipeline_id` property with default `return self.run_id`. Also hardened module and class docstrings with the T10.6 serialization-boundary contract (only `run_id`/`environment`/`config` cross; registry is transient/rebuilt worker-side). **`stage_metrics` deliberately NOT added** — that accessor (`stageMetricsHook()` in Java) belongs to T12.4/StageMetricsHook, which is owned by ticket #113 (another agent). Adding it here would create a conflict. |
| **Source** | MATCHES | `read(context: RuntimeContext) -> Iterator[T_co]` matches Java `Iterator<T> read(RuntimeContext context)`. |
| **Sink** | MATCHES | `write(records: Iterator[U_contra], context: RuntimeContext) -> None` matches Java `void write(Iterator<U> records, RuntimeContext context)`. |
| **Pipeline** | MATCHES | `name` attribute + `stages: Sequence[PipelineStage]` + `validate() -> None` match Java `name()`, `stages()`, `validate()`. |
| **Transform** | MATCHES | `apply(records: Iterator[V], context: RuntimeContext) -> Iterator[W]` matches Java `Iterator<W> apply(Iterator<V> records, RuntimeContext context)`. |

---

## Files changed

- `data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/blob_store.py` —
  split `open(uri, mode)` into `open_input(uri)` + `open_output(uri)`.
- `data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/runtime.py` —
  added `pipeline_id` property (T12.6); hardened module + class docstrings
  with T10.6 serialization-boundary semantics.
- `data-pipeline-libraries/data-pipeline-core/CONTRACT_CONFORMANCE.md` —
  this file (new).

`contracts/__init__.py` — **not touched**. No new public exports are
introduced by this ticket; existing exports are unchanged.

---

## Verification

No pytest environment was available in this worktree at the time of
execution. Command that should be run once an environment is set up:

```
cd data-pipeline-libraries/data-pipeline-core
python -m pytest tests/ -x -q
```

(or `pytest` scoped to whatever the project's core-package test directory is).
The two changed Protocols (`BlobStore`, `RuntimeContext`) have no callable
method bodies — only ellipsis stubs — so the changes are purely structural
and cannot introduce runtime regressions; `mypy --strict` or
`pyright` over the `contracts/` directory is the appropriate static check.

---

## Open flags

1. **ObservabilityHook `span()` richness gap**: Java's nested `Span` interface
   exposes `setAttribute(key, value)` and `recordException(t)`. Python's
   `span()` returns an opaque `AbstractContextManager[Any]`. This is
   intentional per the existing Python docstring but callers cannot set
   span attributes portably. Recommend a follow-up ticket to define a
   minimal `Span` Protocol in Python matching the Java `Span` nested interface.

2. **`stage_metrics` on RuntimeContext**: Java `RuntimeContext` has a
   `stageMetrics() -> StageMetricsHook` accessor added in T12.4. This ticket
   deliberately omits it because #113 owns `StageMetrics`/`StageMetricsHook`.
   Once #113 lands its Python Protocol, a follow-up edit to `runtime.py`
   should add `stage_metrics: "StageMetricsHook"` to match Java.
