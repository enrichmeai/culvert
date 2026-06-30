# Chapter 9 — Execution: Beam on Dataflow

The last chapter drew the map. Java owns execution; Python owns orchestration,
transforms, and the dbt layer. That division is not a preference — it is a
decision taken empirically, under load, with a real bill arriving every month.
This chapter is the proof of the Java side of that map: why execution became
Java's lane, how the Culvert contracts cross the boundary into Apache Beam, and
what the two classes at the heart of `data-pipeline-gcp-dataflow-java` actually
do.

The worked example throughout is the problem that forced the decision: mainframe
ingestion, HDR/TRL files, and the question of whether Python could keep up.

## Why execution is Java's lane

Apache Beam is not a fashionable technology in 2026. The Spark crowd thinks it
is over-engineered. The DuckDB crowd thinks any distributed engine is overkill.
The Snowflake crowd thinks ingestion is something you buy, not build. And yet,
for a particular shape of problem — high-volume, schema-validated, batch-or-streaming,
on Google Cloud — Beam on Dataflow is still the right answer.

The shape is roughly this: you have files on the order of gigabytes-to-terabytes,
you need per-record transformations that do not parallelise well in pure SQL, you
need side outputs for error quarantine, and you want managed autoscaling. Dataflow
gives you all of that in exchange for one Docker image and a JSON parameter file.

The throughput gap between the Java and Python SDKs is real. Java Beam delivers
roughly 2–3× more processed records per Dataflow dollar than Python Beam, and
the reason is not that Python is a slow language in general — it is two specific
things. First, Dataflow Runner v2 (the mode Python pipelines always use) routes
work through an SDK harness container that sits alongside the worker JVM. Every
record crosses that harness-to-worker boundary; the JVM does not have an
equivalent hop. Second, on the hot path, Java serialises through Kryo or AvroIO,
both of which are extremely fast; Python serialises through CPython's pickle
machinery, which is not.

For a pipeline doing heavy per-record work — parsing, enrichment, ML inference —
the CPU time on the actual business logic swamps the serialisation cost and the
SDK matters less. But mainframe ingestion is *not* that kind of pipeline. The
records are wide, the per-record logic is simple, and serialisation sits right
in the critical path.

Volume is what makes the trade-off worth having the conversation about. Below
roughly 50 million rows per day, the overhead of running a polyglot toolchain is
a far bigger cost than the compute bill. Above roughly 500 million rows per day —
which is perfectly normal for a corporate-bank card-transaction or call-detail
feed — a single high-throughput entity can cost you £8–12K per month on Python
Beam where the Java equivalent would run at £3–5K per month. At that point the
saving is real money, it recurs every month, and it is worth the polyglot tax.

The cultural dimension matters too, and it is underrated. Mainframe operations
teams are overwhelmingly Java-oriented. If you are writing files the mainframe
will consume — segment-transform write-back, batch settlement feeds, regulatory
exports — Java has the richer ecosystem: `com.legstar.*` for COBOL copybook\index{COBOL copybook}
binding, `Cp037` and `Cp1047` EBCDIC\index{EBCDIC} support via the standard JDK, IBM's own
JZOS toolkit for direct VSAM interaction. A Python receive-side pipeline feels
foreign to mainframe ops in a way that a Java one does not.

All of this is why — as Chapter 6's division-of-labour table records — the
Dataflow/execution row is: **Java (Beam).** The predecessor Python Beam path is
not being ported forward. `data-pipeline-gcp-dataflow-java` is the
lane, and it has no Python sibling.

## The HDR/TRL mainframe problem

Before we look at how Culvert solves the execution problem in Java, it is worth
understanding exactly what the execution problem is. The mainframe extract format
that drove everything is the HDR/TRL pattern.

A typical mainframe extract looks like this:

```
HDR|customers|20260417|0001|500000
0001|Alice Smith|1985-03-22|SW1A 1AA|2010-06-12T09:14:00Z
0002|Bob Jones |1979-11-04|EH8 9YL |2007-02-19T14:22:30Z
...
0500000|Zara Patel|1992-08-15|M1 1AA|2020-12-30T16:45:00Z
TRL|customers|20260417|0001|500000
```

The `HDR` row carries metadata: entity name, extract date, batch number, expected
record count. The `TRL` row repeats this metadata as a self-check. The body rows
are the actual data.

This pattern is older than I am, and it is everywhere. It is also subtly tricky
to handle in a distributed system, because Beam's parallel execution model assumes
records are independent, and HDR/TRL rows are not. The envelope must be separated
from the body; the expected count in the envelope must be checked against what
actually arrived; and this check must happen *after* all the body records have
been processed, which in a distributed job means after all the workers have
finished.

