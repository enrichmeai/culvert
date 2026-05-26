package com.enrichmeai.culvert.jobcontrol;

import java.time.Instant;
import java.util.Optional;

/**
 * Shape returned by {@code JobControlRepository.getFdpJobStatus}.
 *
 * <p>Java equivalent of the Python {@code FdpJobStatus} TypedDict
 * ({@code total=False}). Reflects the FDP (Foundation Data Product) downstream-of-ODP
 * progress for a single model on a given extract date.
 *
 * @param runId       The pipeline run identifier.
 * @param modelName   The dbt/transformation model name.
 * @param status      Job status string (matches {@link JobStatus#getValue()}).
 * @param recordCount Records produced by the model.
 * @param startedAt   When the model run started (empty if not started).
 * @param completedAt When the model run completed (empty if still running).
 */
public record FdpJobStatus(
        String runId,
        String modelName,
        String status,
        long recordCount,
        Optional<Instant> startedAt,
        Optional<Instant> completedAt) {

    public FdpJobStatus {
        if (runId == null) throw new IllegalArgumentException("runId");
        if (modelName == null) throw new IllegalArgumentException("modelName");
        if (status == null) throw new IllegalArgumentException("status");
        if (startedAt == null) startedAt = Optional.empty();
        if (completedAt == null) completedAt = Optional.empty();
    }
}
