package com.enrichmeai.culvert.contracts;

import com.enrichmeai.culvert.lineage.LineageEvent;

/**
 * Publishes lineage events at pipeline-stage boundaries.
 *
 * <p>Implementations should batch by {@code runId} and emit on stage
 * completion. The default cloud-neutral implementation (added in Stage 3)
 * targets a Marquez or OpenLineage Proxy endpoint. GCP implementation:
 * {@code com.enrichmeai.culvert.gcp.dataplex.DataplexLineagePublisher}.
 *
 * <p>Java mirror of the Python {@code LineageEmitter} Protocol.
 */
@FunctionalInterface
public interface LineageEmitter {

    void emit(LineageEvent event);
}
