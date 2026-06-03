package com.enrichmeai.culvert.e2e;

import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.finops.CostMetrics;
import com.enrichmeai.culvert.finops.FinOpsTag;

import java.io.Serializable;
import java.util.List;
import java.util.Map;

/**
 * Reference E2E skeleton: stub "read" stage (T12.0, issue #92).
 *
 * <p>Produces the logical output channel {@code "rows"} with zero real I/O.
 * Later sprints replace or wrap this with real adapters:
 * <ul>
 *   <li>S12 T12.5 (#80) — observability (latency/error metrics, MDC context)</li>
 *   <li>S13 (#81) — cost / FinOps tagging via {@link RuntimeContext#finops()}</li>
 *   <li>S14 (#82) — data-quality assertions via a DQ hook</li>
 * </ul>
 *
 * <p>S13 (#81): emits a per-stage {@link CostMetrics} record via
 * {@link RuntimeContext#finops()} so the {@code cost_by_stage} SQL query
 * (T13.4) can attribute cost to this stage. The {@code "stage"} key is placed
 * in both {@link CostMetrics#labels()} (needed by the {@code UNNEST(labels)}
 * query) and {@link FinOpsTag#extra()} (preserved for tag-level attribution).
 *
 * <p>Implements {@link Serializable} so Beam can serialize this DoFn capture
 * to workers (required by {@code StageTransform}). Named static class (not
 * anonymous) to survive Beam serialization.
 */
public final class NoOpReadStage implements PipelineStage, Serializable {

    private static final long serialVersionUID = 1L;

    /** Stub BigQuery bytes-scanned value representative of a no-op read. */
    private static final long STUB_BYTES_SCANNED = 1_000_000L;

    /** Stub estimated cost in USD: 1 MB at BigQuery on-demand pricing (~$0.000005). */
    private static final double STUB_COST_USD = 0.000005;

    @Override
    public String name() {
        return "read";
    }

    @Override
    public List<String> inputs() {
        return List.of();
    }

    @Override
    public List<String> outputs() {
        return List.of("rows");
    }

    /**
     * S13 (#81): emits per-stage cost to {@link RuntimeContext#finops()}.
     *
     * <p>In a real deployment this method would submit the BigQuery job, receive
     * the job statistics, and call {@link com.enrichmeai.culvert.gcp.bigquery.BigQueryCostTracker#trackJob}
     * to build the {@link CostMetrics}. For the structural reference skeleton we
     * synthesise a stub metric with a realistic non-zero cost so the
     * {@code cost_by_stage} assertion holds.
     */
    @Override
    public void execute(RuntimeContext context) {
        // S13: emit per-stage cost record.
        CostMetrics metrics = CostMetrics.builder(context.runId())
                .estimatedCostUsd(STUB_COST_USD)
                .billedBytesScanned(STUB_BYTES_SCANNED)
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
