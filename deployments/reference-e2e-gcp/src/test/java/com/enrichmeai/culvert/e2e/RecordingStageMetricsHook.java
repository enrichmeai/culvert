package com.enrichmeai.culvert.e2e;

import com.enrichmeai.culvert.contracts.StageMetrics;
import com.enrichmeai.culvert.contracts.StageMetricsHook;

import java.io.Serializable;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * Serializable recording {@link StageMetricsHook} for the S12 observability E2E test.
 *
 * <p>Registered via {@code META-INF/services/com.enrichmeai.culvert.contracts.StageMetricsHook}
 * so that {@code AutoConfig.discover()} picks it up during both driver-side context
 * construction and worker-side registry rebuild after Beam serialization. This is the
 * mechanism that proves the "no per-stage boilerplate" epic claim (#47) end-to-end on the
 * reference deployment — the hook is injected automatically, not wired per-stage.
 *
 * <p>Events are captured in {@code static} {@link CopyOnWriteArrayList} fields so they
 * survive the DirectRunner's in-process DoFn serialization round-trip. Tests clear the
 * lists in {@code @BeforeEach} and assert post-run.
 *
 * <p>T12.5 / issue #80 — Sprint-12 observability slice.
 */
public final class RecordingStageMetricsHook implements StageMetricsHook, Serializable {

    private static final long serialVersionUID = 1L;

    /**
     * Stage names for which a latency observation was recorded.
     * One entry per stage per run (errorCount-agnostic).
     */
    public static final CopyOnWriteArrayList<String> RECORDED_STAGE_NAMES =
            new CopyOnWriteArrayList<>();

    /**
     * Full {@link StageMetrics} snapshots emitted by the auto-instrumentation.
     * Allows fine-grained assertions on latency, rowsProcessed, errorCount, etc.
     */
    public static final CopyOnWriteArrayList<StageMetrics> RECORDED_METRICS =
            new CopyOnWriteArrayList<>();

    /** Stage names where {@code errorCount > 0} was recorded. */
    public static final CopyOnWriteArrayList<String> ERROR_STAGE_NAMES =
            new CopyOnWriteArrayList<>();

    /**
     * No-arg constructor required by {@link java.util.ServiceLoader}.
     * Also required for Beam DoFn serialization round-trip (worker-side rebuild).
     */
    public RecordingStageMetricsHook() {
        // ServiceLoader / Beam serialization entry point.
    }

    @Override
    public void recordStageMetrics(StageMetrics metrics) {
        RECORDED_STAGE_NAMES.add(metrics.stageName());
        RECORDED_METRICS.add(metrics);
        if (metrics.errorCount() > 0) {
            ERROR_STAGE_NAMES.add(metrics.stageName());
        }
    }

    /** Reset all static recording surfaces — call from {@code @BeforeEach}. */
    public static void reset() {
        RECORDED_STAGE_NAMES.clear();
        RECORDED_METRICS.clear();
        ERROR_STAGE_NAMES.clear();
    }
}
