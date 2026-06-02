package com.enrichmeai.culvert.e2e;

import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.RuntimeContext;

import java.io.Serializable;
import java.util.List;

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
 * <p>Implements {@link Serializable} so Beam can serialize this DoFn capture
 * to workers. Named static class (not anonymous) for serialization safety.
 */
public final class NoOpTransformStage implements PipelineStage, Serializable {

    private static final long serialVersionUID = 1L;

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

    @Override
    public void execute(RuntimeContext context) {
        // No-op: structural skeleton only. Real transform logic (field mapping,
        // enrichment, quality checks) is wired in sprint-specific slices.
    }
}
