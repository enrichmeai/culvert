package com.enrichmeai.culvert.jobcontrol;

import java.time.Instant;
import java.util.Optional;

/**
 * Shape returned by {@code JobControlRepository.getFailedJobs}.
 *
 * <p>Java equivalent of the Python {@code FailedJob} TypedDict
 * ({@code total=False}). Used by retry DAGs and operator dashboards.
 *
 * @param runId         The run identifier of the failed job.
 * @param entityType    The logical entity.
 * @param failureStage  Where in the pipeline the failure occurred.
 * @param errorCode     Structured error code.
 * @param errorMessage  Human-readable error message.
 * @param errorFilePath Opaque URI to quarantined records (empty if no quarantine).
 * @param failedAt      When the job entered the FAILED state.
 * @param retryCount    Number of retries attempted before the final failure.
 */
public record FailedJob(
        String runId,
        String entityType,
        String failureStage,
        String errorCode,
        String errorMessage,
        Optional<String> errorFilePath,
        Instant failedAt,
        int retryCount) {

    public FailedJob {
        if (runId == null) throw new IllegalArgumentException("runId");
        if (entityType == null) throw new IllegalArgumentException("entityType");
        if (failureStage == null) throw new IllegalArgumentException("failureStage");
        if (errorCode == null) errorCode = "";
        if (errorMessage == null) errorMessage = "";
        if (errorFilePath == null) errorFilePath = Optional.empty();
        if (failedAt == null) throw new IllegalArgumentException("failedAt");
    }
}
