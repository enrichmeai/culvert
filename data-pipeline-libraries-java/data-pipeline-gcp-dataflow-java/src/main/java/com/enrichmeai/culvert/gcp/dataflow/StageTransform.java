package com.enrichmeai.culvert.gcp.dataflow;

import com.enrichmeai.culvert.contracts.ObservabilityHook;
import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.RuntimeContext;
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
 * <p>An optional {@code observabilityOverride} field supports test injection of
 * a serializable recording hook. When non-null it takes precedence over
 * {@code context.observability()}. Production callers use {@link #of(PipelineStage, RuntimeContext)},
 * which passes {@code null} (no override) and relies on the context's
 * worker-side registry. T12.4 will reconcile the metrics calls here with the
 * {@code StageMetricsHook} interface introduced in T12.1, swapping
 * {@code histogram}/{@code counter} for typed hook methods.
 *
 * <p>Sprint-9 deliverable (T9.2); auto-instrumentation added in Sprint-12 (T12.3).
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
     * <p>Each execution is wrapped with a trace span, a latency histogram
     * observation, and an error counter — all emitted through the
     * {@link ObservabilityHook} resolved worker-side from
     * {@code context.observability()} (or from {@code observabilityOverride}
     * when a serializable test hook is injected).
     */
    static final class ExecuteStageFn extends DoFn<String, Void> {

        private static final long serialVersionUID = 1L;

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
         * Optional serializable hook override for test injection. When non-null,
         * this hook is used instead of {@code context.observability()}.
         * Production code passes {@code null} here and the context's worker-side
         * registry provides the hook lazily (T10.6 pattern — no new serialized
         * state for the production path).
         *
         * <p>T12.4 reconciliation point: when T12.1's {@code StageMetricsHook}
         * lands on {@code sprint-12}, this override and the metrics calls in
         * {@code processElement} ({@code histogram} + {@code counter}) should be
         * replaced with a typed {@code StageMetricsHook} resolved the same way.
         */
        @SuppressWarnings("serial")
        private final ObservabilityHook observabilityOverride;

        ExecuteStageFn(PipelineStage stage, RuntimeContext context,
                       ObservabilityHook observabilityOverride) {
            this.stage = stage;
            this.context = context;
            this.observabilityOverride = observabilityOverride;
        }

        @ProcessElement
        public void processElement() {
            // Resolve the hook worker-side: mirrors the T10.6 pattern where
            // DefaultRuntimeContext.registry is transient and rebuilt from
            // AutoConfig.discover() after Beam deserialization. No hook is
            // captured at construction time on the production path.
            ObservabilityHook obs = (observabilityOverride != null)
                    ? observabilityOverride
                    : context.observability();

            String stageName = stage.name();
            Map<String, String> stageTags = Map.of("stage", stageName);
            long t0 = System.nanoTime();
            ObservabilityHook.Span span = obs.span("culvert.stage/" + stageName);
            span.setAttribute("culvert.run_id", context.runId());
            try {
                stage.execute(context);
            } catch (RuntimeException e) {
                span.recordException(e);
                obs.counter("culvert.stage.errors", 1, stageTags);
                throw e;
            } finally {
                long elapsedMs = (System.nanoTime() - t0) / 1_000_000L;
                obs.histogram("culvert.stage.latency_ms", elapsedMs, stageTags);
                span.close();
            }
        }
    }
}
