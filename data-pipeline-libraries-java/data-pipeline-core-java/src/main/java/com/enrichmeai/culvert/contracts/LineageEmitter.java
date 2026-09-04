package com.enrichmeai.culvert.contracts;

import com.enrichmeai.culvert.lineage.LineageEvent;

/**
 * Publishes lineage events at pipeline-stage boundaries.
 *
 * <p>Implementations should batch by {@code runId} and emit on stage
 * completion.
 *
 * <p><strong>No implementation currently ships.</strong> Earlier javadoc
 * here named a cloud-neutral Marquez / OpenLineage Proxy emitter and a GCP
 * {@code com.enrichmeai.culvert.gcp.dataplex.DataplexLineagePublisher};
 * neither class exists in this reactor. The one GCP implementation that was
 * written, {@code DataCatalogLineageEmitter}, targets Data Catalog, which
 * began its phased shutdown on 2026-06-01, and is deprecated and no longer
 * registered for discovery (Story 1.5).
 *
 * <p>Because nothing is registered, {@code DefaultRuntimeContext.lineage()}
 * resolves to {@code NoOpDefaults.NoOpLineageEmitter} - lineage is silently
 * not emitted. The replacement over the Data Lineage API
 * ({@code datalineage.googleapis.com}) is blocked offline: the
 * {@code google-cloud-datalineage} client is absent from {@code ~/.m2}.
 *
 * <p>Java mirror of the Python {@code LineageEmitter} Protocol.
 */
@FunctionalInterface
public interface LineageEmitter {

    void emit(LineageEvent event);
}