Real mainframes do not always send a 500,000-row file as one object either. They
sometimes split it into chunks:

```
customers.20260417.001of005.csv
customers.20260417.002of005.csv
...
customers.20260417.001of005.ok
```

Each chunk has its own HDR and TRL. Each `.ok` file signals that one chunk is
complete. You must wait for all chunks, reassemble them in order, and then treat
them as one logical extract. This kind of code is unglamorous and easy to get
wrong. It is also code that a bank runs every day at four in the morning, and
when it breaks, people notice.

The question was whether the Python Beam library we had built could handle this
at corporate-bank volume. The answer was: yes, but not cheaply. The arithmetic
eventually compelled us to the conclusion that execution needed to move to Java.
That conclusion is now the Culvert decision record: execution is Java's lane,
full stop.

The Java Culvert layer does not (yet) ship the rich library of HDR/TRL-specific
transforms that the old Python pipeline had — `HDRTRLParser`, `RobustCsvParseDoFn`,
`SchemaValidateRecordDoFn`, and the rest. Those belong to the predecessor project
and are not being ported. What Culvert ships is the execution *bridge*: the
mechanism by which any `PipelineStage` implementation can be run on Dataflow,
with full instrumentation, in a way that is completely invisible to the stage
itself. The stage author writes business logic against the contracts; the bridge
handles Beam.

## The contract: `Pipeline` and `PipelineStage`

The contracts involved in execution are small, by design. From
`data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Pipeline.java`
(lines 1–30):

```java
public interface Pipeline {
    String name();
    List<PipelineStage> stages();
    void validate();
}
```

That is the whole interface. It is scheduler-agnostic: the pipeline describes a
DAG, and does not know or care whether that DAG will run on Dataflow, on a local
DirectRunner, on a future AWS Step Functions executor, or anything else. The
runtime picks it up and decides.

`PipelineStage`\index{PipelineStage} is equally spare
(`data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/PipelineStage.java`,
lines 1–31):

```java
public interface PipelineStage {
    String name();
    List<String> inputs();
    List<String> outputs();
    void execute(RuntimeContext context);
}
```

`inputs()` and `outputs()` are lists of logical names — strings — that the
framework uses to compute execution order and validate that every input has a
producer. `execute()` is `void` and side-effecting: the stage reads from sources
and writes to sinks through the adapters on the `RuntimeContext`. The stage does
not return a value, does not expose element counts, and does not know which runner
it is executing on.

This is also where the `Transform<V,W>` contract fits in — and where it
*currently does not*. `Transform`
(`data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/contracts/Transform.java`,
lines 17–27) is the element-level map contract:

```java
@FunctionalInterface
public interface Transform<V, W> {
    Iterator<W> apply(Iterator<V> records, RuntimeContext context);
}
```

An element-level Beam execution — where a stage maps an input `PCollection` to
an output `PCollection` so Beam can fuse and parallelise the data flow — would
require bridging `Transform<V,W>` into a proper `DoFn`. That is not what
`StageTransform` does today. Bridging `Transform<V,W>` at the element level is
explicitly deferred (StageTransform.java:35–39). The current bridge triggers
`execute()` once; element-level translation is sprint-future. It is important to
be precise about this distinction, because the architecture is built to
accommodate the upgrade path — but the upgrade has not been done yet.

## `DataflowPipeline`: the adapter

`DataflowPipeline`\index{DataflowPipeline} implements `Pipeline` and adds two
utilities on top of the base contract. The full source is in
`data-pipeline-gcp-dataflow-java/src/main/java/com/enrichmeai/culvert/gcp/dataflow/DataflowPipeline.java`.

Construction is strict and predictable (lines 72–83):

```java
public DataflowPipeline(String name, List<PipelineStage> stages) {
    Objects.requireNonNull(name, "name must not be null");
    Objects.requireNonNull(stages, "stages must not be null");
    if (name.isBlank()) {
        throw new IllegalArgumentException("name must not be blank");
    }
    if (stages.isEmpty()) {
        throw new IllegalArgumentException("stages must not be empty");
    }
    this.name = name;
    this.stages = List.copyOf(stages);
}
```

`List.copyOf` makes the stage list immutable immediately. Nothing downstream can
mutate the topology after construction. I like this pattern — it removes an entire
class of bugs where something hands you a pipeline and then quietly modifies the
stage list later.

### `validate()`: the graph checker

`validate()` (lines 103–150) enforces three properties before anything runs:

1. **Stage names are unique.** Two stages with the same name is a configuration
   error that would produce nonsensical topological ordering.
