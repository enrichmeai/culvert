package com.enrichmeai.culvert.gcp.observability;

import org.slf4j.MDC;

import java.util.Objects;
import java.util.function.Supplier;

/**
 * Structured-logging bridge that writes Culvert pipeline context into the
 * SLF4J MDC at the start of a stage execution and clears it afterwards —
 * even when the stage body throws.
 *
 * <h2>Motivation</h2>
 * <p>When Cloud Logging JSON output is active (via {@code logback-cloud.xml}
 * or an equivalent Logback encoder configuration), every log line emitted
 * inside a stage execution carries the three Culvert context fields as
 * top-level JSON fields without any manual {@link MDC} calls in pipeline
 * code.
 *
 * <h2>MDC keys populated</h2>
 * <ul>
 *   <li>{@link #RUN_ID_KEY} — the pipeline run identifier</li>
 *   <li>{@link #STAGE_NAME_KEY} — the name of the executing stage</li>
 *   <li>{@link #PIPELINE_ID_KEY} — the pipeline identifier</li>
 * </ul>
 *
 * <h2>Usage</h2>
 * <pre>{@code
 * // Void stage body (lambda):
 * CulvertMdcPopulator.withStageContext(runId, stageName, pipelineId, () -> {
 *     LOG.info("reading records");
 *     // MDC fields are populated here
 * });
 *
 * // Stage body that returns a value:
 * List<Record> result = CulvertMdcPopulator.withStageContext(runId, stageName, pipelineId, () -> {
 *     return repository.readAll();
 * });
 * }</pre>
 *
 * <p>This class is a pure slf4j/Logback concern — it imports no GCP or
 * Apache Beam types. Sprint-12 deliverable for issue #66.
 */
public final class CulvertMdcPopulator {

    /** MDC key for the pipeline run identifier. */
    public static final String RUN_ID_KEY = "run_id";

    /** MDC key for the stage name. */
    public static final String STAGE_NAME_KEY = "stage_name";

    /** MDC key for the pipeline identifier. */
    public static final String PIPELINE_ID_KEY = "pipeline_id";

    /** Utility class — no instances. */
    private CulvertMdcPopulator() {
        throw new UnsupportedOperationException("utility class");
    }

    /**
     * Execute {@code body}, populating the SLF4J MDC with the three Culvert
     * context keys for its duration.
     *
     * <p>MDC keys are always cleared in a {@code finally} block, so a
     * throwing {@code body} leaves no stale context on the thread.
     *
     * @param runId      The pipeline run identifier. Must not be null.
     * @param stageName  The name of the executing stage. Must not be null.
     * @param pipelineId The pipeline identifier. Must not be null.
     * @param body       The stage body to execute. Must not be null.
     * @param <T>        The return type of the stage body.
     * @return The value returned by {@code body}.
     * @throws NullPointerException     if any argument is null.
     * @throws StageExecutionException  wrapping any checked exception thrown
     *                                  by {@code body}.
     */
    public static <T> T withStageContext(
            String runId,
            String stageName,
            String pipelineId,
            Supplier<T> body) {

        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(stageName, "stageName must not be null");
        Objects.requireNonNull(pipelineId, "pipelineId must not be null");
        Objects.requireNonNull(body, "body must not be null");

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

    /**
     * Void variant of {@link #withStageContext(String, String, String, Supplier)}.
     *
     * <p>Accepts a {@link Runnable} stage body instead of a value-returning
     * {@link Supplier}. MDC context is still cleared in {@code finally}.
     *
     * @param runId      The pipeline run identifier. Must not be null.
     * @param stageName  The name of the executing stage. Must not be null.
     * @param pipelineId The pipeline identifier. Must not be null.
     * @param body       The void stage body to execute. Must not be null.
     * @throws NullPointerException if any argument is null.
     */
    public static void withStageContext(
            String runId,
            String stageName,
            String pipelineId,
            Runnable body) {

        Objects.requireNonNull(body, "body must not be null");
        withStageContext(runId, stageName, pipelineId, () -> {
            body.run();
            return null;
        });
    }

    /**
     * Checked-exception wrapper thrown when the {@code body} supplied to
     * {@link #withStageContext} raises a checked exception. Runtime
     * exceptions propagate unwrapped.
     */
    public static final class StageExecutionException extends RuntimeException {
        private static final long serialVersionUID = 1L;

        public StageExecutionException(Throwable cause) {
            super("stage body threw a checked exception", cause);
        }
    }
}
