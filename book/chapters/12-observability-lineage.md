# Chapter 12 — Observability and Lineage

\index{observability}A lot of teams mistake "observability" for "three Cloud
Monitoring dashboards and a Slack alert". I made that mistake myself, early on.
You wire up a counter for records processed, a gauge for queue depth, and you
feel good about it. Then something goes wrong at 03:00 — a suspicious revenue
figure, a reconciliation that doesn't close — and you discover the dashboards
tell you *what* without a shred of *why*. The run that produced the bad row had
a trace ID no one wrote down. The log lines are in Cloud Logging but there's no
consistent field to filter on. The Dataflow job succeeded; the data is wrong.
Congratulations, you have three dashboards and zero observability.

Culvert's view is different. Observability means being able to answer, about any
point in the pipeline's history: *what happened, why, how much did it cost, who
was affected, and can I reproduce it?* Answering that requires a single thread of
identity — a `run_id` — that ties every log line, every metric point, every trace
span, and every lineage event to the same run. Everything else is plumbing to
get that thread into the right places.

This chapter covers the plumbing: the two observability contracts, the four GCP
adapters that implement them, the structured-log bridge that writes context into
every log line automatically, and the lineage seam that stamps Data Catalog when
a stage completes. The seams are cloud-neutral; the adapters are GCP-specific and
live behind them. Swap the adapters, keep the pipeline code, take your `run_id`
thread to AWS or Azure.

## Two seams, not one

The observability surface in Culvert v0.1.0 splits across two contracts, and the
distinction matters.

**`ObservabilityHook`** is the general-purpose primitive. It exposes five
methods: `counter`, `gauge`, `histogram`, `log`, and `span`. Pipeline code has
one dependency to inject rather than three separate objects (a metrics collector,
a logger, a tracer). The contract is defined in both Java and Python, with
identical semantics in each language.

```java
// data-pipeline-core-java: ObservabilityHook.java:20
public interface ObservabilityHook {
    void counter(String name, long value, Map<String, String> tags);
    void gauge(String name, double value, Map<String, String> tags);
    void histogram(String name, double value, Map<String, String> tags);
    void log(String level, String message, Map<String, Object> fields);
    Span span(String name);
}
```

Python mirrors it as a `@runtime_checkable` Protocol so that structural
subtyping (`isinstance` checks) works without inheritance:

```python
# data-pipeline-core: contracts/observability.py:26
@runtime_checkable
class ObservabilityHook(Protocol):
    def counter(self, name: str, value: int = 1,
                tags: Mapping[str, str] = _NO_TAGS) -> None: ...
    def gauge(self, name: str, value: float,
              tags: Mapping[str, str] = _NO_TAGS) -> None: ...
    def histogram(self, name: str, value: float,
                  tags: Mapping[str, str] = _NO_TAGS) -> None: ...
    def log(self, level: str, message: str, **fields: Any) -> None: ...
    def span(self, name: str) -> AbstractContextManager[Any]: ...
```

`ObservabilityHook` is intentionally general: arbitrary metric names, arbitrary
tags, arbitrary log fields. That generality is a feature for pipeline code that
just wants to emit something. It is a liability for the *framework* itself, which
needs to guarantee that the same three metrics appear on every stage completion
with the same label schema so Cloud Monitoring dashboards do not drift.

That is why there is a second contract.

**`StageMetricsHook`** is narrow by design. One method, one value type, three
fixed metrics, three fixed label dimensions:

```java
// data-pipeline-core-java: StageMetricsHook.java:32
public interface StageMetricsHook {
    void recordStageMetrics(StageMetrics metrics);
}
```

`StageMetrics` is a Java record
(`data-pipeline-core-java: StageMetrics.java:26`) carrying exactly
`pipelineId`, `runId`, `stageName` (the labels) and `rowsProcessed`,
`stageLatencyMs`, `errorCount` (the values). You cannot mis-name a label;
you cannot forget a field. The contract's Javadoc makes the intent explicit:
narrowness enables type-safe constructors, clear mock-based testing, and
prevents callers from accidentally creating metric series with ad-hoc label
shapes that break dashboard queries.