2. **Every input references an output with a producer.** If a stage declares that
   it consumes `"rows"` but no upstream stage produces `"rows"`, the graph is
   broken — no point launching Dataflow workers to discover that.
3. **No cycles.** Checked by DFS; the cycle detection path (lines 342–365) trims
   the visiting set to the cycle itself and surfaces the full path, which makes
   debugging a misconfigured graph much less painful.

`validate()` runs again inside `buildBeam()` before any Beam pipeline is
constructed. You cannot accidentally submit a malformed graph to Dataflow.

### `buildBeam()`: the translation

`buildBeam(PipelineOptions options, RuntimeContext context)` (lines 199–215) is
where the Culvert topology becomes a Beam pipeline:

```java
public org.apache.beam.sdk.Pipeline buildBeam(
        PipelineOptions options, RuntimeContext context) {
    Objects.requireNonNull(options, "options must not be null");
    Objects.requireNonNull(context, "context must not be null");
    validate();

    org.apache.beam.sdk.Pipeline beam =
            org.apache.beam.sdk.Pipeline.create(options);
    Map<String, PipelineStage> byName = new HashMap<>();
    for (PipelineStage stage : stages) {
        byName.put(stage.name(), stage);
    }
    for (String stageName : topologicalOrder()) {
        PipelineStage stage = Objects.requireNonNull(
                byName.get(stageName), () -> "no stage named " + stageName);
        beam.apply(StageTransform.of(stage, context));
    }
    return beam;
}
```

The key step is `topologicalOrder()` (lines 278–324), which runs Kahn's algorithm
over the input/output edge graph. This means the declaration order of stages in
the constructor is irrelevant — the execution order is derived from data
dependencies, not from the order you wrote them down. The test at
`DataflowPipelineExecutionTest.java:63–65` deliberately declares stages out of
dependency order to prove this:

```java
// Declare OUT of dependency order: "transform" depends on "read"'s
// output, but is declared first. buildBeam must topologically sort.
PipelineStage read = new RecordingStage("read", List.of(), List.of("rows"));
PipelineStage transform = new RecordingStage("transform", List.of("rows"), List.of("clean"));
DataflowPipeline pipeline =
        new DataflowPipeline("two-stage", List.of(transform, read));
```

`topologicalOrder()` returns `["read", "transform"]` regardless of declaration
order. Applied to the HDR/TRL problem: a real ingestion pipeline would have a
stage that reads the mainframe file, a stage that parses and validates records,
and a stage that writes to BigQuery and emits reconciliation. You can declare them
in any order; the framework works it out from the input/output edges.

### `runOnDataflow()`: the submission

`runOnDataflow(DataflowPipelineOptions options)` (lines 230–248) is the convenience
method for production submission:

```java
public PipelineResult runOnDataflow(
        DataflowPipelineOptions options, RuntimeContext context) {
    Objects.requireNonNull(options, "options must not be null");
    Objects.requireNonNull(context, "context must not be null");
    options.setRunner(DataflowRunner.class);
    org.apache.beam.sdk.Pipeline beam = buildBeam(options, context);
    return beam.run();
}
```

It sets `DataflowRunner.class` on the options (overriding whatever was previously
set), builds the Beam pipeline, and submits. The returned `PipelineResult` is
typically a `DataflowPipelineJob`; calling `waitUntilFinish()` on it blocks until
the job completes. The options carry `project`, `region`, `stagingLocation`, and
everything else Dataflow needs — those come from the caller, not from this class.

One thing worth noting: the class Javadoc's comment at lines 39–43 describes
stages as wrapped in `Create.empty(...)` placeholders. That description is stale —
the current implementation uses `Create.of(TRIGGER_TOKEN)` (a single-element
collection, not empty) to guarantee exactly-once execution. The Javadoc reflects
an earlier implementation. The code is authoritative.

## `StageTransform`: the Beam adapter

`StageTransform`\index{StageTransform} is the piece that makes each `PipelineStage` legible to
Beam. The full source is in
`data-pipeline-gcp-dataflow-java/src/main/java/com/enrichmeai/culvert/gcp/dataflow/StageTransform.java`.

The class signature (line 111) is `PTransform<PBegin, PDone>`:

```java
public final class StageTransform extends PTransform<PBegin, PDone> {
```

