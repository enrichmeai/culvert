package com.enrichmeai.culvert.gcp.dataflow;

import com.enrichmeai.culvert.contracts.ObservabilityHook;
import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.StageMetrics;
import com.enrichmeai.culvert.contracts.StageMetricsHook;
import org.slf4j.MDC;
import org.apache.beam.sdk.transforms.Create;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.PBegin;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.PDone;

import java.util.Map;
import java.util.Objects;

/**
 * Adapts a Culvert {@link PipelineStage} into a Beam {@link PTransform} that
 * triggers the stage's {@link PipelineStage#execute(RuntimeContext) execute}
 * hook inside the Beam graph.
 *
 * <h2>Shape: {@code PTransform<PBegin, PDone>}</h2>
 *
 * <p>{@link PipelineStage#execute(RuntimeContext)} is {@code void} and
 * side-effecting: a stage reads and writes through the adapters carried on the
 * {@link RuntimeContext} (Source/Sink/Warehouse/BlobStore), it does not map a
 * {@code PCollection} of elements. So this transform does not consume or
 * produce a typed {@code PCollection}; it is rooted at {@link PBegin} and
 * terminates at {@link PDone}. Its single job is to <em>trigger</em> the stage
 * exactly once when the Beam pipeline runs.
 *
 * <p>Richer element-level translation — where a stage maps an input
 * {@code PCollection} to an output {@code PCollection} so Beam can fuse and
 * parallelise the data flow — is deliberately out of Sprint-9 scope. It will
 * arrive when stages expose a Beam-aware element contract (Sprint-future).
 *
 * <h2>Execution semantics: exactly once per run</h2>
 *
 * <p>The transform expands to {@code Create.of(<single trigger token>)}
 * followed by a {@link ParDo} whose {@link DoFn} calls {@code execute} in its
 * {@code @ProcessElement} method. {@code Create.of} a one-element collection
 * yields exactly one element, so {@code execute} is invoked exactly once for
 * the pipeline run. (A {@code DoFn} {@code @Setup}/{@code @StartBundle} hook
 * was rejected: those fire per-instance / per-bundle and a runner may create
 * several instances or bundles, which would run the stage more than once.)
 *
 * <h2>Serialization</h2>
 *
 * <p>The {@link DoFn} captures both the {@link PipelineStage} and the
 * {@link RuntimeContext}; Beam serializes a {@code DoFn} to its workers. Both
 * must therefore be {@code Serializable} at runtime. {@code DefaultRuntimeContext}
 * is; stub and adapter stages used with this transform are expected to be
 * (a stage that closes over non-serializable state cannot run on a distributed
 * runner regardless of this transform).
 *
 * <h2>Auto-instrumentation (T12.3)</h2>
 *
 * <p>Every stage execution is automatically wrapped with:
 * <ul>
 *   <li>A trace span named {@code culvert.stage/<stage-name>}, opened before
 *       {@code execute} and closed in a {@code finally} block (so the span
 *       always ends even on error).</li>
 *   <li>A latency histogram observation ({@code culvert.stage.latency_ms})
 *       recorded in the same {@code finally} block.</li>
 *   <li>An error counter ({@code culvert.stage.errors}) incremented when
 *       {@code execute} throws, before the exception is re-thrown.</li>
 * </ul>
 *
 * <p>The {@link ObservabilityHook} is resolved <em>worker-side</em> (in
 * {@code processElement}) from {@link RuntimeContext#observability()} — never
 * captured into the DoFn at construction time. This mirrors the T10.6 pattern:
 * the hook is backed by {@code DefaultRuntimeContext#registry} which is
 * {@code transient} and rebuilt from {@code AutoConfig.discover()} after
 * Beam deserialization. No new serialized state is added to the DoFn.
 *
 * <p><strong>T12.4 reconciliation (ObservabilityHook vs StageMetricsHook)</strong>:
 * Two hooks coexist with distinct concerns:
 * <ul>
 *   <li>{@link ObservabilityHook} — the general-purpose primitive surface used
 *       for tracing spans (start / end / recordException). The {@code counter}
 *       and {@code histogram} calls previously used for latency+errors have been
 *       moved to the typed hook below.</li>
 *   <li>{@link StageMetricsHook} — the typed Culvert-specific seam (T12.1)
 *       that emits exactly the three standard Culvert metrics
 *       ({@code rows_processed}, {@code stage_latency_ms}, {@code error_count})
 *       with the fixed label schema. Replaces the raw {@code histogram} /
 *       {@code counter} calls that were in T12.3.</li>
 * </ul>
 * Both hooks are resolved worker-side via {@code context.observability()} and
 * {@code context.stageMetrics()}, mirroring the T10.6 transient-registry pattern.
 *
 * <p>MDC population: before each stage execution the three Culvert MDC keys
 * ({@code run_id}, {@code stage_name}, {@code pipeline_id}) are set on the
 * current thread's SLF4J MDC and cleared in the {@code finally} block, so all
 * log lines emitted inside {@code stage.execute} carry the context fields
 * automatically. This mirrors what {@code CulvertMdcPopulator} (T12.2) does,
 * but is applied inline here to avoid adding a module dependency on
 * {@code data-pipeline-gcp-observability-java} from the dataflow adapter.
 *
 * <p>An optional {@code observabilityOverride} field supports test injection of
 * a serializable recording hook for the tracing seam. Production callers use
 * {@link #of(PipelineStage, RuntimeContext)}, which passes {@code null} (no
 * override) and relies on the context's worker-side registry.
 *
 * <p>Sprint-9 deliverable (T9.2); auto-instrumentation added in Sprint-12 (T12.3);
 * StageMetricsHook + MDC wiring in Sprint-12 (T12.4).
 */
