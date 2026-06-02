package com.enrichmeai.culvert.gcp.dataflow;

import com.enrichmeai.culvert.contracts.ObservabilityHook;
import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.StageMetrics;
import com.enrichmeai.culvert.contracts.StageMetricsHook;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import org.apache.beam.runners.direct.DirectRunner;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.options.PipelineOptions;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.apache.beam.sdk.util.SerializableUtils;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Sprint-12 T12.3 — auto-instrumentation of {@link StageTransform}.
 *
 * <p>Proves that every stage execution automatically emits:
 * <ul>
 *   <li>A span start and end (via {@link ObservabilityHook#span(String)}).</li>
 *   <li>A latency histogram observation ({@code culvert.stage.latency_ms}).</li>
 *   <li>An error counter increment ({@code culvert.stage.errors}) on exception.</li>
 * </ul>
 *
 * <p>Also proves the {@link StageTransform.ExecuteStageFn} remains
 * Beam-serializable after the instrumentation changes. Resolves GitHub issue #67.
 *
 * <h2>Serialization strategy</h2>
 *
 * <p>The {@link RecordingObservabilityHook} is an inner serializable class
 * (static, named — not anonymous) that writes span/metric events into static
 * {@link CopyOnWriteArrayList} collections. Static collections are reachable
 * from the worker-side DoFn (on the in-process DirectRunner, the worker shares
 * this JVM) without needing to be captured in the DoFn's serialized state —
 * the same pattern used by {@link DataflowPipelineExecutionTest#EXECUTED}.
 * The hook itself is serializable so the DoFn round-trip succeeds; its static
 * fields survive the trip intact.
 */
class StageTransformInstrumentationTest {

    // ---------- static recording surfaces (worker-visible) ----------

    /** Names of spans that were opened. */
    static final CopyOnWriteArrayList<String> SPANS_STARTED = new CopyOnWriteArrayList<>();
    /** Names of spans that were closed (ended). */
    static final CopyOnWriteArrayList<String> SPANS_ENDED = new CopyOnWriteArrayList<>();
    /**
     * Latency recordings via StageMetricsHook: each entry is a stage name.
     * (T12.4: moved from ObservabilityHook.histogram to StageMetricsHook.)
     */
    static final CopyOnWriteArrayList<String> LATENCY_RECORDS = new CopyOnWriteArrayList<>();
    /**
     * Error counter increments via StageMetricsHook: each entry is the stage name.
     * (T12.4: moved from ObservabilityHook.counter to StageMetricsHook.)
     */
    static final CopyOnWriteArrayList<String> ERROR_COUNTS = new CopyOnWriteArrayList<>();

    @BeforeEach
    void resetRecorders() {
        SPANS_STARTED.clear();
        SPANS_ENDED.clear();
        LATENCY_RECORDS.clear();
        ERROR_COUNTS.clear();
        CapturingStageMetricsHook.CAPTURED_STATIC.clear();
    }

    // ---------- helper factories ----------

    private static RuntimeContext context() {
        return DefaultRuntimeContext.builder("run-t123", "test").build();
    }

    private static PipelineOptions directRunnerOpts() {
        PipelineOptions opts = PipelineOptionsFactory.create();
        opts.setRunner(DirectRunner.class);
        return opts;
    }

    // ---------- tests ----------

    /**
     * Prove the DoFn is still Beam-serializable after instrumentation changes
     * (T12.3 hard constraint — must not break T10.6's serialization fix).
     */
    @Test
    void executeStageFnRemainsBeamSerializable() {
        DataflowPipelineTest.StubStage stage =
                new DataflowPipelineTest.StubStage("serial-stage", List.of(), List.of());
        RuntimeContext ctx = context();
        StageTransform.ExecuteStageFn fn =
                new StageTransform.ExecuteStageFn(stage, ctx, null);

        // SerializableUtils.serializeToByteArray throws if the DoFn is not
        // Serializable; deserializeFromByteArray verifies the round-trip works.
        byte[] bytes = SerializableUtils.serializeToByteArray(fn);
        assertThat(bytes).isNotEmpty();
        Object roundTripped = SerializableUtils.deserializeFromByteArray(bytes, "ExecuteStageFn");
        assertThat(roundTripped).isInstanceOf(StageTransform.ExecuteStageFn.class);
    }

    /**
     * Two-stage DirectRunner pipeline: both stages emit a span start+end and a
     * latency histogram observation. The hook override is serializable so it
     * survives the Beam DoFn round-trip on the in-process DirectRunner.
     */
    @Test
    void twoStagePipelineEmitsTwoSpansAndTwoLatencyRecords() {
        PipelineStage stageA = new NoOpInstrumentedStage("alpha");
        PipelineStage stageB = new NoOpInstrumentedStage("beta");

        DataflowPipeline pipeline = new DataflowPipeline("inst-two-stage",
                List.of(stageA, stageB));

        RuntimeContext ctx = context();
        RecordingObservabilityHook obsHook = new RecordingObservabilityHook();
        RecordingStageMetricsHook metricsHook = new RecordingStageMetricsHook();

        Pipeline beam = buildWithHooks(pipeline, ctx, obsHook, metricsHook, directRunnerOpts());
        beam.run().waitUntilFinish();

        // Tracing seam: spans opened/closed via ObservabilityHook.
        assertThat(SPANS_STARTED).containsExactlyInAnyOrder(
                "culvert.stage/alpha", "culvert.stage/beta");
        assertThat(SPANS_ENDED).containsExactlyInAnyOrder(
                "culvert.stage/alpha", "culvert.stage/beta");
        // Metrics seam: latency recorded via StageMetricsHook (T12.4).
        assertThat(LATENCY_RECORDS).hasSize(2)
                .allSatisfy(name -> assertThat(name).isIn("alpha", "beta"));
        assertThat(ERROR_COUNTS).isEmpty();
    }

    /**
     * Error path: when {@code stage.execute} throws, the error counter is
     * incremented and the span is still ended (closed in {@code finally}).
     */
    @Test
    void errorPathIncrementsErrorCountAndEndsSpan() {
        PipelineStage failingStage = new ThrowingStage("fail-stage");

        DataflowPipeline pipeline = new DataflowPipeline("inst-error-pipeline",
                List.of(failingStage));

        RuntimeContext ctx = context();
        RecordingObservabilityHook obsHook = new RecordingObservabilityHook();
        RecordingStageMetricsHook metricsHook = new RecordingStageMetricsHook();

        Pipeline beam = buildWithHooks(pipeline, ctx, obsHook, metricsHook, directRunnerOpts());

        // DirectRunner propagates stage exceptions out of waitUntilFinish.
        assertThatThrownBy(() -> beam.run().waitUntilFinish())
                .isInstanceOf(RuntimeException.class);

        // The span was still opened and closed (finally block).
        assertThat(SPANS_STARTED).containsExactly("culvert.stage/fail-stage");
        assertThat(SPANS_ENDED).containsExactly("culvert.stage/fail-stage");
        // Latency is recorded in finally via StageMetricsHook (T12.4).
        assertThat(LATENCY_RECORDS).hasSize(1).containsExactly("fail-stage");
        // Error count incremented exactly once via StageMetricsHook (T12.4).
        assertThat(ERROR_COUNTS).hasSize(1).containsExactly("fail-stage");
    }

    // ---------- helpers ----------

    /**
     * Build a Beam pipeline from a {@link DataflowPipeline} with hook overrides
     * injected into every {@link StageTransform.ExecuteStageFn}.
     *
     * <p>This bypasses the worker-side context registry (which is rebuilt from
     * AutoConfig after deserialization and thus drops test-only registrations)
     * by passing the hooks directly to the DoFn constructor (T12.4 dual-hook
     * injection: observability for tracing, stageMetrics for typed metrics).
     */
    private static Pipeline buildWithHooks(DataflowPipeline culvertPipeline,
                                           RuntimeContext ctx,
                                           ObservabilityHook obsHook,
                                           StageMetricsHook metricsHook,
                                           PipelineOptions opts) {
        culvertPipeline.validate();
        Pipeline beam = Pipeline.create(opts);

        Map<String, PipelineStage> byName = new java.util.HashMap<>();
        for (PipelineStage stage : culvertPipeline.stages()) {
            byName.put(stage.name(), stage);
        }
        for (String stageName : culvertPipeline.topologicalOrder()) {
            PipelineStage stage = byName.get(stageName);
            // Directly apply a ParDo with hook-injected DoFns so the recording
            // hooks survive the DirectRunner serialization round-trip.
            beam.apply("Trigger[" + stageName + "]",
                            org.apache.beam.sdk.transforms.Create.of("execute"))
                    .apply("Execute[" + stageName + "]",
                            org.apache.beam.sdk.transforms.ParDo.of(
                                    new StageTransform.ExecuteStageFn(
                                            stage, ctx, obsHook, metricsHook)));
        }
        return beam;
    }

    // ---------- serializable recording hook ----------

    /**
     * A serializable {@link ObservabilityHook} that records tracing events
     * (span start/end) into the static lists of the enclosing test class.
     *
     * <p>T12.4: counter and histogram calls for metrics have been moved to
     * {@link RecordingStageMetricsHook}. This hook now records spans only.
     *
     * <p>Static fields survive the DirectRunner's DoFn serialization round-trip
     * because the worker runs in the same JVM. The hook instance itself is
     * serializable so it can be captured in the DoFn without breaking
     * {@link SerializableUtils#serializeToByteArray}.
     */
    static final class RecordingObservabilityHook implements ObservabilityHook, Serializable {
        private static final long serialVersionUID = 1L;

        @Override
        public void counter(String name, long value, Map<String, String> tags) {
            // No longer used for stage metrics (T12.4 — moved to StageMetricsHook).
        }

        @Override
        public void gauge(String name, double value, Map<String, String> tags) {
            // not exercised in these tests
        }

        @Override
        public void histogram(String name, double value, Map<String, String> tags) {
            // No longer used for stage latency (T12.4 — moved to StageMetricsHook).
        }

        @Override
        public void log(String level, String message, Map<String, Object> fields) {
            // not exercised in these tests
        }

        @Override
        public Span span(String name) {
            SPANS_STARTED.add(name);
            return new RecordingSpan(name);
        }
    }

    /**
     * A serializable {@link StageMetricsHook} that records per-stage metrics
     * (latency and error count) into the static lists of the enclosing test class.
     *
     * <p>Sprint-12 / T12.4: replaces the raw {@code histogram}/{@code counter}
     * calls that were on {@link RecordingObservabilityHook} in T12.3.
     */
    static final class RecordingStageMetricsHook implements StageMetricsHook, Serializable {
        private static final long serialVersionUID = 1L;

        @Override
        public void recordStageMetrics(StageMetrics metrics) {
            // Record latency: keyed by stage name so tests can assert on stage identity.
            LATENCY_RECORDS.add(metrics.stageName());
            // Record error count: add the stage name for each error.
            if (metrics.errorCount() > 0) {
                ERROR_COUNTS.add(metrics.stageName());
            }
        }
    }

    /** A serializable span that records its close into {@link #SPANS_ENDED}. */
    static final class RecordingSpan implements ObservabilityHook.Span, Serializable {
        private static final long serialVersionUID = 1L;
        private final String name;
        private boolean closed;

        RecordingSpan(String name) {
            this.name = name;
        }

        @Override
        public void setAttribute(String key, String value) {
            // no-op
        }

        @Override
        public void recordException(Throwable t) {
            // no-op
        }

        @Override
        public void close() {
            if (!closed) {
                closed = true;
                SPANS_ENDED.add(name);
            }
        }
    }

    // ---------- rows_processed sentinel + pipeline_id tests (T12.6) ----------

    /**
     * ROWS_PROCESSED_UNKNOWN sentinel is 0L (not a silent magic number):
     * the constant is exposed and documented so tests and callers can assert
     * on the sentinel value explicitly.
     */
    @Test
    void rowsProcessedSentinelIsZeroAndDocumented() {
        assertThat(StageTransform.ExecuteStageFn.ROWS_PROCESSED_UNKNOWN).isEqualTo(0L);
    }

    /**
     * StageMetricsHook receives rowsProcessed == ROWS_PROCESSED_UNKNOWN for
     * execute()-based stages (which do not surface element counts).
     */
    @Test
    void stageMetricsHookReceivesRowsProcessedSentinelNotArbitraryValue() {
        PipelineStage stage = new NoOpInstrumentedStage("sentinel-stage");
        DataflowPipeline pipeline = new DataflowPipeline("sentinel-pipeline", List.of(stage));
        RuntimeContext ctx = context();
        RecordingObservabilityHook obsHook = new RecordingObservabilityHook();
        CapturingStageMetricsHook captureHook = new CapturingStageMetricsHook();

        Pipeline beam = buildWithHooks(pipeline, ctx, obsHook, captureHook, directRunnerOpts());
        beam.run().waitUntilFinish();

        assertThat(CapturingStageMetricsHook.CAPTURED_STATIC).hasSize(1);
        StageMetrics emitted = CapturingStageMetricsHook.CAPTURED_STATIC.get(0);
        assertThat(emitted.rowsProcessed())
                .as("rows_processed must equal the ROWS_PROCESSED_UNKNOWN sentinel (0L)")
                .isEqualTo(StageTransform.ExecuteStageFn.ROWS_PROCESSED_UNKNOWN);
        assertThat(emitted.stageName()).isEqualTo("sentinel-stage");
    }

    /**
     * pipeline_id in emitted StageMetrics comes from RuntimeContext.pipelineId()
     * (the T12.6 contract method), not a hard-coded proxy.
     */
    @Test
    void stageMetricsHookReceivesPipelineIdFromRuntimeContextPipelineId() {
        PipelineStage stage = new NoOpInstrumentedStage("pid-stage");
        DataflowPipeline pipeline = new DataflowPipeline("pid-pipeline", List.of(stage));
        // Default: pipelineId() returns runId() (the default impl on the contract).
        RuntimeContext ctx = context(); // runId = "run-t123"
        RecordingObservabilityHook obsHook = new RecordingObservabilityHook();
        CapturingStageMetricsHook captureHook = new CapturingStageMetricsHook();

        Pipeline beam = buildWithHooks(pipeline, ctx, obsHook, captureHook, directRunnerOpts());
        beam.run().waitUntilFinish();

        assertThat(CapturingStageMetricsHook.CAPTURED_STATIC).hasSize(1);
        StageMetrics emitted = CapturingStageMetricsHook.CAPTURED_STATIC.get(0);
        // pipelineId() default returns runId(); verify both are correctly threaded.
        assertThat(emitted.pipelineId()).isEqualTo(ctx.pipelineId());
        assertThat(emitted.runId()).isEqualTo(ctx.runId());
    }

    /** A {@link StageMetricsHook} that captures all emitted {@link StageMetrics} records. */
    static final class CapturingStageMetricsHook implements StageMetricsHook, java.io.Serializable {
        private static final long serialVersionUID = 1L;
        // Use a thread-safe static list; worker-visible (same JVM on DirectRunner).
        static final java.util.concurrent.CopyOnWriteArrayList<StageMetrics> CAPTURED_STATIC =
                new java.util.concurrent.CopyOnWriteArrayList<>();

        @Override
        public void recordStageMetrics(StageMetrics metrics) {
            CAPTURED_STATIC.add(metrics);
        }
    }

    // ---------- stage stubs ----------

    /**
     * A serializable, no-op stage used for the happy-path instrumentation tests.
     */
    static final class NoOpInstrumentedStage implements PipelineStage, Serializable {
        private static final long serialVersionUID = 1L;
        private final String name;

        NoOpInstrumentedStage(String name) {
            this.name = name;
        }

        @Override
        public String name() {
            return name;
        }

        @Override
        public List<String> inputs() {
            return List.of();
        }

        @Override
        public List<String> outputs() {
            return List.of();
        }

        @Override
        public void execute(RuntimeContext context) {
            // no-op: just allow instrumentation to fire
        }
    }

    /**
     * A serializable stage that always throws from {@code execute}, used to
     * verify the error-path instrumentation.
     */
    static final class ThrowingStage implements PipelineStage, Serializable {
        private static final long serialVersionUID = 1L;
        private final String name;

        ThrowingStage(String name) {
            this.name = name;
        }

        @Override
        public String name() {
            return name;
        }

        @Override
        public List<String> inputs() {
            return List.of();
        }

        @Override
        public List<String> outputs() {
            return List.of();
        }

        @Override
        public void execute(RuntimeContext context) {
            throw new RuntimeException("simulated stage failure for T12.3 error-path test");
        }
    }
}