This shape is deliberate. `PipelineStage#execute()` is `void` and side-effecting
— it reads and writes through the `RuntimeContext` adapters, it does not map a
`PCollection` of elements. So the transform does not consume or produce a typed
`PCollection`; it is rooted at `PBegin` (the Beam pipeline's start) and
terminates at `PDone`. Its single job is to trigger the stage exactly once when
the Beam pipeline runs (StageTransform.java:23–39).

The `expand()` method (lines 145–153) shows the mechanism:

```java
@Override
public PDone expand(PBegin input) {
    PCollection<String> trigger = input.apply(
            "Trigger[" + stage.name() + "]", Create.of(TRIGGER_TOKEN));
    trigger.apply(
            "Execute[" + stage.name() + "]",
            ParDo.of(new ExecuteStageFn(stage, context, null)));
    return PDone.in(input.getPipeline());
}
```

`Create.of(TRIGGER_TOKEN)` produces a one-element collection. `ParDo.of(new
ExecuteStageFn(...))` processes that one element. `ExecuteStageFn#processElement()`
calls `stage.execute(context)`. One element in, one `execute()` call, done. A
`@Setup` or `@StartBundle` hook was considered and rejected because those fire
per-worker-instance or per-bundle, and a runner may create several of each —
which would run the stage more than once (StageTransform.java:44–49).

### Serialisation

Beam serialises a `DoFn` to its workers. Both the `PipelineStage` and the
`RuntimeContext` are captured in `ExecuteStageFn`, so both must be `Serializable`
at runtime (StageTransform.java:200–210). `DefaultRuntimeContext` is. Stub and
adapter stages used in production are expected to be. A stage that closes over
non-serialisable state cannot run on a distributed runner regardless of this
transform — the failure surfaces at `run()` time, which is the right place for
it. The serialisation round-trip is proven in
`StageTransformInstrumentationTest.java` (lines 13, 26–27) using Beam's own
`SerializableUtils.ensureSerializable` utility.

### Auto-instrumentation

Every stage execution is automatically wrapped with three observability
concerns (StageTransform.java:60–103; `ExecuteStageFn#processElement()`,
lines 246–308):

**MDC population.** Before calling `execute()`, the three Culvert MDC keys —
`run_id`, `stage_name`, `pipeline_id` — are written to the current thread's
SLF4J MDC (lines 248–256). This means every log line emitted inside the stage
automatically carries the three context fields. They are cleared in the `finally`
block so they never leak to another stage or thread.

```java
MDC.put(MDC_RUN_ID, runId);
MDC.put(MDC_STAGE_NAME, stageName);
MDC.put(MDC_PIPELINE_ID, pipelineId);
```

**Trace span.** An `ObservabilityHook.Span` named `culvert.stage/<stage-name>`
is opened before `execute()` and closed in `finally`. If the stage throws, the
exception is recorded on the span before being re-thrown (lines 276–283):

```java
ObservabilityHook.Span span = obs.span("culvert.stage/" + stageName);
span.setAttribute("culvert.run_id", runId);
try {
    stage.execute(context);
} catch (RuntimeException e) {
    span.recordException(e);
    errorCount = 1L;
    throw e;
} finally {
    ...
    span.close();
}
```

**Stage metrics.** In the `finally` block, `StageMetricsHook#recordStageMetrics()`
is called with a `StageMetrics` record carrying `pipelineId`, `runId`,
`stageName`, `rowsProcessed`, `stageLatencyMs`, and `errorCount` (lines 294–300):

```java
metricsHook.recordStageMetrics(new StageMetrics(
        pipelineId,
        runId,
        stageName,
        ROWS_PROCESSED_UNKNOWN,
        (double) elapsedMs,
        errorCount));
```

The `ROWS_PROCESSED_UNKNOWN` sentinel (lines 199–199, value `0L`) deserves a
word. Because `PipelineStage#execute()` is `void`, the framework has no way to
know how many records the stage processed. A real row count would require
element-level `PCollection` translation — which is explicitly deferred. In the
meantime, `0L` is the only Cloud Monitoring-valid value for a `CUMULATIVE INT64`
metric (negative values are rejected by the API). The sentinel is documented and
tested explicitly; it is not a silent hard-code.

Both hooks — `ObservabilityHook` for spans and `StageMetricsHook` for the three
standard metrics — are resolved worker-side from the `RuntimeContext`, never
captured at construction time (lines 260–271). This mirrors the T10.6 pattern:
`DefaultRuntimeContext`'s adapter registry is `transient` and rebuilt from
`AutoConfig.discover()` after Beam deserialisation. No extra serialised state is
added to the `DoFn`.

The two hooks have distinct concerns (StageTransform.java:79–92):
`ObservabilityHook` is the general-purpose primitive surface — arbitrary span
names, arbitrary attributes. `StageMetricsHook` is the typed Culvert-specific
seam that emits exactly the three standard metrics (`rows_processed`,
`stage_latency_ms`, `error_count`) with the fixed label schema. They coexist;
they do not duplicate each other.

## Wiring it up: HDR/TRL as a three-stage pipeline

To make the abstraction concrete, here is how the HDR/TRL mainframe ingestion
problem would be expressed in Culvert's Java layer today. The stage
implementations are not shipped by the framework — they are the application
code that sits on top of the bridge. But the wiring is exactly this:

```java
PipelineStage readStage = new HdrTrlReadStage(
    "hdr-trl-read", inputUri, List.of(), List.of("envelope", "rows"));

PipelineStage validateStage = new SchemaValidateStage(
    "validate", schema, List.of("rows"), List.of("valid-rows", "invalid-rows"));

PipelineStage writeStage = new BigQueryWriteStage(
    "bq-write", dataset, table, errorBucket,
    List.of("valid-rows", "invalid-rows"), List.of());

DataflowPipeline pipeline = new DataflowPipeline(
    "customers-ingest",
    List.of(readStage, validateStage, writeStage));

DataflowPipelineOptions options = PipelineOptionsFactory
    .as(DataflowPipelineOptions.class);
options.setProject("my-gcp-project");
options.setRegion("europe-west2");
options.setStagingLocation("gs://my-bucket/staging");

pipeline.runOnDataflow(options).waitUntilFinish();
```

`pipeline.validate()` (called inside `runOnDataflow`) checks the graph: every
input has a producer, there are no cycles, stage names are unique. `buildBeam()`
converts it to a Beam pipeline with three `StageTransform` instances applied in
topological order. `DataflowRunner` submits the job. Each stage's `execute()`
call is automatically traced, metrically recorded, and MDC-annotated.

The stage implementations themselves — reading from GCS, parsing HDR/TRL,
validating records against a schema, routing good/bad rows, writing to BigQuery
— are the application's concern. The framework provides the infrastructure that
makes those implementations observable, ordered, and cloud-portable.

## Honest status

`data-pipeline-gcp-dataflow-java` is built and tested. The two production classes
— `DataflowPipeline` and `StageTransform` — are complete and covered by four test
files (`DataflowPipelineTest`, `DataflowPipelineExecutionTest`,
`StageTransformInstrumentationTest`, `DefaultRuntimeContextWiringIT`).

The things that are not yet done:

- **Element-level `PCollection` translation.** `StageTransform` triggers `execute()` once via a single-element `Create.of`. A future sprint will add the element-level bridge that maps `Transform<V,W>` to a proper `DoFn<V,W>`, allowing Beam to fuse and parallelise data flow between stages.
- **`rowsProcessed` is always `0L`.** Until element-level translation lands, the metric is the documented `ROWS_PROCESSED_UNKNOWN` sentinel.
- **Nothing is published.** The framework is built and held. Coordinated publication to Maven Central (Java) and PyPI (Python) is future work.

These are honest gaps. The architecture is built to close them incrementally; the
contracts are the reason the gaps are closeable without breaking anything
downstream.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item Execution is Java's lane because the 2--3\texttimes{} Dataflow throughput-per-dollar advantage over Python Beam becomes real money above roughly 500 million rows per day, and mainframe operations culture is Java-oriented. The decision is in the division-of-labour table; this chapter is its implementation.
  \item \texttt{DataflowPipeline} implements the scheduler-agnostic \texttt{Pipeline} contract and adds two utilities: \texttt{buildBeam()} (which topologically sorts stages and applies one \texttt{StageTransform} per stage) and \texttt{runOnDataflow()} (which sets \texttt{DataflowRunner}, builds, and submits). Declaration order is irrelevant; execution order derives from input/output edges.
  \item \texttt{StageTransform} bridges \texttt{PipelineStage} to Beam as a \texttt{PTransform<PBegin,PDone>}: a one-element \texttt{Create.of} trigger drives a single \texttt{DoFn\#processElement} call, invoking \texttt{execute()} exactly once. Element-level \texttt{PCollection} mapping -- bridging \texttt{Transform<V,W>} into a proper \texttt{DoFn<V,W>} -- is explicitly deferred.
  \item Every stage execution is automatically wrapped with MDC population (\texttt{run\_id}, \texttt{stage\_name}, \texttt{pipeline\_id}), a trace span via \texttt{ObservabilityHook}, and the three standard Culvert metrics (\texttt{rows\_processed}, \texttt{stage\_latency\_ms}, \texttt{error\_count}) via \texttt{StageMetricsHook}. No stage author has to wire any of this; it is invisible infrastructure.
\end{itemize}
\end{takeaways}

\newpage
