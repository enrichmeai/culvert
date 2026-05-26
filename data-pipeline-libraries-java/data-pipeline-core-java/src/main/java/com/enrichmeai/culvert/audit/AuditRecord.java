package com.enrichmeai.culvert.audit;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;

/**
 * A single audit event emitted at a pipeline boundary (e.g. an ingestion
 * stage completing).
 *
 * <p>Mirrors the Python {@code AuditRecord} dataclass. The eleven fields are
 * structurally identical; this record is what an {@code AuditEventPublisher}
 * implementation receives.
 *
 * <p>{@code auditHash} is a deterministic content hash that downstream
 * reconciliation uses to dedupe replays. {@code metadata} is the catch-all
 * for stage-specific context (table identifiers, partition keys, etc.).
 *
 * @param runId                    The pipeline run identifier.
 * @param pipelineName             The pipeline that emitted this event.
 * @param entityType               The logical entity ("customer", "transaction", ...).
 * @param sourceFile               Opaque URI of the input artefact (gs://, s3://, ...).
 * @param recordCount              Records processed by this stage.
 * @param processedTimestamp       When the stage completed.
 * @param processingDurationSeconds Wall-clock duration of the stage.
 * @param success                  Whether the stage succeeded.
 * @param errorCount               Records that errored during this stage.
 * @param auditHash                Deterministic content hash for dedup.
 * @param metadata                 Stage-specific context.
 */
public record AuditRecord(
        String runId,
        String pipelineName,
        String entityType,
        String sourceFile,
        long recordCount,
        Instant processedTimestamp,
        double processingDurationSeconds,
        boolean success,
        long errorCount,
        String auditHash,
        Map<String, Object> metadata) {

    public AuditRecord {
        Objects.requireNonNull(runId, "runId");
        Objects.requireNonNull(pipelineName, "pipelineName");
        Objects.requireNonNull(entityType, "entityType");
        Objects.requireNonNull(sourceFile, "sourceFile");
        Objects.requireNonNull(processedTimestamp, "processedTimestamp");
        if (auditHash == null) {
            auditHash = "";
        }
        if (metadata == null) {
            metadata = Map.of();
        } else {
            // Defensive copy to keep the record actually immutable.
            metadata = Map.copyOf(metadata);
        }
    }

    /** Builder convenience for callers who don't want all eleven positional args. */
    public static Builder builder() {
        return new Builder();
    }

    public static final class Builder {
        private String runId;
        private String pipelineName;
        private String entityType;
        private String sourceFile;
        private long recordCount;
        private Instant processedTimestamp;
        private double processingDurationSeconds;
        private boolean success;
        private long errorCount;
        private String auditHash = "";
        private Map<String, Object> metadata = new HashMap<>();

        private Builder() {}

        public Builder runId(String v) { this.runId = v; return this; }
        public Builder pipelineName(String v) { this.pipelineName = v; return this; }
        public Builder entityType(String v) { this.entityType = v; return this; }
        public Builder sourceFile(String v) { this.sourceFile = v; return this; }
        public Builder recordCount(long v) { this.recordCount = v; return this; }
        public Builder processedTimestamp(Instant v) { this.processedTimestamp = v; return this; }
        public Builder processingDurationSeconds(double v) { this.processingDurationSeconds = v; return this; }
        public Builder success(boolean v) { this.success = v; return this; }
        public Builder errorCount(long v) { this.errorCount = v; return this; }
        public Builder auditHash(String v) { this.auditHash = v; return this; }
        public Builder metadata(Map<String, Object> v) { this.metadata = v; return this; }

        public AuditRecord build() {
            return new AuditRecord(runId, pipelineName, entityType, sourceFile,
                    recordCount, processedTimestamp, processingDurationSeconds,
                    success, errorCount, auditHash, metadata);
        }
    }
}