public final class StageTransform extends PTransform<PBegin, PDone> {

    private static final long serialVersionUID = 1L;

    /** The single token fed through {@code Create.of} to trigger one execution. */
    private static final String TRIGGER_TOKEN = "execute";

    // Driver-side only: a PTransform is used during pipeline construction,
    // not serialized to workers, so these can be transient (and thus exempt
    // from the serial lint).
    private final transient PipelineStage stage;
    private final transient RuntimeContext context;

    private StageTransform(PipelineStage stage, RuntimeContext context) {
        super("Stage[" + stage.name() + "]");
        this.stage = stage;
        this.context = context;
    }

    /**
     * Wrap a stage + context as a Beam transform.
     *
     * @param stage   The stage to execute. Required; must be serializable to
     *                run on a distributed runner.
     * @param context The runtime context passed to {@code execute}. Required;
     *                must be serializable.
     */
    public static StageTransform of(PipelineStage stage, RuntimeContext context) {
        Objects.requireNonNull(stage, "stage must not be null");
        Objects.requireNonNull(context, "context must not be null");
        return new StageTransform(stage, context);
    }

    @Override
    public PDone expand(PBegin input) {
        PCollection<String> trigger = input.apply(
                "Trigger[" + stage.name() + "]", Create.of(TRIGGER_TOKEN));
        trigger.apply(
                "Execute[" + stage.name() + "]",
                ParDo.of(new ExecuteStageFn(stage, context, null)));
        return PDone.in(input.getPipeline());
    }

    /**
     * The {@link DoFn} that invokes {@link PipelineStage#execute(RuntimeContext)}
     * once per input element. Driven by a one-element {@code Create.of}, so
     * {@code execute} runs exactly once per pipeline run.
     *
     * <p>Each execution is wrapped with:
     * <ul>
     *   <li>SLF4J MDC population ({@code run_id}, {@code stage_name},
     *       {@code pipeline_id}) before {@code execute} and cleared in {@code finally}.</li>
     *   <li>A trace span via {@link ObservabilityHook#span(String)} (start before,
     *       end in {@code finally}).</li>
     *   <li>A {@link StageMetricsHook#recordStageMetrics(StageMetrics)} call in
     *       {@code finally} with the actual latency and error count — replaces the
     *       raw {@code histogram}/{@code counter} calls from T12.3.</li>
     * </ul>
     *
     * <p>Both hooks are resolved worker-side: {@code context.observability()} and
     * {@code context.stageMetrics()} — never captured into the DoFn at construction
     * time on the production path (T10.6 pattern). Optional {@code observabilityOverride}
     * supports test injection of a serializable tracing hook.
     */
    static final class ExecuteStageFn extends DoFn<String, Void> {

        private static final long serialVersionUID = 1L;

        // MDC key constants — mirrors CulvertMdcPopulator (T12.2) without
        // adding a module dependency on data-pipeline-gcp-observability-java.
        private static final String MDC_RUN_ID      = "run_id";
        private static final String MDC_STAGE_NAME  = "stage_name";
        private static final String MDC_PIPELINE_ID = "pipeline_id";

        /**
         * Sentinel value for {@link StageMetrics#rowsProcessed()} when the stage
         * does not expose an element count.
         *
         * <p>{@link com.enrichmeai.culvert.contracts.PipelineStage#execute(RuntimeContext)}
         * is {@code void} — the stage accesses sources/sinks through the
         * {@link RuntimeContext} adapters and does not report element counts back to
         * the framework. A real row count requires element-level translation
         * (PCollection-mapped stages, planned for a future sprint). Until then,
         * 0L is the only Cloud-Monitoring-valid value for a CUMULATIVE INT64
         * metric (negative values are rejected by the API). Callers that need
         * real counts should use the metrics hook directly from within their
         * stage's execute() implementation.
         */
        static final long ROWS_PROCESSED_UNKNOWN = 0L;

