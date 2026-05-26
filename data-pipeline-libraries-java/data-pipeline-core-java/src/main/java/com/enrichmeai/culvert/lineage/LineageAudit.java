package com.enrichmeai.culvert.lineage;

/**
 * Reconciliation summary attached to a lineage edge.
 *
 * <p>Java equivalent of the Python {@code LineageAudit} TypedDict
 * ({@code total=False}).
 *
 * @param recordCountSource      Records read at the source.
 * @param recordCountDestination Records written at the destination.
 * @param errorCount             Errors observed during the stage.
 * @param auditHash              Deterministic content hash for dedup.
 */
public record LineageAudit(
        long recordCountSource,
        long recordCountDestination,
        long errorCount,
        String auditHash) {

    public LineageAudit {
        if (auditHash == null) auditHash = "";
    }
}
