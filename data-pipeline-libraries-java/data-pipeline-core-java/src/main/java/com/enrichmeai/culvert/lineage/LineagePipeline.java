package com.enrichmeai.culvert.lineage;

import java.time.Instant;
import java.util.Optional;

/**
 * The pipeline run that produced a lineage edge.
 *
 * <p>Java equivalent of the Python {@code LineagePipeline} TypedDict
 * ({@code total=False}).
 *
 * @param runId        The pipeline run identifier.
 * @param pipelineName The pipeline name.
 * @param stage        The stage that emitted the lineage event.
 * @param startedAt    When the stage started (empty for in-flight events).
 * @param completedAt  When the stage completed (empty for in-flight events).
 */
public record LineagePipeline(
        String runId,
        String pipelineName,
        String stage,
        Optional<Instant> startedAt,
        Optional<Instant> completedAt) {

    public LineagePipeline {
        if (runId == null) throw new IllegalArgumentException("runId");
        if (pipelineName == null) throw new IllegalArgumentException("pipelineName");
        if (stage == null) throw new IllegalArgumentException("stage");
        if (startedAt == null) startedAt = Optional.empty();
        if (completedAt == null) completedAt = Optional.empty();
    }
}
