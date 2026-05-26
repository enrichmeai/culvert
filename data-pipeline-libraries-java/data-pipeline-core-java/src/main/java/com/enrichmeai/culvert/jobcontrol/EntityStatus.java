package com.enrichmeai.culvert.jobcontrol;

import java.time.Instant;
import java.util.Optional;

/**
 * Per-entity status snapshot returned by
 * {@code JobControlRepository.getEntityStatus}.
 *
 * <p>Java equivalent of the Python {@code EntityStatus} TypedDict
 * ({@code total=False}). Used by the orchestration layer to decide whether
 * downstream FDP/CDP transforms can fire.
 *
 * @param entityType  The logical entity ("customer", "transaction", ...).
 * @param status      The current job status as a string (matches {@link JobStatus#getValue()}).
 * @param runId       The pipeline run identifier.
 * @param recordCount Records processed (or 0 if not started).
 * @param errorCount  Errors encountered (or 0).
 * @param startedAt   When the job started (empty if not started).
 * @param completedAt When the job completed (empty if still running).
 */
public record EntityStatus(
        String entityType,
        String status,
        String runId,
        long recordCount,
        long errorCount,
        Optional<Instant> startedAt,
        Optional<Instant> completedAt) {

    public EntityStatus {
        if (entityType == null) throw new IllegalArgumentException("entityType");
        if (status == null) throw new IllegalArgumentException("status");
        if (runId == null) throw new IllegalArgumentException("runId");
        if (startedAt == null) startedAt = Optional.empty();
        if (completedAt == null) completedAt = Optional.empty();
    }
}
