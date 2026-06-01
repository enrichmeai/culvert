package com.enrichmeai.culvert.contracts;

/**
 * Cloud-neutral contract for emitting per-stage pipeline metrics.
 *
 * <p>This interface is deliberately narrow: one method, one value type,
 * three fixed metrics ({@code rows_processed}, {@code stage_latency_ms},
 * {@code error_count}) labelled by
 * {@code pipeline_id}/{@code run_id}/{@code stage_name}. The narrowness is
 * intentional — it makes the GCP implementation testable in isolation and
 * keeps Beam wiring (which assembles the call-site) in a separate module
 * (T12.3).
 *
 * <h2>Why a new interface instead of {@link ObservabilityHook}</h2>
 * <p>{@link ObservabilityHook} is a general-purpose primitive surface
 * (arbitrary name + tags). This contract codifies the Culvert-specific
 * semantic: one call per stage completion emits exactly the three Culvert
 * metric series with a fixed label schema. That specificity enables
 * type-safe constructors, clear mock-based testing, and prevents callers
 * from accidentally mis-naming labels.
 *
 * <h2>Placement decision (documented per issue #65 requirement)</h2>
 * <p>This interface lives in {@code data-pipeline-core-java} (the
 * cloud-neutral kernel) with no GCP / Beam / cloud-provider imports.
 * The only implementation ({@code CloudMonitoringMetricsHook}) lives in
 * {@code data-pipeline-gcp-observability-java}. Beam wiring belongs in
 * T12.3 ({@code data-pipeline-gcp-dataflow-java}).
 *
 * @see StageMetrics
 * @since Sprint 12 / issue #65
 */
public interface StageMetricsHook {

    /**
     * Record metrics for a completed pipeline stage.
     *
     * <p>Implementations must not propagate monitoring-backend failures to
     * the caller. If the backend is unavailable the implementation logs and
     * swallows the exception so the pipeline continues uninterrupted.
     *
     * @param metrics Stage metrics snapshot. Must not be null.
     */
    void recordStageMetrics(StageMetrics metrics);
}