The two contracts live in `data-pipeline-core-java` with no GCP or Beam
imports. The GCP adapters live in `data-pipeline-gcp-observability-java`. This
is the standard Culvert layering: contracts in the neutral kernel, adapters
behind them, Beam wiring in a separate module.

## `CloudTraceObservabilityHook` — spans, metrics, and logs in one object

\index{CloudTraceObservabilityHook}The GCP implementation of `ObservabilityHook`
is `CloudTraceObservabilityHook`
(`data-pipeline-gcp-observability-java/src/main/java/com/enrichmeai/culvert/gcp/observability/CloudTraceObservabilityHook.java`).
It bridges the Culvert `ObservabilityHook` surface to OpenTelemetry.

The class deliberately does no OTel SDK wiring itself. The design note in the
Javadoc (`CloudTraceObservabilityHook.java:29`) is worth quoting:

> Wiring is decoupled from this class: callers construct an `OpenTelemetry`
> instance whose `SdkTracerProvider` has a `TraceExporter` from
> `com.google.cloud.opentelemetry:exporter-trace` registered (typically via a
> `BatchSpanProcessor`). This class wraps the resulting `Tracer` and `Meter`
> and bridges them to the Culvert `ObservabilityHook` surface.

This matches the graceful-degradation idiom I described earlier. If a full GCP
OTel SDK is wired, spans go to Cloud Trace and metrics go to Cloud Monitoring.
If only the no-op global OTel is installed — which is the default when no SDK
is on the classpath — the hook is still instantiable and every call is a
no-op. No crash, no missing dependency, no conditional import. The pipeline runs
identically; it just does not produce traces.

The three constructors reflect three use cases
(`CloudTraceObservabilityHook.java:113–143`):

```java
// No-arg: ServiceLoader / GlobalOpenTelemetry — graceful no-op if OTel absent
public CloudTraceObservabilityHook() {
    this(io.opentelemetry.api.GlobalOpenTelemetry.get(), DEFAULT_INSTRUMENTATION_SCOPE);
}

// Primary: caller supplies a configured OTel instance and pipeline name
public CloudTraceObservabilityHook(OpenTelemetry otel, String instrumentationScope) { ... }

// Test: inject pre-resolved Tracer and Meter directly
public CloudTraceObservabilityHook(Tracer tracer, Meter meter) { ... }
```

