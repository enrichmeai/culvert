package com.enrichmeai.culvert.contracts;

import java.util.Objects;

/**
 * Immutable snapshot of metrics for a single pipeline stage completion.
 *
 * <p>Carries the three Culvert standard metrics plus the three label
 * dimensions required by {@link StageMetricsHook} implementations:
 *
 * <ul>
 *   <li>{@code pipelineId} — label {@code pipeline_id}</li>
 *   <li>{@code runId}      — label {@code run_id}</li>
 *   <li>{@code stageName}  — label {@code stage_name}</li>
 *   <li>{@code rowsProcessed}  — metric {@code culvert/rows_processed} (CUMULATIVE INT64)</li>
 *   <li>{@code stageLatencyMs} — metric {@code culvert/stage_latency_ms} (GAUGE DOUBLE)</li>
 *   <li>{@code errorCount}     — metric {@code culvert/error_count} (CUMULATIVE INT64)</li>
 * </ul>
 *
 * <p>This is a plain Java record — no GCP or Beam imports — so it can be
 * constructed by any pipeline stage without a dependency on the observability
 * module.
 *
 * @since Sprint 12 / issue #65
 */
public record StageMetrics(
        String pipelineId,
        String runId,
        String stageName,
        long rowsProcessed,
        double stageLatencyMs,
        long errorCount
) {

    /** Validates that the three label fields are non-null. */
    public StageMetrics {
        Objects.requireNonNull(pipelineId, "pipelineId must not be null");
        Objects.requireNonNull(runId,       "runId must not be null");
        Objects.requireNonNull(stageName,   "stageName must not be null");
    }
}
