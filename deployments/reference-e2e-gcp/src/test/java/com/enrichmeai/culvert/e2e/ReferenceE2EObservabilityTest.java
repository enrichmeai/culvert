package com.enrichmeai.culvert.e2e;

import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.StageMetrics;
import com.enrichmeai.culvert.gcp.dataflow.DataflowPipeline;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import org.apache.beam.runners.direct.DirectRunner;
import org.apache.beam.sdk.PipelineResult;
import org.apache.beam.sdk.options.PipelineOptions;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Sprint-12 T12.5 (#80) — Observability slice for the reference-e2e-gcp deployment.
 *
 * <p>Proves the "no per-stage boilerplate" epic gate (#47) on the actual reference
 * deployment: a 2-stage pipeline built through {@code DataflowPipeline#buildBeam}
 * (the public production path) automatically emits per-stage signals via the
 * recording hooks registered in {@code META-INF/services}.
 *
 * <h2>Mechanism</h2>
 *
 * <p>The recording hooks ({@link RecordingStageMetricsHook}, {@link RecordingObservabilityHook})
 * are registered in test-scope {@code META-INF/services} files. When
 * {@link DefaultRuntimeContext} is deserialized on the DirectRunner worker (same JVM),
 * its transient {@code registry} is rebuilt from {@link com.enrichmeai.culvert.autoconfig.AutoConfig#discover()},
 * which loads the recording hooks via {@link java.util.ServiceLoader}. The
 * auto-instrumentation in {@link com.enrichmeai.culvert.gcp.dataflow.StageTransform}
 * then calls these hooks for every stage execution — no per-stage wiring required.
 *
 * <h2>What is asserted</h2>
 *
 * <ul>
 *   <li>Both stages (read, transform) emit a latency record via {@link RecordingStageMetricsHook}.</li>
 *   <li>Both stages emit a span open and a span close via {@link RecordingObservabilityHook}.</li>
 *   <li>Error counter is zero on the happy path.</li>
 *   <li>Emitted {@link StageMetrics} carry correct {@code stageName}, {@code runId},
 *       {@code pipelineId} (from context), and {@code rowsProcessed == 0L}
 *       ({@code ROWS_PROCESSED_UNKNOWN} sentinel — documented, not silent).</li>
 *   <li>Span names follow the convention {@code culvert.stage/<stage-name>}.</li>
 * </ul>
 *
 * <h2>Error-counter signal</h2>
 *
 * <p>An additional test verifies the error-counter path: a stage that throws causes
 * {@code errorCount == 1} in the emitted {@link StageMetrics} — proving the counter
 * fires correctly via the same ServiceLoader mechanism.
 *
 * <p>No live GCP credentials, no Docker, no internet. DirectRunner + recording hooks only.
 */
class ReferenceE2EObservabilityTest {

    @BeforeEach
    void resetRecorders() {
        RecordingStageMetricsHook.reset();
        RecordingObservabilityHook.reset();
    }

    private static PipelineOptions directRunnerOpts() {
        PipelineOptions opts = PipelineOptionsFactory.create();
        opts.setRunner(DirectRunner.class);
        return opts;
    }

    /**
     * Happy-path: the reference 2-stage pipeline (read → transform) runs to completion
     * on the DirectRunner and the recording hooks capture exactly 2 latency records,
     * 2 span-opens, and 2 span-closes with zero errors.
     *
     * <p>This is the structural proof of the epic gate on the actual reference deployment:
     * {@code DataflowPipeline#buildBeam} is the public production path — no test-only hook
     * bypass, no package-private DoFn constructor. Auto-instrumentation fires automatically.
     */
    @Test
    void referenceE2EPipelineEmitsObservabilitySignalsForBothStages() {
        PipelineStage read = new NoOpReadStage();
        PipelineStage transform = new NoOpTransformStage();
        DataflowPipeline pipeline = new DataflowPipeline(
                "reference-e2e-gcp", List.of(read, transform));

        DefaultRuntimeContext context = DefaultRuntimeContext
                .builder("run-t125-obs", "test")
                .config(Map.of("slice", "observability-s12"))
                .build();

        PipelineOptions opts = directRunnerOpts();
        org.apache.beam.sdk.Pipeline beam = pipeline.buildBeam(opts, context);
        PipelineResult.State state = beam.run().waitUntilFinish();

        assertThat(state).isEqualTo(PipelineResult.State.DONE);

        // --- StageMetricsHook: latency recorded for both stages ---
        assertThat(RecordingStageMetricsHook.RECORDED_STAGE_NAMES)
                .as("Both stages must emit a latency record via StageMetricsHook")
                .containsExactlyInAnyOrder("read", "transform");

        // --- StageMetricsHook: error counter is zero on the happy path ---
        assertThat(RecordingStageMetricsHook.ERROR_STAGE_NAMES)
                .as("No errors on the happy path")
                .isEmpty();

        // --- ObservabilityHook: spans opened for both stages ---
        assertThat(RecordingObservabilityHook.SPANS_OPENED)
                .as("Both stages must open a span via ObservabilityHook")
                .containsExactlyInAnyOrder(
                        "culvert.stage/read",
                        "culvert.stage/transform");

        // --- ObservabilityHook: spans closed (finally block ensures this even on error) ---
        assertThat(RecordingObservabilityHook.SPANS_CLOSED)
                .as("Both stages must close their span (closed in finally block)")
                .containsExactlyInAnyOrder(
                        "culvert.stage/read",
                        "culvert.stage/transform");
    }

    /**
     * Verify the StageMetrics payload for the "read" stage: stageName, runId, pipelineId,
     * and the ROWS_PROCESSED_UNKNOWN sentinel (0L).
     *
     * <p>This confirms the full metrics payload flowing through the reference pipeline —
     * not just "did something get recorded", but "are the label dimensions correct?"
     */
    @Test
    void stageMetricsPayloadCarriesCorrectLabelsAndSentinelRowCount() {
        PipelineStage read = new NoOpReadStage();
        PipelineStage transform = new NoOpTransformStage();
        DataflowPipeline pipeline = new DataflowPipeline(
                "reference-e2e-gcp", List.of(read, transform));

        DefaultRuntimeContext context = DefaultRuntimeContext
                .builder("run-t125-labels", "test")
                .build();

        pipeline.buildBeam(directRunnerOpts(), context).run().waitUntilFinish();

        // Find the StageMetrics for the "read" stage.
        StageMetrics readMetrics = RecordingStageMetricsHook.RECORDED_METRICS.stream()
                .filter(m -> "read".equals(m.stageName()))
                .findFirst()
                .orElseThrow(() -> new AssertionError("No StageMetrics recorded for 'read'"));

        assertThat(readMetrics.stageName()).isEqualTo("read");
        assertThat(readMetrics.runId()).isEqualTo("run-t125-labels");
        // pipelineId() default returns runId() (T12.6 contract default).
        assertThat(readMetrics.pipelineId()).isEqualTo(context.pipelineId());
        // rows_processed == 0L is the ROWS_PROCESSED_UNKNOWN sentinel: execute()-based
        // stages do not report element counts (see StageTransform Javadoc).
        assertThat(readMetrics.rowsProcessed())
                .as("rows_processed must be the ROWS_PROCESSED_UNKNOWN sentinel (0L)")
                .isEqualTo(0L);
        assertThat(readMetrics.stageLatencyMs())
                .as("latency must be non-negative")
                .isGreaterThanOrEqualTo(0.0);
        assertThat(readMetrics.errorCount()).isEqualTo(0L);
    }

    /**
     * Error-counter signal: when a stage throws, {@code errorCount == 1} appears in
     * the emitted {@link StageMetrics}, and the span is still closed (finally block).
     *
     * <p>This verifies the error-counter path of the auto-instrumentation fires through
     * the ServiceLoader mechanism — not just on the happy path.
     */
    @Test
    void errorCounterSignalFiredWhenStageThrows() {
        PipelineStage failingStage = new ThrowingReferenceStage("fail-read");
        DataflowPipeline pipeline = new DataflowPipeline(
                "reference-e2e-error", List.of(failingStage));

        DefaultRuntimeContext context = DefaultRuntimeContext
                .builder("run-t125-error", "test")
                .build();

        org.apache.beam.sdk.Pipeline beam = pipeline.buildBeam(directRunnerOpts(), context);
        // DirectRunner propagates stage exceptions out of waitUntilFinish.
        assertThatThrownBy(() -> beam.run().waitUntilFinish())
                .isInstanceOf(RuntimeException.class);

        // StageMetricsHook: error count incremented.
        assertThat(RecordingStageMetricsHook.ERROR_STAGE_NAMES)
                .as("Error counter must fire for the failing stage")
                .containsExactly("fail-read");

        // ObservabilityHook: span still opened and closed (finally block).
        assertThat(RecordingObservabilityHook.SPANS_OPENED)
                .containsExactly("culvert.stage/fail-read");
        assertThat(RecordingObservabilityHook.SPANS_CLOSED)
                .as("Span must be closed even when stage throws (finally block)")
                .containsExactly("culvert.stage/fail-read");
    }

    // --- stage stubs for error-path test ---

    /**
     * A serializable stage that always throws from {@code execute}, used to verify
     * the error-path signals in the reference deployment.
     */
    static final class ThrowingReferenceStage implements PipelineStage, java.io.Serializable {

        private static final long serialVersionUID = 1L;

        private final String stageName;

        ThrowingReferenceStage(String stageName) {
            this.stageName = stageName;
        }

        @Override
        public String name() {
            return stageName;
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
        public void execute(com.enrichmeai.culvert.contracts.RuntimeContext context) {
            throw new RuntimeException("simulated stage failure for T12.5 error-path signal test");
        }
    }
}
