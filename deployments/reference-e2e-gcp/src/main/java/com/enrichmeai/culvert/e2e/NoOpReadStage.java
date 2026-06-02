package com.enrichmeai.culvert.e2e;

import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.RuntimeContext;

import java.io.Serializable;
import java.util.List;

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
 * <p>Implements {@link Serializable} so Beam can serialize this DoFn capture
 * to workers (required by {@code StageTransform}). Named static class (not
 * anonymous) to survive Beam serialization.
 */
public final class NoOpReadStage implements PipelineStage, Serializable {

    private static final long serialVersionUID = 1L;

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

    @Override
    public void execute(RuntimeContext context) {
        // No-op: structural skeleton only. Real read adapters (BigQuery, GCS,
        // Pub/Sub) are wired in sprint-specific slices that append to this stage
        // or replace it with a concrete source.
    }
}
