package com.enrichmeai.culvert.e2e;

import com.enrichmeai.culvert.contracts.FinOpsSink;
import com.enrichmeai.culvert.finops.CostMetrics;
import com.enrichmeai.culvert.finops.FinOpsTag;

import java.io.Serializable;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * Serializable recording {@link FinOpsSink} for the S13 cost/FinOps E2E test.
 *
 * <p>Registered via
 * {@code META-INF/services/com.enrichmeai.culvert.contracts.FinOpsSink}
 * so that {@code AutoConfig.discover()} picks it up during both driver-side
 * context construction and worker-side registry rebuild after Beam serialization.
 * This is necessary because {@link com.enrichmeai.culvert.runtime.DefaultRuntimeContext}'s
 * protocol registry is {@code transient} — any impl registered via
 * {@code context.register(...)} on the driver is NOT shipped to workers; the
 * worker rebuilds its registry from {@link java.util.ServiceLoader}.
 *
 * <p>Events are captured in {@code static} {@link CopyOnWriteArrayList} fields so they
 * survive the DirectRunner's in-process DoFn serialization round-trip. Tests clear the
 * lists in {@code @BeforeEach} and assert post-run.
 *
 * <h2>Design note: not register()-wired</h2>
 * <p>Do NOT wire this via {@code context.register(FinOpsSink.class, new RecordingFinOpsSink())}.
 * That registration only lives on the driver. Worker-side, {@code context.finops()} rebuilds
 * from ServiceLoader; without the services-file entry, it would fall back to the no-op default
 * and no {@code record} call would be captured. The services file makes the recording sink
 * discoverable automatically, matching the {@link RecordingObservabilityHook} pattern.
 *
 * <p>T13.5 / issue #81 — Sprint-13 cost/FinOps slice.
 */
public final class RecordingFinOpsSink implements FinOpsSink, Serializable {

    private static final long serialVersionUID = 1L;

    /**
     * All {@link CostMetrics} records captured across every {@code record()} call.
     * Indexed in call order; tests assert size and content after a run.
     */
    public static final CopyOnWriteArrayList<CostMetrics> RECORDED_METRICS =
            new CopyOnWriteArrayList<>();

    /**
     * All {@link FinOpsTag} records captured alongside the metrics.
     * Parallel list to {@link #RECORDED_METRICS}: {@code RECORDED_TAGS.get(i)}
     * is the tag passed in the same call as {@code RECORDED_METRICS.get(i)}.
     */
    public static final CopyOnWriteArrayList<FinOpsTag> RECORDED_TAGS =
            new CopyOnWriteArrayList<>();

    /**
     * No-arg constructor required by {@link java.util.ServiceLoader}.
     * Also required for Beam DoFn serialization round-trip (worker-side rebuild).
     */
    public RecordingFinOpsSink() {
        // ServiceLoader / Beam serialization entry point.
    }

    @Override
    public void record(CostMetrics metrics, FinOpsTag tags) {
        RECORDED_METRICS.add(metrics);
        RECORDED_TAGS.add(tags);
    }

    /** Reset all static recording surfaces — call from {@code @BeforeEach}. */
    public static void reset() {
        RECORDED_METRICS.clear();
        RECORDED_TAGS.clear();
    }
}