The no-arg constructor enables `ServiceLoader` discovery so Beam workers pick
up the hook automatically when the module is on the classpath — a pattern
introduced in Sprint 12 (T12.6, issue #91) and proven by
`WorkerSideHookResolutionTest.java:105`.

Internally, OTel instruments are lazily created and cached by name in
`ConcurrentHashMap`s
(`CloudTraceObservabilityHook.java:91–93`). Re-registration would be expensive
and would create duplicate metric IDs in Cloud Monitoring; the caches keep
metric identities stable across calls.

One honest rough edge: the gauges implementation uses a single-shot
`DoubleHistogram` rather than a true synchronous gauge
(`CloudTraceObservabilityHook.java:155–163`). The comment explains it:
OTel 1.38 does not have a synchronous-gauge instrument; the 1.40+ `gaugeBuilder`
API is the right fix once the SDK is bumped. The histogram workaround works
but will look odd in Cloud Monitoring — a gauge plotted as a distribution.
Something to clean up before the coordinated Maven Central release.

Spans are returned as an `OtelSpanAdapter`
(`CloudTraceObservabilityHook.java:234`), which wraps the OTel
`Span`+`Scope` pair and is idempotent on `close()`. Try-with-resources works;
double-close is a no-op rather than throwing. Lifecycle for flushing the
`BatchSpanProcessor` on shutdown belongs to whoever built the SDK — the hook
itself is not `AutoCloseable` because the wrapped `OpenTelemetry` interface
makes no lifecycle promise.

## `CloudMonitoringMetricsHook` — the typed metrics seam

\index{CloudMonitoringMetricsHook}Where `CloudTraceObservabilityHook` is
general-purpose, `CloudMonitoringMetricsHook`
(`CloudMonitoringMetricsHook.java:92`) is the typed implementation of
`StageMetricsHook`. It emits exactly three Cloud Monitoring custom metrics per
stage completion via the v3 `MetricServiceClient`:

| Metric type | Kind | Value type |
|---|---|---|
| `custom.googleapis.com/culvert/rows_processed` | CUMULATIVE | INT64 |
| `custom.googleapis.com/culvert/stage_latency_ms` | GAUGE | DOUBLE |
| `custom.googleapis.com/culvert/error_count` | CUMULATIVE | INT64 |

All three carry labels `pipeline_id`, `run_id`, `stage_name` — drawn directly
from the `StageMetrics` record. One `CreateTimeSeries` RPC carries all three
`TimeSeries` objects in a single round-trip
(`CloudMonitoringMetricsHook.java:243–255`).

The contract's resilience rule is enforced here: if the RPC fails, the
exception is caught, logged at `WARN`, and swallowed. The pipeline never stops
because Cloud Monitoring is having a bad morning. The failure count is
accessible via `monitoringFailureCount()` (`CloudMonitoringMetricsHook.java:263`)
for tests and operational alerting.

Project-ID resolution follows a three-step precedence chain
(`CloudMonitoringMetricsHook.java:167–189`):

1. System property `culvert.gcp.project`
2. Environment variable `CULVERT_GCP_PROJECT`
3. ADC default via `com.google.cloud.ServiceOptions.getDefaultProjectId()`

On a Dataflow worker, ADC is always present and the metadata server provides the
project. In a test you set the system property. In a CI environment you set the
environment variable. The hook throws `IllegalStateException` with a diagnostic
message if none of the three yields a value — no silent failure, no metric loss
into the void with no explanation.

The `AutoCloseable` implementation closes the wrapped `MetricServiceClient`
(`CloudMonitoringMetricsHook.java:272`), mirroring the `DataCatalogLineageEmitter`
lifecycle contract. Resources transfer on construction; whoever builds the hook
is responsible for closing it, typically via try-with-resources in the stage
runner.

## `CulvertMdcPopulator` — structured-log correlation without ceremony

\index{CulvertMdcPopulator}\index{structured logging}The best observability
infrastructure is the kind pipeline engineers never have to think about. The
worst outcome is a `run_id` that engineers have to manually thread through every
logging call, and which is inevitably missing from 20% of log lines because
someone forgot.

`CulvertMdcPopulator`
(`CulvertMdcPopulator.java:44`) solves this with a static utility that writes
the three Culvert context fields into the SLF4J MDC for the duration of a stage
body, then clears them in a `finally` block:

```java
// CulvertMdcPopulator.java:77
public static <T> T withStageContext(
        String runId,
        String stageName,
        String pipelineId,
        Supplier<T> body) {

    MDC.put(RUN_ID_KEY, runId);
    MDC.put(STAGE_NAME_KEY, stageName);
    MDC.put(PIPELINE_ID_KEY, pipelineId);
    try {
        return body.get();
    } finally {
        MDC.remove(RUN_ID_KEY);
        MDC.remove(STAGE_NAME_KEY);
        MDC.remove(PIPELINE_ID_KEY);
    }
}
```

The three MDC keys are `run_id`, `stage_name`, and `pipeline_id`
(`CulvertMdcPopulator.java:47–53`). When Cloud Logging JSON output is active
via a Logback encoder configuration, every log line emitted inside the `finally`-
guarded body carries these three fields as top-level JSON keys. A Cloud Logging
filter of `jsonPayload.run_id="20260417T091400Z-7f3a"` then recovers every event
from a single run across every service it touched — without any manual MDC calls
in pipeline code.

There is a void variant (`CulvertMdcPopulator.java:112`) for stage bodies that
return nothing. Both variants guarantee the MDC is clean after the call, even
when the body throws. The class is a pure SLF4J concern — no GCP types, no Beam
types, no OTel dependency. It belongs in the GCP observability module only
because that is where the structured-logging story lives, but it would compile
against any Logback deployment.

The contrast with the v1 code I described in Chapter 11 of the original
manuscript is stark. The Python `LogContext` context manager did the same job
but as a separate object the pipeline code had to import. `CulvertMdcPopulator`
is invoked by the *framework* as part of stage dispatch — the pipeline author
does not see it. That is a better abstraction.

## `DataCatalogLineageEmitter` — lineage as Data Catalog tags

\index{DataCatalogLineageEmitter}\index{lineage}The lineage seam in Culvert is
`LineageEmitter`, a `@FunctionalInterface` in both Java and Python with one
method: `emit(LineageEvent)`. The GCP implementation writes lineage events as
Data Catalog tags on a configurable entry.

```java
// DataCatalogLineageEmitter.java:55
public final class DataCatalogLineageEmitter implements LineageEmitter, AutoCloseable {
    public void emit(LineageEvent event) {
        // flatten event sub-records to scalar fields
        // attach as a Tag to the configured Data Catalog entry
        client.createTag(request);
    }
}
```

Each `LineageEvent` becomes one `Tag` attached to the configured entry
(`DataCatalogLineageEmitter.java:95–115`). `LineageEvent` is a Java record with
four `Optional` sub-records: `source`, `pipeline`, `destination`, and `audit`
(`LineageEvent.java:23–27`). All four are optional because not every stage
produces every section — a streaming source emits no destination until the first
window closes. Construction uses a fluent builder: `LineageEvent.builder()` →
`.source(...)` → `.pipeline(...)` → `.destination(...)` → `.build()`
(`LineageEvent.java:36–54`). The `flatten()` helper in the emitter
(`DataCatalogLineageEmitter.java:137`) unpacks each sub-record to scalar strings
because Data Catalog tag fields are scalars. The `pipeline` sub-record carries
`run_id`, `pipeline_name`, `stage`, `started_at`, and `completed_at`
(`DataCatalogLineageEmitter.java:151–157`). A Data Catalog steward can find every
stage that touched a given table entry by querying its tags.

One design choice worth noting: the Javadoc
(`DataCatalogLineageEmitter.java:33–37`) is honest about why it targets Data
Catalog rather than the newer Cloud Data Lineage API:

> The newer Cloud Data Lineage API is not bundled in the GCP `libraries-bom`
> this module pins. To avoid an out-of-BOM version pin for a product still in
> transition, this Stage-2 implementation uses the stable v1 `DataCatalogClient`
> and stores lineage as tags. A dedicated `DataLineagePublisher` backed by the
> lineage API is deferred to sprint-5.

That is an honest engineering decision, not a limitation to hide. The lineage
information is in Data Catalog; the path to Cloud Data Lineage is clear; the
work is tracked. I would rather ship a working tag-based implementation today
than block on an API that is still moving.

The Python `LineageEmitter` Protocol
(`data-pipeline-core: contracts/lineage.py:18`) mirrors the Java interface with
`@runtime_checkable` structural subtyping. The contract's docstring names the
intended future default implementation (`OpenLineageEmitter`, targeting Marquez)
and the GCP implementation (`DataplexLineagePublisher`). Current status: only
`DataCatalogLineageEmitter` is built and held in v0.1.0.

## The run-ID thread

The four components I have described are only valuable as an ensemble. The
reason is `run_id`.

`CulvertMdcPopulator` writes `run_id` into the MDC so every log line carries
it. `CloudTraceObservabilityHook` carries `run_id` as a span attribute so Cloud
Trace groups spans by run. `CloudMonitoringMetricsHook` receives `run_id` via
the `StageMetrics` record and writes it as a metric label so Cloud Monitoring
can filter time-series to a single run. `DataCatalogLineageEmitter` flattens
`run_id` from the `LineagePipeline` sub-record into the Data Catalog tag so
lineage queries can join on the same identifier.

Put it together and you get what I described in the v1 manuscript as the only
definition of observability worth defending: a single click from a suspicious
Data Catalog tag through to the logs, the trace, the metrics, and the lineage
for that specific run. Not three dashboards — one thread.

The `WorkerSideHookResolutionTest`
(`WorkerSideHookResolutionTest.java:61`) proves this thread survives Beam
serialisation. A `DefaultRuntimeContext` is round-tripped through Java
object serialisation (simulating a Dataflow driver shipping the context to a
worker), and the post-deserialisation `stageMetrics()` call triggers
`AutoConfig.discover()` via `ServiceLoader`, which picks up
`CloudMonitoringMetricsHook` from the SPI registry and instantiates it via the
no-arg constructor — for real, not as a no-op. The test would have failed before
Sprint 12 because the no-arg constructor did not exist; without it,
`AutoConfig.discover()` silently skipped the class and the worker got a
no-op hook.

## The seam in use

A stage runner wires the observability ensemble in roughly this shape:

```java
try (CloudMonitoringMetricsHook metricsHook =
        new CloudMonitoringMetricsHook(monitoringClient, projectId);
     DataCatalogLineageEmitter lineageEmitter =
        new DataCatalogLineageEmitter(catalogClient, entryName, tagTemplate)) {

    CulvertMdcPopulator.withStageContext(runId, stageName, pipelineId, () -> {
        long startMs = System.currentTimeMillis();
        try (ObservabilityHook.Span span =
                observabilityHook.span("stage." + stageName)) {
            span.setAttribute("culvert.run_id", runId);
            // ... stage logic ...
            long rows = processRecords();
            long latencyMs = System.currentTimeMillis() - startMs;

            metricsHook.recordStageMetrics(
                new StageMetrics(pipelineId, runId, stageName,
                    rows, latencyMs, 0L));

            lineageEmitter.emit(LineageEvent.builder()
                .source(source).pipeline(pipelineMeta).destination(dest)
                .build());
        }
    });
}
```

The pattern is mechanical, which means it can be generated. The Beam integration
work (T12.3) is where the try-with-resources and the `CulvertMdcPopulator`
wrapping get encapsulated into a reusable DoFn base so stage authors only
override `processElement`. This chapter describes the seam; Chapter 9 covers the
Beam wiring that hides it.

## Honest status

Culvert v0.1.0 is built and held. Nothing is published to Maven Central or PyPI
yet. The observability module specifically:

- `CloudTraceObservabilityHook` — built, tested, ServiceLoader-registered.
  Gauge implementation has the OTel 1.38 workaround noted above; fix is
  straightforward when the SDK bumps.
- `CloudMonitoringMetricsHook` — built, tested, ServiceLoader-registered.
  Verified end-to-end by `WorkerSideHookResolutionTest`.
- `CulvertMdcPopulator` — built, tested, no external dependencies.
- `DataCatalogLineageEmitter` — built, tested. Uses Data Catalog tags (stable);
  migration to Cloud Data Lineage API deferred and tracked.
- Python `ObservabilityHook` and `LineageEmitter` protocols — defined in
  `data-pipeline-core` v0.1.0. GCP adapter implementations (Python-side) are
  not yet built; the Java adapters are the primary path for Beam-on-Dataflow
  workloads.

The coordinated Maven Central + PyPI `culvert` release is future work, gated on
the full adapter set being verified against real GCP projects in both languages.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item Culvert splits observability across two contracts: \texttt{ObservabilityHook} (general-purpose metrics/logs/spans) and \texttt{StageMetricsHook} (typed, three-metric, three-label contract for per-stage reporting). The narrowness of the second contract is deliberate — it prevents label drift and enables type-safe constructors.
  \item \texttt{CloudTraceObservabilityHook} bridges the Culvert surface to OpenTelemetry and gracefully degrades: if no OTel SDK is wired, the no-arg constructor wraps the GlobalOpenTelemetry no-op and every call is a silent discard. The pipeline runs unmodified; it just does not produce traces.
  \item \texttt{CulvertMdcPopulator} writes \texttt{run\_id}, \texttt{stage\_name}, and \texttt{pipeline\_id} into the SLF4J MDC for the duration of a stage body, then clears them in a \texttt{finally} block. Pipeline code never has to pass context to a logger manually; Cloud Logging sees it on every line.
  \item \texttt{DataCatalogLineageEmitter} stores lineage as Data Catalog tags rather than the newer Cloud Data Lineage API — an honest trade-off taken to avoid an out-of-BOM version pin. Migration path is tracked; the current implementation is functional and stable.
  \item The \texttt{run\_id} is the thread that ties every log line, metric point, trace span, and lineage tag to the same pipeline run. Three dashboards without a shared identity are noise. One identifier that threads thirty artefacts together is observability.
\end{itemize}
\end{takeaways}

\newpage
