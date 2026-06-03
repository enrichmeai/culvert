package com.enrichmeai.culvert.e2e;

import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.finops.CostMetrics;
import com.enrichmeai.culvert.finops.FinOpsTag;

import java.io.Serializable;
import java.util.List;
import java.util.Map;

/**
 * Reference E2E skeleton: stub "transform" stage (T12.0, issue #92).
 *
 * <p>Consumes the logical channel {@code "rows"} (produced by {@link NoOpReadStage})
 * and produces {@code "clean"} with zero real computation.
 *
 * <p>Later sprint slices append real behaviour here:
 * <ul>
 *   <li>S12 T12.5 (#80) — observability hooks (MDC, span, metric recording)</li>
 *   <li>S13 (#81) — FinOps cost tagging</li>
 *   <li>S14 (#82) — data-quality assertions</li>
 * </ul>
 *
 * <p>S13 (#81): emits a per-stage {@link CostMetrics} record via
 * {@link RuntimeContext#finops()} so the {@code cost_by_stage} SQL query
 * (T13.4) can attribute cost to this stage. The {@code "stage"} key is placed
 * in both {@link CostMetrics#labels()} (needed by the {@code UNNEST(labels)}
 * query) and {@link FinOpsTag#extra()} (preserved for tag-level attribution).
 *
 * <p>Implements {@link Serializable} so Beam can serialize this DoFn capture
 * to workers. Named static class (not anonymous) for serialization safety.
 */
public final class NoOpTransformStage implements PipelineStage, Serializable {

    private static final long serialVersionUID = 1L;

    /** Stub bytes-written value representative of a no-op transform. */
    private static final long STUB_BYTES_WRITTEN = 512_000L;

    /** Stub estimated cost in USD: 512 KB written at minimal BigQuery storage cost. */
    private static final double STUB_COST_USD = 0.000002;

    @Override
    public String name() {
        return "transform";
    }

    @Override
    public List<String> inputs() {
        return List.of("rows");
    }

    @Override
    public List<String> outputs() {
        return List.of("clean");
    }

    /**
     * S13 (#81): emits per-stage cost to {@link RuntimeContext#finops()}.
     *
     * <p>In a real deployment this method would call
     * {@link com.enrichmeai.culvert.gcp.bigquery.BigQueryCostTracker#trackJob}
     * after the BigQuery transform job completes. For the structural reference
     * skeleton we synthesise a stub metric with a realistic non-zero cost so
     * the {@code cost_by_stage} assertion holds.
     */
    @Override
    public void execute(RuntimeContext context) {
        // S13: emit per-stage cost record.
        CostMetrics metrics = CostMetrics.builder(context.runId())
                .estimatedCostUsd(STUB_COST_USD)
                .billedBytesWritten(STUB_BYTES_WRITTEN)
                // "stage" in labels so cost_by_stage UNNEST query works.
                .labels(Map.of("stage", name()))
                .build();

        FinOpsTag tag = new FinOpsTag(
                "reference-e2e-gcp",          // system
                context.environment(),         // environment
                "cost-center-reference",       // costCenter
                "culvert-framework-team",      // owner
                context.runId(),               // runId
                Map.of("stage", name())        // extra — also carries stage key
        );

        context.finops().record(metrics, tag);
    }
}