        // Serialized to workers by Beam. PipelineStage / RuntimeContext are
        // interface types not declared Serializable, but the concrete impls
        // placed here at runtime must be (DefaultRuntimeContext is). Suppress
        // the serial lint; a non-serializable impl would fail at run() time,
        // which is the correct place for that error to surface.
        @SuppressWarnings("serial")
        private final PipelineStage stage;
        @SuppressWarnings("serial")
        private final RuntimeContext context;

        /**
         * Optional serializable hook override for test injection of the tracing
         * seam ({@link ObservabilityHook}). When non-null, this hook is used
         * instead of {@code context.observability()} for spans. Production code
         * passes {@code null} here and the context's worker-side registry provides
         * the hook lazily (T10.6 pattern — no new serialized state for the
         * production path).
         */
        @SuppressWarnings("serial")
        private final ObservabilityHook observabilityOverride;

        /**
         * Optional serializable hook override for test injection of the metrics
         * seam ({@link StageMetricsHook}). When non-null, this hook is used
         * instead of {@code context.stageMetrics()}. Production code passes
         * {@code null} here (T12.4 — no new serialized state for the production path).
         */
        @SuppressWarnings("serial")
        private final StageMetricsHook stageMetricsOverride;

        ExecuteStageFn(PipelineStage stage, RuntimeContext context,
                       ObservabilityHook observabilityOverride) {
            this(stage, context, observabilityOverride, null);
        }

        ExecuteStageFn(PipelineStage stage, RuntimeContext context,
                       ObservabilityHook observabilityOverride,
                       StageMetricsHook stageMetricsOverride) {
            this.stage = stage;
            this.context = context;
            this.observabilityOverride = observabilityOverride;
            this.stageMetricsOverride = stageMetricsOverride;
        }

        @ProcessElement
        public void processElement() {
            // --- MDC population (T12.4 / T12.6) ---
            String stageName  = stage.name();
            String runId      = context.runId();
            // T12.6: pipeline_id sourced from RuntimeContext.pipelineId() (new contract
            // method with default → runId for backward compatibility). No longer a silent
            // proxy — callers that set a real pipeline name see it reflected here.
            String pipelineId = context.pipelineId();
            MDC.put(MDC_RUN_ID, runId);
            MDC.put(MDC_STAGE_NAME, stageName);
            MDC.put(MDC_PIPELINE_ID, pipelineId);

            // --- Resolve hooks worker-side (T10.6 pattern) ---
            // ObservabilityHook: used for tracing spans.
            ObservabilityHook obs = (observabilityOverride != null)
                    ? observabilityOverride
                    : context.observability();

            // StageMetricsHook: used for the three Culvert-standard metrics
            // (rows_processed, stage_latency_ms, error_count). Resolved
            // lazily from context.stageMetrics() — no hook captured at
            // construction time, no new serialized state (T12.4).
            // stageMetricsOverride is non-null only for test injection.
            StageMetricsHook metricsHook = (stageMetricsOverride != null)
                    ? stageMetricsOverride
                    : context.stageMetrics();

            Map<String, String> stageTags = Map.of("stage", stageName);
            long t0 = System.nanoTime();
            long errorCount = 0L;
            ObservabilityHook.Span span = obs.span("culvert.stage/" + stageName);
            span.setAttribute("culvert.run_id", runId);
            try {
                stage.execute(context);
            } catch (RuntimeException e) {
                span.recordException(e);
                errorCount = 1L;
                throw e;
            } finally {
                long elapsedMs = (System.nanoTime() - t0) / 1_000_000L;
                // Emit the three Culvert-standard metrics via StageMetricsHook.
                // rows_processed uses the ROWS_PROCESSED_UNKNOWN sentinel (0L) because
                // PipelineStage.execute() is void — stages access sources/sinks through
                // the RuntimeContext adapters and do not report element counts back to
                // the framework. A real row count requires element-level translation
                // (PCollection-mapped stages) which is deferred to a future sprint.
                // See StageTransform class Javadoc. The sentinel is semantically
                // meaningful (not an unintentional hard-code) and tested explicitly.
                metricsHook.recordStageMetrics(new StageMetrics(
                        pipelineId,                       // T12.6: real pipelineId from contract
                        runId,
                        stageName,
                        ROWS_PROCESSED_UNKNOWN,           // documented sentinel, not silent 0
                        (double) elapsedMs,
                        errorCount));
                span.close();
                // Clear MDC in the outermost finally so it is always removed
                // even when recordStageMetrics throws (it should not, but defence
                // in depth).
                MDC.remove(MDC_RUN_ID);
                MDC.remove(MDC_STAGE_NAME);
                MDC.remove(MDC_PIPELINE_ID);
            }
        }
    }
}
